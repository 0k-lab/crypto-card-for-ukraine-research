"""Income model for a balance spent evenly over a standard 30-day month."""
from decimal import Decimal


def monthly_income(offer, model):
    """Return a conditional estimate, never inferred measured yield."""
    if offer.get('eligible_in_ukraine') is False or offer['rate'] is None:
        return None
    rate = Decimal(offer['rate'])
    start = Decimal(model['starting_eligible_balance_usd'])
    end = Decimal(model['ending_eligible_balance_usd'])
    days = Decimal(model['days'])
    year = Decimal(model['days_per_year'])
    assert all(value.is_finite() for value in (rate, start, end, days, year))
    assert rate >= 0 and start >= end >= 0 and year >= days > 0
    # Balance-wide caps require separate eligibility rules from the APR bonus tier.
    assert offer['eligible_balance_cap_usd'] is None
    balance = (start + end) / 2
    apr = balance * days * rate / year
    if offer.get('bonus_apr') is not None:
        assert offer['rate_kind'] == 'apr'
        bonus = Decimal(offer['bonus_apr'])
        cap = Decimal(offer['bonus_balance_cap_usd'])
        assert bonus.is_finite() and cap.is_finite() and bonus >= 0 and cap > 0
        def capped_area(value):
            return value * value / 2 if value <= cap else cap * value - cap * cap / 2
        average_capped = min(start, cap) if start == end else (capped_area(start) - capped_area(end)) / (start - end)
        apr += average_capped * bonus * days / year
    apy = balance * days * ((1 + rate) ** (1 / year) - 1)
    if offer['rate_kind'] == 'apr':
        return apr, apr
    if offer['rate_kind'] == 'apy':
        return apy, apy
    assert offer['rate_kind'] == 'annual_unspecified'
    return min(apr, apy), max(apr, apy)
