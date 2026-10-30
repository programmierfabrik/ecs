from django.utils.translation import gettext_lazy as _

VOTE_PREPARATION_CHOICES = (
    ('1', _('1 positive')),
    ('2', _('2 positive under reserve')),
)

B3b = ('3b', _('3b recessed (examined)'))

B2_VOTE_PREPARATION_CHOICES = VOTE_PREPARATION_CHOICES + (B3b,)

CLASSIC_VOTE_RESULT_CHOICES = VOTE_PREPARATION_CHOICES + (
    ('3a', _('3a recessed (not examined)')),
    B3b,
    ('4', _('4 negative')),
    ('5', _('5 withdrawn (applicant)')),
)

# A CTIS study is discussed in a meeting like any other study, but gets a
# « BCTIS Stellungnahme » instead of a B1-B5 vote: it is never signed, has no
# PDF and ends nothing. It is deliberately absent from POSITIVE/NEGATIVE/
# PERMANENT/RECESSED_VOTE_RESULTS below - that is what keeps every outcome
# branch in ecs.votes.triggers from firing for it.
CTIS_VOTE_RESULT_CHOICES = (
    ('ctis', 'BCTIS Stellungnahme'),
)

VOTE_RESULT_CHOICES = CLASSIC_VOTE_RESULT_CHOICES + CTIS_VOTE_RESULT_CHOICES

POSITIVE_VOTE_RESULTS = ('1', '2')
NEGATIVE_VOTE_RESULTS = ('4', '5')
RECESSED_VOTE_RESULTS = ('3a', '3b')
CTIS_VOTE_RESULTS = ('ctis',)

PERMANENT_VOTE_RESULTS = ('1',) + NEGATIVE_VOTE_RESULTS
