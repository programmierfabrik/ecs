import random
from datetime import timedelta
from functools import reduce
from collections import defaultdict

from django.db.models.fields import DateTimeField, BooleanField
from django.urls import reverse
from django.db.models import Q, Prefetch, ExpressionWrapper, When, F, Case, Value
from django.http import Http404, QueryDict, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.views.decorators.http import require_POST

from ecs.utils.viewutils import redirect_to_next_url
from ecs.users.utils import user_flag_required, sudo
from ecs.users.models import UserProfile
from ecs.core.models import Submission, SubmissionForm, Investigator, AdvancedSettings
from ecs.core.models.constants import (
    SUBMISSION_LANE_BOARD, SUBMISSION_LANE_EXPEDITED,
    SUBMISSION_LANE_RETROSPECTIVE_THESIS, SUBMISSION_LANE_LOCALEC,
)
from ecs.checklists.models import Checklist
from ecs.tasks.models import Task
from ecs.tasks.forms import TaskListFilterForm
from ecs.tasks.signals import task_declined
from ecs.tasks.tasks import send_delete_message
from ecs.votes.models import Vote
from ecs.notifications.models import (
    NOTIFICATION_MODELS, Notification, SafetyNotification,
)
from ecs.meetings.models import Meeting


@user_flag_required('is_internal')
def task_backlog(request, submission_pk=None):
    submission = get_object_or_404(Submission, pk=submission_pk)

    # Filter for users who are is_indisposed since the communication_proxy is still set even though the user is not indisposed
    communication_proxy_users = [profile.user for profile in request.user.communication_proxy_profiles.all() if
                                 profile.is_indisposed]
    with sudo():
        tasks = list(
            Task.objects.for_submission(submission)
            .select_related(
                'task_type', 'task_type__group', 'assigned_to',
                'assigned_to__profile', 'medical_category'
            )
            .annotate(
                deadline=ExpressionWrapper(
                    F('created_at') + Case(
                        When(
                            reminder_message_timeout__isnull=False, then='reminder_message_timeout'
                        ),
                        default=None
                    ), output_field=DateTimeField()
                ),
                has_access=Case(
                    When(
                        Q(created_by=request.user) | Q(created_by__in=communication_proxy_users),
                        then=Value(True)
                    ),
                    default=Value(False),
                    output_field=BooleanField()
                )
            )
            .order_by('-created_at')
        )

    return render(request, 'tasks/log.html', {
        'tasks': tasks,
        'submission': submission,
    })


@user_flag_required('is_internal')
def delete_task(request, submission_pk=None, task_pk=None):
    submission = get_object_or_404(Submission, pk=submission_pk)
    with sudo():
        task = get_object_or_404(Task.objects.for_submission(submission).open(),
            pk=task_pk, task_type__is_dynamic=True)
        task.mark_deleted()
    if task.task_type.is_dynamic and task.created_by and \
        task.created_by != request.user:
        send_delete_message(task, request.user)
    return redirect('tasks.task_backlog', submission_pk=submission_pk)


