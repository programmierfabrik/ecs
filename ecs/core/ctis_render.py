"""
Turns a CTIS trial payload into the nested tab/section/field structure the
CTR submission templates walk.

The payload is the CTR-ECS interface's trial object (see the interface's JSON
schema): the root carries `clinicalTrialId`, `status` and `applications[]`;
each application carries `part1` (trial-wide, assessed jointly) and
`part2s[]` (one per member state concerned).

Everything produced here is read-only display data - the CTIS path has no
editing. Field labels keep the CTIS English wording (that is what reviewers
see in CTIS itself); section headings and the surrounding ECS chrome are
German.
"""

import re
import unicodedata
from dataclasses import dataclass, field as dc_field
from datetime import date, datetime

from django.utils import translation
from django_countries import countries

from ecs.core import ctis_document_types

# A value CTIS delivered as null/empty. The field stays visible with this
# placeholder so a reviewer can tell nothing was silently dropped.
# An empty value reads as a dash, not as a sentence: a form this dense is
# easier to scan when « nothing here » takes one character.
NOT_PROVIDED = '–'

# The same, inside a table, where CTR-ECS shows a dash per cell and one
# « no data available » line for a table with no rows at all.
EMPTY_CELL = '-'
EMPTY_TABLE = 'No data available'

# A field the integration cannot deliver at all (not part of the interface).
# Never rendered empty, so nobody mistakes it for "CTIS says nothing here".
NOT_RETRIEVABLE = (
    'Could not be retrieved from CTIS. '
    'Open the application in CTIS for further information.'
)

# The ethics commission's own country - preselected in the Part II country
# selector.
OWN_COUNTRY = 'AT'

_WEEKDAYS = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')

# Date formats seen from / plausible for the interface, tried in order after
# ISO. The real API's format is not pinned down yet, so be forgiving and fall
# back to showing the raw string rather than swallowing it.
_DATE_FORMATS = ('%d/%m/%Y', '%d.%m.%Y', '%Y/%m/%d', '%d-%m-%Y')


# ─── view model ──────────────────────────────────────────────────────────
# Dataclasses rather than dicts: Django templates resolve attributes on them
# just as happily, and there is no risk of a key like `items` shadowing a
# dict method.

@dataclass
class Field:
    label: str
    value: object = None            # str, or list[str] for widget='list'
    widget: str = 'text'            # text | textarea | list
    note: str = ''

    @property
    def is_placeholder(self):
        return self.value in (NOT_PROVIDED, NOT_RETRIEVABLE)

    @property
    def text(self):
        """Textarea content - a list widget gets one entry per line."""
        if isinstance(self.value, (list, tuple)):
            return '\n'.join(str(v) for v in self.value)
        return '' if self.value is None else str(self.value)

    @property
    def rows(self):
        """
        Pre-JS row count. ecs.textarea.TextArea resizes to the real content
        height once it runs; this only has to avoid an obviously wrong box.
        """
        return min(max(self.text.count('\n') + 1, 2), 15)


@dataclass
class Message:
    """Standalone prose in a section, e.g. the « not retrievable » notice."""
    value: str = ''
    widget: str = 'message'


@dataclass
class Cell:
    value: object = None
    href: str = ''

    def __post_init__(self):
        # In a table an empty value reads as « - », not as the long field
        # placeholder - that is what CTR-ECS shows.
        if self.value in (None, '', [], NOT_PROVIDED):
            self.value = EMPTY_CELL

    @property
    def is_placeholder(self):
        return self.value in (EMPTY_CELL, NOT_RETRIEVABLE)

    @property
    def lines(self):
        """
        Cell content as lines, so the template renders multi-valued cells
        (active substances, addresses) without having to know the type.
        """
        if isinstance(self.value, (list, tuple)):
            return list(self.value)
        if isinstance(self.value, str):
            return self.value.split('\n')
        return [self.value]


@dataclass
class Table:
    label: str = ''
    columns: list = dc_field(default_factory=list)   # column labels
    rows: list = dc_field(default_factory=list)      # list[list[Cell]]
    note: str = ''
    widget: str = 'table'


@dataclass
class DocVersion:
    system_version: str = ''
    from_date: str = ''
    version: str = ''               # the sponsor's own version, free text
    comment: str = ''
    mime_type: str = ''
    url: str = ''


@dataclass
class DocEntry:
    """
    One document-service entry, flattened. `system_version`, `from_date` and
    `url` are the newest version's - `versions` holds the older ones, which is
    what the « Download latest Version » card shows.
    """
    id: str = ''                    # documentId
    title: str = ''
    type_code: str = ''             # the stable CTIS document-type code
    type: str = ''                  # the payload's own type string, as sent
    category: str = ''              # its label, as shown
    family: str = ''                # the document kind the code is a variant of
    part: object = None             # 1 | 2 | None, as CTIS estimates it
    part_label: str = ''            # as shown, e.g. « Part I »
    section: str = ''               # raw CTIS section, e.g. « Review section A »
    product_role: str = ''          # both parsed out of a « Roles: … Name: … »
    product_name: str = ''          # section, which is the per-product linkage
    language: str = ''
    system_version: str = ''
    from_date: str = ''
    version: str = ''
    comment: str = ''               # the uploader's note on this version
    mime_type: str = ''
    source: str = 'CTIS'
    url: str = ''
    versions: list = dc_field(default_factory=list)

    @property
    def is_product_document(self):
        return bool(self.product_name)


@dataclass
class DocGroup:
    name: str
    documents: list = dc_field(default_factory=list)


@dataclass
class Docs:
    label: str = ''
    groups: list = dc_field(default_factory=list)
    note: str = ''
    widget: str = 'docs'


@dataclass
class ChipGroup:
    """One chip and what it shows: loose entries, whole sections, or both."""
    label: str
    entries: list = dc_field(default_factory=list)
    sections: list = dc_field(default_factory=list)


@dataclass
class Chips:
    """
    A set of like items shown one at a time, picked from a chip strip - what
    the classic centres tab does with investigators. Stacking them instead
    would repeat the same twenty labels once per item.
    """
    groups: list = dc_field(default_factory=list)
    note: str = ''
    widget: str = 'chips'


@dataclass
class Filter:
    key: str
    label: str
    options: list = dc_field(default_factory=list)


@dataclass
class DocList:
    """The flat, filterable « Unterlagen » list - the « I just need the PDF » view."""
    documents: list = dc_field(default_factory=list)
    filters: list = dc_field(default_factory=list)
    widget: str = 'doclist'


@dataclass
class Section:
    name: str = ''
    entries: list = dc_field(default_factory=list)
    note: str = ''
    level: int = 3                  # 3 = section heading, 4 = subsection
    anchor: str = ''


@dataclass
class Pane:
    """One subtab's content."""
    sections: list = dc_field(default_factory=list)


@dataclass
class SubTab:
    slug: str
    name: str
    panes: list = dc_field(default_factory=list)


@dataclass
class Tab:
    slug: str
    name: str
    subtabs: list = dc_field(default_factory=list)

    @property
    def has_subtab_strip(self):
        return len(self.subtabs) > 1


# ─── value formatting ────────────────────────────────────────────────────

def _txt(value):
    """Any scalar as display text, with the empty placeholder for null/''."""
    if value is None:
        return NOT_PROVIDED
    if isinstance(value, bool):
        return _bool(value)
    text = str(value).strip()
    return text or NOT_PROVIDED


def _bool(value):
    """CTIS booleans read as Yes/No, never true/false."""
    if value is None:
        return NOT_PROVIDED
    return 'Yes' if value else 'No'


def _parse_date(value):
    if isinstance(value, (datetime, date)):
        return value.date() if isinstance(value, datetime) else value
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).date()
    except ValueError:
        pass
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _date(value):
    """Dates read « Wed 07.01.2026 », as in the CTR-ECS screenshots."""
    parsed = _parse_date(value)
    if parsed is None:
        # Unrecognised format: show what CTIS sent rather than hide it.
        return _txt(value)
    return '{} {}'.format(_WEEKDAYS[parsed.weekday()], parsed.strftime('%d.%m.%Y'))


def _country(code):
    # In English, like every other value CTIS delivers: django_countries
    # translates by the active language, which is German here, and the
    # reference system names the state « Austria ».
    if not code:
        return NOT_PROVIDED
    with translation.override('en'):
        return str(countries.name(code)) or code


def _sort_text(value):
    """
    A sort key that reads as a list of names does: a leading umlaut or accent
    belongs with its base letter, not after Z, which is where sorting by code
    point puts it. Case is ignored.
    """
    decomposed = unicodedata.normalize('NFKD', str(value or ''))
    return ''.join(c for c in decomposed
                   if not unicodedata.combining(c)).casefold()


def _lines(*parts):
    """Join the non-null parts of a multi-line value (addresses, names)."""
    joined = '\n'.join(str(p).strip() for p in parts if p and str(p).strip())
    return joined or NOT_PROVIDED


def _words(*parts):
    joined = ' '.join(str(p).strip() for p in parts if p and str(p).strip())
    return joined or NOT_PROVIDED


