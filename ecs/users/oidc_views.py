from django.http import HttpResponseRedirect
from django.urls import reverse
from mozilla_django_oidc.views import OIDCAuthenticationCallbackView

# One-time session flag consumed (popped) by ecs.core.context_processors.ecs_settings,
# so it never shows up as a query param and never lingers past the next page render.
SSO_ERROR_FLAG = 'oidc_sso_error'


class KeycloakOIDCCallbackView(OIDCAuthenticationCallbackView):
    """
    A failure (e.g. a Keycloak identity with no matching Django user)
    redirects with a one-time error marker so the login page can show a
    message.
    """

    def login_failure(self):
        self.request.session[SSO_ERROR_FLAG] = True
        return HttpResponseRedirect(reverse('users.login'))
