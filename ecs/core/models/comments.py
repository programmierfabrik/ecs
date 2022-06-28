from django.db import models


class Comment(models.Model):
    submission = models.ForeignKey('core.Submission', on_delete=models.CASCADE)
    author = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now=True)
    text = models.TextField()
    attachment = models.ForeignKey('documents.Document', null=True, on_delete=models.CASCADE)
