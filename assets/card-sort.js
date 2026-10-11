(() => {
  const config = JSON.parse(document.getElementById('card-sorting').textContent);
  const select = document.getElementById('card-sort');
  const grid = document.getElementById('card-grid');
  const description = document.getElementById('sort-description');
  const cards = new Map(Array.from(grid.children, card => [card.id, card]));

  function apply(mode) {
    const spec = config.modes[mode];
    if (!spec) return;
    for (const id of spec.order) {
      const card = cards.get(id);
      const item = spec.items[id];
      card.querySelector('.card-index').textContent = item.rank;
      card.querySelector('.sort-label').textContent = spec.metric;
      card.querySelector('.sort-value').textContent = item.display;
      card.querySelector('.sort-note').textContent = item.note;
      card.querySelector('.sort-result').hidden = mode !== 'potential';
      grid.appendChild(card);
    }
    description.textContent = spec.description;
  }

  select.value = config.default;
  apply(select.value);
  select.addEventListener('change', () => apply(select.value));
  document.getElementById('sort-controls').hidden = false;
})();
