"""Validate public evidence and calculations using only Python's standard library."""
from pathlib import Path
from decimal import Decimal
from html.parser import HTMLParser
import hashlib
import json
import html
from string import Formatter
from i18n import LANGUAGES, load_messages, translator
import re
import os
from datetime import date
from xml.etree import ElementTree as ET
import struct
import subprocess
import zlib
from cashback import monthly_cashback, solid_upgrade, solid_spend_threshold
from earning import monthly_income
from sorting import card_sorting, cashback_potential, cashback_value, comparison_cost, included_cashback_value
from copy import deepcopy
from urllib.parse import urlsplit, unquote
from pages import value_text
from scoring import score_cards, CRITERIA

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT / 'data/measurements.json').read_text())
rows = {row['id']: row for row in data['rows']}
research = json.loads((ROOT / 'data/research.json').read_text())
assert research['author'] == {'name': 'kricha', 'url': 'https://github.com/kricha'}
assert date.fromisoformat(research['updated_on']) >= date.fromisoformat(data['test_date'])
config = json.loads((ROOT / 'data/redactions.json').read_text())
assert len(data['rows']) == 9
earning = json.loads((ROOT / 'data/earning.json').read_text())
assert earning['checked_on'] == data['test_date']
assert set(earning['cards']) == {row['id'] for row in data['rows']}
earning_model = earning['model']
assert earning_model['starting_eligible_balance_usd'] == '1000'
assert earning_model['ending_eligible_balance_usd'] == '0'
assert earning_model['average_eligible_balance_usd'] == '500'
assert earning_model['days'] == 30 and earning_model['days_per_year'] == 365
assert earning_model['reinvest_income'] is False
assert (Decimal(earning_model['starting_eligible_balance_usd']) + Decimal(earning_model['ending_eligible_balance_usd'])) / 2 == Decimal(earning_model['average_eligible_balance_usd'])
for identifier, program in earning['cards'].items():
    assert program['evidence_level'] and program['spend_access']
    assert program['measured_annual_yield'] is None, 'No measured annual yield in this test'
    assert len(program['offers']) == (2 if identifier == 'solid' else 1)
    for offer in program['offers']:
        assert offer['rate_kind'] in {None, 'apr', 'apy', 'annual_unspecified'}
        assert isinstance(offer['upper_bound'], bool)
        assert offer['rate'] is None or Decimal(offer['rate']).is_finite() and Decimal(offer['rate']) >= 0
        assert offer['eligible_balance_cap_usd'] is None or Decimal(offer['eligible_balance_cap_usd']) > 0
    for source in program['sources']:
        assert source['evidence_level']
        if 'url' in source:
            assert source['url'].startswith('https://')
        else:
            path = (ROOT / source['file']).resolve()
            assert path.is_relative_to(ROOT) and path.is_file() and 'private' not in path.relative_to(ROOT).parts
            assert path.suffix.lower() not in {'.png', '.jpeg', '.jpg', '.webp', '.gif'}, 'Earning sources must not link to screenshots'
offers = {card: program['offers'][0] for card, program in earning['cards'].items()}
assert monthly_income(offers['bybit'], earning_model)[0].quantize(Decimal('0.01')) == Decimal('2.80')
assert offers['bybit']['rate'] == '0.0681' and offers['bybit']['asset'] == 'USDT'
assert offers['bybit']['upper_bound'] is False
bybit_earning = earning['cards']['bybit']
assert bybit_earning['banner_maximum_apr'] == '0.1089'
assert bybit_earning['auto_earn_enabled_by_asset'] == {'USDT': True, 'USDC': False}
assert bybit_earning['displayed_apr_by_asset']['USDC'] == '0.0542'
usdc_offer = dict(offers['bybit'], rate=bybit_earning['displayed_apr_by_asset']['USDC'])
assert monthly_income(usdc_offer, earning_model)[0].quantize(Decimal('0.01')) == Decimal('2.23')
five_apr = dict(offers['coca'], rate_kind='apr')
five_apy = dict(offers['coca'], rate_kind='apy')
assert abs(monthly_income(five_apr, earning_model)[0] - Decimal('2.054794520547945')) < Decimal('1e-14')
assert abs(monthly_income(five_apy, earning_model)[0] - Decimal('2.005209256701605')) < Decimal('1e-14')
assert tuple(value.quantize(Decimal('0.01')) for value in monthly_income(offers['coca'], earning_model)) == (Decimal('2.01'), Decimal('2.01'))
assert offers['simple']['rate'] == '0.05' and offers['simple']['rate_kind'] == 'apr'
assert tuple(value.quantize(Decimal('0.01')) for value in monthly_income(offers['simple'], earning_model)) == (Decimal('2.05'), Decimal('2.05'))
assert monthly_income(five_apr, dict(earning_model, starting_eligible_balance_usd='0')) == (Decimal(0), Decimal(0))
assert monthly_income(five_apr, dict(earning_model, ending_eligible_balance_usd='1000'))[0] == monthly_income(five_apr, earning_model)[0] * 2
assert monthly_income(dict(five_apr, rate='0'), earning_model) == (Decimal(0), Decimal(0))
for card in ('kolo', 'trustee_plus', 'keyone', 'whitebit'):
    assert monthly_income(offers[card], earning_model) is None, 'Unknown is not zero'
okx_earning = earning['cards']['okx']
assert offers['okx']['eligible_in_ukraine'] is False and offers['okx']['rate'] == '0.041'
assert offers['okx']['rate_kind'] == 'apy' and offers['okx']['article_updated_on'] == '2026-06-02'
assert okx_earning['evidence_level'] == 'official_usdg_rewards_ukraine_exclusion'
assert okx_earning['sources'][0]['url'] == 'https://www.okx.com/ua/learn/usdg'
assert 'за винятком Росії та України' in okx_earning['sources'][0]['quotes'][0]
assert monthly_income(offers['okx'], earning_model) is None, 'Ineligible income must not enter the model'
assert monthly_income(dict(offers['okx'], eligible_in_ukraine=True), earning_model)[0] > 0
for invalid in (dict(five_apr, rate='-0.05'), dict(five_apr, rate='NaN'), dict(five_apr, eligible_balance_cap_usd='100')):
    try:
        monthly_income(invalid, earning_model)
    except AssertionError:
        pass
    else:
        raise AssertionError('Invalid/unsupported Earning offer accepted')
coca_earning = earning['cards']['coca']
assert Decimal(coca_earning['counter_after_usd']) - Decimal(coca_earning['counter_before_usd']) == Decimal(coca_earning['counter_increase_usd']) == Decimal('0.00001864')
assert coca_earning['cashback_claim_cap_applies'] is False and coca_earning['claim_minimum_usd'] == '1'
assert coca_earning['claim_manual'] is True and coca_earning['offers'][0]['applies_to'] == ['Starter', 'Standard']
solid_program = earning['cards']['solid']
assert offers['solid']['rate'] == '0.0429' and offers['solid']['rate_kind'] == 'apy'
assert offers['solid']['rate'] == solid_program['displayed_30_day_apy_by_asset']['USDC']
assert solid_program['displayed_15_day_apy_by_asset']['USDC'] == '0.0344'
assert solid_program['credit_mode']['account_screen_borrowing_rate'] == '0.04'
assert solid_program['credit_mode']['onboarding_illustrative_borrowing_apy'] == '0.0557'
assert solid_program['credit_mode']['included_in_income_model'] is False
assert solid_program['credit_mode']['eligible_collateral'] == 'USD_yield_balance_only'
assert solid_program['savings_mechanism']['deposit_assets_per_faq'] == ['USDC', 'USDT']
assert solid_program['savings_mechanism']['receipt_token_fixed_at_one_usd'] is False
assert monthly_income(offers['solid'], earning_model)[0].quantize(Decimal('0.01')) == Decimal('1.73')
solid_recent_offer = dict(offers['solid'], rate=solid_program['displayed_7_day_apy_by_asset']['USDC'])
assert monthly_income(solid_recent_offer, earning_model)[0].quantize(Decimal('0.01')) == Decimal('1.15')
assert sum(Decimal(row['allocation']) for row in solid_program['displayed_allocations']['USDC']) == Decimal(solid_program['observed_usd_allocation_total']) == Decimal('0.96')
assert sum(Decimal(row['allocation']) for row in solid_program['displayed_allocations']['ETH']) == Decimal('1')
solid_earning = solid_program['offers'][1]
assert solid_earning['boost_apy'] == '0.02' and solid_earning['boost_payout_asset'] == 'soFUSE'
assert solid_earning['eligible_balance_cap_usd'] == '10000' and solid_earning['annual_subscription_usd'] == '199'
assert monthly_income(solid_earning, earning_model) is None, 'Token boost is not a standalone USD offer'
card_links = json.loads((ROOT / 'data/card-links.json').read_text())['cards']
assert set(card_links) == {row['id'] for row in data['rows']}
expected_opening_urls = {
    'bybit': 'https://www.bybit.com/cards/?ref=NZQ05D&source=applet_invite',
    'keyone': 'https://www.keyonepay.com/?ref=ref-2dc64a52-96dd-474e-a750-9d9629225f68',
    'kolo': 'https://get.kolo.xyz/p730944',
    'okx': 'https://okx.com/join/EQHODCN2',
    'simple': 'https://join.simple.app/23649C',
    'solid': 'https://www.solid.xyz/refer?ref=EV8PU',
    'trustee_plus': 'https://trustee.io/ua/?r=ojNqqBbp66b',
    'whitebit': 'https://whitebit.com/card-referral/4380c062-2877-4217-b438-b97f1b6e284f',
    'coca': 'https://coca.go.link?adj_t=24olejd2&referral_code=guhAn6w4gdD',
}
assert {card: item['url'] for card, item in card_links.items()} == expected_opening_urls
expected_official_urls = {
    'bybit': 'https://www.bybit.com/cards/',
    'keyone': 'https://www.keyonepay.com/',
    'kolo': 'https://kolo.xyz/',
    'okx': 'https://www.okx.com/pay',
    'simple': 'https://simple.app/',
    'solid': 'https://www.solid.xyz/',
    'trustee_plus': 'https://trustee.io/ua/',
    'whitebit': 'https://whitebit.com/usd-card',
    'coca': 'https://www.coca.xyz/cards',
}
assert {card: item['official_url'] for card, item in card_links.items()} == expected_official_urls
for card, item in card_links.items():
    url = urlsplit(item['url'])
    assert url.scheme == 'https' and url.hostname and not url.username and not url.password
    official_url = urlsplit(item['official_url'])
    assert official_url.scheme == 'https' and official_url.hostname and not official_url.username and not official_url.password
    assert not official_url.query and not official_url.fragment, 'Official links must not contain referral or tracking parameters'
    assert item['referral'] is True
assert {card for card, item in card_links.items() if item['bonus_note']} == {'bybit', 'okx', 'simple', 'solid', 'whitebit', 'trustee_plus', 'coca'}
assert not (ROOT / 'data/p2p-uah-quotes-2026-10-09.json').exists()
issuers = json.loads((ROOT / 'data/card-issuers.json').read_text())
assert issuers['checked_on'] == data['test_date']
assert set(issuers['entries']) == {row['id'] for row in data['rows']}
for item in issuers['entries'].values():
    assert item['label'] and item['scope'] and item['evidence_level']
    assert item['source_url'] is None or item['source_url'].startswith('https://')
    assert item['source_url'] is None or item['source_quote']
assert issuers['entries']['trustee_plus']['legal_issuer'] == 'Wirex Limited'
trustee_lookup = issuers['entries']['trustee_plus']['bin_lookup']
assert trustee_lookup['issuer_normalized'] == 'Wirex Limited' and trustee_lookup['independently_verified'] is False
assert issuers['entries']['trustee_plus']['evidence_level'] == 'official_product_page'
assert not {'bin', 'card_number', 'screenshot_file'} & trustee_lookup.keys()
assert issuers['entries']['whitebit']['legal_issuer'] == 'JSC Hash Bank'
assert issuers['entries']['whitebit']['evidence_level'] == 'official_product_help'
whitebit_lookup = issuers['entries']['whitebit']['bin_lookup']
assert whitebit_lookup['issuer_normalized'] == 'Insbank' and len(whitebit_lookup['reports']) == 3
assert whitebit_lookup['conflicts_with_program_source'] is True and whitebit_lookup['conflicting_results'] is False
assert whitebit_lookup['independently_verified'] is False
assert issuers['entries']['whitebit']['wallet_display']['label_as_reported'] == 'Hashbank'
assert issuers['entries']['whitebit']['wallet_display']['screenshot_supplied'] is False
for lookup in (whitebit_lookup, *whitebit_lookup['reports']):
    assert not {'bin', 'card_number', 'screenshot_file'} & lookup.keys()
assert issuers['entries']['okx']['legal_issuer'] is None
assert issuers['entries']['okx']['label'] == 'Bano Pty Ltd · уточнюю'
okx_lookup = issuers['entries']['okx']['bin_lookup']
assert okx_lookup['conflicting_results'] is True and okx_lookup['independently_verified'] is False
assert len(okx_lookup['reports']) == 3
assert [item['type_as_displayed'] for item in okx_lookup['reports']] == ['DEBIT • TITANIUM', 'Debit', 'Credit']
assert okx_lookup['reports'][2]['issuer_as_displayed'] == 'JPMORGAN CHASE BANK, N.A.'
assert 'суперечать один одному' in issuers['entries']['okx']['scope']
for lookup in (okx_lookup, *okx_lookup['reports']):
    assert not {'bin', 'card_number', 'screenshot_file'} & lookup.keys()
assert issuers['entries']['bybit']['legal_issuer'] == 'Fly Wallet Pty Ltd'
bin_lookup = issuers['entries']['bybit']['bin_lookup']
assert bin_lookup['issuer_as_displayed'] == 'FLY WALLET PTY, LTD.'
assert bin_lookup['currency_as_displayed'] == 'AUD' and bin_lookup['independently_verified'] is False
assert 'BIN не публікую; оригінальний скрін видалив після аналізу.' in issuers['entries']['bybit']['scope']
assert not {'bin', 'card_number', 'screenshot_file'} & bin_lookup.keys()
coca_lookup = issuers['entries']['coca']['bin_lookup']
assert issuers['entries']['coca']['label'] == coca_lookup['issuer_normalized'] == 'Wirex Limited'
assert issuers['entries']['coca']['legal_issuer'] is None
assert len(coca_lookup['reports']) == 3 and coca_lookup['independently_verified'] is False
assert coca_lookup['reports'][0]['currency_as_displayed'] == 'GBP'
for lookup in (bin_lookup, coca_lookup, *coca_lookup['reports']):
    assert not {'bin', 'card_number', 'screenshot_file'} & lookup.keys()
for card in ('kolo', 'keyone', 'simple', 'solid'):
    entry = issuers['entries'][card]
    assert entry['label'] == entry['bin_lookup']['issuer_normalized'] == 'Wirex Limited'
    assert entry['legal_issuer'] is None and entry['evidence_level'] == 'participant_reported_bin_lookup_result'
    assert entry['bin_lookup']['independently_verified'] is False
    assert not {'bin', 'card_number', 'screenshot_file'} & entry['bin_lookup'].keys()
assert issuers['entries']['okx']['public_documentation']['legal_issuer'] == 'UAB Monavate'
assert issuers['entries']['kolo']['public_documentation']['program_partner'] == 'Signify Holdings Inc. (Rain)'
assert issuers['entries']['coca']['public_documentation']['evidence_level'] == 'official_page_network_scope_mismatch'
assert len({row['id'] for row in data['rows']}) == 9
baseline = Decimal(data['merchant_amount_uah']) / Decimal(data['nbu_usd_uah'])
assert baseline == Decimal(data['nbu_equivalent_usd'])
nbu = json.loads((ROOT / 'data/nbu-usd-2026-10-09.json').read_text(), parse_float=Decimal)
assert nbu[0]['rate'] == Decimal(data['nbu_usd_uah'])
scenario = json.loads((ROOT / 'data/budget-scenario.json').read_text())
tier_data = json.loads((ROOT / 'data/cashback-tiers.json').read_text())
assert tier_data['checked_on'] == data['test_date']
assert set(tier_data['cards']) == {row['id'] for row in data['rows']}
assert tier_data['monthly_eligible_merchant_spend_usd'] == '1000'
for program in tier_data['cards'].values():
    assert program['status'] and program['scope'] and program['sources']
    for source in program['sources']:
        assert source.get('url', '').startswith('https://') or (ROOT / source['file']).is_file()
    for tier in program['tiers']:
        assert tier['rate'] is None or Decimal('0') < Decimal(tier['rate']) <= Decimal('1')
        assert tier['cap_kind'] in {'earning', 'claim', 'payout', 'unknown'}
        assert tier['cap'] is None or Decimal(tier['cap']) > 0
        assert tier['annual_fee_usd'] is None or Decimal(tier['annual_fee_usd']) >= 0
