"""Build ECS objects for tests and local scenarios, following the real lifecycle.

A study gets its vote the way it does in production: it is scheduled onto a
meeting as a TOP, the meeting starts, the vote is recorded on the TOP, the
meeting ends (which starts the vote workflow), and the workflow's tasks are
done until the vote is published. Each step calls the code the UI calls and
refuses what the UI refuses, so a recessed vote sends the study on to a
further meeting by itself.

Callers name only the fields their scenario is about; every other required
column gets a placeholder (see ``fill_required``).
"""
import os
from datetime import timedelta

from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils import timezone

from ecs.core.models import EthicsCommission, Investigator, Submission, SubmissionForm
from ecs.documents.models import Document, DocumentType
from ecs.meetings.models import Meeting, Participation
from ecs.meetings.signals import on_meeting_end, on_meeting_start
from ecs.tasks.models import Task
from ecs.users.utils import get_or_create_user
from ecs.votes.forms import VoteForm

LOREM = 'Lorem ipsum dolor sit amet'
TEST_PDF = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        'core', 'tests', 'data', 'menschenrechtserklaerung.pdf')


def placeholder(field):
    """A value of the right type for ``field``, or None for relations."""
    if field.flatchoices:
        return field.flatchoices[0][0]
    if isinstance(field, models.BooleanField):
        return False
    if isinstance(field, models.EmailField):
        return 'lorem@example.org'
    if isinstance(field, (models.CharField, models.TextField)):
        return LOREM[:field.max_length] if field.max_length else LOREM
    if isinstance(field, (models.IntegerField, models.DecimalField, models.FloatField)):
        return 1
    if isinstance(field, models.DateTimeField):
        return timezone.now()
    if isinstance(field, models.DateField):
        return timezone.localdate()
    if isinstance(field, ArrayField):
        return []
    if isinstance(field, models.JSONField):
        return {}
    return None


def fill_required(model, values):
    """Return ``values`` completed with placeholders for ``model``.

    Fills non-null columns that are missing or given as None, and nullable
    choice columns, which templates index without a None check.
    """
    values = dict(values)
    for field in model._meta.concrete_fields:
        if field.primary_key or field.is_relation or getattr(field, 'auto_now', False) \
                or getattr(field, 'auto_now_add', False):
            continue
        given = field.name in values or field.attname in values
        if given and (values.get(field.name, values.get(field.attname)) is not None or field.null):
            continue
        if not given and field.has_default():
            continue
        if not given and field.null and not field.flatchoices:
            continue
        value = placeholder(field)
        if value is not None:
            values[field.name] = value
    return values


def attach_document(parent, filelike, name, doctype_identifier, mimetype='application/pdf', version='1', date=None):
    doc = Document.objects.create(
        version=version, date=date or timezone.now(), name=name, mimetype=mimetype,
        doctype=DocumentType.objects.get(identifier=doctype_identifier), parent_object=parent)
    doc.store(filelike)
    parent.documents.add(doc)
    return doc


def create_submission_form(ec_number=None, presenter=None, *, render_pdf=True, **fields):
    """A classic (non-CTR) submission form with a protocol and a main investigator.

    The kind of study is just fields, e.g. ``project_type_medical_device=True``
    for an MPG study or ``project_type_non_reg_drug=True`` for an AMG one.
    """
    presenter = presenter or get_or_create_user('test_presenter@example.com')[0]
    submission = Submission.objects.create(ec_number=ec_number, presenter=presenter, susar_presenter=presenter)
    sf = SubmissionForm.objects.create(**fill_required(
        SubmissionForm, {'submission': submission, 'presenter': presenter, **fields}))

    with open(TEST_PDF, 'rb') as f:
        attach_document(sf, f, 'protocol.pdf', 'protocol')
    ec = EthicsCommission.objects.create(name='EK von Neverland')
    Investigator.objects.create(**fill_required(Investigator, {
        'submission_form': sf, 'main': True, 'ethics_commission': ec, 'subject_count': 1}))
    if render_pdf:
        sf.render_pdf_document()
    return sf