def _amount(value, unit):
    """A quantity plus its unit of measure, e.g. « 400 mg »."""
    if value is None and unit is None:
        return NOT_PROVIDED
    return _words(value, unit)


def _strings(values):
    """A list-widget value: plain strings, or the placeholder when empty."""
    items = [str(v).strip() for v in (values or []) if v is not None and str(v).strip()]
    return items or NOT_PROVIDED


def _joined(value):
    """A list-widget value read back as one « a, b » line."""
    return ', '.join(value) if isinstance(value, list) else value


def _named(values, key='name'):
    """A list-widget value built from the given key of each dict entry."""
    return _strings([v.get(key) if isinstance(v, dict) else v for v in (values or [])])


def _get(mapping, *keys):
    """Walk nested dicts tolerantly - a missing level yields None."""
    current = mapping
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _by_number(items, key='id'):
    """
    CTIS numbers its objectives, criteria, end points and advices, and CTR-ECS
    reads every one of those tables in that order rather than in the payload's.
    The number arrives as a string, so « 10 » has to sort after « 2 ». An entry
    whose number is not a number sorts last and keeps its payload order, the
    way an unparseable date does in `_application_sort_key`.
    """
    def sort_key(pair):
        index, item = pair
        raw = item.get(key) if isinstance(item, dict) else None
        try:
            return (0, int(str(raw).strip()), index)
        except (TypeError, ValueError):
            return (1, 0, index)

    entries = [i for i in (items or []) if isinstance(i, dict)]
    return [i for _, i in sorted(enumerate(entries), key=sort_key)]


# ─── tables ──────────────────────────────────────────────────────────────

def _table(label, columns, rows, note=''):
    # An empty table keeps its heading and columns and gets the same
    # « no information given » row the classic inline formsets use, so a
    # reviewer can tell nothing was dropped.
    return Table(label=label, columns=columns, rows=rows, note=note)


# ─── documents ───────────────────────────────────────────────────────────
# Documents are not part of the trial schema - they come from the CTIS
# document service alongside it. Each entry is a plain dict; every key is
# read with .get() so a partial payload degrades instead of crashing.

# Documents that belong to the application itself rather than to either part.
# Not derivable from `estimatedPart` - a cover letter is estimated into Part I
# like everything else - so the kinds are named.
APPLICATION_DOC_FAMILIES = (
    'COVER_LETTER',
    'DESCRIPTION_OF_MODIFICATION',
    'SUPPORTING_INFORMATION',
    'PROOF_OF_PAYMENT',
)

# CTR-ECS heads two of the four with its own capitalisation rather than the
# whitelist's.
APPLICATION_DOC_LABELS = {
    'SUPPORTING_INFORMATION': 'Supporting Information',
    'PROOF_OF_PAYMENT': 'Proof of Payment',
}

# « Compliance with regulation ». CTIS names the section after the regulation
# and files both kinds under it, which is why they share one heading here
# instead of getting one per kind - the section is what a reviewer looks for,
# and « no document available » has to be answerable once, not twice.
GDPR_DOC_FAMILIES = ('JOINT_CONTROLLERSHIP_AGREEMENT', 'PRIVACY_STATMENT')
GDPR_DOC_LABEL = 'Compliance with Regulation (EU) 2016/679'

# Part I « Protocol information ». CTIS files three kinds under « Clinical
# trial protocol » - the protocol, its synopsis and the DSMB charter - so they
# share one heading; « Study design » is its own.
PROTOCOL_DOC_LABEL = 'Clinical trial protocol'
PROTOCOL_DOC_FAMILIES = (
    'PROTOCOL',
    'SYNOPSIS_OF_THE_PROTOCOL',
    'DATA_SAFETY_MONITORING_BOARD_CHARTER',
)
STUDY_DESIGN_DOC_LABEL = 'Study design'
STUDY_DESIGN_DOC_FAMILIES = ('STUDY_DESIGN',)

# Part I « Scientific advice and Paediatric Investigation Plan ». The advice
# documents get no heading of their own - the group above them is the heading.
# CTIS has no document kind for a PIP itself, only an opinion extract; a PIP's
# own documents arrive through part1.paediatricInvestigationPlan[].documentIds.
SCIENTIFIC_ADVICE_DOC_FAMILIES = ('SUMMARY_OF_SCIENTIFIC_ADVICE',
                                  'SUMMARY_OF_SCIENTIFIC_ADVICE_REPORT')

# Population groups CTIS counts as « incapable of giving consent personally »,
# which is a row of its own rather than part of the recruitment groups.
INCAPABLE_GIVING_CONSENT = ('Minors', 'Incapacitated population')
SUBJECTS_IN_EMERGENCY_SITUATION = 'Subjects in emergency situation'
POPULATION_GROUP_OTHER = 'Other'

# Part I « Trial category », next to the low-intervention answer.
LOW_INTERVENTION_DOC_FAMILIES = ('LOW_INTERVENTION_JUSTIFICATION',)

# Listed once for the whole trial even though the documents hang off the
# individual products.
CONTENT_LABELLING_DOC_FAMILIES = ('CONTENT_LABELLING_OF_THE_IMPS',)
CONTENT_LABELLING_DOC_LABEL = "Content labeling of the IMP's"

# Part I « Products »: the three document groups a product role lists, each
# under one heading of CTR-ECS's own wording rather than one per kind.
PRODUCT_IB_DOC_LABEL = 'Investigator brochure for the medicinal product'
PRODUCT_IB_DOC_FAMILIES = ('INVESTIGATOR_BROCHURE',
                           'SUMMARY_OF_PRODUCT_CHARACTERISTICS')

PRODUCT_IMPD_DOC_LABEL = 'IMPD - Safety and Efficacy'
PRODUCT_IMPD_DOC_FAMILIES = (
    'INVESTIGATIONAL_MEDICAL_PRODUCT_DOSSIER_SAFETY_AND_EFFICACY',
    'SIMPLIFIED_INVESTIGATIONAL_MEDICAL_PRODUCT_DOSSIER_SAFETY_EFFICACY',
)

# CTIS files « Authorisation of manufacturing and import » and « QP GMP
# certification » under this heading. Neither has a code in our type whitelist,
# and neither needs one: CTR-ECS matches these two on the document's own `type`
# string rather than on a code, which is why it finds them without knowing the
# codes either. Matched by prefix, so the « (for publication) » and « (not for
# publication) » qualifier CTIS appends is included without being named.
PRODUCT_GMP_DOC_LABEL = 'Compliance with (GMP) for the Medicinal Product'
PRODUCT_GMP_DOC_TYPE_PREFIXES = ('Authorisation of manufacturing and import',
                                 'QP GMP certification')

# Part II « Documents »: the fixed list of groups a member state's documents
# are sorted into, in this order and under CTR-ECS's own headings rather than
# the whitelist's. Every group is shown even when empty - the office has to be
# able to see which of the eight a sponsor has not filed.
PART2_DOC_GROUPS = (
    ('Recruitment Arrangements', ('RECRUITMENT_ARRANGEMENTS',)),
    ('Subject information and informed consent form',
     ('SUBJECT_INFORMATION_AND_INFORMED_CONSENT_FORM',)),
    ('Suitability of the investigator',
     ('INVESTIGATOR_CURRICULUM_VITAE', 'SUITABILITY_OF_THE_INVESTIGATOR')),
    ('Suitability of the facilities',
     ('SUITABILITY_OF_THE_CLINICAL_TRIAL_SITES_FACILITIES',)),
    ('Proof of insurance cover or indemnification', ('PROOF_OF_INSURANCE',)),
    ('Financial and other arrangements', ('FINANCIAL_ARRANGEMENTS',)),
    ('Compliance with national requirements on Data Protection',
     ('COMPLIANCE_WITH_NATIONAL_REQUIREMENTS_ON_DATE_PROTECTION',)),
    ('Compliance with use of Biological samples',
     ('COMPLIANCE_WITH_USE_OF_BIOLOGICAL_SAMPLES',)),
)

# The ninth group, shown only when the eight above leave something over.
PART2_OTHER_DOC_LABEL = 'Other documents'

# What a viewer who is not office, executive or signing sees of a CTIS study -
# a Spezialist doing a « Spezialistenbewertung », a board member, the presenter,
# a « Beteiligte Partei ». Two things and nothing else: the Synopsis, and the
# Austrian Part II's consent form.
#
# Both are narrowed to the variant CTIS marks « not for publication », which is
# the unredacted one: 7 and 57 are the published Synopsis and its extract, 15
# and 64 the published consent form and its extract.
EXTERNAL_SYNOPSIS_DOC_LABEL = 'Synopsis of the protocol'
EXTERNAL_SYNOPSIS_DOC_FAMILIES = ('SYNOPSIS_OF_THE_PROTOCOL',)
EXTERNAL_SYNOPSIS_DOC_TYPE_CODES = ('308', '344')
EXTERNAL_PART2_DOC_LABEL = 'Subject information and informed consent form'
EXTERNAL_PART2_DOC_FAMILIES = ('SUBJECT_INFORMATION_AND_INFORMED_CONSENT_FORM',)
EXTERNAL_PART2_DOC_TYPE_CODES = ('323', '350')

