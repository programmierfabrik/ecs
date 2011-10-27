# -*- coding: utf-8 -*-

from django.db.models.signals import post_save
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _

from ecs.workflow import Activity, guard, register
from ecs.users.utils import get_current_user, sudo
from ecs.core.models import Submission
from ecs.core.signals import on_initial_review, on_categorization_review, on_thesis_recommendation_review
from ecs.checklists.models import ChecklistBlueprint, Checklist, ChecklistAnswer
from ecs.checklists.utils import get_checklist_answer
from ecs.tasks.models import Task
from ecs.communication.utils import send_system_message_template
from ecs.tasks.utils import block_if_task_exists

register(Submission, autostart_if=lambda s, created: bool(s.current_submission_form_id) and not s.workflow and not s.is_transient)

@guard(model=Submission)
def is_acknowledged(wf):
    return wf.data.newest_submission_form.is_acknowledged

@guard(model=Submission)
def is_initial_submission(wf):
    return wf.data.forms.filter(is_acknowledged=True).count() == 1

@guard(model=Submission)
def is_acknowledged_and_initial_submission(wf):
    return is_acknowledged(wf) and is_initial_submission(wf)

@guard(model=Submission)
def is_thesis(wf):
    return Submission.objects.thesis().filter(pk=wf.data.pk).exists() and not is_expedited(wf)

@guard(model=Submission)
def is_retrospective_thesis(wf):
    return Submission.objects.retrospective_thesis().filter(pk=wf.data.pk).exists() and not is_expedited(wf)

@guard(model=Submission)
def is_expedited(wf):
    return wf.data.is_expedited and wf.data.expedited_review_categories.exists()

@guard(model=Submission)
def is_localec(wf):
    return wf.data.current_submission_form.is_categorized_multicentric_and_local

@guard(model=Submission)
def is_expedited_or_retrospective_thesis(wf):
    return is_expedited(wf) or is_retrospective_thesis(wf)

@guard(model=Submission)
def is_acknowledged_and_localec(wf):
    # legacy: only for backwards compatibility
    return is_acknowledged(wf) and is_localec(wf)

@guard(model=Submission)
def is_acknowledged_and_not_localec(wf):
    # legacy: only for backwards compatibility
    return is_acknowledged(wf) and not is_localec(wf)

@guard(model=Submission)
def has_expedited_recommendation(wf):
    return bool(get_checklist_answer(wf.data, 'expedited_review', 1))

@guard(model=Submission)
def has_thesis_recommendation(wf):
    return bool(get_checklist_answer(wf.data, 'thesis_review', 1))

@guard(model=Submission)
@block_if_task_exists('insurance_review')
def needs_insurance_review(wf):
    return wf.data.insurance_review_required

@guard(model=Submission)
@block_if_task_exists('statistical_review')
def needs_statistical_review(wf):
    return wf.data.statistical_review_required

@guard(model=Submission)
@block_if_task_exists('legal_and_patient_review')
def needs_legal_and_patient_review(wf):
    return wf.data.legal_and_patient_review_required

@guard(model=Submission)
@block_if_task_exists('gcp_review')
def needs_gcp_review(wf):
    return wf.data.gcp_review_required

@guard(model=Submission)
@block_if_task_exists('paper_submission_review')
def needs_paper_submission_review(wf):
    return True

class InitialReview(Activity):
    class Meta:
        model = Submission

    def is_repeatable(self):
        return True

    def get_url(self):
        return reverse('ecs.core.views.initial_review', kwargs={'submission_pk': self.workflow.data_id})

    def get_choices(self):
        return (
            (True, _('Acknowledge')),
            (False, _('Reject')),
        )

    def pre_perform(self, choice):
        s = self.workflow.data
        sf = s.newest_submission_form
        sf.is_acknowledged = choice
        sf.save()
        on_initial_review.send(Submission, submission=s, form=sf)

class Resubmission(Activity):
    class Meta:
        model = Submission

    def get_url(self):
        return reverse('ecs.core.views.copy_latest_submission_form', kwargs={'submission_pk': self.workflow.data.pk})

    def get_final_urls(self):
        return super(Resubmission, self).get_final_urls() + [
            reverse('ecs.core.views.readonly_submission_form', kwargs={'submission_form_pk': sf})
            for sf in self.workflow.data.forms.values_list('pk', flat=True)
        ]

    def receive_token(self, *args, **kwargs):
        token = super(Resubmission, self).receive_token(*args, **kwargs)
        token.task.assign(self.workflow.data.current_submission_form.presenter)
        return token

class _CategorizationReviewBase(Activity):
    class Meta:
        model = Submission

    def is_repeatable(self):
        return True

    def get_url(self):
        return reverse('ecs.core.views.categorization_review', kwargs={'submission_form_pk': self.workflow.data.current_submission_form.pk})

    def pre_perform(self, choice):
        s = self.workflow.data
        # create external review checklists
        blueprint = ChecklistBlueprint.objects.get(slug='external_review')
        for user in s.external_reviewers.all():
            checklist, created = Checklist.objects.get_or_create(blueprint=blueprint, submission=s, user=user)
            if created:
                for question in blueprint.questions.order_by('text'):
                    ChecklistAnswer.objects.get_or_create(checklist=checklist, question=question)

        with sudo():
            expedited_recommendation_tasks = Task.objects.for_data(s).filter(
                deleted_at__isnull=True, closed_at=None, task_type__workflow_node__uid='expedited_recommendation')
            for task in expedited_recommendation_tasks:
                task.expedited_review_categories = s.expedited_review_categories.all()