def create_meeting(start=None, board_members=(), **fields):
    """An upcoming meeting. ``board_members`` are the members selected on the
    "EK-Mitglieder" tab."""
    start = start or timezone.now() + timedelta(days=7)
    fields.setdefault('deadline', start - timedelta(days=3))
    fields.setdefault('deadline_diplomathesis', start - timedelta(days=10))
    meeting = Meeting.objects.create(**fill_required(Meeting, {'start': start, **fields}))
    meeting.board_members.set(board_members)
    return meeting


def schedule(submission, meeting=None, participants=()):
    """Put the study on ``meeting`` (default: the next schedulable one) and
    return its TOP. ``participants`` take part in that TOP."""
    requested = meeting
    meeting = submission.schedule_to_meeting(meeting)
    if requested is None and meeting.started:
        raise ValueError(f'submission {submission.pk} is not due for another meeting '
                         f'(only a recessed vote sends it on)')
    top = submission.timetable_entries.filter(meeting=meeting).latest('pk')
    for user in participants:
        Participation.objects.get_or_create(entry=top, user=user)
    return top


def start_meeting(meeting):
    if meeting.started:
        raise ValueError(f'meeting {meeting.pk} has already started')
    meeting.started = timezone.now()
    meeting.save()
    on_meeting_start.send(Meeting, meeting=meeting)
    return meeting


def record_vote(top, result, text='', close_top=True):
    """Record the vote on a TOP of a running meeting, as the meeting assistant does."""
    if not top.meeting.started or top.meeting.ended:
        raise ValueError(f'meeting {top.meeting_id} is not running')
    if not top.is_open:
        raise ValueError(f'TOP {top.pk} is already closed')
    form = VoteForm({'result': result, 'text': text}, instance=getattr(top, 'vote', None),
                    submission=top.submission)
    if not form.is_valid():
        raise ValueError(f'invalid vote: {form.errors.as_json()}')
    vote = form.save(top)
    if close_top:
        top.is_open = False
        top.save()
    return vote


def end_meeting(meeting):
    """End a running meeting; this starts the workflow of every vote recorded in it."""
    if not meeting.started or meeting.ended:
        raise ValueError(f'meeting {meeting.pk} is not running')
    open_tops = list(meeting.open_tops.values_list('pk', flat=True))
    if open_tops:
        raise ValueError(f'meeting {meeting.pk} still has open TOPs {open_tops}')
    meeting.ended = timezone.now()
    meeting.save()
    on_meeting_end.send(Meeting, meeting=meeting)
    return meeting


def finish_vote_workflow(vote, max_steps=10):
    """Do the vote's open tasks (finalization, reviews, signing) until it is published.

    Reviews are done with the vote marked final; signing stores the signed PDF
    the way the signing callback does (``votes.views.sign_success``).
    """
    for _ in range(max_steps):
        vote.refresh_from_db()
        if vote.published_at:
            return vote
        task = Task.objects.for_data(vote).open().order_by('pk').first()
        if task is None:
            raise ValueError(f'vote {vote.pk} is unpublished but has no open task')
        user = task.assigned_to or User.objects.filter(
            groups=task.task_type.group, is_active=True).order_by('pk').first()
        if task.task_type.workflow_node.uid == 'vote_signing':
            Document.objects.create_from_buffer(
                vote.render_pdf(), doctype='votes', parent_object=vote,
                original_file_name=vote.pdf_filename, name=str(vote))
            vote.signed_at = timezone.now()
            vote.save()
            task.done(choice=True, user=user)
        else:
            vote.is_final_version = True
            vote.save(update_fields=('is_final_version',))
            task.done(user=user)
    raise ValueError(f'vote {vote.pk} not published after {max_steps} tasks')


def vote_in_meeting(submission, result, meeting=None, participants=()):
    """The common path in one call: schedule, start, vote, end, publish."""
    top = schedule(submission, meeting, participants=participants)
    start_meeting(top.meeting)
    vote = record_vote(top, result)
    end_meeting(top.meeting)
    return finish_vote_workflow(vote)
