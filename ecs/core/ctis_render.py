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
from dataclasses import dataclass, field as dc_field
from datetime import date, datetime

from django_countries import countries

from ecs.core import ctis_document_types

# A value CTIS delivered as null/empty. The field stays visible with this
# placeholder so a reviewer can tell nothing was silently dropped.
NOT_PROVIDED = '– Keine Angaben –'

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
    if not code:
        return NOT_PROVIDED
    return str(countries.name(code)) or code


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

# Part I « Protocol information ». CTR-ECS heads the PROTOCOL group with CTIS's
# own Part I wording rather than the whitelist label, which is just « Protocol ».
PROTOCOL_DOC_FAMILIES = (
    'PROTOCOL',
    'STUDY_DESIGN',
)
PROTOCOL_DOC_LABELS = {'PROTOCOL': 'Clinical trial protocol'}

# TODO delete once confirmed: SYNOPSIS_OF_THE_PROTOCOL is a real whitelist kind
# (codes 7, 57, 308 and 344), but CTR-ECS does not list it under « Protocol
# information » - and since it does show empty groups, that absence is a
# decision, not a trial without a synopsis. Hidden here rather than dropped
# because nothing else confirms where the kind belongs. « Unterlagen » still
# lists these documents.
HIDDEN_PROTOCOL_DOC_FAMILIES = ('SYNOPSIS_OF_THE_PROTOCOL',)

# Part I « Scientific advice and Paediatric Investigation Plan ». CTIS has no
# document kind for a PIP itself, only an opinion extract - a PIP's own
# documents arrive through part1.paediatricInvestigationPlan[].documentIds.
SCIENTIFIC_ADVICE_DOC_FAMILIES = ('SUMMARY_OF_SCIENTIFIC_ADVICE',)
PIP_DOC_FAMILIES = ('PIP_OPINION',)

# Part I « Trial category », next to the low-intervention answer.
LOW_INTERVENTION_DOC_FAMILIES = ('LOW_INTERVENTION_JUSTIFICATION',)

# Listed once for the whole trial even though the documents hang off the
# individual products.
CONTENT_LABELLING_DOC_FAMILIES = ('CONTENT_LABELLING_OF_THE_IMPS',)

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
    """The entry's versions, newest system version first."""
    versions = [v for v in doc.get('versions') or [] if isinstance(v, dict)]
    return sorted(versions, key=lambda v: v.get('systemVersion') or 0, reverse=True)


def build_document_entries(documents, download_url=None):
    """
    Convert the document service's raw entries into display data, once.

    An entry carries its file only inside `versions[]`, each with its own
    `documentUrl`; the newest version is what the document is shown as. A
    version that already carries a `url` keeps it (that is how ECS-own
    documents arrive), CTIS ones get one built from their `documentUrl`.
    """
    def url_for(version):
        if version.get('url'):
            return version['url']
        key = version.get('documentUrl')
        return download_url(key) if download_url and key else ''

    def as_version(version):
        return DocVersion(
            system_version=version.get('systemVersion') or '–',
            from_date=(_date(version.get('fromDate'))
                       if version.get('fromDate') else '–'),
            version=version.get('version') or '',
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
            title=doc.get('title') or NOT_PROVIDED,
            type_code=str(doc.get('typeCode') or ''),
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
            mime_type=latest.mime_type,
            source=doc.get('source') or 'CTIS',
            url=latest.url,
            versions=[as_version(v) for v in versions[1:]],
        ))
    return entries


def _doc_matches(doc, parts=None, ids=None, product_names=None,
                 is_product=None, exclude_families=()):
    """
    `parts` is the set of `estimatedPart` values to keep - None is a value of
    its own there, so it has to be passed explicitly rather than meaning
    « any ». `ids` scopes to a Part II's `documentIds`, `product_names` to the
    names one product answers to.
    """
    if ids is not None and doc.id not in ids:
        return False
    if parts is not None and doc.part not in parts:
        return False
    if is_product is not None and doc.is_product_document != is_product:
        return False
    if product_names is not None and doc.product_name not in product_names:
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

