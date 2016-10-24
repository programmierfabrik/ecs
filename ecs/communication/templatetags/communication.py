from django.template import Library


register = Library()


@register.filter
def starred_by(thread, user):
    if user.id == thread.sender_id:
        return thread.starred_by_sender
    elif user.id == thread.receiver_id:
        return thread.starred_by_receiver
    else:
        assert False


@register.filter
def remote(thread, user):
    if user == thread.sender:
        return thread.receiver
    elif user == thread.receiver:
        return thread.sender
    else:
        return None


@register.filter
def preview(message, chars):
    text = ' '.join(message.text.splitlines())
    if len(text) > chars:
        return text[:chars-3] + '...'
    else:
        return text