solid_tiers = tier_data['cards']['solid']['tiers']
assert monthly_cashback(solid_tiers[0], 1000) == (Decimal('30'), Decimal('30'))
assert monthly_cashback(solid_tiers[0], 10000) == (Decimal('50'), Decimal('50'))
assert monthly_cashback(solid_tiers[1], 2500) == (Decimal('100'), Decimal('100'))
assert len(solid_tiers) == 2
assert all(len(program['tiers']) <= 2 for card, program in tier_data['cards'].items() if card != 'bybit')
coca_tiers = tier_data['cards']['coca']['tiers']
assert monthly_cashback(coca_tiers[1], 1000) == (Decimal('30'), Decimal('25'))
assert monthly_cashback(coca_tiers[1], 10000) == (Decimal('300'), Decimal('25'))
assert monthly_cashback(coca_tiers[0], 1500) == (Decimal('15'), Decimal('15'))
assert coca_tiers[1]['annual_fee_usd'] == '0' and coca_tiers[1]['token_amount'] == '300'
subscription_rebate = coca_tiers[1]['subscription_rebate']
assert subscription_rebate['rate'] == '0.50' and subscription_rebate['maximum_services'] == 1
assert subscription_rebate['eligible_services'] == ['Netflix', 'Disney+', 'Paramount+', 'YouTube Premium']
assert subscription_rebate['monthly_price_cap_usd'] == '70' and subscription_rebate['shares_monthly_claim_capacity'] is True
assert 'ChatGPT' not in subscription_rebate['eligible_services']
kolo_tiers = tier_data['cards']['kolo']['tiers']
eur_usd = Decimal(str(json.loads((ROOT / 'data/nbu-eur-2026-10-09.json').read_text())[0]['rate'])) / Decimal(data['nbu_usd_uah'])
for tier, expected, purchase_cap in zip(kolo_tiers, ('10', '20'), ('1', '2')):
    assert tier['currency'] == 'EUR' and tier['cap'] == '100'
    assert Decimal(tier['usd_per_currency_unit']) == eur_usd
    assert tier['per_transaction_cap'] == purchase_cap and tier['minimum_purchase'] == '1'
    assert tier['projection_kind'] == 'upper_bound_before_per_transaction_caps'
    assert monthly_cashback(tier, 1000) == (Decimal(expected), Decimal(expected))
    assert monthly_cashback(tier, 20000) == (Decimal(expected) * 20, Decimal('100') * eur_usd)
# A 100 EUR cap is not a 100 USD cap; these are upper bounds before purchase-size caps.
assert monthly_cashback(kolo_tiers[0], 10000) == (Decimal('100'), Decimal('100'))
assert tier_data['cards']['kolo']['sources'][0]['url'] == 'https://help.kolo.xyz/en/articles/13623113-cashback-program'
white_tier = tier_data['cards']['whitebit']['tiers'][0]
assert len(tier_data['cards']['whitebit']['tiers']) == 1
assert white_tier['category_rates']['subscriptions'] == '0.10' and white_tier['category_rates']['groceries'] == '0.01'
assert all(Decimal('0') < Decimal(rate) <= Decimal('1') for rate in white_tier['category_rates'].values())
assert len(white_tier['category_rates']) == 12 and white_tier['active_categories_at_capture'] == []
assert white_tier['maximum_active_categories'] == 3 and white_tier['projection_kind'] == 'upper_bound_after_category_selection'
assert monthly_cashback(white_tier, 1000) == (Decimal('25'), Decimal('25'))
assert monthly_cashback(white_tier, 250) == (Decimal('25'), Decimal('25'))
assert monthly_cashback(white_tier, 100) == (Decimal('10'), Decimal('10'))
bybit_tiers = tier_data['cards']['bybit']['tiers']
assert [monthly_cashback(tier, 1000)[1] for tier in bybit_tiers] == list(map(Decimal, ('5', '20', '10', '20')))
assert monthly_cashback(bybit_tiers[0], 250)[1] == monthly_cashback(bybit_tiers[1], 250)[1]
assert monthly_cashback(bybit_tiers[1], 2500)[1] == Decimal('50')
usd = Decimal(scenario['usd_subscriptions_budget'])
for categories in (Decimal('0'), Decimal('100')):
    threshold = solid_spend_threshold(solid_tiers, usd, categories)
    assert solid_upgrade(solid_tiers, threshold - 1, usd, categories) < 0
    assert solid_upgrade(solid_tiers, threshold + 1, usd, categories) > 0
assert [tier['non_usd_fx_fee'] for tier in solid_tiers] == ['0.015', '0.015']
assert abs(solid_upgrade(solid_tiers, 1000, usd) * 12 - Decimal('-79')) < Decimal('1e-20')
assert abs(solid_upgrade(solid_tiers, 1000, usd, 100) * 12 - Decimal('-7')) < Decimal('1e-20')
assert solid_spend_threshold(solid_tiers, usd).quantize(Decimal('.01')) == Decimal('1658.33')
assert solid_spend_threshold(solid_tiers, usd, 100).quantize(Decimal('.01')) == Decimal('1058.33')
# Equal FX fees give no upgrade savings; above both caps, only the cap difference remains.
assert solid_upgrade(solid_tiers, 1000, 0) == solid_upgrade(solid_tiers, 1000, 1000)
assert abs(solid_upgrade(solid_tiers, 10000, usd) - (Decimal('50') - Decimal('199') / 12)) < Decimal('1e-20')
assert [monthly_cashback(tier, 1000)[1] for tier in tier_data['cards']['okx']['tiers']] == [Decimal('20'), Decimal('40')]
assert all(not tier_data['cards'][card]['tiers'] for card in ('simple', 'keyone', 'trustee_plus'))
snapshot = json.loads((ROOT / 'data/scoring.json').read_text())
funding_tests = json.loads((ROOT / 'data/funding-tests.json').read_text())
scored = score_cards(snapshot, data, tier_data, funding_tests, earning_model)
sorting = json.loads((ROOT / 'data/card-sorting.json').read_text())
def sorting_values(config):
    # Presentation copy can change; money, qualification candidates and order cannot.
    return {'default': config['default'], 'modes': {
        mode: {'order': spec['order'], 'items': {
            identifier: {'value': item['value'], 'rank': item['rank'], 'candidates': [
                {key: value for key, value in candidate.items() if key not in ('tier', 'conditions')}
                for candidate in item.get('candidates', [])
            ]} for identifier, item in spec['items'].items()
        }} for mode, spec in config['modes'].items()
    }}

assert sorting_values(sorting) == sorting_values(card_sorting(data['rows'], tier_data, scored))
modes = sorting['modes']
assert set(modes) == {'score', 'gross', 'potential', 'actual'} and sorting['default'] == 'score'
score_order = sorted(data['rows'], key=lambda row: (-scored[row['id']]['total'], row['name']))
assert modes['score']['order'] == [row['id'] for row in score_order]
for identifier, item in modes['score']['items'].items():
    assert Decimal(item['value']) == scored[identifier]['total']
    assert item['display'] == f'{scored[identifier]["total"]:.1f}/10'
assert modes['gross']['order'] == ['okx', 'coca', 'kolo', 'solid', 'bybit', 'trustee_plus', 'simple', 'keyone', 'whitebit']
assert modes['actual']['order'] == ['okx', 'solid', 'kolo', 'bybit', 'coca', 'whitebit', 'trustee_plus', 'simple', 'keyone']
for mode in ('gross', 'actual'):
    assert all(re.fullmatch(r'≈?\$[0-9]+\.[0-9]{2}', item['display']) for item in modes[mode]['items'].values())
assert modes['potential']['order'] == ['solid', 'coca', 'whitebit', 'kolo', 'bybit', 'okx', 'trustee_plus', 'simple', 'keyone']
for spec in modes.values():
    assert len(spec['order']) == len(set(spec['order'])) == 9
    assert set(spec['order']) == set(spec['items']) == {row['id'] for row in data['rows']}
assert Decimal(modes['actual']['items']['kolo']['value']) == Decimal('3.563619172')
for card, expected in [('solid', '3.53'), ('coca', '3.60'), ('bybit', '3.5687'), ('whitebit', '3.64326104545')]:
    assert Decimal(modes['actual']['items'][card]['value']) == Decimal(expected)
for card, expected in [('solid', '30'), ('coca', '25'), ('bybit', '20'), ('kolo', '20'), ('whitebit', '25'), ('okx', '0'), ('trustee_plus', '0')]:
    assert Decimal(modes['potential']['items'][card]['value']) == Decimal(expected)
assert modes['potential']['items']['solid']['candidates'][1]['net_usd'].startswith('23.416666')
assert all(modes['potential']['items'][card]['value'] is None for card in ('simple', 'keyone'))
solid_row = next(row for row in data['rows'] if row['id'] == 'solid')
assert solid_row['ui_status_finality'] == 'participant_assessed_completed'
assert solid_row['status'] == 'Pending' and solid_row['transaction_ui_completed'] is False
assert solid_row['final_settlement_independently_verified'] is False
assert solid_row['observed_reward']['availability'] == 'participant_accepted_fixed_amount'
assert solid_row['observed_reward']['payout_independently_verified'] is False
assert included_cashback_value(solid_row) == Decimal('0.11')
assert comparison_cost(solid_row) - included_cashback_value(solid_row) == Decimal('3.53')
coca_row = next(row for row in data['rows'] if row['id'] == 'coca')
assert coca_row['status'] == 'Completed' and coca_row['transaction_ui_completed'] is True
assert coca_row['observed_reward']['availability'] == 'participant_accepted_fixed_amount'
assert coca_row['observed_reward']['payout_independently_verified'] is False
assert included_cashback_value(coca_row) == Decimal('0.03')
assert comparison_cost(coca_row) - included_cashback_value(coca_row) == Decimal('3.60')
for row in (solid_row, coca_row):
    assert modes['actual']['items'][row['id']]['note'] == translator('uk')('sort.cashback_included_note', value0=f'{included_cashback_value(row):.2f}')
pending = deepcopy(solid_row)
pending['reward'] = '100'
pending['observed_reward']['availability'] = 'not_confirmed'
assert included_cashback_value(pending) == 0
pending['observed_reward']['availability'] = 'participant_confirmed_credited'
assert included_cashback_value(pending) == 100
assert cashback_potential(solid_row, tier_data['cards']['solid'], 10000)[0] == Decimal('100') - Decimal('199') / 12
unknown_fee = deepcopy(tier_data['cards']['solid'])
unknown_fee['tiers'][1]['annual_fee_usd'] = None
assert cashback_potential(solid_row, unknown_fee, 1000)[0] is None
keyone_program = tier_data['cards']['keyone']
eur_rate = json.loads((ROOT / 'data/nbu-eur-2026-10-09.json').read_text(), parse_float=Decimal)[0]['rate']
keyone_fee = Decimal(keyone_program['annual_premium_eur']) * eur_rate / Decimal(data['nbu_usd_uah']) / 12
keyone_saving_rate = Decimal(keyone_program['crypto_topup_rate_free']) - Decimal(keyone_program['crypto_topup_rate_premium'])
assert keyone_saving_rate == Decimal('.0047')
assert (1000 * keyone_saving_rate - keyone_fee).quantize(Decimal('.01')) == Decimal('-9.18')
assert (keyone_fee / keyone_saving_rate).quantize(Decimal('.01')) == Decimal('2953.19')
assert (Decimal('470') * Decimal('.05') / 12 / Decimal('.02')).quantize(Decimal('.01')) == Decimal('97.92')
white_cap = Decimal(tier_data['cards']['whitebit']['tiers'][0]['cap'])
assert [min(1000 * rate, white_cap) for rate in map(Decimal, ('.01', '.02', '.025', '.10'))] == list(map(Decimal, ('10', '20', '25', '25')))
model = scenario['prime_vs_core_model']
regular = Decimal(scenario['budget_usdt']) * Decimal(model['regular_cashback_increment']) * 12
fx = Decimal(scenario['uah_equivalent_usd']) * Decimal(model['non_usd_fx_fee_reduction']) * 12
assert regular + fx == Decimal(model['annual_regular_and_fx_benefit_usd'])
assert regular + fx + Decimal('100') * Decimal(model['category_increment_over_prime_regular']) * 12 - Decimal(model['annual_tier_cost_usd']) == Decimal(model['annual_net_if_100_monthly_eligible_category_usd'])
usd_subscriptions = sum(Decimal(item['amount']) for item in scenario['subscriptions'] if item['currency'] == 'USD')
assert usd_subscriptions == Decimal(scenario['usd_subscriptions_budget'])
assert sum(Decimal(item['monthly_equivalent_usd_at_nbu']) for item in scenario['subscriptions']) == Decimal(scenario['estimated_total_subscriptions_monthly_usd_at_nbu'])
assert {item['merchant'] for item in scenario['subscriptions']} == {'ChatGPT', 'YouTube Premium', 'Netflix Premium', 'iCloud+ 2TB', 'Apple Music Family', '1Password'}
assert len(scenario['subscriptions']) == 6
assert Decimal(scenario['budget_usdt']) - usd_subscriptions == Decimal(scenario['non_usd_turnover_equivalent_usd']) == Decimal(scenario['uah_equivalent_usd'])
net_without_categories = regular + fx - Decimal(model['annual_tier_cost_usd'])
assert net_without_categories == Decimal(model['annual_net_without_categories_usd'])
assert -net_without_categories / (Decimal(model['category_increment_over_prime_regular']) * 12) == Decimal(model['category_spend_break_even_monthly_usd'])
prices = {item['merchant']: Decimal(item['monthly_equivalent_usd_at_nbu']) for item in scenario['subscriptions']}
for merchant, field in [('Netflix Premium', 'annual_net_if_chatgpt_netflix_first_and_apple_music_eligible_usd'), ('YouTube Premium', 'annual_net_if_chatgpt_youtube_first_and_apple_music_eligible_usd')]:
    assert net_without_categories + (Decimal('100') + prices[merchant] + prices['Apple Music Family']) * Decimal(model['category_increment_over_prime_regular']) * 12 == Decimal(model[field])

public_hashes = set()
all_sources = []
for row in data['rows']:
    debit = Decimal(row['debit'])
    assert Decimal(row['before']) - Decimal(row['after']) == debit
    assert debit - Decimal(row['tx']) == Decimal(row['delta_minus_tx'])
    assert (debit / baseline - 1) * 100 == Decimal(row['gross_overhead_vs_nbu_pct'])
    if row['conditional_net'] is not None:
        assert debit - Decimal(row['reward']) == Decimal(row['conditional_net'])
    for phase, source in row['sources'].items():
        assert source['file'] == f"screenshots/{row['id']}_{phase}.png"
        all_sources.append(source)
terms = json.loads((ROOT / 'data/terms-evidence.json').read_text())
all_sources.extend(terms['images'])
def check_png(raw, dimensions):
    assert raw[:8] == b'\x89PNG\r\n\x1a\n'
    cursor, chunks = 8, []
    while cursor < len(raw):
        length = struct.unpack('>I', raw[cursor:cursor + 4])[0]
        kind = raw[cursor + 4:cursor + 8]
        payload = raw[cursor + 8:cursor + 8 + length]
        assert len(payload) == length
        crc = struct.unpack('>I', raw[cursor + 8 + length:cursor + 12 + length])[0]
        assert zlib.crc32(kind + payload) & 0xffffffff == crc
        chunks.append(kind)
        if kind == b'IHDR':
            assert struct.unpack('>II', payload[:8]) == tuple(dimensions)
        cursor += length + 12
    assert cursor == len(raw) and chunks[0] == b'IHDR' and chunks[-1] == b'IEND'
    assert set(chunks) <= {b'IHDR', b'IDAT', b'IEND'}, 'Unexpected PNG metadata'

for source in all_sources:
    raw = (ROOT / source['file']).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    assert digest == source['sha256']
    public_hashes.add(digest)
    check_png(raw, source.get('dimensions', config['dimensions']))
assert len(public_hashes) == len(all_sources) == 125
assert len([image for image in terms['images'] if image.get('card') == 'coca']) == 2
coca_claim_terms = terms['coca_tiers']['claims_visible']
assert coca_claim_terms['unlimited_accrual_no_monthly_spend_caps'] is True
assert coca_claim_terms['standard_monthly_claim_capacity_usd'] == coca_tiers[1]['cap'] == '25'
assert coca_claim_terms['unclaimed_rewards_carry_over'] is True
assert coca_claim_terms['subscription_services'] == subscription_rebate['eligible_services']
assert coca_claim_terms['subscription_monthly_price_cap_usd'] == subscription_rebate['monthly_price_cap_usd']
assert coca_claim_terms['standard_required_stake_coca'] == coca_tiers[1]['token_amount']
assert any(source.get('url') == 'https://docs.coca.xyz/coca/membership-and-rewards/5-balance-apy' for source in coca_earning['sources'])
assert not any(image.get('card') in {'bybit', 'simple', 'solid'} or image.get('purpose') == 'auto_invest' for image in terms['images'])
for card, term_key in [('bybit', 'bybit_earning'), ('simple', 'simple_earning'), ('solid', 'solid_earning'), ('whitebit', 'whitebit_autoinvest')]:
    assert earning['cards'][card]['source_images_public'] is False
    assert terms[term_key]['source_images_public'] is False
    assert earning['cards'][card]['public_evidence_level'] == terms[term_key]['public_evidence_level'] == 'author_transcription_of_private_app_screenshots'
    assert any(source.get('file') == 'data/participant-confirmations.json' and source['evidence_level'] == 'author_transcription_of_private_app_screenshots' for source in earning['cards'][card]['sources'])
