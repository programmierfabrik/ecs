from django.dispatch import receiver

from ecs.meetings import signals
from ecs.meetings.cache import flush_meeting_page_cache
from ecs.meetings.models import Participation
from ecs.meetings.utils import remove_task_for_board_members
from ecs.votes.models import Vote
from ecs.workflow.signals import token_marked_deleted


def _flush_cache(meeting):
    from ecs.meetings.views import submission_list

    flush_meeting_page_cache(meeting, submission_list)


@receiver(signals.on_meeting_start)
def on_meeting_start(sender, **kwargs):
    meeting = kwargs["meeting"]
    _flush_cache(meeting)


@receiver(signals.on_meeting_end)
def on_meeting_end(sender, **kwargs):
    meeting = kwargs["meeting"]

    for vote in Vote.objects.filter(top__meeting=meeting):
        vote.save()  # trigger post_save for all votes

    for top in meeting.additional_entries.exclude(
        pk__in=Vote.objects.exclude(top=None).values("top__pk").query
    ):
        # update eventual existing vote from vote preperation
        defaults = {"top": top, "result": "3a", "is_draft": False}
        try:
            vote = Vote.objects.get(submission_form=top.submission.current_submission_form)
            for key, value in defaults.items():
                setattr(vote, key, value)
            vote.save()
        except Vote.DoesNotExist:
            new_values = {'submission_form': top.submission.current_submission_form}
            new_values.update(defaults)
            vote = Vote(**new_values)
            vote.save()
        # update_or_create uses select_for_update. Due to that django generates an invalid query with the error:
        # FOR UPDATE is not allowed with DISTINCT clause
        top.is_open = False
        top.save()

    # Remove (close) all the remaining tasks for the given board member
    submissions = meeting.submissions.all()
    board_members = meeting.board_members.all()
    for submission in submissions:
        remove_task_for_board_members(submission, board_members)

    _flush_cache(meeting)


@receiver(signals.on_meeting_date_changed)
def on_meeting_date_changed(sender, **kwargs):
    meeting = kwargs["meeting"]
    _flush_cache(meeting)


@receiver(signals.on_meeting_top_jump)
def on_meeting_top_jump(sender, **kwargs):
    meeting = kwargs["meeting"]
    timetable_entry = kwargs["timetable_entry"]
    _flush_cache(meeting)


@receiver(signals.on_meeting_top_add)
def on_meeting_top_add(sender, **kwargs):
    meeting = kwargs["meeting"]
    timetable_entry = kwargs["timetable_entry"]
    _flush_cache(meeting)


@receiver(signals.on_meeting_top_delete)
def on_meeting_top_delete(sender, **kwargs):
    meeting = kwargs["meeting"]
    timetable_entry = kwargs["timetable_entry"]
    _flush_cache(meeting)


@receiver(signals.on_meeting_top_index_change)
def on_meeting_top_index_change(sender, **kwargs):
    meeting = kwargs["meeting"]
    timetable_entry = kwargs["timetable_entry"]
    _flush_cache(meeting)


@receiver(token_marked_deleted)
def workflow_token_marked_deleted(sender, **kwargs):
    if sender.task:
        Participation.objects.filter(
            entry__meeting__started=None, task=sender.task
        ).delete()
