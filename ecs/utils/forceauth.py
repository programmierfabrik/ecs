"""
Middleware that forces Authentication.
"""
from django.shortcuts import redirect
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin

def exempt(view):
    view._forceauth_exempt = True
    return view

class ForceAuth(MiddlewareMixin):
    def process_view(self, request, view, args, kwargs):
        if not getattr(view, '_forceauth_exempt', False) and request.user.is_anonymous:
            return redirect(settings.LOGIN_URL + '?next=%s' % request.path)

