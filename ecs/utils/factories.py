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
import uuid
from datetime import timedelta

from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from ecs.checklists.forms import ChecklistTaskCreationForm, ChecklistTaskCreationStage2Form
from ecs.checklists.models import Checklist
from ecs.checklists.utils import create_dynamic_task
from ecs.core.forms.review import CategorizationForm
from ecs.core.models import EthicsCommission, Investigator, MedicalCategory, Submission, SubmissionForm
from ecs.core.models.constants import SUBMISSION_LANE_BOARD
from ecs.core.workflow import Categorization, ChecklistReview, VotePreparation
from ecs.documents.models import Document, DocumentType
from ecs.meetings.models import Meeting
from ecs.meetings.signals import on_meeting_end, on_meeting_start
from ecs.signature.views import _receive_document
from ecs.tasks.models import Task
from ecs.users.utils import get_or_create_user, get_user, sudo
from ecs.votes.forms import VoteForm, VotePreparationForm, VoteReviewForm
from ecs.votes.views import sign_success
from ecs.votes.workflow import VoteReview, VoteSigning

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
    # Empty means "not a thesis"; a placeholder would make every study one.
    fields.setdefault('project_type_education_context', None)
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
    "EK-Mitglieder" tab.

    By default it is a week ahead, but before any meeting that has not been
    held yet: meetings are held in order of their start, which scheduling
    relies on (``Submission.schedule_to_meeting``).
    """
    if start is None:
        start = timezone.now() + timedelta(days=7)
        first_unheld = Meeting.objects.filter(started=None).order_by('start').values_list('start', flat=True).first()
        if first_unheld is not None:
            start = min(start, first_unheld - timedelta(hours=1))
    fields.setdefault('deadline', start - timedelta(days=3))
    fields.setdefault('deadline_diplomathesis', start - timedelta(days=10))
    meeting = Meeting.objects.create(**fill_required(Meeting, {'start': start, **fields}))
    meeting.board_members.set(board_members)
    return meeting


def schedule(submission, meeting=None, participants=(), **categorization):
    """Bring the study onto a meeting and return its TOP.

    A new study gets there the way it does in the office: initial review and
    categorization (``categorization`` are the categorization form's fields,
    board lane by default), which puts it on the next schedulable meeting.
    If ``meeting`` is another one, the study is rescheduled onto it.
    ``participants`` are specialists: each gets a specialist review task,
    which makes them take part in the TOP.
    """
    run_workflow(submission, fields={'categorization': categorization})
    top = submission.timetable_entries.order_by('-meeting__start', '-pk').first()
    if top is None:
        raise ValueError(f'submission {submission.pk} is on no meeting; open tasks: '
                         f'{_node_uids(_open_tasks(submission))}')
    if top.meeting.started:
        raise ValueError(f'submission {submission.pk} is not due for another meeting '
                         f'(only a recessed vote sends it on)')
    if meeting is not None and top.meeting != meeting:
        top = submission.reschedule(top.meeting, meeting)
    for user in participants:
        create_task(submission, 'specialist_review', assign_to=user)
    return top


def create_task(submission, node_uid, assign_to=None, created_by=None,
                send_message_on_close=False, reminder_days=None):
    """Add a task by hand, as the office does with « create task » on a study
    (``specialist_review``, ``statistical_review``, ``external_review`` ...).

    ``assign_to`` defaults to the group for tasks that can be delegated, else
    to the first active member of the task's group who is not biased;
    ``created_by`` to the first office user.
    """
    if not submission.allows_dynamic_task_creation():
        raise ValueError(f'submission {submission.pk} allows no new tasks')
    task_types = ChecklistTaskCreationForm.base_fields['task_type'].queryset
    task_type = task_types.filter(workflow_node__uid=node_uid).first()
    if task_type is None:
        raise ValueError(f'{node_uid} is not a task the office can add; one of: '
                         f'{sorted(task_types.values_list("workflow_node__uid", flat=True))}')
    form = ChecklistTaskCreationForm({
        'task_type': task_type.pk,
        'send_message_on_close': send_message_on_close,
        'reminder_message_timeout': reminder_days or '',
    })
    if assign_to is None and not task_type.is_delegatable:
        assign_to = task_type.group.user_set.filter(is_active=True).exclude(
            pk__in=submission.biased_board_members.values('pk')).order_by('pk').first()
    stage2 = ChecklistTaskCreationStage2Form(
        submission, task_type, {'assign_to': assign_to.pk if assign_to else ''})
    if not (form.is_valid() and stage2.is_valid()):
        raise ValueError(f'invalid task: {form.errors.as_json()} {stage2.errors.as_json()}')
    created_by = created_by or User.objects.filter(
        groups__name='EC-Office', is_active=True).order_by('pk').first()
    with sudo(created_by):
        try:
            return create_dynamic_task(
                submission, task_type, stage2.cleaned_data['assign_to'], created_by,
                send_message_on_close=form.cleaned_data['send_message_on_close'],
                reminder_message_timeout=form.cleaned_data['reminder_message_timeout'])
        except ValidationError as e:
            raise ValueError(f'{node_uid}: {" ".join(e.messages)}') from None


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


def finish_vote_workflow(vote):
    """Do the vote's tasks (finalization, reviews, signing) until it is published."""
    run_workflow(vote)
    vote.refresh_from_db()
    if not vote.published_at:
        raise ValueError(f'vote {vote.pk} is unpublished; open tasks: '
                         f'{_node_uids(_open_tasks(vote))}')
    return vote


