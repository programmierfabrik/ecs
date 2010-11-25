import os
from django.conf.urls.defaults import *
from django.conf import settings

urlpatterns = patterns('ecs.help.views',
    url(r'^$', 'index'),
    url(r'^page/(?P<page_pk>\d+)/$', 'view_help_page'),
    url(r'^page/new/$', 'edit_help_page'),
    url(r'^view/(?P<view_pk>\d+)/', 'find_help'),
    url(r'^view/(?P<view_pk>\d+)/(?P<anchor>[\w-]+)/$', 'find_help'),

    url(r'^edit/page/(?P<page_pk>\d+)/$', 'edit_help_page'),
    url(r'^edit/view/(?P<view_pk>\d+)/$', 'edit_help_page'),
    url(r'^edit/view/(?P<view_pk>\d+)/(?P<anchor>[\w-]+)/$', 'edit_help_page'),
    
    url(r'^preview/$', 'preview_help_page_text'),
    url(r'^attachments/$', 'attachments'),
    url(r'^attachments/upload/$', 'upload'),
    url(r'^attachments/find/$', 'find_attachments'),
    url(r'^attachment/(?P<attachment_pk>\d+)/download/$', 'download_attachment'),
    url(r'^attachment/(?P<attachment_pk>\d+)/delete/$', 'delete_attachment'),
)