def _formular_tab(trial, application, documents):
    details = Section(name='Application details', entries=[
        Field('Application ID', _txt(application.get('applicationId'))),
        Field('Application type', _txt(application.get('applicationType'))),
        Field('Application status', _txt(application.get('status'))),
        Field('Submission date', _date(application.get('submissionDate'))),
        Field('Decision date', _date(application.get('decisionDate'))),
        Field('Part II only application', _bool(application.get('part2OnlyApplication'))),
        Field('Winter clock stop used', _bool(application.get('winterClockStopUsed'))),
        Field('EU-CT number', _txt(trial.get('clinicalTrialId'))),
        Field('Trial ID', _txt(application.get('trialId'))),
        Field('Trial status', _txt(_get(trial, 'status', 'text'))),
        Field('Referenced trials', _strings(application.get('referencedTrials')),
              widget='list'),
    ])

    docs = Section(name='Documents', entries=[
        _docs('', documents, APPLICATION_DOC_FAMILIES),
    ])

    return Tab('formular', 'Formular', subtabs=[
        SubTab('formular-main', 'Formular', panes=[
            Pane(sections=[details, docs]),
        ]),
    ])


# ─── tab 2: MSC (member states concerned) ────────────────────────────────

def _member_states_sections(application, part1, part2s):
    # One member state can carry more than one Part II, so collect them all
    # rather than letting the last one win: the first submission is the date
    # shown, and the subject counts add up.
    by_country = {}
    for part2 in part2s:
        by_country.setdefault(part2.get('mscCountryCode'), []).append(part2)

    rows = []
    for member_state in application.get('memberStates') or []:
        code = member_state.get('countryCode')
        country_part2s = by_country.get(code) or []
        dates = [d for d in (_parse_date(p.get('submissionDate'))
                             for p in country_part2s) if d]
        subjects = [p.get('recruitmentSubjectCount') for p in country_part2s
                    if p.get('recruitmentSubjectCount') is not None]
        rows.append([
            Cell(_country(code)),
            Cell('Selected' if member_state.get('isRms') else '–'),
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

def _identifier_lines(part1):
    """Each secondary identifying number as « type: number », one per line."""
    lines = []
    for identifier in part1.get('identifiers') or []:
        if isinstance(identifier, dict):
            key, number = identifier.get('key'), identifier.get('number')
            lines.append(': '.join(str(v) for v in (key, number) if v))
        else:
            lines.append(identifier)
    return _strings(lines)


def _trial_identifiers_sections(part1):
    return [
        Section(name='Trial Identifiers', level=4, entries=[
            Field('Full title (English)', _txt(part1.get('title')),
                  widget='textarea'),
            Field('Public title (English)', _txt(part1.get('publicTitle')),
                  widget='textarea'),
            Field('Protocol code', _txt(part1.get('protocolCode'))),
        ]),
        Section(name='Secondary identifying numbers', level=5, entries=[
            Field('Identifier', _identifier_lines(part1), widget='list'),
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
        for e in part1.get('endpoints') or []
        if bool(e.get('isPrimary')) is is_primary
    ])


def _subject_gender(part1):
    """The two sex flags read as one « Subject gender » value, as in CTIS."""
    female = part1.get('containsFemaleSubjects')
    male = part1.get('containsMaleSubjects')
    if female is None and male is None:
        return NOT_PROVIDED
    genders = [g for g, included in (('Female', female), ('Male', male)) if included]
    return ', '.join(genders) or NOT_PROVIDED


def _trial_information_sections(part1, documents):
    low_intervention = part1.get('isLowInterventionTrial')
    category = NOT_PROVIDED if low_intervention is None else (
        'Low intervention trial' if low_intervention
        else 'No low intervention trial'
    )

    return [
        Section(name='Trial information', level=4),
        Section(name='Trial category', level=5, entries=[
            Field('Category', category),
            _docs('Attachment of justification of low interventional '
                  'clinical trial', documents, LOW_INTERVENTION_DOC_FAMILIES),
            Field('Trial phase', _txt(part1.get('phase'))),
        ]),
        Section(name='Medical condition', level=5, entries=[
            _table('', [
                'Medical condition (English)',
                'Is the medical condition considered to be a rare disease',
            ], [
                [Cell(_txt(m.get('description'))), Cell(_bool(m.get('isRareDisease')))]
                for m in part1.get('medicalConditions') or []
            ]),
            Field('Therapeutic area', _strings(part1.get('therapeuticAreas')),
                  widget='list'),
            Field('MedDRA codes', NOT_RETRIEVABLE),
        ]),
        Section(name='Main objective', level=5, entries=[
            Field('Trial scope', _named(part1.get('trialScopes')), widget='list'),
            Field('Main objective (English)', _txt(part1.get('mainObjective')),
                  widget='textarea'),
        ]),
        Section(name='Secondary objectives', level=5, entries=[
            _table('', [
                'New ID',
                'Secondary objective (English)',
            ], [
                [Cell(_txt(o.get('id'))), Cell(_txt(o.get('description')))]
                for o in part1.get('secondaryObjectives') or []
            ]),
        ]),
        Section(name='Eligibility criteria', level=5, entries=[
            _table('Principal inclusion criteria', [
                'New ID',
                'Principal inclusion criteria (English)',
            ], [
                [Cell(_txt(c.get('id'))), Cell(_txt(c.get('description')))]
                for c in part1.get('principalInclusionCriteria') or []
            ]),
            _table('Principal exclusion criteria', [
                'New ID',
                'Principal exclusion criteria (English)',
            ], [
                [Cell(_txt(c.get('id'))), Cell(_txt(c.get('description')))]
                for c in part1.get('principalExclusionCriteria') or []
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
        Section(name='Population of trial subjects', level=5, entries=[
            Field('Age range', _strings(part1.get('ageRanges')), widget='list'),
            Field('Age range secondary identifier',
                  _strings(part1.get('ageRangeSecondaryIdentifiers')),
                  widget='list'),
            Field('Subject gender', _subject_gender(part1)),
            Field('Clinical trial group',
                  _strings(part1.get('recruitmentPopulationGroups')),
                  widget='list'),
        ]),
    ]


def _protocol_information_sections(documents):
    # CTR-ECS labels this « Clinical trial protocol » and « Study design »;
    # the whitelist's own kinds are Protocol, Synopsis of the protocol and
    # Study design. TODO: check the headings against a screenshot.
    return [Section(name='Protocol information', level=4, entries=[
        _docs('', documents, PROTOCOL_DOC_FAMILIES,
              labels=PROTOCOL_DOC_LABELS),
    ])]


def _scientific_advice_sections(part1, documents):
    # The interface schema declares scientificAdvices[] and
    # paediatricInvestigationPlan[] without an item shape, so read both
    # tolerantly: a dict contributes its known keys, anything else is shown
    # as-is rather than dropped.
    rows = []
    for advice in part1.get('scientificAdvices') or []:
        if isinstance(advice, dict):
            rows.append([
                Cell(_txt(advice.get('id'))),
                Cell(_txt(advice.get('competentAuthorities')
                          or advice.get('competentAuthority'))),
            ])
        else:
            rows.append([Cell(None), Cell(_txt(advice))])

    # The group heading already names both halves, so the entries carry the
    # labels instead of repeating « Scientific advice » as a sub-heading. Both
    # document kinds are labelled rows like the table above them - CTR-ECS
    # words the PIP one after the plan, not after the whitelist kind
    # « PIP opinion ».
    return [Section(
        name='Scientific advice and Paediatric Investigation Plan (PIP)',
        level=4, entries=[
            _table('Scientific advice', [
                'ID',
                'Competent authorities that have provided scientific advice',
            ], rows),
            _docs('Summary of scientific advice', documents,
                  SCIENTIFIC_ADVICE_DOC_FAMILIES),
            _docs('Paediatric investigation plan', documents,
                  PIP_DOC_FAMILIES),
        ])]


def _associated_trials_sections(part1):
    return [Section(name='Associated clinical trials', level=4, entries=[
        _table('', [
            'EU CT number',
            'Title',
            'Sponsor',
        ], [
            [Cell(_txt(t.get('trialId'))), Cell(_txt(t.get('title'))),
             Cell(_txt(t.get('sponsorName')))]
            for t in part1.get('associatedTrials') or []
        ]),
    ])]


def _sponsor_sections(application):
    sponsors = application.get('sponsors') or []

    rows = []
    for sponsor in sponsors:
        commercial = sponsor.get('isCommercial')
        active_from = sponsor.get('activeFrom')
        active_to = sponsor.get('activeTo')
        rows.append([
            Cell(_txt(sponsor.get('name'))),
            Cell(_txt(sponsor.get('organisationType'))),
            Cell(_country(sponsor.get('country')) if sponsor.get('country') else None),
            # « Type » is the commercial flag and « Status » the active period -
            # CTR-ECS shows neither as a raw boolean or a date range.
            Cell(None if commercial is None else
                 ('Commercial' if commercial else 'Non-commercial')),
            Cell(None if not (active_from or active_to) else
                 ('Inactive' if active_to else 'Active')),
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

    # One contact point on screen at a time, picked by sponsor name.
    groups = []
    for i, sponsor in enumerate(sponsors):
        contact = sponsor.get('unionContactPoint') or {}
        groups.append(ChipGroup(
            label=sponsor.get('name') or 'Sponsor {}'.format(i + 1),
            entries=[
                Field('Organisation name',
                      _txt(contact.get('organisationName'))),
                # CTR-ECS shows an « Address » of its own next to the four
                # address lines; the interface schema has no such key, so say
                # so unless a later payload starts delivering one.
                Field('Address', _txt(contact['address'])
                      if 'address' in contact else NOT_RETRIEVABLE),
                Field('Address line 1', _txt(contact.get('addressLine1'))),
                Field('Address line 2', _txt(contact.get('addressLine2'))),
                Field('Address line 3', _txt(contact.get('addressLine3'))),
                Field('Address line 4', _txt(contact.get('addressLine4'))),
                Field('Town/City', _txt(contact.get('city'))),
                Field('Post code', _txt(contact.get('postCode'))),
                Field('Country', _country(contact.get('country'))
                      if contact.get('country') else NOT_PROVIDED),
                Field('Functional contact point name',
                      _txt(contact.get('functionalContactPointName'))),
                Field('Firstname', _txt(contact.get('firstName'))),
                Field('Lastname', _txt(contact.get('lastName'))),
                Field('Phone', _txt(contact.get('phone'))),
                Field('Email', _txt(contact.get('email'))),
            ]))

    if groups:
        sections.append(Section(name='Contact Point for Union', level=4,
                                entries=[Chips(groups=groups)]))
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


def _product_chip(role, product, documents):
    details = product.get('productDetails') or {}
    substances = product.get('substances') or []
    dosage = product.get('dosage') or {}
    authorisation = product.get('authorisationDetails') or {}
    title = _product_title(role, product)
    number = details.get('medicinalProductNumber')

    summary = _table('', [
        'EU MP number',
        'Marketing auth. no.',
        'Product auth.',
        'Product name',
        'Pharmaceutical form',
        'Strength',
        'Sponsor product code',
        'Active substance name',
        'EU substance number',
    ], [[
        Cell(_txt(number)),
        Cell(_txt(authorisation.get('marketingAuthorisationNumber'))),
        Cell(_txt(details.get('authorisationStatus'))),
        Cell(_txt(details.get('medicinalProductName'))),
        Cell(_txt(details.get('pharmaceuticalForm'))),
        Cell(_txt(details.get('strength'))),
        Cell(_txt(product.get('sponsorProductCode'))),
        Cell(_strings([s.get('activeSubstanceName') for s in substances])),
        Cell(_strings([s.get('substanceEvCode') for s in substances])),
    ]])

    # The chip names the product, so the block below it does not repeat it.
    return ChipGroup(label='{}: {}'.format(_txt(role.get('name')), title), sections=[
        Section(level=4, entries=[summary]),
        Section(name='Details for Product with EU MP number {}'.format(_txt(number)),
                level=5, entries=[
            Field('Role description', _txt(role.get('description'))),
            Field('Role in trial', _txt(details.get('medicinalProductRoleInTrial'))),
            Field('Product other name',
                  _txt(details.get('medicinalProductOtherName'))),
            Field('Paediatric formulation',
                  _txt(details.get('paediatricFormulation'))),
            Field('Sponsor product code (edit)',
                  _txt(details.get('sponsorProductCodeEdit'))),
            Field('ATC code / level / name', _words(
                      product.get('atcCode'), product.get('atcLevel'),
                      product.get('atcName'))),
            Field('Marketing authorisation holder',
                  _txt(authorisation.get('maHolder'))),
            Field('Marketing authorisation country',
                  _txt(authorisation.get('marketingAuthorisationCountry'))),
            Field('Centralised procedure number',
                  _txt(authorisation.get('centralisedProcedureNumber'))),
            Field('Orphan drug designer', _txt(product.get('orphanDrugDesigner'))),
            Field('Product changed relation',
                  _txt(product.get('productChangedRelation'))),
            Field('Linked product names',
                  _strings(product.get('linkedProductNames')), widget='list'),
            Field('Advanced therapies', _strings(product.get('advancedTherapies')),
                  widget='list'),
            Field('Devices', _strings(product.get('devices')), widget='list'),
            Field('Route of administration', _txt(dosage.get('routeAdministration'))),
            Field('Max. daily dose', _amount(
                      dosage.get('maxDailyDoseAmount'),
                      dosage.get('maxDailyDoseUomEvCode'))),
            Field('Max. total dose', _amount(
                      dosage.get('maxTotalDoseAmount'),
                      dosage.get('maxTotalDoseUomEvCode'))),
            Field('Max. treatment period', _txt(dosage.get('maxTreatmentPeriod'))),
            _table('Characteristics', [
                'Characteristic',
                'Description',
            ], [
                [Cell(_txt(c.get('name'))), Cell(_txt(c.get('description')))]
                for c in product.get('characteristics') or []
            ]),
            _table('Active substances', [
                'Active substance name',
                'Synonyms',
                'Other descriptive name',
                'Classification',
                'Status',
                'Strength',
                'EU substance number',
            ], [
                [Cell(_txt(s.get('activeSubstanceName'))),
                 Cell(_txt(s.get('activeSubstanceNameSynonyms'))),
                 Cell(_txt(s.get('otherDescriptiveName'))),
                 Cell(_txt(s.get('classification'))),
                 Cell(_txt(s.get('status'))),
                 Cell(_txt(s.get('strength'))),
                 Cell(_txt(s.get('substanceEvCode')))]
                for s in substances
            ]),
        ]),
        # CTR-ECS shows each document kind as a heading of its own over its
        # cards, not as a labelled row - the one place a non-section gets a
        # heading. Content labelling is sectioned per product like the rest
        # but listed once for the trial, so it is not repeated here.
        # TODO: which kinds a product shows, and in what order, still needs a
        # screenshot; for now they are whichever kinds its documents have.
        Section(level=5, entries=[
            _docs('', documents, product_names=_product_names(role, product),
                  exclude_families=CONTENT_LABELLING_DOC_FAMILIES),
        ]),
    ])


def _product_sections(part1, documents):
    chips = [_product_chip(role, product, documents)
             for role in part1.get('medicinalProductRoles') or []
             for product in role.get('products') or []]

    return [
        Section(name='Products', level=3,
                entries=[Chips(groups=chips)] if chips else []),
        # Content labelling is a trial-wide document list, so it stays outside
        # the per-product chips - and it is nothing but that list, which is why
        # it carries one heading rather than a heading over a heading.
        Section(name='Content Labelling', level=4, entries=[
            _docs('', documents, CONTENT_LABELLING_DOC_FAMILIES),
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


def _trial_site_sections(part2):
    rows = []
    for site in part2.get('trialSites') or []:
        organisation = site.get('organisation') or {}
        address = organisation.get('address') or {}
        investigator = site.get('principalInvestigator') or {}
        rows.append([
            Cell(_words(investigator.get('titleName'),
                        investigator.get('firstName'),
                        investigator.get('lastName'))),
            Cell(_txt(organisation.get('name'))),
            # TODO: « Site location » has no source. A trial site carries one
            # address and its four lines are the street address - real payloads
            # fill line 1 only - so whatever CTR-ECS shows here comes from
            # somewhere the contract does not describe. Left empty rather than
            # filled with the street address a second time.
            Cell(None),
            Cell(_lines(address.get('line1'), address.get('line2'),
                        address.get('line3'), address.get('line4'))),
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

    return [Section(name='Trial sites', level=4, entries=[
        _table('', [
            'Contact',
            'Org name',
            'Site location',
            'Site street address',
            'Site city',
            'Site post code',
            'Site country',
            'Department',
            'Phone',
            'E-mail',
            'Org ID',
        ], rows),
    ])]


def _part2_document_sections(part2, documents):
    # The country's Part II documents are the ones it references by id. Only
    # the kinds it actually holds are shown - CTR-ECS lists no empty group
    # here, unlike the Part I sections with their fixed kind lists.
    ids = set(part2.get('documentIds') or [])
    return [Section(name='Documents', level=4, entries=[
        _docs('', documents, ids=ids),
    ])]


def _part2_label(part2, duplicate_country):
    """
    A member state names its own chip. Two Part IIs can name the same state,
    so those carry their submission date as well rather than reading as two
    identical chips.
    """
    label = _country(part2.get('mscCountryCode'))
    if duplicate_country:
        label = '{} ({})'.format(label, _date(part2.get('submissionDate')))
    return label


def _part2_tab(part2s, documents, selected_country=None):
    # A member state that has not submitted has nothing to assess yet.
    part2s = [p for p in part2s if _part2_available(p)]

    if not part2s:
        return Tab('part2', 'Part II', subtabs=[
            SubTab('part2-all', 'Part II', panes=[
                Pane(sections=[Section(entries=[
                    Field('Member state', NOT_PROVIDED)])])]),
        ])

    counts = {}
    for part2 in part2s:
        code = part2.get('mscCountryCode')
        counts[code] = counts.get(code, 0) + 1

    # The first chip is the open one: the country asked for, else the ethics
    # commission's own, else whichever the interface delivered first. A country
    # with two Part IIs opens on the first of them.
    def order(part2):
        code = part2.get('mscCountryCode')
        rank = 0 if code == selected_country else 1 if code == OWN_COUNTRY else 2
        return (rank, _part2_label(part2, counts[code] > 1))

    groups = []
    for part2 in sorted(part2s, key=order):
        country = _country(part2.get('mscCountryCode'))
        label = _part2_label(part2, counts[part2.get('mscCountryCode')] > 1)
        # The heading names the member state; telling two of them apart is the
        # chip's job, so the submission date does not repeat here.
        groups.append(ChipGroup(label=label, sections=(
            [Section(name='Country specific details (Part II - {})'.format(country))]
            + _trial_site_sections(part2)
            + _part2_document_sections(part2, documents))))

    return Tab('part2', 'Part II', subtabs=[
        SubTab('part2-all', 'Part II', panes=[
            Pane(sections=[Section(entries=[Chips(groups=groups)])]),
        ]),
    ])


# ─── tab 5: Unterlagen (flat document list) ──────────────────────────────

def _document_filters(documents):
    """The distinct values each « Unterlagen » filter offers."""
    def options(attribute):
        return sorted({getattr(d, attribute) for d in documents if getattr(d, attribute)})

    return [
        Filter('category', 'Kategorie', options('category')),
        Filter('part', 'Teil', options('part_label')),
        Filter('language', 'Sprache', options('language')),
        Filter('source', 'Quelle', options('source')),
    ]


def _unterlagen_tab(documents):
    doclist = DocList(documents=documents, filters=_document_filters(documents))
    return Tab('unterlagen', 'Unterlagen', subtabs=[
        SubTab('unterlagen-all', 'Unterlagen', panes=[
            Pane(sections=[Section(name='All documents', entries=[doclist])]),
        ]),
    ])


# ─── entry point ─────────────────────────────────────────────────────────

def build_ctr_view(trial, documents=None, selected_country=None,
                   download_url=None):
    """
    Build the CTIS view model for one imported trial payload.

    `trial` is the raw payload and `documents` the accompanying entries from
    the document service. `download_url` is called with a document id and
    returns the URL to download it. Returns a dict of template context.

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

    # The document list is fetched per application, so every entry in it
    # belongs to this one - a document carries no application of its own.
    tabs = [
        _formular_tab(trial, application, entries),
        _msc_tab(application, part1, part2s),
        _part1_tab(application, part1, entries),
        _part2_tab(part2s, entries, selected_country),
        _unterlagen_tab(entries),
    ]

    return {
        'ctr_tabs': tabs,
        'ctr_payload_unusable': False,
    }
