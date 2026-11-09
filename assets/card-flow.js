/* Expand existing route nodes inside the spending-balance canvas. */
(() => {
  const scroller = document.querySelector('.balance-map-scroll');
  const fallback = document.querySelector('.process-map');
  if (!scroller || !fallback) return;
  const map = scroller.querySelector('.balance-map');
  const svg = map.querySelector('.hub-links');
  const balance = map.querySelector('.balance-hub');
  const toolbar = document.querySelector('.hub-toolbar');
  const nodes = new Map([['balance', balance]]);
  const positions = {
    earning: [125, 0, 'left'], cashback: [390, 0, 'right'],
    funding: [125, 1, 'left'], payment: [655, 1, 'right'],
    level: [125, 2, 'left'], withdrawal: [390, 2, 'bottom'], referral: [655, 2, 'right'],
  };
  const branches = [];
  let scale = 1;
  for (const root of map.querySelectorAll('.hub-process')) {
    const key = root.dataset.process;
    const toggle = root.querySelector('.hub-process-toggle');
    const element = document.getElementById('flow-' + key);
    const [x, row, side] = positions[key];
    const routes = [];
    for (const figure of element.querySelectorAll('.flow-route')) {
      const steps = figure.querySelector('.flow-steps');
      const caption = figure.querySelector('figcaption');
      const title = caption.querySelector('span');
      const toggle = document.createElement('button');
      toggle.type = 'button';
      toggle.className = 'hub-route-toggle';
      const label = document.createElement('span');
      label.textContent = title.textContent;
      const hint = document.createElement('span');
      hint.className = 'hub-open';
      hint.setAttribute('aria-hidden', 'true');
      hint.textContent = '+';
      toggle.append(label);
      toggle.append(hint);
      title.replaceWith(toggle);
      steps.id = element.id + '-route-' + routes.length;
      steps.classList.add('hub-route-steps');
      steps.hidden = true;
      toggle.setAttribute('aria-expanded', 'false');
      toggle.setAttribute('aria-controls', steps.id);
      routes.push({figure, steps, caption, toggle, hint, width: steps.children.length * 180 + (steps.children.length - 1) * 24});
    }
    element.classList.add('hub-branch', side);
    element.hidden = true;
    map.append(element);
    toggle.setAttribute('role', 'button');
    toggle.setAttribute('aria-controls', element.id);
    toggle.setAttribute('aria-expanded', 'false');
    nodes.set(key, root);
    branches.push({key, root, toggle, element, x, row, side, width: 200, routes});
  }
  fallback.hidden = true;
  document.querySelector('.flow-details-heading').hidden = true;
  scroller.before(toolbar);
  toolbar.hidden = false;
  scroller.classList.add('interactive');
  map.classList.add('interactive');
  let drag = null;
  function stopDragging(event) {
    if (!drag || drag.id !== event.pointerId) return;
    drag = null;
    scroller.classList.remove('dragging');
    if (map.hasPointerCapture(event.pointerId)) map.releasePointerCapture(event.pointerId);
  }
  map.addEventListener('pointerdown', event => {
    if (event.pointerType !== 'mouse' || event.button !== 0 || event.target.closest('a, button, input, select, textarea, [contenteditable], .flow-node, .balance-hub, figcaption')) return;
    drag = {id: event.pointerId, x: event.clientX, y: event.clientY, left: scroller.scrollLeft, top: scroller.scrollTop};
    map.setPointerCapture(event.pointerId);
    scroller.classList.add('dragging');
    event.preventDefault();
  });
  map.addEventListener('pointermove', event => {
    if (!drag || drag.id !== event.pointerId) return;
    if (!(event.buttons & 1)) {
      stopDragging(event);
      return;
    }
    scroller.scrollLeft = drag.left - (event.clientX - drag.x);
    scroller.scrollTop = drag.top - (event.clientY - drag.y);
    event.preventDefault();
  });
  for (const name of ['pointerup', 'pointercancel', 'lostpointercapture']) map.addEventListener(name, stopDragging);
  const detailEdges = document.createElementNS('http://www.w3.org/2000/svg', 'g');
  svg.append(detailEdges);

  function port(element, side) {
    const rect = element.getBoundingClientRect();
    const origin = map.getBoundingClientRect();
    const x = (rect.left - origin.left) / scale;
    const y = (rect.top - origin.top) / scale;
    return {
      left: [x, y + rect.height / scale / 2, -1, 0],
      right: [x + rect.width / scale, y + rect.height / scale / 2, 1, 0],
      top: [x + rect.width / scale / 2, y, 0, -1],
      bottom: [x + rect.width / scale / 2, y + rect.height / scale, 0, 1],
    }[side];
  }

  function connect(path, source, sourceSide, target, targetSide) {
    const [x1, y1, dx1, dy1] = port(source, sourceSide);
    const [x2, y2, dx2, dy2] = port(target, targetSide);
    const bend = Math.max(24, Math.min(110, Math.hypot(x2 - x1, y2 - y1) / 2));
    path.setAttribute('d', `M ${x1} ${y1} C ${x1 + dx1 * bend} ${y1 + dy1 * bend} ${x2 + dx2 * bend} ${y2 + dy2 * bend} ${x2} ${y2}`);
  }

  function addEdge(source, sourceSide, target, targetSide, kind) {
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('class', 'hub-edge ' + kind);
    if (kind !== 'relation') path.setAttribute('marker-end', 'url(#hub-arrow)');
    connect(path, source, sourceSide, target, targetSide);
    detailEdges.append(path);
  }

  function layout() {
    const before = balance.getBoundingClientRect();
    const visible = branches.filter(branch => !branch.element.hidden);
    for (const branch of visible) {
      for (const route of branch.routes) route.figure.style.width = (route.steps.hidden ? 200 : route.width + 228) + 'px';
      branch.width = Math.max(...branch.routes.map(route => route.steps.hidden ? 200 : route.width + 228));
      branch.element.style.width = branch.width + 'px';
    }
    const bottom = visible.find(branch => branch.side === 'bottom');
    const bottomExtra = bottom ? Math.max(0, (bottom.width - 780) / 2 + 24) : 0;
    const left = Math.max(bottomExtra, ...visible.filter(b => b.side === 'left').map(b => b.width + 72));
    const right = Math.max(bottomExtra, ...visible.filter(b => b.side === 'right').map(b => b.width + 72));
    const heights = [112, 112, 112];
    for (const branch of branches) heights[branch.row] = Math.max(heights[branch.row], branch.root.offsetHeight + 32);
    heights[1] = Math.max(heights[1], balance.offsetHeight + 32);
    for (const branch of visible) {
      if (branch.side !== 'bottom') heights[branch.row] = Math.max(heights[branch.row], branch.element.offsetHeight + 32);
    }
    const centres = [heights[0] / 2, heights[0] + heights[1] / 2, heights[0] + heights[1] + heights[2] / 2];
    const mainHeight = heights.reduce((sum, height) => sum + height, 0);
    const width = left + 780 + right;
    const height = mainHeight + (bottom ? bottom.element.offsetHeight + 72 : 0);
    map.style.width = width + 'px';
    map.style.height = height + 'px';
    balance.style.left = left + 390 + 'px';
    balance.style.top = centres[1] + 'px';
    for (const branch of branches) {
      branch.root.style.left = left + branch.x + 'px';
      branch.root.style.top = centres[branch.row] + 'px';
      if (branch.element.hidden) continue;
      const branchX = branch.side === 'left' ? left - branch.width - 48 : branch.side === 'right' ? left + 828 : left + 390 - branch.width / 2;
      const branchY = branch.side === 'bottom' ? mainHeight + 48 : centres[branch.row] - branch.element.offsetHeight / 2;
      branch.element.style.left = branchX + 'px';
      branch.element.style.top = branchY + 'px';
    }
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    for (const path of svg.querySelectorAll('[data-from]')) {
      connect(path, nodes.get(path.dataset.from), path.dataset.fromPort, nodes.get(path.dataset.to), path.dataset.toPort);
    }
    detailEdges.replaceChildren();
    for (const branch of visible) {
      for (const route of branch.routes) {
        if (branch.side === 'left') addEdge(branch.root, 'left', route.caption, 'right', 'relation');
        else addEdge(branch.root, branch.side === 'bottom' ? 'bottom' : 'right', route.caption, branch.side === 'bottom' ? 'top' : 'left', 'relation');
        if (route.steps.hidden) continue;
        const steps = [...route.steps.children];
        if (branch.side === 'left') addEdge(route.caption, 'left', steps[steps.length - 1], 'right', 'relation');
        else addEdge(route.caption, 'right', steps[0], 'left', 'relation');
        for (let index = 1; index < steps.length; index++) {
          const tested = [steps[index - 1], steps[index]].every(step => step.querySelector('.flow-status').classList.contains('test'));
          addEdge(steps[index - 1], 'right', steps[index], 'left', tested ? 'money' : 'conditional');
        }
      }
    }

    const after = balance.getBoundingClientRect();
    scroller.scrollLeft += after.left - before.left;
    scroller.scrollTop += after.top - before.top;
  }

  function reveal(branch, target = branch.routes[0].caption) {
    const point = port(target, 'left');
    const margin = target === branch.routes[0].caption ? 480 : 240;
    const x = branch.side === 'left' ? port(target, 'right')[0] * scale - scroller.clientWidth + margin : point[0] * scale - margin;
    scroller.scrollTo({left: Math.max(0, x), top: Math.max(0, point[1] * scale - 134)});
  }

  function expand(branch, open) {
    branch.element.hidden = !open;
    branch.toggle.setAttribute('aria-expanded', String(open));
    branch.root.querySelector('.hub-open').textContent = open ? '−' : '+';
    layout();
    if (open) reveal(branch);
    toolbar.querySelector('.hub-live').textContent = branch.root.querySelector('.hub-title').textContent + ' · ' + (open ? scroller.dataset.collapse : scroller.dataset.expand);
  }

  for (const branch of branches) {
    for (const route of branch.routes) {
      route.toggle.addEventListener('click', () => {
        route.steps.hidden = !route.steps.hidden;
        route.toggle.setAttribute('aria-expanded', String(!route.steps.hidden));
        route.hint.textContent = route.steps.hidden ? '+' : '−';
        layout();
        const target = route.steps.hidden ? route.caption : branch.side === 'left' ? route.steps.lastElementChild : route.steps.firstElementChild;
        reveal(branch, target);
      });
    }
    branch.toggle.addEventListener('click', event => {
      event.preventDefault();
      expand(branch, branch.element.hidden);
    });
    branch.toggle.addEventListener('keydown', event => {
      if (event.key === ' ') {
        event.preventDefault();
        branch.toggle.click();
      }
    });
  }
  function centreBalance() {
    const [x, y] = port(balance, 'top');
    scroller.scrollTo({left: Math.max(0, x * scale - scroller.clientWidth / 2), top: Math.max(0, (y + balance.offsetHeight / 2) * scale - scroller.clientHeight / 2)});
  }
  toolbar.querySelector('.hub-home').addEventListener('click', centreBalance);
  function setScale(value) {
    scale = value;
    map.style.zoom = String(scale);
    toolbar.querySelector('.hub-reset').textContent = Math.round(scale * 100) + '%';
    toolbar.querySelector('.hub-zoom-out').disabled = scale <= 0.1;
    toolbar.querySelector('.hub-zoom-in').disabled = scale >= 2;
    layout();
    centreBalance();
  }
  toolbar.querySelector('.hub-fit').addEventListener('click', () => {
    const availableHeight = parseFloat(getComputedStyle(scroller).maxHeight);
    setScale(Math.min(1, (scroller.clientWidth - 16) / parseFloat(map.style.width), (availableHeight - 16) / parseFloat(map.style.height)));
  });
  toolbar.querySelector('.hub-zoom-out').addEventListener('click', () => setScale(Math.max(0.1, scale - 0.1)));
  toolbar.querySelector('.hub-zoom-in').addEventListener('click', () => setScale(Math.min(2, scale + 0.1)));
  toolbar.querySelector('.hub-reset').addEventListener('click', () => setScale(1));
  function openFragment() {
    const branch = branches.find(item => '#' + item.element.id === location.hash);
    if (branch) expand(branch, true);
  }
  window.addEventListener('hashchange', openFragment);
  new ResizeObserver(layout).observe(scroller);
  layout();
  openFragment();
})();
