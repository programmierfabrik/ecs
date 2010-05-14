# -*- coding: utf-8 -*-
from django import forms
from django.contrib.auth.models import User

class DelegateTaskForm(forms.Form):
    user = forms.ModelChoiceField(User.objects.all())
    message = forms.CharField(required=False)
    
class DeclineTaskForm(forms.Form):
    message = forms.CharField(required=False)
    

TASK_MANAGEMENT_CHOICES = ('delegate', 'message', 'complete')
TASK_QUESTION_TYPE = ('callback', 'somebody')

class CallbackTaskChoiceField(forms.ModelChoiceField):
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
        super(ManageTaskForm, self).__init__(*args, **kwargs)
        self.fields['callback_task'] = CallbackTaskChoiceField(queryset=task.trail, required=False)
    
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

        return self.cleaned_data