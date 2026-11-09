"""Process diagrams assembled from the study's existing measurements and terms."""
from datetime import date
from decimal import Decimal
from html import escape
from earning import monthly_income
from sorting import comparison_cost


def card_processes(identifier, datasets, t):
    row = next(row for row in datasets['measurements']['rows'] if row['id'] == identifier)
    test = next(test for test in datasets['funding']['tests'] if test['card'] == identifier)
    card = datasets['scoring']['cards'][identifier]
    program = datasets['tiers']['cards'][identifier]
    tested_on = date.fromisoformat(test['date']).strftime('%d.%m.%Y')
    funds_source = '#funding-' + identifier
    reward_source = '#tiers-' + identifier

    def node(title, detail, status):
        assert status in {'test', 'terms', 'app', 'pending', 'model'}
        return {'title': t('flow.' + title), 'detail': str(detail), 'status': status}

    def path(title, source, *steps):
        assert 2 <= len(steps) <= 5 and source.startswith('#')
        return {'title': title, 'source': source, 'steps': steps}

    test_title = t('flow.test_date', value0=tested_on)
    current_title = t('flow.current_route')
    snapshot_date = date.fromisoformat(datasets['scoring']['checked_on']).strftime('%d.%m.%Y')
    currencies = ' · '.join(card['currencies'])
    funding = []
    if identifier == 'solid':
        for route in test['funding_routes']:
            network = 'Arbitrum → Fuse' if route['route'] == 'arbitrum_to_fuse' else 'Fuse'
            detail = t('flow.solid_bridge') if route['route'] == 'arbitrum_to_fuse' else t('pages.zero_fee')
            funding.append(path(test_title + ' · ' + network, funds_source,
                node('wallet', route['sent_token_amount'] + ' USDT · ' + network, 'test'),
                node('conversion', detail, 'test'),
                node('balance', route['credited_token_amount'] + ' USDT', 'test')))
        small = card['confirmed_small_deposit']
        funding.append(path(date.fromisoformat(small['credited_on']).strftime('%d.%m.%Y') + ' · USDC / Arbitrum', '#card-scores',
            node('wallet', small['amount'] + ' USDC · ' + small['network'], 'app'),
            node('received', t('flow.solid_cent'), 'app'),
            node('balance', small['amount'] + ' USDC', 'app')))
        funding.append(path('IBAN / SEPA → EURC', funds_source,
            node('bank', 'SEPA', 'terms'),
            node('received', t('flow.solid_sepa'), 'terms'),
            node('balance', 'EURC / Base', 'terms')))
    elif identifier == 'trustee_plus':
        credit = test['card_funding']
        funding.append(path(test_title, funds_source,
            node('wallet', test['sent_token_amount'] + ' USDT · Polygon', 'test'),
            node('internal_wallet', test['credited_token_amount'] + ' USDT', 'test'),
            node('send', t('flow.trustee_funding'), 'test'),
            node('card', credit['credited_token_amount'] + ' ' + credit['credited_asset_as_displayed'], 'test')))
    else:
        network = test['network'] or t('flow.network_unspecified')
        sent = test['sent_token_amount'] + ' ' + test.get('sent_asset', 'USDT')
        if identifier in {'coca', 'keyone'}:
            credited = test['credit_execution']['transaction_amount'] + ' USDC'
            detail = t('flow.keyone_fee') if identifier == 'keyone' else t('flow.coca_conversion')
        elif identifier == 'simple':
            credited = t('flow.simple_credit')
            detail = network
        else:
            credited = test['credited_token_amount'] + ' USDT'
            detail = t('flow.bybit_funding') if identifier == 'bybit' else t('flow.kolo_balance') if identifier == 'kolo' else t('flow.exchange_funding') if identifier == 'whitebit' else network
        funding.append(path(test_title, funds_source,
            node('wallet', sent + ' · ' + network, 'test'),
            node('conversion' if identifier in {'coca', 'keyone'} else 'received', detail, 'test'),
            node('balance', credited, 'test')))
    if identifier == 'coca':
        funding.append(path(snapshot_date + ' · ' + t('flow.small_deposit'), '#card-scores',
            node('send', '$' + card['confirmed_small_deposit']['nominal_usd'], 'app'),
            node('balance', t('flow.coca_cent'), 'app')))
    if identifier not in {'solid', 'okx'}:
        level = 'terms' if identifier in {'bybit', 'whitebit', 'keyone', 'trustee_plus'} else 'app'
        fee = t('pages.keyone_fee' if identifier == 'keyone' else 'pages.trustee_fee' if identifier == 'trustee_plus' else 'pages.zero_fee')
        funding.append(path(current_title, '#funding-assets-title',
            node('wallet', card['deposit_route'], level),
            node('internal_wallet' if identifier == 'trustee_plus' else 'received', fee, level),
            node('exchange_balance' if identifier in {'bybit', 'whitebit'} else 'balance', card['deposit_route'] if identifier in {'bybit', 'whitebit'} else currencies, 'app')))

    payment = [path(t('flow.purchase_date'), '#test-evidence',
        node('balance', row['card_currency'], 'test'),
        node('merchant', datasets['measurements']['merchant_amount_uah'] + ' ₴', 'test'),
        node('debit', format(comparison_cost(row), 'f') + ' ' + t('flow.usd_equivalent'), 'test'))]
    if identifier == 'bybit':
        final = row['final_transaction']
        quote = row['conversion_quote']
        payment[0] = path(t('flow.purchase_date'), '#test-evidence',
            node('savings', final['spent_amount'] + ' USDT · Easy Earn', 'test'),
            node('conversion', t('flow.bybit_conversion', value0=final['card_amount_usd'], value1=quote['shown_conversion_fee_usdt']), 'test'),
            node('merchant', datasets['measurements']['merchant_amount_uah'] + ' ₴ · ' + t('flow.bybit_fx', value0=final['foreign_transaction_fee_usd']), 'test'))
    elif identifier == 'whitebit':
        final = row['final_transaction']
        payment[0] = path(t('flow.purchase_date'), '#test-evidence',
            node('exchange_balance', final['spent_amount'] + ' USDT', 'app'),
            node('conversion', t('flow.whitebit_conversion', value0=final['card_amount_usd']), 'app'),
            node('merchant', datasets['measurements']['merchant_amount_uah'] + ' ₴', 'test'))
    for earlier in datasets['history']['usd_tests']:
        if earlier['card'] != identifier:
            continue
        evidence = 'test' if earlier.get('source_file') or earlier.get('source_files') else 'app'
        asset = t('flow.usd_display') if earlier['asset'] == 'USD display' else earlier['asset']
        payment.append(path(t('flow.historical_route') + ' · ' + earlier.get('merchant', 'USD'), '#test-evidence',
            node('balance', asset, evidence),
            node('merchant', '$' + earlier['merchant_usd'], 'app' if identifier == 'solid' else evidence),
            node('debit', earlier['debit'] + ' ' + asset, evidence)))
    bill = datasets['history']['uah_bill_test']
    for outcome in bill['results']:
        if outcome['card'] != identifier:
            continue
        if outcome.get('result', '').startswith('declined'):
            steps = [node('merchant', bill['merchant_uah'] + ' ₴ · ' + bill['merchant'], 'app'),
                     node('pending', t('flow.payment_declined'), 'app')]
        else:
            debit = outcome.get('tx_debit', outcome.get('debit'))
            if identifier == 'kolo':
                debit = outcome['debit_usdt'] + ' USDT + ' + outcome['debit_usdc'] + ' USDC'
            elif identifier == 'simple':
                debit = t('flow.bill_difference', value0=outcome['tx_debit'], value1=outcome['balance_delta'])
            else:
                debit += ' USD'
            steps = [node('merchant', bill['merchant_uah'] + ' ₴ · ' + bill['merchant'], 'app'), node('debit', debit, 'app')]
        payment.append(path(bill['date'] + ' · RozetkaPay', '#test-evidence', *steps))
    if identifier == 'solid':
        payment.append(path(t('flow.payment_confirmation'), '#test-evidence',
            node('merchant', t('flow.confirmation_required'), 'app'),
            node('card', t('flow.solid_approvals'), 'app'),
            node('eligible', t('flow.confirm_in_app'), 'app')))
        payment.append(path('EUR / EURC · ' + t('flow.sufficient_balance'), funds_source,
            node('balance', 'EURC / Base · Wirex', 'terms'),
            node('merchant', t('flow.solid_eur'), 'terms')))
        payment.append(path('EUR / EURC · ' + t('flow.insufficient_balance'), funds_source,
            node('balance', 'EURC / Base · Wirex', 'terms'),
            node('fallback', t('flow.solid_eur_fallback'), 'terms')))

    cashback = []
    reward = row['observed_reward']
    if Decimal(reward['amount']):
        steps = [node('merchant', datasets['measurements']['merchant_amount_uah'] + ' ₴', 'test'), node('reward', reward['amount'] + ' ' + reward['asset'], 'test')]
        if identifier == 'bybit':
            steps.append(node('conversion', row['points_assessment']['points'] + ' × ' + row['points_assessment']['usdt_per_point'] + ' = ' + row['points_assessment']['cashback_deduction_usd'] + ' USDT', 'model'))
            steps.append(node('claim', t('flow.bybit_points_pending'), 'pending'))
        elif identifier == 'whitebit':
            steps.append(node('received', t('flow.whitebit_payout'), 'test'))
        elif identifier == 'trustee_plus':
            steps.append(node('reward', t('flow.trustee_points'), 'app'))
        else:
            steps.append(node('claim', t('flow.kolo_payout') if identifier == 'kolo' else t('flow.claim_unknown'), 'pending'))
        cashback.append(path(t('flow.purchase_date'), '#test-evidence', *steps))
    if identifier in {'solid', 'coca', 'bybit'}:
        tier = program['tiers'][0]
        rate = format((Decimal(tier['rate']) * 100).normalize(), 'f')
        cap_key = 'flow.claim_capacity' if identifier == 'coca' else 'flow.base_cashback'
        cap_text = t(cap_key, value0=rate, value1=tier['cap'])
        steps = [node('merchant', t('flow.eligible_purchases'), 'terms'), node('reward', cap_text, 'app' if identifier == 'bybit' else 'terms')]
        if identifier == 'coca':
            steps += [node('wait', t('flow.coca_wait'), 'terms'), node('balance', 'USD', 'terms')]
        elif identifier == 'solid':
            steps += [node('wait', t('flow.solid_wait'), 'terms'), node('savings', t('flow.solid_savings_reward'), 'terms')]
        else:
            steps += [node('wait', t('flow.bybit_points'), 'terms'), node('balance', 'USDT', 'terms')]
        cashback.append(path(t('flow.current_program'), reward_source, *steps))
    elif identifier == 'kolo':
        cashback.append(path(t('flow.current_program'), reward_source,
            node('merchant', 'EUR', 'app'), node('reward', t('flow.kolo_cashback'), 'terms'), node('received', 'BTC', 'terms')))
    elif identifier == 'whitebit':
        cashback.append(path(t('flow.current_program'), reward_source,
            node('eligible', t('flow.whitebit_category'), 'app'), node('reward', t('flow.whitebit_regular'), 'app')))
        cashback.append(path('Welcome', reward_source,
            node('merchant', t('flow.first_purchase'), 'terms'), node('reward', t('flow.whitebit_welcome'), 'terms')))
    elif identifier != 'trustee_plus':
        cashback.append(path(t('flow.current_program'), reward_source,
            node('merchant', 'USDT' if identifier == 'okx' else currencies, 'app'),
            node('reward', t('flow.okx_usdg') if identifier == 'okx' else t('flow.no_cashback'), 'terms' if identifier == 'okx' else 'app')))

    processes = [('funding', funding), ('payment', payment), ('cashback', cashback)]
    offer = card['income_offer']
    if offer['rate'] is not None:
        rate_details = t('flow.' + identifier + ('_yield' if identifier == 'solid' else '_earn' if identifier in {'bybit', 'coca'} else '_earning'))
        steps = [node('savings' if identifier in {'solid', 'bybit'} else 'balance', 'USDT' if identifier == 'bybit' else 'USDC' if identifier == 'simple' else 'USD Yield / soUSD' if identifier == 'solid' else 'USD', 'app'),
                 node('rate', rate_details, 'app')]
        income = monthly_income(offer, datasets['earning']['model'])[0]
        steps.append(node('reward', t('flow.model_income', value0=f'{income:.2f}'), 'model'))
        if identifier != 'bybit':
            claim = t('flow.solid_savings_exit') if identifier == 'solid' else t('flow.coca_earn_claim') if identifier == 'coca' else t('flow.simple_claim')
            steps.append(node('claim', claim, 'terms' if identifier in {'solid', 'coca'} else 'app'))
        earning_paths = [path(snapshot_date, '#card-scores', *steps)]
        if identifier == 'bybit':
            earning_paths.append(path(t('flow.purchase_date'), '#test-evidence',
                node('savings', 'Flexible Earn · USDT', 'test'),
                node('payment_source', t('flow.bybit_deduction'), 'test')))
        if identifier == 'solid':
            earning_paths.append(path('Credit · 09.10.2026', '#earning-solid',
                node('savings', 'USD Yield / soUSD', 'terms'), node('credit', t('flow.solid_credit'), 'app'), node('card', t('flow.solid_credit_debt'), 'terms')))
        processes.append(('earning', earning_paths))
    elif identifier == 'okx':
        processes.append(('earning', [path('USDG', '#earning-okx',
            node('savings', 'USDG', 'terms'), node('eligible', t('flow.okx_usdg'), 'terms'))]))

    withdrawal = test['withdrawal']
    outgoing = []
    received = withdrawal.get('recipient_token_amount_onchain')
    if received is not None:
        asset = withdrawal['asset']
        start = withdrawal.get('requested_token_amount', withdrawal.get('requested_total_debit_as_displayed', received))
        detail = start + ' ' + asset
        if identifier == 'kolo':
            detail += ' · ' + t('flow.additional_funds', value0=withdrawal['other_amount_excluded_from_new_deposit'], value1=asset)
        elif identifier == 'solid':
            detail += ' · ' + t('flow.solid_combined')
        steps = [node('balance', detail, 'test')]
        if identifier == 'simple':
            steps.append(node('internal_wallet', withdrawal['stages'][0]['received_usdc'] + ' USDC · Base · ' + t('flow.transfer_fee', value0=withdrawal['fee_amount'], value1='USDC'), 'test'))
        else:
            steps.append(node('send', withdrawal['network'] + ' · ' + t('flow.transfer_fee', value0=withdrawal['fee_amount'], value1=asset), 'test'))
        steps.append(node('wallet', received + ' ' + asset + ' · ' + withdrawal['network'], 'test'))
        outgoing.append(path(test_title, funds_source, *steps))
    elif identifier == 'whitebit':
        outgoing.append(path(test_title + ' · Plasma', funds_source,
            node('exchange_balance', withdrawal['total_debit_as_displayed'] + ' USDT · ' + t('flow.additional_funds', value0=withdrawal['other_account_residual_usdt'], value1='USDT'), 'app'),
            node('review', withdrawal['recipient_token_amount_as_displayed'] + ' USDT + ' + withdrawal['fees_as_displayed'] + ' USDT', 'app'),
            node('wallet', t('flow.no_outcome'), 'pending')))
    elif identifier == 'trustee_plus':
        attempt = withdrawal['base_attempt']
        outgoing.append(path(test_title + ' · Base', funds_source,
            node('internal_wallet', attempt['requested_amount'] + ' USDC', 'app'), node('minimum', t('flow.trustee_base_block'), 'app')))
        swap = withdrawal['exchange_quote']
        outgoing.append(path(t('flow.historical_route') + ' · USDC → USDT', funds_source,
            node('internal_wallet', swap['give_amount'] + ' ' + swap['give_asset'], 'app'),
            node('conversion', t('flow.trustee_swap'), 'app'), node('received', swap['receive_amount'] + ' ' + swap['receive_asset'], 'app')))
        attempt = withdrawal['polygon_attempt']
        review = withdrawal['review']
        outgoing.append(path(test_title + ' · Polygon', funds_source,
            node('internal_wallet', attempt['wallet_balance_as_displayed'] + ' USDT', 'app'),
            node('minimum', attempt['available_after_fee_as_displayed'] + ' USDT < 10 USDT', 'app'),
            node('received', t('flow.trustee_extra'), 'app'),
            node('review', review['total_debit_as_displayed'] + ' USDT → ' + review['requested_recipient_amount'] + ' USDT + ' + review['fee_as_displayed'] + ' USDT', 'app'),
            node('wallet', t('flow.no_outcome'), 'pending')))
    level = 'terms' if identifier in {'bybit', 'whitebit', 'keyone'} else 'app'
    steps = [node('balance', currencies, 'app')]
    if identifier in {'simple', 'trustee_plus'}:
        steps.append(node('internal_wallet', t('pages.via_wallet'), 'app'))
    minimum = t('pages.no_minimum') if card['minimum_out_total'] is None else t('flow.minimum_route', value0=card['minimum_out_total'])
    route = t('flow.transfer_fee', value0=card['withdrawal_fee'], value1=t('flow.usd_equivalent')) + ' · ' + minimum
    source = '#card-scores'
    if identifier == 'simple':
        level = 'terms'
        steps.append(node('upgrade', t('flow.simple_gasless_activation'), level))
        route = t('flow.simple_gasless_fee')
        source = '#simple-wallet-update'
    steps += [node('send', route, level), node('wallet', card['withdrawal_route'], level)]
    outgoing.append(path(current_title, source, *steps))
    if identifier == 'solid':
        quote = card['withdrawal_quote']
        for network in quote['networks']:
            outgoing.append(path(t('flow.alternative') + ' · USDC / ' + network, '#card-scores',
                node('balance', t('flow.solid_quote_amount', value0=quote['sample_withdrawal_amount']), 'app'),
                node('review', t('flow.solid_usdc_exit', value0=card['withdrawal_minima']['USDC'][network], value1=quote['sample_withdrawal_amount'], value2=quote['sample_fee']), 'app'),
                node('wallet', 'USDC · ' + network + ' · ' + t('flow.no_outcome'), 'pending')))
        outgoing.append(path(t('flow.alternative') + ' · Arbitrum', funds_source,
            node('balance', withdrawal['requested_token_amount'] + ' USDT', 'app'), node('review', t('flow.solid_other_exit'), 'app'), node('wallet', t('flow.no_outcome'), 'pending')))
        outgoing.append(path('IBAN / SEPA', funds_source,
            node('balance', 'EURC', 'terms'), node('send', t('flow.solid_sepa_out'), 'terms')))
    elif identifier == 'okx':
        outgoing.append(path(t('flow.alternative') + ' · Ethereum', funds_source,
            node('send', '1 USDT · Ethereum', 'app'), node('review', t('flow.okx_eth'), 'app'), node('wallet', t('flow.no_outcome'), 'pending')))
        outgoing.append(path('Ethereum', '#losses-okx',
            node('send', 'Ethereum', 'app'), node('minimum', t('flow.okx_activation'), 'app')))
    processes.append(('withdrawal', outgoing))

    if identifier in {'solid', 'coca', 'bybit', 'keyone'}:
        detail = t('flow.solid_lock' if identifier == 'solid' else 'flow.coca_upgrade' if identifier == 'coca' else 'flow.bybit_upgrade' if identifier == 'bybit' else 'flow.keyone_upgrade')
        result = t('flow.solid_prime' if identifier == 'solid' else 'flow.coca_standard' if identifier == 'coca' else 'flow.bybit_beta' if identifier == 'bybit' else 'flow.keyone_premium')
        steps = [node('plan', detail, 'terms'), node('upgrade', result, 'terms')]
        if identifier == 'solid':
            steps.append(node('rate', t('flow.solid_boost'), 'terms'))
        processes.append(('level', [path(t('flow.current_program'), reward_source, *steps)]))
    if identifier in {'solid', 'coca'}:
        steps = [node('card', t('flow.referral_' + identifier), 'terms' if identifier == 'solid' else 'app')]
        if identifier == 'solid':
            steps.append(node('wait', t('flow.referral_solid_wait'), 'terms'))
        steps.append(node('reward', t('flow.referral_' + identifier + '_bonus'), 'terms' if identifier == 'solid' else 'app'))
        processes.append(('referral', [path(t('flow.referral_conditions'), '#get-card', *steps)]))
    return processes


