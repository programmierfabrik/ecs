from django import forms
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from ecs.core.forms.utils import ReadonlyFormMixin
from ecs.core.models import Submission
from ecs.core.models.clinic import Clinic
from ecs.core.models.constants import SUBMISSION_LANE_BOARD, SUBMISSION_LANE_EXPEDITED
from ecs.core.models.core import MedicalCategory
from ecs.utils.formutils import require_fields


class CategorizationForm(ReadonlyFormMixin, forms.ModelForm):
    class Meta:
        model = Submission
        fields = (
            'workflow_lane', 'medical_categories', 'clinics', 'remission',
            'invite_primary_investigator_to_meeting',
        )
        labels = {
            'workflow_lane': _('workflow lane'),
            'medical_categories': _('medical_categories'),
            'clinics': 'Kliniken',
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

    def clean(self):
        cd = self.cleaned_data
        lane = cd.get('workflow_lane')
        if lane in (SUBMISSION_LANE_BOARD, SUBMISSION_LANE_EXPEDITED):
            require_fields(self, ('medical_categories',))
        if lane != SUBMISSION_LANE_BOARD:
            cd['invite_primary_investigator_to_meeting'] = False
        return cd


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