# --- Tasks ----------------------------------------------------------------
#
# A task is done the way its page does it: the page's form is saved, then the
# task is completed with a choice (``ecs.tasks.utils.TaskManagementData``).
# Most pages save nothing; those that do have a ``_save_*`` below.

DEFAULT = object()


def _save_categorization(task, user, fields):
    """The categorization form; board lane and the first medical category
    unless ``fields`` name others."""
    submission = task.data
    data = {
        'workflow_lane': submission.workflow_lane or SUBMISSION_LANE_BOARD,
        'medical_categories': list(submission.medical_categories.values_list('pk', flat=True)) or [
            MedicalCategory.objects.filter(is_disabled=False).order_by('name').values_list('pk', flat=True).first()],
        **fields,
    }
    form = CategorizationForm(data, instance=submission)
    if not form.is_valid():
        raise ValueError(f'invalid categorization: {form.errors.as_json()}')
    form.save()


def _save_checklist(task, user, fields):
    """The checklist of a checklist review, every question answered positively
    with a lorem comment (``core.views.submissions.checklist_review``)."""
    blueprint = task.node_controller.node.data
    owner = user if blueprint.multiple else get_user('root@system.local')
    checklist, created = Checklist.unfiltered.update_or_create(
        blueprint=blueprint, submission=task.data, user=owner, defaults={'last_edited_by': user})
    if created:
        for question in blueprint.questions.order_by('text'):
            checklist.answers.get_or_create(question=question)
    for answer in checklist.answers.select_related('question'):
        answer.answer = not answer.question.is_inverted
        answer.comment = LOREM
        answer.save()
    checklist.save()    # unlocks the review task


def _prepare_vote(task, user, fields):
    """The vote preparation form: a draft vote (result 1 unless named) on the
    current form (``core.views.submissions.vote_preparation``)."""
    submission = task.data
    vote = submission.current_pending_vote
    data = {'result': vote.result if vote else '1', 'text': vote.text if vote else LOREM, **fields}
    form = VotePreparationForm(data, instance=vote)
    if not form.is_valid():
        raise ValueError(f'invalid vote preparation: {form.errors.as_json()}')
    vote = form.save(commit=False)
    vote.submission_form = submission.current_submission_form
    vote.save()


def _save_vote_review(task, user, fields):
    """The vote review form, marked proofread and valid (executives also see
    the result, posted unchanged)."""
    vote = task.data
    data = {'result': vote.result, 'text': vote.text, 'is_final_version': True, **fields}
    form = VoteReviewForm(data, instance=vote)
    if not form.is_valid():
        raise ValueError(f'invalid vote review: {form.errors.as_json()}')
    form.save()


