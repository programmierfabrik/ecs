from django import forms

from ecs.core.ctis import CTIS_NUMBER_RE


class CTISNumberForm(forms.Form):
    ctis_number = forms.CharField(
        label='CTIS-Nummer',
        max_length=16,
        help_text='Format: JJJJ-NNNNNN-XX-Y (z. B. 2024-123456-00-1)',
        widget=forms.TextInput(attrs={
            'placeholder': 'JJJJ-NNNNNN-XX-Y',
            'maxlength': 16,
            'inputmode': 'numeric',
            'autocomplete': 'off',
            'pattern': r'\d{4}-\d{6}-\d{2}-\d',
            'title': 'Format: JJJJ-NNNNNN-XX-Y',
        }),
    )

    def clean_ctis_number(self):
        value = self.cleaned_data['ctis_number'].strip()
        if not CTIS_NUMBER_RE.match(value):
            raise forms.ValidationError(
                'Ungültiges CTIS-Nummer-Format. Erwartet wird JJJJ-NNNNNN-XX-Y.')
        return value
