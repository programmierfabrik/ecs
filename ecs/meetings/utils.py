from django.utils import timezone


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
    # return redirect(reverse('meetings.meeting_details', kwargs={'meeting_pk': meeting.id}) + '#clinic_tab')
