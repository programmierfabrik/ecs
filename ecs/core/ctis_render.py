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
    """
    One switchable variant of a subtab's content. Everything but Part II has
    a single unkeyed pane; Part II has one pane per member state, switched by
    the country selector above the third-level tabs.
    """
    key: str = ''
    sections: list = dc_field(default_factory=list)


@dataclass
class SubTab:
    slug: str
    name: str
    panes: list = dc_field(default_factory=list)


@dataclass
class Choice:
    key: str
    label: str


@dataclass
class Tab:
    slug: str
    name: str
    subtabs: list = dc_field(default_factory=list)
    # non-empty only for Part II: the country selector shown above the
    # third-level tabs, switching every subtab's pane at once.
    pane_choices: list = dc_field(default_factory=list)
    pane_selector_label: str = ''

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

# CTIS types a document by a numeric `typeCode` and a `type` label. Grouping
# keys off the code and takes its heading from here, so a renamed label
# upstream does not silently split a group in two.
#
# Read off a real document list, so these 24 are confirmed - but they are only
# the types that one trial happened to carry, not the whole CTIS taxonomy.
# TODO: complete from the CTIS document-type list. Until it is complete, a
# group of unknown types falls back to the label the payload carried, and a
# type CTIS holds nothing for cannot be shown as « No document available »
# because nothing names it.
DOCUMENT_TYPES = {
    '2': 'Cover letter',
    '5': 'Protocol (not for publication)',
    '7': 'Synopsis of the protocol (for publication)',
    '10': 'Financial arrangements',
    '14': 'Recruitment arrangements (for publication)',
    '15': 'Subject information and informed consent form (for publication)',
    '86': 'Part I Section 1 Introduction - Draft',
    '88': 'Part I Section 3 Pre clinical Assessment - Draft',
    '89': 'Part I Section 4 Clinical Assessment - Draft',
    '90': 'Part I Section 5 Statistical Methodological Assessment - Draft',
    '91': 'Part I Section 6 Regulatory Assessment - Draft',
    '104': 'Protocol (for publication)',
    '308': 'Synopsis of the protocol (not for publication)',
    '313': 'Investigator Brochure',
    '317': 'Content labelling of the IMPs',
    '318': 'Proof of insurance',
    '319': 'Suitability of the clinical trial sites facilities',
    '320': 'Investigator CV',
    '321': 'Suitability of the investigator',
    '323': 'Subject information and informed consent form (not for publication)',
    '326': 'Proof of payment',
    '327': 'Compliance with national requirements on Data Protection',
    '328': 'Compliance with use of Biological samples',
    '331': 'Investigational Medicinal Product Dossier: Safety and Efficacy',
}

# Documents that belong to the application itself rather than to either part.
# Not derivable from `estimatedPart` - a cover letter is estimated into Part I
# like everything else - so the types are named.
APPLICATION_DOC_TYPES = ('2', '326')

# The trial protocol, as Part I « Protocol information » shows it.
PROTOCOL_DOC_TYPES = ('5', '104', '7', '308')

# Listed once for the whole trial even though the documents hang off the
# individual products.
CONTENT_LABELLING_DOC_TYPES = ('317',)

# « Roles: {role} Name: {product name} » - how the document service names the
# section of a document that belongs to one product of the trial.
_PRODUCT_SECTION_RE = re.compile(
    r'^\s*Roles:\s*(?P<role>.*?)\s+Name:\s*(?P<name>.+?)\s*$')

_PART_LABELS = {1: 'Part I', 2: 'Part II'}


def _doc_type_label(doc):
    return (DOCUMENT_TYPES.get(str(doc.get('typeCode') or ''))
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
                 is_product=None, exclude_types=()):
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
    if doc.type_code in exclude_types:
        return False
    return True


