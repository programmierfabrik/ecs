import base64
from functools import cache
from urllib.parse import unquote

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin

from ecs.pki.models import Certificate, CertificateAuthority


@cache
def _ca_certificate():
    return x509.load_pem_x509_certificate(
        CertificateAuthority.objects.get().cert.encode())


def _client_certificate(request):
    """
    The Certificate for the client certificate Traefik forwards, or None.

    Traefik (passtlsclientcert, pem = true) sends the presented chain as
    URL-escaped base64 DER without PEM delimiters, comma separated, leaf
    first. Traefik already verified the chain; checking the issuer again keeps
    a forged header from passing should Traefik ever forward client-sent
    X-Forwarded-* headers.
    """
    header = request.META.get('HTTP_X_FORWARDED_TLS_CLIENT_CERT', '')
    if not header:
        return None
    try:
        der = base64.b64decode(unquote(header).split(',')[0], validate=True)
        cert = x509.load_der_x509_certificate(der)
        cert.verify_directly_issued_by(_ca_certificate())
    except (ValueError, TypeError, InvalidSignature):
        return None
    return Certificate.objects.filter(
        serial=cert.serial_number, revoked_at=None,
        expires_at__gt=timezone.now()).first()


class ClientCertMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if not getattr(settings, 'ECS_REQUIRE_CLIENT_CERTS', False):
            return

        if request.user.is_authenticated:
            profile = request.user.profile
            if profile.is_internal or profile.is_omniscient_member:
                certificate = _client_certificate(request)
                # The certificate identifies the person at the keyboard, who
                # is the original user when the userswitcher is in use.
                user = getattr(request, 'original_user', request.user)
                if certificate is None or certificate.user_id != user.pk:
                    raise PermissionDenied()
