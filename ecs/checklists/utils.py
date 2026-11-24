from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

from ecs.checklists.models import Checklist, ChecklistBlueprint, ChecklistAnswer
from ecs.tasks.models import Task
from ecs.users.utils import get_current_user

def get_checklist_answer_instance(submission, blueprint_slug, number):
    blueprint = ChecklistBlueprint.objects.get(slug=blueprint_slug)
    q = ChecklistAnswer.objects.filter(
        checklist__submission=submission, 
        question__blueprint__pk=blueprint.pk,
        question__number=str(number)
    )
    if blueprint.multiple:
        q.filter(checklist__user=get_current_user())
    return q.get()

def get_checklist_answer(submission, blueprint_slug, number):
    return get_checklist_answer_instance(submission, blueprint_slug, number).answer


def create_dynamic_task(submission, task_type, assign_to, created_by,
                        send_message_on_close=False, reminder_message_timeout=None):
    """Create a task the office adds by hand (specialist, statistical,
    external review ...) and return it.

    An external review gets its checklist (or a returned one is reopened); a
    specialist review takes part in the study's TOP on an unstarted meeting.
    Raises ``ValidationError`` when the task already exists.
    """
    tasks = Task.unfiltered.for_submission(submission).open().filter(
        task_type__name=task_type.name)
    if not task_type.is_delegatable:
        tasks = tasks.filter(assigned_to=assign_to)
    if tasks.exists():
        raise ValidationError(_('This task does already exist'))

    if task_type.workflow_node.uid == 'external_review':
        blueprint = ChecklistBlueprint.objects.get(slug='external_review')
        checklist, checklist_created = Checklist.objects.get_or_create(
            blueprint=blueprint, submission=submission, user=assign_to,
            defaults={'last_edited_by': assign_to})

        if checklist_created:
            for question in blueprint.questions.order_by('text'):
                checklist.answers.get_or_create(question=question)

            task = Task.unfiltered.for_data(checklist).open().filter(
                task_type=task_type).get()
        else:
            review_task = Task.unfiltered.for_data(checklist).filter(
                task_type__workflow_node__uid='external_review_review'
            ).open().first()
            if review_task:
                raise ValidationError(_('There is an external review review in progress'))

            checklist.status = 'new'
            checklist.save()

            task = Task.unfiltered.for_data(checklist).filter(
                task_type__workflow_node__uid='external_review'
            ).first().reopen()
            task.accepted = False

    else:
        token = task_type.workflow_node.bind(
            submission.workflow.workflows[0]).receive_token(None)
        token.task.assign(user=assign_to)
        task = token.task

        if task_type.workflow_node.uid == 'specialist_review':
            entry = submission.timetable_entries.filter(
                meeting__started=None).first()
            if entry:
                entry.participations.create(user=assign_to, task=task)

    task.created_by = created_by
    task.send_message_on_close = send_message_on_close
    task.reminder_message_timeout = reminder_message_timeout
    task.save()
    return task
