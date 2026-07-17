import logging

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from mozilla_django_oidc.auth import OIDCAuthenticationBackend

from ecs.users.utils import hash_email

logger = logging.getLogger(__name__)

class EmailAuthBackend(ModelBackend):
    # noinspection PyMethodOverriding
    # Deliberately narrower than ModelBackend.authenticate() (no **kwargs):
    # Django's authenticate() dispatcher only calls a backend whose signature
    # can bind the given credentials, so this exact signature is what makes
    # Django skip this backend during the Keycloak OIDC flow (whose
    # credentials are nonce/code_verifier, not email/password) instead of
    # crashing on email=None. Do not add **kwargs here.
    def authenticate(self, request, email=None, password=None):
        username = hash_email(email)
        return super().authenticate(request, username=username, password=password)


class KeycloakOIDCBackend(OIDCAuthenticationBackend):
    """
    Keycloak is authentication-only: it must never create accounts or
    grant access on its own. A Keycloak identity can only resolve to a
    Django user that is already provisioned - authorization stays with
    the app (see ecs.authorization).
    """

    def filter_users_by_claims(self, claims):
        # Keycloak realm emails often don't match ECS accounts, so try the
        # "second-email" attribute (mapped to userinfo) first, falling back
        # to the regular email claim, before giving up.
        for email in (claims.get('second-email'), claims.get('email')):
            print(email)
            if not email:
                continue
            users = User.objects.filter(username=hash_email(email), is_active=True)
            if users.exists():
                return users
        return User.objects.none()

    def create_user(self, claims):
        logger.warning(
            'Rejected Keycloak login for %s: no matching, pre-provisioned Django user.',
            claims.get('email'))
        return None

    def update_user(self, user, claims):
        return user
