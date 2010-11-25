from django import forms
from ecs.help.models import Page, Attachment

class HelpPageForm(forms.ModelForm):
    class Meta:
        model = Page
        
class AttachmentUploadForm(forms.ModelForm):
    slug = forms.CharField(required=False)

    class Meta:
        model = Attachment
        fields = ('file', 'slug',)