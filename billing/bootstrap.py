# -*- coding: utf-8 -*-
from decimal import Decimal
from ecs import bootstrap
from ecs.billing.models import Price
from ecs.billing.models import STUDY_PRICING_OTHER, STUDY_PRICING_MULTICENTRIC_AMG_MAIN, STUDY_PRICING_MULTICENTRIC_AMG_LOCAL, STUDY_PRICING_REMISSION, EXTERNAL_REVIEW_PRICING

@bootstrap.register()
def prices():
    prices = {
        STUDY_PRICING_OTHER: 1500,
        STUDY_PRICING_MULTICENTRIC_AMG_MAIN: 4000,
        STUDY_PRICING_MULTICENTRIC_AMG_LOCAL: 500,
        STUDY_PRICING_REMISSION: 0,
        EXTERNAL_REVIEW_PRICING: Decimal('200.00'),
    }
    for category, price in prices.items():
        Price.objects.get_or_create(category=category, defaults={
            'price': price,
        })
