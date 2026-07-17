from django.conf import settings

from ecs.users.oidc_views import SSO_ERROR_FLAG

def ecs_settings(request):
    return {
        'debug': settings.DEBUG,
        'keycloak_sso_enabled': settings.ECS_KEYCLOAK_ENABLED,
        # Popped (not just read): shown/consumed on the very next page
        # render only, so it never lingers past a refresh.
        'oidc_sso_error': request.session.pop(SSO_ERROR_FLAG, False),
    }
