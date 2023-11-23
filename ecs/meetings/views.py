import io
import re
import zipfile
from collections import OrderedDict
from datetime import timedelta

import reversion
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator, EmptyPage, InvalidPage
from django.db.models import Q, Max, Prefetch
from django.http import FileResponse, HttpResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext as _

from ecs.checklists.models import Checklist, ChecklistBlueprint
from ecs.communication.mailutils import deliver
from ecs.communication.utils import send_system_message_template
from ecs.core.models import Submission, SubmissionForm, MedicalCategory, AdvancedSettings, Clinic
from ecs.core.models.constants import SUBMISSION_TYPE_MULTICENTRIC
from ecs.documents.models import Document
from ecs.documents.views import handle_download
from ecs.meetings.cache import cache_meeting_page
from ecs.meetings.forms import (
    MeetingForm, TimetableEntryForm, FreeTimetableEntryForm,
    UserConstraintFormSet, SubmissionReschedulingForm,
    AssignedMedicalCategoryFormSet, MeetingAssistantForm, ExpeditedVoteFormSet,
    AmendmentVoteFormSet, ManualTimetableEntryCommentForm,
    ManualTimetableEntryCommentFormset, EkMemberMarkedForm, SendProtocolGroupsForm,
)
from ecs.meetings.models import Meeting, Participation, TimetableEntry, MeetingSubmissionProtocol, MeetingDocument
from ecs.meetings.signals import on_meeting_start, on_meeting_end, on_meeting_top_jump, \
    on_meeting_date_changed
from ecs.meetings.tasks import optimize_timetable_task
from ecs.meetings.utils import render_protocol_pdf_for_submission, send_submission_protocol_pdf, \
    get_users_for_protocol
from ecs.notifications.models import NotificationAnswer
from ecs.tasks.models import Task
from ecs.users.models import UserProfile
from ecs.users.utils import user_flag_required, user_group_required, sudo, get_current_user
from ecs.utils.viewutils import render_html, pdf_response
from ecs.votes.forms import VoteForm, SaveVoteForm
from ecs.votes.models import Vote


@user_group_required('EC-Office')
def create_meeting(request):
    form = MeetingForm(request.POST or None)
    if form.is_valid():
        meeting = form.save()
        return redirect('meetings.meeting_details', meeting_pk=meeting.pk)
    return render(request, 'meetings/form.html', {
        'form': form,
    })


def meeting_list(request, meetings, title=None):
    if not title:
        title = _('Meetings')
    paginator = Paginator(meetings, 12)
    try:
        meetings = paginator.page(int(request.GET.get('page', '1')))
    except (EmptyPage, InvalidPage):
        meetings = paginator.page(1)
    return render(request, 'meetings/list.html', {
        'meetings': meetings,
        'title': title,
    })


@user_flag_required('is_internal', 'is_resident_member', 'is_omniscient_member')
def upcoming_meetings(request):
    return meeting_list(request, Meeting.objects.upcoming().order_by('start'), title=_('Upcoming Meetings'))


@user_flag_required('is_internal')
def past_meetings(request):
    return meeting_list(request, Meeting.objects.past().order_by('-start'), title=_('Past Meetings'))


@user_flag_required('is_executive')
def reschedule_submission(request, submission_pk=None):
    submission = get_object_or_404(Submission, pk=submission_pk)
    form = SubmissionReschedulingForm(request.POST or None, submission=submission)
    if form.is_valid():
        from_meeting = form.cleaned_data['from_meeting']
        to_meeting = form.cleaned_data['to_meeting']

        old_entry = from_meeting.timetable_entries.get(submission=submission)
        assert not hasattr(old_entry, 'vote')
        visible = (not old_entry.timetable_index is None)
        new_entry = to_meeting.add_entry(submission=submission,
                                         duration=old_entry.duration, title=old_entry.title, visible=visible)
        old_entry.participations.exclude(task=None).update(entry=new_entry)
        old_entry.participations.all().delete()
        old_entry.delete()

        old_experts = set(from_meeting.medical_categories
                          .exclude(specialist=None)
                          .filter(category__in=submission.medical_categories.values('pk'))
                          .values_list('specialist_id', flat=True))
        new_experts = set(to_meeting.medical_categories
                          .exclude(specialist=None)
                          .filter(category__in=submission.medical_categories.values('pk'))
                          .values_list('specialist_id', flat=True))

        with sudo():
            Task.objects.for_data(submission).filter(
                task_type__workflow_node__uid='specialist_review',
                assigned_to__in=(old_experts - new_experts)
            ).open().mark_deleted()

        return redirect('view_submission', submission_pk=submission.pk)

    return render(request, 'meetings/reschedule.html', {
        'submission': submission,
        'form': form,
    })


@user_flag_required('is_internal')
@cache_meeting_page(timeout=60)
def open_tasks(request, meeting=None):
    tops = list(meeting.timetable_entries.filter(submission__isnull=False).select_related('submission',
                                                                                          'submission__current_submission_form'))
    tops.sort(key=lambda e: e.agenda_index)

    open_tasks = OrderedDict()
    for top in tops:
        ts = list(
            Task.unfiltered.for_submission(top.submission).open()
            .select_related('task_type', 'task_type__group', 'assigned_to',
                            'assigned_to__profile', 'medical_category')
            .order_by('created_at')
        )
        if len(ts):
            open_tasks[top] = ts

    return render_html(request, 'meetings/tabs/open_tasks.html', {
        'meeting': meeting,
        'open_tasks': open_tasks,
    })


