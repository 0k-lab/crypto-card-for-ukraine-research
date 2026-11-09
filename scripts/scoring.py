"""Dense criterion ranks for the explicitly documented Ukrainian base-tier scenario."""
from decimal import Decimal
from cashback import monthly_cashback
from earning import monthly_income
from sorting import comparison_cost

CRITERIA = ('currencies', 'purchase', 'cashback', 'income', 'funding', 'withdrawal',
            'minimum_in', 'minimum_out', 'networks', 'actions')
HIGHER_IS_BETTER = {'currencies', 'cashback', 'income', 'networks'}


def score_cards(snapshot, measurements, tiers, funding_tests, earning_model):
    rows = {row['id']: row for row in measurements['rows']}
    tests = {test['card']: test for test in funding_tests['tests']}
    assert set(snapshot['cards']) == set(rows) == set(tiers['cards'])
    result = {}
    for identifier, card in snapshot['cards'].items():
        assert card['currencies'] and len(card['currencies']) == len(set(card['currencies']))
        assert card['withdrawal_networks'] and len(card['withdrawal_networks']) == len(set(card['withdrawal_networks']))
        offer = card['income_offer']
        income = monthly_income(offer, earning_model)
        income_value = income[0] if income is not None else None
        if identifier == 'okx':
            income_value = Decimal(0)
        if identifier in {'okx', 'simple', 'keyone', 'trustee_plus'}:
            cashback = Decimal(0)
        else:
            regular = dict(tiers['cards'][identifier]['tiers'][0])
            if identifier == 'whitebit':
                regular['rate'] = str(min(Decimal(rate) for rate in regular['category_rates'].values() if Decimal(rate) > 0))
            cashback = monthly_cashback(regular, snapshot['monthly_spend_usd'])[1]
        assert cashback is not None
        funding = Decimal(0)
        if identifier == 'keyone':
            test = tests[identifier]
            funding = Decimal(test['credit_execution']['shortfall_vs_sent_nominal_usd']) / Decimal(test['sent_token_amount'])
        elif identifier == 'trustee_plus':
            test = tests[identifier]['card_funding']
            funding = Decimal(test['total_difference_estimate_usdt']) / Decimal(test['wallet_debit_estimate_usdt'])
        values = {
            'currencies': Decimal(len(card['currencies'])),
            'purchase': comparison_cost(rows[identifier]),
            'cashback': cashback,
            'income': income_value,
            'funding': funding,
            'withdrawal': Decimal(card['withdrawal_fee']),
            'minimum_in': None if card['minimum_in'] is None else Decimal(card['minimum_in']),
            'minimum_out': None if card['minimum_out_total'] is None else Decimal(card['minimum_out_total']),
            'networks': Decimal(len(card['withdrawal_networks'])),
            'actions': Decimal(card['manual_actions']),
        }
        assert all(value is None or value.is_finite() and value >= 0 for value in values.values())
        result[identifier] = {'values': values, 'scores': {}, 'conditional': set(card['conditional_criteria'])}
    for criterion in CRITERIA:
        # No declared minimum is an explicit scoring category, separate from a numeric zero.
        comparable = {}
        for identifier, item in result.items():
            value = item['values'][criterion]
            if criterion in {'minimum_in', 'minimum_out'}:
                assert snapshot['cards'][identifier]['no_' + criterion + '_declared'] == (value is None)
                comparable[identifier] = (0, Decimal(0)) if value is None else (1, value)
            elif value is not None:
                comparable[identifier] = value
        levels = sorted(set(comparable.values()), reverse=criterion in HIGHER_IS_BETTER)
        assert 1 <= len(levels) <= 10
        for identifier, item in result.items():
            item['scores'][criterion] = 10 - levels.index(comparable[identifier]) if identifier in comparable else 10 - len(levels)
    for item in result.values():
        item['total'] = sum(item['scores'].values()) / Decimal(len(CRITERIA))
    return result
