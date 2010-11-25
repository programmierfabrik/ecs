import os
import mimetypes

from django.db import models
from django.conf import settings
from django.template.defaultfilters import slugify
from django.core.files.storage import FileSystemStorage
from django.utils.encoding import smart_str
from django.core.urlresolvers import reverse

from ecs.utils import cached_property
from ecs.tracking.models import View
from ecs.help.utils import publish_parts


class Page(models.Model):
    view = models.ForeignKey(View, null=True, blank=True)
    anchor = models.CharField(max_length=100, blank=True)
    slug = models.CharField(max_length=100, blank=True)
    title = models.CharField(max_length=150)
    text = models.TextField()
    
    class Meta:
        unique_together = ('view', 'anchor')
        
    def __unicode__(self):
        return self.title

    @cached_property
    def publish_parts(self):
        return publish_parts(self.text)


class AttachmentFileStorage(FileSystemStorage):
    def path(self, name):
        # We need to overwrite the default behavior, because django won't let us save documents outside of MEDIA_ROOT
        return smart_str(os.path.normpath(name))

    
class Attachment(models.Model):
    file = models.FileField(upload_to=os.path.join(settings.ECSHELP_ROOT, 'images'), storage=AttachmentFileStorage())
    mimetype = models.CharField(max_length=100)
    screenshot = models.BooleanField(default=False)
    slug = models.CharField(max_length=100, blank=True)
    view = models.ForeignKey(View, null=True, blank=True)
    page = models.ForeignKey(Page, null=True, blank=True)
    
    def save(self, **kwargs):
        if not self.mimetype:
            mimetype, encoding = mimetypes.guess_type(self.file.name)
            self.mimetype = mimetype
        if not self.slug:
            name, ext = os.path.splitext(self.file.name)
            self.slug = slugify(name) + ext
        return super(Attachment, self).save(**kwargs)
        
    