@user_flag_required('is_internal', 'is_board_member', 'is_resident_member', 'is_omniscient_member')
def submission_list(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)

    extra_fields = ()
    if request.user.profile.is_omniscient_member:
        extra_fields = (
            'submission__current_submission_form__pdf_document_id',

            'submission__current_submission_form__pdf_document__doctype_id',
            'submission__current_submission_form__pdf_document__name',
            'submission__current_submission_form__pdf_document__version',
            'submission__current_submission_form__pdf_document__date',

            'submission__current_submission_form__pdf_document__doctype__name',
            'submission__current_submission_form__pdf_document__doctype__is_downloadable',
        )

    tops = meeting.timetable_entries.select_related(
        'submission', 'submission__current_submission_form'
    ).only(
        'timetable_index', 'is_open', 'duration', 'submission_id', 'meeting_id',

        'submission__ec_number',
        'submission__current_submission_form_id',
        'submission__invite_primary_investigator_to_meeting',

        'submission__current_submission_form__german_project_title',
        'submission__current_submission_form__project_title',
        'submission__current_submission_form__project_type_non_reg_drug',
        'submission__current_submission_form__project_type_reg_drug',
        'submission__current_submission_form__submission_type',
        'submission__current_submission_form__project_type_medical_device',
        'submission__current_submission_form__project_type_education_context',
        'submission__current_submission_form__subject_minage',
        'submission__current_submission_form__project_type_non_interventional_study',

        *extra_fields
    ).prefetch_related(
        Prefetch('participations', queryset=
        Participation.objects.select_related(
            'user',
        ).only(
            'entry_id', 'user_id',

            'user__first_name',
            'user__last_name',
            'user__email',
        ).prefetch_related(
            Prefetch('user__profile', queryset=
            UserProfile.objects.only('gender', 'title', 'user_id')
                     ),
        ).order_by('user__email')
                 )
    ).order_by('timetable_index', 'pk')

    if request.user.profile.is_omniscient_member:
        tops = tops.select_related(
            'submission__current_submission_form__pdf_document',
            'submission__current_submission_form__pdf_document__doctype'
        ).prefetch_related(
            Prefetch('submission__current_submission_form__documents',
                     queryset=Document.objects.select_related('doctype').only(
                         'doctype_id', 'name', 'version', 'date',
                         'doctype__name', 'doctype__is_downloadable',
                     ).order_by('doctype__identifier', 'date', 'name'))
        )

    accessible_submissions = set(
        Submission.objects.filter(
            id__in=[top.submission.pk for top in tops if top.submission]
        ).values_list('id', flat=True)
    )

    start = meeting.start
    for entry in tops:
        if entry.timetable_index is not None:
            entry._start_cache = start
            entry._end_cache = start + entry.duration
            start += entry.duration

        submission = entry.submission
        if submission:
            submission.current_submission_form._submission_cache = submission
            submission.is_accessible = submission.id in accessible_submissions

    active_top = meeting.active_top

    return render(request, 'meetings/tabs/submissions.html', {
        'meeting': meeting,
        'tops': tops,
        'active_top_pk': active_top.pk if active_top else None,
    })


@user_flag_required('is_omniscient_member')
def download_document(request, meeting_pk=None, document_pk=None, view=False):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    with sudo():
        doc = get_object_or_404(
            Document,
            content_type=ContentType.objects.get_for_model(SubmissionForm),
            object_id__in=SubmissionForm.objects.filter(
                submission__in=meeting.timetable_entries.values('submission_id')),
            pk=document_pk
        )
    return handle_download(request, doc, view=view)


def view_document(request, meeting_pk=None, document_pk=None):
    return download_document(request, meeting_pk, document_pk, view=True)


@user_flag_required('is_internal', 'is_board_member', 'is_resident_member', 'is_omniscient_member')
def notification_list(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)

    b1ized = Vote.unfiltered.filter(
        result='1', upgrade_for__result='2', published_at__isnull=False
    ).select_related(
        'submission_form', 'submission_form__submission',
        'submission_form__submitter', 'submission_form__submitter__profile',
    ).order_by('submission_form__submission__ec_number')

    answers = NotificationAnswer.unfiltered.exclude(
        notification__amendmentnotification__is_substantial=True
    ).exclude(published_at=None).select_related(
        'notification', 'notification__type',
        'notification__safetynotification',
        'notification__centerclosenotification'
    ).prefetch_related(
        Prefetch('notification__submission_forms',
                 queryset=SubmissionForm.unfiltered.select_related('submission'))
    ).order_by(
        'notification__type__position',
        'notification__safetynotification__safety_type', 'published_at'
    )

    with sudo():
        start = Meeting.objects.filter(start__lt=meeting.start).aggregate(
            Max('protocol_sent_at'))['protocol_sent_at__max']
    if start:
        b1ized = b1ized.filter(published_at__gt=start)
        answers = answers.filter(published_at__gt=start)

    end = meeting.protocol_sent_at
    if end:
        b1ized = b1ized.filter(published_at__lte=end)
        answers = answers.filter(published_at__lte=end)

    substantial_amendments = meeting.amendments.prefetch_related(
        Prefetch('submission_forms',
                 queryset=SubmissionForm.unfiltered.select_related('submission'))
    ).order_by('submission_forms__submission__ec_number')

    return render(request, 'meetings/tabs/notifications.html', {
        'meeting': meeting,
        'substantial_amendments': substantial_amendments,
        'b1ized': b1ized,
        'answers': answers,
    })


@user_flag_required('is_internal', 'is_board_member', 'is_resident_member', 'is_omniscient_member')
def download_zipped_documents(request, meeting_pk=None, submission_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)

    if not submission_pk:
        if not meeting.documents_zip:
            raise Http404()

        doc = meeting.documents_zip
        response = FileResponse(doc.retrieve_raw(), content_type=doc.mimetype)
        response['Content-Disposition'] = \
            'attachment; filename="{}.zip"'.format(slugify(meeting.title))
        return response

    submission = get_object_or_404(meeting.submissions(manager='unfiltered'),
                                   pk=submission_pk)
    sf = submission.current_submission_form

    docs = []
    if sf.pdf_document:
        docs.append(sf.pdf_document)
    docs += sf.documents.filter(doctype__identifier='patientinformation')
    docs += Document.objects.filter(
        content_type=ContentType.objects.get_for_model(Checklist),
        object_id__in=submission.checklists.filter(status='review_ok'),
    )

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        path = [submission.get_filename_slice()]
        for doc in docs:
            zf.writestr('/'.join(path + [doc.get_filename()]),
                        doc.retrieve(request.user, 'meeting-zip').read())

    response = HttpResponse(zip_buf.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename="{}_{}.zip"'.format(
        slugify(meeting.title), submission.get_filename_slice())
    return response


@user_group_required('EC-Office')
def add_free_timetable_entry(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk, started=None)
    form = FreeTimetableEntryForm(request.POST or None)
    if form.is_valid():
        meeting.add_entry(**form.cleaned_data)
        return redirect('meetings.timetable_editor', meeting_pk=meeting.pk)
    return render(request, 'meetings/timetable/add_free_entry.html', {
        'form': form,
        'meeting': meeting,
    })


