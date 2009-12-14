from django.conf.urls.defaults import *
from django.conf import settings

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

from ecs.mockup.models import Mockup

urlpatterns = patterns('',
    # Example:
    # (r'^mockup/', include('mockup.urls')),
    ('^(.*)\.html$', 'ecs.mockup.views.mockup'),
    ('^feedback/summary/([^/]+)/([^/]+)', 'ecs.feedback.views.feedback_summary',
        {"model" : Mockup, }),

    # Uncomment the admin/doc line below and add 'django.contrib.admindocs' 
    # to INSTALLED_APPS to enable admin documentation:
    # (r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    (r'^admin/', include(admin.site.urls)),
    (r'^media/(.*)', 'django.views.static.serve',
        { 'document_root' : settings.MEDIA_ROOT })
)
