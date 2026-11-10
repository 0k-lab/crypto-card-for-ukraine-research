"""Shared ranking, route and chart markup for the static research pages."""
from decimal import Decimal
from datetime import date
import html
import json
from cashback import monthly_cashback
from scoring import CRITERIA
from sorting import comparison_cost, included_cashback_value


def esc(value):
    return html.escape(str(value), quote=True)


def encoded(value):
    return json.dumps(value, ensure_ascii=False).replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')


def points(item, criterion):
    return str(item['scores'][criterion]) + ('*' if criterion in item['conditional'] else '')


def value_text(criterion, item, card, t):
    value = item['values'][criterion]
    if criterion == 'currencies':
        return ' · '.join(card['currencies'])
    if value is None:
        return t('pages.no_minimum' if criterion in {'minimum_in', 'minimum_out'} else 'pages.not_established')
    if criterion in {'currencies', 'networks', 'actions'}:
        return str(value)
    if criterion == 'funding':
        return f'{value * 100:.3f}%'
    if criterion in {'income', 'cashback'}:
        return f'${value:.2f}'
    amount = '$' + format(value.normalize(), 'f')
    if criterion == 'withdrawal' and card.get('withdrawal_fee_basis') == 'historical_test':
        return t('pages.historical_fee', value0=amount)
    return amount



def criterion_note(criterion, card, t):
    key = card.get('criterion_notes', {}).get(criterion)
    return f'<p class="muted">{esc(t(key))}</p>' if key else ''

def score_badge(identifier, item, language, t):
    edition = 'en/' if language == 'en' else ''
    label = t('pages.score_label') + f' · {item["total"]:.1f}/10'
    return f'<a class="score-badge" href="../{edition}ranking/#score-{identifier}" aria-label="{esc(label)}"><strong>{item["total"]:.1f}<small>/10</small></strong></a>'


def purchase_chart(rows, language, t):
    edition = 'en/' if language == 'en' else ''
    ordered = sorted(rows, key=comparison_cost)
    values = []
    # A dot plot uses a labeled, zoomed axis to make small cost differences readable.
    low, high = Decimal('3.4'), Decimal('3.9')
    for row in ordered:
        gross = comparison_cost(row)
        net = gross - included_cashback_value(row)
        gross_x = (gross - low) / (high - low) * 100
        net_x = (net - low) / (high - low) * 100
        assert 0 <= net_x <= gross_x <= 100
        approximation = '≈' if 'reward_valuation' in row else ''
        label = f'{row["name"]}, {t("chart.gross")} ${gross:.4f}, {t("chart.net")} {approximation}${net:.4f}'
        values.append(f'''<div class="purchase-row"><a href="../{edition}cards/{row['id']}/">{esc(row['name'])}</a><div class="purchase-track" role="img" aria-label="{esc(label)}" style="--gross:{gross_x:.4f}%;--net:{net_x:.4f}%"><span class="purchase-connector"></span><span class="purchase-point gross"><span>${gross:.2f}</span></span><span class="purchase-point net"><span>{approximation}${net:.2f}</span></span></div></div>''')
    ticks = ''.join(f'<span>${value:.2f}</span>' for value in (low, Decimal('3.5'), Decimal('3.6'), Decimal('3.7'), Decimal('3.8'), high))
    return f'''<figure class="purchase-figure" aria-labelledby="purchase-heading"><div class="section-heading"><div><span class="eyebrow">{esc(t('chart.purchase_note'))}</span><h2 id="purchase-heading">{esc(t('chart.purchase_title'))}</h2><p>{esc(t('chart.purchase_description'))}</p></div></div><div class="chart-legend"><span><i class="legend-dot gross"></i>{esc(t('chart.gross'))}</span><span><i class="legend-dot net"></i>{esc(t('chart.net'))}</span></div><div class="purchase-rows">{''.join(values)}</div><div class="purchase-axis">{ticks}</div></figure>'''