# « Roles: {role} Name: {product name} » - how the document service names the
# section of a document that belongs to one product of the trial.
_PRODUCT_SECTION_RE = re.compile(
    r'^\s*Roles:\s*(?P<role>.*?)\s+Name:\s*(?P<name>.+?)\s*$')

_PART_LABELS = {1: 'Part I', 2: 'Part II'}


def _doc_type_label(doc):
    """
    The whitelist's label, not the payload's - a payload sometimes drops the
    « (not for publication) » qualifier, and an unknown code has no whitelist
    entry at all, so fall back to whatever it sent.
    """
    return (ctis_document_types.TYPES.get(str(doc.get('typeCode') or ''))
            or doc.get('type') or NOT_PROVIDED)


def _doc_versions(doc):
    """
    The entry's versions, newest system version first.

    An entry with no versions at all is an older/thinner EcsDocumentDto -
    carrying only `documentId` and `name`, from before the interface grew
    per-version download paths. One version standing in for the document
    itself, pointing at the documented bare-document endpoint, is what gives
    such an entry a file to point at.
    """
    versions = [v for v in doc.get('versions') or [] if isinstance(v, dict)]
    if not versions:
        document_id = str(doc.get('documentId') or '')
        return [{'downloadUrl': 'api/v1/ecs/documents/' + document_id}] if document_id else []
    return sorted(versions, key=lambda v: v.get('systemVersion') or 0, reverse=True)


def _doc_file_type(doc):
    """
    « PDF » - the file kind the list shows. A version states it outright; for
    an entry that has none, the document's name is the only place it is
    written down.
    """
    name = doc.get('name') or ''
    suffix = name.rsplit('.', 1)[-1] if '.' in name else ''
    return suffix.upper() if suffix.isalnum() and len(suffix) <= 4 else ''


def _download_path(version):
    """
    A version's CTR-ECS download path, without its leading slash - stripped
    once here so it embeds cleanly into ECS's own /doc/<path> URL instead of
    doubling up into « /doc//api/... ». fetch_ctis_document strips it again
    regardless, but the ECS-facing URL should not carry it either.
    """
    return str(version.get('downloadUrl') or '').lstrip('/')


def document_handles(documents):
    """
    Every key the download route may be asked for. A file hangs off a version,
    not off the document, so there is one key per version - and for an entry
    with no versions, the stand-in `_doc_versions` supplies. Kept beside that
    function so the route trusts exactly the keys the rendered entries link
    to.
    """
    return {
        _download_path(version)
        for doc in documents or []
        for version in _doc_versions(doc)
        if version.get('downloadUrl')
    }


def latest_download_path(doc):
    """
    The download path for one document's newest version - what
    `fetch_ctis_document` needs to retrieve its bytes, for building a zip of
    a study's documents outside the page/route pairing `document_handles` and
    `download_ctr_document` normally go through. Empty for a document with no
    version, or whose newest version already carries its own `url` - an
    ECS-own upload, not a document to fetch from CTIS (see
    `build_document_entries`).
    """
    versions = _doc_versions(doc)
    if not versions:
        return ''
    latest = versions[0]
    return '' if latest.get('url') else _download_path(latest)


def build_document_entries(documents, download_url=None):
    """
    Convert the document service's raw entries into display data, once.

    An entry carries its file only inside `versions[]`, each with its own
    `downloadUrl` - CTR-ECS's own download path for that version, taken as
    given rather than reconstructed, since nothing pins its shape down as
    stable. A version that already carries a `url` keeps it instead (that is
    how ECS-own uploads arrive); those never go through fetch_ctis_document.
    """
    def url_for(version):
        if version.get('url'):
            return version['url']
        key = _download_path(version) if version.get('downloadUrl') else ''
        return download_url(key) if download_url and key else ''

    def as_version(version):
        return DocVersion(
            system_version=version.get('systemVersion') or '–',
            from_date=(_date(version.get('fromDate'))
                       if version.get('fromDate') else '–'),
            version=version.get('version') or '',
            comment=version.get('comment') or '',
            mime_type=(version.get('mimeType') or '').upper(),
            url=url_for(version),
        )

    entries = []
    for doc in documents:
        versions = _doc_versions(doc)
        latest = as_version(versions[0]) if versions else DocVersion()
        part = doc.get('estimatedPart')
        section = doc.get('section') or ''
        product = _PRODUCT_SECTION_RE.match(section)
        entries.append(DocEntry(
            id=str(doc.get('documentId') or ''),
            # `name` is what the CTR-ECS shape calls the title.
            title=doc.get('title') or doc.get('name') or NOT_PROVIDED,
            type_code=str(doc.get('typeCode') or ''),
            type=doc.get('type') or '',
            category=_doc_type_label(doc),
            family=ctis_document_types.FAMILIES.get(
                str(doc.get('typeCode') or ''), ''),
            part=part,
            part_label=_PART_LABELS.get(part) or NOT_PROVIDED,
            section=section,
            product_role=product.group('role') if product else '',
            product_name=product.group('name') if product else '',
            language=(doc.get('estimatedLanguageCode') or '').upper(),
            system_version=latest.system_version,
            from_date=latest.from_date,
            version=latest.version,
            comment=latest.comment,
            mime_type=latest.mime_type or _doc_file_type(doc),
            source=doc.get('source') or 'CTIS',
            url=latest.url,
            versions=[as_version(v) for v in versions[1:]],
        ))
    return entries


def _doc_type_starts_with(doc, prefixes):
    """
    Whether the document's type string begins with one of `prefixes`. The
    payload's own `type` is what is matched - a whitelisted code's label is
    only the fallback, for a payload that sends the code and no type.
    """
    text = (doc.type or doc.category or '').lower()
    return any(text.startswith(p.lower()) for p in prefixes)


def _doc_matches(doc, parts=None, ids=None, product_names=None,
                 is_product=None, exclude_families=(), type_codes=None,
                 type_prefixes=None):
    """
    `parts` is the set of `estimatedPart` values to keep - None is a value of
    its own there, so it has to be passed explicitly rather than meaning
    « any ». `ids` scopes to a Part II's `documentIds`, `product_names` to the
    names one product answers to. `type_codes` scopes below the document kind,
    to single publication variants - CTIS issues « (for publication) » and
    « (not for publication) » as separate codes of the same kind.

    `type_prefixes` selects on the document's own type string instead of its
    kind, which is what CTR-ECS does throughout and the only way to reach a
    kind CTIS issues no whitelisted code for. Case-insensitive and by prefix,
    so the publication qualifier does not have to be spelled out.
    """
    if ids is not None and doc.id not in ids:
        return False
    if type_prefixes is not None and not _doc_type_starts_with(doc, type_prefixes):
        return False
    if parts is not None and doc.part not in parts:
        return False
    if is_product is not None and doc.is_product_document != is_product:
        return False
    if product_names is not None and doc.product_name not in product_names:
        return False
    if type_codes is not None and doc.type_code not in type_codes:
        return False
    if doc.family in exclude_families:
        return False
    return True


def _docs(label, documents, families=None, note='', labels=None, **filters):
    """
    Group documents by document kind - not by `typeCode`, which is one code per
    publication variant and would split « Protocol » into four groups.

    `families` names the kinds to show, in order, and every one is emitted even
    when empty, so a reviewer sees what CTIS holds nothing for rather than a
    silently shorter list. With no `families` only the kinds the matching
    documents actually have are shown, in alphabetical order - the payload's
    own order is not stable enough to read a page by twice. `labels` overrides
    a kind's heading where CTR-ECS words it differently from the whitelist.
    """
    matching = [d for d in documents if _doc_matches(d, **filters)]

    def name_of(key):
        if labels and key in labels:
            return labels[key]
        label = ctis_document_types.FAMILY_LABELS.get(key)
        if label:
            return label
        # An unwhitelisted code is its own group, labelled as it arrived.
        for d in matching:
            if not d.family and d.type_code == key:
                return d.category
        return key

    if families is None:
        keys = sorted({d.family or d.type_code for d in matching}, key=name_of)
    else:
        keys = list(families)

    # Strictly the asked-for kinds: a widget scoped to one kind must not absorb
    # every other document that happens to share its part. Nothing goes missing
    # because « Unterlagen » lists the application's documents in full.
    return Docs(label=label, note=note, groups=[
        DocGroup(name=name_of(key),
                 documents=[d for d in matching
                            if (d.family or d.type_code) == key])
        for key in keys
    ])


def _docs_as_one(name, documents, families=None, **filters):
    """
    Every kind of one CTIS section under a single heading, rather than one
    heading per kind - what « Compliance with regulation » shows. Empty like
    `_docs`, so the heading stays and answers « nothing here » itself.

    With no `families` the kinds are not constrained at all and the filters
    alone select - `type_prefixes` is the one that does, for a section whose
    documents CTIS issues no whitelisted code for.
    """
    return Docs(groups=[DocGroup(name=name, documents=sorted((
        d for d in documents
        if (families is None or (d.family or d.type_code) in families)
        and _doc_matches(d, **filters)
    ), key=lambda d: d.title))])


