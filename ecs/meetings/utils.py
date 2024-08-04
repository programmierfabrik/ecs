from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.db.models import Q
from django.utils import timezone

from ecs import settings
from ecs.communication.mailutils import deliver
from ecs.tasks.models import TaskType, Task
from ecs.users.utils import sudo
from ecs.utils.viewutils import render_html


def render_protocol_pdf_for_submission(meeting, submission):
    # Get the protocol or create it
    meeting_protocol, _ = meeting.meeting_protocols.get_or_create(
        submission=submission
    )

    # If a protocol is already being rendered, raise an error
    if meeting_protocol.protocol_rendering_started_at is not None:
        raise Exception('Concurrent Rendering')

    if meeting_protocol.protocol:
        meeting_protocol.protocol.delete()

    # Start the rendering process
    meeting_protocol.protocol_rendering_started_at = timezone.now()

    from ecs.meetings.tasks import render_meeting_protocol_pdf
    render_meeting_protocol_pdf.apply_async(kwargs={'meeting_protocol': meeting_protocol})


def send_submission_protocol_pdf(request, meeting, meeting_protocol):
    meeting_protocol.protocol_sent_at = timezone.now()
    meeting_protocol.save(update_fields=('protocol_sent_at',))

    protocol = meeting_protocol.protocol
    protocol_pdf = protocol.retrieve_raw().read()
    attachments = (
        (protocol.original_file_name, protocol_pdf, 'application/pdf'),
    )

    clinics = meeting_protocol.submission.clinics.all()
    for clinic in clinics:
        email = clinic.email
        htmlmail = str(render_html(
            request, 'meetings/messages/protocol-clinic.html',
            {'meeting': meeting, 'recipient': clinic.name, 'submission': meeting_protocol.submission}
        ))

        deliver(email, subject='Protokollauszug', message=None,
                message_html=htmlmail, from_email=settings.DEFAULT_FROM_EMAIL,
                attachments=attachments)


def create_task_for_board_members(submission, board_members):
    # From the board_members that were selected in the ui "board_members" remove the biased ones for the given submission
    board_members_to_add = board_members.filter(~Q(id__in=submission.biased_board_members.all()))
    for member in board_members_to_add:
        tasks = Task.unfiltered.for_submission(submission).open().filter(assigned_to=member, task_type__name='Specialist Review')
        # Maybe the task for this user was already created manually
        if not tasks.exists():
            task_type = TaskType.objects.get(is_dynamic=True, workflow_node__graph__auto_start=True, name='Specialist Review')
            token = task_type.workflow_node.bind(submission.workflow.workflows[0]).receive_token(None)
            token.task.assign(user=member)
            task = token.task
            entry = submission.timetable_entries.filter(meeting__started=None).first()
            if entry:
                entry.participations.get_or_create(user=member, task=task)

            task.send_message_on_close = False
            task.reminder_message_timeout = None
            task.save()


def remove_task_for_board_members(submission, board_members):
    for member in board_members:
        tasks = Task.unfiltered.for_submission(submission).open().filter(
            task_type__name='Specialist Review', assigned_to=member, created_by__isnull=True
        )

        if tasks.exists():
            tasks.first().mark_deleted()


def get_users_for_protocol(meeting, invited_group_ids, invite_ek_member=False, board_members=None, board_member_group=None):
    if board_members is None:
        board_members = meeting.board_members.all()
    if board_member_group is None:
        board_member_group = Group.objects.get(name='Board Member')
    
    group_ids = invited_group_ids.copy()
    if invite_ek_member and str(board_member_group.pk) in group_ids:
        group_ids.remove(str(board_member_group.pk))
        board_member_filter = Q(pk__in=board_members)
    else:
        board_member_filter = Q()
    return User.objects.filter((Q(groups__in=group_ids) | board_member_filter) & Q(is_active=True)).distinct()


def reschedule_submission_meeting(from_meeting, submission, to_meeting):
    # Instead of changing the whole workflow and the logic how the categoriziation works
    # We instead create a shallow entry which will later be updated in the categorization workflow
    # visible needs to be false so the duration gets updated if the visibilty is actually true (workflow_lane = BOARD)
    # Duration 0 is just a default value since it will be updated either way
    duration = timedelta(minutes=0)
    visible = False
    title = None
    old_entry = None
    if from_meeting is not None:
        old_entry = from_meeting.timetable_entries.get(submission=submission)
        assert not hasattr(old_entry, 'vote')
        visible = (not old_entry.timetable_index is None)
        duration = old_entry.duration
        title = old_entry.title

    new_entry = to_meeting.add_entry(submission=submission, duration=duration, title=title, visible=visible)
    
    if from_meeting is not None and old_entry is not None:
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


def get_blocking_meeting_tasks(meeting):
    with sudo():
        # Get the list of submissions from timetable_entries
        submission_ids = [top.submission.pk for top in meeting.timetable_entries.filter(submission__isnull=False)]

        # Get open recommendations
        recommendations = Task.objects.filter(
            task_type__workflow_node__uid__in=[
                'thesis_recommendation', 'thesis_recommendation_review',
                'expedited_recommendation',
                'localec_recommendation'
            ],
        ).for_submissions(submission_ids).open()

        # Get open vote preparations
        vote_preparations = Task.objects.filter(
            task_type__workflow_node__uid='vote_preparation',
        ).for_submissions(submission_ids).open()

        return {'recommendations': recommendations, 'vote_preparations': vote_preparations}
