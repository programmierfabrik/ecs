from datetime import timedelta

from django import forms
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from ecs import settings
from ecs.core.forms.utils import ReadonlyFormMixin
from ecs.core.models import Submission
from ecs.core.models.clinic import Clinic
from ecs.core.models.constants import SUBMISSION_LANE_BOARD, SUBMISSION_LANE_EXPEDITED, \
    SUBMISSION_LANE_RETROSPECTIVE_THESIS
from ecs.core.models.core import MedicalCategory
from ecs.meetings.models import Meeting
from ecs.utils.formutils import require_fields


class CategorizationForm(ReadonlyFormMixin, forms.ModelForm):
    meeting_to_be_scheduled_board = forms.ModelChoiceField(Meeting.objects.none(), label='Sitzung', initial=0)
    meeting_to_be_scheduled_thesis = forms.ModelChoiceField(Meeting.objects.none(), label='Sitzung', initial=0)

    class Meta:
        model = Submission
        fields = (
            'workflow_lane', 'medical_categories', 'clinics', 'remission',
            'invite_primary_investigator_to_meeting',
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

        self.fields['clinics'].queryset = Clinic.objects.filter(clinic_filter).order_by('-is_favorite', 'name')
        self.fields['medical_categories'].queryset = MedicalCategory.objects.filter(medical_category_filter).order_by(
            'name')
        
        # Querysets for meetings. since you cant just schedule any meeting (deadlines) we need to find out
        # which are available. Used the same logic as in MeetingManager.next_schedulable_meeting
        self.fields['meeting_to_be_scheduled_board'].label_from_instance = \
            self.fields['meeting_to_be_scheduled_thesis'].label_from_instance = lambda obj: obj.title

        first_sf = self.instance.forms.order_by('created_at')[0]
        try:
            accepted_sf = self.instance.forms.filter(is_acknowledged=True).order_by('created_at')[0]
        except IndexError:
            print("IndexError: using current_submisison_form")
            accepted_sf = self.instance.current_submission_form

        grace_period = getattr(settings, 'ECS_MEETING_GRACE_PERIOD', timedelta(0))
        self.fields['meeting_to_be_scheduled_board'].widget.attrs['p_hidden'] = True
        self.fields['meeting_to_be_scheduled_board'].queryset = (
            Meeting.objects.filter(deadline__gt=first_sf.created_at)
            .filter(deadline__gt=accepted_sf.created_at - grace_period)
        ).order_by('start')
        self.fields['meeting_to_be_scheduled_thesis'].widget.attrs['p_hidden'] = True
        self.fields['meeting_to_be_scheduled_thesis'].queryset = (
            Meeting.objects.filter(deadline_diplomathesis__gt=first_sf.created_at)
            .filter(deadline_diplomathesis__gt=accepted_sf.created_at - grace_period)
        ).order_by('start')

    def clean(self):
        cd = self.cleaned_data
        lane = cd.get('workflow_lane')
        if lane in (SUBMISSION_LANE_BOARD, SUBMISSION_LANE_EXPEDITED):
            require_fields(self, ('medical_categories',))
        if lane != SUBMISSION_LANE_BOARD:
            cd['invite_primary_investigator_to_meeting'] = False
        return cd

    def save(self, commit=True):
        instance = super().save(commit=commit)
        # Instead of changing the whole workflow and the logic how the categoriziation works
        # We instead create a shallow entry which will later be updated in the categorization workflow
        # visible needs to be false so the duration gets updated if the visibilty is actually true (workflow_lane = BOARD)
        # Duration 0 is just a default value since it will be updated either way
        duration = timedelta(minutes=0)
        visible = False
        
        workflow_lane = self.cleaned_data['workflow_lane']
        meeting_to_be_scheduled_board = self.cleaned_data['meeting_to_be_scheduled_board']
        meeting_to_be_scheduled_thesis = self.cleaned_data['meeting_to_be_scheduled_thesis']

        meeting_to_be_scheduled = meeting_to_be_scheduled_board
        if workflow_lane == SUBMISSION_LANE_RETROSPECTIVE_THESIS and meeting_to_be_scheduled_thesis:
            meeting_to_be_scheduled = meeting_to_be_scheduled_thesis

        if meeting_to_be_scheduled:
            new_entry = meeting_to_be_scheduled.add_entry(submission=instance, duration=duration, visible=visible)
        return instance

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
