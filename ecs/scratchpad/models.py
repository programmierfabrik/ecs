from django.db import models
from django.contrib.auth.models import User

from ecs.core.models.submissions import Submission


class ScratchPad(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)
    text = models.TextField(null=True, blank=True)
    owner = models.ForeignKey(User, on_delete=models.PROTECT)
    submission = models.ForeignKey(Submission, null=True, on_delete=models.PROTECT)

    class Meta:
        unique_together = (('owner', 'submission'),)

    def is_empty(self):
        return not self.text
