(() => {
  if (!window.researchAnalyticsEnabled) return;
  const main = document.querySelector('main[data-page-type]');
  const context = {page_language: document.documentElement.lang, page_type: main.dataset.pageType};
  if (main.dataset.cardId) context.card_id = main.dataset.cardId;
  const initiallyOpen = new WeakSet(document.querySelectorAll('details[open]'));
  const processes = ['funding', 'payment', 'cashback', 'earning', 'withdrawal', 'level', 'referral'];

  function track(name, parameters = {}) {
    if (typeof window.gtag === 'function') window.gtag('event', name, {...context, ...parameters});
  }
  function cardOf(element) {
    return element.closest('.card')?.id || context.card_id;
  }
  function evidenceParameters(popover, view) {
    return {
      card_id: popover.id === 'evidence-prime' ? 'solid' : popover.id.slice('evidence-'.length),
      evidence_type: popover.id === 'evidence-prime' ? 'prime_terms' : 'transactions',
      evidence_view: view,
    };
  }
  function placement(link) {
    if (link.matches('.card-art-link')) return 'image';
    if (link.matches('.card-details-link')) return 'details_button';
    if (link.matches('.score-badge')) return 'score';
    if (link.closest('.recommendations')) return 'recommendation';
    if (link.closest('.score-matrix')) return 'matrix';
    if (link.closest('.purchase-chart')) return 'purchase_chart';
    if (link.closest('h3')) return 'title';
    if (link.closest('footer')) return 'footer';
    if (link.closest('nav')) return 'navigation';
    return 'content';
  }

  document.getElementById('card-sort')?.addEventListener('change', event => {
    if (['score', 'gross', 'potential', 'actual'].includes(event.target.value)) {
      track('sort_change', {sort_mode: event.target.value});
    }
  });
  document.addEventListener('toggle', event => {
    const target = event.target;
    if (initiallyOpen.delete(target)) return;
    if (target.matches('details.calculation') && target.open) {
      const section = target.classList.contains('cashback-tiers') ? 'cashback'
        : target.classList.contains('earning') ? 'earning'
        : target.classList.contains('funding-summary') ? 'funding'
        : target.classList.contains('losses') ? 'losses' : 'purchase';
      track('detail_open', {card_id: cardOf(target), section});
    } else if (target.matches('details[data-faq-id]') && target.open) {
      track('faq_open', {faq_id: target.dataset.faqId});
    } else if (target.matches('details[id^="criterion-"]') && target.open) {
      track('criterion_open', {criterion: target.id.slice('criterion-'.length)});
    } else if (event.newState === 'open') {
      if (target.matches('.evidence-popover')) track('evidence_open', evidenceParameters(target, 'gallery'));
      else if (target.matches('.score-input-popover')) track('criterion_open', {criterion: target.id.slice('score-input-'.length)});
      else if (target.matches('.hub-tooltip')) track('flow_interaction', {
        interaction_action: 'info', flow_process: target.id.slice('hub-note-'.length),
      });
    }
  }, true);

  document.addEventListener('click', event => {
    const toggle = event.target.closest('.hub-process-toggle, .hub-route-toggle');
    if (toggle) {
      const process = toggle.closest('.hub-process')?.dataset.process
        || toggle.closest('.hub-branch')?.id.slice('flow-'.length);
      if (processes.includes(process)) {
        const parameters = {flow_process: process, interaction_action: toggle.getAttribute('aria-expanded') === 'true' ? 'expand' : 'collapse'};
        if (toggle.matches('.hub-route-toggle')) parameters.flow_route = toggle.getAttribute('aria-controls').replace('flow-', '');
        track('flow_interaction', parameters);
      }
      return;
    }
    const control = event.target.closest('.hub-toolbar button');
    if (control) {
      const action = [['hub-home', 'center'], ['hub-fit', 'fit'], ['hub-zoom-in', 'zoom_in'], ['hub-zoom-out', 'zoom_out'], ['hub-reset', 'reset']]
        .find(([name]) => control.classList.contains(name));
      if (action && !control.disabled) track('flow_interaction', {interaction_action: action[1]});
      return;
    }
    const link = event.target.closest('a');
    if (!link) return;
    if (link.matches('.open-card')) {
      track('card_open', {card_id: cardOf(link), is_referral: link.relList.contains('sponsored'), placement: context.page_type});
    } else if (link.matches('.language-switch a') && !link.hasAttribute('aria-current')) {
      track('language_switch', {target_language: link.lang});
    } else if (link.matches('[data-repository-link]')) {
      track('repository_click', {placement: link.closest('footer') ? 'footer' : 'header'});
    } else if (link.matches('.image-file')) {
      track('evidence_open', evidenceParameters(link.closest('.evidence-popover'), 'original'));
    } else {
      const destination = new URL(link.href, window.location.href);
      if (destination.origin !== window.location.origin
          || destination.pathname.replace(/index\.html$/, '') === window.location.pathname.replace(/index\.html$/, '')) return;
      const card = destination.pathname.match(/\/cards\/([a-z_]+)\/(?:index\.html)?$/);
      if (card) track('card_detail_click', {card_id: card[1], placement: placement(link)});
      else if (/\/ranking\/(?:index\.html)?$/.test(destination.pathname)) {
        const parameters = {placement: placement(link)};
        if (destination.hash.startsWith('#score-')) parameters.card_id = destination.hash.slice(7);
        if (destination.hash.startsWith('#criterion-')) parameters.criterion = destination.hash.slice(11);
        track('ranking_open', parameters);
      }
    }
  });

  document.addEventListener('change', event => {
    if (!['cashback-budget', 'cashback-basis'].includes(event.target.id)) return;
    const amount = Number(document.getElementById('cashback-budget').value);
    const basis = document.getElementById('cashback-basis').value;
    if (!Number.isFinite(amount) || amount < 0 || amount > 5000 || !['1', '2'].includes(basis)) return;
    const band = amount === 0 ? 'zero' : amount <= 500 ? '1_500' : amount <= 1000 ? '501_1000'
      : amount <= 2000 ? '1001_2000' : amount <= 3500 ? '2001_3500' : '3501_5000';
    track('chart_change', {chart_basis: basis === '1' ? 'payout' : 'after_fee', budget_band: band});
  });

  // Visibility means exposure, not proof of reading. Count each target once per page.
  let detailViewed = false;
  const targets = new Map();
  const seen = new WeakSet();
  for (const image of document.querySelectorAll('.overview .card .card-art-link')) {
    targets.set(image, ['card_view', {card_id: cardOf(image)}]);
  }
  for (const heading of document.querySelectorAll('main section[id] > h2')) {
    targets.set(heading, ['section_view', {section: heading.parentElement.id}]);
  }
  const observer = typeof IntersectionObserver === 'function' ? new IntersectionObserver(entries => {
    if (document.visibilityState === 'hidden') return;
    for (const entry of entries) {
      if (!entry.isIntersecting || entry.intersectionRatio < 0.5 || seen.has(entry.target)) continue;
      seen.add(entry.target);
      observer.unobserve(entry.target);
      track(...targets.get(entry.target));
    }
  }, {threshold: 0.5}) : null;
  function observeVisible() {
    observer?.disconnect();
    if (document.visibilityState === 'hidden') return;
    if (context.page_type === 'card' && !detailViewed) {
      detailViewed = true;
      track('card_detail_view');
    }
    if (observer) for (const target of targets.keys()) if (!seen.has(target)) observer.observe(target);
  }
  document.addEventListener('visibilitychange', observeVisible);
  observeVisible();
})();