# ─── application selection ───────────────────────────────────────────────

def _application_sort_key(item):
    index, application = item
    submitted = _parse_date(application.get('submissionDate'))
    # Newest submission first; unknown dates sort last but keep payload order.
    return (submitted is None, -(submitted.toordinal() if submitted else 0), -index)


def sorted_applications(trial):
    """Applications newest-first; the first one is what gets rendered."""
    applications = trial.get('applications') or []
    return [a for _, a in sorted(enumerate(applications), key=_application_sort_key)]


# ─── tab 1: Formular ─────────────────────────────────────────────────────

def formatted_application_id(application):
    """
    CTR-ECS's Application.formattedId - « IN - 5700 » for an initial
    application: the business key that says which kind of application it is,
    then the application's own id.
    """
    if not isinstance(application, dict):
        return ''
    return ' - '.join(
        str(v).strip() for v in (application.get('businessKey'),
                                 application.get('applicationId')) if v)


def _formular_tab(trial, application, documents):
    formatted_id = formatted_application_id(application)

    details = Section(name=_words(formatted_id, 'Details'), level=4, entries=[
        _docs('', documents, APPLICATION_DOC_FAMILIES,
              labels=APPLICATION_DOC_LABELS),
    ])

    # No heading of its own - the document heading names the regulation.
    compliance = Section(level=4, entries=[
        _docs_as_one(GDPR_DOC_LABEL, documents, GDPR_DOC_FAMILIES),
    ])

    # Only the first trial category is shown, which is the one CTR-ECS reads.
    classification = next(
        (c for c in (application.get('part1') or {}).get('classification') or []
         if isinstance(c, dict)), {})

    deferral = [
        Section(name='Deferral publication dates', level=4),
        Section(name='Deferral of clinical trial information', level=5, entries=[
            Field('Short title/ Trial category *',
                  _txt(classification.get('trialCategory'))),
            Field('Justification for trial category / Trial category *',
                  _txt(classification.get('justification'))),
            Field('Justification for deferral published at decision',
                  NOT_RETRIEVABLE),
        ]),
    ]

    return Tab('formular', 'Formular', subtabs=[
        SubTab('formular-main', 'Formular', panes=[
            Pane(sections=[Section(name='Form Details', level=3),
                           details, compliance] + deferral),
        ]),
    ])


# ─── tab 2: MSC (member states concerned) ────────────────────────────────

def _member_states_sections(application, part1, part2s):
    # A country can appear more than once - one member state entry per Part II
    # it has, each with its own subject count. They are paired up in payload
    # order, so the second Austrian row reports the second Austrian Part II
    # rather than both rows repeating the country's total.
    by_country = {}
    for part2 in part2s:
        by_country.setdefault(part2.get('mscCountryCode'), []).append(part2)
    seen_per_country = {}

    # By the country name as it is shown, which is the order CTR-ECS lists the
    # member states in - the payload's own order is the interface's, not one a
    # reviewer can read a page by twice.
    member_states = sorted(
        (m for m in application.get('memberStates') or [] if isinstance(m, dict)),
        key=lambda m: _sort_text(_country(m.get('countryCode'))))

    rows = []
    for member_state in member_states:
        code = member_state.get('countryCode')
        country_part2s = by_country.get(code) or []
        # The nth member state entry of a country takes its nth Part II. A
        # country listed more often than it has Part IIs - one not submitted
        # yet - leaves the surplus rows with nothing to report.
        index = seen_per_country.get(code, 0)
        seen_per_country[code] = index + 1
        own = country_part2s[index:index + 1]
        dates = [d for d in (_parse_date(p.get('submissionDate'))
                             for p in own) if d]
        subjects = [p.get('recruitmentSubjectCount') for p in own
                    if p.get('recruitmentSubjectCount') is not None]
        # A reporting member state is « Selected » once it is settled and
        # « Proposed » while it is still only put forward. A state that is not
        # the RMS answers the question with a dash either way.
        if not member_state.get('isRms'):
            rms = '–'
        elif member_state.get('isProposed'):
            rms = 'Proposed'
        else:
            rms = 'Selected'
        rows.append([
            Cell(_country(code)),
            Cell(rms),
            Cell(_date(min(dates)) if dates else None),
            Cell(_txt(sum(subjects)) if subjects else None),
        ])

    table = _table('Member states concerned', [
        'Member state concerned',
        'RMS',
        'First submission date',
        'Subjects',
    ], rows)

    eea_subjects = sum(p.get('recruitmentSubjectCount') or 0 for p in part2s)
    rest_of_world = part1.get('restOfTheWorldSubjectCount')

    return [
        Section(entries=[
            table,
            Field('Countries outside the European Economic Area', NOT_RETRIEVABLE),
            # Shown twice on purpose - the reference system repeats it below.
            Field('Rest of the world subjects', _txt(rest_of_world)),
        ]),
        Section(name='Estimated total population for the trial', entries=[
            Field('EEA subjects', _txt(eea_subjects)),
            Field('Rest of the world subjects', _txt(rest_of_world)),
            Field('Total subjects', _txt(eea_subjects + (rest_of_world or 0))),
        ]),
    ]


def _msc_tab(application, part1, part2s):
    return Tab('msc', 'MSC', subtabs=[
        SubTab('msc-member-states', 'Member states', panes=[
            Pane(sections=_member_states_sections(application, part1, part2s)),
        ]),
    ])


# ─── tab 3: Part I (trial-wide) ──────────────────────────────────────────
# One page, no third-level tabs: « Trial Details » with its seven groups,
# then « Sponsors », then « Products » - the structure CTR-ECS shows.

# The three registries CTIS abbreviates in `identifiers[].key`, named in full
# the way CTR-ECS names them. Its own spelling of the first two carries two
# typos (« trail », « ClinicalTrails »); they are corrected here rather than
# reproduced on screen.
IDENTIFIER_LABELS = {
    'UTN': 'WHO universal trial number (UTN)',
    'NCT': 'ClinicalTrials.gov identifier (NCT number)',
    'ISRCTN': 'ISRCTN number',
}

# The EudraCT number is not a secondary identifier: it has a row of its own,
# from `eudraCtCode`, and listing it here as well would show it twice.
IDENTIFIER_EXCLUDED_KEY = 'eudract'


def _identifier_fields(part1):
    """
    One row per secondary identifying number, headed by its registry - the
    reference system gives each registry a field of its own rather than
    stacking « registry: number » lines in a single « Identifier » row.
    """
    fields = []
    for identifier in part1.get('identifiers') or []:
        if isinstance(identifier, dict):
            key, number = identifier.get('key'), identifier.get('number')
            if str(key or '').lower() == IDENTIFIER_EXCLUDED_KEY:
                continue
            label = IDENTIFIER_LABELS.get(str(key or '').upper(), key)
            fields.append(Field(_txt(label), _txt(number)))
        else:
            # A registry CTIS names in the entry itself and nowhere else.
            fields.append(Field('Identifier', _txt(identifier)))
    # An empty section would drop the heading's question altogether.
    return fields or [Field('Identifier', NOT_PROVIDED)]


def _trial_identifiers_sections(part1):
    # The asterisks are CTIS's own « required » markers, part of the label.
    entries = [
        Field('Full title (English) *', _txt(part1.get('title')),
              widget='textarea'),
        Field('Public title (English) *', _txt(part1.get('publicTitle')),
              widget='textarea'),
    ]
    # A trial without a protocol code shows no row at all, rather than an
    # empty one - CTR-ECS omits it.
    if part1.get('protocolCode'):
        entries.append(Field('Protocol code', _txt(part1.get('protocolCode'))))

    return [
        Section(name='Trial Identifiers', level=4, entries=entries),
        Section(name='Secondary identifying numbers', level=5,
                entries=_identifier_fields(part1) + [
            Field('EudraCT number', _txt(part1.get('eudraCtCode'))),
        ]),
    ]


def _endpoint_table(part1, is_primary, label):
    # Two tables like CTIS itself, rather than one with a « Primary » column.
    return _table(label.replace(' (English)', ''), [
        'New ID',
        label,
    ], [
        [Cell(_txt(e.get('sequenceNumber'))), Cell(_txt(e.get('description')))]
        for e in _by_number(part1.get('endpoints'), 'sequenceNumber')
        if bool(e.get('isPrimary')) is is_primary
    ])


def _subject_gender(part1):
    """
    The two sex flags read as one « Subject gender » value, lower case and
    female first, as CTIS words it.
    """
    female = part1.get('containsFemaleSubjects')
    male = part1.get('containsMaleSubjects')
    if female is None and male is None:
        return NOT_PROVIDED
    genders = [g for g, included in (('female', female), ('male', male))
               if included]
    return ', '.join(genders) or NOT_PROVIDED