def balance_map(identifier, datasets, processes, t):
    """Show account relationships without merging separate tests into one transfer."""
    card = datasets['scoring']['cards'][identifier]
    row = next(row for row in datasets['measurements']['rows'] if row['id'] == identifier)
    reward = row['observed_reward']
    summaries = {
        'funding': card['deposit_route'],
        'payment': t('flow.hub.purchase', value0=datasets['measurements']['merchant_amount_uah'], value1=f'{comparison_cost(row):.2f}'),
        'cashback': reward['amount'] + ' ' + reward['asset'] if Decimal(reward['amount']) else t('flow.hub.no_reward'),
        'withdrawal': card['withdrawal_route'],
        'level': {'solid': 'Prime', 'coca': 'Standard', 'bybit': 'Beta', 'keyone': 'Premium'}.get(identifier, ''),
        'referral': 'FUSE' if identifier == 'solid' else 'USD',
    }
    offer = card['income_offer']
    if offer['rate'] is not None:
        rate = format((Decimal(offer['rate']) * 100).normalize(), 'f')
        summaries['earning'] = rate + '% ' + offer['rate_kind'].upper()
        if identifier == 'bybit':
            summaries['earning'] = t('flow.hub.bybit_rate', value0=rate, value1=offer['bonus_balance_cap_usd'])
    else:
        summaries['earning'] = t('flow.hub.usdg_unavailable')
    notes = {key: t('flow.hub.' + key) for key, routes in processes}
    if Decimal(reward['amount']) == 0:
        notes['cashback'] = t('flow.hub.reward_rules')
    if identifier == 'solid':
        notes['cashback'] = t('flow.hub.to_savings')
    elif identifier in {'whitebit', 'kolo', 'trustee_plus'}:
        notes['cashback'] = t('flow.hub.separate_reward')
    elif identifier == 'bybit':
        notes['cashback'] = t('flow.hub.points_conversion')
    nodes = []
    tooltips = []
    for key, routes in processes:
        label = escape(t('flow.' + key))
        info_label = escape(t('flow.hub.info', value0=t('flow.' + key)), quote=True)
        nodes.append(
            f'<div class="hub-process {key}" data-process="{key}">'
            f'<a class="hub-process-toggle" href="#flow-{key}" aria-describedby="hub-note-{key}">'
            f'<strong><span class="hub-title">{label}</span><span class="hub-open" aria-hidden="true">+</span></strong>'
            f'<span class="hub-value">{escape(summaries[key])}</span></a>'
            f'<button type="button" class="hub-info" popovertarget="hub-note-{key}" aria-label="{info_label}" style="anchor-name:--hub-note-{key}">i</button></div>'
        )
        tooltips.append(f'<div class="hub-tooltip" id="hub-note-{key}" popover role="tooltip" style="position-anchor:--hub-note-{key}">{escape(notes[key])}</div>')
    links = [
        ('money', 'M 280 355 H 355', 'funding', 'balance', 'right', 'left', False),
        ('money', 'M 605 355 H 680', 'balance', 'payment', 'right', 'left', False),
        ('conditional', 'M 805 270 V 140 Q 805 110 775 110 H 605', 'payment', 'cashback', 'top', 'right', False),
        ('money', 'M 480 440 V 515', 'balance', 'withdrawal', 'bottom', 'top', False),
    ]
    keys = {key for key, routes in processes}
    if identifier == 'solid':
        links.append(('conditional', 'M 355 110 H 280', 'cashback', 'earning', 'left', 'right', False))
    elif identifier in {'coca', 'bybit'}:
        links.append(('conditional', 'M 480 195 V 270', 'cashback', 'balance', 'bottom', 'top', False))
    if 'earning' in keys:
        kind = 'conditional' if offer['rate'] is not None else 'relation'
        links.append((kind, 'M 280 170 Q 325 170 355 285', 'earning', 'balance', 'right', 'left', offer['rate'] is not None))
    if 'level' in keys:
        links.append(('relation', 'M 280 570 Q 325 570 355 425', 'level', 'balance', 'right', 'left', False))
    if 'referral' in keys:
        links.append(('relation', 'M 680 570 Q 635 570 605 425', 'referral', 'balance', 'left', 'right', False))
    edges = []
    for kind, path, source, target, source_port, target_port, both in links:
        end = '' if kind == 'relation' else ' marker-end="url(#hub-arrow)"'
        start = ' marker-start="url(#hub-arrow)"' if both else ''
        edges.append(f'<path class="hub-edge {kind}" d="{path}" data-from="{source}" data-to="{target}" data-from-port="{source_port}" data-to-port="{target_port}"{start}{end}/>')
    svg = '<svg class="hub-links" viewBox="0 0 960 720" aria-hidden="true"><defs><marker id="hub-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 1 1 L 9 5 L 1 9"/></marker></defs>' + ''.join(edges) + '</svg>'
    title = t('flow.exchange_balance') if identifier in {'bybit', 'whitebit'} else t('flow.hub.balance')
    hub = f'<div class="balance-hub" id="flow-balance"><span>{escape(row["name"])}</span><strong id="flow-balance-title">{escape(title)}</strong><span>{escape(" · ".join(card["currencies"]))}</span><small>{escape(t("flow.hub.shared" if identifier in {"bybit", "whitebit"} else "flow.hub.currencies"))}</small></div>'
    legend = ''.join(f'<span class="hub-key {kind}">{escape(t("flow.hub.edge_" + kind))}</span>' for kind in ('money', 'conditional', 'relation'))
    return f'<p class="hub-scroll-hint">{escape(t("flow.hub.scroll"))} ↔</p><div class="balance-map-scroll" role="region" aria-labelledby="flow-balance-title" tabindex="0" data-route-expand="{escape(t("flow.hub.route_expand"), quote=True)}" data-route-collapse="{escape(t("flow.hub.route_collapse"), quote=True)}" data-expand="{escape(t("flow.hub.expand"), quote=True)}" data-collapse="{escape(t("flow.hub.collapse"), quote=True)}"><div class="balance-map">{svg}{hub}{"".join(nodes)}</div></div>{"".join(tooltips)}<div class="hub-toolbar" hidden><button type="button" class="hub-home">{escape(t("flow.hub.home"))}</button><button type="button" class="hub-fit">{escape(t("flow.hub.fit"))}</button><span class="hub-zoom"><button type="button" class="hub-zoom-out" aria-label="{escape(t("flow.hub.zoom_out"), quote=True)}">−</button><button type="button" class="hub-reset" title="{escape(t("flow.hub.actual_size"), quote=True)}">100%</button><button type="button" class="hub-zoom-in" aria-label="{escape(t("flow.hub.zoom_in"), quote=True)}">+</button></span><span class="hub-live" role="status"></span></div><div class="hub-legend">{legend}</div>'