def my_tasks(request, template=None, submission_pk=None, ignore_task_types=True):
    if template is None:
        template = 'tasks/compact_list.html'
    submission = None
    all_tasks = (Task.objects.for_user(request.user).for_widget().open()
        .select_related('task_type__workflow_node')
        .only(
            'accepted', 'content_type_id', 'data_id',
            'task_type__workflow_node__uid', 'task_type__is_delegatable',
        ).order_by('task_type__workflow_node__uid', 'created_at', 'assigned_at'))

    if submission_pk:
        submission = get_object_or_404(Submission, pk=submission_pk)
        all_tasks = all_tasks.for_submission(submission)
    else:
        usersettings = request.user.ecs_settings

        filterdict = request.POST or request.GET or None
        if filterdict is None and usersettings.task_filter is not None:
            filterdict = QueryDict(usersettings.task_filter)
        filterform = TaskListFilterForm(filterdict)

        if request.method == 'POST':
            usersettings.task_filter = filterform.urlencode()
            usersettings.save()
            if len(request.GET) > 0:
                return redirect(request.path)

    open_tasks = all_tasks.filter(assigned_to=None).for_submissions(
        Submission.objects.exclude(biased_board_members=request.user))

    my_tasks = all_tasks.filter(assigned_to=request.user)

    if AdvancedSettings.objects.get(pk=1).dont_delegate_specalist_tasks_from_executive:
        proxy_tasks = (all_tasks
                       .for_submissions(Submission.objects.exclude(biased_board_members=request.user))
                       .filter(assigned_to__profile__is_indisposed=True)
                       .exclude(assigned_to=request.user)
                       .exclude(Q(task_type__name='Specialist Review') & Q(assigned_to__profile__is_executive=True)))
    else:
        proxy_tasks = (all_tasks
                       .for_submissions(Submission.objects.exclude(biased_board_members=request.user))
                       .filter(assigned_to__profile__is_indisposed=True)
                       .exclude(assigned_to=request.user))

    if not submission and filterform.is_valid():
        cd = filterform.cleaned_data
        past_meetings = cd['past_meetings']
        next_meeting = cd['next_meeting']
        upcoming_meetings = cd['upcoming_meetings']
        no_meeting = cd['no_meeting']
        lane_board = cd['lane_board']
        lane_expedited = cd['lane_expedited']
        lane_retrospective_thesis = cd['lane_retrospective_thesis']
        lane_localec = cd['lane_localec']
        lane_none = cd['lane_none']
        amg = cd['amg']
        mpg = cd['mpg']
        thesis = cd['thesis']
        other = cd['other']

        if (past_meetings and next_meeting and upcoming_meetings and no_meeting and
            lane_board and lane_expedited and lane_retrospective_thesis and lane_localec and lane_none and
            amg and mpg and thesis and other):
            pass
        else:
            submissions = Submission.objects.all()

            if not (past_meetings and next_meeting and upcoming_meetings and no_meeting):
                qs = []
                if past_meetings:
                    qs.append(Q(meetings__ended__isnull=False))
                if next_meeting:
                    try:
                        meeting = Meeting.objects.next()
                    except Meeting.DoesNotExist:
                        pass
                    else:
                        qs.append(Q(meetings=meeting))
                if upcoming_meetings:
                    qs.append(Q(meetings__isnull=False, meetings__ended=None))
                if no_meeting:
                    qs.append(Q(meetings=None))

                if qs:
                    submissions = submissions.filter(reduce(lambda x, y: x | y, qs))
                else:
                    submissions = submissions.none()

            if not (lane_board and lane_expedited and lane_retrospective_thesis and lane_localec and lane_none):
                lanes = []
                if lane_board:
                    lanes.append(SUBMISSION_LANE_BOARD)
                if lane_expedited:
                    lanes.append(SUBMISSION_LANE_EXPEDITED)
                if lane_retrospective_thesis:
                    lanes.append(SUBMISSION_LANE_RETROSPECTIVE_THESIS)
                if lane_localec:
                    lanes.append(SUBMISSION_LANE_LOCALEC)
                q = Q(workflow_lane__in=lanes)
                if lane_none:
                    q |= Q(workflow_lane=None)

                submissions = submissions.filter(q)

            if not (amg and mpg and thesis and other):
                amg_q = Submission.objects.amg()
                mpg_q = Submission.objects.mpg()
                thesis_q = Submission.objects.exclude(
                    current_submission_form__project_type_education_context=None)
                other_q = Submission.objects.exclude(
                    pk__in=(amg_q | mpg_q | thesis_q).values('pk'))

                q = Submission.objects.none()
                if amg:
                    q |= amg_q
                if mpg:
                    q |= mpg_q
                if thesis:
                    q |= thesis_q
                if other:
                    q |= other_q
                submissions &= q

            submission_q = submissions.values('pk')
            checklist_ct = ContentType.objects.get_for_model(Checklist)
            submission_ct = ContentType.objects.get_for_model(Submission)
            vote_ct = ContentType.objects.get_for_model(Vote)
            notification_cts = list(map(ContentType.objects.get_for_model, NOTIFICATION_MODELS))

            submission_tasks_q = Q(
                content_type=submission_ct, data_id__in=submission_q)

            checklist_tasks_q = Q(
                content_type=checklist_ct,
                data_id__in=Checklist.objects.filter(
                    submission__in=submission_q
                ).values('pk'))

            vote_tasks_q = Q(
                content_type=vote_ct,
                data_id__in=Vote.objects.filter(
                    submission_form__submission__in=submission_q
                ).values('pk'))

            notification_tasks_q = Q(
                content_type__in=notification_cts,
                data_id__in=Notification.objects.filter(
                    submission_forms__submission__in=submission_q
                ).values('pk'))

            open_tasks = open_tasks.filter(submission_tasks_q |
                checklist_tasks_q | vote_tasks_q | notification_tasks_q)
    
        if not ignore_task_types:
            task_types = filterform.cleaned_data['task_types']
            if task_types:
                open_tasks = open_tasks.filter(task_type__workflow_node__uid__in=
                    task_types.values('workflow_node__uid'))

    def _prefetch_data(tasks):
        tasks_by_submission = defaultdict(list)
        submission_ct = ContentType.objects.get_for_model(Submission)
        for task in tasks:
            if task.content_type_id == submission_ct.id:
                tasks_by_submission[task.data_id].append(task)
        submissions = Submission.objects.filter(
            id__in=tasks_by_submission.keys(),
        ).only('ec_number')
        for submission in submissions:
            for task in tasks_by_submission[submission.id]:
                task._data_cache = submission

        tasks_by_checklist = defaultdict(list)
        checklist_ct = ContentType.objects.get_for_model(Checklist)
        for task in tasks:
            if task.content_type_id == checklist_ct.id:
                tasks_by_checklist[task.data_id].append(task)
        checklists = Checklist.objects.filter(
            id__in=tasks_by_checklist.keys(),
        ).select_related(
            'blueprint', 'submission', 'submission__current_submission_form',
            'last_edited_by',
        ).only(
            'last_edited_by', 'user_id',

            'submission__ec_number',
            'submission__current_submission_form_id',
            'submission__presenter_id', 'submission__susar_presenter_id',

            'submission__current_submission_form__submitter_id',
            'submission__current_submission_form__sponsor_id',

            'blueprint__multiple', 'blueprint__name',
            'blueprint__reviewer_is_anonymous',

            'last_edited_by__first_name',
            'last_edited_by__last_name',
            'last_edited_by__email',
            'last_edited_by__profile__gender',
            'last_edited_by__profile__title',
        ).prefetch_related(
            Prefetch('submission__current_submission_form__investigators',
                queryset=Investigator.objects
                    .only('user_id', 'submission_form_id',)
            ),
            Prefetch('last_edited_by__profile', queryset=
                UserProfile.objects.only('user_id', 'gender', 'title')
            ),
        )
        for checklist in checklists:
            for task in tasks_by_checklist[checklist.id]:
                task._data_cache = checklist

        tasks_by_notification = defaultdict(list)
        notification_ct = ContentType.objects.get_for_model(SafetyNotification)
        for task in tasks:
            if task.content_type_id == notification_ct.id:
                tasks_by_notification[task.data_id].append(task)
        notifications = SafetyNotification.objects.filter(
            id__in=tasks_by_notification.keys(),
        ).select_related('type').only(
            'safety_type', 'type__name',
        ).prefetch_related(
            Prefetch('submission_forms', queryset=
                SubmissionForm.objects.select_related('submission')
                    .only('submission__ec_number')
            ),
        )
        for notification in notifications:
            for task in tasks_by_notification[notification.id]:
                task._data_cache = notification
                task._data_cache._safetynotification_cache = notification

        for model in NOTIFICATION_MODELS:
            if model == SafetyNotification:
                continue

            tasks_by_notification = defaultdict(list)
            notification_ct = ContentType.objects.get_for_model(model)
            for task in tasks:
                if task.content_type_id == notification_ct.id:
                    tasks_by_notification[task.data_id].append(task)
            notifications = model.objects.filter(
                id__in=tasks_by_notification.keys(),
            ).select_related('type').only('type__name').prefetch_related(
                Prefetch('submission_forms', queryset=
                    SubmissionForm.objects.select_related('submission')
                        .only('submission__ec_number')
                ),
            )
            for notification in notifications:
                for task in tasks_by_notification[notification.id]:
                    task._data_cache = notification
                    task._data_cache._safetynotification_cache = None

        tasks_by_vote = defaultdict(list)
        vote_ct = ContentType.objects.get_for_model(Vote)
        for task in tasks:
            if task.content_type_id == vote_ct.id:
                tasks_by_vote[task.data_id].append(task)
        votes = Vote.objects.filter(id__in=tasks_by_vote.keys()).select_related(
            'submission_form', 'submission_form__submission',
        ).only(
            'result', 'submission_form__id',
            'submission_form__submission__ec_number',
        )
        for vote in votes:
            for task in tasks_by_vote[vote.id]:
                task._data_cache = vote

    _prefetch_data(my_tasks)
    _prefetch_data(proxy_tasks)
    _prefetch_data(open_tasks)

    data = {
        'submission': submission,
        'form_id': 'task_list_filter_%s' % random.randint(1000000, 9999999),
        'my_tasks': my_tasks,
        'proxy_tasks': proxy_tasks,
        'open_tasks': open_tasks,
    }
    if not submission:
        data.update({
            'filterform': filterform,
            'bookmarklink':
                '{0}?{1}'.format(
                    request.build_absolute_uri(request.path),
                    filterform.urlencode()
                ),
        })

    return render(request, template, data)


