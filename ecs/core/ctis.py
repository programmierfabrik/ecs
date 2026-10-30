import re
from urllib.parse import quote, unquote

import requests
from django.conf import settings
from django.core.cache import cache
from django.db import transaction

from ecs.core.ctis_render import sorted_applications
from ecs.core.models import Submission, CTRSubmissionForm

# JJJJ-NNNNNN-CC-SS: the EU CT number - year, 6-digit sequence and 2-digit
# check digit - followed by the 2-digit application sequence number, which is
# what makes one revision of a trial. The check digit's computation is a
# CTIS-internal detail we don't have, so we can only validate the shape here.
# The whole string is what the API takes as its clinicalTrialId path segment.
CTIS_NUMBER_RE = re.compile(r'^\d{4}-\d{6}-\d{2}-\d{2}$')

# EcsDocumentDto (part of the OpenAPI schema, not a separate document
# service as first assumed):
#   documentId, name, type, typeCode, section, estimatedPart,
#   estimatedLanguageCode,
#   versions: [{documentUrl, systemVersion, fromDate, submissionDate,
#               version, mimeType, title, comment}]
# with these traps:
#   estimatedPart  - 1 | 2 | null, and « estimated » is meant literally.
#                    Part II's authoritative list is part2s[].documentIds.
#   section        - free text, and overloaded: usually a form section
#                    (« Review section A »), but « Roles: {role} Name:
#                    {product} » for a document belonging to one product.
#                    That string is the only product linkage there is.
#   typeCode       - the stable document type; `type` is its label, and the
#                    same code arrives with differently worded labels.
#   documentUrl    - a UUID handle, not a URL, and it hangs off the version
#                    rather than the document.
# The version fields themselves are still unconfirmed against a real
# payload - EcsDocumentVersionDto's schema was not part of what CTR-ECS sent,
# so ctis_render.py's handling of `versions[]` wants a check against one once
# an import actually carries them.
#   mimeType       - a file extension ('PDF'), not a MIME type.
# ecs.core.ctis_render additionally honours, for ECS-own documents:
#   source         - defaults to 'CTIS',
#   versions[].url - overrides the CTIS download URL.


class CTISError(Exception):
    """The CTR-ECS interface could not be reached or refused to answer."""


class CTISNotConfigured(CTISError):
    """This instance has no CTR-ECS credentials - see ecs.settings."""


class CTISNoInitialApplication(CTISError):
    """The trial carries no Initial (IN) application - see _initial_application."""


# Renew once this much of the token's advertised lifetime has passed, so a
# request never sets off carrying a token that expires mid-flight.
_TOKEN_RENEW_FRACTION = 0.8
_TOKEN_CACHE_KEY = 'ctis_access_token'
_TIMEOUT = 30


def ctis_configured():
    """Whether this instance has CTR-ECS credentials (see ecs.settings)."""
    return bool(
        settings.CTIS_API and
        settings.CTIS_TOKEN_ENDPOINT and
        settings.CTIS_CLIENT_ID and
        settings.CTIS_CLIENT_SECRET
    )


def _request_access_token():
    try:
        response = requests.post(settings.CTIS_TOKEN_ENDPOINT, timeout=_TIMEOUT, data={
            'grant_type': 'client_credentials',
            'client_id': settings.CTIS_CLIENT_ID,
            'client_secret': settings.CTIS_CLIENT_SECRET,
        })
        response.raise_for_status()
        payload = response.json()
        # expires_in is optional in the spec; without it we can only assume a
        # short life and pay for a fresh token on the next call.
        return payload['access_token'], float(payload.get('expires_in') or 60)
    except (requests.RequestException, ValueError, KeyError, TypeError) as e:
        raise CTISError('could not obtain a CTIS access token: {}'.format(e))


def ctis_access_token(renew=False):
    """
    The bearer token for the CTR-ECS API, shared through the cache so the
    workers don't each keep their own. It is cached for 80% of the lifetime
    the token server advertises, and so expires out of the cache before the
    token itself does. Pass renew=True to discard the cached one - the server
    can retire a token early, which only shows up as a 401 on a real call.
    """
    if not ctis_configured():
        raise CTISNotConfigured('the CTR-ECS interface is not configured')
    if not renew:
        access_token = cache.get(_TOKEN_CACHE_KEY)
        if access_token:
            return access_token
    access_token, expires_in = _request_access_token()
    cache.set(_TOKEN_CACHE_KEY, access_token,
        timeout=int(expires_in * _TOKEN_RENEW_FRACTION))
    return access_token


def ctis_request(method, url, **kwargs):
    """
    A CTR-ECS API call carrying the bearer token, retried once with a fresh
    token if the API rejects the cached one. Returns the requests.Response;
    anything but a 2xx raises CTISError.
    """
    kwargs.setdefault('timeout', _TIMEOUT)
    caller_headers = kwargs.pop('headers', None) or {}
    for renew in (False, True):
        headers = dict(caller_headers)
        headers['Authorization'] = 'Bearer ' + ctis_access_token(renew=renew)
        try:
            response = requests.request(method, url, headers=headers, **kwargs)
        except requests.RequestException as e:
            raise CTISError('CTIS request to {} failed: {}'.format(url, e))
        if response.status_code == 401 and not renew:
            continue
        if not response.ok:
            raise CTISError('CTIS request to {} returned {}'.format(
                url, response.status_code))
        return response


