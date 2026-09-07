from collections import Counter

from django import forms
from django.contrib.auth.models import User
from django.db.models import Q
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _

from ecs.core.forms.fields import DateField
from ecs.core.forms.utils import ReadonlyFormMixin
from ecs.core.models import Submission
from ecs.core.models.clinic import Clinic
from ecs.core.models.constants import SUBMISSION_LANE_BOARD, SUBMISSION_LANE_EXPEDITED
from ecs.core.models.core import MedicalCategory
from ecs.documents.forms import DocumentForm
from ecs.documents.models import DocumentType
from ecs.utils.formutils import require_fields


class TrialSiteSelect(forms.CheckboxSelectMultiple):
    """
    The « Hauptprüfer einladen » table of a CTIS study: one selectable row per
    Austrian trial site, and a hint in place of the table when the payload
    offers none.

    Rendered through the project's template engine rather than a widget
    template, because the form renderer only searches Django's own template
    directories.
    """
    template = 'submissions/ctr/trial_sites.html'
    sites = ()

    def render(self, name, value, attrs=None, renderer=None):
        selected = {str(v) for v in (value or [])}
        rows = [dict(site, checked=site['key'] in selected)
                for site in self.sites]

        # Two investigators of the same name at the same address would read as
        # one row twice; those get their department and organisation as well.
        ambiguous = Counter((r['name'], r['email']) for r in rows)
        for row in rows:
            row['detail'] = ' – '.join(
                p for p in (row['department'], row['organisation']) if p
            ) if ambiguous[(row['name'], row['email'])] > 1 else ''

        return render_to_string(self.template, {
            'name': name,
            'rows': rows,
            # readonly mode disables every widget of the form; a disabled
            # checkbox still shows who was invited.
            'disabled': bool(self.attrs.get('disabled')),
        })


