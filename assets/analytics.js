(() => {
  function track(name, parameters) {
    if (typeof window.gtag === 'function') {
      window.gtag('event', name, {page_language: document.documentElement.lang, ...parameters});
    }
  }

  function evidenceParameters(popover, view) {
    return {
      card_id: popover.id === 'evidence-prime' ? 'solid' : popover.id.slice('evidence-'.length),
      evidence_type: popover.id === 'evidence-prime' ? 'prime_terms' : 'transactions',
      evidence_view: view,
    };
  }

  document.getElementById('card-sort').addEventListener('change', event => {
    if (['gross', 'potential', 'actual'].includes(event.target.value)) {
      track('sort_change', {sort_mode: event.target.value});
    }
  });

  // Native toggle events cover mouse, keyboard and programmatic opening alike.
  document.addEventListener('toggle', event => {
    const target = event.target;
    if (target.matches('details.calculation') && target.open) {
      const card = target.closest('.card');
      const section = target.classList.contains('cashback-tiers') ? 'cashback'
        : target.classList.contains('earning') ? 'earning'
        : target.classList.contains('funding-summary') ? 'funding'
        : target.classList.contains('losses') ? 'losses' : 'purchase';
      track('detail_open', {card_id: card.id, section});
    } else if (target.matches('.evidence-popover') && event.newState === 'open') {
      track('evidence_open', evidenceParameters(target, 'gallery'));
    }
  }, true);

  document.addEventListener('click', event => {
    const link = event.target.closest('a');
    if (!link) return;
    if (link.matches('.open-card')) {
      track('card_open', {
        card_id: link.closest('.card').id,
        is_referral: link.relList.contains('sponsored'),
      });
    } else if (link.matches('.language-switch a') && !link.hasAttribute('aria-current')) {
      track('language_switch', {target_language: link.lang});
    } else if (link.matches('[data-repository-link]')) {
      track('repository_click', {placement: link.closest('footer') ? 'footer' : 'header'});
    } else if (link.matches('.image-file')) {
      track('evidence_open', evidenceParameters(link.closest('.evidence-popover'), 'original'));
    }
  });
})();