def task_list(request, *args, **kwargs):
    kwargs.setdefault('template', 'tasks/list.html')
    kwargs.setdefault('ignore_task_types', False)
    return my_tasks(request, **kwargs)


@require_POST
def accept_task(request, task_pk=None, full=False):
    task = get_object_or_404(Task.objects.acceptable_for_user(request.user), pk=task_pk)
    task.accept(request.user)

    submission_pk = request.GET.get('submission')
    view = 'tasks.task_list' if full else 'tasks.my_tasks'
    return redirect_to_next_url(request, reverse(view, kwargs={'submission_pk': submission_pk} if submission_pk else None))

@require_POST
def accept_task_full(request, task_pk=None):
    return accept_task(request, task_pk=task_pk, full=True)

@require_POST
def accept_tasks(request, full=False):
    task_ids = request.POST.getlist('task_id')
    submission_pk = request.GET.get('submission')
    tasks = Task.objects.acceptable_for_user(request.user).filter(id__in=task_ids)

    for task in tasks:
        task.accept(request.user)

    view = 'tasks.task_list' if full else 'tasks.my_tasks'
    return redirect_to_next_url(request, reverse(view, kwargs={'submission_pk': submission_pk} if submission_pk else None))

@require_POST
def accept_tasks_full(request):
    return accept_tasks(request, full=True)