def card_score_overview(item, card, language, t):
    edition = 'en/' if language == 'en' else ''
    criteria, inputs = [], []
    for criterion in CRITERIA:
        score = item['scores'][criterion]
        title = t('pages.withdrawal_networks') if criterion == 'networks' else t('score.' + criterion)
        value = esc(value_text(criterion, item, card, t))
        if criterion == 'networks':
            value += f'<span class="score-network-list">{esc(", ".join(card["withdrawal_networks"]))}</span>'
        identifier = 'score-input-' + criterion
        criteria.append(
            f'<div><dt><button type="button" popovertarget="{identifier}">{esc(t("score." + criterion))}</button></dt>'
            f'<dd><span class="score-track" aria-hidden="true"><i style="width:{score * 10}%"></i></span>'
            f'<strong>{points(item, criterion)}</strong></dd></div>'
        )
        conditional = f'<p class="muted">* {esc(t("pages.conditional_note"))}</p>' if criterion in item['conditional'] else ''
        inputs.append(
            f'<div class="score-input-popover" id="{identifier}" popover role="dialog" aria-labelledby="{identifier}-title">'
            f'<header class="score-input-heading"><h3 id="{identifier}-title">{esc(title)}</h3>'
            f'<button class="close" type="button" popovertarget="{identifier}" popovertargetaction="hide" aria-label="{esc(t("pages.close_input", value0=title))}" autofocus>×</button></header>'
            f'<p class="score-input-label">{esc(t("pages.value"))}</p><p class="score-input-value">{value}</p>'
            f'<p class="muted">{esc(t("score." + criterion + ".description"))}</p>{conditional}{criterion_note(criterion, card, t)}'
            f'<p class="muted">{esc(t("pages.current_note"))}</p>'
            f'<a href="../{edition}ranking/#criterion-{criterion}">{esc(t("pages.score_link"))} →</a></div>'
        )
    return f'<dl class="detail-criteria" aria-label="{esc(t("pages.score_label"))}">{"".join(criteria)}</dl>{"".join(inputs)}'


def route_networks(networks, t):
    if not networks:
        return esc(t('pages.route_incomplete'))
    labels = ''.join(f'<span>{esc(network)}</span>' for network in networks)
    return f'<span class="route-networks">{labels}</span>'


def route_table(title, headers, rows):
    headings = ''.join(f'<th scope="col" role="columnheader">{esc(label)}</th>' for label in headers)
    body = []
    for row in rows:
        cells = f'<th scope="row" role="rowheader"><span class="route-asset">{row[0]}</span></th>'
        cells += ''.join(
            f'<td role="cell"><span class="route-cell-label" aria-hidden="true">{esc(label)}</span>{value}</td>'
            for label, value in zip(headers[1:], row[1:])
        )
        body.append(f'<tr role="row">{cells}</tr>')
    return f'<div class="route-table-wrap"><table class="route-table" role="table" aria-label="{esc(title)}"><thead role="rowgroup"><tr role="row">{headings}</tr></thead><tbody role="rowgroup">{"".join(body)}</tbody></table></div>'



def regular_use_summary(summary, t):
    start = date.fromisoformat(summary['period_start']).strftime('%d.%m.%Y')
    end = date.fromisoformat(summary['period_end']).strftime('%d.%m.%Y')
    fields = [
        (t('regular_use.purchases'), summary['purchase_count']),
        (t('regular_use.debited'), '$' + format(Decimal(summary['debited_usd']), '.2f')),
        (t('regular_use.days'), summary['purchase_days']),
        (t('regular_use.cashback'), '$' + format(Decimal(summary['cashback_reported_usd']), '.2f')),
    ]
    ledger = '<dl class="ledger">' + ''.join(f'<div><dt>{esc(label)}</dt><dd>{esc(value)}</dd></div>' for label, value in fields) + '</dl>'
    rows = []
    for group in summary['currency_groups']:
        currency = group['original_currency']
        original = f"{Decimal(group['original_amount']):.2f} {currency}" if currency else '—'
        rows.append([esc(currency or t('regular_use.unspecified')), str(group['purchase_count']), esc(original), '$' + format(Decimal(group['debited_usd']), '.2f')])
    table = route_table(t('regular_use.breakdown'), [t('regular_use.currency'), t('regular_use.count'), t('regular_use.original'), t('regular_use.debit_usd')], rows)
    return (
        f'<section class="panel" id="regular-use"><header class="route-panel-heading"><h3>{esc(t("regular_use.title"))}</h3>'
        f'<span class="route-selected">{esc(start)} — {esc(end)}</span></header><p class="muted">{esc(t("regular_use.intro"))}</p>{ledger}'
        f'<details><summary>{esc(t("regular_use.breakdown"))}</summary>{table}<p class="muted">{esc(t("regular_use.unspecified_note", value0=sum(group["purchase_count"] for group in summary["currency_groups"] if group["original_currency"] is None)))}</p></details>'
        f'<p class="muted">{esc(t("regular_use.zero_note", value0=summary["outgoing_transfer_records_excluded"], value1=summary["incoming_transfer_records_excluded"]))}</p>'
        f'<p class="muted">{esc(t("regular_use.cashback_note"))}</p><p class="route-table-note">{esc(t("regular_use.privacy"))}</p>'
        f'<p class="muted"><a href="../data/historical.json">{esc(t("regular_use.data_link"))} →</a></p></section>'
    )

