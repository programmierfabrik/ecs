from django import forms
from django.utils.translation import gettext_lazy as _


class AdministrationFilterForm(forms.Form):
    activity = forms.ChoiceField(required=False, choices=(
        ('both', _('Both')),
        ('active', _('active')),
        ('inactive', _('inactive')),
    ), label=_('Activity'))
    keyword = forms.CharField(required=False, label="Klinik")
    page = forms.CharField(required=False, widget=forms.HiddenInput())
