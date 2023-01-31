from django.utils.functional import wraps
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse

from ecs.docstash.models import DocStash


def with_docstash(group=None):
    def _decorator(view):
        view_name = group or '.'.join((view.__module__, view.__name__))

        @wraps(view)
        def _inner(request, docstash_key=None, **kwargs):
            if view_name == 'ecs.core.views.submissions.create_submission_form':
                from ecs.core.views.submissions import create_submission_form
                view_to_redirect = create_submission_form
            elif view_name == 'ecs.notifications.views.create_notification':
                from ecs.notifications.views import create_notification
                view_to_redirect = create_notification

            assert view_to_redirect is not None

            if not docstash_key:
                docstash = DocStash.objects.create(group=view_name, owner=request.user)
                return redirect(view_to_redirect, docstash_key=docstash.key, **kwargs)

            docstash = get_object_or_404(DocStash, group=view_name,
                owner=request.user, key=docstash_key)
            request.docstash = docstash
            return view(request, **kwargs)

        return _inner

    return _decorator
