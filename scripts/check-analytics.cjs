// Exercise event handlers without loading Google or transmitting test events.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const script = fs.readFileSync(path.join(root, 'assets/analytics.js'), 'utf8');

function element(selectors, properties = {}, parents = {}) {
  return {
    matches: selector => selectors.includes(selector),
    closest(selector) { return selectors.includes(selector) ? this : parents[selector] || null; },
    ...properties,
  };
}

for (const [edition, language] of [['index.html', 'uk'], ['en/index.html', 'en']]) {
  const html = fs.readFileSync(path.join(root, edition), 'utf8');
  const cardIds = Array.from(html.matchAll(/<article class="card [^"]+" id="([^"]+)"/g), match => match[1]);
  assert.equal(cardIds.length, 9);
  assert.equal((html.match(/<script src="(?:\.\.\/)?assets\/analytics.js" defer><\/script>/g) || []).length, 1);
  assert.equal((html.match(/data-repository-link/g) || []).length, 2);
  const handlers = new Map();
  const events = [];
  const select = {addEventListener: (type, callback) => handlers.set('sort:' + type, callback)};
  const window = {gtag: (...args) => events.push(JSON.parse(JSON.stringify(args)))};
  vm.runInNewContext(script, {
    window,
    document: {
      documentElement: {lang: language},
      getElementById: id => { assert.equal(id, 'card-sort'); return select; },
      addEventListener: (type, callback, capture) => {
        if (type === 'toggle') assert.equal(capture, true);
        assert.equal(handlers.has(type), false);
        handlers.set(type, callback);
      },
    },
  });
  assert.equal(events.length, 0, 'Initial setup must not count as a user action');
  function expect(name, parameters, action) {
    const count = events.length;
    action();
    assert.equal(events.length, count + 1, 'One event per action');
    assert.deepEqual(events.at(-1), ['event', name, {page_language: language, ...parameters}]);
  }
  function silent(action) {
    const count = events.length;
    action();
    assert.equal(events.length, count);
  }
  const click = target => handlers.get('click')({target});
  const toggle = (target, newState) => handlers.get('toggle')({target, newState});
  for (const mode of ['gross', 'potential', 'actual']) {
    expect('sort_change', {sort_mode: mode}, () => handlers.get('sort:change')({target: {value: mode}}));
  }
  silent(() => handlers.get('sort:change')({target: {value: 'unexpected'}}));
  for (const id of cardIds) {
    const card = {id};
    for (const [className, section] of [['', 'purchase'], ['cashback-tiers', 'cashback'], ['earning', 'earning'], ['funding-summary', 'funding'], ['losses', 'losses']]) {
      assert.ok(html.includes(`class="calculation${className ? ' ' + className : ''}"`));
      const details = element(['details.calculation'], {open: true, classList: {contains: name => name === className}}, {'.card': card});
      expect('detail_open', {card_id: id, section}, () => toggle(details, 'open'));
      details.open = false;
      silent(() => toggle(details, 'closed'));
    }
    const popover = element(['.evidence-popover'], {id: 'evidence-' + id});
    expect('evidence_open', {card_id: id, evidence_type: 'transactions', evidence_view: 'gallery'}, () => toggle(popover, 'open'));
    silent(() => toggle(popover, 'closed'));
    const imageLink = element(['a', '.image-file'], {}, {'.evidence-popover': popover});
    expect('evidence_open', {card_id: id, evidence_type: 'transactions', evidence_view: 'original'}, () => click(imageLink));
    for (const sponsored of id === 'coca' ? [false] : [false, true]) {
      const cardLink = element(['a', '.open-card'], {relList: {contains: value => value === 'sponsored' && sponsored}}, {'.card': card});
      const nestedIcon = element([], {}, {a: cardLink});
      expect('card_open', {card_id: id, is_referral: sponsored}, () => click(nestedIcon));
    }
  }
  const prime = element(['.evidence-popover'], {id: 'evidence-prime'});
  expect('evidence_open', {card_id: 'solid', evidence_type: 'prime_terms', evidence_view: 'gallery'}, () => toggle(prime, 'open'));
  const langLink = element(['a', '.language-switch a'], {lang: language === 'uk' ? 'en' : 'uk', hasAttribute: () => false});
  expect('language_switch', {target_language: langLink.lang}, () => click(langLink));
  langLink.hasAttribute = () => true;
  silent(() => click(langLink));
  for (const placement of ['header', 'footer']) {
    const link = element(['a', '[data-repository-link]'], {}, {footer: placement === 'footer' ? {} : null});
    expect('repository_click', {placement}, () => click(link));
  }
  silent(() => click(element(['a'])));
  silent(() => click(element([])));
  silent(() => toggle(element(['details']), 'open'));
  // A blocked or absent Google tag must not break any interaction handler.
  delete window.gtag;
  silent(() => handlers.get('sort:change')({target: {value: 'gross'}}));
  silent(() => click(element(['a', '[data-repository-link]'])));
}
console.log('PASS: six analytics events in both languages; all card sections; gallery/PNG and Prime; nested-link clicks; no setup/close duplicates; no transmission; absent Google tag is harmless.');
