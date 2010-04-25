from django.db import models
from django.contrib.auth.models import User

# Create your models here.

import reversion
from reversion.models import Version


class Feedback(models.Model):
    FEEDBACK_TYPES=(('i', 'Idea'),('q','Question'),('p', 'Problem'),('l','Praise'))
    feedbacktype = models.CharField(choices=FEEDBACK_TYPES, max_length=1)
    summary = models.CharField(max_length=200) 
    description = models.TextField()
    origin = models.CharField(max_length=200)
    user = models.ForeignKey(User, related_name='author', null=True)
    pub_date = models.DateTimeField('date published')
    me_too_votes = models.ManyToManyField(User)

import reversion

# disabled for now, because i dont know if we currently need reversion for feedback model
#if not reversion.is_registered(Feedback):
#    reversion.register(Feedback)
