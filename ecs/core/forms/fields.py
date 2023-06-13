import datetime

from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.translation import gettext as _

from ecs.users.utils import get_user

DATE_INPUT_FORMATS = ("%d.%m.%Y", "%Y-%m-%d")
TIME_INPUT_FORMATS = ("%H:%M", "%H:%M:%S")


class LooseTimeWidget(forms.TextInput):
    def _format_value(self, value):
        if isinstance(value, datetime.time):
            return value.strftime('%H:%M')
        return value


class DateField(forms.DateField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('input_formats', DATE_INPUT_FORMATS)
        kwargs.setdefault('error_messages', {'invalid': _('Please enter a date in the format dd.mm.yyyy.')})
        super().__init__(*args, **kwargs)


class DateTimeField(forms.SplitDateTimeField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('input_date_formats', DATE_INPUT_FORMATS)
        kwargs.setdefault('input_time_formats', TIME_INPUT_FORMATS)
        kwargs.setdefault('widget', forms.SplitDateTimeWidget(date_format=DATE_INPUT_FORMATS[0]))
        kwargs.setdefault('error_messages',
                          {'invalid': _('Please enter a date in dd.mm.yyyy format and time in format HH:MM.')})
        super().__init__(*args, **kwargs)


class TimeField(forms.TimeField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('error_messages', {'invalid': _('Please enter a time in the format HH: MM.')})
        kwargs.setdefault('widget', LooseTimeWidget())
        super().__init__(*args, **kwargs)


class NullBooleanWidget(forms.widgets.NullBooleanSelect):
    def __init__(self, attrs=None):
        choices = (('unknown', '-'), ('true', _('Yes')), ('false', _('No')))
        forms.widgets.Select.__init__(self, attrs, choices)


class NullBooleanField(forms.NullBooleanField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', NullBooleanWidget)
        super().__init__(*args, **kwargs)


class NullBooleanWidgetNewMedtechLaw(forms.widgets.NullBooleanSelect):
    def __init__(self, attrs=None):
        choices = (('unknown', '-'), ('true', 'Ja - nach neuem Gesetz'), ('false', 'Nein - nach altem Gesetz'))
        forms.widgets.Select.__init__(self, attrs, choices)


class NullBooleanFieldNewMedtechLaw(forms.NullBooleanField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', NullBooleanWidgetNewMedtechLaw)
        super().__init__(*args, **kwargs)


class AutocompleteModelChoiceField(forms.ChoiceField):
    def __init__(self, queryset_name, queryset, **kwargs):
        kwargs['widget'] = self.Widget(self)
        self.queryset_name = queryset_name
        self.queryset = queryset
        super().__init__(**kwargs)

    def clean(self, value):
        if value is None or value == '':
            if self.required:
                raise ValidationError('Das Feld darf nicht leer sein!')
            return None
        value = super().clean(value)
        return User.objects.get(id=value)

    def valid_value(self, value):
        """Check to see if the provided value is a valid choice."""
        if not self.required:
            return True

        first = self.queryset.all().filter(pk=value).first()
        return first is not None

    class Widget(forms.Select):
        def __init__(self, field):
            self.field = field
            super().__init__()

        def render(self, name, value, attrs=None, renderer=None):
            attrs['data-ajax--url'] = reverse(
                'core.autocomplete',
                kwargs={'queryset_name': self.field.queryset_name}
            )

            try:
                if value:
                    user = User.objects.get(pk=value)
                    self.choices = [(user.pk, '{} [{}]'.format(user, user.email))]
            except User.DoesNotExist:
                pass

            return super().render(name, value, attrs=attrs)


class StrippedTextInput(forms.TextInput):
    def value_from_datadict(self, *args, **kwargs):
        v = super().value_from_datadict(*args, **kwargs)
        if v is not None:
            v = v.strip()
        return v


class EmailUserSelectWidget(forms.TextInput):
    def render(self, name, value, attrs=None, renderer=None):
        if value is None:
            value = ''
        else:
            value = User.objects.get(pk=value).email
        return super().render(name, value, attrs=attrs)

    def value_from_datadict(self, data, files, name):
        val = data.get(name, '')
        if not val:
            return None
        try:
            return get_user(val.strip()).pk
        except User.DoesNotExist:
            return None