assert terms['solid_earning']['claims_visible']['asset_apy'] == solid_program['displayed_apy_by_asset']
assert terms['solid_earning']['claims_visible']['asset_7_day_apy'] == solid_program['displayed_7_day_apy_by_asset']
assert terms['solid_earning']['claims_visible']['portfolio_total_usd'] == '0.00'
assert terms['simple_earning']['claims_visible']['apr'] == offers['simple']['rate']
assert terms['simple_earning']['claims_visible']['claim_minimum_usdc'] == earning['cards']['simple']['claim_minimum_usdc'] == '1'
assert terms['bybit_earning']['claims_visible']['asset_apr'] == bybit_earning['displayed_apr_by_asset']
assert terms['bybit_earning']['claims_visible']['usdt_auto_earn_enabled'] is True
assert terms['bybit_earning']['claims_visible']['usdc_auto_earn_enabled'] is False
assert terms['bybit_earning']['claims_visible']['usdt_auto_deduction'] == 'Deducted during payment'
whitebit_auto = earning['cards']['whitebit']['other_displayed_product']
assert len([image for image in terms['images'] if image.get('card') == 'whitebit']) == 3
assert whitebit_auto['included_in_earning_model'] is False and whitebit_auto['historical_roi_is_apr_or_apy'] is False
assert offers['whitebit']['rate'] is None and monthly_income(offers['whitebit'], earning_model) is None
assert whitebit_auto['historical_roi_period'] is None
assert whitebit_auto['historical_roi_pct_as_displayed'] == terms['whitebit_autoinvest']['claims_visible']['historical_roi_pct']
assert whitebit_auto['historical_roi_pct_as_displayed']['WBT'] == '4130.41'
assert whitebit_auto['historical_roi_pct_as_displayed']['S'] == '-94.36'
assert terms['whitebit']['claims_visible']['active_categories_count'] == 0
assert terms['whitebit']['claims_visible']['category_rates'] == white_tier['category_rates']
assert terms['whitebit']['claims_visible']['cashback_currencies'] == ['BTC', 'WBT']
assert len(list((ROOT / 'screenshots').glob('*.png'))) == len(all_sources)
assert not list((ROOT / 'screenshots').glob('*.jpeg'))
art = json.loads((ROOT / 'data/card-art.json').read_text())
art_hashes = {}
assert len(art['images']) == 9
assert {item['id'] for item in art['images']} == {row['id'] for row in data['rows']}
assert art['originals_public'] is False and art['normalized_dimensions'] == [960, 600]
assert art['redaction_method'] == 'gaussian_blur' and art['radius_pixels'] == 42
for item in art['images']:
    assert item['kind'] == 'sanitized_card_sample'
    assert item['file'] == f"assets/cards/{item['id']}.png"
    raw = (ROOT / item['file']).read_bytes()
    assert item['dimensions'] == art['normalized_dimensions']
    check_png(raw, item['dimensions'])
    assert raw[25] == 6, 'Card art must have RGBA transparency'
    assert 0 < item['corner_radius_pixels'] < min(x for x in item['original_dimensions']) / 2
    digest = hashlib.sha256(raw).hexdigest()
    assert digest == item['sha256']
    art_hashes[item['file']] = digest
    assert Path(item['original_file']).name == item['original_file']
    x1, y1, x2, y2 = item['crop']
    width, height = item['original_dimensions']
    assert 0 <= x1 < x2 <= width and 34 <= y1 < y2 <= height
    for mask in item['redactions']:
        left, top, right, bottom = mask['box']
        assert x1 <= left < right <= x2 and y1 <= top < bottom <= y2
assert set((ROOT / 'assets/cards').glob('*.png')) == {ROOT / name for name in art_hashes}
for masks in config['images'].values():
    assert all(mask['box'][1] >= 34 for mask in masks), 'Status bar must remain unchanged'

class ReportAudit(HTMLParser):
    def __init__(self, language="uk", page_folder=None):
        super().__init__()
        self.t = translator(language)
        self.page_folder = page_folder or ROOT / ('en' if language == 'en' else '')
        self.images = []
        self.metadata = {}
        self.canonicals = []
        self.alternates = {}
        self.ids = set()
        self.links = []
        self.cards = []
        self.popovers = set()
        self.popover_targets = []
        self.label_targets = []
        self.image_files = []
        self.art_files = []
        self.scripts = []
        self.tier_levels = {}
        self.current_card = None
        self.opening_links = {}
        self.bonus_cards = []
        self.hidden_sort_cards = set()
        self.conditional_cards = set()
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        assert tag != 'iframe'
        if tag == 'meta' and ('name' in attrs or 'property' in attrs):
            key = attrs.get('property', attrs.get('name'))
            assert key not in self.metadata, 'Duplicate metadata'
            self.metadata[key] = attrs.get('content')
        if tag == 'link' and attrs.get('rel') == 'canonical':
            self.canonicals.append(attrs['href'])
        if tag == 'link' and attrs.get('rel') == 'alternate':
            assert attrs['hreflang'] not in self.alternates
            self.alternates[attrs['hreflang']] = attrs['href']
        assert not any(name.lower().startswith('on') for name in attrs), 'Unexpected inline event handler'
        if tag == 'script':
            if attrs.get('type') == 'application/json':
                assert attrs['id'] in {'card-sorting', 'cashback-chart-data'} and set(attrs) == {'type', 'id'}
            elif attrs.get('type') == 'application/ld+json':
                assert attrs == {'type': 'application/ld+json', 'id': 'research-schema'}
            elif attrs.get('src') == 'https://www.googletagmanager.com/gtag/js?id=G-NWFJQ8WLJ7':
                assert set(attrs) == {'src', 'async'}
            elif attrs.get('id') == 'google-analytics':
                assert attrs == {'id': 'google-analytics'}
            else:
                assert set(attrs) == {'src', 'defer'}
                script_path = (self.page_folder / attrs['src']).resolve()
                assert script_path in {ROOT / 'assets/card-sort.js', ROOT / 'assets/analytics.js', ROOT / 'assets/cashback-chart.js', ROOT / 'assets/card-flow.js'}
            self.scripts.append(attrs)
        if attrs.get('id'):
            assert attrs['id'] not in self.ids, 'Duplicate HTML anchor'
            self.ids.add(attrs['id'])
        if tag == 'a':
            self.links.append(attrs['href'])
            if 'open-card' in attrs.get('class', '').split():
                assert self.current_card
                opening = card_links[self.current_card]
                opening_links = self.opening_links.setdefault(self.current_card, [])
                is_referral = bool(opening_links)
                assert len(opening_links) < (2 if opening['referral'] else 1), 'Duplicate opening link'
                assert attrs['href'] == (opening['url'] if is_referral else opening['official_url'])
                assert attrs.get('target') == '_blank'
                label = 'ui.open_with_referral_label' if is_referral else 'ui.open_without_referral_label' if opening['referral'] else 'ui.open_card_label'
                assert attrs.get('aria-label') == self.t(label, value0=next(row['name'] for row in data['rows'] if row['id'] == self.current_card))
                assert attrs.get('rel') == ('noopener sponsored' if is_referral else 'noopener')
                opening_links.append(attrs['href'])
            if 'image-file' in attrs.get('class', '').split():
                assert attrs.get('target') == '_blank' and attrs.get('rel') == 'noopener'
                self.image_files.append(attrs['href'])
        if tag == 'article' and 'card' in attrs.get('class', '').split():
            self.cards.append(attrs['id'])
            self.current_card = attrs['id']
            self.tier_levels[self.current_card] = 0
        if tag == 'div' and 'tier' in attrs.get('class', '').split():
            self.tier_levels[self.current_card] += 1
        if tag == 'div' and 'sort-result' in attrs.get('class', '').split() and 'hidden' in attrs:
            self.hidden_sort_cards.add(self.current_card)
        if tag == 'div' and 'conditional-cost' in attrs.get('class', '').split():
            self.conditional_cards.add(self.current_card)
        if tag == 'p' and 'referral-note' in attrs.get('class', '').split():
            assert self.current_card in self.opening_links
            self.bonus_cards.append(self.current_card)
        if 'popover' in attrs:
            if attrs.get('class') == 'hub-tooltip':
                assert attrs.get('role') == 'tooltip' and attrs['id'].startswith('hub-note-')
            else:
                assert attrs.get('role') == 'dialog' and attrs.get('aria-labelledby')
            self.popovers.add(attrs['id'])
        if attrs.get('popovertarget'):
            assert tag == 'button' and attrs.get('type') == 'button'
            self.popover_targets.append(attrs['popovertarget'])
        if attrs.get('aria-labelledby'):
            self.label_targets.extend(attrs['aria-labelledby'].split())
        if tag == 'img':
            assert attrs.get('alt')
            if 'product-art' in attrs.get('class', '').split():
                self.art_files.append(attrs['src'])
                assert (int(attrs['width']), int(attrs['height'])) == tuple(art['normalized_dimensions'])
                return
            assert not urlsplit(attrs['src']).scheme and attrs.get('loading') == 'lazy'
            source_path = (self.page_folder / attrs['src']).resolve()
            assert source_path.is_relative_to(ROOT / 'screenshots') and source_path.suffix == '.png'
            image = source_path.read_bytes()
            assert (int(attrs['width']), int(attrs['height'])) == struct.unpack('>II', image[16:24]), 'Screenshot intrinsic size must match its pixels'
            self.images.append(hashlib.sha256(image).hexdigest())
    def handle_endtag(self, tag):
        if tag == 'article':
            self.current_card = None

uk_messages = load_messages('uk')
en_messages = load_messages('en')
assert uk_messages.keys() == en_messages.keys(), 'Every message needs both translations'
for key in uk_messages:
    fields = lambda value: {field for _, field, _, _ in Formatter().parse(value) if field is not None}
    assert fields(uk_messages[key]) == fields(en_messages[key]), key
    assert re.findall(r'\{\{([A-Z_]+)\}\}', uk_messages[key]) == re.findall(r'\{\{([A-Z_]+)\}\}', en_messages[key]), key
    assert not re.search('[А-Яа-яІіЇїЄєҐґ]', en_messages[key]), key
english_sorting = json.loads((ROOT / 'data/card-sorting-en.json').read_text())
assert sorting_values(english_sorting) == sorting_values(sorting), 'Language must not change financial results or rankings'

expected_scores = {
    'bybit': [9, 7, 8, 7, 10, 10, 9, 9, 10, 10],
    'coca': [10, 9, 9, 8, 10, 10, 10, 10, 4, 10],
    'keyone': [9, 5, 7, 5, 9, 10, 10, 10, 4, 10],
    'kolo': [9, 9, 9, 5, 10, 8, 7, 8, 6, 10],
    'okx': [9, 10, 7, 6, 10, 10, 10, 10, 5, 10],
    'simple': [9, 5, 7, 9, 10, 10, 7, 10, 8, 10],
    'solid': [10, 8, 10, 10, 10, 10, 8, 10, 7, 10],
    'trustee_plus': [9, 6, 7, 5, 8, 9, 6, 6, 8, 9],
    'whitebit': [9, 4, 9, 5, 10, 10, 8, 7, 9, 10],
}
for identifier, item in scored.items():
    assert [item['scores'][key] for key in CRITERIA] == expected_scores[identifier]
    assert item['total'] == sum(item['scores'].values()) / Decimal(10)
assert scored['solid']['total'] == Decimal('9.3')
assert scored['coca']['total'] == Decimal('9.0')
solid_exit_evidence = snapshot['cards']['solid']['withdrawal_network_evidence']
solid_exit_networks = ['Arbitrum', 'Base', 'BNB Smart Chain', 'Ethereum', 'Fuse']
assert snapshot['cards']['solid']['withdrawal_networks'] == solid_exit_networks
assert solid_exit_evidence['confirmed_in_app']['USDC'] == solid_exit_networks
assert solid_exit_evidence['coming_soon']['USDC'] == ['Polygon']
assert solid_exit_evidence['current_usdt_list_verified'] is False
assert solid_exit_evidence['executed'] == ['Fuse'] and solid_exit_evidence['quoted'] == ['Arbitrum']
assert 'networks' not in snapshot['cards']['solid']['conditional_criteria']
assert snapshot['cards']['solid']['withdrawal_minima']['USDC'] == dict(zip(solid_exit_networks, ['5', '5', '5', '10', None]))
solid_quote = snapshot['cards']['solid']['withdrawal_quote']
assert solid_quote['asset'] == 'USDC' and solid_quote['networks'] == solid_exit_networks[:-1]
assert solid_quote['initial_fee'] == '1.36' and solid_quote['initial_withdrawal_amount'] is None
assert solid_quote['sample_withdrawal_amount'] == '100' and solid_quote['sample_fee'] == '1.41'
assert solid_quote['executed'] is False
assert scored['solid']['values']['minimum_in'] == Decimal('0.01')
assert snapshot['cards']['solid']['confirmed_small_deposit']['network'] == 'Arbitrum'
assert len(snapshot['cards']['kolo']['withdrawal_minima']['USDT']) == 3
assert len(snapshot['cards']['kolo']['withdrawal_minima']['USDC']) == 4
assert scored['simple']['scores']['networks'] == scored['trustee_plus']['scores']['networks']
# The APR bonus applies only to the eligible part of a declining balance.
banded = snapshot['cards']['bybit']['income_offer']
assert monthly_income(banded, earning_model)[0].quantize(Decimal('.01')) == Decimal('1.35')
assert monthly_income(dict(banded, bonus_apr='0.03'), earning_model)[0].quantize(Decimal('.01')) == Decimal('1.20')
for balance in ('0', '50', '100', '1000'):
    flat = dict(earning_model, starting_eligible_balance_usd=balance, ending_eligible_balance_usd=balance)
    expected = (Decimal(balance) * Decimal('.0234') + min(Decimal(balance), Decimal(100)) * Decimal('.05')) * 30 / 365
    assert abs(monthly_income(banded, flat)[0] - expected) < Decimal('1e-20')

