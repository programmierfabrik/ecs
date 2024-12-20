import hashlib
import os
import time
from io import BytesIO

import xlwt
from celery.schedules import crontab
from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Min
from django.utils import timezone
from django.utils.translation import gettext as _

from ecs.celery import app as celery_app
from ecs.communication.utils import send_system_message_template
from ecs.core.forms import AllSubmissionsFilterForm
from ecs.core.models import Submission, SubmissionForm, Investigator
from ecs.core.paper_forms import get_field_info
from ecs.docstash.models import DocStash

from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@celery_app.task()
def render_submission_form(submission_form_id=None):
    try:
        sf = SubmissionForm.unfiltered.get(id=submission_form_id)
        sf.render_pdf_document()
    except SubmissionForm.DoesNotExist:
        logger.error("SubmissionForm(id=%d) doesn't exist", submission_form_id)


@celery_app.task
def xls_export(user_id=None, filters=None):
    user = User.objects.get(id=user_id)

    # Use same filters as selected in the HTML view.
    filterform = AllSubmissionsFilterForm(filters)
    submissions = filterform.filter_submissions(Submission.objects.all(), user)

    submissions = submissions.select_related(
        'current_submission_form',
        'current_submission_form__primary_investigator',
        'current_published_vote',
        'presenter', 'presenter__profile',
    ).prefetch_related(
        'current_submission_form__investigators',
        'current_submission_form__foreignparticipatingcenter_set',
        'medical_categories',
    ).annotate(first_sf_date=Min('forms__created_at')).order_by('ec_number')

    xls = xlwt.Workbook(encoding="utf-8")
    sheet = xls.add_sheet(_('Submissions'))
    sheet.panes_frozen = True
    sheet.horz_split_pos = 3

    header = xlwt.easyxf(
        'font: bold on; align: horiz center, vert center, wrap on;')
    italic = xlwt.easyxf('font: italic on;')

    def label(f):
        return str(get_field_info(SubmissionForm, f).label)

    def inv_label(f):
        return str(get_field_info(Investigator, f).label)

    sheet.write_merge(0, 2, 0, 0, _('EC-Number'), header)
    sheet.write_merge(0, 2, 1, 1, label('project_title'), header)
    sheet.write_merge(0, 2, 2, 2, label('german_project_title'), header)
    sheet.write_merge(0, 2, 3, 3, label('eudract_number'), header)
    sheet.write_merge(0, 1, 4, 5, _('AMG'), header)
    sheet.write(2, 4, _('Yes') + '/' + _('No'), header)
    sheet.write(2, 5, _('Type'), header)
    sheet.write_merge(0, 2, 6, 6, _('MPG'), header)
    sheet.write_merge(0, 2, 7, 7, _('medtech_eu_ct_id'), header)
    sheet.write_merge(0, 2, 8, 8, _('monocentric') + '/' + _('multicentric'),
                      header)
    sheet.write_merge(0, 2, 9, 9, _('workflow lane'), header)
    sheet.write_merge(0, 2, 10, 10, _('remission'), header)
    sheet.write_merge(0, 2, 11, 11, _('Medical Categories'), header)
    sheet.write_merge(0, 2, 12, 12, _('Phase'), header)
    sheet.write_merge(0, 1, 13, 14, _('Vote'), header)
    sheet.write(2, 13, _('Vote'), header)
    sheet.write(2, 14, _('valid until'), header)
    sheet.write_merge(0, 2, 15, 15, _('first acknowledged form'), header)
    sheet.write_merge(0, 1, 16, 18, _('Presenter'), header)
    sheet.write(2, 16, _('Organisation'), header)
    sheet.write(2, 17, _('name'), header)
    sheet.write(2, 18, _('email'), header)
    sheet.write_merge(0, 1, 19, 21, _('Submitter'), header)
    sheet.write(2, 19, label('submitter_organisation'), header)
    sheet.write(2, 20, _('contact person'), header)
    sheet.write(2, 21, _('email'), header)
    sheet.write_merge(0, 1, 22, 24, _('Sponsor'), header)
    sheet.write(2, 22, label('sponsor_name'), header)
    sheet.write(2, 23, _('contact person'), header)
    sheet.write(2, 24, _('email'), header)
    sheet.write_merge(0, 1, 25, 27, _('invoice recipient'), header)
    sheet.write(2, 25, label('invoice_name'), header)
    sheet.write(2, 26, _('contact person'), header)
    sheet.write(2, 27, _('email'), header)
    sheet.write_merge(0, 1, 28, 30, _('Primary Investigator'), header)
    sheet.write(2, 28, inv_label('organisation'), header)
    sheet.write(2, 29, _('investigator'), header)
    sheet.write(2, 30, _('email'), header)
    sheet.write_merge(0, 1, 31, 43, _('participants'), header)
    sheet.write(2, 31, label('subject_count'), header)
    sheet.write(2, 32, label('subject_minage'), header)
    sheet.write(2, 33, label('subject_minage_unit'), header)
    sheet.write(2, 34, label('subject_maxage'), header)
    sheet.write(2, 35, label('subject_maxage_unit'), header)
    sheet.write(2, 36, label('subject_noncompetent_guarded'), header)
    sheet.write(2, 37, label('subject_noncompetent_minor'), header)
    sheet.write(2, 38, label('subject_noncompetent_emergency_study'), header)
    sheet.write(2, 39, label('subject_noncompetent_unconscious'), header)
    sheet.write(2, 40, label('subject_males'), header)
    sheet.write(2, 41, label('subject_females'), header)
    sheet.write(2, 42, label('subject_childbearing'), header)
    sheet.write(2, 43, label('subject_divers'), header)
    sheet.write_merge(0, 0, 44, 64, _('type of project'), header)
    sheet.write_merge(1, 2, 44, 44, label('project_type_non_reg_drug'), header)
    sheet.write_merge(1, 1, 45, 47, label('project_type_reg_drug'), header)
    sheet.write(2, 45, _('Yes') + '/' + _('No'), header)
    sheet.write(2, 46, label('project_type_reg_drug_within_indication'), header)
    sheet.write(2, 47, label('project_type_reg_drug_not_within_indication'),
                header)
    sheet.write_merge(1, 2, 48, 48, label('project_type_medical_method'),
                      header)
    sheet.write_merge(1, 1, 49, 52, label('project_type_medical_device'),
                      header)
    sheet.write(2, 49, _('Yes') + '/' + _('No'), header)
    sheet.write(2, 50, label('project_type_medical_device_with_ce'), header)
    sheet.write(2, 51, label('project_type_medical_device_without_ce'), header)
    sheet.write(2, 52, label('project_type_medical_device_performance_evaluation'), header)
    sheet.write_merge(1, 2, 53, 53, label('project_type_basic_research'), header)
    sheet.write_merge(1, 2, 54, 54, label('project_type_genetic_study'), header)
    sheet.write_merge(1, 2, 55, 55, label('project_type_misc'), header)
    sheet.write_merge(1, 2, 56, 56, label('project_type_education_context'), header)
    sheet.write_merge(1, 2, 57, 57, label('project_type_register'), header)
    sheet.write_merge(1, 2, 58, 58, label('project_type_biobank'), header)
    sheet.write_merge(1, 2, 59, 59, label('project_type_retrospective'), header)
    sheet.write_merge(1, 2, 60, 60, label('project_type_questionnaire'), header)
    sheet.write_merge(1, 2, 61, 61, label('project_type_psychological_study'), header)
    sheet.write_merge(1, 2, 62, 62, label('project_type_nursing_study'), header)
    sheet.write_merge(1, 2, 63, 63, label('project_type_non_interventional_study'), header)
    sheet.write_merge(1, 2, 64, 64, label('project_type_gender_medicine'), header)
    sheet.write_merge(1, 2, 65, 65, label('project_type_non_interventional_study_mpg'), header)

    # format helpers
    _b = lambda x: _('Yes') if x else _('No')
    _d = lambda x: timezone.localtime(x).strftime('%d.%m.%Y') if x else None

    for i, submission in enumerate(submissions, 3):
        sf = submission.current_submission_form
        vote = submission.current_published_vote
        pi = sf.primary_investigator

        multicentric = (
                           sf.investigators.count() +
                           sf.foreignparticipatingcenter_set.count()
                       ) > 1

        sheet.write(i, 0, submission.get_ec_number_display())
        sheet.write(i, 1, sf.project_title)
        sheet.write(i, 2, sf.german_project_title)
        sheet.write(i, 3, sf.eudract_number)
        sheet.write(i, 4, _b(sf.is_amg))
        sheet.write(i, 5,
                    sf.get_submission_type_display() if sf.is_amg else None)
        sheet.write(i, 6, _b(sf.is_mpg))
        sheet.write(i, 7, _b(sf.medtech_eu_ct_id))
        sheet.write(i, 8,
                    _('multicentric') if multicentric else _('monocentric'))
        sheet.write(i, 9, submission.get_workflow_lane_display())
        sheet.write(i, 10, _b(submission.remission))
        sheet.write(i, 11, ', '.join(sorted(
            m.name for m in submission.medical_categories.all())))
        sheet.write(i, 12, submission.lifecycle_phase)
        sheet.write(i, 13, vote.result if vote else None)
        sheet.write(i, 14, _d(vote.valid_until) if vote else None)
        sheet.write(i, 15, _d(submission.first_sf_date))
        sheet.write(i, 16, submission.presenter.profile.organisation)
        sheet.write(i, 17, str(submission.presenter))
        sheet.write(i, 18, submission.presenter.email)
        sheet.write(i, 19, sf.submitter_organisation)
        sheet.write(i, 20, sf.submitter_contact.full_name)
        sheet.write(i, 21, sf.submitter_email)
        sheet.write(i, 22, sf.sponsor_name)
        sheet.write(i, 23, sf.sponsor_contact.full_name)
        sheet.write(i, 24, sf.sponsor_email)
        if sf.invoice_name:
            sheet.write(i, 25, sf.invoice_name)
            sheet.write(i, 26, sf.invoice_contact.full_name)
            sheet.write(i, 27, sf.invoice_email)
        else:
            sheet.write_merge(i, i, 25, 27, _('same as sponsor'), italic)
        sheet.write(i, 28, pi.organisation)
        sheet.write(i, 29, pi.contact.full_name)
        sheet.write(i, 30, pi.email)
        sheet.write(i, 31, sf.subject_count)
        sheet.write(i, 32, sf.subject_minage)
        sheet.write(i, 33, sf.get_subject_minage_unit_display())
        sheet.write(i, 34, sf.subject_maxage)
        sheet.write(i, 35, sf.get_subject_maxage_unit_display())
        sheet.write(i, 36, _b(sf.subject_noncompetent_guarded))
        sheet.write(i, 37, _b(sf.subject_noncompetent_minor))
        sheet.write(i, 38, _b(sf.subject_noncompetent_emergency_study))
        sheet.write(i, 39, _b(sf.subject_noncompetent_unconscious))
        sheet.write(i, 40, _b(sf.subject_males))
        sheet.write(i, 41, _b(sf.subject_females))
        sheet.write(i, 42, _b(sf.subject_childbearing))
        sheet.write(i, 43, _b(sf.subject_divers))
        sheet.write(i, 44, _b(sf.project_type_non_reg_drug))
        sheet.write(i, 45, _b(sf.project_type_reg_drug))
        sheet.write(i, 46, _b(sf.project_type_reg_drug_within_indication))
        sheet.write(i, 47, _b(sf.project_type_reg_drug_not_within_indication))
        sheet.write(i, 48, _b(sf.project_type_medical_method))
        sheet.write(i, 49, _b(sf.project_type_medical_device))
        sheet.write(i, 50, _b(sf.project_type_medical_device_with_ce))
        sheet.write(i, 51, _b(sf.project_type_medical_device_without_ce))
        sheet.write(i, 52,
                    _b(sf.project_type_medical_device_performance_evaluation))
        sheet.write(i, 53, _b(sf.project_type_basic_research))
        sheet.write(i, 54, _b(sf.project_type_genetic_study))
        sheet.write(i, 55, sf.project_type_misc)
        sheet.write(i, 56, sf.get_project_type_education_context_display())
        sheet.write(i, 57, _b(sf.project_type_register))
        sheet.write(i, 58, _b(sf.project_type_biobank))
        sheet.write(i, 59, _b(sf.project_type_retrospective))
        sheet.write(i, 60, _b(sf.project_type_questionnaire))
        sheet.write(i, 61, _b(sf.project_type_psychological_study))
        sheet.write(i, 62, _b(sf.project_type_nursing_study))
        sheet.write(i, 63, _b(sf.project_type_non_interventional_study))
        sheet.write(i, 64, _b(sf.project_type_gender_medicine))
        sheet.write(i, 65, _b(sf.project_type_non_interventional_study_mpg))

    xls_buf = BytesIO()
    xls.save(xls_buf)
    xls_data = xls_buf.getvalue()

    h = hashlib.sha1()
    h.update(xls_data)

    cache_file = os.path.join(settings.ECS_DOWNLOAD_CACHE_DIR, 'xls-export', '{}.xls'.format(h.hexdigest()))

    with open(cache_file, 'wb') as f:
        f.write(xls_data)

    send_system_message_template(user, _('XLS-Export done'),
                                 'submissions/xls_export_done.txt', {'shasum': h.hexdigest()})


