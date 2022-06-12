from django.contrib.auth.models import User
from ecs.userswitcher import SESSION_KEY
from django.utils.deprecation import MiddlewareMixin

class UserSwitcherMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if SESSION_KEY in request.session:
            try:
                request.original_user = request.user # save the original user
                request.user = User.objects.get(pk=request.session[SESSION_KEY])
            except User.DoesNotExist:
                pass