def card_route_details(identifier, snapshot, t):
    card = snapshot['cards'][identifier]
    funding_rows = []
    for route in card['funding_routes']:
        asset = esc(route['asset'])
        minimum = f'<span class="route-amount">{esc(route["minimum"])}</span> <span class="route-unit">{asset}</span>' if route['minimum'] is not None else f'<span class="route-unknown" aria-label="{esc(t("pages.route_minimum_unknown"))}">—</span>'
        funding_rows.append([
            asset, route_networks(route['networks'], t), minimum,
            esc(t('route.' + route['fee_note'])),
        ])
    funding_title = t('pages.funding_assets')
    funding_table = route_table(funding_title, [t('pages.asset'), t('pages.network'), t('pages.deposit_minimum'), t('pages.fee')], funding_rows)
    funding = (
        f'<section class="panel funding-assets" aria-labelledby="funding-assets-title">'
        f'<header class="route-panel-heading"><h3 id="funding-assets-title">{esc(funding_title)}</h3></header>'
        f'{funding_table}<p class="route-table-note">{esc(t("pages.route_scope"))}</p></section>'
    )
    withdrawal_tables = []
    for field, title in (('withdrawal_minima', 'pages.per_asset'), ('withdrawal_fees', 'pages.withdrawal_fee')):
        if field not in card:
            continue
        rows = []
        for asset, networks in card[field].items():
            for network, amount in networks.items():
                amount_text = t('pages.no_minimum') if amount is None else f'{amount} {asset}'
                rows.append([esc(asset), route_networks([network], t), esc(amount_text)])
        table_title = t(title)
        amount_heading = t('pages.minimum') if field == 'withdrawal_minima' else table_title
        table = route_table(table_title, [t('pages.asset'), t('pages.network'), amount_heading], rows)
        withdrawal_tables.append(f'<h4 class="route-table-heading">{esc(table_title)}</h4>{table}')
    quote_note = ''
    if identifier == 'solid':
        quote = card['withdrawal_quote']
        checked_on = date.fromisoformat(quote['observed_on']).strftime('%d.%m.%Y')
        quote_note = f'<aside class="route-callout"><p>{esc(t("pages.solid_withdrawal_quote", value0=checked_on, value1=quote["initial_fee"], value2=quote["sample_withdrawal_amount"], value3=quote["sample_fee"]))}</p></aside>'
    withdrawal = (
        f'<section class="panel withdrawal-routes" aria-labelledby="withdrawal-routes-title">'
        f'<header class="route-panel-heading"><h3 id="withdrawal-routes-title">{esc(t("flow.withdrawal"))}</h3>'
        f'<span class="route-selected">{esc(card["withdrawal_route"])}</span></header>'
        f'<p class="route-table-note">{esc(t("pages.withdrawal_route_scope"))}</p>'
        f'<div class="withdrawal-networks"><span class="label">{esc(t("pages.withdrawal_networks"))}</span>{route_networks(card["withdrawal_networks"], t)}</div>'
        f'{"".join(withdrawal_tables)}{quote_note}</section>'
    )
    update = ''
    if identifier == 'simple':
        wallet = card['wallet_engine_update']
        checked_on = date.fromisoformat(wallet['checked_on']).strftime('%d.%m.%Y')
        rows = [[esc(network), esc(', '.join(tokens))] for network, tokens in wallet['gasless_tokens_by_network'].items()]
        table = route_table(t('pages.gasless_networks'), [t('pages.network'), t('pages.gasless_tokens')], rows)
        update = (
            f'<section class="panel" id="simple-wallet-update"><header class="route-panel-heading"><h3>{esc(t("pages.simple_wallet_title"))}</h3>'
            f'<span class="route-selected">{esc(checked_on)}</span></header>'
            f'<p class="muted">{esc(t("pages.simple_wallet_migration"))}</p>'
            f'<p class="muted">{esc(t("pages.simple_gasless_scope"))}</p>{table}'
            f'<p class="route-table-note">{esc(t("pages.simple_gasless_exclusions"))}</p>'
            f'<aside class="route-callout">{criterion_note("withdrawal", card, t)}</aside></section>'
        )
    elif identifier == 'whitebit':
        fees = card['payment_fees']
        checked_on = date.fromisoformat(fees['checked_on']).strftime('%d.%m.%Y')
        transaction = f'{(Decimal(fees["transaction_rate"]) * 100).normalize():f}% + ${fees["transaction_fixed_usd"]}'
        conversion = f'{(Decimal(fees["possible_conversion_rate"]) * 100).normalize():f}%'
        update = (
            f'<section class="panel" id="whitebit-payment-fees"><header class="route-panel-heading"><h3>{esc(t("pages.payment_fees"))}</h3>'
            f'<span class="route-selected">{esc(checked_on)}</span></header>'
            f'<dl class="ledger"><div><dt>{esc(t("pages.transaction_fee"))}</dt><dd>{esc(transaction)}</dd></div>'
            f'<div><dt>{esc(t("pages.possible_conversion_fee"))}</dt><dd>{esc(conversion)}</dd></div></dl>'
            f'<p class="muted">{esc(t("pages.whitebit_fee_scope"))}</p>'
            f'<aside class="route-callout">{criterion_note("purchase", card, t)}</aside></section>'
        )
    return f'<section class="section" id="card-scores"><h2>{esc(t("pages.current"))}</h2><p class="muted">{esc(t("pages.current_note"))}</p>{update}{funding}{withdrawal}</section>'


