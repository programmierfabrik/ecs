from django import forms
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.utils.translation import gettext_lazy as _

from ecs.documents.models import Document, DocumentType
from ecs.utils.pdfutils import decrypt_pdf

PDF_MAGIC = b'%PDF'


class DocumentForm(forms.ModelForm):
    """
    This form caters two functionalities:
    1. Insert a new Document: 
        For this operation, the 'file', 'doctype', 'name', 'version' and 'date' are required. The 'file' can be replaced by another document.
    2. Update existing Document:
        In this operation, a field 'update_id' is used to get the existing document. 
        Only 'Name', 'version' and 'date' are required. Other fields are used from the existing document. 
    """
    file = forms.FileField(required=False)
    doctype = forms.ModelChoiceField(queryset=DocumentType.objects.exclude(is_hidden=True).order_by('identifier'),
                                     required=False)
    # required for both save and update operations
    date = forms.DateField(required=True)
    # If this is provided, then it means it is an update operation
    update_id = forms.IntegerField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Document
        fields = ('file', 'name', 'doctype', 'version', 'date', 'replaces_document')
        widgets = {'date': forms.DateInput(), 'replaces_document': forms.HiddenInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = getattr(self, 'instance', None)
        if self.data:
            prefix_update_id = "%s-%s" % (self.prefix, 'update_id') if self.prefix else 'update_id'
            if prefix_update_id in self.data and self.data[prefix_update_id]:
                self.fields['file'].widget.attrs['disabled'] = True
                self.fields['doctype'].widget.attrs['disabled'] = True
    

    def clean(self):
        """
        Checks if this is an update operation or a save operation and handles accordingly.
        """
        cd = super().clean()

        replaced_document = cd.get('replaces_document')
        if replaced_document:
            cd['doctype'] = replaced_document.doctype

            # if it's not an update operation
        if cd.get('update_id') is None:
            self.validate_file()
            file = cd.get('file')
            # 'doctype' is required if 'file' is present
            if file and not cd.get('doctype'):
                raise ValidationError(_('doctype is required when uploading a file.'))

        return cd

    def save(self, commit=True):
        """
        If 'update_id' is given then update the document, else save a new document.
        """
        update_id = self.cleaned_data.get('update_id')
        # if it's an update operation
        if update_id is not None:
            # get the existing instance
            instance = Document.objects.get(pk=update_id)
            # update only specific fields
            instance.name = self.cleaned_data.get('name')
            instance.version = self.cleaned_data.get('version')
            instance.date = self.cleaned_data.get('date')

            if commit:
                instance.save(update_fields=('name', 'version', 'date',))

        else:  # if it's not an update operation and a file is uploaded
            instance = super().save(commit=False)
            instance.original_file_name = self.cleaned_data.get('original_file_name')

            if commit:
                instance.save()  # save the document
                file = self.files.get('document-file')
                file.seek(0)
                instance.store(file)  # replace the old file

        return instance

    def validate_file(self):
        """
        Cleans the 'file', checks if it is a PDF document and validates it.
        """
        if self.cleaned_data.get('update_id') is not None:
            raise ValidationError(_('illegal file'))

        pdf = self.cleaned_data['file']
        if not pdf:
            raise ValidationError(_('no file'))

        # pdf magic check
        if pdf.read(4) != PDF_MAGIC:
            raise ValidationError(_('This file is not a PDF document.'))
        pdf.seek(0)

        # sanitization
        try:
            f = decrypt_pdf(pdf)
        except:
            raise ValidationError(
                _('The PDF-File seems to broken. For more Information click on the question mark in the sidebar.'))

        return UploadedFile(f, content_type='application/pdf', name='upload.pdf')
