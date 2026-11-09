const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
for (const language of ['uk', 'en']) {
  const page = fs.readFileSync(path.join(root, language === 'en' ? 'en' : '', 'ranking/index.html'), 'utf8');
  const data = page.match(/<script type="application\/json" id="cashback-chart-data">(.*?)<\/script>/s)[1];
  const handlers = new Map();
  const budget = {value: '1000', addEventListener: (name, callback) => handlers.set('budget:' + name, callback)};
  const basis = {value: '1', addEventListener: (name, callback) => handlers.set('basis:' + name, callback)};
  const outputs = new Map();
  const label = {};
  const guide = {setAttribute: (key, value) => outputs.set(key, value)};
  const nodes = new Map([
    ['cashback-chart-data', {textContent: data}], ['cashback-budget', budget],
    ['cashback-basis', basis], ['budget-label', label], ['budget-guide', guide],
  ]);
  vm.runInNewContext(fs.readFileSync(path.join(root, 'assets/cashback-chart.js'), 'utf8'), {
    Intl,
    document: {
      documentElement: {lang: language}, getElementById: id => nodes.get(id),
      querySelector: selector => ({
        setAttribute: (key, value) => outputs.set(selector + key, value),
        set textContent(value) { outputs.set(selector, value); },
      }),
    },
  });
  const format = new Intl.NumberFormat(language, {style: 'currency', currency: 'USD', maximumFractionDigits: 2});
  assert.equal(outputs.get('[data-budget-result="0"]'), format.format(30));
  assert.equal(outputs.get('[data-budget-result="1"]'), format.format(40));
  assert.equal(outputs.get('[data-budget-result="3"]'), format.format(25));
  basis.value = '2';
  handlers.get('basis:change')();
  assert.equal(outputs.get('[data-budget-result="1"]'), format.format(40 - 199 / 12));
  budget.value = '0';
  handlers.get('budget:input')();
  assert.equal(outputs.get('[data-budget-result="1"]'), format.format(-199 / 12));
  assert.equal(outputs.get('[data-budget-result="0"]'), format.format(0));
  budget.value = '5000';
  handlers.get('budget:input')();
  assert.equal(outputs.get('[data-budget-result="0"]'), format.format(50));
  const previous = label.value;
  budget.value = 'NaN';
  handlers.get('budget:input')();
  assert.equal(label.value, previous);
}
console.log('PASS: cashback charts in both languages, tier limits, fee switch, zero spending and invalid input.');

// Exercise diagram zoom through the same toolbar handlers used on card pages.
{
  const controls = new Map();
  const listeners = new Map();
  for (const name of ['home', 'fit', 'reset', 'zoom-out', 'zoom-in', 'live']) {
    controls.set('.hub-' + name, {
      textContent: name === 'reset' ? '100%' : '', disabled: false,
      addEventListener: (event, callback) => listeners.set(name + ':' + event, callback),
    });
  }
  const classList = {add() {}};
  const svg = {append() {}, setAttribute() {}, querySelectorAll: () => []};
  const map = {
    style: {}, classList, addEventListener() {}, querySelectorAll: () => [],
    getBoundingClientRect: () => ({left: 0, top: 0}),
    querySelector: selector => selector === '.hub-links' ? svg : balance,
  };
  const balance = {
    style: {}, offsetHeight: 80,
    getBoundingClientRect: () => {
      const scale = Number(map.style.zoom || 1);
      return {left: (parseFloat(balance.style.left || 390) - 100) * scale,
        top: (parseFloat(balance.style.top || 168) - 40) * scale,
        width: 200 * scale, height: 80 * scale};
    },
  };
  const toolbar = {querySelector: selector => controls.get(selector)};
  const scroller = {
    classList, clientWidth: 520, clientHeight: 350, scrollLeft: 0, scrollTop: 0,
    querySelector: () => map, before() {},
    scrollTo({left, top}) {
      assert.ok(Number.isFinite(left) && Number.isFinite(top));
      this.scrollLeft = left;
      this.scrollTop = top;
    },
  };
  const elements = new Map([
    ['.balance-map-scroll', scroller], ['.process-map', {}],
    ['.hub-toolbar', toolbar], ['.flow-details-heading', {}],
  ]);
  vm.runInNewContext(fs.readFileSync(path.join(root, 'assets/card-flow.js'), 'utf8'), {
    document: {querySelector: selector => elements.get(selector), createElementNS: () => ({replaceChildren() {}})},
    window: {addEventListener() {}}, location: {hash: ''},
    ResizeObserver: class {observe() {}}, getComputedStyle: () => ({maxHeight: '780px'}),
  });
  const click = name => listeners.get(name + ':click')();
  const percentage = () => controls.get('.hub-reset').textContent;
  click('zoom-out');
  assert.equal(percentage(), '90%');
  click('zoom-in');
  assert.equal(percentage(), '100%');
  for (let index = 0; index < 25; index++) click('zoom-in');
  assert.equal(percentage(), '200%');
  assert.equal(controls.get('.hub-zoom-in').disabled, true);
  for (let index = 0; index < 25; index++) click('zoom-out');
  assert.equal(percentage(), '10%');
  assert.equal(controls.get('.hub-zoom-out').disabled, true);
  click('reset');
  assert.equal(percentage(), '100%');
  assert.equal(controls.get('.hub-zoom-in').disabled, false);
  assert.equal(controls.get('.hub-zoom-out').disabled, false);
  click('fit');
  assert.equal(percentage(), '65%');
  click('zoom-in');
  assert.equal(percentage(), '75%');
  scroller.clientWidth = 60;
  click('fit');
  assert.equal(percentage(), '6%');
  assert.equal(controls.get('.hub-zoom-out').disabled, true);
  click('zoom-in');
  assert.equal(percentage(), '16%');
}
console.log('PASS: diagram zoom steps, live percentage, bounds, reset and zoom after fitting.');
