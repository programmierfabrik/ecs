import re
from datetime import datetime, time, timedelta

from django.conf import settings
from django.core.cache import cache
from django.template import Library, Node, TemplateSyntaxError
from django.utils import timezone
from django.utils.translation import gettext as _

from ecs.core import paper_forms
from ecs.core.models import Submission, AdvancedSettings, EthicsCommission
from ecs.docstash.models import DocStash

register = Library()

register.filter('type_name', lambda obj: type(obj).__name__)
register.filter('endswith', lambda obj, end: obj.endswith(end))
register.filter('not', lambda obj: not obj)
register.filter('multiply', lambda a, b: a * b)
register.filter('euro', lambda val: ("€ %.2f" % float(val)).replace('.', ','))
register.filter('is_none', lambda obj: obj is None)


@register.filter
def getitem(obj, name):
    try:
        return obj[name]
    except KeyError:
        return None


@register.filter
def ec_number(submission):
    if submission:
        return submission.get_ec_number_display()
    return None


@register.filter
def get_field_info(formfield):
    if formfield and hasattr(formfield.form, '_meta'):
        return paper_forms.get_field_info(model=formfield.form._meta.model, name=formfield.name)
    else:
        return None


@register.filter
def form_value(form, fieldname):
    if form.data:
        field = form.fields[fieldname]
        prefix = form.add_prefix(fieldname)
        return field.widget.value_from_datadict(form.data, form.files, prefix)
    try:
        return form.initial[fieldname]
    except KeyError:
        return None


@register.filter
def simple_timedelta_format(td):
    if not td.seconds:
        return "0"
    minutes, seconds = divmod(td.seconds, 60)
    hours, minutes = divmod(minutes, 60)
    result = []
    if hours:
        result.append("%sh" % hours)
    if minutes:
        result.append("%smin" % minutes)
    if seconds:
        result.append("%ss" % seconds)
    return " ".join(result)


@register.filter
def smart_truncate(s, n):
    if not s:
        return ""
    if len(s) <= n:
        return s
    return "%s …" % re.match(r'(.{,%s})\b' % (n - 2), s).group(0)


@register.filter
def has_submissions(user):
    return (
        Submission.unfiltered.mine(user).exists() or
        DocStash.objects.filter(
            group='ecs.core.views.submissions.create_submission_form',
            owner=user, current_version__gte=0
        ).exists()
    )


@register.filter
def has_assigned_submissions(user):
    return Submission.objects.reviewed_by_user(user).exists()


@register.filter
def is_docstash(obj):
    return isinstance(obj, DocStash)


@register.filter
def yes_no_unknown(v):
    if v is True:
        return _('yes')
    elif v is False:
        return _('no')
    else:
        return _('Unknown')


@register.filter
def last_recessed_vote(top):
    if top.submission:
        return top.submission.get_last_recessed_vote(top)
    return None


@register.filter
def allows_amendments_by(sf, user):
    return sf.allows_amendments(user)


@register.filter
def allows_edits_by(sf, user):
    return sf.allows_edits(user)


class BreadcrumbsNode(Node):
    def __init__(self, varname):
        super().__init__()
        self.varname = varname

    def render(self, context):
        user = context['request'].user
        if not user.is_anonymous:
            crumbs_cache_key = 'submission_breadcrumbs-user_{0}'.format(user.pk)
            crumb_pks = cache.get(crumbs_cache_key, [])
            crumbs = list(Submission.objects.filter(pk__in=crumb_pks).only('ec_number'))
            crumbs.sort(key=lambda x: crumb_pks.index(x.pk))
            context[self.varname] = crumbs
        return ''


@register.tag
def get_breadcrumbs(parser, token):
    try:
        name, as_, varname = token.split_contents()
    except ValueError:
        raise TemplateSyntaxError('{% get_breadcrumbs as VAR %} expected')
    return BreadcrumbsNode(varname)


class DbSettingNode(Node):
    def __init__(self, name, varname):
        super().__init__()
        self.name = name
        self.varname = varname

    def render(self, context):
        name = self.name.resolve(context)
        val = AdvancedSettings.objects.values_list(name, flat=True)[0]

        if self.varname:
            context[self.varname] = val
            return ''
        else:
            return val


@register.tag
def db_setting(parser, token):
    bits = token.split_contents()
    if len(bits) == 2:
        kw_, name = bits
        varname = None
    elif len(bits) == 4 and bits[2] == 'as':
        kw_, name, as_, varname = bits
    else:
        raise TemplateSyntaxError('{% db_setting name [as VAR] %}')

    name = parser.compile_filter(name)
    return DbSettingNode(name, varname)


@register.simple_tag
def ec_name():
    ec = EthicsCommission.objects.get(uuid=settings.ETHICS_COMMISSION_UUID)
    return ec.name


@register.simple_tag
def maintenance_warning():
    return _('Waring maintenance: begins at %(begin)s and ends at %(end)s') % {'begin': '14:00', 'end': '15:00'}


@register.simple_tag
def is_maintenance():
    weekday = datetime.today().weekday()
    # Only on fridays
    if weekday != 4:
        return False

    begin = time(10, 00)
    end = time(15, 00)
    now = datetime.now().time()
    return begin < now < end


@register.filter
def deadline_duration(input_value):
    if input_value is None:
        return ''
    value = input_value - timezone.now()  # This will give us a timedelta object.
    if value <= timedelta(seconds=0):
        return ''
    elif value >= timedelta(days=1):
        days = value.days
        return f'{days} Tag' if days == 1 else f'{days} Tage'
    elif timedelta(hours=1) <= value < timedelta(days=1):
        hours = value.seconds // 3600
        return f'{hours} Stunde' if hours == 1 else f'{hours} Stunden'
    else:
        return '1 Stunde'