logical_pages = ['index.html', 'ranking/index.html'] + ['cards/' + row['id'] + '/index.html' for row in data['rows']]
site_url = os.environ.get('SITE_URL', research['public_url']).strip().rstrip('/')
page_parsers = {}
seo_titles = set()
seo_descriptions = set()
for language in LANGUAGES:
    prefix = 'en/' if language == 'en' else ''
    t = translator(language)
    edition_images, edition_image_links = [], []
    card_questions = [t(f'cards.{identifier}.faq.{n}.question') for identifier in rows for n in range(4)]
    assert len(set(card_questions)) == 36, 'Each card needs its own contextual questions'
    for logical in logical_pages:
        relative = prefix + logical
        page = ROOT / relative
        report = page.read_text()
        parser = ReportAudit(language, page.parent)
        parser.feed(report)
        page_parsers[relative] = parser
        assert report.count('<h1') == 1
        badges = re.findall(r'<a class="score-badge"[^>]*>(.*?)</a>', report)
        assert all(re.fullmatch(r'<strong>\d+\.\d<small>/10</small></strong>', badge) for badge in badges)
        assert len(parser.canonicals) == (1 if site_url else 0)
        assert 'data:image/' not in report and '/Users/' not in report
        assert not re.search(r'\{\{[A-Z_]+\}\}|\[\[[a-zA-Z0-9_.]+\]\]', report)
        assert not re.search(r'\son[a-z]+=', report, re.I)
        assert page.stat().st_size < 250000
        assert f'<html lang="{language}">' in report
        if language == 'en':
            assert not re.search('[А-Яа-яІіЇїЄєҐґ]', report), relative
        assert set(parser.label_targets) <= parser.ids, relative
        assert set(parser.popover_targets) <= parser.popovers, relative
        assert report.count('data-repository-link') == 2
        assert report.count("gtag('config', 'G-NWFJQ8WLJ7');") == 1
        assert sum(script.get('src', '').endswith('/analytics.js') for script in parser.scripts) == 1
        assert report.count('aria-current="page"') == 1
        meta = parser.metadata
        assert meta['author'] == research['author']['name']
        assert meta['google-site-verification']
        assert meta['robots'] == 'index, follow, max-image-preview:large'
        assert meta['og:title'] == meta['twitter:title']
        titles = re.findall(r'<title>(.*?)</title>', report.split('</head>', 1)[0], re.S)
        assert len(titles) == 1 and html.unescape(titles[0]) == meta['og:title']
        assert 25 <= len(meta['og:title']) <= 70
        assert 100 <= len(meta['description']) <= 180
        assert meta['og:title'] not in seo_titles, relative
        assert meta['description'] not in seo_descriptions, relative
        seo_titles.add(meta['og:title'])
        seo_descriptions.add(meta['description'])
        assert meta['og:site_name'] == t('seo.site_name')
        assert 'rel="author"' in report and research['author']['name'] in report
        assert meta['og:description'] == meta['twitter:description'] == meta['description']
        assert meta['og:locale'] == ('uk_UA' if language == 'uk' else 'en_US')
        assert meta['twitter:card'] == 'summary_large_image'
        card_id = logical.split('/')[1] if logical.startswith('cards/') else None
        image_path = f'assets/cards/{card_id}.png' if card_id else f'assets/social/preview-{language}.png'
        image_size = (960, 600) if card_id else (1200, 630)
        image_url = site_url + '/' + image_path if site_url else '../' * (len(Path(relative).parts) - 1) + image_path
        image_alt = t('seo.card_image_alt', value0=rows[card_id]['name']) if card_id else t('page.head.social_image_alt')
        check_png((ROOT / image_path).read_bytes(), image_size)
        assert meta['og:image'] == meta['twitter:image'] == image_url
        assert (int(meta['og:image:width']), int(meta['og:image:height'])) == image_size
        assert meta['og:image:alt'] == meta['twitter:image:alt'] == image_alt
        assert all(not urlsplit(href).path.endswith('index.html') for href in parser.links if not urlsplit(href).scheme)
        if card_id:
            assert meta['og:title'] == t('seo.cards.' + card_id + '.title')
            assert meta['description'] == t('seo.cards.' + card_id + '.description')

        site_url = os.environ.get('SITE_URL', research['public_url']).strip().rstrip('/')
        if site_url:
            directory = logical.removesuffix('index.html')
            page_url = site_url + '/' + prefix + directory
            assert parser.canonicals == [page_url] and meta['og:url'] == page_url
            assert parser.alternates == {'uk': site_url + '/' + directory, 'en': site_url + '/en/' + directory, 'x-default': site_url + '/' + directory}
            schema = json.loads(re.search(r'<script type="application/ld\+json" id="research-schema">(.*?)</script>', report, re.S)[1])
            article = schema['@graph'][0]
            assert article['url'] == page_url and article['headline'] == meta['og:title']
            assert article['author'] == {'@type': 'Person', **research['author']}
            assert article['dateModified'] == research['updated_on'] and article['inLanguage'] == language
            graph = {node['@type']: node for node in schema['@graph']}
            assert schema['@context'] == 'https://schema.org'
            assert len({node['@id'] for node in schema['@graph']}) == len(schema['@graph'])
            assert article['publisher'] == article['author'] and article['isAccessibleForFree'] is True
            assert article['mainEntityOfPage'] == {'@id': page_url + '#webpage'}
            assert article['image'] == {'@type': 'ImageObject', 'url': image_url, 'width': image_size[0], 'height': image_size[1], 'caption': image_alt}
            assert 'aggregateRating' not in json.dumps(schema) and 'Review' not in graph
            website = graph['WebSite']
            webpage = graph['WebPage' if card_id else 'CollectionPage']
            assert website['url'] == site_url + '/' and website['inLanguage'] == list(LANGUAGES)
            assert website['name'] == t('page.head.a_2').strip() and website['alternateName'] == meta['og:site_name']
            assert webpage['url'] == page_url and webpage['name'] == meta['og:title']
            assert webpage['description'] == meta['description'] and webpage['inLanguage'] == language
            assert webpage['isPartOf'] == {'@id': website['@id']}
            assert webpage['mainEntity'] == {'@id': article['@id']}
            assert webpage['primaryImageOfPage'] == article['image']
            if logical != 'index.html':
                breadcrumbs = graph['BreadcrumbList']
                assert webpage['breadcrumb'] == {'@id': breadcrumbs['@id']}
                assert [item['position'] for item in breadcrumbs['itemListElement']] == [1, 2]
                assert [item['item'] for item in breadcrumbs['itemListElement']] == [site_url + '/' + prefix, page_url]
            if card_id:
                assert article['about'] == {'@type': 'Thing', '@id': page_url + '#card', 'name': rows[card_id]['name'], 'url': card_links[card_id]['official_url']}
                assert set(snapshot['cards'][card_id]['sources']) <= set(article['citation'])
            else:
                listing = graph['ItemList']
                assert article['mainEntity'] == {'@id': listing['@id']}
                assert listing['numberOfItems'] == 9 and listing['itemListOrder'] == 'https://schema.org/ItemListOrderDescending'
                expected_order = modes[sorting['default'] if logical == 'index.html' else 'score']['order']
                assert [item['position'] for item in listing['itemListElement']] == list(range(1, 10))
                assert [item['url'] for item in listing['itemListElement']] == [site_url + '/' + prefix + 'cards/' + key + '/' for key in expected_order]
                assert [item['name'] for item in listing['itemListElement']] == [rows[key]['name'] for key in expected_order]
        if logical == 'index.html':
            page_sorting = english_sorting if language == 'en' else sorting
            assert parser.cards == page_sorting['modes'][sorting['default']]['order']
            assert not parser.images and not parser.popovers
            assert 'class="calculation' not in report
            assert report.count('class="score-badge"') == 9
            assert report.count('class="card-details-link"') == 9
            image_links = re.findall(r'<figure class="card-art"><a class="card-art-link" href="([^"]+)" aria-label="[^"]+"><img[^>]+></a></figure>', report)
            assert len(image_links) == 9
            assert image_links == re.findall(r'<a class="card-details-link" href="([^"]+)">', report)
            assert '.card-details-link::after' not in (ROOT / 'assets/site.css').read_text()
            assert report.count('class="purchase-row"') == 9
            assert len(parser.art_files) == 9
            assert 'purchase-heading' in parser.ids
            assert json.loads(re.search(r'<script type="application/json" id="card-sorting">(.*?)</script>', report, re.S)[1]) == page_sorting
            assert len(parser.opening_links) == 9
            if site_url:
                assert len(schema['@graph'][1]['mainEntity']) == 8
                for item in schema['@graph'][1]['mainEntity']:
                    assert html.escape(item['name'], quote=True) in report
                    assert html.escape(item['acceptedAnswer']['text'], quote=True) in report
        elif logical == 'ranking/index.html':
            assert not parser.images and not parser.cards
            assert html.escape(t('pages.choice_title'), quote=True) in report
            assert html.escape(t('pages.choice_description'), quote=True) in report
            matrix = re.search(r'<table class="score-matrix".*?</table>', report, re.S)[0]
            assert matrix.count('<th scope="col">') == 12 and matrix.count('<tr id="score-') == 9
            assert re.findall(r'<tr id="score-([^"]+)">', matrix) == modes['score']['order']
            for identifier, item in scored.items():
                matrix_row = re.search(r'<tr id="score-' + identifier + r'">.*?</tr>', matrix, re.S)[0]
                values = re.findall(r'<td>([0-9]+)\*?</td>', matrix_row)
                assert list(map(int, values)) == expected_scores[identifier]
                assert f'{item["total"]:.1f}</td>' in matrix_row
            chart_config = json.loads(re.search(r'<script type="application/json" id="cashback-chart-data">(.*?)</script>', report, re.S)[1])
            assert len(chart_config['programs']) == 4
            core, prime, starter, standard = chart_config['programs']
            assert prime['samples'][0][1] == 0 and prime['samples'][0][2] < 0
            assert core['samples'][20][1] == 30 and starter['samples'][20][1] == 10
            assert standard['samples'][20][1] == 25
        else:
            identifier = logical.split('/')[1]
            assert parser.cards == [identifier]
            assert report.count('class="detail-summary"') == 1
            assert report.count('class="detail-rating"') == 1
            assert report.count('class="card-rating-panel"') == 1
            rating_panel = re.search(r'<section class="card-rating-panel".*?</section>', report, re.S)[0]
            assert 'class="detail-rating"' in rating_panel and 'class="detail-criteria"' in rating_panel
            assert report.count('class="score-badge"') == 1
            intro = re.search(r'<section class="page-intro card-intro">.*?</section>', report, re.S)[0]
            assert 'score-badge' not in intro
            rating = re.search(r'<div class="detail-rating">.*?<a href="[^"]+ranking/#scoring-method">.*?</a></div>', report, re.S)[0]
            assert f'<strong>{scored[identifier]["total"]:.1f}<small>/10</small></strong>' in rating
            assert f'width:{scored[identifier]["total"] * 10}%' in rating
            assert report.count('class="detail-criteria"') == 1
            criteria = re.search(r'<dl class="detail-criteria".*?</dl>', report, re.S)[0]
            assert criteria.count('class="score-track"') == len(CRITERIA)
            assert 'class="card-score-table"' not in report
            for criterion in CRITERIA:
                criterion_markup = re.search(r'<div><dt><button type="button" popovertarget="score-input-' + criterion + r'">.*?</dd></div>', criteria)[0]
                score = scored[identifier]['scores'][criterion]
                suffix = '*' if criterion in scored[identifier]['conditional'] else ''
                assert f'width:{score * 10}%' in criterion_markup
                assert f'<strong>{score}{suffix}</strong>' in criterion_markup
                score_input = re.search(r'<div class="score-input-popover" id="score-input-' + criterion + r'".*?</div>', report, re.S)[0]
                value = html.escape(value_text(criterion, scored[identifier], snapshot['cards'][identifier], t), quote=True)
                assert value in score_input
                assert f'aria-labelledby="score-input-{criterion}-title"' in score_input
            assert report.index('class="detail-summary"') < report.index('class="detail-rating"') < report.index('class="detail-criteria"') < report.index('class="card-body"')
            assert '<h4 class="card-opening-title">' + html.escape(t('seo.open_card_heading', value0=rows[identifier]['name']), quote=True) + '</h4>' in report
            assert len(parser.art_files) == 1
            assert 'class="card-art-link"' not in report
            faq_block = re.search(r'<section class="section card-faq" id="faq".*?</section>', report, re.S)[0]
            visible_faq = re.findall(r'<details><summary>(.*?)</summary><p>(.*?)</p></details>', faq_block, re.S)
            expected_faq = [(t(f'cards.{identifier}.faq.{n}.question'), t(f'cards.{identifier}.faq.{n}.answer')) for n in range(4)]
            assert [(html.unescape(q), html.unescape(a)) for q, a in visible_faq] == expected_faq
            assert len({q for q, _ in expected_faq}) == 4
            assert report.index('id="card-scores"') < report.index('id="faq"') < report.index('id="sources"')
            assert '<a href="#faq">' in report
            if site_url:
                faq_schema = graph['FAQPage']
                assert faq_schema['@id'] == page_url + '#faq' and faq_schema['inLanguage'] == language
                assert article['hasPart'] == {'@id': faq_schema['@id']}
                assert [(item['name'], item['acceptedAnswer']['text']) for item in faq_schema['mainEntity']] == expected_faq
                assert all(item['@type'] == 'Question' and item['acceptedAnswer']['@type'] == 'Answer' for item in faq_schema['mainEntity'])
            assert report.count('class="process-map"') == 1
            assert report.count('class="balance-map"') == 1
            assert report.count('class="balance-hub"') == 1
            hub_markup = re.search(r'<div class="balance-map">(.*?)</svg>(.*?)</div></div>', report, re.S)
            assert hub_markup
            hub_svg = ET.fromstring(re.search(r'<svg class="hub-links".*?</svg>', report, re.S)[0])
            edges = {path.attrib['d']: path.attrib for path in hub_svg.findall('path')}
            assert edges['M 280 355 H 355']['marker-end'] == 'url(#hub-arrow)'
            assert edges['M 605 355 H 680']['marker-end'] == 'url(#hub-arrow)'
            assert edges['M 480 440 V 515']['marker-end'] == 'url(#hub-arrow)'
            assert any(script.get('src', '').endswith('/assets/card-flow.js') for script in parser.scripts)
            assert 'class="hub-toolbar" hidden' in report
            assert report.count('class="hub-zoom-out"') == 1
            assert report.count('class="hub-zoom-in"') == 1
            assert f'class="hub-reset" title="{html.escape(t("flow.hub.actual_size"), quote=True)}">100%</button>' in report
            hub_keys = {'balance'} | set(re.findall(r'data-process="([a-z]+)"', report))
            for edge in edges.values():
                assert {edge['data-from'], edge['data-to']} <= hub_keys
                assert edge['data-from-port'] in {'top', 'right', 'bottom', 'left'}
                assert edge['data-to-port'] in {'top', 'right', 'bottom', 'left'}
                if edge['class'].endswith('relation'):
                    assert 'marker-start' not in edge and 'marker-end' not in edge
            if identifier == 'solid':
                assert 'M 355 110 H 280' in edges  # Cashback goes to Savings.
                assert 'M 480 195 V 270' not in edges
            elif identifier in {'coca', 'bybit'}:
                assert 'M 480 195 V 270' in edges
            else:
                assert 'M 480 195 V 270' not in edges
            process_links = re.findall(r'class="hub-process ([a-z]+)" data-process="[a-z]+"><a class="hub-process-toggle" href="#flow-([a-z]+)"', report)
            assert report.count('class="hub-info"') == len(process_links)
            assert report.count('class="hub-open" aria-hidden="true">+</span>') == len(process_links)
            for key, target in process_links:
                assert f'aria-describedby="hub-note-{key}"' in report
                assert f'popovertarget="hub-note-{key}"' in report
                assert f'class="hub-tooltip" id="hub-note-{key}" popover' in report
                assert html.escape(t('flow.hub.info', value0=t('flow.' + key)), quote=True) in report
            assert process_links and all(key == target for key, target in process_links)
            assert len(process_links) == report.count('<details class="process-flow">')
            for key, target in process_links:
                assert re.search(r'<details class="process-flow"><summary>.*?</summary><div class="flow-routes[^"]*" id="flow-' + target + '">', report)
            assert 'class="money-cycle"' not in report
            for process in ['funding', 'payment', 'cashback', 'withdrawal']:
                assert 'flow-' + process in parser.ids
            flow_markup = re.search(r'<div class="process-map">.*?</section>', report, re.S)[0]
            assert 'class="flow-node"' in flow_markup
            assert 'class="flow-status test"' in flow_markup
            assert 'class="flow-status app"' in flow_markup
            for route in re.findall(r'<figure class="flow-route">(.*?)</figure>', flow_markup, re.S):
                assert 2 <= route.count('class="flow-node"') <= 5
                assert route.count('class="flow-status ') == route.count('class="flow-node"')
                assert '<figcaption>' in route and 'href="#' in route
            if identifier == 'solid':
                assert '19.997 USDT' in flow_markup and '0.33 USDT' in flow_markup
                assert '100 USDC' in flow_markup and '1.41 USDC' in flow_markup
                for network in solid_quote['networks']:
                    assert 'USDC / ' + network in flow_markup
                quote_note = t('pages.solid_withdrawal_quote', value0='05.11.2026', value1='1.36', value2='100', value3='1.41')
                assert html.escape(quote_note, quote=True) in report
                assert 'Fuse' in report and html.escape(t('pages.no_minimum'), quote=True) in report
                assert 'flow-level' in parser.ids and 'flow-referral' in parser.ids
                assert html.escape(t('flow.solid_combined'), quote=True) in flow_markup
            if identifier in {'whitebit', 'trustee_plus'}:
                assert html.escape(t('flow.no_outcome'), quote=True) in flow_markup
            if identifier == 'trustee_plus':
                assert '9.945677 USDT' in flow_markup and '11.885677 USDT' in flow_markup
            if identifier == 'simple':
                assert flow_markup.count('9.989909 USDC') >= 3
            if identifier == 'bybit':
                assert '36 × 0.002 = 0.072 USDT' in flow_markup
                assert html.escape(t('flow.bybit_points_pending'), quote=True) in flow_markup
            assert report.count('<details class="calculation" open>') == 1
            if included_cashback_value(rows[identifier]):
                expected_cashback = '<dt>' + html.escape(t('sort.actual_metric'), quote=True) + '</dt><dd>' + html.escape(modes['actual']['items'][identifier]['display'], quote=True) + '</dd>'
                assert expected_cashback in report
            funding_block = re.search(r'<section class="panel funding-assets".*?</section>', report, re.S)[0]
            assert '<summary' not in funding_block and 'class="route-table"' in funding_block
            assert '<h3 id="funding-assets-title">' + html.escape(t('pages.funding_assets'), quote=True) + '</h3>' in funding_block
            assert report.count('class="score-network-list"') == 1
            assert html.escape(t('pages.withdrawal_networks'), quote=True) in report
            assert 'card-scores' in parser.ids and 'test-evidence' in parser.ids
            assert report.index('id="test-evidence"') < report.index('id="cycle"') < report.index('id="card-scores"')
            assert report.index('href="#test-evidence"') < report.index('href="#cycle"') < report.index('href="#card-scores"')
            assert '<h2>' + html.escape(t('pages.historical'), quote=True) + '</h2>' in report
            assert 'criterion-explanations' not in report and 'card-criterion-' not in report
            for criterion in CRITERIA:
                expected_href = ('../' * (len(Path(relative).parts) - 1)) + prefix + 'ranking/#criterion-' + criterion
                assert expected_href in parser.links, (relative, criterion)
            assert parser.opening_links == {identifier: [card_links[identifier]['official_url'], card_links[identifier]['url']]}
            assert set(parser.popovers) == {'hub-note-' + key for key, target in process_links} | {'score-input-' + criterion for criterion in CRITERIA} | {'evidence-' + identifier} | ({'evidence-prime'} if identifier == 'solid' else set())
            for section in ['cashback-tiers', 'earning', 'funding-summary', 'losses']:
                assert report.count('class="calculation ' + section + '"') == 1
            for key in ['experience', 'funding', 'note']:
                assert html.escape(t('cards.' + identifier + '.' + key), quote=True) in report
            historical_income = re.search(r'<details class="calculation earning".*?</details>', report, re.S)[0]
            assert 'screenshots/' not in historical_income
            assert html.escape(t('pages.historical_income'), quote=True) in historical_income
            edition_images.extend(parser.images)
            edition_image_links.extend(hashlib.sha256((page.parent / href).read_bytes()).hexdigest() for href in parser.image_files)
    assert len(edition_images) == len(all_sources) and set(edition_images) == public_hashes
    assert set(edition_image_links) == public_hashes

assert len(seo_titles) == len(seo_descriptions) == len(page_parsers) == 22

for relative, parser in page_parsers.items():
    page = ROOT / relative
    for href in parser.links:
        url = urlsplit(href)
        if url.scheme:
            assert url.scheme in {'https', 'http'}
            continue
        target = (page.parent / unquote(url.path)).resolve() if url.path else page
        assert target.is_relative_to(ROOT) and 'private' not in target.relative_to(ROOT).parts
        if target.is_dir():
            target = target / 'index.html'
        assert target.is_file(), (relative, href)
        if url.fragment:
            target_parser = page_parsers.get(str(target.relative_to(ROOT)))
            assert target_parser is not None and unquote(url.fragment) in target_parser.ids, (relative, href)

