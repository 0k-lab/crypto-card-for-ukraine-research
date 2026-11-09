(() => {
  const node = document.getElementById('cashback-chart-data');
  if (!node) return;
  const config = JSON.parse(node.textContent);
  const budget = document.getElementById('cashback-budget');
  const basis = document.getElementById('cashback-basis');
  const format = new Intl.NumberFormat(document.documentElement.lang, {
    style: 'currency', currency: 'USD', maximumFractionDigits: 2,
  });
  const y = value => config.bottom - (value + 20) / 130 * (config.bottom - config.top);
  const x = value => config.left + value / 5000 * (config.right - config.left);

  function update() {
    const column = Number(basis.value);
    const amount = Number(budget.value);
    if (![1, 2].includes(column) || !Number.isFinite(amount) || amount < 0 || amount > 5000 || amount % 50) return;
    document.getElementById('budget-label').value = format.format(amount);
    const guide = document.getElementById('budget-guide');
    guide.setAttribute('x1', x(amount));
    guide.setAttribute('x2', x(amount));
    config.programs.forEach((program, index) => {
      const path = document.querySelector(`[data-program="${index}"]`);
      path.setAttribute('points', program.samples.map(sample => `${x(sample[0])},${y(sample[column])}`).join(' '));
      document.querySelector(`[data-budget-result="${index}"]`).textContent = format.format(program.samples[amount / 50][column]);
    });
  }

  budget.addEventListener('input', update);
  basis.addEventListener('change', update);
  update();
})();
