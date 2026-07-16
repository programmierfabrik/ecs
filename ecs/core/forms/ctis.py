from django import forms

from ecs.core.ctis import CTIS_NUMBER_RE


class CTISNumberForm(forms.Form):
    ctis_number = forms.CharField(
        label='CTIS-Nummer',
        max_length=20,
        help_text='Format: JJJJ-NNNNNN-XX-Y (z. B. 2024-123456-00-1)',
    )

    def clean_ctis_number(self):
        value = self.cleaned_data['ctis_number'].strip()
        if not CTIS_NUMBER_RE.match(value):
            raise forms.ValidationError(
                'Ungültiges CTIS-Nummer-Format. Erwartet wird JJJJ-NNNNNN-XX-Y.')
        return value
