import json
import re
from pathlib import Path

from django.db import transaction

from ecs.core.models import Submission, CTRSubmissionForm

_SAMPLE_DIR = Path(__file__).parent

# JJJJ-NNNNNN-XX-Y: year, 6-digit sequence, 2-digit revision (application
# sequence number), 1-digit check digit. The check digit's computation is a
# CTIS-internal detail we don't have - we can only validate the shape here.
CTIS_NUMBER_RE = re.compile(r'^\d{4}-\d{6}-\d{2}-\d$')

# Document-service entries are not part of the trial schema; the interface's
# Kotlin contract (contracts/model/Document.kt) is what defines them:
#   documentId, title, type, typeCode, section, estimatedPart,
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
#   mimeType       - a file extension ('PDF'), not a MIME type.
# ecs.core.ctis_render additionally honours, for ECS-own documents:
#   source         - defaults to 'CTIS',
#   versions[].url - overrides the CTIS download URL.


def ctis_base_number(ctis_number):
    """The "JJJJ-NNNNNN" part identifying the trial, independent of revision."""
    year, sequence, _revision, _check_digit = ctis_number.split('-')
    return f'{year}-{sequence}'


def fetch_ctis_study(ctis_number):
    """
    Mock for the CTR-ECS interface, which is still in development. Accepts
    any well-formed CTIS number and returns a payload shaped like the real
    API is expected to: {"application": {...}, "documents": [...]}, where
    "application" is the CTIS trial object described by the interface's JSON
    schema and "documents" the accompanying document-service entries.

    The payload comes from ctis_sample.json / ctis_sample_documents.json -
    synthesised from the interface schema, not real trial data - with the
    requested CTIS number patched in so the imported study identifies itself
    as the one that was asked for.

    TODO: replace with the real CTR-ECS API client once it's available.
    """
    with open(_SAMPLE_DIR / 'ctis_sample.json') as f:
        trial = json.load(f)
    with open(_SAMPLE_DIR / 'ctis_sample_documents.json') as f:
        documents = json.load(f)

    trial['clinicalTrialId'] = ctis_number
    trial_id = ctis_base_number(ctis_number) + '-' + ctis_number.split('-')[2]
    for application in trial.get('applications') or []:
        application['trialId'] = trial_id

    return {'application': trial, 'documents': documents}


def fetch_ctis_document(document_id):
    """
    Mock for downloading a single CTIS document by id.

    TODO: replace with the real CTR-ECS document-download endpoint once
    it's available.
    """
    content = (
        f'Mock content for document {document_id}\n'
        '(CTR-ECS document API is not yet available)'
    ).encode()
    return {'filename': f'{document_id}.txt', 'mime_type': 'text/plain', 'content': content}


@transaction.atomic
def import_or_sync_ctis_study(ctis_number):
    """
    Fetches a CTIS study (mocked for now) and links it to an ECS submission.

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