if site_url:
    ns = {'s': 'http://www.sitemaps.org/schemas/sitemap/0.9', 'x': 'http://www.w3.org/1999/xhtml'}
    entries = ET.parse(ROOT / 'sitemap.xml').findall('s:url', ns)
    assert len(entries) == 22
    assert {entry.findtext('s:loc', namespaces=ns) for entry in entries} == {site_url + '/' + path.removesuffix('index.html') for path in page_parsers}
    for entry in entries:
        assert entry.findtext('s:lastmod', namespaces=ns) == research['updated_on']
        assert len(entry.findall('x:link', ns)) == 3
        relative_page = entry.findtext('s:loc', namespaces=ns).removeprefix(site_url + '/') + 'index.html'
        assert {link.attrib['hreflang']: link.attrib['href'] for link in entry.findall('x:link', ns)} == page_parsers[relative_page].alternates


def study_html(language):
    prefix = 'en/' if language == 'en' else ''
    return '\n'.join((ROOT / prefix / 'cards' / row['id'] / 'index.html').read_text() for row in data['rows'])

confirmations = json.loads((ROOT / 'data/participant-confirmations.json').read_text())
solid_completion = [claim for claim in confirmations['claims'] if claim['evidence_level'] == 'participant_assessed_completed_payment']
assert len(solid_completion) == 1 and solid_completion[0]['card'] == 'solid'
assert confirmations['claims'][0]['evidence_level'] == 'participant_confirmed_historical_payout'
currency_claims = [claim for claim in confirmations['claims'] if claim['evidence_level'] == 'participant_confirmed_test_card_currency']
assert len(currency_claims) == 1
assert currency_claims[0]['card_currencies'] == {row['id']: row['card_currency'] for row in data['rows']}
issuer_claims = {claim['card']: claim for claim in confirmations['claims'] if claim['evidence_level'] == 'participant_confirmed_test_card_issuer'}
assert set(issuer_claims) == {'okx', 'bybit', 'solid', 'kolo', 'keyone', 'coca', 'simple', 'whitebit'}
for card, claim in issuer_claims.items():
    assert claim['issuer_reported'] == issuers['entries'][card]['participant_reported_issuer']
    assert claim['screenshots_in_public_dataset'] is False
okx = rows['okx']
assert okx['reward'] == '0' and okx['conditional_net'] == okx['debit']
assert okx['reward_eligibility']['required_spending_asset'] == 'USDG'
assert okx['reward_eligibility']['tested_spending_asset'] == 'USDT'
assert okx['reward_eligibility']['eligible_for_cashback'] is False
assert okx['reward_eligibility']['usdg_available_on_my_account'] is False
assert next(item for item in confirmations['claims'] if item['card'] == 'okx')['evidence_level'] == 'participant_report_rule_and_account_availability'
assert rows['kolo']['ui_status_finality'] == 'participant_confirmed_final'
btc_quote = json.loads((ROOT / 'data/btc-usd-valuation-2026-10-09.json').read_text())
assert btc_quote['requested_date'] == data['test_date']
assert btc_quote['response']['data']['base'] == 'BTC' and btc_quote['response']['data']['currency'] == 'USD'
valuation = rows['kolo']['reward_valuation']
assert valuation['price_usd_per_btc'] == btc_quote['response']['data']['amount'] == '82976.035'
assert Decimal(rows['kolo']['observed_reward']['amount']) * Decimal(valuation['price_usd_per_btc']) == Decimal(valuation['usd_value']) == Decimal('0.066380828')
assert Decimal(rows['kolo']['debit']) - Decimal(valuation['usd_value']) == Decimal(valuation['net_value_usd']) == Decimal('3.563619172')
assert Decimal('3.53') < Decimal(valuation['net_value_usd']) < Decimal('3.5687')
assert rows['kolo']['observed_reward']['availability'] == 'participant_confirmed_amount_pending_credit'
history = rows['kolo']['historical_cashback_credit']
assert history['amount_btc'] == '0.00000443' and history['payments_count'] == 2
assert history['test_purchase_credit'] is False and history['absolute_credit_date_verified'] is False
assert history['source_file'] == rows['kolo']['sources']['cashback_history']['file']
assert rows['kolo']['observed_reward']['amount'] == '0.0000008'
assert rows['kolo']['observed_reward']['payout_independently_verified'] is False
assert rows['kolo']['observed_reward']['mechanism_confirmed_by_historical_credit'] is True
historical = json.loads((ROOT / 'data/historical.json').read_text())
purchases = historical['kolo_cashback_purchases']
assert len(purchases) == history['payments_count'] == 2
assert sum(Decimal(item['cashback_btc_shown']) for item in purchases) == Decimal(history['amount_btc'])
assert history['purchase_source_files'] == [item['source_file'] for item in purchases]
assert all(item['source_file'] in {source['file'] for source in all_sources} for item in purchases)
usd_example = next(item for item in historical['usd_tests'] if item['card'] == 'kolo')
assert (Decimal(usd_example['debit']) / Decimal(usd_example['merchant_usd']) - 1) * 100 == Decimal(usd_example['gross_overhead_pct'])
assert usd_example['merchant'] == 'OpenRouter' and usd_example['net_usd_after_cashback'] is None
okx_usd = next(item for item in historical['usd_tests'] if item['card'] == 'okx')
assert okx_usd['source_file'] == rows['okx']['sources']['historical_usd']['file']
assert okx_usd['previous_reported_debit'] == okx_usd['merchant_usd'] == '5.80'
assert okx_usd['debit'] == '5.75' and okx_usd['network_fee_paid_by'] == 'OKX'
assert Decimal(okx_usd['debit']) - Decimal(okx_usd['merchant_usd']) == Decimal(okx_usd['debit_minus_merchant_nominal_usdt']) == Decimal('-0.05')
assert (Decimal(okx_usd['debit']) / Decimal(okx_usd['merchant_usd']) - 1) * 100 == Decimal(okx_usd['gross_overhead_pct'])
assert okx_usd['cashback_included'] == '0'
solid_usd_examples = [item for item in historical['usd_tests'] if item['card'] == 'solid']
assert len(solid_usd_examples) == 2
for example, phase, amount, cashback, net in zip(solid_usd_examples, ('historical_usd', 'historical_chatgpt'), ('5.80', '100.00'), ('0.17', '3.00'), ('5.63', '97.00')):
    assert example['source_file'] == rows['solid']['sources'][phase]['file']
    assert example['debit'] == amount and example['reward_shown'] == cashback
    assert Decimal(example['debit']) - Decimal(example['reward_shown']) == Decimal(example['conditional_net_usd']) == Decimal(net)
    assert example['cashback_type_as_displayed'] == 'Standard' and example['cashback_rate_as_displayed'] == '0.03'
    assert example['payout_independently_verified'] is False and example['exact_crypto_debit'] is None
    assert example['status_at_observation'] == 'Pending'
simple_usd_examples = [item for item in historical['usd_tests'] if item['card'] == 'simple' and item.get('source_file')]
assert {item['merchant'] for item in simple_usd_examples} == {'Apple', 'OpenAI ChatGPT'}
for example in simple_usd_examples:
    phase = 'historical_apple' if example['merchant'] == 'Apple' else 'historical_chatgpt'
    assert example['source_file'] == rows['simple']['sources'][phase]['file']
    assert example['asset'] == 'USDC' and example['status_as_displayed'] == 'Завершено'
    assert example['exchange_rate_as_displayed'] == '1 USDC = 1 USD'
    assert Decimal(example['debit']) == Decimal(example['merchant_usd'])
    assert Decimal(example['gross_overhead_pct']) == Decimal(example['debit_minus_merchant_nominal_usdc']) == 0
assert {item['debit'] for item in simple_usd_examples} == {'99', '100'}
bybit_usd = next(item for item in historical['usd_tests'] if item['card'] == 'bybit')
assert bybit_usd['status_as_displayed'] == 'Successful' and bybit_usd['merchant_mcc'] == '5734'
assert bybit_usd['source_files'] == [rows['bybit']['sources'][phase]['file'] for phase in ('historical_usd', 'historical_usd_details', 'historical_usd_points', 'historical_usd_assets')]
assert Decimal(bybit_usd['total_transaction_usd']) - Decimal(bybit_usd['transaction_amount_usd']) == Decimal(bybit_usd['visible_card_surcharge_usd']) == 0
assert bybit_usd['credited_points'] == bybit_usd['points_assessment']['points'] == '58'
assert bybit_usd['points_assessment']['usdt_per_point'] == rows['bybit']['points_assessment']['usdt_per_point']
assert Decimal('58') * Decimal(bybit_usd['points_assessment']['usdt_per_point']) == Decimal(bybit_usd['points_assessment']['value_usdt']) == Decimal('0.116')
assert Decimal(bybit_usd['debit']) - Decimal('0.116') == Decimal(bybit_usd['conditional_net_usdt']) == Decimal('5.7659')
assert (Decimal('5.7659') / Decimal(bybit_usd['merchant_usd']) - 1) * 100 == Decimal(bybit_usd['conditional_net_overhead_pct'])
assert bybit_usd['exact_crypto_debit_verified'] is True and bybit_usd['reward_payout_verified'] is False
assert bybit_usd['screen_shows_crypto_amount_in'] == 'USD in card screens; USDT in asset history' and bybit_usd['pay_with_crypto_usd'] == '5.80'
assert purchases[1]['funding_components'] == [{'amount': '2.2', 'asset': 'USDT'}, {'amount': '10', 'asset': 'EUR'}]
assert rows['kolo']['reward'] is None and rows['kolo']['conditional_net'] is None
assert next(claim for claim in confirmations['claims'] if claim['evidence_level'] == 'participant_confirmed_btc_amount_pending_credit')['amount_shown'] == '0.0000008'
assert rows['whitebit']['observed_reward']['availability'] == 'participant_confirmed_credited'
whitebit_reward = rows['whitebit']['observed_reward']
assert rows['whitebit']['transaction_ui_completed'] is True and rows['whitebit']['status'] == 'Успішно'
assert rows['whitebit']['final_transaction']['status'] == 'Успішно'
assert rows['whitebit']['final_transaction']['card_amount_usd'] == '3.57'
assert rows['whitebit']['final_transaction']['spent_amount'] == '3.82'
assert whitebit_reward['amount'] == whitebit_reward['credited_balance_btc_as_displayed'] == '0.00000213'
assert whitebit_reward['amount_at_initial_capture'] == '0.00000215'
assert whitebit_reward['credit_independently_verified'] is True and whitebit_reward['credit_observed_on'] == '2026-10-12'
assert whitebit_reward['usd_equivalent_as_displayed'] == '0.17' and whitebit_reward['usd_equivalent_is_approximate'] is True
assert whitebit_reward['last_withdrawal_usd_as_displayed'] == '0'
assert whitebit_reward['source_file'] == rows['whitebit']['sources']['cashback_credited']['file']
assert rows['whitebit']['sources']['cashback_credited']['dimensions'] == [1179, 2556]
assert modes['actual']['items']['whitebit']['note'] == translator('uk')('sort.btc_credited_note')
for card in ('kolo', 'whitebit'):
    row = rows[card]
    assert row['observed_reward']['credited_at'] is None
    assert row['observed_reward']['payout_independently_verified'] is False
    assert row['reward_valuation']['quote_time_utc'] == btc_quote['response_time_utc']
    assert row['reward_valuation']['price_usd_per_btc'] == btc_quote['response']['data']['amount']
    assert included_cashback_value(row) == Decimal(row['reward_valuation']['usd_value'])
    assert 'credit-time price' in row['reward_valuation']['basis']
    unconfirmed_btc = deepcopy(row)
    unconfirmed_btc['observed_reward']['availability'] = 'not_confirmed'
    assert included_cashback_value(unconfirmed_btc) == 0
assert included_cashback_value(rows['whitebit']) == Decimal('0.17673895455')
assert Decimal(rows['whitebit']['reward_valuation']['net_value_usd']) == Decimal('3.64326104545')
assert len([claim for claim in confirmations['claims'] if claim['evidence_level'] == 'participant_requested_btc_valuation_before_credit']) == 2
assert rows['trustee_plus']['ui_status_finality'] == 'participant_likely_final'
tp_terms = json.loads((ROOT / 'data/trustee-points-terms.json').read_text())
assert tp_terms['evidence_level'] == 'participant_supplied_terms_excerpt'
assert tp_terms['source_url'] is None and tp_terms['independently_verified'] is False
points = rows['trustee_plus']['points_assessment']
assert Decimal(points['cashback_deduction_usd']) == Decimal(tp_terms['comparison_cashback_deduction_usd']) == 0
assert rows['trustee_plus']['observed_reward']['amount'] == '15'
assert rows['trustee_plus']['observed_reward']['cash_value'] is None
assert rows['trustee_plus']['reward'] is None and rows['trustee_plus']['conditional_net'] is None
receipt = rows['trustee_plus']['receipt']
assert Decimal(receipt['amount']) - Decimal(points['cashback_deduction_usd']) == Decimal(points['net_cost_usdc']) == Decimal('3.648467')
assert receipt['amount'] == '3.648467' and receipt['asset'] == 'USDC' and receipt['merchant_amount_uah'] == data['merchant_amount_uah']
assert receipt['transaction_date'] == data['test_date'] and receipt['explicit_settlement_status'] is None
assert Decimal(receipt['amount']).quantize(Decimal('0.01')) == Decimal(rows['trustee_plus']['debit'])
assert rows['trustee_plus']['final_settlement_independently_verified'] is False

assert okx['transaction_ui_completed'] is True and okx['final_transaction']['spent_amount'] == '3.49'
assert comparison_cost(okx) == Decimal('3.49') and okx['debit'] == '3.52', 'Final token amount must override the initial USD snapshot'
assert okx['final_transaction']['card_amount_usd'] == okx['tx'] == '3.52'
assert rows['bybit']['transaction_ui_completed'] is True and rows['bybit']['final_transaction']['card_amount_usd'] == '3.59'
assert rows['bybit']['final_transaction']['spent_amount'] == '3.6407'
assert comparison_cost(rows['bybit']) == Decimal('3.6407'), 'Reconciled USDT history must override the initial USD balance snapshot'
assert rows['bybit']['observed_reward']['amount'] == '36' and rows['bybit']['observed_reward']['availability'] == 'participant_confirmed_credited'
assert rows['bybit']['observed_reward']['cash_conversion_verified'] is False
points = rows['bybit']['points_assessment']
assert Decimal(points['points']) * Decimal(points['usdt_per_point']) == included_cashback_value(rows['bybit']) == Decimal('0.072')
assert comparison_cost(rows['bybit']) - included_cashback_value(rows['bybit']) == Decimal('3.5687')
quote = rows['bybit']['conversion_quote']
assert (quote['input_amount'], quote['output_amount'], quote['shown_usdt_per_usd'], quote['shown_conversion_fee_usdt']) == ('3.6407', '3.59', '1.0141', '0.0328')
assert quote['input_asset'] == 'USDT' and quote['output_asset'] == 'USD'
input_amount, output_amount, rate = map(Decimal, (quote['input_amount'], quote['output_amount'], quote['shown_usdt_per_usd']))
assert abs(input_amount - output_amount * rate) <= output_amount * Decimal('0.00005') + Decimal('0.00005'), 'Amounts must agree within displayed rounding'
assert quote['fee_inclusion'] == 'included_in_input_amount; not added again'
assert input_amount - Decimal(rows['bybit']['reward']) == Decimal('3.5687')
assert (input_amount / baseline - 1) * 100 > Decimal('3.35')
assert quote['final_token_ledger_reconciled'] is True
bybit_ledger = rows['bybit']['asset_history']
assert bybit_ledger['source_file'] == rows['bybit']['sources']['asset_history']['file']
assert rows['bybit']['final_transaction']['spent_source_file'] == bybit_ledger['source_file']
assert rows['bybit']['final_transaction']['token_ledger_reconciled'] is True
assert bybit_ledger['crypto_spent_usdt'] == quote['input_amount']
assert bybit_ledger['converted_usd'] == quote['output_amount']
historical_ledger = bybit_usd['asset_history']
assert historical_ledger['source_file'] == rows['bybit']['sources']['historical_usd_assets']['file']
assert historical_ledger['additional_debit_confirmed_fee'] is False
assert historical_ledger['purchase_attribution_independently_verified'] is False
assert Decimal(historical_ledger['crypto_sale_usdt']) + Decimal(historical_ledger['additional_debit_usdt']) == Decimal(bybit_usd['debit']) == Decimal('5.8819')
assert (Decimal(bybit_usd['debit']) / Decimal(bybit_usd['merchant_usd']) - 1) * 100 == Decimal(bybit_usd['gross_overhead_pct'])
for ledger, expected_debit in ((bybit_ledger, '3.6407'), (historical_ledger, '5.8819')):
    entries = ledger['entries']
    token_debits = [-Decimal(item['amount']) for item in entries if item['asset'] == 'USDT' and Decimal(item['amount']) < 0]
    assert sum(token_debits) == Decimal(expected_debit), 'Count token debits, not internal redemptions or the USD leg again'
    redemption = next(item for item in entries if item['label_as_displayed'].startswith('Savings Redemption'))
    sale = next(item for item in entries if item['label_as_displayed'] == 'Продаж USDT')
    assert Decimal(redemption['amount']) == -Decimal(sale['amount']) == Decimal(ledger['internal_redemption_usdt'])
    assert Decimal(redemption['available_balance_as_displayed']) + Decimal(sale['amount']) == Decimal(sale['available_balance_as_displayed'])
    assert sum(Decimal(item['amount']) for item in entries if item['asset'] == 'USD') == 0
