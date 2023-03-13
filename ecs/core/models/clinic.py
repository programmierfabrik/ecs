from django.db import models


class Clinic(models.Model):
    name = models.TextField(blank=False, unique=True)
    email = models.EmailField(blank=False)
    deactivated = models.BooleanField(default=False)
    is_favorite = models.BooleanField(default=False)

    def __str__(self):
        return self.name