def _sign_vote(task, user, fields):
    """Store the signed vote PDF the way the PDF-AS callback does (``mock:``
    signing); completing the task then publishes the vote."""
    vote = task.data
    _receive_document(None, {
        'success_func': sign_success,
        'parent_pk': vote.pk,
        'parent_type': type(vote),
        'document_uuid': uuid.uuid4().hex,
        'document_type': 'votes',
        'document_version': 'signed-at',
        'document_filename': vote.pdf_filename,
    }, None, vote.render_pdf())


TASK_FORMS = (
    (Categorization, _save_categorization),
    (ChecklistReview, _save_checklist),
    (VotePreparation, _prepare_vote),
    (VoteReview, _save_vote_review),
    (VoteSigning, _sign_vote),
)


def _task_form(task):
    controller = task.node_controller
    return next((save for activity, save in TASK_FORMS if isinstance(controller, activity)), None)


def _open_tasks(data):
    return Task.objects.for_data(data).open().order_by('pk').select_related('task_type__workflow_node')


def _node_uids(tasks):
    return [t.task_type.workflow_node.uid for t in tasks]


def _doable(task):
    return _task_form(task) is not None or not task.is_locked


def _task_user(task):
    """Whoever the task is assigned to, else the first active member of its group."""
    user = task.assigned_to or User.objects.filter(
        groups=task.task_type.group, is_active=True).order_by('pk').first()
    if user is None:
        raise ValueError(f'nobody can do task {task.pk} ({task.task_type.workflow_node.uid})')
    return user


def do_task(data, node_uid=None, choice=DEFAULT, user=None, **fields):
    """Do one open task of ``data`` (a submission, vote, checklist ...) and return it.

    ``node_uid`` picks the task (default: the oldest one that can be done),
    ``choice`` defaults to the first one the page offers (the success path),
    ``user`` to the assignee or the first active member of the task's group.
    ``fields`` go into the page's form, e.g. ``workflow_lane=2`` for categorization.
    """
    tasks = _open_tasks(data)
    if node_uid:
        task = tasks.filter(task_type__workflow_node__uid=node_uid).first()
    else:
        task = next((t for t in tasks if _doable(t)), None)
    if task is None:
        raise ValueError(f'no {node_uid or "doable"} task on {data!r}; open: {_node_uids(tasks)}')
    user = user or _task_user(task)
    save = _task_form(task)
    if fields and save is None:
        raise ValueError(f'task {task.task_type.workflow_node.uid} has no form for {sorted(fields)}')
    with sudo(user):
        if save:
            save(task, user, fields)
        task = Task.unfiltered.get(pk=task.pk)     # refetch: saving the form may unlock it
        if task.is_locked:
            raise ValueError(f'task {task.pk} ({task.task_type.workflow_node.uid}) is locked')
        if choice is DEFAULT:
            choice = task.choices[0][0] if task.choices else None
        task.done(choice=choice, user=user)
    return task


def run_workflow(data, until=None, fields=None, max_steps=50):
    """Do the open tasks of ``data``, oldest first, until a task at node
    ``until`` is open, or (without ``until``) until none is left to do.

    ``fields`` maps a node uid to the fields of its form, e.g.
    ``{'categorization': {'workflow_lane': 2}}``. Returns the open tasks.
    """
    fields = fields or {}
    for _ in range(max_steps):
        tasks = list(_open_tasks(data))
        if until in _node_uids(tasks):
            return tasks
        task = next((t for t in tasks if _doable(t)), None)
        if task is None:
            if until:
                raise ValueError(f'{until} not reached on {data!r}; open: {_node_uids(tasks)}')
            return tasks
        uid = task.task_type.workflow_node.uid
        do_task(data, uid, **fields.get(uid, {}))
    raise ValueError(f'{data!r} still has tasks after {max_steps} steps')


def vote_in_meeting(submission, result, meeting=None, participants=()):
    """The common path in one call: schedule, start, vote, end, publish."""
    top = schedule(submission, meeting, participants=participants)
    start_meeting(top.meeting)
    vote = record_vote(top, result)
    end_meeting(top.meeting)
    return finish_vote_workflow(vote)