for lang in ('uk', 'en'):
    t = translator(lang)
    report = study_html(lang)
    assert html.escape(t('ui.asset_history_caption'), quote=True) in report
    assert html.escape(t('ui.historical_usd_assets_caption'), quote=True) in report
assert [row['id'] for row in data['rows']] == ['okx', 'coca', 'kolo', 'solid', 'bybit', 'trustee_plus', 'simple', 'keyone', 'whitebit']
onchain = json.loads((ROOT / 'data/onchain-summary.json').read_text())
assert len(onchain['rows']) == 4
chain_rows = {row['card']: row for row in onchain['rows'] if row['scope'] == 'controlled_uah_purchase'}
assert set(chain_rows) == {'solid', 'keyone'}
assert chain_rows['solid']['source_token'] == 'WEUR' and chain_rows['solid']['transaction_type'] == 'MasterAccount-Debit-Settlement'
assert chain_rows['keyone']['source_token'] == 'WUSD' and chain_rows['keyone']['transaction_type'] == 'Card-Debit-POS'
assert all(row['transaction_currency_decoded'] == 'EUR' and row['execution_status'] == 'Success' for row in chain_rows.values())
assert Decimal(chain_rows['keyone']['source_amount_rounded_6dp']).quantize(Decimal('0.01')) == Decimal(rows['keyone']['debit'])
assert rows['solid']['final_settlement_independently_verified'] is False
historical_chain_rows = [row for row in onchain['rows'] if row['scope'] == 'historical_usd_purchase']
assert {row['merchant'] for row in historical_chain_rows} == {'OpenRouter', 'OpenAI ChatGPT'}
for chain_row in historical_chain_rows:
    assert chain_row['card'] == 'solid' and chain_row['execution_status'] == 'Success'
    assert chain_row['transaction_type'] == 'MasterAccount-Debit-Settlement'
    assert chain_row['transaction_currency_decoded'] == 'USD' and chain_row['source_token'] == 'WUSD'
    assert chain_row['source_token_decimals'] == 18 and chain_row['matches_displayed_usd_at_6dp'] is True
    assert Decimal(chain_row['transaction_amount_raw']) / Decimal(10**18) == Decimal(chain_row['card_amount_usd'])
    assert Decimal(chain_row['source_amount_rounded_6dp']) == Decimal(chain_row['card_amount_usd'])
    example = next(item for item in solid_usd_examples if item['merchant'] == chain_row['merchant'])
    assert Decimal(example['debit']) == Decimal(chain_row['card_amount_usd'])
    assert example['onchain_assessment']['exact_crypto_debit_verified'] is False
    assert chain_row['cashback_payout_verified_by_this_event'] is False

funding_tests = json.loads((ROOT / 'data/funding-tests.json').read_text())
assert len(funding_tests['tests']) == 9
funding_test = funding_tests['tests'][0]
assert funding_test['card'] == 'bybit' and funding_test['network'] == 'Polygon'
assert funding_test['onchain_asset_as_displayed'] == 'USDT0' and funding_test['account_asset_as_displayed'] == 'USDT'
assert Decimal(funding_test['sent_token_amount']) == Decimal(funding_test['onchain_recipient_amount']) == Decimal(funding_test['credited_token_amount']) == 10
assert Decimal(funding_test['sent_token_amount']) - Decimal(funding_test['credited_token_amount']) == Decimal(funding_test['token_credit_shortfall']) == Decimal(funding_test['deposit_fee_deducted_from_token_credit']) == 0
assert Decimal(funding_test['available_token_balance_after_credit']) - Decimal(funding_test['credited_token_amount']) == Decimal(funding_test['residual_before_credit_inferred']) == Decimal('0.000085046615')
assert Decimal(funding_test['available_token_balance_after_credit']).quantize(Decimal('0.0001')) == Decimal(funding_test['total_capital_as_displayed'])
assert funding_test['manual_card_transfer_required'] is False
assert funding_test['spending_power_shortfall_is_proven_deposit_fee'] is False
assert Decimal(funding_test['credited_token_amount']) / Decimal(funding_test['valuation_assessment']['reference_usdt_per_usd']) >= Decimal(funding_test['spending_power_after_usd']) - Decimal('0.005')
assert (Decimal(funding_test['credited_token_amount']) / Decimal(funding_test['valuation_assessment']['reference_usdt_per_usd'])).quantize(Decimal('0.01')) == Decimal('9.86')
assert funding_test['network_fee']['asset'] == 'POL' and funding_test['network_fee']['payer'] == 'sending_wallet'
assert Decimal(funding_test['network_fee']['amount']) > 0 and Decimal(funding_test['network_fee']['explorer_displayed_usd']) < Decimal('0.01')
assert funding_test['timing']['exact_spend_unlock_time_verified'] is False
phases = ('funding_before', 'funding_waiting', 'funding_after', 'funding_paywith', 'funding_balance', 'funding_credit')
assert funding_test['source_files'] == [rows['bybit']['sources'][phase]['file'] for phase in phases]
assert rows['bybit']['funding_reported']['amount'] == '5', 'New top-up must not overwrite initial controlled funding'
assert comparison_cost(rows['bybit']) == Decimal('3.6407')
for phase in phases:
    source = rows['bybit']['sources'][phase]
    assert source['kind'] == 'funding_test'
    assert source['dimensions'] == ([1179, 685] if phase == 'funding_credit' else [590, 1280])
for lang in ('uk', 'en'):
    report = study_html(lang)
    t = translator(lang)
    for phase in phases:
        assert html.escape(t('ui.' + phase + '_caption'), quote=True) in report

coca_funding = next(item for item in funding_tests['tests'] if item['card'] == 'coca')
assert coca_funding['status_as_displayed'] == 'Completed'
assert Decimal(coca_funding['sent_token_amount']) == Decimal(coca_funding['onchain_recipient_amount']) == 10
assert Decimal(coca_funding['quoted_usd_per_usdt']) * Decimal(coca_funding['sent_token_amount']) == Decimal(coca_funding['quoted_amount_usd']) == Decimal('9.9200')
assert Decimal(coca_funding['credited_card_amount_usd']) == Decimal(coca_funding['card_balance_after_usd']) == Decimal('9.96')
shortfall = Decimal(coca_funding['sent_token_amount']) - Decimal(coca_funding['credited_card_amount_usd'])
assert shortfall == Decimal(coca_funding['displayed_shortfall_usd']) == Decimal('0.04')
assert shortfall / Decimal(coca_funding['sent_token_amount']) * 100 == Decimal(coca_funding['displayed_shortfall_pct']) == Decimal('0.4')
credit = coca_funding['credit_execution']
assert credit['network'] == 'Base' and credit['transaction_type'] == 'MigrateSynthetic' and credit['transaction_currency'] == 'WUS'
assert Decimal(credit['transaction_amount']) == Decimal(credit['target_amount']) == Decimal(credit['balance_increase']) == Decimal('9.969083')
assert Decimal(credit['target_amount']) - Decimal(coca_funding['credited_card_amount_usd']) == Decimal(credit['displayed_card_amount_difference']) == Decimal('0.009083')
assert Decimal(credit['target_amount']).quantize(Decimal('0.01')) == Decimal('9.97')
assert credit['displayed_card_amount_matches_rounded_2dp'] is False
assert Decimal('10') - Decimal(credit['target_amount']) == Decimal(credit['shortfall_vs_sent_nominal_usd'])
assert Decimal(credit['shortfall_vs_sent_nominal_usd']) / Decimal('10') * 100 == Decimal(credit['shortfall_pct'])
assert credit['user_paid_gas_verified'] is False and credit['gas_added_to_sender_cost'] is False
assert coca_funding['network_fee']['asset'] == 'ETH' and coca_funding['network_fee']['payer'] == 'sending_wallet'
coca_phases = ('funding_before', 'funding_method', 'funding_quote', 'funding_after', 'funding_completed')
assert coca_funding['source_files'] == [rows['coca']['sources'][phase]['file'] for phase in coca_phases]
assert not any('funding_account' in source['file'] for source in all_sources), 'Private Earning account screenshot must not be published'
assert comparison_cost(rows['coca']) == Decimal('3.63'), 'New deposit does not change controlled purchase cost'
for lang in ('uk', 'en'):
    report = study_html(lang)
    t = translator(lang)
    for phase in coca_phases:
        assert html.escape(t('ui.' + phase + '_caption'), quote=True) in report

keyone_funding = next(item for item in funding_tests['tests'] if item['card'] == 'keyone')
assert keyone_funding['network'] == 'Base' and keyone_funding['status_as_displayed'] == 'Completed'
assert keyone_funding['status_at_first_observation'] == 'Pending'
assert keyone_funding['pending_crypto_asset_as_displayed'] == 'USDC'
assert Decimal(keyone_funding['sent_token_amount']) == Decimal(keyone_funding['onchain_recipient_amount']) == 10
assert Decimal(keyone_funding['credited_card_amount_usd']) == Decimal(keyone_funding['card_balance_after_usd']) == Decimal('9.91')
credit = keyone_funding['credit_execution']
assert Decimal(credit['transaction_amount']) == Decimal(credit['target_amount']) == Decimal('9.910683')
assert Decimal(credit['target_amount']).quantize(Decimal('0.01')) == Decimal(keyone_funding['credited_card_amount_usd'])
assert credit['displayed_card_amount_matches_rounded_2dp'] is True
assert Decimal(credit['target_amount']) - Decimal(keyone_funding['credited_card_amount_usd']) == Decimal(credit['displayed_card_amount_difference']) == Decimal('0.000683')
assert Decimal('10') - Decimal(credit['target_amount']) == Decimal(credit['shortfall_vs_sent_nominal_usd']) == Decimal('0.089317')
assert Decimal(credit['shortfall_vs_sent_nominal_usd']) / Decimal('10') * 100 == Decimal(credit['shortfall_pct']) == Decimal('0.89317')
assert Decimal('10') - Decimal(keyone_funding['credited_card_amount_usd']) == Decimal(keyone_funding['displayed_shortfall_usd']) == Decimal('0.09')
assert Decimal(keyone_funding['displayed_shortfall_usd']) / Decimal('10') * 100 == Decimal(keyone_funding['displayed_shortfall_pct']) == Decimal('0.9')
assert credit['user_paid_gas_verified'] is False and credit['gas_added_to_sender_cost'] is False
assert keyone_funding['prior_withdrawal_included_in_funding_cost'] is False
fee_terms = keyone_funding['documented_terms_comparison']
assert fee_terms['active_plan_confirmed_by_these_screenshots'] is False
assert fee_terms['free_crypto_topup_rate'] == tier_data['cards']['keyone']['crypto_topup_rate_free']
assert Decimal('10') * (1 - Decimal(fee_terms['free_crypto_topup_rate'])) == Decimal(fee_terms['nominal_result_if_only_free_fee_applies'])
assert Decimal(fee_terms['nominal_result_if_only_free_fee_applies']) - Decimal(credit['target_amount']) == Decimal(fee_terms['actual_internal_credit_below_this_result']) == Decimal('0.009317')
keyone_phases = ('funding_before', 'funding_pending', 'funding_details_pending', 'funding_after', 'funding_completed')
assert keyone_funding['source_files'] == [rows['keyone']['sources'][phase]['file'] for phase in keyone_phases]
assert comparison_cost(rows['keyone']) == Decimal('3.66'), 'New top-up must not change the controlled purchase'
for lang in ('uk', 'en'):
    report = study_html(lang)
    t = translator(lang)
    for phase in keyone_phases:
        assert html.escape(t('ui.' + phase + '_caption'), quote=True) in report

withdrawal = coca_funding['withdrawal']
assert withdrawal['status_as_displayed'] == 'Completed' and withdrawal['fees_as_displayed'] == 'Sponsored'
assert Decimal(coca_funding['credit_execution']['target_amount']).quantize(Decimal('0.0001')) == Decimal(withdrawal['recipient_token_amount_as_displayed']) == Decimal('9.9691')
assert withdrawal['matches_internal_credit_at_display_precision'] is True
assert withdrawal['destination_receipt_independently_verified'] is True
assert withdrawal['measured_duration_verified'] is False
assert withdrawal['user_fee_amount_as_displayed'] == '0'
withdrawal = keyone_funding['withdrawal']
assert withdrawal['status_as_displayed'] == 'Completed'
assert Decimal(withdrawal['requested_token_amount']) == Decimal(keyone_funding['credit_execution']['target_amount']) == Decimal('9.910683')
assert Decimal(withdrawal['requested_token_amount']).quantize(Decimal('0.01')) == Decimal(withdrawal['completed_debit_usd_as_displayed'])
assert withdrawal['recipient_token_amount_as_displayed'] is None and withdrawal['fee_amount'] == '0'
assert withdrawal['destination_receipt_independently_verified'] is True
assert funding_test['withdrawal']['evidence_level'] == 'participant_report_only'
assert funding_test['withdrawal']['fee_amount'] is None and funding_test['withdrawal']['source_files'] == []
for test, phases in ((coca_funding, ('withdrawal_review', 'withdrawal_confirmation', 'withdrawal_completed')), (keyone_funding, ('withdrawal_form', 'withdrawal_completed'))):
    withdrawal = test['withdrawal']
    execution = withdrawal['execution']
    assert execution['network'] == 'Base' and execution['status'] == 'Success'
    assert execution['recipient_matches_screenshot_privately'] is True
    received = Decimal(execution['recipient_usdc_raw_units']) / Decimal(10) ** execution['recipient_usdc_decimals']
    assert received == Decimal(withdrawal['recipient_token_amount_onchain']) == Decimal(test['credit_execution']['target_amount'])
    assert received == Decimal(execution['internal_balance_debit_wusd'])
    assert Decimal(execution['internal_balance_debit_wusd']) - received == Decimal(execution['token_deduction_between_internal_debit_and_recipient']) == Decimal(withdrawal['fee_amount']) == 0
    assert Decimal(test['sent_token_amount']) - received == Decimal(test['credit_execution']['shortfall_vs_sent_nominal_usd'])
    assert withdrawal['fee_asset'] == 'USDC' and execution['wusd_burn_matches_transfer'] is True
    assert execution['user_operation_success'] is True and execution['user_operation_actual_gas_cost_wei'] == '0'
    assert Decimal(execution['bundle_transaction_gas_eth']) > 0 and execution['bundle_gas_added_to_user_cost'] is False
    assert execution['ultimate_gas_sponsor_identified'] is False
    assert withdrawal['evidence_level'] == 'visually_transcribed_app_and_author_checked_explorer_transfer_and_events'
    assert test['withdrawal']['source_files'] == [rows[test['card']]['sources'][phase]['file'] for phase in phases]
    for phase in phases:
        source = rows[test['card']]['sources'][phase]
        assert source['kind'] == 'withdrawal_test' and source['dimensions'] == [590, 1280]
        masks = config['images'][test['card'] + '_' + phase + '.jpeg']
        assert masks and all(mask['box'][1] >= 200 for mask in masks), 'Preserve status bars while hiding identifiers'
    for lang in ('uk', 'en'):
        report = study_html(lang)
        t = translator(lang)
        withdrawal = test['withdrawal']
        text = t('cards.' + test['card'] + '.funding')
        assert html.escape(text, quote=True) in report
        for phase in phases:
            assert html.escape(t('ui.' + phase + '_caption'), quote=True) in report
        credit = test['credit_execution']
        displayed = '$' + credit['shortfall_vs_sent_nominal_usd']
        assert displayed in report, 'Use precise internal credit for nominal route difference'

