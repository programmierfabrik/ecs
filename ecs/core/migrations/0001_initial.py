# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='MySubmission',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('user_id', models.IntegerField()),
                ('submission_id', models.IntegerField()),
            ],
            options={
                'db_table': 'core_mysubmission',
                'managed': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='AdvancedSettings',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='EthicsCommission',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uuid', models.CharField(max_length=32)),
                ('name', models.CharField(max_length=120)),
                ('address_1', models.CharField(max_length=120)),
                ('address_2', models.CharField(max_length=120)),
                ('zip_code', models.CharField(max_length=10)),
                ('city', models.CharField(max_length=80)),
                ('contactname', models.CharField(max_length=120, null=True)),
                ('chairperson', models.CharField(max_length=120, null=True)),
                ('email', models.EmailField(max_length=75, null=True)),
                ('url', models.URLField(null=True)),
                ('phone', models.CharField(max_length=60, null=True)),
                ('fax', models.CharField(max_length=60, null=True)),
                ('vote_receiver', models.EmailField(max_length=75, null=True, blank=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ExpeditedReviewCategory',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=60)),
                ('abbrev', models.CharField(unique=True, max_length=12)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ForeignParticipatingCenter',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=60)),
                ('investigator_name', models.CharField(max_length=60, blank=True)),
            ],
            options={
                'ordering': ['id'],
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Investigator',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('main', models.BooleanField(default=True)),
                ('organisation', models.CharField(max_length=80)),
                ('phone', models.CharField(max_length=30, blank=True)),
                ('mobile', models.CharField(max_length=30, blank=True)),
                ('fax', models.CharField(max_length=30, blank=True)),
                ('email', models.EmailField(max_length=75)),
                ('jus_practicandi', models.BooleanField(default=False)),
                ('specialist', models.CharField(max_length=80, blank=True)),
                ('certified', models.BooleanField(default=False)),
                ('subject_count', models.IntegerField()),
                ('contact_gender', models.CharField(max_length=1, null=True, choices=[(b'f', 'Ms'), (b'm', 'Mr')])),
                ('contact_title', models.CharField(max_length=30, blank=True)),
                ('contact_first_name', models.CharField(max_length=30)),
                ('contact_last_name', models.CharField(max_length=30)),
            ],
            options={
                'ordering': ['id'],
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='InvestigatorEmployee',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('sex', models.CharField(max_length=1, choices=[(b'm', 'Mr'), (b'f', 'Ms')])),
                ('title', models.CharField(max_length=40, blank=True)),
                ('firstname', models.CharField(max_length=40)),
                ('surname', models.CharField(max_length=40)),
                ('organisation', models.CharField(max_length=80)),
            ],
            options={
                'ordering': ['id'],
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Measure',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('category', models.CharField(max_length=3, choices=[(b'6.1', 'only study-related'), (b'6.2', 'for routine purposes')])),
                ('type', models.CharField(max_length=150)),
                ('count', models.CharField(max_length=150)),
                ('period', models.CharField(max_length=30)),
                ('total', models.CharField(max_length=30)),
            ],
            options={
                'ordering': ['id'],
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='MedicalCategory',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=60)),
                ('abbrev', models.CharField(unique=True, max_length=12)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='NonTestedUsedDrug',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('generic_name', models.CharField(max_length=40)),
                ('preparation_form', models.CharField(max_length=40)),
                ('dosage', models.CharField(max_length=40)),
            ],
            options={
                'ordering': ['id'],
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Submission',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('ec_number', models.PositiveIntegerField(unique=True, db_index=True)),
                ('workflow_lane', models.SmallIntegerField(db_index=True, null=True, choices=[(3, 'board'), (2, 'expedited'), (1, 'retrospective thesis'), (4, 'Local EC')])),
                ('remission', models.NullBooleanField(default=False)),
                ('executive_comment', models.TextField(null=True, blank=True)),
                ('legal_and_patient_review_required', models.NullBooleanField(default=False)),
                ('statistical_review_required', models.NullBooleanField(default=False)),
                ('insurance_review_required', models.NullBooleanField(default=False)),
                ('gcp_review_required', models.NullBooleanField(default=False)),
                ('invite_primary_investigator_to_meeting', models.BooleanField(default=False)),
                ('is_transient', models.BooleanField(default=False)),
                ('is_finished', models.BooleanField(default=False)),
                ('is_expired', models.BooleanField(default=False)),
                ('billed_at', models.DateTimeField(default=None, null=True, db_index=True, blank=True)),
                ('valid_until', models.DateField(null=True, blank=True)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='SubmissionForm',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('is_notification_update', models.BooleanField(default=False)),
                ('is_transient', models.BooleanField(default=False)),
                ('is_acknowledged', models.BooleanField(default=False)),
                ('project_title', models.TextField()),
                ('eudract_number', models.CharField(max_length=60, null=True, blank=True)),
                ('submission_type', models.SmallIntegerField(default=1, null=True, blank=True, choices=[(1, 'monocentric'), (2, 'multicentric, main ethics commission'), (6, 'multicentric, local ethics commission')])),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('sponsor_name', models.CharField(max_length=100, null=True)),
                ('sponsor_address', models.CharField(max_length=60, null=True)),
                ('sponsor_zip_code', models.CharField(max_length=10, null=True)),
                ('sponsor_city', models.CharField(max_length=80, null=True)),
                ('sponsor_phone', models.CharField(max_length=30, null=True)),
                ('sponsor_fax', models.CharField(max_length=30, null=True, blank=True)),
                ('sponsor_email', models.EmailField(max_length=75, null=True)),
                ('sponsor_agrees_to_publishing', models.BooleanField(default=True)),
                ('sponsor_uid', models.CharField(max_length=35, null=True, blank=True)),
                ('invoice_name', models.CharField(max_length=160, null=True, blank=True)),
                ('invoice_address', models.CharField(max_length=60, null=True, blank=True)),
                ('invoice_zip_code', models.CharField(max_length=10, null=True, blank=True)),
                ('invoice_city', models.CharField(max_length=80, null=True, blank=True)),
                ('invoice_phone', models.CharField(max_length=50, null=True, blank=True)),
                ('invoice_fax', models.CharField(max_length=45, null=True, blank=True)),
                ('invoice_email', models.EmailField(max_length=75, null=True, blank=True)),
                ('invoice_uid', models.CharField(max_length=35, null=True, blank=True)),
                ('project_type_non_reg_drug', models.BooleanField(default=False)),
                ('project_type_reg_drug', models.BooleanField(default=False)),
                ('project_type_reg_drug_within_indication', models.BooleanField(default=False)),
                ('project_type_reg_drug_not_within_indication', models.BooleanField(default=False)),
                ('project_type_medical_method', models.BooleanField(default=False)),
                ('project_type_medical_device', models.BooleanField(default=False)),
                ('project_type_medical_device_with_ce', models.BooleanField(default=False)),
                ('project_type_medical_device_without_ce', models.BooleanField(default=False)),
                ('project_type_medical_device_performance_evaluation', models.BooleanField(default=False)),
                ('project_type_basic_research', models.BooleanField(default=False)),
                ('project_type_genetic_study', models.BooleanField(default=False)),
                ('project_type_register', models.BooleanField(default=False)),
                ('project_type_biobank', models.BooleanField(default=False)),
                ('project_type_retrospective', models.BooleanField(default=False)),
                ('project_type_questionnaire', models.BooleanField(default=False)),
                ('project_type_education_context', models.SmallIntegerField(blank=True, null=True, choices=[(1, b'Dissertation'), (2, b'Diplomarbeit')])),
                ('project_type_misc', models.TextField(null=True, blank=True)),
                ('project_type_psychological_study', models.BooleanField(default=False)),
                ('project_type_nursing_study', models.BooleanField(default=False)),
                ('project_type_non_interventional_study', models.BooleanField(default=False)),
                ('project_type_gender_medicine', models.BooleanField(default=False)),
                ('specialism', models.TextField(null=True)),
                ('pharma_checked_substance', models.TextField(null=True, blank=True)),
                ('pharma_reference_substance', models.TextField(null=True, blank=True)),
                ('medtech_checked_product', models.TextField(null=True, blank=True)),
                ('medtech_reference_substance', models.TextField(null=True, blank=True)),
                ('clinical_phase', models.CharField(max_length=10, null=True, blank=True)),
                ('already_voted', models.BooleanField(default=False)),
                ('subject_count', models.IntegerField()),
                ('subject_minage', models.IntegerField(null=True, blank=True)),
                ('subject_maxage', models.IntegerField(null=True, blank=True)),
                ('subject_noncompetents', models.BooleanField(default=False)),
                ('subject_males', models.BooleanField(default=False)),
                ('subject_females', models.BooleanField(default=False)),
                ('subject_childbearing', models.BooleanField(default=False)),
                ('subject_duration', models.CharField(max_length=200)),
                ('subject_duration_active', models.CharField(max_length=200)),
                ('subject_duration_controls', models.CharField(max_length=200, null=True, blank=True)),
                ('subject_planned_total_duration', models.CharField(max_length=250)),
                ('substance_preexisting_clinical_tries', models.NullBooleanField(db_column=b'existing_tries')),
                ('substance_p_c_t_phase', models.CharField(max_length=80, null=True, blank=True)),
                ('substance_p_c_t_period', models.TextField(null=True, blank=True)),
                ('substance_p_c_t_application_type', models.CharField(max_length=145, null=True, blank=True)),
                ('substance_p_c_t_gcp_rules', models.NullBooleanField()),
                ('substance_p_c_t_final_report', models.NullBooleanField()),
                ('medtech_product_name', models.CharField(max_length=210, null=True, blank=True)),
                ('medtech_manufacturer', models.CharField(max_length=80, null=True, blank=True)),
                ('medtech_certified_for_exact_indications', models.NullBooleanField()),
                ('medtech_certified_for_other_indications', models.NullBooleanField()),
                ('medtech_ce_symbol', models.NullBooleanField()),
                ('medtech_manual_included', models.NullBooleanField()),
                ('medtech_technical_safety_regulations', models.TextField(null=True, blank=True)),
                ('medtech_departure_from_regulations', models.TextField(null=True, blank=True)),
                ('insurance_not_required', models.BooleanField(default=False)),
                ('insurance_name', models.CharField(max_length=125, null=True, blank=True)),
                ('insurance_address', models.CharField(max_length=80, null=True, blank=True)),
                ('insurance_phone', models.CharField(max_length=30, null=True, blank=True)),
                ('insurance_contract_number', models.CharField(max_length=60, null=True, blank=True)),
                ('insurance_validity', models.CharField(max_length=60, null=True, blank=True)),
                ('additional_therapy_info', models.TextField(blank=True)),
                ('german_project_title', models.TextField(null=True)),
                ('german_summary', models.TextField(null=True)),
                ('german_preclinical_results', models.TextField(null=True)),
                ('german_primary_hypothesis', models.TextField(null=True)),
                ('german_inclusion_exclusion_crit', models.TextField(null=True)),
                ('german_ethical_info', models.TextField(null=True)),
                ('german_protected_subjects_info', models.TextField(null=True, blank=True)),
                ('german_recruitment_info', models.TextField(null=True)),
                ('german_consent_info', models.TextField(null=True)),
                ('german_risks_info', models.TextField(null=True)),
                ('german_benefits_info', models.TextField(null=True)),
                ('german_relationship_info', models.TextField(null=True)),
                ('german_concurrent_study_info', models.TextField(null=True)),
                ('german_sideeffects_info', models.TextField(null=True)),
                ('german_statistical_info', models.TextField(null=True, blank=True)),
                ('german_dataprotection_info', models.TextField(null=True, blank=True)),
                ('german_aftercare_info', models.TextField(null=True)),
                ('german_payment_info', models.TextField(null=True)),
                ('german_abort_info', models.TextField(null=True)),
                ('german_dataaccess_info', models.TextField(null=True, blank=True)),
                ('german_financing_info', models.TextField(null=True, blank=True)),
                ('german_additional_info', models.TextField(null=True, blank=True)),
                ('study_plan_blind', models.SmallIntegerField(choices=[(0, 'open'), (1, 'blind'), (2, 'double-blind'), (3, 'not applicable')])),
                ('study_plan_observer_blinded', models.BooleanField(default=False)),
                ('study_plan_randomized', models.BooleanField(default=False)),
                ('study_plan_parallelgroups', models.BooleanField(default=False)),
                ('study_plan_controlled', models.BooleanField(default=False)),
                ('study_plan_cross_over', models.BooleanField(default=False)),
                ('study_plan_placebo', models.BooleanField(default=False)),
                ('study_plan_factorized', models.BooleanField(default=False)),
                ('study_plan_pilot_project', models.BooleanField(default=False)),
                ('study_plan_equivalence_testing', models.BooleanField(default=False)),
                ('study_plan_misc', models.TextField(null=True, blank=True)),
                ('study_plan_number_of_groups', models.TextField(null=True, blank=True)),
                ('study_plan_stratification', models.TextField(null=True, blank=True)),
                ('study_plan_sample_frequency', models.TextField(null=True, blank=True)),
                ('study_plan_primary_objectives', models.TextField(null=True, blank=True)),
                ('study_plan_null_hypothesis', models.TextField(null=True, blank=True)),
                ('study_plan_alternative_hypothesis', models.TextField(null=True, blank=True)),
                ('study_plan_secondary_objectives', models.TextField(null=True, blank=True)),
                ('study_plan_alpha', models.CharField(max_length=80)),
                ('study_plan_alpha_sided', models.SmallIntegerField(blank=True, null=True, choices=[(0, 'single-sided'), (1, 'double-sided')])),
                ('study_plan_power', models.CharField(max_length=80)),
                ('study_plan_statalgorithm', models.CharField(max_length=80)),
                ('study_plan_multiple_test', models.BooleanField(default=False)),
                ('study_plan_multiple_test_correction_algorithm', models.CharField(max_length=100, null=True, blank=True)),
                ('study_plan_dropout_ratio', models.CharField(max_length=80)),
                ('study_plan_population_intention_to_treat', models.BooleanField(default=False)),
                ('study_plan_population_per_protocol', models.BooleanField(default=False)),
                ('study_plan_interim_evaluation', models.BooleanField(default=False)),
                ('study_plan_abort_crit', models.CharField(max_length=265, null=True, blank=True)),
                ('study_plan_planned_statalgorithm', models.TextField(null=True, blank=True)),
                ('study_plan_dataquality_checking', models.TextField()),
                ('study_plan_datamanagement', models.TextField()),
                ('study_plan_biometric_planning', models.CharField(max_length=260)),
                ('study_plan_statistics_implementation', models.CharField(max_length=270)),
                ('study_plan_dataprotection_choice', models.CharField(default=b'non-personal', max_length=15, choices=[(b'personal', 'individual-related'), (b'non-personal', 'implicit individual-related'), (b'anonymous', 'completely anonymous')])),
                ('study_plan_dataprotection_reason', models.CharField(max_length=120, null=True, blank=True)),
                ('study_plan_dataprotection_dvr', models.CharField(max_length=180, null=True, blank=True)),
                ('study_plan_dataprotection_anonalgoritm', models.TextField(null=True, blank=True)),
                ('submitter_email', models.EmailField(max_length=75, null=True)),
                ('submitter_organisation', models.CharField(max_length=180)),
                ('submitter_jobtitle', models.CharField(max_length=130)),
                ('submitter_is_coordinator', models.BooleanField(default=False)),
                ('submitter_is_main_investigator', models.BooleanField(default=False)),
                ('submitter_is_sponsor', models.BooleanField(default=False)),
                ('submitter_is_authorized_by_sponsor', models.BooleanField(default=False)),
                ('date_of_receipt', models.DateField(null=True, blank=True)),
                ('submitter_contact_gender', models.CharField(max_length=1, null=True, choices=[(b'f', 'Ms'), (b'm', 'Mr')])),
                ('submitter_contact_title', models.CharField(max_length=30, blank=True)),
                ('submitter_contact_first_name', models.CharField(max_length=30)),
                ('submitter_contact_last_name', models.CharField(max_length=30)),
                ('invoice_contact_gender', models.CharField(blank=True, max_length=1, null=True, choices=[(b'f', 'Ms'), (b'm', 'Mr')])),
                ('invoice_contact_title', models.CharField(max_length=30, blank=True)),
                ('invoice_contact_first_name', models.CharField(max_length=30, blank=True)),
                ('invoice_contact_last_name', models.CharField(max_length=30, blank=True)),
                ('sponsor_contact_gender', models.CharField(max_length=1, null=True, choices=[(b'f', 'Ms'), (b'm', 'Mr')])),
                ('sponsor_contact_title', models.CharField(max_length=30, blank=True)),
                ('sponsor_contact_first_name', models.CharField(max_length=30)),
                ('sponsor_contact_last_name', models.CharField(max_length=30)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TemporaryAuthorization',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('start', models.DateTimeField()),
                ('end', models.DateTimeField()),
                ('submission', models.ForeignKey(related_name='temp_auth', to='core.Submission')),
                ('user', models.ForeignKey(related_name='temp_submission_auth', to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