@user_group_required('EC-Office')
def add_timetable_entry(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk, started=None)
    is_break = request.GET.get('break', False)
    if is_break:
        entry = meeting.add_break(duration=timedelta(minutes=30))
    else:
        entry = meeting.add_entry(duration=timedelta(minutes=7, seconds=30),
                                  submission=Submission.objects.order_by('?')[:1].get())
        import random
        for user in User.objects.order_by('?')[:random.randint(1, 4)]:
            entry.participations.create(user=user)
    return redirect('meetings.timetable_editor', meeting_pk=meeting.pk)


@user_group_required('EC-Office')
def remove_timetable_entry(request, meeting_pk=None, entry_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk, started=None)
    entry = get_object_or_404(meeting.timetable_entries, pk=entry_pk)
    if entry.submission:
        raise Http404(_("only tops without associated submission can be deleted"))
    entry.delete()
    return redirect('meetings.timetable_editor', meeting_pk=meeting.pk)


@user_group_required('EC-Office')
def update_timetable_entry(request, meeting_pk=None, entry_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk, started=None)
    entry = get_object_or_404(meeting.timetable_entries, pk=entry_pk)
    form = TimetableEntryForm(request.POST)
    if form.is_valid():
        entry.duration = form.cleaned_data['duration']
        entry.optimal_start = form.cleaned_data['optimal_start']
        entry.save()
        if entry.optimal_start:
            entry.move_to_optimal_position()
    return redirect('meetings.timetable_editor', meeting_pk=meeting.pk)


@user_group_required('EC-Office')
def toggle_participation(request, meeting_pk=None, user_pk=None, entry_pk=None):
    participations = Participation.objects.filter(entry=entry_pk, user=user_pk)
    ignored = not participations.first().ignored_for_optimization
    participations.update(ignored_for_optimization=ignored)
    return redirect('meetings.timetable_editor',
                    meeting_pk=meeting_pk)


@user_group_required('EC-Office')
def move_timetable_entry(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk, started=None)
    from_index = int(request.GET.get('from_index'))
    to_index = int(request.GET.get('to_index'))
    meeting[from_index].index = to_index
    return redirect('meetings.timetable_editor', meeting_pk=meeting.pk)


