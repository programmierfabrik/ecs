from django.contrib.sessions.exceptions import SessionInterrupted
from django.urls import include, path, re_path
from django.conf import settings
from django.shortcuts import redirect, render
from django.views.defaults import bad_request
from django.views.generic.base import RedirectView
from django.views.static import serve

from ecs.utils import forceauth

def handler500(request):
    ''' 500 error handler which includes ``request`` in the context '''
    return render(request, '500.html', status=500)


def handler400(request, exception=None):
    ''' 400 error handler. A SessionInterrupted (the session was deleted by
    a concurrent request, e.g. logging out and starting a new login within
    the same moment) isn't a real error - just bounce back to the login
    page instead of showing an error page. '''
    if isinstance(exception, SessionInterrupted):
        return redirect(settings.LOGIN_URL)
    return bad_request(request, exception)


urlpatterns = [
    # Default redirect is same as redirect from login if no redirect is set (/dashboard/)
    path('', RedirectView.as_view(url=settings.LOGIN_REDIRECT_URL, permanent=False)),

    path('', include('ecs.users.urls')),
    path('core/', include('ecs.core.urls')),
    path('docstash/', include('ecs.docstash.urls')),
    path('documents/', include('ecs.documents.urls')),
    path('checklist/', include('ecs.checklists.urls')),
    path('vote/', include('ecs.votes.urls')),
    path('dashboard/', include('ecs.dashboard.urls')),
    path('task/', include('ecs.tasks.urls')),
    path('communication/', include('ecs.communication.urls')),
    path('billing/', include('ecs.billing.urls')),
    path('boilerplate/', include('ecs.boilerplate.urls')),
    path('scratchpad/', include('ecs.scratchpad.urls')),
    path('meeting/', include('ecs.meetings.urls')),
    path('notification/', include('ecs.notifications.urls')),
    path('signature/', include('ecs.signature.urls')),
    path('statistics/', include('ecs.statistics.urls')),
    path('tags/', include('ecs.tags.urls')),
    path('', include('ecs.pki.urls')),
    path('i18n/', include('django.conf.urls.i18n')),
    re_path('static/(?P<path>.*)$', forceauth.exempt(serve), {'document_root': settings.STATIC_ROOT}),
    re_path(r'^(?P<path>favicon\.ico)$', serve, {'document_root': settings.STATIC_ROOT}),
]


# XXX: do not bind to settings.DEBUG, to test working sentry on DEBUG:False
if 'ecs.userswitcher' in settings.INSTALLED_APPS:
    from django.http import HttpResponse
    import logging

    logger = logging.getLogger(__name__)

    @forceauth.exempt
    def _trigger_log(request):
        logger.warn('debug test message')
        return HttpResponse()

    @forceauth.exempt
    def _403(request):
        return render(request, '403.html', status=403)

    @forceauth.exempt
    def _404(request):
        return render(request, '404.html', status=404)

    @forceauth.exempt
    def _500(request):
        return render(request, '500.html', status=500)

    urlpatterns += [
        path('debug/403/', _403),
        path('debug/404/', _404),
        path('debug/500/', _500),
        path('debug/trigger-log/', _trigger_log),
    ]

if 'ecs.userswitcher' in settings.INSTALLED_APPS:
    urlpatterns += [
        path('userswitcher/', include('ecs.userswitcher.urls')),
    ]

if 'rosetta' in settings.INSTALLED_APPS:
    urlpatterns += [
        path('rosetta/', include('rosetta.urls')),
    ]
