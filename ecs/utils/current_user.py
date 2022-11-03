from threading import local

_user = local()


class CurrentUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_request(self, request):
        _user.value = request.user

    def process_response(self, request, response):
        # when response is ready, request should be flushed
        self.reset()
        return response

    def process_exception(self, request, exception):
        # if an exception has happened, request should be flushed too
        self.reset()

    def reset(self):
        if getattr(_user, 'value', None) is not None:
            del _user.value


def get_current_user():
    return _user.value