def faq_markup(items):
    return ''.join(f'<details data-faq-id="q{index + 1}"><summary>{esc(item["name"])}</summary><p>{esc(item["acceptedAnswer"]["text"])}</p></details>' for index, item in enumerate(items))


def card_sources(identifier, snapshot, t):
    sources = ''.join(f'<a href="{esc(url)}">{esc(t("pages.official_source", value0=n))} ↗</a>' for n, url in enumerate(snapshot['cards'][identifier]['sources'], 1))
    return f'<section class="section route-sources" id="sources"><h2>{esc(t("pages.raw_sources"))}</h2><p class="muted">{esc(t("pages.source_basis"))}</p><div class="detail-sources">{sources}</div></section>'



def ranking_page(snapshot, scores, measurements, language, t):
    edition = 'en/' if language == 'en' else ''
    names = {row['id']: row['name'] for row in measurements['rows']}
    order = sorted(scores, key=lambda identifier: (-scores[identifier]['total'], names[identifier]))
    head = ''.join(f'<th scope="col"><a href="#criterion-{key}">{esc(t("score." + key))}</a></th>' for key in CRITERIA)
    rows = []
    for identifier in order:
        item = scores[identifier]
        cells = ''.join(f'<td>{points(item, key)}</td>' for key in CRITERIA)
        rows.append(f'<tr id="score-{identifier}"><th scope="row"><a href="../{edition}cards/{identifier}/">{esc(names[identifier])}</a></th>{cells}<td class="total-score">{item["total"]:.1f}</td></tr>')
    methods = []
    for key in CRITERIA:
        inputs = []
        for identifier in order:
            item = scores[identifier]
            inputs.append(f'<tr><th scope="row">{esc(names[identifier])}</th><td>{esc(value_text(key, item, snapshot["cards"][identifier], t))}{criterion_note(key, snapshot["cards"][identifier], t)}</td><td>{points(item, key)}</td></tr>')
        methods.append(f'<details class="panel" id="criterion-{key}"><summary>{esc(t("score." + key))}</summary><p class="muted">{esc(t("score." + key + ".description"))}</p><div class="scroll"><table><thead><tr><th scope="col">{esc(t("pages.details"))}</th><th scope="col">{esc(t("pages.value"))}</th><th scope="col">{esc(t("pages.points"))}</th></tr></thead><tbody>{"".join(inputs)}</tbody></table></div></details>')
    notes = ''.join(f'<p>{esc(t(key))}</p>' for key in ('pages.method_rank', 'pages.method_limits', 'pages.method_unknown', 'pages.method_routes', 'pages.recent_score_review', 'pages.income_conditions', 'pages.network_conditions', 'pages.cashback_conditions'))
    return f'''<section class="page-intro"><span class="eyebrow">{esc(t('pages.provisional'))}</span><h1>{esc(t('pages.rating_title'))}</h1><p class="lead">{esc(t('pages.rating_intro'))}</p></section><nav class="nav" aria-label="{esc(t('pages.rating'))}"><a href="#matrix">{esc(t('pages.rating'))}</a><a href="#scoring-method">{esc(t('pages.method'))}</a><a href="#cashback-chart">{esc(t('chart.cashback_title'))}</a></nav><section id="matrix" aria-label="{esc(t('pages.rating'))}"><h2>{esc(t('pages.choice_title'))}</h2><p class="muted">{esc(t('pages.choice_description'))}</p><p class="muted" id="matrix-note">{esc(t('pages.matrix_note'))}</p><p class="table-scroll-hint muted">{esc(t('pages.scroll_hint'))}</p><div class="scroll matrix-scroll" role="region" tabindex="0" aria-label="{esc(t('pages.rating'))}"><table class="score-matrix" aria-describedby="matrix-note"><thead><tr><th scope="col">{esc(t('page.comparison.th_1'))}</th>{head}<th scope="col">{esc(t('pages.average'))}</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></section><section class="section" id="scoring-method"><h2>{esc(t('pages.method'))}</h2><div class="reading">{notes}</div>{''.join(methods)}</section><section class="section" id="income-method"><h2>{esc(t('score.income'))}</h2><div class="reading"><p>{esc(t('pages.method_income'))}</p><p>{esc(t('pages.method_income_bands'))}</p></div></section><section class="section" id="cashback-method"><h2>{esc(t('score.cashback'))}</h2><p class="muted">{esc(t('pages.method_cashback'))}</p></section>'''


