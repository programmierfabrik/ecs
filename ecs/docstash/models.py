import math
import uuid

from django.db import models
from django.http import QueryDict
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils import timezone
from django_extensions.db.fields.json import JSONField

from ecs import settings
from ecs.core.forms import SubmissionFormForm, ParticipatingCenterNonSubjectFormSet, InvestigatorFormSet, \
    ForeignParticipatingCenterFormSet, MeasureFormSet, RoutineMeasureFormSet, NonTestedUsedDrugFormSet
from ecs.core.models import InvestigatorEmployee
from ecs.core.models.constants import SUBMISSION_TYPE_MULTICENTRIC, SUBMISSION_TYPE_MULTICENTRIC_LOCAL
from ecs.core.models.names import Name
from ecs.documents.models import Document
from ecs.utils.viewutils import render_pdf_context


class DocStash(models.Model):
    class ConcurrentModification(Exception):
        pass

    key = models.UUIDField(default=uuid.uuid4, primary_key=True)
    group = models.CharField(max_length=120, db_index=True, null=True)
    current_version = models.IntegerField(default=-1)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    modtime = models.DateTimeField(auto_now=True)
    name = models.TextField(blank=True, null=True)
    value = JSONField(null=False)
    # Only for create_submission
    preview_generated_at = models.DateTimeField(null=True)

    content_type = models.ForeignKey(ContentType, null=True, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField(null=True)
    parent_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        unique_together = ('group', 'owner', 'content_type', 'object_id')

    def __getitem__(self, key):
        return self.value[key]

    def __setitem__(self, key, value):
        self.value[key] = value

    def __delitem__(self, key):
        del self.value[key]

    def __contains__(self, key):
        return key in self.value

    def get(self, name, default=None):
        return self.value.get(name, default)

    @property
    def POST(self):
        if 'POST' in self.value:
            return QueryDict(self.value['POST'])
        return None

    @POST.setter
    def POST(self, data):
        self.value['POST'] = data.urlencode()

    def save(self, **kwargs):
        if DocStash.objects.filter(key=self.key).exists():
            updated = DocStash.objects.filter(
                key=self.key, current_version=self.current_version
            ).update(current_version=models.F('current_version') + 1)
            if not updated:
                raise self.ConcurrentModification()

        self.current_version += 1
        return super(DocStash, self).save(**kwargs)

    def preview_generation_cooldown(self):
        cooldown_duration = timezone.timedelta(minutes=5)
        if not self.preview_generated_at:
            # No cooldown if preview has not been generated yet
            return 0

        time_passed_since_last_generation = timezone.now() - self.preview_generated_at
        if time_passed_since_last_generation >= cooldown_duration:
            return 0  # No cooldown if the required time has passed

        cooldown_remaining = cooldown_duration - time_passed_since_last_generation
        # Return remaining cooldown length in seconds

        return math.ceil(cooldown_remaining.total_seconds())
    
    def can_generate(self):
        if not self.preview_generated_at:
            return True
        five_minutes_ago = timezone.now() - timezone.timedelta(minutes=5)
        return self.preview_generated_at <= five_minutes_ago

    def render_preview_pdf(self):
        if self.group == 'ecs.core.views.submissions.create_submission_form':
            self.preview_generated_at = timezone.now()
            self.save(update_fields=('preview_generated_at',))
            form = SubmissionFormForm(self.POST)
            form.is_valid()
            mocked_form = form.cleaned_data

            # default values that are computed or created after inserting
            measure_formset = MeasureFormSet(self.POST, prefix='measure', initial=None)
            routinemeasure_formset = RoutineMeasureFormSet(self.POST, prefix='routinemeasure', initial=None)
            nontesteduseddrug_formset = NonTestedUsedDrugFormSet(self.POST, prefix='nontesteduseddrug', initial=None)
            participatingcenternonsubject_formset = ParticipatingCenterNonSubjectFormSet(self.POST,
                                                                                         prefix='participatingcenternonsubject',
                                                                                         initial=None)

            foreignparticipatingcenter_formset = ForeignParticipatingCenterFormSet(self.POST,
                                                                                   prefix='foreignparticipatingcenter',
                                                                                   initial=None)
            investigator_formset = InvestigatorFormSet(self.POST, prefix='investigator', initial=None)

            def parse_formset(formset):
                formset_items = []
                for form in formset:
                    form.is_valid()
                    # Edge case for nested. if nested exists carry it over. else just cleaned_data
                    result = {**form.cleaned_data, 'nested': form.nested} if hasattr(form,
                                                                                     'nested') else form.cleaned_data
                    formset_items.append(result)

                return formset_items

            measures = parse_formset(measure_formset)
            routinemeasures = parse_formset(routinemeasure_formset)
            nontesteduseddrugs = parse_formset(nontesteduseddrug_formset)
            participatingcenternonsubjects = parse_formset(participatingcenternonsubject_formset)
            foreignparticipatingcenters = parse_formset(foreignparticipatingcenter_formset)
            investigators = parse_formset(investigator_formset)

            name_fields = ['gender', 'title', 'first_name', 'last_name', 'suffix_title']
            sex_field = InvestigatorEmployee._meta.get_field('sex')

            # Set the employees of the investigator
            for investigator in investigators:
                employee_formset = investigator.pop('nested')
                employees = parse_formset(employee_formset)

                # Use the labels from InvestigatorEmployee class for sex
                for employee in employees:
                    for value, label in sex_field.choices:
                        if value == employee['sex']:
                            employee.update({
                                'get_sex_display': label
                            })

                investigator.update({
                    'contact': Name(**{field: investigator.get(f'contact_{field}') for field in name_fields}),
                    'employees': {
                        'all': employees
                    }
                })

            def has_matching_uuid(investigator):
                uuid = getattr(investigator.get('ethics_commission'), 'uuid', None)
                if uuid:
                    return str(uuid).replace('-', '') != settings.ETHICS_COMMISSION_UUID
                return False
            non_system_ec = list(filter(has_matching_uuid, investigators))

            submission_type = mocked_form.get('submission_type')
            is_multicentric = (
                submission_type == SUBMISSION_TYPE_MULTICENTRIC or
                submission_type == SUBMISSION_TYPE_MULTICENTRIC_LOCAL or
                len(non_system_ec) > 0 or
                len(participatingcenternonsubjects) > 0 or
                len(foreignparticipatingcenters) > 0
            )

            # Set values that are either generate after a save or a function properties that are computed
            mocked_form.update({
                'version': -1,
                'is_multicentric': is_multicentric,
                'is_monocentric': not is_multicentric,
                'is_amg': mocked_form.get('project_type_non_reg_drug') or mocked_form.get('project_type_reg_drug'),
                'is_mpg': mocked_form.get('project_type_medical_device'),
                'study_plan_open': mocked_form.get('study_plan_blind') == 0,
                'study_plan_single_blind': mocked_form.get('study_plan_blind') == 1,
                'study_plan_double_blind': mocked_form.get('study_plan_blind') == 2,
                'study_plan_alpha_single_sided': mocked_form.get('study_plan_alpha_sided') == 0,
                'study_plan_alpha_double_sided': mocked_form.get('study_plan_alpha_sided') == 1,
                'study_plan_dataprotection_none': mocked_form.get('study_plan_dataprotection_choice') == 'personal',
                'study_plan_dataprotection_partial': mocked_form.get(
                    'study_plan_dataprotection_choice') == 'non-personal',
                'study_plan_dataprotection_full': mocked_form.get('study_plan_dataprotection_choice') == 'anonymous',
                'submitter_contact': Name(
                    **{field: mocked_form.get(f'submitter_contact_{field}') for field in name_fields}),
                'investigators': {
                    'all': investigators,
                    'non_system_ec': {
                        'exists': len(non_system_ec) > 0,
                    },
                },
                'participatingcenternonsubject_set': {
                    'exists': len(participatingcenternonsubjects) > 0,
                    'all': participatingcenternonsubjects,
                },
                'foreignparticipatingcenter_set': {
                    'exists': len(foreignparticipatingcenters) > 0,
                    'all': foreignparticipatingcenters,
                },
                'nontesteduseddrug_set': {
                    'all': nontesteduseddrugs,
                },
                'measures_study_specific': measures,
                'measures_nonspecific': routinemeasures,
            })

            return render_pdf_context('submissions/pdf/view.html', {
                'submission_form': form.cleaned_data,
                'watermark': True,
                'documents': Document.objects.filter(id__in=self.value.get('document_pks', []))
                                      .order_by('doctype__identifier', 'date', 'name')
            })
        else:
            return None
