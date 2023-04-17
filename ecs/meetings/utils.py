from django.contrib.auth.models import Group, User
from django.db.models import Q
from django.utils import timezone

from ecs import settings
from ecs.communication.mailutils import deliver
from ecs.tasks.models import TaskType, Task
from ecs.users.utils import get_user
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
            request, 'meetings/messages/protocol.html', {'meeting': meeting, 'recipient': clinic.name}
        ))
        
        deliver(email, subject='Protokollauszug', message=None,
                message_html=htmlmail, from_email=settings.DEFAULT_FROM_EMAIL,
                attachments=attachments)


def create_task_for_board_members(submission, board_members):
    task_type = TaskType.objects.get(is_dynamic=True, workflow_node__graph__auto_start=True, name='Specialist Review')

    for member in board_members:
        tasks = Task.unfiltered.for_submission(submission).open().filter(task_type=task_type)
        if not task_type.is_delegatable:
            tasks = tasks.filter(assigned_to=member)
        # Maybe the task for this user was already created manually
        if not tasks.exists():
            token = task_type.workflow_node.bind(submission.workflow.workflows[0]).receive_token(None)
            token.task.assign(user=member)
            task = token.task
            entry = submission.timetable_entries.filter(meeting__started=None).first()
            if entry:
                entry.participations.create(user=member, task=task)

            task.send_message_on_close = False
            task.reminder_message_timeout = None
            task.save()


def remove_task_for_board_members(submission, board_members):
    for member in board_members:
        task_type = TaskType.objects.get(
            is_dynamic=True, workflow_node__graph__auto_start=True,
            name='Specialist Review'
        )
        tasks = Task.unfiltered.for_submission(submission).open().filter(
            task_type=task_type, assigned_to=member,
            created_by__isnull=True
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
    return User.objects.filter(Q(groups__in=group_ids) | board_member_filter).distinct()