def cashback_chart(tiers, t):
    programs = []
    for identifier, index in (('solid', 0), ('solid', 1), ('coca', 0), ('coca', 1)):
        tier = tiers['cards'][identifier]['tiers'][index]
        name = ('Solid Core', t('chart.prime_label'), 'COCA Starter', 'COCA Standard · 300 COCA')[len(programs)]
        fee = Decimal(tier['annual_fee_usd']) / 12
        samples = []
        for spend in range(0, 5001, 50):
            payout = monthly_cashback(tier, spend)[1]
            assert payout is not None
            samples.append([spend, float(payout), float(payout - fee)])
        programs.append({'name': name, 'samples': samples})
    left, right, top, bottom = 65, 925, 20, 335
    def y(value):
        return bottom - (value + 20) / 130 * (bottom - top)
    paths = []
    legend = []
    outputs = []
    for index, program in enumerate(programs):
        points_text = ' '.join(f'{left + spend / 5000 * (right - left):.2f},{y(payout):.2f}' for spend, payout, net in program['samples'])
        paths.append(f'<polyline class="chart-line series-{index}" data-program="{index}" points="{points_text}"/>')
        legend.append(f'<span><i class="line-swatch series-{index}"></i>{esc(program["name"])}</span>')
        outputs.append(f'<div><span>{esc(program["name"])}</span><strong data-budget-result="{index}">${program["samples"][20][1]:.2f}</strong></div>')
    grid = ''.join(f'<line x1="{left}" x2="{right}" y1="{y(value):.2f}" y2="{y(value):.2f}" class="chart-grid"/><text x="{left - 10}" y="{y(value)+4:.2f}" text-anchor="end">{value}</text>' for value in (-20, 0, 25, 50, 75, 100))
    ticks = ''.join(f'<text x="{left + value / 5000 * (right-left):.2f}" y="360" text-anchor="middle">{value}</text>' for value in range(0, 5001, 1000))
    config = {'programs': programs, 'left': left, 'right': right, 'top': top, 'bottom': bottom}
    return f'''<section class="section" id="cashback-chart"><h2>{esc(t('chart.cashback_title'))}</h2><p class="muted">{esc(t('chart.cashback_note'))}</p><div class="chart-legend">{''.join(legend)}</div><div class="chart-controls"><label>{esc(t('chart.basis'))}<select id="cashback-basis" aria-label="{esc(t('chart.basis'))}"><option value="1">{esc(t('chart.payout'))}</option><option value="2">{esc(t('chart.after_fee'))}</option></select></label><label for="cashback-budget">{esc(t('chart.budget'))}<output id="budget-label" for="cashback-budget">$1,000</output><input id="cashback-budget" type="range" min="0" max="5000" step="50" value="1000"></label></div><div class="scroll cashback-plot"><svg viewBox="0 0 960 405" role="img" aria-labelledby="cashback-chart-title"><title id="cashback-chart-title">{esc(t('chart.cashback_title'))}</title><text x="65" y="14">{esc(t('chart.cashback_axis'))}</text>{grid}{ticks}{''.join(paths)}<line id="budget-guide" x1="237" x2="237" y1="20" y2="335" class="budget-guide"/><text x="495" y="395" text-anchor="middle">{esc(t('chart.spend_axis'))}</text></svg></div><div class="budget-results" aria-live="polite" aria-atomic="true">{''.join(outputs)}</div><p class="muted">{esc(t('chart.fee_explanation'))}</p><p class="muted">{esc(t('chart.coca_explanation'))}</p><p class="muted">{esc(t('chart.prime_explanation'))}</p><script type="application/json" id="cashback-chart-data">{encoded(config)}</script></section>'''