def _docs(label, documents, type_codes=None, note='', **filters):
    """
    Group documents by CTIS document type. `type_codes` names the groups to
    show, in CTIS order, and every one of them is emitted even when empty, so
    a reviewer sees which types CTIS holds nothing for rather than a silently
    shorter list.

    With no `type_codes` the groups are whichever types the matching documents
    have, in payload order - see DOCUMENT_TYPES.
    """
    matching = [d for d in documents if _doc_matches(d, **filters)]

    if type_codes is None:
        codes = list(dict.fromkeys(d.type_code for d in matching))
    else:
        codes = list(type_codes)

    def name_of(code):
        for d in matching:
            if d.type_code == code:
                return d.category
        return DOCUMENT_TYPES.get(code) or code

    # Strictly the asked-for types: a widget scoped to one type must not
    # absorb every other document that happens to share its part. Nothing goes
    # missing because « Unterlagen » lists the application's documents in full.
    return Docs(label=label, note=note, groups=[
        DocGroup(name=name_of(code),
                 documents=[d for d in matching if d.type_code == code])
        for code in codes
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
        _docs('', documents, APPLICATION_DOC_TYPES),
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

    table = _table('', [
        'Member state concerned',
        'RMS',
        'First submission date',
        'Subjects',
    ], rows)

    eea_subjects = sum(p.get('recruitmentSubjectCount') or 0 for p in part2s)
    rest_of_world = part1.get('restOfTheWorldSubjectCount')

    return [
        Section(name='Member states concerned', entries=[
            table,
            Field('Countries outside the European Economic Area', NOT_RETRIEVABLE),
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
            # TODO: DOCUMENT_TYPES pending - « Attachment of justification of
            # low interventional clinical trial » is a document type whose
            # code is not known yet, as in « Protocol information » below.
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
    # CTR-ECS labels this « Clinical trial protocol » and « Study design ».
    # Neither is a CTIS document type; these four are what a real document
    # list holds here. TODO: check against a screenshot.
    return [Section(name='Protocol information', level=4, entries=[
        _docs('', documents, PROTOCOL_DOC_TYPES),
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
    # labels instead of repeating « Scientific advice » as a sub-heading. The
    # advice documents sit unlabelled right under their table, as in CTR-ECS.
    return [Section(
        name='Scientific advice and Paediatric Investigation Plan (PIP)',
        level=4, entries=[
            _table('Scientific advice', [
                'ID',
                'Competent authorities that have provided scientific advice',
            ], rows),
            # TODO: DOCUMENT_TYPES pending, as in « Protocol information ».
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

    for sponsor in sponsors:
        contact = sponsor.get('unionContactPoint') or {}
        name = 'Contact Point for Union'
        if len(sponsors) > 1:
            name = '{} - {}'.format(name, _txt(sponsor.get('name')))
        sections.append(Section(name=name, level=4, entries=[
            Field('Organisation name', _txt(contact.get('organisationName'))),
            # CTR-ECS shows an « Address » of its own next to the four address
            # lines; the interface schema has no such key, so say so unless a
            # later payload starts delivering one.
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


def _one_product_sections(role, product, documents):
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

    return [
        Section(name='{}: {}'.format(_txt(role.get('name')), title),
                level=4, entries=[summary]),
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
        # CTR-ECS shows each document type as a heading of its own over its
        # cards, not as a labelled row - the one place a non-section gets a
        # heading. Content labelling is sectioned per product like the rest
        # but listed once for the trial, so it is not repeated here.
        # TODO: the full ordered type list is pending, so the groups shown
        # are whichever types this product's documents have.
        Section(level=5, entries=[
            _docs('', documents, product_names=_product_names(role, product),
                  exclude_types=CONTENT_LABELLING_DOC_TYPES),
        ]),
    ]


def _product_sections(part1, documents):
    sections = [Section(name='Products', level=3)]

    for role in part1.get('medicinalProductRoles') or []:
        for product in role.get('products') or []:
            sections += _one_product_sections(role, product, documents)

    sections += [
        Section(name='Content Labelling', level=4),
        Section(name="Content labeling of the IMP's", level=5, entries=[
            _docs('', documents, CONTENT_LABELLING_DOC_TYPES),
        ]),
    ]
    return sections


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

def _country_details_sections(part2):
    return [Section(entries=[
        Field('Member state', _country(part2.get('mscCountryCode'))),
        Field('Subjects to be recruited',
              _txt(part2.get('recruitmentSubjectCount'))),
        Field('Submission date', _date(part2.get('submissionDate'))),
    ])]


def _part2_available(part2):
    """
    Part2.isAvailable() in the interface contract: a member state that has not
    submitted yet carries no assessable content.
    """
    return bool(part2.get('submissionDate'))


def _part2_key(part2):
    """
    A pane key per Part II. Not the country code - an application can carry
    more than one Part II for the same member state, which the contract's own
    `hasRelevantPart2` is written for.
    """
    return str(part2.get('id') or '')


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
            Cell(_txt(investigator.get('email'))),
            Cell(_txt(investigator.get('phoneNumber'))),
            Cell(_txt(organisation.get('name'))),
            Cell(_txt(site.get('departmentName'))),
            Cell(_lines(address.get('line1'), address.get('line2'),
                        address.get('line3'), address.get('line4'))),
            Cell(_txt(address.get('city'))),
            Cell(_txt(address.get('zipCode'))),
            # A site address carries a country *name*, unlike mscCountryCode
            # and the member states, which are two-letter codes.
            Cell(_txt(address.get('country'))),
            Cell(_txt(organisation.get('id'))),
        ])

    return [Section(name='Trial sites', entries=[
        _table('', [
            'Contact',
            'E-mail',
            'Phone',
            'Org name',
            'Department',
            'Site street address',
            'Site city',
            'Site post code',
            'Site country',
            'Org ID',
        ], rows),
    ])]


def _part2_document_sections(part2, documents):
    # The country's Part II documents are the ones it references by id.
    ids = set(part2.get('documentIds') or [])
    return [Section(name='Documents', entries=[
        _docs('', documents, ids=ids),
    ])]


def _part2_choices(part2s):
    """
    One selector entry per Part II. Two of them can name the same member
    state, so those get their submission date alongside the country to tell
    them apart rather than reading as a duplicate button.
    """
    counts = {}
    for part2 in part2s:
        code = part2.get('mscCountryCode')
        counts[code] = counts.get(code, 0) + 1

    choices = []
    for part2 in part2s:
        code = part2.get('mscCountryCode')
        label = _country(code)
        if counts.get(code, 0) > 1:
            label = '{} ({})'.format(label, _date(part2.get('submissionDate')))
        choices.append(Choice(key=_part2_key(part2), label=label))
    return choices


def _part2_tab(part2s, documents, selected_country=None):
    # A member state that has not submitted has nothing to assess yet.
    part2s = [p for p in part2s if _part2_available(p)]

    if not part2s:
        return Tab('part2', 'Part II', subtabs=[
            SubTab('part2-country-details', 'Country details', panes=[
                Pane(sections=[Section(entries=[
                    Field('Member state', NOT_PROVIDED)])])]),
        ])

    choices = _part2_choices(part2s)
    keys_by_country = {}
    for part2 in part2s:
        keys_by_country.setdefault(part2.get('mscCountryCode'), _part2_key(part2))

    # The ethics commission's own country is preselected when the trial
    # includes it; otherwise fall back to the first delivered one. A country
    # with two Part IIs preselects the first of them.
    default = (keys_by_country.get(selected_country)
               or keys_by_country.get(OWN_COUNTRY)
               or choices[0].key)
    choices.sort(key=lambda c: (c.key != default, c.label))

    def panes(build):
        return [Pane(key=_part2_key(p), sections=build(p)) for p in part2s]

    return Tab('part2', 'Part II', pane_choices=choices,
               pane_selector_label='Mitgliedsstaat', subtabs=[
        SubTab('part2-country-details', 'Country details',
               panes=panes(_country_details_sections)),
        SubTab('part2-trial-sites', 'Trial sites',
               panes=panes(_trial_site_sections)),
        SubTab('part2-documents', 'Documents',
               panes=panes(lambda p: _part2_document_sections(p, documents))),
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
            'ctr_selected_pane': None,
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

    part2_tab = tabs[3]
    selected = part2_tab.pane_choices[0].key if part2_tab.pane_choices else None

    return {
        'ctr_tabs': tabs,
        'ctr_selected_pane': selected,
        'ctr_payload_unusable': False,
    }
