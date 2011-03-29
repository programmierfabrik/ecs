# -*- coding: utf-8 -*-
import datetime
from uuid import uuid4

from django.db import models
from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django_extensions.db.fields.json import JSONField
from django.utils.translation import ugettext_lazy as _


class UserProfile(models.Model):
    user = models.OneToOneField(User, related_name='ecs_profile')
    last_password_change = models.DateTimeField(default=datetime.datetime.now)
    phantom = models.BooleanField(default=False)
    approved_by_office = models.BooleanField(default=False)
    indisposed = models.BooleanField(default=False)

    external_review = models.BooleanField(default=False)
    board_member = models.BooleanField(default=False)
    executive_board_member = models.BooleanField(default=False)
    thesis_review = models.BooleanField(default=False)
    insurance_review = models.BooleanField(default=False)
    expedited_review = models.BooleanField(default=False)
    internal = models.BooleanField(default=False)
    help_writer = models.BooleanField(default=False)

    session_key = models.CharField(max_length=40, null=True)
    single_login_enforced = models.BooleanField(default=False)
    
    gender = models.CharField(max_length=1, choices=(('f', _(u'Ms')), ('m', _(u'Mr'))))
    title = models.CharField(max_length=30, blank=True)
    organisation = models.CharField(max_length=180, blank=True)
    jobtitle = models.CharField(max_length=130, blank=True)
    swift_bic = models.CharField(max_length=11, blank=True)
    iban = models.CharField(max_length=40, blank=True)
    
    address1 = models.CharField(max_length=60, blank=True)
    address2 = models.CharField(max_length=60, blank=True)
    zip_code = models.CharField(max_length=10, blank=True)
    city = models.CharField(max_length=80, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    fax = models.CharField(max_length=45, blank=True)
    
    social_security_number = models.CharField(max_length=10, blank=True)

    # 0 = never send messages
    forward_messages_after_minutes = models.PositiveIntegerField(null=False, blank=False, default=0)
    
    def __unicode__(self):
        return unicode(self.user)

    def get_single_login_enforced(self):
        if self.single_login_enforced:
            self.single_login_enforced = False
            self.save()
            return True
        else:
            return False

    def has_explicit_workflow(self):
        return self.user.groups.exclude(name__in=[u'Presenter', u'Sponsor', u'Investigator', u'External Reviewer', u'userswitcher_target']).count() > 0
    
class UserSettings(models.Model):
    user = models.OneToOneField(User, related_name='ecs_settings')
    submission_filter_all = JSONField()
    submission_filter_widget = JSONField()
    submission_filter_widget_internal = JSONField()
    submission_filter_mine = JSONField()
    submission_filter_assigned = JSONField()
    task_filter = JSONField()
    communication_filter = JSONField()
    useradministration_filter = JSONField()
    pdfviewer_settings = JSONField()

def _post_user_save(sender, **kwargs):
    # XXX: 'raw' is passed during fixture loading, but that's an undocumented feature - see django bug #13299 (FMD1)
    if kwargs['created'] and not kwargs.get('raw'):
        UserProfile.objects.create(user=kwargs['instance'])
        UserSettings.objects.create(user=kwargs['instance'])
    
post_save.connect(_post_user_save, sender=User)


class InvitationQuerySet(models.query.QuerySet):
    def new(self):
        return self.filter(accepted=False)

class InvitationManager(models.Manager):
    def get_query_set(self):
        return InvitationQuerySet(self.model).distinct()
    
    def new(self):
        return self.all().new()

class Invitation(models.Model):
    user = models.ForeignKey(User, related_name='ecs_invitations')
    uuid = models.CharField(max_length=32, default=lambda: uuid4().get_hex(), unique=True)
    accepted = models.BooleanField(default=False)

    objects = InvitationManager()