kolo_funding = next(test for test in funding_tests['tests'] if test['card'] == 'kolo')
assert Decimal(kolo_funding['sent_token_amount']) == Decimal(kolo_funding['onchain_recipient_amount']) == Decimal(kolo_funding['credited_token_amount']) == 10
assert Decimal(kolo_funding['token_credit_shortfall']) == Decimal(kolo_funding['deposit_fee_deducted_from_token_credit']) == 0
assert kolo_funding['status_at_first_observation'] == 'В обробці' and kolo_funding['status_as_displayed'] == 'Успішно'
assert kolo_funding['timing']['confirmation_threshold_as_displayed'] == 65
assert kolo_funding['valuation_assessment']['quote_is_executed_conversion'] is False
assert Decimal(kolo_funding['wallet_token_valuation_eur_as_displayed']) + Decimal(kolo_funding['other_btc_valuation_eur_as_displayed']) == Decimal(kolo_funding['total_balance_after_eur_as_displayed'])
assert (Decimal('10') / Decimal(kolo_funding['valuation_assessment']['quote_usdt_per_eur_as_displayed'])).quantize(Decimal('0.01')) == Decimal('8.83')
assert kolo_funding['valuation_assessment']['quote_reconciles_with_shown_eur_value'] is False
withdrawal = kolo_funding['withdrawal']
assert Decimal(withdrawal['requested_total_debit_as_displayed']) - Decimal(withdrawal['fee_amount']) == Decimal(withdrawal['recipient_token_amount_onchain']) == Decimal(withdrawal['recipient_token_amount_as_displayed']) == Decimal('10.46')
assert Decimal(withdrawal['requested_total_debit_as_displayed']) - Decimal(kolo_funding['sent_token_amount']) == Decimal(withdrawal['other_amount_excluded_from_new_deposit']) == Decimal('1.46')
assert Decimal(withdrawal['execution']['recipient_raw_units']) / Decimal(10) ** withdrawal['execution']['token_decimals'] == Decimal(withdrawal['recipient_token_amount_onchain'])
assert withdrawal['destination_receipt_independently_verified'] is True and withdrawal['status_onchain'] == 'Success'
assert withdrawal['execution']['same_token_contract_as_deposit'] is True and withdrawal['execution']['recipient_matches_screenshot_privately'] is True
assert withdrawal['execution']['sender_is_service_wallet'] is True and withdrawal['execution']['gas_added_separately_to_user_cost'] is False
assert kolo_funding['network_fee']['payer'] == 'sending_wallet' and Decimal(kolo_funding['network_fee']['amount']) > 0
assert kolo_funding['source_files'] == [rows['kolo']['sources'][phase]['file'] for phase in ('funding_before', 'funding_pending', 'funding_completed', 'funding_balance', 'funding_after')]
assert withdrawal['source_files'] == [rows['kolo']['sources'][phase]['file'] for phase in ('withdrawal_form', 'withdrawal_review')]
assert rows['kolo']['sources']['funding_balance']['dimensions'] == [1179, 1095]
assert comparison_cost(rows['kolo']) == Decimal('3.63') and Decimal(modes['actual']['items']['kolo']['value']) == Decimal('3.563619172'), 'Route test must not change purchase or BTC cashback'
for lang in ('uk', 'en'):
    report = study_html(lang)
    t = translator(lang)
    for phase in ('funding_before', 'funding_pending', 'funding_completed', 'funding_balance', 'funding_after', 'withdrawal_form', 'withdrawal_review'):
        assert html.escape(t('ui.' + phase + '_caption'), quote=True) in report

okx_funding = next(test for test in funding_tests['tests'] if test['card'] == 'okx')
assert Decimal(okx_funding['sent_token_amount']) == Decimal(okx_funding['credited_token_amount']) == Decimal(okx_funding['onchain_recipient_amount']) == 10
assert Decimal(okx_funding['token_credit_shortfall']) == Decimal(okx_funding['deposit_fee_deducted_from_token_credit']) == 0
assert okx_funding['credit_account_as_displayed'] == 'Платіжний баланс' and okx_funding['status_as_displayed'] == 'Виконано'
valuation = okx_funding['valuation_assessment']
assert valuation['usd_display_shortfall_is_token_deduction'] is False
assert Decimal(valuation['implied_usd_per_usdt_display_value']) * Decimal(okx_funding['credited_token_amount']) == Decimal(valuation['asset_usd_value_as_displayed']) == Decimal('9.98')
execution = okx_funding['funding_execution']
assert execution['chain_id'] == 196 and execution['status'] == 'Success' and execution['source_matches_screenshot_privately'] is True
assert execution['l1_fee_wei'] == '0'
assert Decimal(execution['received_raw_units']) / Decimal(10) ** execution['token_decimals'] == Decimal('10')
fee = okx_funding['network_fee']
assert fee['asset'] == 'OKB' and fee['payer'] == 'sending_wallet' and fee['explorer_displayed_usd'] is None
assert Decimal(execution['gas_used']) * Decimal(execution['effective_gas_price_wei']) / Decimal(10) ** 18 == Decimal(fee['amount']) == Decimal('0.0000015222')
terms = okx_funding['alternate_network_terms']
assert terms['network'] == 'Ethereum' and terms['included_in_test_cost'] is False
assert terms['evidence_level'] == 'live_app_activation_terms' and terms['first_send_activation_fee_minimum_eth_as_displayed'] == '0.00082681'
withdrawal = okx_funding['withdrawal']
assert withdrawal['status_onchain'] == 'Success' and withdrawal['destination_receipt_independently_verified'] is True
assert Decimal(withdrawal['recipient_token_amount_onchain']) == Decimal(withdrawal['requested_token_amount']) == Decimal(okx_funding['credited_token_amount']) == 10
assert Decimal(withdrawal['fee_amount']) == 0 and withdrawal['fees_as_displayed'] == 'Сплачено OKX'
execution = withdrawal['execution']
assert execution['chain_id'] == 196 and execution['same_token_contract_as_deposit'] is True and execution['sender_matches_deposit_recipient'] is True
assert execution['recipient_matches_screenshot_privately'] is True
assert Decimal(execution['recipient_raw_units']) / Decimal(10) ** execution['token_decimals'] == Decimal('10')
assert Decimal(execution['effective_gas_price_wei']) == Decimal(execution['network_fee_okb']) == 0 and int(execution['gas_used']) > 0
assert execution['l1_fee_wei'] == '0'
assert execution['sponsor_funding_mechanism_verified'] is False
phases = ('funding_before', 'funding_method', 'funding_alternate_method', 'funding_after', 'funding_completed', 'funding_balance')
assert okx_funding['source_files'] == [rows['okx']['sources'][phase]['file'] for phase in phases]
assert withdrawal['source_files'] == [rows['okx']['sources']['withdrawal_review']['file']]
assert not any('notification' in source['file'] for source in all_sources)
assert comparison_cost(rows['okx']) == Decimal('3.49'), 'Pay route must not alter completed purchase'
for lang in ('uk', 'en'):
    report = study_html(lang)
    t = translator(lang)
    for phase in phases + ('withdrawal_review',):
        assert html.escape(t('ui.' + phase + '_caption'), quote=True) in report

simple_funding = next(test for test in funding_tests['tests'] if test['card'] == 'simple')
assert simple_funding['account_asset_as_displayed'] == 'USDC' and simple_funding['status_as_displayed'] == 'Завершено'
assert 'credit_execution' not in simple_funding, 'Precise withdrawal must not be relabeled as independently measured initial credit'
assert simple_funding['funding_execution']['exact_card_credit_independently_verified'] is False
assert Decimal(simple_funding['funding_execution']['sent_raw_units']) / Decimal(10) ** simple_funding['funding_execution']['token_decimals'] == Decimal(simple_funding['sent_token_amount']) == 10
assert simple_funding['credited_token_amount'] == simple_funding['card_balance_after_as_displayed'] == '9.98'
withdrawal = simple_funding['withdrawal']
returned = Decimal(withdrawal['recipient_token_amount_onchain'])
assert returned == Decimal(withdrawal['requested_token_amount']) == Decimal(simple_funding['valuation_assessment']['withdrawal_max_usdc']) == Decimal('9.989909')
assert returned.quantize(Decimal('.01')) == Decimal('9.99') and simple_funding['valuation_assessment']['app_credit_matches_standard_2dp_rounding_of_return'] is False
route = simple_funding['route_result']
assert Decimal(simple_funding['sent_token_amount']) - returned == Decimal(route['nominal_shortfall']) == Decimal('0.010091')
assert Decimal(route['nominal_shortfall']) / Decimal(simple_funding['sent_token_amount']) * 100 == Decimal(route['nominal_shortfall_pct']) == Decimal('0.10091')
first, second = withdrawal['stages']
for stage in withdrawal['stages']:
    assert stage['status'] == 'Success'
    assert Decimal(stage['received_usdc_raw_units']) / Decimal(10) ** stage['usdc_decimals'] == Decimal(stage['received_usdc']) == returned
    assert Decimal(stage['token_deduction']) == 0 and stage['ultimate_economic_gas_payer_verified'] is False
assert Decimal(first['internal_balance_debit_wusd']) == returned and first['wusd_burn_matches_transfer'] is True
assert first['paymaster_is_nonzero'] is True and first['user_operation_success'] is True
assert Decimal(first['user_operation_actual_gas_cost_wei']) / Decimal(10) ** 18 == Decimal(first['user_operation_actual_gas_cost_eth']) > 0
assert Decimal(first['bundle_transaction_gas_eth']) > 0 and first['bundle_gas_added_to_user_cost'] is False
assert second['sender_matches_stage_one_recipient'] is True and second['recipient_matches_original_sending_wallet'] is True
assert second['transaction_gas_payer_differs_from_token_sender'] is True and second['transaction_gas_added_to_user_cost'] is False
assert Decimal(second['transaction_gas_eth']) > 0
assert Decimal(withdrawal['fee_amount']) == 0 and withdrawal['fees_as_displayed'] == '0 USDC'
assert simple_funding['network_fee']['payer'] == 'sending_wallet' and simple_funding['network_fee']['asset'] == 'POL'
assert simple_funding['source_files'] == [rows['simple']['sources'][phase]['file'] for phase in ('funding_before', 'funding_method', 'funding_after', 'funding_completed')]
assert withdrawal['source_files'] == [rows['simple']['sources'][phase]['file'] for phase in ('withdrawal_form', 'withdrawal_review')]
for phase in ('funding_before', 'funding_after'):
    masks = config['images']['simple_' + phase + '.jpeg']
    assert any(mask['box'] == [132, 637, 454, 691] for mask in masks), 'Keep historical Earning private'
assert comparison_cost(rows['simple']) == Decimal('3.66'), 'Funding route must not change the controlled purchase'
for lang in ('uk', 'en'):
    report = study_html(lang)
    t = translator(lang)
    assert '9.98 USDC' in report and '$0.010091' in report

solid_funding = next(test for test in funding_tests['tests'] if test['card'] == 'solid')
cross, direct = solid_funding['funding_routes']
assert cross['route'] == 'arbitrum_to_fuse' and direct['route'] == 'direct_fuse'
for route in (cross, direct):
    assert Decimal(route['sent_token_amount']) == Decimal(route['service_deposit_token_amount']) == 10
    assert Decimal(route['service_deposit_received_raw_units']) / Decimal(10) ** route['service_deposit_token_decimals'] == 10
    credit = route['credit_execution']
    assert credit['status'] == 'Success' and credit['recipient_matches_screenshot_privately'] is True
    assert Decimal(credit['raw_amount']) / Decimal(10) ** credit['token_decimals'] == Decimal(credit['credited_token_amount']) == Decimal(route['credited_token_amount'])
    assert Decimal(route['sent_token_amount']) - Decimal(route['credited_token_amount']) == Decimal(route['token_shortfall'])
    assert Decimal(route['token_shortfall']) / Decimal(route['sent_token_amount']) * 100 == Decimal(route['shortfall_pct'])
    assert credit['paymaster_is_nonzero'] is True and credit['user_operation_success'] is True
    assert Decimal(credit['bundle_transaction_gas_fuse']) > 0 and Decimal(credit['user_operation_actual_gas_cost_fuse']) > 0
    assert credit['sponsored_event_token_charge_raw'] == '0' and credit['gas_added_as_user_debit'] is False
assert cross['credited_token_amount'] == '9.997' and direct['credited_token_amount'] == '10'
assert Decimal(cross['credited_token_amount']).quantize(Decimal('.01')) == Decimal(solid_funding['wallet_token_balance_after_first_credit_as_displayed']) == Decimal('10.00')
assert solid_funding['valuation_assessment']['usd_value_is_token_amount'] is False
withdrawal = solid_funding['withdrawal']
received = Decimal(withdrawal['recipient_token_amount_onchain'])
assert sum(Decimal(route['credited_token_amount']) for route in (cross, direct)) == received == Decimal(withdrawal['requested_token_amount']) == Decimal('19.997')
assert Decimal(solid_funding['sent_token_amount']) - received == Decimal(solid_funding['token_credit_shortfall']) == Decimal('0.003')
assert solid_funding['deposit_fee_deducted_from_token_credit'] is None, 'Route difference does not establish an itemized fee'
execution = withdrawal['execution']
assert Decimal(execution['recipient_raw_units']) / Decimal(10) ** execution['token_decimals'] == received
assert execution['sender_matches_both_credit_recipients'] is True and execution['recipient_matches_both_original_sending_wallets'] is True
assert execution['same_fuse_token_contract_as_both_credits'] is True
assert withdrawal['status_as_displayed'] == withdrawal['status_onchain'] == 'Success'
assert withdrawal['fees_as_displayed'] == 'Paid by Solid' and Decimal(withdrawal['fee_amount']) == 0
assert execution['paymaster_is_nonzero'] is True and execution['sponsored_event_token_charge_raw'] == '0'
assert execution['gas_added_as_user_debit'] is False and execution['ultimate_economic_sponsor_verified'] is False
quote = withdrawal['alternate_quote']
assert quote['included_in_measured_route_cost'] is False and quote['fee_usdt'] == '0.33'
assert (received - Decimal(quote['fee_usdt'])).quantize(Decimal('.01')) == Decimal(quote['recipient_estimate_usdt'])
eth_fee, fuse_fee = solid_funding['network_fees']
assert eth_fee['asset'] == 'ETH' and eth_fee['payer'] == 'sending_wallet' and eth_fee['amount'] == '0.000001239929504'
assert fuse_fee['asset'] == 'FUSE' and fuse_fee['payer'] == 'sending_wallet' and fuse_fee['amount'] == '0.0008222985'
assert fuse_fee['explorer_displayed_usd'] is None
funding_phases = ('funding_before', 'funding_method', 'funding_after', 'funding_balance', 'funding_completed', 'funding_direct_credit')
withdrawal_phases = ('withdrawal_method', 'withdrawal_alternate_quote', 'withdrawal_form', 'withdrawal_review', 'withdrawal_completed')
assert solid_funding['source_files'] == [rows['solid']['sources'][phase]['file'] for phase in funding_phases]
assert withdrawal['source_files'] == [rows['solid']['sources'][phase]['file'] for phase in withdrawal_phases]
assert comparison_cost(rows['solid']) == Decimal('3.64') and included_cashback_value(rows['solid']) == Decimal('0.11'), 'Funding test must not alter purchase or cashback'
for lang in ('uk', 'en'):
    report = study_html(lang)
    t = translator(lang)
    assert '0.003 USDT' in report, 'Do not round a measured small route difference to zero'
    for phase in funding_phases + withdrawal_phases:
        assert html.escape(t('ui.' + phase + '_caption'), quote=True) in report

trustee_funding = next(test for test in funding_tests['tests'] if test['card'] == 'trustee_plus')
assert [deposit['amount'] for deposit in trustee_funding['deposits']] == ['10', '1']
for deposit in trustee_funding['deposits']:
    assert Decimal(deposit['received_raw_units']) / Decimal(10) ** deposit['token_decimals'] == Decimal(deposit['amount'])
    assert deposit['status_onchain'] == 'Success' and deposit['same_sender_and_recipient'] is True