def ctis_base_number(ctis_number):
    """
    The "JJJJ-NNNNNN" part identifying the trial across its revisions. The
    check digit is fixed per trial and would identify it just as well, but is
    left out so the value keeps fitting CTRSubmissionForm.ctis_base_number.
    """
    year, sequence, _check_digit, _application_sequence = ctis_number.split('-')
    return f'{year}-{sequence}'


def _filename(response, fallback):
    # RFC 6266: filename* wins over filename when the server sends both, and
    # carries its own percent-encoding.
    disposition = response.headers.get('Content-Disposition') or ''
    match = re.search(r"filename\*=(?:[\w-]+'[\w-]*')?([^;]+)", disposition, re.I)
    if match:
        return unquote(match.group(1).strip().strip('"')) or fallback
    match = re.search(r'filename=("([^"]*)"|[^;]+)', disposition, re.I)
    if match:
        return (match.group(2) or match.group(1)).strip() or fallback
    return fallback


def _initial_application(trial):
    """
    The trial's Initial application (CTIS business key « IN »), the only kind
    ecs.core.ctis_render currently knows how to show - a modification (SM,
    NSM, a subsequent addition of MSC, ...) carries no guarantee that Part I
    or Part II restate the trial in full, so it is not rendered.

    A trial is believed to carry exactly one, but that is not documented as a
    guarantee CTIS enforces - so, defensively, more than one Initial
    application is not an error: the newest of them wins, the same way
    ctis_render picks among applications elsewhere. None at all is an error;
    there is nothing supported to show.
    """
    applications = [a for a in trial.get('applications') or []
                    if isinstance(a, dict)
                    and str(a.get('applicationType') or '').strip().upper() == 'INITIAL']
    if not applications:
        raise CTISNoInitialApplication(
            'the trial carries no Initial (IN) application')
    return sorted_applications({'applications': applications})[0]


def fetch_ctis_study(ctis_number):
    """
    The CTIS trial behind a CTIS number, as
    {"application": {...}, "documents": [...]} - "application" being the trial
    object (EcsTrialDto), narrowed to its Initial application alone, and
    "documents" that application's document entries.

    Only the Initial application is stored - see _initial_application for
    why. Storing the rest alongside it would serve no purpose today and would
    only grow every future payload; ecs.core.ctis_render can go back to
    picking among several once modifications are supported.
    """
    response = ctis_request('GET', '{}/api/v1/ecs/trials/{}'.format(
        settings.CTIS_API, quote(ctis_number, safe='')))
    try:
        trial = response.json()
    except ValueError as e:
        raise CTISError('CTIS returned no readable trial for {}: {}'.format(
            ctis_number, e))
    if not isinstance(trial, dict):
        raise CTISError('CTIS returned no trial object for {}'.format(ctis_number))

    initial = _initial_application(trial)
    trial['applications'] = [initial]
    return {'application': trial, 'documents': initial.get('documents') or []}


def fetch_ctis_document(download_path):
    """
    One CTIS document version, by the download path its own `downloadUrl`
    gave it - e.g. « api/v1/ecs/documents/193821/versions/1 » - as
    {"filename": str, "mime_type": str, "content": bytes}. The endpoint
    answers with the bytes themselves; what the file is called and what type
    it has are only in the response headers.

    Taken as CTIS gave it, not rebuilt from a documentId: nothing pins its
    shape down as stable, and a version's download path is not necessarily
    the bare-document endpoint the OpenAPI spec documents on its own.
    """
    response = ctis_request('GET', '{}/{}'.format(
        settings.CTIS_API, download_path.lstrip('/')))
    # Content-Type may carry a charset, which is not part of the type.
    mime_type = (response.headers.get('Content-Type') or '').split(';')[0].strip()
    # documentId out of its own download path, for a response without a
    # Content-Disposition to name the file by - the path's own last segment
    # would be a version number instead, which names nothing.
    match = re.search(r'documents/([^/]+)', download_path)
    fallback = match.group(1) if match else download_path.rsplit('/', 1)[-1]
    return {
        'filename': _filename(response, fallback),
        'mime_type': mime_type or 'application/octet-stream',
        'content': response.content,
    }


@transaction.atomic
def import_or_sync_ctis_study(ctis_number):
    """
    Fetches a CTIS study and links it to an ECS submission.

    - The exact same CTIS number (incl. revision) was already imported ->
      no-op, return the existing submission unchanged.
    - Same base number (year + sequence), different revision -> merge: add
      a new CTRSubmissionForm version onto the existing submission.
    - Unknown base number -> create a brand new submission.
    """
    existing = CTRSubmissionForm.unfiltered.filter(ctis_number=ctis_number).first()
    if existing:
        return existing.submission

    base_number = ctis_base_number(ctis_number)
    sibling = (
        CTRSubmissionForm.unfiltered.filter(ctis_base_number=base_number)
        .order_by('-created_at').first()
    )
    submission = sibling.submission if sibling else Submission.objects.create()

    data = fetch_ctis_study(ctis_number)
    ctr_form = CTRSubmissionForm.objects.create(
        submission=submission,
        application=data['application'],
        documents=data['documents'],
        ctis_number=ctis_number,
        ctis_base_number=base_number,
    )
    # _post_ctr_submission_form_save only auto-marks a form current when
    # it's the submission's first one ever; a later revision merged in via
    # sync needs to be explicitly promoted to current here.
    ctr_form.mark_current()
    return submission
