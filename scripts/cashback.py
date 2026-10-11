"""Cap-aware monthly cashback projections; token principal is never a tier fee."""
from decimal import Decimal


def monthly_cashback(tier, spend):
    spend = Decimal(spend)
    assert spend >= 0
    rate = tier['rate']
    if rate is None and tier.get('category_rates'):
        # Without purchase categories, only the maximum after selecting eligible categories is known.
        rate = max(map(Decimal, tier['category_rates'].values()))
    if rate is None:
        return None, None
    earned = Decimal(rate) * spend
    if tier['cap'] is None:
        return earned, None  # Unknown cap does not establish an available payout.
    # EUR caps use the saved reference conversion; per-purchase caps make this an upper bound.
    capacity = Decimal(tier['cap']) * Decimal(tier.get('usd_per_currency_unit', '1'))
    if tier['cap_kind'] == 'earning':
        earned = min(earned, capacity)
    return earned, min(earned, capacity)


def solid_upgrade(tiers, spend, usd_subscriptions, eligible_categories=0):
    base, prime = tiers[:2]
    spend, usd, categories = map(Decimal, (spend, usd_subscriptions, eligible_categories))
    assert 0 <= categories <= spend and 0 <= usd <= spend
    base_cashback = monthly_cashback(base, spend)[1]
    prime_cashback = min(
        spend * Decimal(prime['rate']) + categories * (Decimal(prime['category_rate']) - Decimal(prime['rate'])),
        Decimal(prime['cap']),
    )
    fx_saving = (spend - usd) * (Decimal(base['non_usd_fx_fee']) - Decimal(prime['non_usd_fx_fee']))
    return prime_cashback - base_cashback + fx_saving - Decimal(prime['annual_fee_usd']) / 12


def solid_spend_threshold(tiers, usd_subscriptions, eligible_categories=0):
    base, prime = tiers[:2]
    usd, categories = map(Decimal, (usd_subscriptions, eligible_categories))
    fx = Decimal(base['non_usd_fx_fee']) - Decimal(prime['non_usd_fx_fee'])
    category_increment = Decimal(prime['category_rate']) - Decimal(prime['rate'])
    threshold = (Decimal(prime['annual_fee_usd']) / 12 + fx * usd - category_increment * categories) / (Decimal(prime['rate']) - Decimal(base['rate']) + fx)
    # This closed-form threshold applies before either cashback cap; refuse an invalid extrapolation.
    assert threshold >= max(usd, categories)
    assert threshold * Decimal(base['rate']) <= Decimal(base['cap'])
    assert threshold * Decimal(prime['rate']) + categories * category_increment <= Decimal(prime['cap'])
    assert abs(solid_upgrade(tiers, threshold, usd, categories)) < Decimal('1e-20')
    return threshold
