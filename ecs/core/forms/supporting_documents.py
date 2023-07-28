from django import forms
from django.utils.translation import gettext_lazy as _

from ecs.core.models.supporting_documents import SupportingDocument
from ecs.documents.models import Document
from ecs.tasks.models import TaskType


class TaskTypeMultipleChoiceField(forms.ModelMultipleChoiceField):
    def __init__(self, *args, **kwargs):
        queryset = TaskType.objects.filter(
            name__in=TaskType.objects.values('name').distinct()
        ).order_by('name', '-pk').distinct('name')

        kwargs.setdefault('queryset', queryset)
        kwargs.setdefault('required', False)
        kwargs.setdefault('label', _('Task Type'))

        super().__init__(*args, **kwargs)


class SupportingDocumentsAdministrationFilterForm(forms.Form):
    tasks = TaskTypeMultipleChoiceField()
    filename = forms.CharField(required=False, label="Dateiname")
    page = forms.CharField(required=False, widget=forms.HiddenInput())


class SupportingDocumentsForm(forms.ModelForm):
    tasks = TaskTypeMultipleChoiceField()
    file = forms.FileField()

    def __init__(self, *args, **kwargs):
        replace = kwargs.pop('replace', False)
        super().__init__(*args, **kwargs)
        if replace:
            self.fields['file'].required = False

    def save(self, commit=True):
        instance = super().save(commit=False)
        file = self.cleaned_data['file']
        instance.document = Document.objects.create_from_buffer(
            file.read(), doctype='supporting_documents',
            stamp_on_download=False, mimetype=file.content_type, name=file.name
        )
        if commit:
            instance.save()
            self.save_m2m()
        return instance

    class Meta:
        model = SupportingDocument
        fields = ('tasks',)