@celery_app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(crontab(hour=3, minute=28), cull_cache_dir.s())


# run once per day at 03:28
@celery_app.task
def cull_cache_dir():
    logger.info("culling download cache")

    def clear_old_files_in_subfolder(sub_folder, max_age):
        sub_folder_path = os.path.join(settings.ECS_DOWNLOAD_CACHE_DIR, sub_folder)
        for path in os.listdir(sub_folder_path):
            if path.startswith('.'):
                continue
            full_path = os.path.join(sub_folder_path, path)
            age = time.time() - os.path.getmtime(full_path)
            if age > max_age:
                os.remove(full_path)

    clear_old_files_in_subfolder('xls-export', settings.ECS_DOWNLOAD_CACHE_MAX_AGE)
    clear_old_files_in_subfolder('submission-preview', 60 * 60 * 24)
    clear_old_files_in_subfolder('english-vote', 60 * 60 * 24)


@celery_app.task
def generate_submission_preview(docstash_key=None, user_id=None):
    docstash = DocStash.objects.get(key=docstash_key)
    user = User.objects.get(id=user_id)

    preview_pdf = docstash.render_preview_pdf()

    h = hashlib.sha1()
    h.update(preview_pdf)

    cache_file = os.path.join(settings.ECS_DOWNLOAD_CACHE_DIR, 'submission-preview', '{}-{}.pdf'.format(user_id, h.hexdigest()))
    with open(cache_file, 'wb') as f:
        f.write(preview_pdf)

    send_system_message_template(user, 'Einreichungsvorschau Fertig', 'submissions/submission_preview_done.txt', {'shasum': h.hexdigest()})