def _trial_information_sections(part1, documents):
    low_intervention = part1.get('isLowInterventionTrial')
    category = NOT_PROVIDED if low_intervention is None else (
        'Low intervention trial' if low_intervention
        else 'No low intervention trial'
    )

    scopes = [s for s in part1.get('trialScopes') or [] if isinstance(s, dict)]
    scope_descriptions = [s.get('description') for s in scopes
                          if s.get('description')]

    groups = [g for g in part1.get('recruitmentPopulationGroups') or []
              if isinstance(g, dict)]

    def group_named(name):
        return next((g for g in groups
                     if str(g.get('name') or '').lower() == name.lower()), None)

    incapable = [g for g in groups if str(g.get('name') or '').lower()
                 in [n.lower() for n in INCAPABLE_GIVING_CONSENT]]
    recruitment = [g for g in groups if g not in incapable]

    # CTIS can send the same age range twice, spelled differently - « 18-64
    # years » and « 18-64 Years » are one range, and CTR-ECS shows it once.
    seen = set()
    age_ranges = []
    for age_range in part1.get('ageRanges') or []:
        text = str(age_range).strip() if age_range is not None else ''
        if not text or text.lower() in seen:
            continue
        seen.add(text.lower())
        age_ranges.append(text)

    population = [
        Field('Age range', _joined(_strings(age_ranges))),
        Field('Age range secondary identifier',
              _strings(part1.get('ageRangeSecondaryIdentifiers')),
              widget='list'),
        Field('Subject gender', _subject_gender(part1)),
        Field('Clinical trial group', NOT_RETRIEVABLE),
        Field('Is vulnerable population?', NOT_RETRIEVABLE),
        Field('Recruitment population group', _named(recruitment),
              widget='list'),
        Field('Subjects incapable of giving consent personally',
              _named(incapable), widget='list'),
    ]
    # Two groups carry a free-text explanation, shown only when the group is
    # one of the trial's own.
    emergency = group_named(SUBJECTS_IN_EMERGENCY_SITUATION)
    if emergency is not None:
        population.append(Field('Emergency situation description',
                                _txt(emergency.get('explanation'))))
    other = group_named(POPULATION_GROUP_OTHER)
    if other is not None:
        population.append(Field('Other description',
                                _txt(other.get('explanation'))))

    return [
        Section(name='Trial information', level=4),
        Section(name='Trial Category', level=5, entries=[
            Field('Category', category),
            _docs('Attachment of justification of low interventional '
                  'clinical trial', documents, LOW_INTERVENTION_DOC_FAMILIES),
            Field('Trial Phase', _txt(part1.get('phase'))),
        ]),
        Section(name='Medical Condition', level=5, entries=[
            _table('', [
                'Medical condition (english)',
                'Is the medical condition considered to be a rare disease',
            ], [
                [Cell(_txt(m.get('description'))), Cell(_bool(m.get('isRareDisease')))]
                for m in part1.get('medicalConditions') or []
            ]),
            Field('Therapeutic area', _strings(part1.get('therapeuticAreas')),
                  widget='list'),
            Field('MedDRA codes', NOT_RETRIEVABLE),
        ]),
        Section(name='Main Objective', level=5, entries=[
            # One value, comma-separated - « Therapy, Safety » - as the
            # reference system words a trial's scope.
            Field('Trial Scope', _joined(_named(scopes))),
            # Only asked about when a scope actually describes itself, which
            # is the « Other » scope.
            ] + ([Field('Other scope description',
                        _strings(scope_descriptions), widget='list')]
                 if scope_descriptions else []) + [
            Field('Main objective (English)', _txt(part1.get('mainObjective')),
                  widget='textarea'),
        ]),
        Section(name='Secondary Objective', level=5, entries=[
            _table('', [
                'New ID',
                'Secondary objective (English)',
            ], [
                [Cell(_txt(o.get('id'))), Cell(_txt(o.get('description')))]
                for o in _by_number(part1.get('secondaryObjectives'))
            ]),
        ]),
        Section(name='Eligibility criteria', level=5, entries=[
            _table('Principal inclusion criteria', [
                'New ID',
                'Principal inclusion criteria (English)',
            ], [
                [Cell(_txt(c.get('id'))), Cell(_txt(c.get('description')))]
                for c in _by_number(part1.get('principalInclusionCriteria'))
            ]),
            _table('Principal exclusion criteria', [
                'New ID',
                'Principal exclusion criteria (English)',
            ], [
                [Cell(_txt(c.get('id'))), Cell(_txt(c.get('description')))]
                for c in _by_number(part1.get('principalExclusionCriteria'))
            ]),
        ]),
        Section(name='End points', level=5, entries=[
            _endpoint_table(part1, True, 'Primary end points (English)'),
            _endpoint_table(part1, False, 'Secondary end points (English)'),
        ]),
        Section(name='Trial duration', level=5, entries=[
            Field('Estimated recruitment start date in EEA',
                  _date(part1.get('estimatedRecruitmentStartDate'))),
            Field('Estimated end of trial date in EEA',
                  _date(part1.get('estimatedEndDate'))),
            Field('Estimated global end date of the trial',
                  _date(part1.get('estimatedGlobalEndDate'))),
        ]),
        Section(name='Source of monetary support or material support', level=5,
                entries=[
            _table('', ['Organisation name'], [
                [Cell(_txt(source))]
                for source in part1.get('monetaryMaterialSupport') or []
            ]),
        ]),
        Section(name='Population of trial subjects', level=5, entries=population),
    ]


def _protocol_information_sections(documents):
    return [Section(name='Protocol information', level=4, entries=[
        _docs_as_one(PROTOCOL_DOC_LABEL, documents, PROTOCOL_DOC_FAMILIES),
        _docs_as_one(STUDY_DESIGN_DOC_LABEL, documents,
                     STUDY_DESIGN_DOC_FAMILIES),
    ])]


def _scientific_advice_sections(part1, documents):
    # The interface schema declares scientificAdvices[] and
    # paediatricInvestigationPlan[] without an item shape, so read both
    # tolerantly: a dict contributes its known keys, anything else is shown
    # as-is rather than dropped.
    advices = part1.get('scientificAdvices') or []
    # Sorted by the id CTIS numbers them with, as CTR-ECS reads the table;
    # anything that is not a dict has no id to sort on and goes last.
    rows = []
    for advice in _by_number(advices):
        rows.append([
            Cell(_txt(advice.get('id'))),
            Cell(_txt(advice.get('advice')
                      or advice.get('competentAuthorities')
                      or advice.get('competentAuthority'))),
        ])
    for advice in advices:
        if not isinstance(advice, dict):
            rows.append([Cell(None), Cell(_txt(advice))])

    # The advice documents get no heading - « Scientific advice » above them
    # is the heading.
    plans = [p for p in part1.get('paediatricInvestigationPlan') or []
             if isinstance(p, dict)]
    pip_entries = []
    for plan in plans:
        pip_entries.append(Field('EMA paediatric investigation number',
                                 _txt(plan.get('number'))))
        pip_entries.append(_docs('', documents,
                                 ids=set(plan.get('documentIds') or [])))

    return [
        Section(name='Scientific advice and Paediatric Investigation Plan (PIP)',
                level=4),
        Section(name='Scientific advice', level=5, entries=[
            _table('', [
                'ID',
                'Competent authorities that have provided scientific advice',
            ], rows),
            _docs_as_one('', documents, SCIENTIFIC_ADVICE_DOC_FAMILIES),
        ]),
        # A trial with no plan shows the heading and nothing under it, which is
        # how CTR-ECS says « none registered ».
        Section(name='Paediatric investigation plan', level=5,
                entries=pip_entries),
    ]


def _associated_trials_sections(part1):
    return [Section(name='Associated clinical trials', level=4, entries=[
        _table('', [
            'EU CT Number',
            'Title',
            'Sponsor',
        ], [
            [Cell(_txt(t.get('trialId'))), Cell(_txt(t.get('title'))),
             Cell(_txt(t.get('sponsorName')))]
            for t in part1.get('associatedTrials') or []
        ]),
    ])]


def _sponsor_active(sponsor):
    """
    Whether the sponsor's active period covers today, both ends inclusive - a
    period that has not started yet is as inactive as one that has ended. A
    sponsor with no `activeFrom` at all is taken as active, the way CTR-ECS
    takes it: the interface leaves the field empty for the trial's own sponsor.
    """
    active_from = _parse_date(sponsor.get('activeFrom'))
    active_to = _parse_date(sponsor.get('activeTo'))
    if active_from is None:
        return True
    today = date.today()
    return active_from <= today and (active_to is None or active_to >= today)


