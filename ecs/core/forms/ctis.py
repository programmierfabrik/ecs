from django import forms

from ecs.core.ctis import CTIS_NUMBER_RE


class CTISNumberForm(forms.Form):
    ctis_number = forms.CharField(
        label='CTIS-Nummer',
        max_length=17,
        help_text='Format: JJJJ-NNNNNN-CC-SS (z. B. 2026-503364-87-00)',
        widget=forms.TextInput(attrs={
            'placeholder': 'JJJJ-NNNNNN-CC-SS',
            'maxlength': 17,
            'inputmode': 'numeric',
            'autocomplete': 'off',
            'pattern': r'\d{4}-\d{6}-\d{2}-\d{2}',
            'title': 'Format: JJJJ-NNNNNN-CC-SS',
        }),
    )

    def clean_ctis_number(self):
        value = self.cleaned_data['ctis_number'].strip()
        if not CTIS_NUMBER_RE.match(value):
            raise forms.ValidationError(
                'Ungültiges CTIS-Nummer-Format. Erwartet wird JJJJ-NNNNNN-CC-SS.')
        return value