class CategorizationReview(_CategorizationReviewBase):
    class Meta:
        model = Submission

    def pre_perform(self, choice):
        super(CategorizationReview, self).pre_perform(choice)
        on_categorization_review.send(Submission, submission=self.workflow.data)


class ThesisCategorizationReview(_CategorizationReviewBase):
    class Meta:
        model = Submission

    def pre_perform(self, choice):
        super(ThesisCategorizationReview, self).pre_perform(choice)
        # stub


class PaperSubmissionReview(Activity):
    class Meta:
        model = Submission

    def get_url(self):
        return reverse('ecs.core.views.paper_submission_review', kwargs={'submission_pk': self.workflow.data_id})


class ChecklistReview(Activity):
    class Meta:
        model = Submission
        vary_on = ChecklistBlueprint

    def is_repeatable(self):
        return True

    def is_reentrant(self):
        return True

    def is_locked(self):
        blueprint = self.node.data
        lookup_kwargs = {'blueprint': blueprint}
        if blueprint.multiple:
            lookup_kwargs['user'] = get_current_user()
        try:
            checklist = self.workflow.data.checklists.get(**lookup_kwargs)
        except Checklist.DoesNotExist:
            return True
        return not checklist.is_complete

    def get_url(self):
        blueprint = self.node.data
        submission_form = self.workflow.data.current_submission_form
        return reverse('ecs.core.views.checklist_review', kwargs={'submission_form_pk': submission_form.pk, 'blueprint_pk': blueprint.pk})

    def pre_perform(self, choice):
        blueprint = self.node.data
        lookup_kwargs = {'blueprint': blueprint}
        if blueprint.multiple:
            lookup_kwargs['user'] = get_current_user()
        try:
            checklist = self.workflow.data.checklists.get(**lookup_kwargs)
        except Checklist.DoesNotExist:
            pass
        else:
            checklist.status = 'completed'
            checklist.save()

def unlock_checklist_review(sender, **kwargs):
    kwargs['instance'].submission.workflow.unlock(ChecklistReview)
post_save.connect(unlock_checklist_review, sender=Checklist)

class NonRepeatableChecklistReview(ChecklistReview):
    def is_repeatable(self):
        return False

    def is_reentrant(self):
        return False

def unlock_non_repeatable_checklist_review(sender, **kwargs):
    kwargs['instance'].submission.workflow.unlock(NonRepeatableChecklistReview)
post_save.connect(unlock_non_repeatable_checklist_review, sender=Checklist)

class BoardMemberReview(ChecklistReview):
    def is_reentrant(self):
        return True

def unlock_boardmember_review(sender, **kwargs):
    kwargs['instance'].submission.workflow.unlock(BoardMemberReview)
post_save.connect(unlock_boardmember_review, sender=Checklist)


# XXX: This could be done without the additional signal handler if `ecs.workflow` properly supported activity inheritance. (FMD3)
class ThesisRecommendationReview(NonRepeatableChecklistReview):
    def is_reentrant(self):
        return True

    def pre_perform(self, choice):
        super(ThesisRecommendationReview, self).pre_perform(choice)
        on_thesis_recommendation_review.send(Submission, submission=self.workflow.data)

def unlock_thesis_recommendation_review(sender, **kwargs):
    kwargs['instance'].submission.workflow.unlock(ThesisRecommendationReview)
post_save.connect(unlock_thesis_recommendation_review, sender=Checklist)

class ExpeditedRecommendation(NonRepeatableChecklistReview):
    def receive_token(self, *args, **kwargs):
        token = super(ExpeditedRecommendation, self).receive_token(*args, **kwargs)
        s = self.workflow.data
        token.task.expedited_review_categories = s.expedited_review_categories.all()
        return token

def unlock_expedited_recommendation(sender, **kwargs):
    kwargs['instance'].submission.workflow.unlock(ExpeditedRecommendation)
post_save.connect(unlock_expedited_recommendation, sender=Checklist)

class ExpeditedRecommendationReview(NonRepeatableChecklistReview):
    def is_reentrant(self):
        return True

    def pre_perform(self, choice):
        super(ExpeditedRecommendationReview, self).pre_perform(choice)
        on_expedited_recommendation_review.send(Submission, submission=self.workflow.data)
            

def unlock_expedited_recommendation_review(sender, **kwargs):
    kwargs['instance'].submission.workflow.unlock(ExpeditedRecommendationReview)
post_save.connect(unlock_expedited_recommendation_review, sender=Checklist)


class LocalEcRecommendationReview(NonRepeatableChecklistReview):
    def is_reentrant(self):
        return True

    def pre_perform(self, choice):
        super(LocalEcRecommendationReview, self).pre_perform(choice)
        on_local_ec_recommendation_review.send(Submission, submission=self.workflow.data)

def unlock_localec_recommendation_review(sender, **kwargs):
    kwargs['instance'].submission.workflow.unlock(LocalEcRecommendationReview)
post_save.connect(unlock_localec_recommendation_review, sender=Checklist)