def _sponsor_sections(application):
    sponsors = application.get('sponsors') or []
    # One organisation can arrive more than once - CTR-ECS shows it once per
    # name and country, and the contact-point chips below follow the same list.
    seen = set()
    unique = []
    for sponsor in sponsors:
        key = (sponsor.get('name'), sponsor.get('country'))
        if key in seen:
            continue
        seen.add(key)
        unique.append(sponsor)
    sponsors = unique

    rows = []
    for sponsor in sponsors:
        commercial = sponsor.get('isCommercial')
        rows.append([
            Cell(_txt(sponsor.get('name'))),
            Cell(_txt(sponsor.get('organisationType'))),
            Cell(_country(sponsor.get('country')) if sponsor.get('country') else None),
            # « Type » is the commercial flag and « Status » the active period -
            # CTR-ECS shows neither as a raw boolean or a date range.
            Cell(None if commercial is None else
                 ('Commercial' if commercial else 'Non-commercial')),
            Cell('Active' if _sponsor_active(sponsor) else 'Not active'),
            Cell(_txt(sponsor.get('legalRepresentative'))),
            Cell(_txt(sponsor.get('scientificContactPoint'))),
            Cell(_txt(sponsor.get('publicContactPoint'))),
            Cell(_txt(sponsor.get('thirdPartyCount'))),
        ])

    sections = [Section(name='Sponsors', level=3, entries=[
        _table('', [
            'Name',
            'Organisation type',
            'Country',
            'Type',
            'Status',
            'Legal representative',
            'Scientific contact point',
            'Public contact point',
            'Third parties',
        ], rows),
    ])]

    # The union contact point is who the authorities address about the trial,
    # and the payload names one sponsor for it - the others send
    # `unionContactPoint: null`. Shown as a plain section rather than one chip
    # per sponsor: a chip strip suggests a choice to make, and the block names
    # the organisation it belongs to in its first field anyway.
    for sponsor in sponsors:
        contact = sponsor.get('unionContactPoint')
        if not contact:
            continue
        sections.append(Section(name='Contact Point for Union', level=4, entries=[
            Field('Organisation name',
                  _txt(contact.get('organisationName'))),
            # The four address lines as one line, comma-joined - CTR-ECS
            # shows the whole address once and then line by line.
            Field('Address', _txt(', '.join(
                str(contact.get(k)).strip()
                for k in ('addressLine1', 'addressLine2',
                          'addressLine3', 'addressLine4')
                if contact.get(k) and str(contact.get(k)).strip()))),
            # The asterisks are CTIS's own « required » markers, kept as
            # part of the label the way CTR-ECS shows them.
            Field('Address line 1*', _txt(contact.get('addressLine1'))),
            Field('Address line 2', _txt(contact.get('addressLine2'))),
            Field('Address line 3', _txt(contact.get('addressLine3'))),
            Field('Address line 4', _txt(contact.get('addressLine4'))),
            Field('Town/City*', _txt(contact.get('city'))),
            Field('Post code', _txt(contact.get('postCode'))),
            Field('Country*', _country(contact.get('country'))
                  if contact.get('country') else NOT_PROVIDED),
            Field('Functional contact point name',
                  _txt(contact.get('functionalContactPointName'))),
            Field('Firstname*', _txt(contact.get('firstName'))),
            Field('Lastname*', _txt(contact.get('lastName'))),
            Field('Phone*', _txt(contact.get('phone'))),
            Field('Email*', _txt(contact.get('email'))),
        ]))
    return sections


def _product_names(role, product):
    """
    The names one product answers to. A document links to its product by name,
    in its « Roles: … Name: … » section; which of the two the interface uses
    there is not pinned down, so match on either rather than guess.
    """
    details = product.get('productDetails') or {}
    return {n for n in (role.get('description'),
                        details.get('medicinalProductName')) if n}


def _product_title(role, product):
    """
    What CTR-ECS heads the product section with. `role.description` carries
    the name for an authorised comparator, whose productDetails are otherwise
    largely empty.
    """
    details = product.get('productDetails') or {}
    return _txt(role.get('description') or details.get('medicinalProductName'))


def _product_summary_row(product):
    details = product.get('productDetails') or {}
    authorisation = product.get('authorisationDetails') or {}
    substances = product.get('substances') or []
    return [
        Cell(_txt(details.get('medicinalProductNumber'))),
        # One column, country then number - « NO EU/1/14/916/033 ».
        Cell(_words(authorisation.get('marketingAuthorisationCountry'),
                    authorisation.get('marketingAuthorisationNumber'))),
        Cell(_txt(details.get('authorisationStatus'))),
        Cell(_txt(details.get('medicinalProductName'))),
        Cell(_txt(details.get('pharmaceuticalForm'))),
        Cell(_txt(details.get('strength'))),
        Cell(_txt(product.get('sponsorProductCode'))),
        Cell(_strings([s.get('activeSubstanceName') for s in substances])),
        Cell(_strings([s.get('substanceEvCode') for s in substances])),
        Cell(_txt(product.get('atcName'))),
        Cell(_txt(product.get('atcCode'))),
        Cell(_txt(product.get('atcLevel'))),
    ]


def _advanced_therapy_fields(therapy):
    gene = therapy.get('geneTherapyDescription') or {}
    somatic = therapy.get('somaticCellTherapy') or {}
    tissue = therapy.get('tissueEngineeredMedicinalProduct') or {}

    fields = [Field('Therapy type', _txt(therapy.get('advancedTherapyTypeName')))]
    # Only the therapy's own kind contributes rows - a gene therapy has no
    # somatic cell origin to leave blank.
    if gene:
        fields += [
            Field('Gene of interest', _txt(gene.get('geneOfInterest'))),
            Field('Type of gene transfer product',
                  _txt(gene.get('typeGeneTransferProduct'))),
            Field('Gene therapy type', _txt(gene.get('geneTherapyType'))),
            Field('Additional description', _txt(gene.get('additionalDescription'))),
            Field('Genetically modified cells present?',
                  _txt(gene.get('geneticallyModifiedCellsPresent'))),
            Field('Specify type of cells', _txt(gene.get('specifyTypeCells'))),
            Field('Origin of the genetically modified cells',
                  _txt(gene.get('originGeneticallyModifiedCells'))),
            Field('Species origin for the xenogeneic cells',
                  _txt(gene.get('speciesOriginXenogeneicCells'))),
        ]
    if somatic:
        fields += [
            Field('Somatic cell origin', _txt(somatic.get('somaticCellOrigin'))),
            Field('Somatic cell type', _txt(somatic.get('somaticCellType'))),
            Field('Species origin for the xenogeneic cell',
                  _txt(somatic.get('speciesOriginXenogeneicCell'))),
            Field('Specify type of differentiated cells',
                  _txt(somatic.get('specifyOtherSomaticCellType'))),
        ]
    if tissue:
        fields += [
            Field('Tissue engineered cell type',
                  _txt(tissue.get('tissueEngineeredCellType'))),
            Field('Origin of the engineered tissue',
                  _txt(tissue.get('originEngineeredTissue'))),
            Field('Cell specification', _txt(tissue.get('cellSpecification'))),
            Field('Tissue Engineered xenogeneic species of origin',
                  _txt(tissue.get('tissueEngineeredXenogeneicSpecies'))),
        ]
    return fields


def _product_detail_sections(product):
    details = product.get('productDetails') or {}
    dosage = product.get('dosage') or {}
    authorisation = product.get('authorisationDetails') or {}
    characteristics = product.get('characteristics') or []
    substances = product.get('substances') or []
    therapies = product.get('advancedTherapies') or []

    sections = [
        Section(name='Details for Product with EU MP number {}'.format(
            _txt(details.get('medicinalProductNumber'))), level=5),
        Section(name='Medicinal Product Details', level=6, entries=[
            Field('Medicinal name', _txt(details.get('medicinalProductName'))),
            Field('EU medicinal product number/medicinal product unique ID',
                  _txt(details.get('medicinalProductNumber'))),
            Field('Pharmaceutical form', _txt(details.get('pharmaceuticalForm'))),
            Field('Strength', _txt(details.get('strength'))),
            Field('Medicinal product other name',
                  _txt(details.get('medicinalProductOtherName'))),
            Field('Is this a specific paediatric formulation?',
                  _txt(details.get('paediatricFormulation'))),
            Field('Authorisation status', _txt(details.get('authorisationStatus'))),
            Field('Medicinal product role in trial',
                  _txt(details.get('medicinalProductRoleInTrial'))),
            Field("Sponsor's product code",
                  _txt(details.get('sponsorProductCodeEdit'))),
        ]),
        Section(name='Product characteristics', level=6, entries=[
            Field('Medicinal product characteristics',
                  _strings([c.get('name') for c in characteristics]),
                  widget='list'),
            Field('Other medicinal product',
                  _strings([c.get('description') for c in characteristics]),
                  widget='list'),
        ]),
        Section(name='Dosage and administration details', level=6, entries=[
            Field('Route of administration', _txt(dosage.get('routeAdministration'))),
            Field('Maximum duration of treatment',
                  _txt(dosage.get('maxTreatmentPeriod'))),
            Field('Maximum Total dose allowed',
                  _txt(dosage.get('maxTotalDoseAmount'))),
            Field('Total dose unit of measure',
                  _txt(dosage.get('maxTotalDoseUomEvCode'))),
            Field('Maximum daily dose allowed',
                  _txt(dosage.get('maxDailyDoseAmount'))),
            Field('Daily dose unit of measure',
                  _txt(dosage.get('maxDailyDoseUomEvCode'))),
        ]),
        Section(name='Information about the modification of the Medicinal Product',
                level=6, entries=[
            Field('Has the medicinal product been modified in relation to its '
                  'Marketing Authorisation?',
                  _txt(product.get('productChangedRelation'))),
        ]),
        Section(name='Product Classification', level=6, entries=[
            Field('Anatomic therapeutic chemical (ATC) code',
                  _txt(product.get('atcCode'))),
            Field('Anatomic therapeutic chemical (ATC) name',
                  _txt(product.get('atcName'))),
            Field('Anatomic therapeutic chemical (ATC) level',
                  _txt(product.get('atcLevel'))),
        ]),
        Section(name='Product authorisation details', level=6, entries=[
            Field('MA holder', _txt(authorisation.get('maHolder'))),
            Field('Marketing authorisation country',
                  _txt(authorisation.get('marketingAuthorisationCountry'))),
            Field('Marketing authorisation number',
                  _txt(authorisation.get('marketingAuthorisationNumber'))),
            Field('Centralised procedure/MRP/DCP/registration procedure number',
                  _txt(authorisation.get('centralisedProcedureNumber'))),
        ]),
        Section(name='Orphan Designation', level=6, entries=[
            Field('Does this product have an orphan drug designation',
                  _txt(product.get('orphanDrugDesigner'))),
        ]),
        Section(name='Active substance', level=6, entries=[
            field
            for substance in substances
            for field in (
                Field('Active substance name',
                      _txt(substance.get('activeSubstanceName'))),
                Field('Classification', _txt(substance.get('classification'))),
                Field('Active substance name synonyms',
                      _txt(substance.get('activeSubstanceNameSynonyms'))),
                Field('Active substance other descriptive name',
                      _txt(substance.get('otherDescriptiveName'))),
                Field('EU active substance code',
                      _txt(substance.get('substanceEvCode'))),
                Field('Strength', _txt(substance.get('strength'))),
                Field('Status', _txt(substance.get('status'))),
            )
        ]),
        # No heading of its own - the field below carries the wording.
        Section(level=6, entries=(
            [field for therapy in therapies
             for field in _advanced_therapy_fields(therapy)]
            # A product that is no ATMP still answers the question.
            or [Field('Advanced Therapy Medicinal Product', NOT_PROVIDED)]
        )),
        Section(name='Device associated with medicinal product', level=6, entries=[
            _table('', [
                'Product used in combination with a device',
                'Product ID',
                'Device Trade Name',
                'Description of the device',
                'Type of device',
                'Device has CE mark',
                'Device notified body',
            ], [
                [Cell(_txt(d.get('productUseDeviceName'))),
                 Cell(_txt(d.get('productId'))),
                 Cell(_txt(d.get('tradeName'))),
                 Cell(_txt(d.get('description'))),
                 Cell(_txt(d.get('deviceTypeName'))),
                 Cell(_bool(d.get('hasCeMark'))),
                 Cell(_txt(d.get('notifiedBody')))]
                for d in product.get('devices') or []
            ]),
        ]),
    ]
    return sections