class CategorizationForm(ReadonlyFormMixin, forms.ModelForm):
    # The CTIS replacement for `invite_primary_investigator_to_meeting`: the
    # keys of the ticked trial sites. Declared here so it renders as the site
    # table instead of the model field's raw comma-separated text input.
    ctr_invited_trial_sites = forms.MultipleChoiceField(
        required=False, widget=TrialSiteSelect,
        label=_('invite_primary_investigator_to_meeting'))

    class Meta:
        model = Submission
        fields = (
            'workflow_lane', 'medical_categories', 'clinics', 'remission',
            'invite_primary_investigator_to_meeting', 'ctr_invited_trial_sites',
        )
        labels = {
            'workflow_lane': _('workflow lane'),
            'medical_categories': _('medical_categories'),
            'clinics': 'Krankenanstalten',
            'remission': _('remission'),
            'invite_primary_investigator_to_meeting': _('invite_primary_investigator_to_meeting'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if kwargs.get('readonly', None) is None:
            clinic_filter = Q(deactivated=False)
            medical_category_filter = Q(is_disabled=False)
        else:
            clinic_filter = Q()
            medical_category_filter = Q()

        self.fields['medical_categories'].queryset = MedicalCategory.objects.filter(medical_category_filter).order_by(
            'name')

        # A CTIS study is always in the board lane and has neither clinics nor
        # a fee, and its investigators come from the payload rather than from a
        # single checkbox.
        self.is_ctr = self.instance.uses_ctr_form
        if self.is_ctr:
            del self.fields['clinics']
            del self.fields['remission']
            del self.fields['invite_primary_investigator_to_meeting']

            # Locked rather than hidden: the office reads « Standard » as
            # confirmation that the study is in the normal process. `disabled`
            # makes the value come from the initial data, so a submitted form
            # cannot clear it.
            self.fields['workflow_lane'].disabled = True
            self.initial['workflow_lane'] = SUBMISSION_LANE_BOARD

            sites = self.instance.ctr_trial_sites
            field = self.fields['ctr_invited_trial_sites']
            field.choices = [(s['key'], s['name']) for s in sites]
            field.widget.sites = sites
        else:
            del self.fields['ctr_invited_trial_sites']
            self.fields['clinics'].queryset = Clinic.objects.filter(clinic_filter).order_by('-is_favorite', 'name')

    def clean(self):
        cd = self.cleaned_data
        lane = cd.get('workflow_lane')
        if lane in (SUBMISSION_LANE_BOARD, SUBMISSION_LANE_EXPEDITED):
            require_fields(self, ('medical_categories',))
        if self.is_ctr:
            # The four « Investigator invited » markers stay a plain marker and
            # read this flag; for a CTIS study it means « at least one trial
            # site is ticked ».
            self.instance.invite_primary_investigator_to_meeting = \
                bool(cd.get('ctr_invited_trial_sites'))
        elif lane != SUBMISSION_LANE_BOARD:
            cd['invite_primary_investigator_to_meeting'] = False
        return cd


class DraftAssessmentReportDeadlineForm(ReadonlyFormMixin, forms.ModelForm):
    draft_assessment_report_deadline = DateField(
        label=_('Draft Assessment Report deadline'), required=False)

    class Meta:
        model = Submission
        fields = ('draft_assessment_report_deadline',)


# The three states a study's Draft Assessment Report deadline can be in,
# shared between the CTIS overview's filter and its annotated queryset
# (`ecs/core/views/submissions.py:ctis_overview`).
DAR_DEADLINE_NOT_ENTERED = 'not_entered'
DAR_DEADLINE_UPCOMING = 'upcoming'
DAR_DEADLINE_PASSED = 'passed'


class CTISOverviewFilterForm(forms.Form):
    deadline_status = forms.MultipleChoiceField(
        required=False,
        label='Deadline-Status',
        choices=(
            (DAR_DEADLINE_NOT_ENTERED, 'Keine Deadline gesetzt'),
            (DAR_DEADLINE_UPCOMING, 'Anstehend'),
            (DAR_DEADLINE_PASSED, 'Fällig'),
        ),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
    )
    uploaded = forms.MultipleChoiceField(
        required=False,
        label='Hochgeladen',
        choices=(
            ('yes', 'Ja'),
            ('no', 'Nein'),
        ),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
    )

    def __init__(self, data=None, *args, **kwargs):
        # Nothing submitted yet, and nothing saved for this user yet either
        # (`ecs_settings.ctis_overview_filter` starts as `{}`): default every
        # box to ticked, the same "everything on until you narrow it down"
        # convention `SubmissionFilterForm` uses, and for the same reason -
        # so an unfiltered visit isn't indistinguishable from "show nothing".
        if not data:
            data = {
                name: [c for c, _ in field.choices]
                for name, field in self.base_fields.items()
            }
        super().__init__(data, *args, **kwargs)

    def filter(self, submissions):
        statuses = self.cleaned_data.get('deadline_status')
        if statuses:
            submissions = submissions.filter(deadline_status__in=statuses)
        # Checking neither or both means "don't care" - only a single ticked
        # box actually narrows anything, same as the checkbox groups on the
        # classic study list filter.
        uploaded = self.cleaned_data.get('uploaded')
        if uploaded and len(uploaded) == 1:
            submissions = submissions.filter(
                draft_assessment_report_uploaded=(uploaded[0] == 'yes'))
        return submissions


class SubmissionDocumentForm(DocumentForm):
    """
    The classic per-application `DocumentForm` - same fields, same upload/
    replace/correct-metadata behaviour, same `ecs.setupDocumentUploadForms()`
    JS - restricted to the handful of types this study-level tab is for,
    since it isn't the classic per-application document list.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['doctype'].queryset = DocumentType.objects.filter(
            identifier__in=('draft_assessment_report', 'other'))


class BiasedBoardMemberForm(forms.Form):
    biased_board_member = forms.ModelChoiceField(
        queryset=User.objects
        .filter(is_active=True, groups__name='Board Member')
        .select_related('profile')
        .order_by('last_name', 'first_name', 'email')
    )

    def __init__(self, *args, submission=None, **kwargs):
        super().__init__(*args, **kwargs)
        f = self.fields['biased_board_member']
        f.queryset = f.queryset.exclude(
            id__in=submission.biased_board_members.values('id'))
