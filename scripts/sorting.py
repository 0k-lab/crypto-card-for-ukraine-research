"""Exact comparison values and precomputed orders; the browser only moves cards."""
from decimal import Decimal
from cashback import monthly_cashback
from i18n import translator


def comparison_cost(row):
    final = row.get('final_transaction', {})
    if final.get('spent_amount') is not None:
        return Decimal(final['spent_amount'])
    return Decimal(row['conversion_quote']['input_amount'] if 'conversion_quote' in row else row['receipt']['amount'] if 'receipt' in row else row['debit'])


def cashback_value(row):
    if 'points_assessment' in row:
        return Decimal(row['points_assessment']['cashback_deduction_usd'])
    if 'reward_valuation' in row:
        return Decimal(row['observed_reward']['amount']) * Decimal(row['reward_valuation']['price_usd_per_btc'])
    return None if row['reward'] is None else Decimal(row['reward'])


def included_cashback_value(row):
    reward = row['observed_reward']
    # Fixed BTC amounts count before payout at the author's requested reference valuation.
    expected_btc = reward['asset'] == 'BTC' and reward['availability'] == 'participant_confirmed_amount_pending_credit'
    accepted_amount = reward['availability'] == 'participant_accepted_fixed_amount'
    if reward['availability'] != 'participant_confirmed_credited' and not expected_btc and not accepted_amount:
        return Decimal('0')
    value = cashback_value(row)
    assert value is not None, 'Included cashback requires a monetary valuation'
    if accepted_amount:
        assert reward['asset'] == 'USD' and value == Decimal(reward['amount']), 'Accepted cashback must match the displayed USD amount'
    return value


def cashback_potential(row, program, spend, t=None):
    t = translator("uk") if t is None else t
    if row['id'] == 'okx' and not row['reward_eligibility']['eligible_for_cashback']:
        return Decimal('0'), t('sort.okx_ineligible'), []
    if row['id'] == 'trustee_plus':
        return Decimal(row['points_assessment']['cashback_deduction_usd']), t('sort.points'), []
    # Bybit has two conflicting base/next schedules; retain both conditional projections.
    tiers = program['tiers'] if row['id'] == 'bybit' else program['tiers'][:2]
    candidates = []
    for tier in tiers:
        earned, available = monthly_cashback(tier, spend)
        fee = None if tier['annual_fee_usd'] is None else Decimal(tier['annual_fee_usd']) / 12
        net = None if available is None or fee is None else available - fee
        candidates.append({
            'tier': tier['name'], 'conditions': tier['conditions'],
            'earned_usd': None if earned is None else str(earned),
            'available_usd': None if available is None else str(available),
            'monthly_fee_usd': None if fee is None else str(fee),
            'net_usd': None if net is None else str(net),
        })
    if not candidates or any(item['net_usd'] is None for item in candidates):
        return None, t('sort.unknown'), candidates
    best = max(candidates, key=lambda item: Decimal(item['net_usd']))
    note = best['tier'] + '.'
    if row['id'] == 'solid':
        note += t('sort.solid_fee_note')
    elif row['id'] == 'coca':
        note += t('sort.coca_stake_note')
    elif row['id'] == 'bybit':
        note = t('sort.bybit_note')
    elif row['id'] == 'kolo':
        note = t('sort.kolo_note')
    elif row['id'] == 'whitebit':
        note = t('sort.whitebit_note')
    return Decimal(best['net_usd']), note, candidates


def card_sorting(rows, tier_data, language="uk"):
    t = translator(language)
    modes = {
        'gross': {
            'label': t('sort.gross_label'), 'metric': t('ui.debit'),
            'description': t('sort.gross_description'),
        },
        'potential': {
            'label': t('sort.potential_label'), 'metric': t('sort.potential_metric'),
            'description': t('sort.potential_description'),
        },
        'actual': {
            'label': t('sort.actual_label'), 'metric': t('sort.actual_metric'),
            'description': t('sort.actual_description'),
        },
    }
    for mode, spec in modes.items():
        values, items = {}, {}
        for row in rows:
            identifier = row['id']
            cost = comparison_cost(row)
            if mode == 'potential':
                value, note, candidates = cashback_potential(row, tier_data['cards'][identifier], tier_data['monthly_eligible_merchant_spend_usd'], t)
                display = t('ui.unknown') if value is None else t('sort.monthly_display', value0=f'{value:.2f}')
                if identifier == 'okx' and not row['reward_eligibility']['eligible_for_cashback']:
                    display = t('sort.okx_unavailable_display')
                elif identifier in ('kolo', 'whitebit') and value is not None:
                    display = t('ui.up_to', value0=display)
            else:
                deduction = included_cashback_value(row) if mode == 'actual' else Decimal('0')
                value = cost - deduction
                display = ('≈' if deduction and 'reward_valuation' in row else '') + f'${value:.2f}'
                if mode == 'gross':
                    note = t('sort.gross_note')
                elif cashback_value(row):
                    note = t('sort.cashback_unconfirmed')
                elif 'points_assessment' in row:
                    note = t('sort.points')
                elif identifier == 'okx':
                    note = t('sort.okx_ineligible')
                else:
                    note = t('sort.no_cashback')
                if mode == 'actual' and deduction:
                    if row['observed_reward']['availability'] == 'participant_accepted_fixed_amount':
                        note = t('sort.cashback_included_note', value0=f'{deduction:.2f}')
                    else:
                        note = t('sort.btc_expected_note') if row['observed_reward']['availability'] == 'participant_confirmed_amount_pending_credit' else t('sort.btc_credited_note') if 'reward_valuation' in row else t('sort.points_credited_note')
                candidates = []
            values[identifier] = value
            items[identifier] = {'value': None if value is None else str(value), 'display': display, 'note': note}
            if mode == 'potential':
                items[identifier]['candidates'] = candidates
        ordered = sorted(rows, key=lambda row: (
            values[row['id']] is None,
            -(values[row['id']] or Decimal('0')) if mode == 'potential' else values[row['id']],
            comparison_cost(row),
        ))
        spec['order'] = [row['id'] for row in ordered]
        spec['items'] = items
        for rank, row in enumerate(ordered, 1):
            items[row['id']]['rank'] = '—' if values[row['id']] is None else f'{rank:02d}'
    return {'default': 'actual', 'modes': modes}