@require_POST
def decline_task(request, task_pk=None, full=False):
    task = get_object_or_404(Task.objects, assigned_to=request.user,
        task_type__is_delegatable=True, pk=task_pk)
    task.assign(None)
    task_declined.send(type(task.node_controller), task=task)

    submission_pk = request.GET.get('submission')
    view = 'tasks.task_list' if full else 'tasks.my_tasks'
    return redirect_to_next_url(request, reverse(view, kwargs={'submission_pk': submission_pk} if submission_pk else None))

@require_POST
def decline_task_full(request, task_pk=None):
    return decline_task(request, task_pk=task_pk, full=True)


def do_task(request, task_pk=None):
    task = get_object_or_404(Task, assigned_to=request.user, pk=task_pk)
    url = task.url
    if not task.closed_at is None:
        url = task.afterlife_url
        if url is None:
            raise Http404()
    return redirect(url)


def preview_task(request, task_pk=None):
    task = get_object_or_404(Task, pk=task_pk)
    url = task.get_preview_url()
    if not url:
        raise Http404()
    return redirect(url)


def reset_reminder_timeout_task(request, task_pk=None):
    communication_proxy_users = [profile.user for profile in request.user.communication_proxy_profiles.all() if
                                 profile.is_indisposed]
    task = get_object_or_404(Task.unfiltered, pk=task_pk, created_by__in=[request.user] + communication_proxy_users)

    if request.POST:
        timeout_days = request.POST.get('reminder_message_timeout')
        if timeout_days.isdigit() and int(timeout_days) > 0:
            timeout_days = int(timeout_days)
            interval_from_created_at = timezone.now() - task.created_at
            task.reminder_message_timeout = interval_from_created_at + timedelta(days=timeout_days)
            task.save(update_fields=('reminder_message_timeout',))
            return HttpResponse(status=204)

    return HttpResponse(status=400)
