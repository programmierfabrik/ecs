from django.db import models


class Clinic(models.Model):
    name = models.TextField(blank=False, unique=True)
    deactivated = models.BooleanField(default=False)
    is_favorite = models.BooleanField(default=False)