def money_flow(identifier, datasets, t):
    processes = card_processes(identifier, datasets, t)
    checked_on = date.fromisoformat(datasets['scoring']['checked_on']).strftime('%d.%m.%Y')
    legend = ''.join(f'<span class="flow-status {status}">{escape(t("flow.status." + status))}</span>' for status in ('test', 'terms', 'app', 'pending', 'model'))
    overview = balance_map(identifier, datasets, processes, t)
    groups = []
    for key, paths in processes:
        diagrams = []
        for route in paths:
            steps = []
            for step in route['steps']:
                status = step['status']
                steps.append(f'<li class="flow-node"><span class="flow-status {status}">{escape(t("flow.status." + status))}</span><h4>{escape(step["title"])}</h4><p>{escape(step["detail"])}</p></li>')
            diagrams.append(f'<figure class="flow-route"><figcaption><span>{escape(route["title"])}</span><a href="{escape(route["source"], quote=True)}">{escape(t("flow.sources"))} ↗</a></figcaption><ol class="flow-steps" style="--steps:{len(steps)}">{"".join(steps)}</ol></figure>')
        branching = ' branched' if len(paths) > 1 else ''
        groups.append(f'<details class="process-flow"><summary>{escape(t("flow." + key))}<span>{escape(t("flow.hub.routes", value0=len(paths)))}</span></summary><div class="flow-routes{branching}" id="flow-{key}">{"".join(diagrams)}</div></details>')
    return f'<section class="section" id="cycle"><h2>{escape(t("pages.cycle"))}</h2><p class="muted">{escape(t("flow.intro"))}</p><p class="muted">{escape(t("flow.scope", value0=checked_on))}</p>{overview}<h3 class="flow-details-heading">{escape(t("flow.hub.details"))}</h3><div class="flow-legend">{legend}</div><div class="process-map">{"".join(groups)}</div></section>'
