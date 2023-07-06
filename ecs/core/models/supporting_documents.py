from django.db import models

from ecs.documents.models import Document
from ecs.tasks.models import TaskType


class SupportingDocument(models.Model):
    tasks = models.ManyToManyField(TaskType)
    document = models.ForeignKey(Document, on_delete=models.CASCADE)
