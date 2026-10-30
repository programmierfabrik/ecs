from django.conf import settings

from ecs.users.oidc_views import SSO_ERROR_FLAG

def ecs_settings(request):
    # Templates are also rendered with synthetic HttpRequest() objects (e.g.
    # invitation emails, diff documents), which carry no session.
    session = getattr(request, 'session', None)
    return {
        'debug': settings.DEBUG,
        'keycloak_sso_enabled': settings.ECS_KEYCLOAK_ENABLED,
        # Popped (not just read): shown/consumed on the very next page
        # render only, so it never lingers past a refresh.
        'oidc_sso_error': session.pop(SSO_ERROR_FLAG, False) if session else False,
    }
