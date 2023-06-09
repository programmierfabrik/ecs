from django import forms
from django.utils.translation import gettext_lazy as _

from ecs.core.models.clinic import Clinic


class AdministrationFilterForm(forms.Form):
    activity = forms.ChoiceField(required=False, choices=(
        ('both', _('Both')),
        ('active', _('active')),
        ('inactive', _('inactive')),
    ), label=_('Activity'))
    keyword = forms.CharField(required=False, label="Krankenanstalt")
    page = forms.CharField(required=False, widget=forms.HiddenInput())


class ClinicForm(forms.ModelForm):
    class Meta:
        model = Clinic
        fields = ('name', 'email', 'deactivated')
        labels = {
            'name': 'Name',
            'deactivated': 'Deaktiviert',
        }
