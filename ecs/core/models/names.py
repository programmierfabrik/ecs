from django.db import models
from django.utils.translation import gettext_lazy as _


class Name(object):
    def __init__(self, **kwargs):
        for key, val in kwargs.items():
            setattr(self, key, val)

    @property
    def salutation(self):
        if not self.gender:
            return ''
        if self.gender == 'f':
            return 'Frau'
        if self.gender == 'm':
            return 'Herr'
        return ''

    @property
    def full_name(self):
        return " ".join(
            bit for bit in [self.salutation, self.title, self.first_name, self.last_name, self.suffix_title] if
            bit
        ).strip()

    def __str__(self):
        return self.full_name


class NameField(object):
    def __init__(self, required=None):
        self.required = required or []
        return super().__init__()

    def __get__(self, obj, obj_type=None):
        if not obj:
            return self
        return Name(**dict((field, getattr(obj, '%s_%s' % (self.name, field))) for field in
                           ('gender', 'title', 'first_name', 'last_name', 'suffix_title')))

    def contribute_to_class(self, cls, name):
        self.name = name

        flist = (
            ('gender', models.CharField, {'max_length': 1, 'choices': (('f', _('Ms')), ('m', _('Mr')), ('d', _('Divers'))), 'null': True}),
            ('title', models.CharField, {'max_length': 30}),
            ('suffix_title', models.CharField, {'max_length': 30}),
            ('first_name', models.CharField, {'max_length': 30}),
            ('last_name', models.CharField, {'max_length': 30}),
        )

        for fname, fcls, fkwargs in flist:
            fkwargs['blank'] = not fname in self.required
            fcls(**fkwargs).contribute_to_class(cls, '{0}_{1}'.format(name, fname))

        setattr(cls, name, self)
