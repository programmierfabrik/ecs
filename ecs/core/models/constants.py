from django.utils.translation import gettext_lazy as _

MIN_EC_NUMBER = 1000

SUBMISSION_TYPE_MONOCENTRIC = 1
SUBMISSION_TYPE_MULTICENTRIC = 2
SUBMISSION_TYPE_MULTICENTRIC_LOCAL = 6

SUBMISSION_TYPE_CHOICES = (
    (SUBMISSION_TYPE_MONOCENTRIC, _('monocentric')),
    (SUBMISSION_TYPE_MULTICENTRIC, _('multicentric, main ethics commission')),
    (SUBMISSION_TYPE_MULTICENTRIC_LOCAL, _('multicentric, local ethics commission')),
)

SUBMISSION_INFORMATION_PRIVACY_CHOICES = (
    ('personal', _('individual-related')),
    ('non-personal', _('implicit individual-related')),
    ('anonymous', _('completely anonymous')),
)

SUBMISSION_LANE_RETROSPECTIVE_THESIS = 1
SUBMISSION_LANE_EXPEDITED = 2
SUBMISSION_LANE_BOARD = 3
SUBMISSION_LANE_LOCALEC = 4

SUBMISSION_LANE_CHOICES = (
    (SUBMISSION_LANE_BOARD, _('board')),
    (SUBMISSION_LANE_EXPEDITED, _('expedited')),
    (SUBMISSION_LANE_RETROSPECTIVE_THESIS, _('retrospective thesis')),
    (SUBMISSION_LANE_LOCALEC, _('Local EC')),
)

SUBMISSION_AGE_UNIT_HOURS = 1
SUBMISSION_AGE_UNIT_DAYS = 2
SUBMISSION_AGE_UNIT_MONTHS = 3
SUBMISSION_AGE_UNIT_YEARS = 4

SUBMISSION_AGE_UNIT = (
    (SUBMISSION_AGE_UNIT_HOURS, _('hours')),
    (SUBMISSION_AGE_UNIT_DAYS, _('days')),
    (SUBMISSION_AGE_UNIT_MONTHS, _('months')),
    (SUBMISSION_AGE_UNIT_YEARS, _('years'))
)