def _product_chip(role, documents):
    """
    One chip per medicinal product role: its products in one summary table, a
    details block per product, then the role's three document groups - the
    shape CTR-ECS gives a product role group.
    """
    products = role.get('products') or []

    sections = [
        # The chip already names the role and its description; this heading is
        # the description on its own, as CTR-ECS heads the group with.
        Section(name=_txt(role.get('description')), level=4, entries=[
            _table('', [
                'EU MP Number',
                'Marketing Auth. No.',
                'Product Auth.',
                'Product Name',
                'Pharmaceutical Form',
                'Strength',
                'Sponsor Product Code',
                'Active Substance Name',
                'EU Substance Number',
                'ATC Name',
                'ATC Code',
                'ATC Level',
            ], [_product_summary_row(p) for p in products]),
        ]),
    ]

    for product in products:
        sections += _product_detail_sections(product)

    # The documents belong to the role, not to one of its products.
    names = set()
    for product in products:
        names |= _product_names(role, product)

    sections += [
        Section(level=5, entries=[
            _docs_as_one(PRODUCT_IB_DOC_LABEL, documents,
                         PRODUCT_IB_DOC_FAMILIES, product_names=names),
            _docs_as_one(PRODUCT_GMP_DOC_LABEL, documents,
                         type_prefixes=PRODUCT_GMP_DOC_TYPE_PREFIXES,
                         product_names=names),
            _docs_as_one(PRODUCT_IMPD_DOC_LABEL, documents,
                         PRODUCT_IMPD_DOC_FAMILIES, product_names=names),
        ]),
    ]

    return ChipGroup(label='{}: {}'.format(_txt(role.get('name')),
                                          _txt(role.get('description'))),
                     sections=sections)


def _product_sections(part1, documents):
    roles = part1.get('medicinalProductRoles') or []
    chips = [_product_chip(role, documents) for role in roles]
    linked = [name for role in roles
              for product in role.get('products') or []
              for name in product.get('linkedProductNames') or []]

    return [
        Section(name='Products', level=3,
                entries=[Chips(groups=chips)] if chips else []),
        # A trial-wide list, so it stays outside the per-role chips even though
        # the documents hang off the individual products.
        Section(name='Content Labelling', level=4, entries=[
            _docs_as_one(CONTENT_LABELLING_DOC_LABEL, documents,
                         CONTENT_LABELLING_DOC_FAMILIES),
            Field('Linked products', _strings(dict.fromkeys(linked)),
                  widget='list'),
        ]),
    ]


def _part1_tab(application, part1, documents):
    sections = [Section(name='Trial Details', level=3)]
    sections += _trial_identifiers_sections(part1)
    sections += _trial_information_sections(part1, documents)
    sections += _protocol_information_sections(documents)
    sections += _scientific_advice_sections(part1, documents)
    sections += _associated_trials_sections(part1)
    # CTR-ECS cannot deliver either of these two at all.
    sections += [
        Section(name='References', level=4, entries=[Message(NOT_RETRIEVABLE)]),
        Section(name='Countries outside the European Economic Area', level=4,
                entries=[Message(NOT_RETRIEVABLE)]),
    ]
    sections += _sponsor_sections(application)
    sections += _product_sections(part1, documents)

    return Tab('part1', 'Part I', subtabs=[
        SubTab('part1-all', 'Part I', panes=[Pane(sections=sections)]),
    ])


# ─── tab 4: Part II (country-specific) ───────────────────────────────────

def _part2_available(part2):
    """
    Part2.isAvailable() in the interface contract: a member state that has not
    submitted yet carries no assessable content.
    """
    return bool(part2.get('submissionDate'))


def austrian_trial_sites(application):
    """
    The invitable principal investigators of a CTIS application: every trial
    site of its submitted Austrian Part II.

    `TrialSite.principalInvestigator` is a single object, not a list - one
    investigator per site, so a site row is a person. Sites are taken
    regardless of their own address country; what makes them ours is the
    Part II's `mscCountryCode`.

    Every incomplete payload yields an empty list rather than an error: no
    Austrian Part II, one that has not been submitted, and one without sites
    are indistinguishable here on purpose - the Einstufung screen shows a
    single hint for all of them.
    """
    if not isinstance(application, dict):
        return []

    sites = []
    seen = set()
    for part2 in application.get('part2s') or []:
        if not isinstance(part2, dict):
            continue
        if part2.get('mscCountryCode') != OWN_COUNTRY:
            continue
        if not _part2_available(part2):
            continue

        for site in part2.get('trialSites') or []:
            if not isinstance(site, dict):
                continue
            investigator = site.get('principalInvestigator') or {}
            email = str(investigator.get('email') or '').strip()
            # `trialSite.id` is a populated non-null string in real data;
            # the e-mail is the fallback. Never `principalInvestigator.id`,
            # which is '' in every payload seen so far.
            key = str(site.get('id') or '').strip() or email
            # Without an e-mail address there is nobody to invite, so the row
            # would only be a checkbox that cannot do anything.
            if not key or not email or key in seen:
                continue
            seen.add(key)

            organisation = site.get('organisation') or {}
            sites.append({
                'key': key,
                'name': _words(investigator.get('titleName'),
                               investigator.get('firstName'),
                               investigator.get('lastName')),
                'email': email,
                'title': str(investigator.get('titleName') or '').strip(),
                'first_name': str(investigator.get('firstName') or '').strip(),
                'last_name': str(investigator.get('lastName') or '').strip(),
                'organisation': str(organisation.get('name') or '').strip(),
                'department': str(site.get('departmentName') or '').strip(),
            })

    return sites


def _trial_site_sections(part2):
    rows = []
    for site in part2.get('trialSites') or []:
        organisation = site.get('organisation') or {}
        address = organisation.get('address') or {}
        investigator = site.get('principalInvestigator') or {}
        street = _txt(', '.join(
            str(address.get(k)).strip()
            for k in ('line1', 'line2', 'line3', 'line4')
            if address.get(k) and str(address.get(k)).strip()))
        rows.append([
            Cell(_words(investigator.get('titleName'),
                        investigator.get('firstName'),
                        investigator.get('lastName'))),
            Cell(_txt(organisation.get('name'))),
            # « Site Location » and « Site Street Address » both show the
            # address lines - a trial site has only the one address, and
            # CTR-ECS repeats it in both columns.
            Cell(street),
            Cell(street),
            Cell(_txt(address.get('city'))),
            Cell(_txt(address.get('zipCode'))),
            # A site address carries a country *name*, unlike mscCountryCode
            # and the member states, which are two-letter codes.
            Cell(_txt(address.get('country'))),
            Cell(_txt(site.get('departmentName'))),
            Cell(_txt(investigator.get('phoneNumber'))),
            Cell(_txt(investigator.get('email'))),
            Cell(_txt(organisation.get('id'))),
        ])

    return [Section(name='Trial Sites', level=4, entries=[
        _table('', [
            'Contact',
            'Org Name',
            'Site Location',
            'Site Street Address',
            'Site City',
            'Site Post Code',
            'Site Country',
            'Department',
            'Phone',
            'Email',
            'Org ID',
        ], rows),
    ])]


