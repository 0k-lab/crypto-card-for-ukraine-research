"""Build the static study from public data, with native screenshot popovers."""
from pathlib import Path
from decimal import Decimal
import html
import hashlib
import json
import struct
import re
import os
from datetime import date
from xml.etree import ElementTree as ET
from urllib.parse import urlsplit
from functools import partial
from i18n import LANGUAGES, load_messages, translate
from cashback import monthly_cashback, solid_upgrade, solid_spend_threshold
from earning import monthly_income
from sorting import comparison_cost, cashback_value, included_cashback_value, card_sorting
from scoring import score_cards
from flows import money_flow
from pages import score_badge, purchase_chart, card_score_overview, card_route_details, ranking_page, cashback_chart, regular_use_summary, faq_markup, card_sources

ROOT = Path(__file__).resolve().parents[1]
research = json.loads((ROOT / 'data/research.json').read_text())
site_url = os.environ.get('SITE_URL', research['public_url']).strip().rstrip('/')
if site_url:
    url = urlsplit(site_url)
    assert url.scheme == 'https' and url.hostname and not url.username and not url.password and not url.query and not url.fragment, 'SITE_URL must be a public HTTPS base URL without credentials, query or fragment'
date.fromisoformat(research['updated_on'])

page_routes = []

def build(language):
    messages = load_messages(language)
    t = partial(translate, messages)
    data = json.loads((ROOT / 'data/measurements.json').read_text())
    terms = json.loads((ROOT / 'data/terms-evidence.json').read_text())
    scenario = json.loads((ROOT / 'data/budget-scenario.json').read_text())
    art = {item['id']: item for item in json.loads((ROOT / 'data/card-art.json').read_text())['images']}
    assert set(art) == {row['id'] for row in data['rows']}
    issuers = json.loads((ROOT / 'data/card-issuers.json').read_text())['entries']
    assert set(issuers) == set(art)
    tier_data = json.loads((ROOT / 'data/cashback-tiers.json').read_text())
    assert set(tier_data['cards']) == set(art)
    card_links = json.loads((ROOT / 'data/card-links.json').read_text())['cards']
    assert set(card_links) == set(art)
    funding_tests = json.loads((ROOT / 'data/funding-tests.json').read_text())
    earning = json.loads((ROOT / 'data/earning.json').read_text())
    assert set(earning['cards']) == set(art)
    snapshot = json.loads((ROOT / 'data/scoring.json').read_text())
    scores = score_cards(snapshot, data, tier_data, funding_tests, earning['model'])
    edition = 'en/' if language == 'en' else ''

    for row in data['rows']:
        for field in ('asset', 'status', 'note', 'reward_text'):
            row[field] = t(f"cards.{row['id']}.{field}")
    for identifier, program in tier_data['cards'].items():
        program['scope'] = t(f'programs.{identifier}.scope')
        program['notes'] = [t(f'programs.{identifier}.notes.{n}') for n in range(len(program['notes']))]
        for n, tier in enumerate(program['tiers']):
            for field in ('name', 'conditions'):
                tier[field] = t(f'programs.{identifier}.tiers.{n}.{field}')
        for n, source in enumerate(program['sources']):
            source['label'] = t(f'programs.{identifier}.sources.{n}')
    for identifier, opening in card_links.items():
        opening['bonus_note'] = t(f'cards.{identifier}.bonus_note') if opening['bonus_note'] else t('ui.no_bonus')
    sorting = card_sorting(data['rows'], tier_data, scores, language)
    rows_by_id = {row['id']: row for row in data['rows']}
    default_sort = sorting['modes'][sorting['default']]
    ordered_rows = [rows_by_id[identifier] for identifier in default_sort['order']]
    (ROOT / ('data/card-sorting.json' if language == 'uk' else 'data/card-sorting-en.json')).write_text(json.dumps(sorting, ensure_ascii=False, indent=2) + '\n')

    def fmt(value, places=2):
        return f'{Decimal(value):.{places}f}'

    def esc(value):
        return html.escape(str(value), quote=True)

    def picture(source, caption, name):
        raw = (ROOT / source['file']).read_bytes()
        width, height = struct.unpack('>II', raw[16:24])
        figure_class = 'receipt-evidence' if source.get('kind') in ('receipt', 'conversion_quote') else ''
        return f'''<figure class="{figure_class}"><figcaption>{esc(caption)}</figcaption>\n      <div class="image-viewport"><img width="{width}" height="{height}" alt="{esc(t('ui.screenshot_alt', value0=name, value1=caption))}" src="../{esc(source['file'])}" loading="lazy"></div>\n      <a class="image-file" href="../{esc(source['file'])}" target="_blank" rel="noopener">{esc(t('ui.open_png'))}<span>{width} × {height} px</span></a></figure>'''

    def popover(identifier, title, figures):
        return f'''<div id="{identifier}" class="evidence-popover" popover role="dialog" aria-labelledby="{identifier}-title">\n      <header class="popover-heading"><div><span class="eyebrow">{esc(t('ui.screenshots_title'))}</span><h2 id="{identifier}-title">{esc(title)}</h2></div>\n      <button class="close" type="button" popovertarget="{identifier}" popovertargetaction="hide" aria-label="{esc(t('ui.close_evidence', value0=title))}" autofocus>×</button></header>\n      <div class="gallery">{figures}</div><p class="muted">{esc(t('ui.privacy_note'))}</p></div>'''

    def card_picture(identifier, name, href=None):
        item = art[identifier]
        width, height = item['dimensions']
        image = f'''<img class="product-art" width="{width}" height="{height}" src="../{esc(item['file'])}" alt="{esc(t('ui.card_alt', value0=name))}" loading="lazy">'''
        if href:
            label = name + ' — ' + t('pages.details')
            image = f'<a class="card-art-link" href="{esc(href)}" aria-label="{esc(label)}">{image}</a>'
        return f'<figure class="card-art">{image}</figure>'

    def earning_values(identifier):
        offer = earning['cards'][identifier]['offers'][0]
        if offer['rate'] is None:
            rate = t('earning.unknown_rate')
        else:
            kind = t('earning.annual') if offer['rate_kind'] == 'annual_unspecified' else offer['rate_kind'].upper()
            rate = t('earning.percent', value0=fmt(Decimal(offer['rate']) * 100).rstrip('0').rstrip('.'), value1=kind)
            if offer['upper_bound']:
                rate = t('earning.maximum_rate', value0=rate)
        income = monthly_income(offer, earning['model'])
        result = t('earning.unknown')
        if offer.get('eligible_in_ukraine') is False:
            rate = t('earning.okx_rate', value0=fmt(Decimal(offer['rate']) * 100, 1))
            result = t('earning.okx_unavailable')
        if income is not None:
            lower, upper = map(fmt, income)
            result = t('earning.maximum_amount', value0=upper) if offer['upper_bound'] else t('earning.range', value0=lower, value1=upper) if lower != upper else t('earning.amount', value0=lower)
        return rate, result

    def source_links(sources):
        return '<p class="detail-sources">' + ''.join(f'<a href="{esc(source["url"] if "url" in source else "../" + source["file"])}">{esc(source["label"])}</a>' for source in sources) + '</p>'

    def earning_details(identifier):
        rate, result = earning_values(identifier)
        program = earning['cards'][identifier]
        fields = [(t('earning.rate'), rate), (t('earning.before_fees') if identifier == 'solid' else t('earning.assumed'), result)]
        ledger = '<dl class="ledger">' + ''.join(f'<div><dt>{esc(label)}</dt><dd>{esc(value)}</dd></div>' for label, value in fields) + '</dl>' if program['offers'][0]['rate'] is not None else ''
        body = ledger + f'<p class="muted">{esc(t("earning.cards." + identifier + ".note"))}</p>'
        if identifier == 'bybit':
            usdc_offer = dict(program['offers'][0], rate=program['displayed_apr_by_asset']['USDC'])
            body += f'<p class="muted">{esc(t("earning.cards.bybit.usdc_note", value0=fmt(monthly_income(usdc_offer, earning["model"])[0])))}</p>'
        if identifier == 'coca':
            body += f'<p class="muted">{esc(t("earning.cards.coca.claim_note"))}</p>'
        if identifier == 'solid':
            body = '<h4>Savings</h4>' + body
            body += f'<p class="muted">{esc(t("earning.cards.solid.fees_note"))}</p>'
            recent_offer = dict(program['offers'][0], rate=program['displayed_7_day_apy_by_asset']['USDC'])
            body += f'<p class="muted">{esc(t("earning.cards.solid.recent_note", value0=fmt(Decimal(recent_offer["rate"]) * 100), value1=fmt(monthly_income(recent_offer, earning["model"])[0]), value2=fmt(Decimal(program["displayed_15_day_apy_by_asset"]["USDC"]) * 100), value3=fmt(Decimal(program["displayed_30_day_apy_by_asset"]["USDC"]) * 100)))}</p>'
            prime = program['offers'][1]
            boost = '+' + fmt(Decimal(prime['boost_apy']) * 100, 0) + '% APY'
            body += f'<h4>Prime</h4><dl class="ledger"><div><dt>{esc(t("earning.boost"))}</dt><dd>{esc(boost)}</dd></div><div><dt>{esc(t("earning.balance_cap"))}</dt><dd>${int(prime["eligible_balance_cap_usd"]):,}</dd></div></dl><p class="muted">{esc(t("earning.cards.solid.prime_note"))}</p>'
            credit_rate = fmt(Decimal(program['credit_mode']['account_screen_borrowing_rate']) * 100) + '% APY'
            body += f'<h4>Credit</h4><dl class="ledger"><div><dt>{esc(t("earning.borrowing_rate"))}</dt><dd>{esc(credit_rate)}</dd></div></dl><p class="muted">{esc(t("earning.cards.solid.borrow_note"))}</p>'
        sources = [dict(source, label=t(f'earning.cards.{identifier}.sources.{n}')) for n, source in enumerate(program['sources'])]
        sources.append({'url': '../' + edition + 'ranking/#income-method', 'label': t('earning.rules')})
        snapshot = f'<p class="muted">{esc(t("earning.rate_snapshot", value0=date.fromisoformat(earning["checked_on"]).strftime("%d.%m.%Y")))}</p>' if program['offers'][0]['rate'] is not None else ''
        return f'<details class="calculation earning" id="earning-{identifier}"><summary>{esc(t("pages.historical_income"))}</summary>{snapshot}{body}{source_links(sources)}</details>'

    def cashback_details(identifier):
        program = tier_data['cards'][identifier]
        spend = Decimal(tier_data['monthly_eligible_merchant_spend_usd'])
        blocks = []
        groups = [[program['tiers'][0], program['tiers'][2]], [program['tiers'][1], program['tiers'][3]]] if identifier == 'bybit' else [[tier] for tier in program['tiers']]
        for level, group in enumerate(groups):
            if all(tier['rate'] is None and tier['cap'] is None for tier in group):
                continue
            name = (t('ui.base_group') if level == 0 else t('ui.next_group')) if identifier == 'bybit' else group[0]['name']
            blocks.append(f'<div class="tier"><h4>{esc(name)}</h4>')
            for tier in group:
                blocks.append(tier_ledger(tier, spend, identifier == 'bybit'))
            blocks.append('</div>')
        extra = ''
        if identifier == 'solid':
            usd = Decimal(scenario['usd_subscriptions_budget'])
            tiers = program['tiers']
            no_categories = solid_upgrade(tiers, spend, usd)
            chatgpt = solid_upgrade(tiers, spend, usd, Decimal('100'))
            extra = f"""<p class="muted"><strong>{esc(t('ui.solid_comparison'))}</strong>{esc(t('ui.solid_result', value0=f'{no_categories:+.2f}', value1=f'{chatgpt:+.2f}'))}</p><p class="muted"><strong>{esc(t('ui.solid_threshold_title'))}</strong>{esc(t('ui.solid_threshold', value0=fmt(solid_spend_threshold(tiers, usd)), value1=fmt(solid_spend_threshold(tiers, usd, Decimal('100')))))}</p>"""
        elif identifier == 'coca':
            capital = Decimal(program['tiers'][1]['documented_approx_capital_usd'])
            assumed_annual_hurdle = Decimal('0.05')
            hurdle = capital * assumed_annual_hurdle / 12
            rate_difference = Decimal(program['tiers'][1]['rate']) - Decimal(program['tiers'][0]['rate'])
            extra = f"""<p class="muted"><strong>{esc(t('ui.capital_title'))}</strong>{esc(t('ui.capital_scenario', value0=fmt(capital, 0), value1=fmt(hurdle), value2=fmt(hurdle / rate_difference), value3=fmt(Decimal('15') - hurdle)))}</p>"""
        elif identifier == 'whitebit':
            category_rates = program['tiers'][0]['category_rates']
            categories = ''.join(f'<div><dt>{esc(t("whitebit.categories." + key))}</dt><dd>{fmt(Decimal(rate) * 100, 0)}%</dd></div>' for key, rate in category_rates.items())
            subs = sum(Decimal(item['monthly_equivalent_usd_at_nbu']) for item in scenario['subscriptions'])
            subs_cashback = subs * Decimal(category_rates['subscriptions'])
            mixed = min(subs_cashback + (spend - subs) * Decimal(category_rates['groceries']), Decimal(program['tiers'][0]['cap']))
            extra = f'<dl class="ledger">{categories}</dl><p class="muted">{esc(t("ui.whitebit_budget_scenario", value0=fmt(subs), value1=fmt(subs_cashback), value2=fmt(mixed)))}</p>'
        elif identifier == 'keyone':
            eur_rate = json.loads((ROOT / 'data/nbu-eur-2026-10-09.json').read_text(), parse_float=Decimal)[0]['rate']
            eur_usd = eur_rate / Decimal(data['nbu_usd_uah'])
            monthly_price = Decimal(program['annual_premium_eur']) * eur_usd / 12
            difference = Decimal(program['crypto_topup_rate_free']) - Decimal(program['crypto_topup_rate_premium'])
            extra = f"""<p class="muted"><strong>{esc(t('ui.premium_title'))}</strong>{esc(t('ui.premium_scenario', value0=fmt(spend * difference), value1=fmt(monthly_price), value2=f'{spend * difference - monthly_price:+.2f}', value3=fmt(monthly_price / difference)))}</p>"""
        notes = ''.join(f'<p class="muted">{esc(note)}</p>' for note in program['notes'] if note)
        sources = program['sources'] + [{'url': '../' + edition + 'ranking/#cashback-method', 'label': t('ui.model_sources')}]
        terms_button = f"""<button class="evidence-button" type="button" popovertarget="evidence-prime">{esc(t('ui.prime_button'))}<span>↗</span></button>""" if identifier == 'solid' else ''
        checked_on = date.fromisoformat(program.get('checked_on', tier_data['checked_on'])).strftime('%d.%m.%Y')
        return f"""<details class="calculation cashback-tiers" id="tiers-{identifier}"><summary>{esc(t('ui.cashback'))}</summary><p class="muted">{esc(t('ui.terms_date', value0=program['scope'], value1=checked_on))}</p>{''.join(blocks)}{extra}{notes}{source_links(sources)}{terms_button}</details>"""

    def tier_ledger(tier, spend, regional=False):
        rate = t('ui.rate_unknown') if tier['rate'] is None else fmt(Decimal(tier['rate']) * 100, 0) + '%'
        if tier.get('category_rates'):
            rates = list(map(Decimal, tier['category_rates'].values()))
            rate = fmt(min(rates) * 100, 0) + '–' + fmt(max(rates) * 100, 0) + '%'
        symbol = '€' if tier.get('currency') == 'EUR' else '$'
        cap = t('ui.cap_unknown') if tier['cap'] is None else symbol + fmt(tier['cap'], 0) + (t('ui.claim_month') if tier['cap_kind'] == 'claim' else t('ui.per_month'))
        earned, available = monthly_cashback(tier, spend)
        result = t('ui.unknown') if earned is None else '$' + fmt(available if tier['cap_kind'] == 'payout' and available is not None else earned) + (t('ui.unknown_cap') if available is None else t('ui.earned_claim_prefix') + fmt(available) + t('ui.claim_suffix') if tier['cap_kind'] == 'claim' else t('ui.cashback_suffix'))
        if tier.get('projection_kind') in ('upper_bound_before_per_transaction_caps', 'upper_bound_after_category_selection'):
            result = t('ui.up_to', value0=result)
        fields = [(t('ui.rate'), rate), (t('ui.monthly_cap'), cap), (t('ui.at_budget'), result)]
        if available is not None and tier['annual_fee_usd'] is not None and Decimal(tier['annual_fee_usd']) > 0:
            fields.append((t('ui.after_tier_fee'), '$' + fmt(available - Decimal(tier['annual_fee_usd']) / 12)))
        if tier['rate'] is not None and tier['cap'] is not None:
            fields.append((t('ui.spend_to_cap'), symbol + fmt(Decimal(tier['cap']) / Decimal(tier['rate']))))
        if tier.get('per_transaction_cap') is not None:
            fields.append((t('ui.per_purchase_cap'), symbol + fmt(tier['per_transaction_cap'])))
            fields.append((t('ui.minimum_purchase'), symbol + fmt(tier['minimum_purchase'])))
        ledger = ''.join(f'<div><dt>{esc(label)}</dt><dd>{esc(value)}</dd></div>' for label, value in fields)
        heading = f'<p class="muted">{esc(tier["name"])}</p>' if regional else ''
        return f'{heading}<dl class="ledger">{ledger}</dl><p class="muted">{esc(tier["conditions"])}</p>'

    tests_by_card = {test['card']: test for test in funding_tests['tests']}
    assert set(tests_by_card) == set(rows_by_id)
    losses = []

    def loss(group, card, stage, amount, asset, approximate=False, minimum=False):
        losses.append({'group': group, 'card': card, 'stage_key': 'losses.' + stage, 'amount': str(amount) if amount is not None else None, 'asset': asset, 'approximate': approximate, 'minimum': minimum})

    bybit = rows_by_id['bybit']
    loss('observed', 'bybit', 'payment_foreign', bybit['final_transaction']['foreign_transaction_fee_usd'], 'USD')
    loss('observed', 'bybit', 'payment_conversion', bybit['conversion_quote']['shown_conversion_fee_usdt'], 'USDT')
    for card in ('coca', 'keyone', 'simple'):
        test = tests_by_card[card]
        returned = test['withdrawal']['recipient_token_amount_onchain']
        loss('observed', card, 'route_nominal', Decimal(test['sent_token_amount']) - Decimal(returned), 'USD')
    loss('observed', 'solid', 'solid_cross', tests_by_card['solid']['funding_routes'][0]['token_shortfall'], 'USDT')
    for tier in ('Core', 'Prime'):
        rate = Decimal(funding_tests['current_terms']['solid']['sepa_deposit_rates'][tier])
        loss('tariffs', 'solid', 'solid_sepa_' + tier.lower(), fmt(1000 * rate), 'EUR')
    loss('observed', 'trustee_plus', 'trustee_topup', tests_by_card['trustee_plus']['card_funding']['total_difference_estimate_usdt'], 'USDT', approximate=True)
    loss('observed', 'kolo', 'kolo_withdrawal', tests_by_card['kolo']['withdrawal']['fee_amount'], 'USDT')
    for card, test in tests_by_card.items():
        fees = test['network_fees'] if 'network_fees' in test else [test['network_fee']]
        for fee in fees:
            stage = 'solid_cross_gas' if fee.get('route') == 'arbitrum_to_fuse' else 'solid_direct_gas' if fee.get('route') == 'direct_fuse' else 'trustee_gas' if card == 'trustee_plus' else 'whitebit_gas' if card == 'whitebit' else 'deposit_gas'
            loss('gas', card, stage, fee['amount'], fee['asset'])
    trustee = tests_by_card['trustee_plus']['withdrawal']
    loss('conversion', 'trustee_plus', 'trustee_exchange', trustee['exchange_quote']['nominal_parity_difference'], 'USD')
    loss('tariffs', 'trustee_plus', 'trustee_withdrawal', trustee['review']['fee_as_displayed'], 'USDT')
    whitebit = tests_by_card['whitebit']['withdrawal']
    for network, stage in (('PLASMA', 'whitebit_plasma'), ('ERC20', 'whitebit_erc20'), ('POLYGON', 'whitebit_other')):
        loss('tariffs', 'whitebit', stage, whitebit['alternate_network_fees_usdt_as_displayed'][network], 'USDT')
    loss('activation', 'okx', 'okx_activation', tests_by_card['okx']['alternate_network_terms']['first_send_activation_fee_minimum_eth_as_displayed'], 'ETH', minimum=True)
    quote = bybit['conversion_quote']
    loss('conversion', 'bybit', 'bybit_difference', Decimal(quote['input_amount']) - Decimal(quote['output_amount']) - Decimal(quote['shown_conversion_fee_usdt']), 'USDT')
    loss('differences', 'simple', 'simple_difference', rows_by_id['simple']['delta_minus_tx'], 'USDC')
    loss('conversion', 'whitebit', 'whitebit_difference', rows_by_id['whitebit']['delta_minus_tx'], 'USDT')
    historical = json.loads((ROOT / 'data/historical.json').read_text())
    for card in ('bybit', 'kolo'):
        payment = next(payment for payment in historical['usd_tests'] if payment['card'] == card)
        loss('conversion' if card == 'bybit' else 'observed', card, 'historical_' + card, Decimal(payment['debit']) - Decimal(payment['merchant_usd']), payment['asset'] if card == 'bybit' else 'USD')
    bill = next(payment for payment in historical['uah_bill_test']['results'] if payment['card'] == 'simple')
    loss('differences', 'simple', 'historical_simple_bill', Decimal(bill['balance_delta']) - Decimal(bill['tx_debit']), 'USDC')
    (ROOT / 'data/losses.json').write_text(json.dumps({'scope': 'Different operations; do not sum rows. Stablecoin differences use nominal parity. Quotes and display discrepancies are separate from observed costs. Native sending-wallet gas only; no sponsor/bundle double counting.', 'entries': losses}, ensure_ascii=False, indent=2) + '\n')

    def loss_details(identifier):
        groups = []
        for group in ('observed', 'conversion', 'tariffs', 'activation', 'quoted', 'differences'):
            items = []
            for entry in (entry for entry in losses if entry['card'] == identifier and entry['group'] == group):
                amount = t('losses.unknown') if entry['amount'] is None else ('≈' if entry['approximate'] else '≥' if entry['minimum'] else '') + ('$' + entry['amount'] if entry['asset'] == 'USD' else entry['amount'] + ' ' + entry['asset'])
                items.append(f'<div><dt>{esc(t(entry["stage_key"]))}</dt><dd>{esc(amount)}</dd></div>')
            if items:
                groups.append(f'<h4>{esc(t("losses." + group))}</h4><dl class="loss-ledger">{"".join(items)}</dl>')
        sources = source_links([{'url': quote['documented_terms']['fees_url'], 'label': t('losses.bybit_fees_source')}]) if identifier == 'bybit' else ''
        if identifier == 'solid':
            sources = source_links([{'url': funding_tests['current_terms']['solid']['sources'][1]['url'], 'label': t('losses.solid_fees_source')}])
        return f'<details class="calculation losses" id="losses-{identifier}"><summary>{esc(t("losses.title"))}</summary>{"".join(groups)}{sources}</details>'

    networks = {'okx': 'Mastercard', 'bybit': 'Mastercard'}
    table, cards, evidence = [], [], []
    full_cards, card_evidence = {}, {}
    for number, row in enumerate(ordered_rows, start=1):
        identifier = row['id']
        cost = comparison_cost(row)
        cashback = cashback_value(row)
        if cashback is not None:
            net_value = cost - cashback
            net = ('≈$' if 'reward_valuation' in row else '$') + fmt(net_value, 6 if identifier == 'trustee_plus' else 4 if identifier == 'bybit' or 'reward_valuation' in row else 2)
        elif row['observed_reward']['asset'] == 'BTC':
            net = f"${row['debit']} − BTC"
        else:
            net = t('ui.net_unknown')
        overhead = f"{(cost / Decimal(data['nbu_equivalent_usd']) - 1) * 100:+.2f}%"
        rate = Decimal(data['merchant_amount_uah']) / cost
        reward = '$0.00' if identifier == 'okx' else t('ui.not_shown')
        if row['reward'] is not None and Decimal(row['reward']):
            reward = '$' + fmt(row['reward'])
        elif row['observed_reward']['asset'] in ('BTC', 'TP'):
            reward = row['observed_reward']['amount'] + ' ' + row['observed_reward']['asset']
        receipt_detail = f"<div><dt>{esc(t('ui.exact_receipt'))}</dt><dd>{row['receipt']['amount']} USDC</dd></div>" if 'receipt' in row else ''
        final = row.get('final_transaction')
        final_detail = f'<div><dt>{esc(t("ui.final_card_amount"))}</dt><dd>${esc(final["card_amount_usd"])}</dd></div>' if final else ''
        if final and final['spent_amount'] is not None:
            final_detail += f'<div><dt>{esc(t("ui.final_crypto_spent"))}</dt><dd>{esc(final["spent_amount"])} {esc(final["spent_asset"])}</dd></div>'
        if row['observed_reward']['asset'] == 'Bybit Points':
            points = row['points_assessment']
            final_detail += f'<div><dt>{esc(t("ui.credited_points"))}</dt><dd>{esc(points["points"])}</dd></div><div><dt>{esc(t("ui.points_equivalent"))}</dt><dd>{esc(points["points"])} × {esc(points["usdt_per_point"])} = {esc(points["cashback_deduction_usd"])} USDT</dd></div>'
        quote_detail = f"<div><dt>{esc(t('ui.conversion_quote'))}</dt><dd>3.6407 USDT → $3.59</dd></div><div><dt>{esc(t('ui.included_fee'))}</dt><dd>0.0328 USDT</dd></div><div><dt>{esc(t('ui.quoted_rate'))}</dt><dd>1 USD = 1.0141 USDT</dd></div>" if 'conversion_quote' in row else ''
        reward_label = t('ui.points') if identifier == 'trustee_plus' else t('ui.shown_btc') if 'reward_valuation' in row else t('ui.shown_cashback')
        if row['observed_reward']['asset'] == 'BTC' and row['observed_reward']['availability'] == 'participant_confirmed_credited':
            reward_label = t('ui.credited_cashback')
        valuation_detail = f"""<div><dt>{esc(t('ui.btc_value'))}</dt><dd>≈${fmt(cashback, 4)}</dd></div><div><dt>{esc(t('ui.btc_rate'))}</dt><dd>${esc(row['reward_valuation']['price_usd_per_btc'])} · {esc(row['reward_valuation']['quote_date'])}</dd></div><div><dt>{esc(t('ui.valuation_source'))}</dt><dd><a href="../{esc(row['reward_valuation']['source_file'])}">{esc(t('ui.coinbase_source'))}</a></dd></div>""" if 'reward_valuation' in row else ''
        issuer = issuers[identifier]
        extra_sources = [source for source in terms['images'] if source.get('card') == identifier]
        source_count = len(row['sources']) + len(extra_sources)
        sort_item = default_sort['items'][identifier]
        rank_label = sort_item['rank']
        cashback_inline = ''
        if cashback:
            net_display = ('≈$' if 'reward_valuation' in row else '$') + fmt(net_value)
            cashback_inline = f'<span class="cashback-inline" aria-describedby="cashback-note">· {esc(t("ui.cashback_net", value0=net_display))}</span>'
        reward_detail = f'<div><dt>{reward_label}</dt><dd>{esc(reward)}</dd></div>'
        actual_sort = sorting['modes']['actual']
        included_detail = f'<div><dt>{esc(actual_sort["metric"])}</dt><dd>{esc(actual_sort["items"][identifier]["display"])}</dd></div>' if included_cashback_value(row) else ''
        conditional_detail = f'<div class="conditional-cost"><dt>{esc(t("ui.after_pending"))}</dt><dd>{esc(net)}</dd></div>' if cashback is not None and cashback != included_cashback_value(row) else ''
        opening = card_links[identifier]
        official_label = t('ui.open_without_referral_label' if opening['referral'] else 'ui.open_card_label', value0=row['name'])
        official_button = t('ui.open_without_referral_button' if opening['referral'] else 'ui.open_card_button')
        opening_buttons = f'<a class="open-card" href="{esc(opening["official_url"])}" target="_blank" rel="noopener" aria-label="{esc(official_label)}"><span>{esc(official_button)}</span><span aria-hidden="true">↗</span></a>'
        if opening['referral']:
            opening_buttons += f'<a class="open-card" href="{esc(opening["url"])}" target="_blank" rel="noopener sponsored" aria-label="{esc(t("ui.open_with_referral_label", value0=row["name"]))}"><span>{esc(t("ui.open_with_referral_button"))}</span><span aria-hidden="true">↗</span></a>'
        referral_kind = f'<span class="referral-kind">{esc(t("ui.referral"))}</span>' if opening['referral'] else ''
        conditions_link = f''' <a href="{esc(opening['conditions_url'])}" target="_blank" rel="noopener">{esc(t('ui.referral_terms'))}</a>''' if opening.get("conditions_url") else ""
        bonus_note = f'<p class="referral-note">{referral_kind}{esc(opening["bonus_note"])}{conditions_link}</p>'
        funding_body = f'<p class="muted"><strong>{esc(t("ui.test_result"))}</strong> {esc(t("cards." + identifier + ".funding"))}</p>'
        if identifier in funding_tests['current_terms']:
            current = funding_tests['current_terms'][identifier]
            checked_on = date.fromisoformat(current['checked_on']).strftime('%d.%m.%Y')
            paragraphs = t("cards." + identifier + ".funding_current").splitlines()
            funding_body += f'<p class="muted"><strong>{esc(t("ui.current_terms", value0=checked_on))}</strong> {esc(paragraphs[0])}</p>'
            funding_body += ''.join(f'<p class="muted">{esc(paragraph)}</p>' for paragraph in paragraphs[1:])
            funding_body += source_links([dict(source, label=t(f'cards.{identifier}.funding_sources.{n}')) for n, source in enumerate(current['sources'])])
        funding_detail = f'<details class="calculation funding-summary" id="funding-{identifier}"><summary>{esc(t("ui.funding_title"))}</summary>{funding_body}</details>'
        experience = t('cards.' + identifier + '.experience')
        usd_example = t('cards.' + identifier + '.usd_example')
        usd_detail = f'<h4>{esc(t("ui.usd_examples"))}</h4><p class="muted">{esc(usd_example)}</p>' if usd_example else ''
        onchain_detail = ''
        if identifier in ('solid', 'keyone'):
            onchain_source = source_links([{'file': 'data/onchain-summary.json', 'label': t('ui.onchain_limits')}])
            onchain_detail = f'<h4>{esc(t("ui.onchain"))}</h4><p class="muted">{esc(t("cards." + identifier + ".onchain"))}</p>{onchain_source}'
        rating = (
            f'<section class="card-rating-panel" aria-label="{esc(t("pages.score_label"))}">'
            f'<div class="detail-rating"><div class="detail-rating-value">'
            f'{score_badge(identifier, scores[identifier], language, t)}'
            f'<span>{esc(t("pages.score_label"))}</span></div>'
            f'<span class="score-track" aria-hidden="true"><i style="width:{scores[identifier]["total"] * 10}%"></i></span>'
            f'<a href="../{edition}ranking/#scoring-method">{esc(t("pages.score_link"))} →</a></div>'
            f'{card_score_overview(scores[identifier], snapshot["cards"][identifier], language, t)}</section>'
        )
        cards.append(f'''<article class="card {identifier}" id="{identifier}">\n      <div class="detail-summary"><header class="card-header"><span class="card-index">{rank_label}</span><div><h3>{esc(row['name'])}</h3><span class="card-meta">{esc(issuer['label'].partition(' · ')[0])} · {esc(networks.get(identifier, 'Visa'))} · {esc(row['card_currency'])}</span></div></header>\n      <div class="debit"><div class="debit-amount"><span class="label">{esc(t('ui.debit'))}</span><div class="debit-values"><strong>${fmt(cost)}</strong>{cashback_inline}</div>\n      <div class="sort-result" hidden><span class="label sort-label">{esc(default_sort['metric'])}</span><strong class="sort-value">{esc(sort_item['display'])}</strong><p class="sort-note">{esc(sort_item['note'])}</p></div></div><span class="overhead">{overhead}<small>{esc(t('ui.vs_nbu'))}</small></span></div>\n      {card_picture(identifier, row['name'])}</div>\n      {rating}\n      <div class="card-body">\n      <p class="verdict">{esc(experience)}</p>\n      <div class="card-details"><details class="calculation" open><summary>{esc(t('ui.calculation'))}</summary><dl class="ledger"><div><dt>{esc(t('ui.before_after'))}</dt><dd>{row['before']} → {row['after']}</dd></div><div><dt>{esc(t('ui.transaction_amount'))}</dt><dd>{row['tx']}</dd></div>{receipt_detail}{quote_detail}{final_detail}{reward_detail}{valuation_detail}{included_detail}{conditional_detail}<div><dt>{esc(t('ui.effective_rate'))}</dt><dd>{fmt(rate, 4)} ₴/$</dd></div></dl><p class="muted">{esc(row['asset'])}. {esc(row['note'])}</p>{usd_detail}{onchain_detail}</details>\n      {cashback_details(identifier)}\n      {earning_details(identifier)}\n      {funding_detail}\n      {loss_details(identifier)}\n      <button class="evidence-button" type="button" popovertarget="evidence-{identifier}" aria-label="{esc(t('ui.evidence_label', value0=row['name']))}">{esc(t('ui.screenshots_button'))}<span>{source_count} ↗</span></button></div></div>\n      <div class="card-opening"><h4 class="card-opening-title">{esc(t("seo.open_card_heading", value0=row["name"]))}</h4><div class="card-actions">{opening_buttons}</div>{bonus_note}</div></article>''')
        captions = {'before': t('ui.before'), 'after': t('ui.after'), 'tx': t('ui.transaction'), 'receipt': t('ui.receipt_caption'), 'quote': t('ui.quote_caption'), 'completed': t('ui.completed_caption'), 'points': t('ui.credited_points_caption'), 'cashback_history': t('ui.kolo_cashback_history_caption'), 'historical_usd': t('ui.historical_usd_caption'), 'historical_usd_details': t('ui.historical_usd_details_caption'), 'historical_usd_points': t('ui.historical_usd_points_caption'), 'historical_chatgpt': t('ui.historical_chatgpt_caption'), 'historical_apple': t('ui.historical_apple_caption'), 'historical_uah': t('ui.kolo_historical_uah_caption'), 'asset_history': t('ui.asset_history_caption'), 'historical_usd_assets': t('ui.historical_usd_assets_caption'), 'funding_before': t('ui.funding_before_caption'), 'funding_waiting': t('ui.funding_waiting_caption'), 'funding_after': t('ui.funding_after_caption'), 'funding_paywith': t('ui.funding_paywith_caption'), 'funding_balance': t('ui.funding_balance_caption'), 'funding_credit': t('ui.funding_credit_caption'), 'funding_method': t('ui.funding_method_caption'), 'funding_alternate_method': t('ui.funding_alternate_method_caption'), 'funding_quote': t('ui.funding_quote_caption'), 'funding_completed': t('ui.funding_completed_caption'), 'funding_pending': t('ui.funding_pending_caption'), 'funding_details_pending': t('ui.funding_details_pending_caption'), 'withdrawal_review': t('ui.withdrawal_review_caption'), 'withdrawal_confirmation': t('ui.withdrawal_confirmation_caption'), 'withdrawal_completed': t('ui.withdrawal_completed_caption'), 'withdrawal_form': t('ui.withdrawal_form_caption'), 'withdrawal_minimum_blocked': t('ui.withdrawal_minimum_blocked_caption'), 'withdrawal_exchange_quote': t('ui.withdrawal_exchange_quote_caption'), 'withdrawal_fee_blocked': t('ui.withdrawal_fee_blocked_caption'), 'funding_direct_credit': t('ui.funding_direct_credit_caption'), 'withdrawal_method': t('ui.withdrawal_method_caption'), 'withdrawal_alternate_quote': t('ui.withdrawal_alternate_quote_caption'), 'funding_form_before': t('ui.funding_form_before_caption'), 'funding_fee_blocked': t('ui.funding_fee_blocked_caption'), 'funding_minimum_blocked': t('ui.funding_minimum_blocked_caption'), 'funding_extra_balance': t('ui.funding_extra_balance_caption'), 'funding_card_after': t('ui.funding_card_after_caption'), 'funding_card_receipt': t('ui.funding_card_receipt_caption'), 'funding_card_debit': t('ui.funding_card_debit_caption')}
        figures = ''.join(picture(source, t(source['caption_key']) if source.get('caption_key') else captions[phase], row['name']) for phase, source in row['sources'].items())
        figures += ''.join(picture(source, t(source['caption_key']), row['name']) for source in extra_sources)
        evidence.append(popover('evidence-' + identifier, row['name'], figures))
        card_evidence[identifier] = evidence[-1]
        full_cards[identifier] = cards.pop().replace('class="card-opening"', 'class="card-opening" id="get-card"')
        detail_href = '../' + edition + 'cards/' + identifier + '/'
        score_item = scores[identifier]
        currencies = ' · '.join(snapshot['cards'][identifier]['currencies'])
        summary = t('pages.cards.' + identifier + '.summary')
        cashback_month = f"${score_item['values']['cashback']:.0f}"
        badge = score_badge(identifier, score_item, language, t)
        short_bonus = f'<p class="referral-note">{esc(t("pages.referral_short"))} <a href="{detail_href}#get-card">{esc(t("ui.referral_terms"))}</a></p>'
        cards.append(f'''<article class="card {identifier}" id="{identifier}">
          <header class="card-header"><span class="card-index">{rank_label}</span><div><h3><a href="{detail_href}">{esc(row['name'])}</a></h3><span class="card-meta">{esc(issuer['label'].partition(' · ')[0])} · {esc(networks.get(identifier, 'Visa'))} · {esc(currencies)}</span></div>{badge}</header>
          {card_picture(identifier, row['name'], detail_href)}<div class="card-body"><div class="debit"><div class="debit-amount"><span class="label">{esc(t('ui.debit'))}</span><div class="debit-values"><strong>${fmt(cost)}</strong>{cashback_inline}</div><div class="sort-result" hidden><span class="label sort-label">{esc(default_sort['metric'])}</span><strong class="sort-value">{esc(sort_item['display'])}</strong><p class="sort-note">{esc(sort_item['note'])}</p></div></div><span class="overhead">{overhead}<small>{esc(t('ui.vs_nbu'))}</small></span></div>
          <p class="card-summary">{esc(summary)}</p><dl class="overview-facts"><div><dt>{esc(t('pages.currency_label'))}</dt><dd>{esc(currencies)}</dd></div><div><dt>{esc(t('pages.monthly'))}</dt><dd>{cashback_month}</dd></div></dl><a class="card-details-link" href="{detail_href}"><span>{esc(t('pages.details'))}</span><span aria-hidden="true">→</span></a></div>
          <div class="card-opening"><p class="card-opening-title">{esc(t('ui.get_card'))}</p><div class="card-actions">{opening_buttons}</div>{short_bonus}</div></article>''')

        included = included_cashback_value(row)
        approximate = '≈' if 'reward_valuation' in row else ''
        cells = ['$' + fmt(cost), approximate + '$' + fmt(included), approximate + '$' + fmt(cost - included), overhead]
        table.append(f'<tr data-card="{identifier}"><th scope="row"><a href="#{identifier}">{esc(row["name"])}</a></th>' + ''.join('<td class="money">' + esc(cell) + '</td>' for cell in cells) + '</tr>')

    prime_evidence = popover('evidence-prime', t('ui.prime_title'), picture(terms['images'][0], t('ui.prime_caption'), 'Solid Prime'))
    formatted_date = lambda value: date.fromisoformat(value).strftime('%d.%m.%Y')
    footer_credit = f'{esc(t("ui.test_date"))} <time datetime="{data["test_date"]}">{formatted_date(data["test_date"])}</time> · {esc(t("ui.updated_date"))} <time datetime="{research["updated_on"]}">{formatted_date(research["updated_on"])}</time> · <a href="{esc(research["author"]["url"])}" rel="author">{esc(research["author"]["name"])}</a> · {esc(t("ui.own_license"))} '
    def faq_items(prefix, count):
        return [{'@type': 'Question', 'name': t(f'{prefix}.{n}.question'), 'acceptedAnswer': {'@type': 'Answer', 'text': t(f'{prefix}.{n}.answer')}} for n in range(count)]

    faq = faq_items('page.faq', 8)

    def render_page(logical_path, title, description, body, scripts='', page_class='', home=False, card_id=None, questions=None):
        output_path = edition + logical_path
        directory = logical_path.removesuffix('index.html')
        page_url = site_url + '/' + edition + directory
        image_path = art[card_id]['file'] if card_id else f'assets/social/preview-{language}.png'
        image_width, image_height = art[card_id]['dimensions'] if card_id else (1200, 630)
        image_alt = t('seo.card_image_alt', value0=rows_by_id[card_id]['name']) if card_id else t('page.head.social_image_alt')
        image_url = site_url + '/' + image_path if site_url else '../' + image_path
        metadata = [
            ('name', 'author', research['author']['name']),
            ('name', 'robots', 'index, follow, max-image-preview:large'),
            ('property', 'og:type', 'website' if home else 'article'),
            ('property', 'og:site_name', t('seo.site_name')),
            ('property', 'og:title', title), ('property', 'og:description', description),
            ('property', 'og:locale', 'uk_UA' if language == 'uk' else 'en_US'),
            ('property', 'og:locale:alternate', 'en_US' if language == 'uk' else 'uk_UA'),
            ('property', 'og:image', image_url), ('property', 'og:image:type', 'image/png'),
            ('property', 'og:image:width', str(image_width)), ('property', 'og:image:height', str(image_height)),
            ('property', 'og:image:alt', image_alt),
            ('name', 'twitter:card', 'summary_large_image'), ('name', 'twitter:title', title),
            ('name', 'twitter:description', description), ('name', 'twitter:image', image_url),
            ('name', 'twitter:image:alt', image_alt),
        ]
        social = '\n'.join(f'<meta {attribute}="{key}" content="{esc(value)}">' for attribute, key, value in metadata)
        schema_html = ''
        alternates = [('uk', '/' + directory), ('en', '/en/' + directory), ('x-default', '/' + directory)]
        if site_url:
            social += f'\n<meta property="og:url" content="{esc(page_url)}"><link rel="canonical" href="{esc(page_url)}">'
            social += ''.join(f'<link rel="alternate" hreflang="{lang}" href="{esc(site_url + path)}">' for lang, path in alternates)
            image = {'@type': 'ImageObject', 'url': image_url, 'width': image_width, 'height': image_height, 'caption': image_alt}
            article = {'@type': 'Article', '@id': page_url + '#research', 'url': page_url,
                       'headline': title, 'description': description, 'inLanguage': language,
                       'image': image, 'dateModified': research['updated_on'],
                       'author': {'@type': 'Person', **research['author']},
                       'mainEntityOfPage': {'@id': page_url + '#webpage'},
                       'citation': [site_url + '/data/scoring.json', site_url + '/data/measurements.json']}
            article['publisher'] = article['author']
            article['isAccessibleForFree'] = True
            website = {'@type': 'WebSite', '@id': site_url + '/#website', 'url': site_url + '/',
                       'name': t('page.head.a_2').strip(), 'alternateName': t('seo.site_name'), 'inLanguage': list(LANGUAGES)}
            webpage = {'@type': 'WebPage' if card_id else 'CollectionPage', '@id': page_url + '#webpage',
                       'url': page_url, 'name': title, 'description': description, 'inLanguage': language,
                       'isPartOf': {'@id': website['@id']}, 'mainEntity': {'@id': article['@id']},
                       'primaryImageOfPage': image, 'dateModified': research['updated_on']}
            graph = [article]
            if questions:
                article['hasPart'] = {'@id': page_url + '#faq'}
                graph.append({'@type': 'FAQPage', '@id': page_url + '#faq', 'inLanguage': language, 'mainEntity': questions})
            graph.extend([website, webpage])
            if not home:
                breadcrumbs = {'@type': 'BreadcrumbList', '@id': page_url + '#breadcrumbs', 'itemListElement': [
                    {'@type': 'ListItem', 'position': 1, 'name': t('pages.home'), 'item': site_url + '/' + edition},
                    {'@type': 'ListItem', 'position': 2, 'name': rows_by_id[card_id]['name'] if card_id else t('pages.rating'), 'item': page_url},
                ]}
                webpage['breadcrumb'] = {'@id': breadcrumbs['@id']}
                graph.append(breadcrumbs)
            if card_id:
                article['about'] = {'@type': 'Thing', '@id': page_url + '#card', 'name': rows_by_id[card_id]['name'],
                                    'url': card_links[card_id]['official_url']}
                article['citation'].extend(snapshot['cards'][card_id]['sources'])
            else:
                listed_rows = ordered_rows if home else [rows_by_id[key] for key in sorting['modes']['score']['order']]
                items = [{'@type': 'ListItem', 'position': position, 'name': row['name'],
                          'url': site_url + '/' + edition + 'cards/' + row['id'] + '/'}
                         for position, row in enumerate(listed_rows, 1)]
                item_list = {'@type': 'ItemList', '@id': page_url + '#card-list', 'name': t('pages.rating_title'),
                             'itemListOrder': 'https://schema.org/ItemListOrderDescending',
                             'numberOfItems': len(items), 'itemListElement': items}
                article['mainEntity'] = {'@id': item_list['@id']}
                graph.append(item_list)
            schema = json.dumps({'@context': 'https://schema.org', '@graph': graph}, ensure_ascii=False).replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')
            schema_html = f'<script type="application/ld+json" id="research-schema">{schema}</script>'
        language_switch = '<nav class="language-switch" aria-label="' + esc(t('ui.language')) + '">' + ''.join(
            f'<a href="../{prefix + directory or "./"}" lang="{lang}" hreflang="{lang}"' + (' aria-current="page"' if lang == language else '') + f'>{label}</a>'
            for lang, prefix, label in (('uk', '', 'UA'), ('en', 'en/', 'EN'))
        ) + '</nav>'
        slots = {
            'LANG': language, 'SOCIAL_META': social, 'STRUCTURED_DATA': schema_html,
            'PAGE_TITLE': esc(title), 'PAGE_DESCRIPTION': esc(description), 'PAGE_BODY': body,
            'STYLESHEET_VERSION': hashlib.sha256((ROOT / 'assets/site.css').read_bytes()).hexdigest()[:12],
            'ANALYTICS_VERSION': hashlib.sha256((ROOT / 'assets/analytics.js').read_bytes()).hexdigest()[:12],
            'PAGE_TYPE': 'card' if card_id else 'home' if home else 'ranking', 'PAGE_CARD': card_id or '',
            'PAGE_SCRIPTS': scripts, 'PAGE_CLASS': page_class,
            'HOME_HREF': '../' + edition + ('./' if output_path == 'index.html' else ''), 'RANKING_HREF': '../' + edition + 'ranking/',
            'LANG_SWITCH': language_switch, 'FOOTER_CREDIT': footer_credit,
        }
        report = (ROOT / 'scripts/page-template.html').read_text()
        for key, value in slots.items():
            report = report.replace('{{' + key + '}}', value)
        report = re.sub(r'\[\[([a-zA-Z0-9_.]+)\]\]', lambda match: esc(messages[match[1]]), report)
        report = report.replace('{{SUBS_TOTAL}}', fmt(scenario['estimated_total_subscriptions_monthly_usd_at_nbu']))
        prefix = '../' * (len(Path(output_path).parts) - 1)
        report = re.sub(r'(href|src|content)="\.\./', lambda match: match[1] + '="' + prefix, report)
        assert not re.search(r'\{\{[A-Z_]+\}\}|\[\[[a-zA-Z0-9_.]+\]\]', report), 'Unfilled template slot'
        assert 'data:image/' not in report and '/Users/' not in report
        target = ROOT / output_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(report)
        page_routes.append((output_path, alternates))

    home_slots = {
        'CARD_BASE_HREF': '../' + edition + 'cards/',
        'AUTHOR_LINE': f'{esc(t("ui.author"))} <a href="{esc(research["author"]["url"])}" rel="author">{esc(research["author"]["name"])}</a>',
        'FAQ': faq_markup(faq),
        'LOWEST_DEBIT': esc(rows_by_id[sorting['modes']['gross']['order'][0]]['name'] + ' · $' + fmt(comparison_cost(rows_by_id[sorting['modes']['gross']['order'][0]]))),
        'SUPPORTING_DOCS': '<p class="muted">' + esc(t('ui.supporting_docs')) + '</p>' if language == 'en' else '',
        'SORT_OPTIONS': ''.join(f'<option value="{mode}"' + (' selected' if mode == sorting['default'] else '') + f'>{esc(spec["label"])}</option>' for mode, spec in sorting['modes'].items()),
        'SORT_DESCRIPTION': esc(default_sort['description']),
        'CARDS': ''.join(cards), 'TABLE': ''.join(table),
        'PAYMENT_EVIDENCE_COUNT': str(sum(len(row['sources']) for row in data['rows'])),
        'EVIDENCE': '', 'SUBS_TOTAL': fmt(scenario['estimated_total_subscriptions_monthly_usd_at_nbu']),
        'PURCHASE_CHART': purchase_chart(data['rows'], language, t),
    }
    body = (ROOT / 'scripts/report-template.html').read_text().replace('class="card-grid"', 'class="card-grid overview"')
    for key, value in home_slots.items():
        body = body.replace('{{' + key + '}}', value)
    sorting_json = json.dumps(sorting, ensure_ascii=False).replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')
    home_scripts = f'<script type="application/json" id="card-sorting">{sorting_json}</script><script src="../assets/card-sort.js" defer></script>'
    render_page('index.html', t('page.head.title_1'), t('page.head.meta_content_1'), body, home_scripts, home=True, questions=faq)
    flow_inputs = {'measurements': data, 'scoring': snapshot, 'funding': funding_tests,
                   'tiers': tier_data, 'earning': earning, 'history': historical}
    for identifier, row in rows_by_id.items():
        card = snapshot['cards'][identifier]
        card_body = f'<nav class="breadcrumbs" aria-label="{esc(t("pages.back"))}"><a href="../{edition}#comparison">← {esc(t("pages.back"))}</a><a href="../{edition}ranking/">{esc(t("pages.rating"))}</a></nav>'
        card_body += f'<section class="page-intro card-intro"><div><span class="eyebrow">{esc(t("pages.provisional"))}</span><h1>{esc(row["name"])}</h1><p class="lead">{esc(t("pages.cards." + identifier + ".summary"))}</p></div></section>'
        card_body += f'<nav class="nav" aria-label="{esc(t("pages.details"))}"><a href="#test-evidence">{esc(t("pages.historical"))}</a><a href="#cycle">{esc(t("pages.cycle"))}</a><a href="#card-scores">{esc(t("pages.current"))}</a><a href="#faq">{esc(t("pages.card_faq_nav"))}</a></nav>'
        monthly_use = regular_use_summary(historical["regular_use"]["solid"], t) if identifier == "solid" else ""
        card_body += f'<section class="section" id="test-evidence"><h2>{esc(t("pages.historical"))}</h2><p class="muted">{esc(t("pages.historical_note"))}</p>{full_cards[identifier]}{monthly_use}</section>'
        card_body += money_flow(identifier, flow_inputs, t)
        card_body += card_route_details(identifier, snapshot, t)
        card_faq = faq_items('cards.' + identifier + '.faq', 4)
        card_body += f'<section class="section card-faq" id="faq" aria-labelledby="faq-title"><h2 id="faq-title">{esc(t("pages.card_faq_title", value0=row["name"]))}</h2><div class="faq-list">{faq_markup(card_faq)}</div></section>'
        card_body += card_sources(identifier, snapshot, t)
        card_body += '<div id="evidence">' + card_evidence[identifier] + (prime_evidence if identifier == 'solid' else '') + '</div>'
        card_body += f'<p class="footnote" id="cashback-note">{esc(t("page.comparison.p_3"))}</p>'
        render_page('cards/' + identifier + '/index.html', t('seo.cards.' + identifier + '.title'), t('seo.cards.' + identifier + '.description'), card_body, '<script src="../assets/card-flow.js" defer></script>', page_class='detail-page', card_id=identifier, questions=card_faq)
    rating_body = ranking_page(snapshot, scores, data, language, t) + cashback_chart(tier_data, t)
    rating_body += f'<section class="section"><h2>{esc(t("pages.raw_sources"))}</h2><p class="muted">{esc(t("pages.source_basis"))}</p><a href="../data/scoring.json" download>{esc(t("pages.download"))}</a></section>'
    render_page('ranking/index.html', t('seo.ranking_title'), t('pages.rating_description'), rating_body, '<script src="../assets/cashback-chart.js" defer></script>')
    print(f'Built {language} overview, ranking and nine card pages.')


for language in LANGUAGES:
    build(language)

if site_url:
    ns = 'http://www.sitemaps.org/schemas/sitemap/0.9'
    xhtml = 'http://www.w3.org/1999/xhtml'
    ET.register_namespace('', ns)
    ET.register_namespace('xhtml', xhtml)
    sitemap = ET.Element(f'{{{ns}}}urlset')
    for output_path, alternates in page_routes:
        entry = ET.SubElement(sitemap, f'{{{ns}}}url')
        ET.SubElement(entry, f'{{{ns}}}loc').text = site_url + '/' + output_path.removesuffix('index.html')
        ET.SubElement(entry, f'{{{ns}}}lastmod').text = research['updated_on']
        for lang, path in alternates:
            ET.SubElement(entry, f'{{{xhtml}}}link', rel='alternate', hreflang=lang, href=site_url + path)
    ET.indent(sitemap)
    (ROOT / 'sitemap.xml').write_bytes(ET.tostring(sitemap, encoding='utf-8', xml_declaration=True) + b'\n')
else:
    (ROOT / 'sitemap.xml').unlink(missing_ok=True)
