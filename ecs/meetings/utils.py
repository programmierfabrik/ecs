from django.contrib.auth.models import Group, User
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.utils import timezone

from ecs import settings
from ecs.checklists.models import Checklist
from ecs.communication.mailutils import deliver
from ecs.documents.models import Document
from ecs.tasks.models import TaskType, Task
from ecs.utils.viewutils import render_html


def _read_zip_document(doc, user=None):
    if user is None:
        return doc.retrieve_raw().read()
    return doc.retrieve(user, 'meeting-zip').read()


def write_submission_zip_entries(zf, submission, path, user=None):
    """
    Write every document a submission's meeting zip should carry into `zf`
    under `path`.

    For a CTIS study, that is the same set the restricted (mini) study view
    shows - Synopsis of the protocol plus Austria's own subject
    information/informed consent form - unless `user` has real study-level
    access to it, in which case it is every document the CTIS document
    service holds. `user=None` (the unattended meeting-zip generation task,
    whose one output file is shared by everyone who downloads it) is treated
    as having no such access, since the file cannot be scoped per
    downloader - the restricted set is the only one safe to bake into it. A
    document that cannot be fetched (no version, or CTIS refuses it) is left
    out rather than failing the whole zip.

    For a classic study, its submission form PDF and patient information
    documents, as before - a viewer's study-level access has never gated
    those here (see `download_zipped_documents`), so it does not start
    gating the classic side now either. Checklist review documents either
    way.

    `user` is also who to attribute the download to for a classic study's
    watermarking/audit trail (`Document.retrieve`) - omitted for the task,
    which reads the raw file instead.
    """
    # Imported here, not at module level: ecs.core.ctis(_render) sits above
    # ecs.core.models, which this module's own importer - ecs.meetings.models
    # - sits below, so importing it up top would be circular.
    from ecs.core.ctis import fetch_ctis_document, CTISError
    from ecs.core.ctis_render import external_documents, latest_download_path
    from ecs.core.views.submissions import sees_full_ctr_form

    if submission.uses_ctr_form:
        ctr_submission_form = submission.current_ctr_form
        documents = ctr_submission_form.documents or []
        full_access = user is not None and sees_full_ctr_form(user, submission)
        if not full_access:
            permitted = {d.id for d in external_documents(
                ctr_submission_form.application, documents)}
            documents = [d for d in documents
                         if str(d.get('documentId') or '') in permitted]
        for doc in documents:
            download_path = latest_download_path(doc)
            if not download_path:
                continue
            try:
                fetched = fetch_ctis_document(download_path)
            except CTISError:
                continue
            zf.writestr('/'.join(path + [fetched['filename']]), fetched['content'])
    else:
        sf = submission.current_submission_form
        docs = []
        if sf.pdf_document:
            docs.append(sf.pdf_document)
        docs += sf.documents.filter(doctype__identifier='patientinformation')
        for doc in docs:
            zf.writestr('/'.join(path + [doc.get_filename()]),
                        _read_zip_document(doc, user))

    checklist_docs = Document.objects.filter(
        content_type=ContentType.objects.get_for_model(Checklist),
        object_id__in=submission.checklists.filter(status='review_ok'),
    )
    for doc in checklist_docs:
        zf.writestr('/'.join(path + [doc.get_filename()]),
                    _read_zip_document(doc, user))


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