assert sum(Decimal(deposit['amount']) for deposit in trustee_funding['deposits']) == Decimal(trustee_funding['sent_token_amount']) == Decimal(trustee_funding['credited_token_amount']) == 11
assert trustee_funding['token_credit_shortfall'] == trustee_funding['deposit_fee_deducted_from_token_credit'] == '0'
assert trustee_funding['card_balance_after_first_wallet_credit_usd_as_displayed'] == '0'
card = trustee_funding['card_funding']
assert card['minimum_as_displayed_usdt'] == card['requested_token_amount'] == card['wallet_transfer_as_displayed'] == '10'
assert card['credited_asset_as_displayed'] == 'USDT'
assert card['credited_token_amount'] == card['receipt_original_amount_usdt'] == '9.965114'
assert Decimal(card['requested_token_amount']) - Decimal(card['credited_token_amount']) == Decimal(card['requested_to_receipt_difference_usdt']) == Decimal('0.034886')
assert Decimal(card['requested_to_receipt_difference_usdt']) / Decimal(card['requested_token_amount']) * 100 == Decimal(card['requested_to_receipt_difference_pct'])
assert Decimal(card['requested_token_amount']) + Decimal(card['wallet_fee_as_displayed_usdt']) == Decimal(card['wallet_debit_estimate_usdt']) == Decimal('10.06')
assert Decimal(trustee_funding['credited_token_amount']) - Decimal(card['wallet_remaining_as_displayed_usdt']) == Decimal(card['wallet_debit_estimate_usdt'])
assert Decimal(card['wallet_debit_estimate_usdt']) - Decimal(card['credited_token_amount']) == Decimal(card['total_difference_estimate_usdt']) == Decimal('0.094886')
assert Decimal(card['total_difference_estimate_usdt']) / Decimal(card['requested_token_amount']) * 100 == Decimal(card['estimated_difference_pct_of_requested']) == Decimal('0.94886')
assert card['extra_deposit_amount_usdt'] == '1' and card['extra_deposit_is_entirely_a_fee'] is False
assert card['exact_wallet_fee_independently_verified'] is False and card['card_credit_independently_verified_onchain'] is False
warning = card['fee_warning']
assert Decimal(warning['balance_as_displayed_usdt']) - Decimal(warning['fee_as_displayed_usdt']) == Decimal(warning['simple_subtraction_usdt']) == Decimal('9.94')
assert Decimal(warning['available_after_fee_as_displayed_usdt']) - Decimal(warning['simple_subtraction_usdt']) == Decimal(warning['display_discrepancy_usdt']) == Decimal('0.01')
assert warning['included_as_additional_fee'] is False and card['minimum_warning']['card_topup_blocked'] is True
assert trustee_funding['network_fee']['asset'] == 'POL' and trustee_funding['network_fee']['payer'] == 'sending_wallet'
assert sum(Decimal(deposit['network_fee_pol']) for deposit in trustee_funding['deposits']) == Decimal(trustee_funding['network_fee']['amount']) == Decimal('0.043778475419491624')
assert trustee_funding['network_fee']['transaction_count'] == 2
assert trustee_funding['timing']['end_to_end_network_latency_measured'] is False
withdrawal = trustee_funding['withdrawal']
assert withdrawal['completed'] is False and withdrawal['completion_independently_verified'] is False
assert withdrawal['recipient_token_amount_onchain'] is None and withdrawal['fee_actually_paid_verified'] is False
assert withdrawal['internal_return']['card_to_wallet_ledger_supplied'] is False
assert withdrawal['base_attempt']['blocked'] is True
assert Decimal(withdrawal['base_attempt']['requested_amount']) < Decimal(withdrawal['base_attempt']['minimum_as_displayed']) == 10
quote = withdrawal['exchange_quote']
assert Decimal(quote['give_amount']) - Decimal(quote['receive_amount']) == Decimal(quote['nominal_parity_difference']) == Decimal('0.019437')
assert (Decimal(quote['nominal_parity_difference']) / Decimal(quote['give_amount']) * 100).quantize(Decimal('0.000001')) == Decimal(quote['nominal_parity_difference_pct'])
assert abs(Decimal(quote['give_amount']) * Decimal(quote['rate_as_displayed']) - Decimal(quote['receive_amount'])) < Decimal('0.00001')
assert quote['rate_rounding_difference_is_additional_fee'] is False and quote['execution_receipt_supplied'] is False
assert quote['completed'] is True and quote['confirmed_by_participant'] is True
assert quote['confirmed_on'] == '2026-10-12'
attempt = withdrawal['polygon_attempt']
assert Decimal(quote['receive_amount']) + Decimal(card['wallet_remaining_as_displayed_usdt']) == Decimal(attempt['wallet_balance_as_displayed'])
assert Decimal(attempt['wallet_balance_as_displayed']) - Decimal(attempt['fee_as_displayed']) == Decimal(attempt['available_after_fee_as_displayed'])
assert attempt['blocked'] is True and attempt['minimum_verified'] is False
extra = withdrawal['extra_deposit']
assert extra['confirmed_by_participant'] is True and extra['independently_verified_onchain'] is False
assert extra['network_fee'] is None and extra['included_in_initial_two_deposits'] is False
assert Decimal(extra['wallet_after_as_displayed']) - Decimal(extra['wallet_before_as_displayed']) == Decimal(extra['amount_usdt']) == 1
review = withdrawal['review']
assert Decimal(review['requested_recipient_amount']) + Decimal(review['fee_as_displayed']) == Decimal(review['total_debit_as_displayed']) == Decimal(extra['wallet_after_as_displayed'])
assert review['stage'] == 'before_transfer_button' and review['execution_time_measured'] is False
trustee_withdrawal_phases = ('withdrawal_minimum_blocked', 'withdrawal_exchange_quote', 'withdrawal_fee_blocked', 'withdrawal_form', 'withdrawal_review')
assert withdrawal['source_files'] == [rows['trustee_plus']['sources'][phase]['file'] for phase in trustee_withdrawal_phases]
for phase in trustee_withdrawal_phases:
    masks = config['images'][f'trustee_plus_{phase}.jpeg']
    assert len(masks) == (0 if phase == 'withdrawal_exchange_quote' else 1), 'Keep every private recipient fragment blurred'
trustee_phases = ('funding_form_before', 'funding_before', 'funding_after', 'funding_completed', 'funding_fee_blocked', 'funding_minimum_blocked', 'funding_extra_balance', 'funding_card_after', 'funding_card_receipt', 'funding_card_debit')
assert trustee_funding['source_files'] == [rows['trustee_plus']['sources'][phase]['file'] for phase in trustee_phases]
assert rows['trustee_plus']['sources']['funding_card_receipt']['kind'] == 'receipt'
assert len(config['images']['trustee_plus_funding_card_receipt.jpeg']) == 4, 'Receipt payer, card ending, Trustee ID and transaction number must be redacted'
assert comparison_cost(rows['trustee_plus']) == Decimal('3.648467'), 'New funding must not change the controlled purchase'
for lang in ('uk', 'en'):
    report = study_html(lang)
    t = translator(lang)
    for phase in trustee_phases + trustee_withdrawal_phases:
        assert html.escape(t('ui.' + phase + '_caption'), quote=True) in report

loss_entries = json.loads((ROOT / 'data/losses.json').read_text())['entries']
def recorded_loss(card, stage):
    return next(entry for entry in loss_entries if entry['card'] == card and entry['stage_key'] == 'losses.' + stage)

assert len(loss_entries) == 32
current_terms = funding_tests['current_terms']
solid_current = current_terms['solid']
assert solid_current['eligible_issuer'] == 'Wirex' and solid_current['personally_tested'] is False
assert solid_current['eur_balance_asset'] == 'EURC' and solid_current['eur_balance_network'] == 'Base'
assert solid_current['sepa_incoming_supported'] is True and solid_current['sepa_outgoing_supported'] is False
for tier, expected_credit in [('Core', '995'), ('Prime', '997.5')]:
    fee = Decimal('1000') * Decimal(solid_current['sepa_deposit_rates'][tier])
    assert Decimal('1000') - fee == Decimal(expected_credit)
    entry = recorded_loss('solid', 'solid_sepa_' + tier.lower())
    assert entry['group'] == 'tariffs' and entry['asset'] == 'EUR'
    assert Decimal(entry['amount']) == fee, 'Documented SEPA fees must not be recorded as tested losses'
assert solid_program['current_fees']['displayed_apy_net_of_performance_fee'] is None
assert solid_program['current_fees']['performance_fee_on_yield'] == '0.10'
assert solid_program['current_fees']['withdrawal_solver_fee'] == '0.0001'
assert subscription_rebate['current_terms_review']['account_category_eligibility_reverified'] is False
for lang in ('uk', 'en'):
    messages = load_messages(lang)
    report = study_html(lang)
    for card, current in current_terms.items():
        block = re.search(r'<details[^>]+id="funding-' + card + r'".*?</details>', report, re.S)[0]
        assert all(html.escape(paragraph, quote=True) in block for paragraph in messages['cards.' + card + '.funding_current'].splitlines())
        assert date.fromisoformat(current['checked_on']) <= date.fromisoformat(research['updated_on'])
        assert date.fromisoformat(current['checked_on']).strftime('%d.%m.%Y') in block
        assert all(source['url'] in block for source in current['sources'])
assert not any(entry['stage_key'] == 'losses.solid_alternate' for entry in loss_entries), 'Unused Solid route belongs in funding options, not measured losses'
assert Decimal(recorded_loss('bybit', 'historical_bybit')['amount']) == Decimal('0.0819')
assert Decimal(recorded_loss('kolo', 'historical_kolo')['amount']) == Decimal('0.14')
assert not any(entry['stage_key'] == 'losses.historical_bybit_extra' for entry in loss_entries), 'Extra debit is already included in the historical total'
assert recorded_loss('bybit', 'historical_bybit')['group'] == 'conversion'
assert recorded_loss('bybit', 'historical_bybit')['asset'] == 'USDT'
assert Decimal(recorded_loss('simple', 'historical_simple_bill')['amount']) == Decimal('0.01')
assert Decimal(recorded_loss('coca', 'route_nominal')['amount']) == Decimal('0.030917')
assert Decimal(recorded_loss('keyone', 'route_nominal')['amount']) == Decimal('0.089317')
assert Decimal(recorded_loss('simple', 'route_nominal')['amount']) == Decimal('0.010091')
assert Decimal(recorded_loss('solid', 'solid_cross')['amount']) == Decimal('0.003')
assert Decimal(recorded_loss('trustee_plus', 'trustee_topup')['amount']) == Decimal('0.094886')
assert recorded_loss('trustee_plus', 'trustee_topup')['approximate'] is True
assert Decimal(recorded_loss('bybit', 'payment_foreign')['amount']) == Decimal(rows['bybit']['final_transaction']['foreign_transaction_fee_usd'])
assert Decimal(recorded_loss('bybit', 'payment_conversion')['amount']) == Decimal(rows['bybit']['conversion_quote']['shown_conversion_fee_usdt'])
bybit_conversion = recorded_loss('bybit', 'bybit_difference')
assert bybit_conversion['group'] == 'conversion' and bybit_conversion['asset'] == 'USDT'
assert Decimal(bybit_conversion['amount']) == Decimal('0.0179')
bybit_terms = rows['bybit']['conversion_quote']['documented_terms']
assert bybit_terms['crypto_conversion_fee_rate'] == '0.009'
for lang in ('uk', 'en'):
    report = study_html(lang)
    assert bybit_terms['fees_url'] in report
whitebit_conversion = recorded_loss('whitebit', 'whitebit_difference')
assert whitebit_conversion['group'] == 'conversion' and whitebit_conversion['asset'] == 'USDT'
assert Decimal(whitebit_conversion['amount']) == Decimal(rows['whitebit']['final_transaction']['spent_amount']) - Decimal(rows['whitebit']['final_transaction']['card_amount_usd']) == Decimal('0.25')
assert recorded_loss('trustee_plus', 'trustee_withdrawal')['group'] == 'tariffs'
assert recorded_loss('trustee_plus', 'trustee_exchange')['group'] == 'conversion'
assert Decimal(recorded_loss('trustee_plus', 'trustee_exchange')['amount']) == Decimal('0.019437')
assert all(recorded_loss('whitebit', stage)['group'] == 'tariffs' for stage in ('whitebit_plasma', 'whitebit_erc20', 'whitebit_other'))
assert recorded_loss('okx', 'okx_activation')['minimum'] is True
assert recorded_loss('okx', 'okx_activation')['group'] == 'activation'
assert recorded_loss('okx', 'okx_activation')['asset'] == 'ETH'
assert recorded_loss('whitebit', 'whitebit_gas')['amount'] is None
for test in funding_tests['tests']:
    fees = test['network_fees'] if 'network_fees' in test else [test['network_fee']]
    gas_rows = [entry for entry in loss_entries if entry['card'] == test['card'] and entry['group'] == 'gas']
    assert [(entry['amount'], entry['asset']) for entry in gas_rows] == [(fee['amount'], fee['asset']) for fee in fees], 'Native sending-wallet gas only; do not add sponsor or bundle charges'
for language in ('uk', 'en'):
    t = translator(language)
    report = study_html(language)
    for row in data['rows']:
        card = re.search(r'<article class="card ' + row['id'] + r'".*?</article>', report, re.S)[0]
        block = re.search(r'<details class="calculation losses".*?</details>', card, re.S)[0]
        own = [entry for entry in loss_entries if entry['card'] == row['id'] and entry['group'] != 'gas']
        assert block.count('<dt>') == len(own), 'Each card shows only its own losses'
        assert set(re.findall(r'<h4>(.*?)</h4>', block)) == {html.escape(t('losses.' + entry['group']), quote=True) for entry in own}, 'Only card-specific service costs and discrepancies are shown'
        for entry in loss_entries:
            if entry['group'] == 'gas':
                assert html.escape(t(entry['stage_key']), quote=True) not in block, 'Per-transfer gas is retained in data, not shown as a card fee'
        for entry in own:
            assert html.escape(t(entry['stage_key']), quote=True) in block
            if entry['amount'] is not None:
                assert entry['amount'] in block, 'Keep tiny losses at source precision'

whitebit_funding = next(test for test in funding_tests['tests'] if test['card'] == 'whitebit')
assert whitebit_funding['status_as_displayed'] == 'Успішно'
assert whitebit_funding['credited_token_amount'] == whitebit_funding['main_token_balance_after_as_displayed'] == '10'
assert whitebit_funding['network'] is None and whitebit_funding['onchain_recipient_amount'] is None
assert whitebit_funding['sender_debit_independently_verified'] is False
assert whitebit_funding['network_fee']['amount'] is None and whitebit_funding['deposit_fee_deducted_from_token_credit'] is None
assert whitebit_funding['manual_card_transfer_required'] is False
valuation = whitebit_funding['valuation_assessment']
assert Decimal(whitebit_funding['credited_token_amount']) * Decimal(valuation['implied_usd_per_usdt_display_value']) == Decimal(whitebit_funding['card_balance_after_usd_as_displayed']) == Decimal('9.98')
assert valuation['usd_display_shortfall_is_token_deduction'] is False
assert whitebit_funding['timing']['latency_measured'] is False
withdrawal = whitebit_funding['withdrawal']
assert withdrawal['completed'] is False and withdrawal['fee_actually_paid_verified'] is False
assert withdrawal['recipient_token_amount_onchain'] is None and withdrawal['completion_independently_verified'] is False
assert Decimal(withdrawal['total_debit_as_displayed']) - Decimal(withdrawal['fees_as_displayed']) == Decimal(withdrawal['recipient_token_amount_as_displayed']) == Decimal('11.08')
assert Decimal(whitebit_funding['credited_token_amount']) + Decimal(withdrawal['other_account_residual_usdt']) == Decimal(withdrawal['total_debit_as_displayed'])
assert withdrawal['residual_origin_confirmed_by_participant'] is True and withdrawal['residual_counted_as_test_gain'] is False
assert withdrawal['display_amount_includes_fee'] is True and withdrawal['stage'] == 'before_continue_button'
fees = withdrawal['alternate_network_fees_usdt_as_displayed']
assert fees['PLASMA'] == withdrawal['fees_as_displayed'] == '0.1' and fees['ERC20'] == '0.8'
assert all(fee == '1' for network, fee in fees.items() if network not in ('PLASMA', 'ERC20'))
assert Decimal(fees['PLASMA']) / Decimal(whitebit_funding['sent_token_amount']) * 100 == Decimal(withdrawal['quoted_fee_pct_of_test_deposit']) == 1
assert withdrawal['quicksend_terms']['external_wallet_equivalent'] is False
whitebit_funding_phases = ('funding_before', 'funding_after', 'funding_credit', 'funding_balance')
whitebit_withdrawal_phases = ('withdrawal_method', 'withdrawal_review')
assert whitebit_funding['source_files'] == [rows['whitebit']['sources'][phase]['file'] for phase in whitebit_funding_phases]
assert withdrawal['source_files'] == [rows['whitebit']['sources'][phase]['file'] for phase in whitebit_withdrawal_phases]
assert rows['whitebit']['sources']['funding_credit']['dimensions'] == [1179, 969]
assert config['images']['whitebit_funding_credit.jpeg'][0]['box'] == [38, 886, 322, 938]
assert comparison_cost(rows['whitebit']) == Decimal('3.82'), 'Funding and quoted fees must not change the controlled purchase'
for lang in ('uk', 'en'):
    report = study_html(lang)
    t = translator(lang)
    for phase in whitebit_funding_phases + whitebit_withdrawal_phases:
        assert html.escape(t('ui.' + phase + '_caption'), quote=True) in report

# shortcut: privacy regions are manually reviewed per batch; review new sources before extending the manifest.
visible = subprocess.run(['git', '-C', str(ROOT), 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], check=True, capture_output=True).stdout.decode().split('\0')
for name in filter(None, visible):
    p = Path(name)
    if p == Path('sitemap.xml') and not site_url:
        assert not (ROOT / p).exists()
        continue
    assert p.parts[0] in {'.gitignore', '.github', '.nojekyll', 'index.html', 'sitemap.xml', 'README.md', 'LICENSE', 'docs', 'data', 'scripts', 'screenshots', 'assets', 'en', 'locales', 'cards', 'ranking'}, name
    assert not {'private', 'cards_samples'} & set(p.parts) and p.suffix.lower() not in {'.zip', '.jpeg', '.jpg', '.csv'} and p.name != '.DS_Store', name
    if p.suffix.lower() == '.png':
        assert not re.search(r'_(?:earning|savings|yield|autoinvest)(?:_|$)', p.stem), 'Analysis-only screenshot in public files: ' + name
    if p.suffix in {'.md', '.json', '.py', '.html', '.xml', '.js', '.cjs'}:
        text = (ROOT / p).read_text()
        assert not re.search(r'/(?:Users|home|mnt/data)/[A-Za-z0-9]', text), name
        assert not re.search(r'0x[0-9a-fA-F]{40,}', text), 'Public blockchain identifier: ' + name
print('PASS: SEO across 22 pages, unique titles and descriptions, canonical language URLs, page-specific card previews, linked structured data, breadcrumbs, card lists and reciprocal sitemap alternatives.')
print('PASS: matching Ukrainian/English financial values, locale keys and placeholders; four exact sorting modes with Solid/COCA accepted cashback and credited Bybit points included; OKX completed USDT amount selected; shown BTC included at a fixed reference quote before payout and cap/fee-aware base/next projections; issuer evidence; conditional Earning arithmetic and unknown-rate handling; financial arithmetic; Kolo BTC valuation; Trustee receipt; Bybit quote and asset-history reconciliation; nine card samples; 125 public PNGs; credited WhiteBIT BTC and completed purchase; WhiteBIT main-account credit, unknown sender gas, Plasma quote and existing-balance exclusion; Trustee wallet/card separation, minimum/fee failures, participant-confirmed swap, stated withdrawal fee, confirmed extra deposit and unexecuted withdrawal review; Solid two funding routes and combined sponsored Fuse withdrawal; Simple exact two-stage USDC return and separate paymaster/relayer gas; OKX Pay X Layer token parity and separate OKB gas; KOLO full token credit, withdrawal fee and other-balance exclusion; COCA and KeyOne withdrawal precision and evidence limits; exact Kolo historical cashback sum and USD example; local scripts and links; private originals excluded.')
