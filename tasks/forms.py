# -*- coding: utf-8 -*-
from django import forms
from django.contrib.auth.models import User

class DelegateTaskForm(forms.Form):
    user = forms.ModelChoiceField(User.objects.all())
    message = forms.CharField(required=False)
    
class DeclineTaskForm(forms.Form):
    message = forms.CharField(required=False)
    

TASK_MANAGEMENT_CHOICES = ('delegate', 'message',)
TASK_QUESTION_TYPE = ('callback', 'somebody', 'related', )

class TaskChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, task):
        return u"%s (%s)" % (task.assigned_to, task)

class ManageTaskForm(forms.Form):
    action = forms.ChoiceField(choices=zip(TASK_MANAGEMENT_CHOICES, TASK_MANAGEMENT_CHOICES))
    question_type = forms.ChoiceField(required=False, choices=zip(TASK_QUESTION_TYPE, TASK_QUESTION_TYPE))
    assign_to = forms.ModelChoiceField(queryset=User.objects.all(), required=False, empty_label='<Gruppe>')
    question = forms.CharField(required=False, widget=forms.Textarea())
    receiver = forms.ModelChoiceField(queryset=User.objects.all(), required=False)
    
    def __init__(self, *args, **kwargs):
        task = kwargs.pop('task')
        self.task = task
        super(ManageTaskForm, self).__init__(*args, **kwargs)
        self.fields['callback_task'] = TaskChoiceField(queryset=task.trail, required=False)
        self.fields['related_task'] = TaskChoiceField(queryset=task.related_tasks.exclude(assigned_to=None).exclude(pk=task.pk), required=False)
        self.fields['assign_to'].queryset = User.objects.filter(groups__task_types=task.task_type)
        if task.choices:
            self.fields['action'].choices += [('complete_%s' % i, choice[i]) for i, choice in enumerate(task.choices)]
        else:
            self.fields['action'].choices += [('complete', 'complete')]
        
    def get_choice(self):
        if not hasattr(self, 'choice_index'):
            return None
        return self.task.choices[self.choice_index][0]
        
    def clean_action(self):
        action = self.cleaned_data.get('action')
        if action.startswith('complete'):
            try:
                self.choice_index = int(action.split('_')[1])
                action = 'complete'
            except (ValueError, IndexError):
                pass
        return action
    
    def clean(self):
        cd = self.cleaned_data
        action = cd.get('action')
        if action == 'delegate':
            if 'assign_to' not in cd:
                self._errors['assign_to'] = self.error_class([u'Sie müssen einen Benutzer auswählen.'])
        elif action == 'message':
            question_type = cd.get('question_type')
            if question_type == 'callback':
                if not cd.get('callback_task'):
                    self._errors['callback_task'] = self.error_class([u'Sie müssen einen Benutzer auswählen.'])
            elif question_type == 'somebody':
                if not cd.get('receiver'):
                    self._errors['receiver'] = self.error_class([u'Sie müssen einen Benutzer auswählen.'])
            elif question_type == 'related':
                if not cd.get('related_task'):
                    self._errors['related_task'] = self.error_class([u'Sie müssen einen Benutzer auswählen.'])
            elif not question_type:
                self._errors['question_type'] = self.error_class([u'Sie müssen einen Adressaten auswählen'])

        return cd

class TaskListFilterForm(forms.Form):
    amg = forms.BooleanField(required=False)
    mpg = forms.BooleanField(required=False)
    other = forms.BooleanField(required=False)

    mine = forms.BooleanField(required=False)
    open = forms.BooleanField(required=False)
    proxy = forms.BooleanField(required=False)