def _part2_document_sections(part2, documents):
    # The country's Part II documents are the ones it references by id.
    ids = set(part2.get('documentIds') or [])
    own = [d for d in documents if d.id in ids]

    entries = []
    claimed = set()
    for label, families in PART2_DOC_GROUPS:
        group = _docs_as_one(label, own, families)
        claimed |= {d.id for d in group.groups[0].documents}
        entries.append(group)

    # Whatever the eight groups do not claim. Unlike them it is left out when
    # empty, the way CTR-ECS omits it - an empty « Other documents » would be
    # a heading for a question nobody asked.
    leftovers = sorted((d for d in own if d.id not in claimed),
                       key=lambda d: d.title)
    if leftovers:
        entries.append(Docs(groups=[
            DocGroup(name=PART2_OTHER_DOC_LABEL, documents=leftovers)]))

    return [Section(name='Documents', level=4, entries=entries)]


def _own_part2s(part2s):
    """
    The Austrian Part IIs worth showing. Another member state's Part II is not
    this commission's to assess, and one that has not been submitted carries
    nothing to assess yet.
    """
    return [p for p in part2s
            if _part2_available(p) and p.get('mscCountryCode') == OWN_COUNTRY]


def _merged_part2(part2s):
    """
    Several Part IIs of one country read as one.

    CTIS can carry a country more than once - MSC lists each of them, because
    they are separate submissions with their own subject counts and dates. The
    Part II tab is not about the submissions though, it is about what Austria
    holds for this trial: its sites and its documents, in one list rather than
    split across selectable copies of the same country.

    Sites are deduplicated by `trialSite.id`, the way `austrian_trial_sites`
    does it - the same site can be filed under two Part IIs. A site without an
    id is kept as it is; dropping it would lose a row rather than a repeat.
    """
    sites, seen = [], set()
    document_ids, seen_documents = [], set()
    for part2 in part2s:
        for site in part2.get('trialSites') or []:
            key = str(site.get('id') or '').strip() if isinstance(site, dict) else ''
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            sites.append(site)
        for document_id in part2.get('documentIds') or []:
            if document_id in seen_documents:
                continue
            seen_documents.add(document_id)
            document_ids.append(document_id)

    return {
        'mscCountryCode': OWN_COUNTRY,
        # The date the country first submitted, as the MSC table reads it.
        'submissionDate': min(
            (p.get('submissionDate') for p in part2s if p.get('submissionDate')),
            default=None),
        'trialSites': sites,
        'documentIds': document_ids,
    }


def _empty_part2_tab():
    return Tab('part2', 'Part II', subtabs=[
        SubTab('part2-all', 'Part II', panes=[
            Pane(sections=[Section(entries=[
                Field('Member state', NOT_PROVIDED)])])]),
    ])


def _part2_tab(part2s, documents):
    part2s = _own_part2s(part2s)
    if not part2s:
        return _empty_part2_tab()

    part2 = _merged_part2(part2s)
    country = _country(OWN_COUNTRY)
    sections = (
        [Section(name='Country specific details (Part II - {})'.format(country))]
        + _trial_site_sections(part2)
        + _part2_document_sections(part2, documents))

    return Tab('part2', 'Part II', subtabs=[
        SubTab('part2-all', 'Part II', panes=[Pane(sections=sections)]),
    ])


# ─── the restricted view ─────────────────────────────────────────────────
# Two tabs instead of five, built from the whitelist above rather than by
# pruning the full ones: a section that is never assembled cannot leak, and
# the internal tabs stay free to change without dragging the permission
# boundary along with them.

def _external_synopsis_documents(documents):
    return _docs_as_one(
        EXTERNAL_SYNOPSIS_DOC_LABEL, documents, EXTERNAL_SYNOPSIS_DOC_FAMILIES,
        type_codes=EXTERNAL_SYNOPSIS_DOC_TYPE_CODES)


def _external_part1_tab(documents):
    return Tab('part1', 'Part I', subtabs=[
        SubTab('part1-all', 'Part I', panes=[
            Pane(sections=[
                Section(name='Protocol information', level=4, entries=[
                    _external_synopsis_documents(documents),
                ]),
            ]),
        ]),
    ])


def _external_part2_documents(part2, documents):
    return _docs_as_one(
        EXTERNAL_PART2_DOC_LABEL, documents, EXTERNAL_PART2_DOC_FAMILIES,
        ids=set(part2.get('documentIds') or []),
        type_codes=EXTERNAL_PART2_DOC_TYPE_CODES)


def _external_part2_tab(part2s, documents):
    # Austria only, and only its documents - no country details, no trial
    # sites. Another member state is not rendered at all, not as a locked chip.
    part2s = _own_part2s(part2s)
    if not part2s:
        return _empty_part2_tab()

    return Tab('part2', 'Part II', subtabs=[
        SubTab('part2-all', 'Part II', panes=[Pane(sections=[
            Section(name='Documents', level=4, entries=[
                _external_part2_documents(_merged_part2(part2s), documents)]),
        ])]),
    ])


def external_documents(trial, documents):
    """
    Every document the restricted view shows, for gating the download route.

    Built from the same two calls the restricted tabs make, so a document can
    never be listed on the page without being downloadable, or the reverse.
    """
    trial = trial if isinstance(trial, dict) else {}
    applications = sorted_applications(trial)
    if not applications:
        return []

    entries = build_document_entries(documents or [])
    part2s = (applications[0].get('part2s') or [])

    permitted = list(
        _external_synopsis_documents(entries).groups[0].documents)
    for part2 in part2s:
        if not _part2_available(part2):
            continue
        if part2.get('mscCountryCode') != OWN_COUNTRY:
            continue
        permitted += _external_part2_documents(part2, entries).groups[0].documents
    return permitted


# ─── tab 5: Unterlagen (flat document list) ──────────────────────────────

def _document_filters(documents):
    """
    The distinct values each document filter offers. A filter every document
    answers the same way narrows nothing - « Quelle » was always CTIS - so it
    is left out rather than offered as a choice that changes nothing.
    """
    def options(attribute):
        return sorted({getattr(d, attribute) for d in documents if getattr(d, attribute)})

    candidates = [
        Filter('category', 'Document type', options('category')),
        Filter('section', 'Section', options('section')),
        Filter('part', 'Part', options('part_label')),
        Filter('language', 'Language', options('language')),
        Filter('source', 'Source', options('source')),
    ]
    return [f for f in candidates if len(f.options) > 1]


def _unterlagen_tab(documents):
    doclist = DocList(documents=documents, filters=_document_filters(documents))
    return Tab('unterlagen', 'Application Documents', subtabs=[
        SubTab('unterlagen-all', 'Application Documents', panes=[
            Pane(sections=[Section(name='All documents', entries=[doclist])]),
        ]),
    ])


# ─── entry point ─────────────────────────────────────────────────────────

def build_ctr_view(trial, documents=None, download_url=None,
                   restricted=False):
    """
    Build the CTIS view model for one imported trial payload.

    `trial` is the raw payload and `documents` the accompanying entries from
    the document service. `download_url` is called with a document id and
    returns the URL to download it. Returns a dict of template context.

    With `restricted`, only what a viewer outside the ethics commission may
    see is assembled - see the EXTERNAL_* whitelist above. Everyone who is not
    office, executive or signing gets that view; there is no tier between it
    and the full one.

    Only the payload's newest application is rendered. Versioning is the
    data model's job - each import is its own CTRSubmissionForm of the
    submission, listed in the Status tab - so there is no version switch here.
    """
    trial = trial if isinstance(trial, dict) else {}
    entries = build_document_entries(documents or [], download_url)
    applications = sorted_applications(trial)

    if not applications:
        # A payload with no application at all - e.g. a study imported before
        # the interface delivered the real trial object. Say so rather than
        # blowing up.
        return {
            'ctr_tabs': [],
            'ctr_payload_unusable': True,
        }

    application = applications[0]
    part1 = application.get('part1') or {}
    part2s = list(application.get('part2s') or [])

    if restricted:
        tabs = [
            _external_part1_tab(entries),
            _external_part2_tab(part2s, entries),
        ]
    else:
        # The document list is fetched per application, so every entry in it
        # belongs to this one - a document carries no application of its own.
        tabs = [
            _formular_tab(trial, application, entries),
            _msc_tab(application, part1, part2s),
            _part1_tab(application, part1, entries),
            _part2_tab(part2s, entries),
            _unterlagen_tab(entries),
        ]

    return {
        'ctr_tabs': tabs,
        'ctr_payload_unusable': False,
    }
