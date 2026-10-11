// Prove sorting reuses card nodes, preserving expanded details and evidence buttons.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
for (const edition of ['index.html', 'en/index.html']) {
const report = fs.readFileSync(path.join(root, edition), 'utf8');
const configText = report.match(/<script type="application\/json" id="card-sorting">(.*?)<\/script>/s)[1];
const config = JSON.parse(configText);
const cards = new Map(config.modes.actual.order.map(id => {
  const fields = new Map(['.card-index', '.sort-label', '.sort-value', '.sort-note', '.sort-result'].map(key => [key, {textContent: ''}]));
  return [id, {id, details: {open: true}, querySelector: key => fields.get(key)}];
}));
const grid = {
  children: Array.from(cards.values()),
  appendChild(card) {
    this.children.splice(this.children.indexOf(card), 1);
    this.children.push(card);
  },
};
const events = new Map();
const select = {value: 'actual', addEventListener: (name, listener) => events.set(name, listener)};
const controls = {hidden: true};
const description = {textContent: ''};
const elements = new Map([
  ['card-sorting', {textContent: configText}], ['card-sort', select],
  ['card-grid', grid], ['sort-description', description], ['sort-controls', controls],
]);
vm.runInNewContext(fs.readFileSync(path.join(root, 'assets/card-sort.js'), 'utf8'), {
  document: {getElementById: id => elements.get(id)},
});
assert.equal(controls.hidden, false);
assert.deepEqual(grid.children.map(card => card.id), config.modes.actual.order);
for (const mode of ['gross', 'potential', 'actual', 'potential', 'actual']) {
  select.value = mode;
  events.get('change')();
  const spec = config.modes[mode];
  assert.deepEqual(grid.children.map(card => card.id), spec.order);
  assert.equal(description.textContent, spec.description);
  for (const card of grid.children) {
    assert.equal(card, cards.get(card.id));
    assert.equal(card.details.open, true);
    assert.equal(card.querySelector('.card-index').textContent, spec.items[card.id].rank);
    assert.equal(card.querySelector('.sort-label').textContent, spec.metric);
    assert.equal(card.querySelector('.sort-value').textContent, spec.items[card.id].display);
    assert.equal(card.querySelector('.sort-note').textContent, spec.items[card.id].note);
    assert.equal(card.querySelector('.sort-result').hidden, mode !== 'potential');
  }
}
select.value = 'unknown';
events.get('change')();
assert.deepEqual(grid.children.map(card => card.id), config.modes.actual.order);
}
console.log('PASS: both languages, all three UI modes; ranks and monetary labels; unchanged card identity and expanded details.');
