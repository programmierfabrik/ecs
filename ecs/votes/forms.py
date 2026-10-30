import reversion
from django import forms
from django.utils.translation import gettext_lazy as _

from ecs.core.forms.utils import ReadonlyFormMixin
from ecs.votes.models import Vote
from ecs.votes.constants import (VOTE_PREPARATION_CHOICES,
    B2_VOTE_PREPARATION_CHOICES, CLASSIC_VOTE_RESULT_CHOICES,
    CTIS_VOTE_RESULT_CHOICES)
from ecs.users.utils import get_current_user
from ecs.core.forms.utils import mark_readonly

def ResultField(**kwargs):
    return Vote._meta.get_field('result').formfield(widget=forms.RadioSelect(), **kwargs)


def restrict_result_choices(field, submission):
    """Offer only the results that make sense for this kind of study.

    A CTIS study is only ever given a « BCTIS Stellungnahme », a classic
    study never is. Whatever empty choice the field already carries is kept.
    """
    if submission is not None and submission.uses_ctr_form:
        allowed = CTIS_VOTE_RESULT_CHOICES
    else:
        allowed = CLASSIC_VOTE_RESULT_CHOICES
    allowed = [value for value, label in allowed]
    field.choices = [(value, label) for value, label in field.choices
        if not value or value in allowed]

class SaveVoteForm(forms.ModelForm):
    result = ResultField(required=False)
    close_top = forms.BooleanField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Vote
        fields = ('result', 'text')

    def __init__(self, *args, submission, **kwargs):
        super().__init__(*args, **kwargs)
        restrict_result_choices(self.fields['result'], submission)

    def save(self, top, *args, **kwargs):
        kwargs['commit'] = False
        instance = super().save(*args, **kwargs)
        for key, value in top.submission.current_form_kwargs().items():
            setattr(instance, key, value)
        instance.top = top
        instance.save()
        return instance

class VoteForm(SaveVoteForm):
    result = ResultField(required=True)

    def __init__(self, *args, **kwargs):
        self.readonly = kwargs.pop('readonly', False)
        super().__init__(*args, **kwargs)
        if self.readonly:
            mark_readonly(self)

class VoteReviewForm(ReadonlyFormMixin, forms.ModelForm):
    class Meta:
        model = Vote
        fields = ('text', 'is_final_version')
        labels = {
            'is_final_version': _('Proofread and valid'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        user = get_current_user()
        if not self.readonly and user.profile.is_executive:
            result = Vote._meta.get_field('result').formfield(
                initial=self.instance.result)
            restrict_result_choices(result,
                self.instance.submission if self.instance.submission_id else None)
            self.fields['result'] = result

            # reorder fields
            self.fields['text'] = self.fields.pop('text')
            self.fields['is_final_version'] = self.fields.pop('is_final_version')

    def clean(self):
        cleaned_data = super().clean()
        if 'result' in self.fields:
            original_result = self.instance.result
            result = cleaned_data['result']
            if not result == original_result and 'is_final_version' in cleaned_data:
                del cleaned_data['is_final_version']
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if 'result' in self.fields:
            original_result = instance.result
            instance.result = self.cleaned_data['result']
            if not instance.result == original_result:
                instance.is_final_version = False
                instance.changed_after_voting = True
        if commit:
            with reversion.create_revision():
                reversion.set_user(get_current_user())
                instance.save()


class VotePreparationForm(forms.ModelForm):
    result = Vote._meta.get_field('result').formfield(
        choices=VOTE_PREPARATION_CHOICES)

    class Meta:
        model = Vote
        fields = ('result', 'text')

    def save(self, commit=True):
        vote = super().save(commit=False)
        vote.is_draft = True
        if commit:
            vote.save()
        return vote


class B2VotePreparationForm(forms.ModelForm):
    result = Vote._meta.get_field('result').formfield(
        choices=B2_VOTE_PREPARATION_CHOICES)
    
    class Meta:
        model = Vote
        fields = ('result', 'text')
