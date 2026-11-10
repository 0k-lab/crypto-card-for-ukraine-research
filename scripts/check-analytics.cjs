// Exercise real event handlers and the tag bootstrap without Google or network access.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');
const root = path.resolve(__dirname, '..');
const script = fs.readFileSync(path.join(root, 'assets/analytics.js'), 'utf8');
const version = crypto.createHash('sha256').update(script).digest('hex').slice(0, 12);
const base = 'https://0k-lab.github.io/crypto-card-for-ukraine-research/';
const ids = [...fs.readFileSync(path.join(root, 'index.html'), 'utf8').matchAll(/<article class="card [^"]+" id="([^"]+)"/g)].map(match => match[1]);
assert.equal(ids.length, 9);

function element(selectors = [], properties = {}, parents = {}) {
  return {
    matches: selector => selectors.includes(selector),
    closest(selector) {
      return selector.split(',').some(part => this.matches(part.trim())) ? this : parents[selector] || null;
    },
    classList: {contains: () => false},
    ...properties,
  };
}
function setup(language = 'uk', pageType = 'home', cardId = '', options = {}) {
  const handlers = {}, events = [], observed = new Set();
  const open = element(['details.calculation'], {open: true}, {'.card': {id: 'okx'}});
  const image = element([], {}, {'.card': {id: 'solid'}});
  const heading = element([], {parentElement: {id: 'cycle'}});
  const budget = {value: '1000'}, basis = {value: '1'};
  const location = new URL(base + (language === 'en' ? 'en/' : '') + (pageType === 'card' ? `cards/${cardId}/` : pageType === 'ranking' ? 'ranking/' : ''));
  const window = {researchAnalyticsEnabled: options.enabled !== false, location, gtag: (...args) => events.push(JSON.parse(JSON.stringify(args)))};
  const document = {
    visibilityState: options.hidden ? 'hidden' : 'visible',
    documentElement: {lang: language},
    querySelector: selector => {
      assert.equal(selector, 'main[data-page-type]');
      return {dataset: {pageType, cardId}};
    },
    querySelectorAll: selector => {
      if (selector === 'details[open]') return [open];
      if (selector === '.overview .card .card-art-link') return pageType === 'home' ? [image] : [];
      if (selector === 'main section[id] > h2') return [heading];
      throw Error('Unexpected selector: ' + selector);
    },
    getElementById: id => id === 'card-sort' ? pageType === 'home' ? {addEventListener: (type, fn) => { handlers.sort = fn; }} : null
      : id === 'cashback-budget' ? budget : id === 'cashback-basis' ? basis : null,
    addEventListener(type, fn, capture) {
      assert.equal(handlers[type], undefined);
      if (type === 'toggle') assert.equal(capture, true);
      handlers[type] = fn;
    },
  };
  let intersection;
  class Observer {
    constructor(fn, settings) { intersection = fn; assert.equal(settings.threshold, 0.5); }
    observe(target) { observed.add(target); }
    unobserve(target) { observed.delete(target); }
    disconnect() { observed.clear(); }
  }
  vm.runInNewContext(script, {window, document, URL, IntersectionObserver: options.noObserver ? undefined : Observer});
  const context = {page_language: language, page_type: pageType, ...(cardId ? {card_id: cardId} : {})};
  function expect(name, parameters, action) {
    const count = events.length; action();
    assert.equal(events.length, count + 1, 'Exactly one event: ' + name);
    assert.deepEqual(events.at(-1), ['event', name, {...context, ...parameters}]);
  }
  function silent(action) { const count = events.length; action(); assert.equal(events.length, count); }
  return {handlers, events, window, document, budget, basis, open, image, heading, observed, expect, silent,
    click: target => handlers.click({target}), toggle: (target, newState) => handlers.toggle({target, newState}),
    intersect: (target, ratio) => intersection([{target, intersectionRatio: ratio, isIntersecting: ratio > 0}])};
}

for (const language of ['uk', 'en']) {
  const s = setup(language);
  const {expect, silent, click, toggle} = s;
  assert.equal(s.events.length, 0, 'Setup is not a user interaction');
  silent(() => toggle(s.open, 'open'));
  s.open.open = false; silent(() => toggle(s.open, 'closed'));
  s.open.open = true; expect('detail_open', {card_id: 'okx', section: 'purchase'}, () => toggle(s.open, 'open'));
  for (const mode of ['score', 'gross', 'potential', 'actual']) expect('sort_change', {sort_mode: mode}, () => s.handlers.sort({target: {value: mode}}));
  silent(() => s.handlers.sort({target: {value: 'unexpected'}}));
  for (const id of ids) {
    const card = {id};
    for (const [className, section] of [['', 'purchase'], ['cashback-tiers', 'cashback'], ['earning', 'earning'], ['funding-summary', 'funding'], ['losses', 'losses']]) {
      const target = element(['details.calculation'], {open: true, classList: {contains: value => value === className}}, {'.card': card});
      expect('detail_open', {card_id: id, section}, () => toggle(target, 'open'));
      target.open = false; silent(() => toggle(target, 'closed'));
    }
    const popover = element(['.evidence-popover'], {id: 'evidence-' + id});
    expect('evidence_open', {card_id: id, evidence_type: 'transactions', evidence_view: 'gallery'}, () => toggle(popover, 'open'));
    silent(() => toggle(popover, 'closed'));
    expect('evidence_open', {card_id: id, evidence_type: 'transactions', evidence_view: 'original'}, () => click(element(['a', '.image-file'], {}, {'.evidence-popover': popover})));
    for (const isReferral of [false, true]) {
      const link = element(['a', '.open-card'], {relList: {contains: () => isReferral}}, {'.card': card});
      expect('card_open', {card_id: id, is_referral: isReferral, placement: 'home'}, () => click(element([], {}, {a: link})));
    }
    for (const [selector, placement] of [['.card-art-link', 'image'], ['.card-details-link', 'details_button']]) {
      const link = element(['a', selector], {href: base + `cards/${id}/`});
      expect('card_detail_click', {card_id: id, placement}, () => click(link));
    }
  }
  const faq = element(['details[data-faq-id]'], {open: true, dataset: {faqId: 'q2'}});
  expect('faq_open', {faq_id: 'q2'}, () => toggle(faq, 'open'));
  faq.open = false; silent(() => toggle(faq, 'closed'));
  expect('criterion_open', {criterion: 'payment'}, () => toggle(element(['.score-input-popover'], {id: 'score-input-payment'}), 'open'));
  expect('criterion_open', {criterion: 'networks'}, () => toggle(element(['details[id^="criterion-"]'], {id: 'criterion-networks', open: true}), 'open'));
  const prime = element(['.evidence-popover'], {id: 'evidence-prime'});
  expect('evidence_open', {card_id: 'solid', evidence_type: 'prime_terms', evidence_view: 'gallery'}, () => toggle(prime, 'open'));
  const lang = element(['a', '.language-switch a'], {lang: language === 'uk' ? 'en' : 'uk', hasAttribute: () => false});
  expect('language_switch', {target_language: lang.lang}, () => click(lang));
  for (const placement of ['header', 'footer']) expect('repository_click', {placement}, () => click(element(['a', '[data-repository-link]'], {}, {footer: placement === 'footer' ? {} : null})));
  expect('ranking_open', {placement: 'score', card_id: 'solid'}, () => click(element(['a', '.score-badge'], {href: base + 'ranking/#score-solid'})));
  const process = element(['.hub-process-toggle'], {getAttribute: () => 'true'}, {'.hub-process': {dataset: {process: 'funding'}}});
  expect('flow_interaction', {flow_process: 'funding', interaction_action: 'expand'}, () => click(process));
  process.getAttribute = () => 'false';
  expect('flow_interaction', {flow_process: 'funding', interaction_action: 'collapse'}, () => click(process));
  const route = element(['.hub-route-toggle'], {getAttribute: name => name === 'aria-expanded' ? 'true' : 'flow-funding-route-0'}, {'.hub-branch': {id: 'flow-funding'}});
  expect('flow_interaction', {flow_process: 'funding', interaction_action: 'expand', flow_route: 'funding-route-0'}, () => click(route));
  expect('flow_interaction', {interaction_action: 'zoom_in'}, () => click(element(['.hub-toolbar button'], {classList: {contains: name => name === 'hub-zoom-in'}})));
  silent(() => click(element(['.hub-toolbar button'], {disabled: true, classList: {contains: name => name === 'hub-zoom-in'}})));
  expect('flow_interaction', {interaction_action: 'info', flow_process: 'funding'}, () => toggle(element(['.hub-tooltip'], {id: 'hub-note-funding'}), 'open'));
  expect('chart_change', {chart_basis: 'payout', budget_band: '501_1000'}, () => s.handlers.change({target: {id: 'cashback-budget'}}));
  s.basis.value = '2';
  expect('chart_change', {chart_basis: 'after_fee', budget_band: '501_1000'}, () => s.handlers.change({target: {id: 'cashback-basis'}}));
  s.budget.value = 'NaN'; silent(() => s.handlers.change({target: {id: 'cashback-budget'}}));
  silent(() => s.intersect(s.image, 0.49));
  expect('card_view', {card_id: 'solid'}, () => s.intersect(s.image, 0.5));
  silent(() => s.intersect(s.image, 1));
  expect('section_view', {section: 'cycle'}, () => s.intersect(s.heading, 1));
  silent(() => s.intersect(s.heading, 1));
  silent(() => click(element(['a'], {href: 'https://example.com/cards/solid/'})));
  silent(() => click(element(['a'], {href: s.window.location.href + '#faq'})));
  silent(() => click(element([])));
  delete s.window.gtag;
  silent(() => s.handlers.sort({target: {value: 'score'}}));
  silent(() => click(element(['a', '[data-repository-link]'])));
  const allowed = new Set(['page_language', 'page_type', 'card_id', 'section', 'placement', 'is_referral', 'sort_mode', 'evidence_type', 'evidence_view', 'target_language', 'criterion', 'faq_id', 'flow_process', 'flow_route', 'interaction_action', 'chart_basis', 'budget_band']);
  for (const [, , parameters] of s.events) {
    assert.ok(Object.keys(parameters).every(key => allowed.has(key)));
    assert.ok(!JSON.stringify(parameters).includes('https://'), 'Custom parameters contain IDs, not full URLs or text');
  }
}
for (const language of ['uk', 'en']) for (const id of ids) {
  const s = setup(language, 'card', id);
  assert.deepEqual(s.events[0], ['event', 'card_detail_view', {page_language: language, page_type: 'card', card_id: id}]);
  s.silent(() => s.handlers.visibilitychange());
  s.silent(() => s.click(element(['a'], {href: s.window.location.href + '#cycle'})));
}
const hidden = setup('uk', 'card', 'solid', {hidden: true});
assert.equal(hidden.events.length, 0);
hidden.document.visibilityState = 'visible';
hidden.expect('card_detail_view', {}, () => hidden.handlers.visibilitychange());
hidden.document.visibilityState = 'hidden'; hidden.handlers.visibilitychange();
hidden.silent(() => hidden.intersect(hidden.heading, 1));
assert.equal(hidden.observed.size, 0);
const disabled = setup('uk', 'home', '', {enabled: false});
assert.equal(disabled.events.length, 0); assert.equal(Object.keys(disabled.handlers).length, 0);
setup('uk', 'ranking', '', {noObserver: true});

// Audit all generated editions and execute the actual bootstrap under public and local URLs.
for (const language of ['uk', 'en']) for (const route of ['', 'ranking/', ...ids.map(id => `cards/${id}/`)]) {
  const relative = (language === 'en' ? 'en/' : '') + route + 'index.html';
  const html = fs.readFileSync(path.join(root, relative), 'utf8');
  const type = route.startsWith('cards/') ? 'card' : route ? 'ranking' : 'home';
  const cardId = type === 'card' ? route.split('/')[1] : '';
  assert.ok(html.includes(`data-page-type="${type}" data-card-id="${cardId}"`));
  assert.equal((html.match(new RegExp(`assets/analytics\\.js\\?v=${version}`, 'g')) || []).length, 1);
  if (type === 'card') for (let n = 1; n <= 4; n++) assert.ok(html.includes(`data-faq-id="q${n}"`));
  const bootstrap = html.match(/<script id="google-analytics">([\s\S]*?)<\/script>/)[1];
  assert.ok(!/<script[^>]+src=["']https:\/\/www\.googletagmanager\.com/.test(html), 'No unconditional Google tag on previews');
  const canonical = html.match(/<link rel="canonical" href="([^"]+)"/)?.[1];
  const disabledWindow = {};
  vm.runInNewContext(bootstrap, {window: disabledWindow, document: {querySelector: () => null}});
  assert.equal(disabledWindow.researchAnalyticsEnabled, false, 'No canonical means no analytics');
  assert.equal(disabledWindow.gtag, undefined);
  if (!canonical) continue;
  for (const [url, enabled] of [[canonical, true], [canonical + 'index.html?qa=1', true], [canonical.replace('https:', 'http:'), false], [canonical.replace('https://0k-lab.github.io', 'http://127.0.0.1:8765'), false], [canonical.replace('0k-lab.github.io', 'localhost'), false], [canonical.replace('/crypto-card-for-ukraine-research/', '/other-project/'), false]]) {
    const loaded = [], window = {};
    vm.runInNewContext(bootstrap, {window, location: new URL(url), URL, Date, document: {
      querySelector: () => ({href: canonical}), createElement: () => ({}), head: {append: element => loaded.push(element)},
    }});
    assert.equal(window.researchAnalyticsEnabled, enabled, url);
    assert.equal(loaded.length, enabled ? 1 : 0);
    if (enabled) {
      assert.equal(loaded[0].src, 'https://www.googletagmanager.com/gtag/js?id=G-NWFJQ8WLJ7');
      assert.equal(window.dataLayer.length, 2, 'Exactly one config; no duplicate page_view');
    } else assert.equal(window.gtag, undefined, 'No tag or queue on previews');
  }
}
console.log('PASS: behavioral funnel in UA/EN; all four sort modes; navigation, FAQ, criteria, flows and chart controls; one-time visibility without background counts; all 22 page contexts; local-preview suppression; cache version; no transmitted test events.');