@user_group_required('EC-Office')
def timetable_editor(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    from ecs.meetings.tasks import _eval_timetable

    with sudo():
        recommendations_not_done = Task.objects.for_submissions(
            meeting.timetable_entries.filter(submission__isnull=False).values('pk')
        ).filter(task_type__workflow_node__uid__in=[
            'thesis_recommendation', 'thesis_recommendation_review',
            'expedited_recommendation', 'localec_recommendation'
        ]).open().exists()

    return render(request, 'meetings/timetable/editor.html', {
        'meeting': meeting,
        'running_optimization': bool(meeting.optimization_task_id),
        'readonly': bool(meeting.optimization_task_id) or not meeting.started is None,
        'score': _eval_timetable(meeting.metrics),
        'recommendations_not_done': recommendations_not_done,
    })


@user_group_required('EC-Office')
def optimize_timetable(request, meeting_pk=None, algorithm=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk, started=None)
    if not meeting.optimization_task_id:
        meeting.optimization_task_id = "xxx:fake"
        meeting.save()
        optimize_timetable_task.apply_async(kwargs={'meeting_id': meeting.id, 'algorithm': algorithm})
    return redirect('meetings.timetable_editor', meeting_pk=meeting.pk)


@user_group_required('EC-Office')
def optimize_timetable_long(request, meeting_pk=None, algorithm=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk, started=None)
    if not meeting.optimization_task_id:
        meeting.optimization_task_id = "xxx:fake"
        meeting.save()
        optimize_timetable_task.apply_async(
            kwargs={'meeting_id': meeting.id, 'algorithm': algorithm, 'algorithm_parameters': {
                'population_size': 400,
                'iterations': 2000,
            }})
    return redirect('meetings.timetable_editor', meeting_pk=meeting.pk)


@user_group_required('EC-Office')
def edit_user_constraints(request, meeting_pk=None, user_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk, started=None)
    user = get_object_or_404(User, pk=user_pk)
    formset = UserConstraintFormSet(request.POST or None, prefix='constraint',
                                    queryset=user.meeting_constraints.filter(meeting=meeting))
    if formset.is_valid():
        for constraint in formset.save(commit=False):
            constraint.meeting = meeting
            constraint.user = user
            constraint.save()
        for constraint in formset.deleted_objects:
            constraint.delete()
        formset = UserConstraintFormSet(None, prefix='constraint',
                                        queryset=user.meeting_constraints.filter(meeting=meeting))
        messages.success(request,
                         _('The constraints have been saved. The constraints will be taken into account when optimizing the timetable.'))
    return render(request, 'meetings/constraints/user_form.html', {
        'meeting': meeting,
        'participant': user,
        'formset': formset,
    })


@user_group_required('EC-Office')
def meeting_assistant_quickjump(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk, started__isnull=False)
    top = None
    q = request.POST.get('q', '').strip().upper()

    m = re.match('(\d{4})(?:/(\d{4}))?$', q)
    if m:
        if m.group(2):
            ec_number = '{}{}'.format(m.group(2), m.group(1))
        else:
            year = timezone.now().year
            ec_number = '{}{}'.format(year, m.group(1))
        try:
            top = meeting.timetable_entries.get(submission__ec_number=ec_number)
        except (TimetableEntry.DoesNotExist,
                TimetableEntry.MultipleObjectsReturned):
            pass

    if not top:
        m = re.match(r'(?:TOP)?\s*(\d+)$', q)
        if m:
            idx = int(m.group(1)) - 1
            try:
                top = meeting.timetable_entries.get(timetable_index=idx)
            except TimetableEntry.DoesNotExist:
                pass

    if top:
        if top.timetable_index is None:
            return redirect('meetings.meeting_assistant_other_tops',
                            meeting_pk=meeting.pk)
        return redirect('meetings.meeting_assistant_top',
                        meeting_pk=meeting.pk, top_pk=top.pk)

    return render(request, 'meetings/assistant/quickjump_error.html', {
        'meeting': meeting,
        'last_top': meeting.active_top,
        'query': q,
    })


@user_group_required('EC-Office')
def meeting_assistant(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    if meeting.started:
        if meeting.ended:
            return render(request, 'meetings/assistant/error.html', {
                'active': 'assistant',
                'meeting': meeting,
                'message': _('This meeting has ended.'),
            })
        try:
            top = meeting.active_top or meeting[0]
            return redirect('meetings.meeting_assistant_top',
                            meeting_pk=meeting.pk, top_pk=top.pk)
        except IndexError:
            return render(request, 'meetings/assistant/error.html', {
                'active': 'assistant',
                'meeting': meeting,
                'message': _('No TOPs are assigned to this meeting.'),
            })
    else:
        return render(request, 'meetings/assistant/error.html', {
            'active': 'assistant',
            'meeting': meeting,
            'message': _('This meeting has not yet started.'),
        })


@user_group_required('EC-Office')
def meeting_assistant_start(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk, started=None)
    nocheck = request.GET.get('nocheck', False) if settings.DEBUG else False

    for top in meeting.timetable_entries.filter(submission__isnull=False):
        with sudo():
            recommendation_exists = Task.objects.for_submission(top.submission).filter(
                task_type__workflow_node__uid__in=['thesis_recommendation', 'thesis_recommendation_review',
                                                   'expedited_recommendation',
                                                   'localec_recommendation']).open().exists()
        if recommendation_exists and not nocheck:
            return render(request, 'meetings/assistant/error.html', {
                'active': 'assistant',
                'meeting': meeting,
                'message': _(
                    'There are open recommendations. You can start the meeting assistant when all recommendations are done.'),
            })
        with sudo():
            vote_preparation_exists = Task.objects.filter(
                task_type__workflow_node__uid='vote_preparation'
            ).for_submission(top.submission).open().exists()
        if vote_preparation_exists and not nocheck:
            return render(request, 'meetings/assistant/error.html', {
                'active': 'assistant',
                'meeting': meeting,
                'message': _(
                    'There are open vote preparations. You can start the meeting assistant when all vote preparations are done.'),
            })

    meeting.started = timezone.now()
    meeting.save()
    on_meeting_start.send(Meeting, meeting=meeting)
    return redirect('meetings.meeting_assistant', meeting_pk=meeting.pk)


@user_group_required('EC-Office')
def meeting_assistant_stop(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk, started__isnull=False)
    if meeting.open_tops.exists():
        raise Http404(_("unfinished meetings cannot be stopped"))
    meeting.ended = timezone.now()
    meeting.save()
    on_meeting_end.send(Meeting, meeting=meeting)
    return redirect('meetings.meeting_assistant', meeting_pk=meeting.pk)


@user_group_required('EC-Office')
def meeting_assistant_comments(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk, started__isnull=False)
    form = MeetingAssistantForm(request.POST or None, instance=meeting)
    if form.is_valid():
        form.save()
        if request.POST.get('autosave', False):
            return HttpResponse('OK')
        return redirect('meetings.meeting_assistant', meeting_pk=meeting.pk)
    return render(request, 'meetings/assistant/comments.html', {
        'meeting': meeting,
        'last_top': meeting.active_top,
        'form': form,
    })


@user_group_required('EC-Office')
def meeting_assistant_other_tops(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk, started__isnull=False)

    def _prefetch_entries(entries):
        return entries.select_related(
            'submission', 'submission__current_submission_form',
            'submission__current_pending_vote',
        ).only(
            'meeting_id',
            'submission__ec_number',
            'submission__current_submission_form__project_title',
            'submission__current_submission_form__german_project_title',
            'submission__current_pending_vote__result',
            'submission__current_pending_vote__text',
        ).order_by('submission__ec_number')

    def _prefetch_amendments(amendments):
        return amendments.select_related(
            'new_submission_form', 'new_submission_form__submission',
        ).only(
            'meeting_id',
            'new_submission_form__submission__ec_number',
            'new_submission_form__project_title',
            'new_submission_form__german_project_title',
        ).prefetch_related(
            Prefetch('answer', queryset=
            NotificationAnswer.objects
                     .only('notification_id', 'is_rejected', 'text')
                     ),
        ).order_by('submission_forms__submission__ec_number')

    thesis_vote_formset = ExpeditedVoteFormSet(request.POST or None,
                                               queryset=_prefetch_entries(meeting.retrospective_thesis_entries),
                                               prefix='thesis')
    expedited_vote_formset = ExpeditedVoteFormSet(request.POST or None,
                                                  queryset=_prefetch_entries(meeting.expedited_entries),
                                                  prefix='expedited')
    localec_vote_formset = ExpeditedVoteFormSet(request.POST or None,
                                                queryset=_prefetch_entries(meeting.localec_entries), prefix='localec')
    amendment_vote_formset = AmendmentVoteFormSet(request.POST or None,
                                                  queryset=_prefetch_amendments(meeting.amendments.filter(
                                                      answer__is_valid=False
                                                  )), prefix='amendment')

    if request.method == 'POST':
        with reversion.create_revision():
            reversion.set_user(get_current_user())
            thesis_vote_formset.save()
            expedited_vote_formset.save()
            localec_vote_formset.save()
            amendment_vote_formset.save()

        return redirect('meetings.meeting_assistant_other_tops',
                        meeting_pk=meeting_pk)

    return render(request, 'meetings/assistant/other_tops.html', {
        'retrospective_thesis_entries':
            _prefetch_entries(meeting.retrospective_thesis_entries.filter(
                vote__isnull=False, vote__is_draft=False
            )),
        'expedited_entries':
            _prefetch_entries(meeting.expedited_entries.filter(
                vote__isnull=False, vote__is_draft=False
            )),
        'localec_entries':
            _prefetch_entries(meeting.localec_entries.filter(
                vote__isnull=False, vote__is_draft=False
            )),
        'amendment_entries':
            _prefetch_amendments(meeting.amendments.filter(
                answer__is_valid=True
            )),
        'meeting': meeting,
        'last_top': meeting.active_top,
        'thesis_vote_formset': thesis_vote_formset,
        'expedited_vote_formset': expedited_vote_formset,
        'localec_vote_formset': localec_vote_formset,
        'amendment_vote_formset': amendment_vote_formset,
    })


@user_group_required('EC-Office')
def edit_notification_answer(request, meeting_pk=None, notification_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk, started__isnull=False)
    notification = get_object_or_404(NotificationAnswer, pk=notification_pk)
    if request.POST:
        notification.text = request.POST.get('new-answer')
        notification.save()
        return HttpResponse(status=204)

    return HttpResponse(status=400)

@user_group_required('EC-Office')
def meeting_assistant_top(request, meeting_pk=None, top_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk, started__isnull=False)
    top = get_object_or_404(meeting.timetable_entries, pk=top_pk)
    simple_save = request.POST.get('simple_save', False)
    autosave = request.POST.get('autosave', False)
    try:
        vote = top.vote
    except Vote.DoesNotExist:
        vote = None
    form = None

    def next_top_redirect():
        if top.next_open:
            next_top = top.next_open
        else:
            try:
                next_top = meeting.open_tops[0]
            except IndexError:
                on_meeting_top_jump.send(Meeting, meeting=meeting, timetable_entry=top)
                return redirect('meetings.meeting_assistant', meeting_pk=meeting.pk)
        return redirect('meetings.meeting_assistant_top', meeting_pk=meeting.pk, top_pk=next_top.pk)

    if top.submission and top.is_open:
        form_cls = SaveVoteForm if simple_save else VoteForm
        form = form_cls(request.POST or None, instance=vote)
        if form.is_valid():
            vote = form.save(top)
            if autosave:
                return HttpResponse('OK')
            if form.cleaned_data['close_top']:
                with reversion.create_revision():
                    reversion.set_user(get_current_user())
                    vote = form.save(top)
                top.is_open = False
                top.save()
                return next_top_redirect()
            return redirect('meetings.meeting_assistant_top',
                            meeting_pk=meeting.pk, top_pk=top.pk)
    elif top.submission and not top.is_open:
        form = VoteForm(None, instance=vote, readonly=True)
    elif not top.submission and not top.is_break:
        form = ManualTimetableEntryCommentForm(request.POST or None, instance=top)
        if form.is_valid():
            form.save()
            top.is_open = False
            top.save()
            return next_top_redirect()
    elif request.method == 'POST':
        top.is_open = False
        top.save()
        return next_top_redirect()

    last_top = meeting.active_top
    meeting.active_top = top
    if last_top != top:
        on_meeting_top_jump.send(Meeting, meeting=meeting, timetable_entry=top)

    checklist_review_states = OrderedDict()
    blueprint_ct = ContentType.objects.get_for_model(ChecklistBlueprint)
    checklist_ct = ContentType.objects.get_for_model(Checklist)
    if top.submission:
        for blueprint in ChecklistBlueprint.objects.order_by('name'):
            with sudo():
                tasks = Task.objects.for_submission(top.submission).filter(deleted_at=None)
                tasks = tasks.filter(task_type__workflow_node__data_ct=blueprint_ct,
                                     task_type__workflow_node__data_id=blueprint.id
                                     ) | tasks.filter(content_type=checklist_ct, data_id__in=Checklist.objects.filter(
                    blueprint=blueprint)).exclude(workflow_token__node__uid='external_review_review')
                tasks = list(tasks.order_by('-created_at'))
            checklists = []
            for task in tasks:
                lookup_kwargs = {'blueprint': blueprint}
                if blueprint.multiple:
                    lookup_kwargs['last_edited_by'] = task.assigned_to
                try:
                    checklist = top.submission.checklists.exclude(status='dropped').filter(**lookup_kwargs)[0]
                except IndexError:
                    checklist = None
                if not checklist in [x[1] for x in checklists]:
                    checklists.append((task, checklist))
            checklists.reverse()
            checklist_review_states[blueprint] = checklists

    return render(request, 'meetings/assistant/top.html', {
        'meeting': meeting,
        'submission': top.submission,
        'top': top,
        'vote': vote,
        'form': form,
        'last_top': last_top,
        'checklist_review_states': list(checklist_review_states.items()),
    })


@user_flag_required('is_internal', 'is_board_member', 'is_resident_member', 'is_omniscient_member')
def agenda_pdf(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    filename = '{}-{}-{}.pdf'.format(slugify(meeting.title),
                                     timezone.localtime(meeting.start).strftime('%d-%m-%Y'),
                                     slugify(_('agenda')))
    pdf = meeting.get_agenda_pdf(request)
    return pdf_response(pdf, filename=filename)


@user_group_required('EC-Office')
def send_agenda_to_board(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)

    agenda_pdf = meeting.get_agenda_pdf(request)
    agenda_filename = '{}-{}-{}.pdf'.format(slugify(meeting.title),
                                            timezone.localtime(meeting.start).strftime('%d-%m-%Y'),
                                            slugify(_('agenda')))
    timetable_pdf = meeting.get_timetable_pdf(request)
    timetable_filename = '{}-{}-{}.pdf'.format(slugify(meeting.title),
                                               timezone.localtime(meeting.start).strftime('%d-%m-%Y'),
                                               slugify(_('time slot')))
    attachments = (
        (agenda_filename, agenda_pdf, 'application/pdf'),
        (timetable_filename, timetable_pdf, 'application/pdf'),
    )
    subject = _('EC Meeting {}').format(
        timezone.localtime(meeting.start).strftime('%d.%m.%Y'))
    reply_to = AdvancedSettings.objects.get().contact_email

    users = User.objects.filter(meeting_participations__entry__meeting=meeting).distinct()
    for user in users:
        timeframe = meeting._get_timeframe_for_user(user)
        if timeframe is None:
            continue
        start, end = timeframe
        htmlmail = str(render_html(request, \
                                   'meetings/messages/boardmember_invitation.html', \
                                   {'meeting': meeting, 'start': start, 'end': end, 'recipient': user}))
        deliver(user.email, subject=subject, message=None,
                message_html=htmlmail, from_email=settings.DEFAULT_FROM_EMAIL,
                rfc2822_headers={"Reply-To": reply_to},
                attachments=attachments)

    for user in User.objects.filter(groups__name__in=settings.ECS_MEETING_AGENDA_RECEIVER_GROUPS):
        start, end = meeting.start, meeting.end
        htmlmail = str(render_html(request, \
                                   'meetings/messages/resident_boardmember_invitation.html', \
                                   {'meeting': meeting, 'recipient': user}))
        deliver(user.email, subject=subject, message=None,
                message_html=htmlmail, from_email=settings.DEFAULT_FROM_EMAIL,
                rfc2822_headers={"Reply-To": reply_to},
                attachments=attachments)

    tops_with_primary_investigator = meeting.timetable_entries.filter(
        submission__invite_primary_investigator_to_meeting=True,
        submission__current_submission_form__primary_investigator__user__isnull=False, timetable_index__isnull=False)
    for top in tops_with_primary_investigator:
        sf = top.submission.current_submission_form
        for u in {sf.primary_investigator.user, sf.presenter, sf.submitter, sf.sponsor}:
            send_system_message_template(u, subject, 'meetings/messages/primary_investigator_invitation.txt',
                                         {'top': top}, submission=top.submission)

    meeting.agenda_sent_at = timezone.now()
    meeting.save()

    return redirect('meetings.meeting_details', meeting_pk=meeting.pk)


@user_group_required('EC-Office')
def send_expedited_reviewer_invitations(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)

    categories = MedicalCategory.objects.filter(
        submissions__in=meeting.submissions.expedited())
    users = User.objects.filter(profile__is_board_member=True,
                                medical_categories__in=categories.values('pk'))
    start = meeting.deadline_expedited_review
    for user in users:
        subject = _('Expedited Review at {}').format(
            timezone.localtime(start).strftime('%d.%m.%Y'))
        send_system_message_template(user, subject,
                                     'meetings/messages/expedited_reviewer_invitation.txt',
                                     {'start': start})

    meeting.expedited_reviewer_invitation_sent_at = timezone.now()
    meeting.save(update_fields=('expedited_reviewer_invitation_sent_at',))

    return redirect('meetings.meeting_details', meeting_pk=meeting.pk)


@user_group_required('EC-Office')
def edit_protocol(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk, ended__isnull=False,
                                protocol_sent_at=None)

    formset = ManualTimetableEntryCommentFormset(
        request.POST or None,
        prefix='protocol',
        queryset=meeting.timetable_entries.filter(submission=None, is_break=False)
    )

    if request.method == 'POST' and formset.is_valid():
        formset.save()

    return render(request, 'meetings/tabs/protocol.html', {
        'meeting': meeting,
        'formset': formset,
    })


@user_group_required('EC-Office')
def send_protocol(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, ended__isnull=False,
                                protocol_sent_at=None, pk=meeting_pk)

    meeting.protocol_sent_at = timezone.now()
    meeting.save()

    protocol_pdf = meeting.protocol.retrieve_raw().read()
    attachments = (
        (meeting.protocol.original_file_name, protocol_pdf, 'application/pdf'),
    )

    for user in User.objects.filter(Q(meeting_participations__entry__meeting=meeting) | Q(
        groups__name__in=settings.ECS_MEETING_PROTOCOL_RECEIVER_GROUPS)).distinct():
        htmlmail = str(render_html(request, 'meetings/messages/protocol.html', {'meeting': meeting, 'recipient': user}))
        deliver(user.email, subject=_('Meeting Protocol'), message=None,
                message_html=htmlmail, from_email=settings.DEFAULT_FROM_EMAIL,
                attachments=attachments)

    return redirect('meetings.meeting_details', meeting_pk=meeting.pk)


@user_flag_required('is_internal')
def render_protocol_pdf(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting.unfiltered.select_for_update(),
                                protocol_rendering_started_at=None, pk=meeting_pk)

    meeting.protocol_rendering_started_at = timezone.now()
    meeting.save(update_fields=('protocol_rendering_started_at',))
    if meeting.protocol:
        meeting.protocol.delete()

    from ecs.meetings.tasks import render_protocol_pdf
    render_protocol_pdf.apply_async(kwargs={
        'meeting_id': meeting.pk,
        'user_id': request.user.id,
    })
    return redirect('meetings.meeting_details', meeting_pk=meeting.pk)


@user_flag_required('is_internal', 'is_board_member', 'is_resident_member', 'is_omniscient_member')
def protocol_pdf(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, protocol__isnull=False, pk=meeting_pk)

    response = FileResponse(meeting.protocol.retrieve_raw(),
                            content_type=meeting.protocol.mimetype)
    response['Content-Disposition'] = \
        'attachment;filename={}'.format(meeting.protocol.original_file_name)
    return response


@user_flag_required('is_internal', 'is_board_member', 'is_resident_member', 'is_omniscient_member')
def timetable_pdf(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    filename = '{}-{}-{}.pdf'.format(slugify(meeting.title),
                                     timezone.localtime(meeting.start).strftime('%d-%m-%Y'),
                                     slugify(_('time slot')))
    with sudo():
        pdf = meeting.get_timetable_pdf(request)
    return pdf_response(pdf, filename=filename)


@user_flag_required('is_internal')
def timetable_htmlemailpart(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    response = render(request, 'meetings/email/timetable.html', {
        'meeting': meeting,
    })
    return response


@user_flag_required('is_internal', 'is_board_member', 'is_resident_member', 'is_omniscient_member')
def next_meeting(request):
    try:
        meeting = Meeting.objects.next()
    except Meeting.DoesNotExist:
        return redirect('dashboard')
    else:
        return redirect('meetings.meeting_details', meeting_pk=meeting.pk)


@user_flag_required('is_internal', 'is_board_member', 'is_resident_member', 'is_omniscient_member')
def meeting_details(request, meeting_pk=None, active=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)

    expert_formset = AssignedMedicalCategoryFormSet(request.POST or None,
                                                    prefix='experts', queryset=meeting.medical_categories.all())

    if request.method == 'POST' and expert_formset.is_valid() and \
        request.user.profile.is_internal and meeting.started is None:

        previous_experts = dict(
            meeting.medical_categories.values_list('pk', 'specialist_id'))

        for amc in expert_formset.save():
            previous_expert = previous_experts[amc.pk]
            if not previous_expert:
                continue

            # remove all participations for a previous selected board member.
            Participation.objects.filter(medical_category=amc.category,
                                         entry__meeting=meeting, user=previous_expert).delete()

            entries = meeting.timetable_entries.filter(
                submission__medical_categories=amc.category
            ).exclude(
                submission__medical_categories__in=
                meeting.medical_categories
                .filter(specialist=previous_expert)
                .values('category_id')
            )

            for entry in entries:
                with sudo():
                    Task.objects.for_data(entry.submission).filter(
                        task_type__workflow_node__uid='specialist_review',
                        assigned_to=previous_expert
                    ).open().mark_deleted()

        meeting.expert_assignment_user = request.user
        meeting.save()

        meeting.create_specialist_reviews()

        messages.success(request,
                         _('The expert assignment has been saved. The experts will be invited to the meeting when you send the agenda to the board.'))
        active = 'experts'

    with sudo():
        submissions = meeting.submissions.order_by('ec_number')

    return render(request, 'meetings/details.html', {
        'cumulative_count': submissions.distinct().count(),

        'board_submissions': submissions.for_board_lane(),
        'amg_submissions': submissions.for_board_lane().amg().exclude(
            pk__in=meeting.submissions.mpg().values('pk').query),
        'mpg_submissions': submissions.for_board_lane().mpg().exclude(
            pk__in=meeting.submissions.amg().values('pk').query),
        'amg_mpg_submissions': submissions.for_board_lane().amg_mpg(),
        'not_amg_and_not_mpg_submissions': submissions.for_board_lane().not_amg_and_not_mpg(),

        'retrospective_thesis_submissions': submissions.for_thesis_lane(),
        'expedited_submissions': submissions.expedited(),
        'localec_submissions': submissions.localec(),

        'dissertation_submissions': submissions.filter(current_submission_form__project_type_education_context=1),
        'diploma_thesis_submissions': submissions.filter(current_submission_form__project_type_education_context=2),
        'amg_multi_main_submissions': submissions.amg().filter(
            current_submission_form__submission_type=SUBMISSION_TYPE_MULTICENTRIC),
        'billable_submissions': submissions.exclude(remission=True),
        'b3_examined_submissions': submissions.filter(
            pk__in=Vote.objects.filter(result='3b').values('submission_form__submission').query),
        'b3_not_examined_submissions': submissions.filter(
            pk__in=Vote.objects.filter(result='3a').values('submission_form__submission').query),
        'substantial_amendments':
            meeting.amendments.prefetch_related(
                Prefetch('submission_forms',
                         queryset=SubmissionForm.unfiltered.select_related('submission'))
            ).order_by('submission_forms__submission__ec_number'),

        'meeting': meeting,
        'expert_formset': expert_formset,
        'active': active,
    })


@user_group_required('EC-Office')
def edit_meeting(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)
    form = MeetingForm(request.POST or None, instance=meeting)
    if form.is_valid():
        meeting = form.save()
        on_meeting_date_changed.send(Meeting, meeting=meeting)
        return redirect('meetings.meeting_details', meeting_pk=meeting.pk)
    return render(request, 'meetings/form.html', {
        'form': form,
        'meeting': meeting,
    })


@user_group_required('EC-Office')
def send_protocol_custom_groups(request, meeting_pk=None):
    meeting = get_object_or_404(
        Meeting.objects.filter(ended__isnull=False).prefetch_related('invited_users', 'invited_groups'),
        pk=meeting_pk
    )
    invited_groups_id = meeting.invited_groups.all().values_list('id', flat=True)
    users_to_send_protocol = meeting.invited_users.all()
    is_disabled = True if meeting.protocol_sent_at is not None else False
    form = SendProtocolGroupsForm(is_disabled, request.POST or None,
                                  initial={'groups': list(map(str, invited_groups_id))})

    # Invite all the users with the provided groups
    invited_count = None
    protocol_sent = meeting.protocol_sent_at is not None
    if request.method == 'POST' and form.is_valid() and not protocol_sent:
        invited_group_ids = form.cleaned_data['groups']
        invite_ek_member = form.cleaned_data['invite_ek_member']
        board_member_group = (
            next(filter(lambda group: (group[1].name == 'Board Member'), form.fields['groups'].choices), None)[1])
        users_to_send_protocol = get_users_for_protocol(meeting, invited_group_ids, invite_ek_member,
                                                        board_member_group=board_member_group)

        meeting.protocol_sent_at = timezone.now()
        attachments = (
            (meeting.protocol.original_file_name, (meeting.protocol.retrieve_raw().read()), 'application/pdf'),
        )

        for user in users_to_send_protocol:
            htmlmail = str(
                render_html(request, 'meetings/messages/protocol.html', {'meeting': meeting, 'recipient': user}))
            deliver(
                user.email, subject=_('Meeting Protocol'), message=None,
                message_html=htmlmail, from_email=settings.DEFAULT_FROM_EMAIL,
                attachments=attachments
            )

        meeting.invited_users.set(users_to_send_protocol)
        meeting.invited_groups.set(invited_group_ids)
        meeting.save()
        invited_count = len(users_to_send_protocol)
        protocol_sent = True
        form.set_disabled(True)

    return render(request, 'meetings/tabs/custom_protocol.html', {
        'form': form,
        'meeting': meeting,
        'invited_count': invited_count,
        'users_to_invite': users_to_send_protocol,
        'protocol_sent': protocol_sent,
    })


@user_group_required('EC-Office')
def preview_users(request, meeting_pk=None):
    meeting = get_object_or_404(
        Meeting.objects.filter(ended__isnull=False, protocol_sent_at__isnull=True),
        pk=meeting_pk
    )
    form = SendProtocolGroupsForm(False, request.POST or None)
    users_to_send_protocol = []
    if form.is_valid():
        invite_ek_member = form.cleaned_data['invite_ek_member']
        invited_group_ids = form.cleaned_data['groups']
        users_to_send_protocol = get_users_for_protocol(meeting, invited_group_ids, invite_ek_member)

    return render(request, 'meetings/users_to_invite.html', {
        'users': users_to_send_protocol,
    })


@user_group_required('EC-Office')
def list_submissions_protocols(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting, pk=meeting_pk)

    pdfs_sent_to_render = None
    pdfs_sent_per_email = None
    # We need this for the hot replacment.
    if request.method == 'POST':
        # Render all pdfs if requested
        if 'create_all_pdfs' in request.POST:
            # Render submission that aren't currently in the render pipeline
            submissions_to_render = meeting.submissions \
                .filter(~Q(clinics=None),
                        meeting_protocols__protocol_rendering_started_at__isnull=True,
                        meeting_protocols__protocol_sent_at__isnull=True,
                        ) \
                .prefetch_related('meeting_protocols')
            for submission in submissions_to_render:
                render_protocol_pdf_for_submission(meeting, submission)

            pdfs_sent_to_render = len(submissions_to_render)

        # Send all pdfs if requested
        elif 'send_all_pdfs' in request.POST:
            assert meeting.ended is not None
            not_sent_submissions = meeting.submissions.filter(
                meeting_protocols__isnull=False,
                meeting_protocols__protocol_sent_at__isnull=True
            ).values_list('pk', flat=True)

            for submission_pk in not_sent_submissions:
                meeting_protocol = get_object_or_404(
                    MeetingSubmissionProtocol.objects.prefetch_related(Prefetch(
                        'submission', queryset=Submission.objects.prefetch_related('clinics')
                    )),
                    submission=submission_pk
                )

                send_submission_protocol_pdf(request, meeting, meeting_protocol)

            pdfs_sent_per_email = len(not_sent_submissions)
        # Afterwards just show the list as usual

    submissions = meeting.submissions.prefetch_related(
        Prefetch(
            'meeting_protocols', to_attr='protocols',
            queryset=MeetingSubmissionProtocol.objects.filter(meeting=meeting)
        )
    )

    return render(request, 'meetings/tabs/clinics.html', {
        'meeting': meeting,
        'submissions': submissions,
        'pdfs_sent_to_render': pdfs_sent_to_render,
        'pdfs_sent_per_email': pdfs_sent_per_email
    })


@user_group_required('EC-Office')
def render_submission_protocol(request, meeting_pk=None, submission_pk=None):
    try:
        # Get Meeting or fail
        meeting = get_object_or_404(Meeting, pk=meeting_pk)
        # Get the submission from the pool of possible submission in this meeting
        submission = get_object_or_404(meeting.submissions, id=submission_pk)
        render_protocol_pdf_for_submission(meeting, submission)
        return redirect(reverse('meetings.meeting_details', kwargs={'meeting_pk': meeting.id}) + '#clinic_tab')
    except:
        raise Http404('')


@user_group_required('EC-Office')
def submission_protocol_pdf(request, meeting_pk=None, protocol_pk=None):
    # meeting = get_object_or_404(Meeting, pk=meeting_pk)
    meeting_protocol = get_object_or_404(MeetingSubmissionProtocol, pk=protocol_pk)

    protocol = meeting_protocol.protocol
    response = FileResponse(protocol.retrieve_raw(), content_type=protocol.mimetype)
    response['Content-Disposition'] = 'attachment;filename={}'.format(protocol.original_file_name)
    return response


@user_group_required('EC-Office')
def send_submission_protocol(request, meeting_pk=None, submission_pk=None):
    meeting = get_object_or_404(Meeting, ended__isnull=False, pk=meeting_pk)
    meeting_protocol = get_object_or_404(
        MeetingSubmissionProtocol.objects.prefetch_related(Prefetch(
            'submission', queryset=Submission.objects.prefetch_related('clinics')
        )),
        submission=submission_pk,
        meeting=meeting
    )

    send_submission_protocol_pdf(request, meeting, meeting_protocol)
    return redirect(reverse('meetings.meeting_details', kwargs={'meeting_pk': meeting.id}) + '#clinic_tab')


@user_group_required('EC-Office')
def list_ek_member(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting.objects.prefetch_related('board_members'), pk=meeting_pk)
    user_ids_in_meeting = meeting.board_members.all().values_list('id', flat=True)
    form = EkMemberMarkedForm(request.POST or None, initial={'users': list(map(str, user_ids_in_meeting))})
    meeting_ended = meeting.ended is not None
    if meeting_ended:
        form.fields['users'].disabled = True

    if request.method == 'POST' and form.is_valid() and not meeting_ended:
        new_user_ids = set(map(int, form.cleaned_data['users']))
        current_user_ids = set(user_ids_in_meeting)
        # Get the connection that need to be deleted (current - new) -> [1, 5, 9] - [1, 5, 10, 11] = [9]
        users_to_delete = current_user_ids.difference(new_user_ids)
        # Get the connectionts that need to be added (new - current) -> [1, 5, 10, 11] - [1, 5, 9] = [10, 11]
        users_to_add = new_user_ids.difference(current_user_ids)
        # Delete and create the connectinos
        meeting.board_members.remove(*users_to_delete)
        meeting.board_members.add(*users_to_add)

    return render(request, 'meetings/tabs/ek-member.html', {
        'form': form,
        'meeting': meeting,
        'meeting_ended': meeting_ended,
    })


@user_group_required('EC-Office', 'EC-Executive', 'Board Member', 'Omniscient Board Member', 'Resident Board Member')
def list_documents(request, meeting_pk=None):
    meeting = get_object_or_404(Meeting.objects.prefetch_related('board_members'), pk=meeting_pk)

    if 'new_meeting_documents' in request.FILES:
        for file in request.FILES.getlist('new_meeting_documents'):
            document = Document.objects.create_from_buffer(
                file.read(), doctype='meeting_documents',
                parent_object=meeting, stamp_on_download=False,
                mimetype=file.content_type, name=file.name
            )
            meeting_document = MeetingDocument(meeting=meeting, document=document, uploaded_by=request.user)
            meeting_document.save()

    if request.user.profile.is_internal:
        meeting_documents = meeting.meetingdocument_set.all()
    else:
        meeting_documents = meeting.meetingdocument_set.filter(board_member_insight=True)

    return render(request, 'meetings/tabs/documents.html', {
        'meeting': meeting,
        'meeting_documents': meeting_documents
    })


@user_group_required('EC-Office', 'EC-Executive')
def toggle_visiblity_for_member(request, meeting_pk=None, meeting_document_pk=None):
    meeting_document = get_object_or_404(
        MeetingDocument,
        pk=meeting_document_pk,
        document__content_type=ContentType.objects.get_for_model(Meeting),
        document__object_id=meeting_pk,
    )

    # Toggle visibility
    meeting_document.board_member_insight = not meeting_document.board_member_insight
    meeting_document.save(update_fields=['board_member_insight'])

    return HttpResponse(status=204)


@user_group_required('EC-Office', 'EC-Executive', 'Board Member', 'Omniscient Board Member', 'Resident Board Member')
def download_meeting_documents(request, meeting_pk=None, meeting_document_pk=None):
    query_arguments = {
        'pk': meeting_document_pk,
        'document__content_type': ContentType.objects.get_for_model(Meeting),
        'document__object_id': meeting_pk,
    }
    # If the user is not Office or Executive only query for documents that have board_member_insight set to true
    if not request.user.profile.is_internal:
        query_arguments['board_member_insight'] = True

    meeting_document = get_object_or_404(MeetingDocument, **query_arguments)
    doc = meeting_document.document

    response = FileResponse(doc.retrieve_raw(), content_type=doc.mimetype)
    response['Content-Disposition'] = 'attachment;filename={}'.format(doc.name)
    return response


@user_group_required('EC-Office', 'EC-Executive')
def delete_meeting_documents(request, meeting_pk=None, meeting_document_pk=None):
    meeting_document = get_object_or_404(
        MeetingDocument,
        pk=meeting_document_pk,
        document__content_type=ContentType.objects.get_for_model(Meeting),
        document__object_id=meeting_pk,
    )

    meeting_document.document.delete()
    meeting_document.delete()
    return HttpResponse(status=204)
