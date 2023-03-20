from django.utils import timezone

from ecs import settings
from ecs.communication.mailutils import deliver
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
