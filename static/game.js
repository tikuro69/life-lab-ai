const size = 20;
let grid = Array.from({ length: size }, () => Array(size).fill(0));
let generation = 0;
let running = false;
let revision = null;
let busy = false;
const board = document.getElementById('board');
const toggle = document.getElementById('toggle');
const stepButton = document.getElementById('step');
const randomButton = document.getElementById('random');
const clearButton = document.getElementById('clear');
const error = document.getElementById('error');
const commandForm = document.getElementById('command-form');
const instruction = document.getElementById('instruction');
const commandSubmit = document.getElementById('command-submit');
const commandResult = document.getElementById('command-result');
const cells = [];

for (let row = 0; row < size; row++) {
  for (let col = 0; col < size; col++) {
    const cell = document.createElement('button');
    cell.className = 'cell';
    cell.setAttribute('aria-label', `Row ${row + 1}, column ${col + 1}`);
    cell.addEventListener('click', () => {
      if (!running && !busy && revision !== null) {
        mutate('/api/board/actions', { actions: [{ action: 'set_cell', row: row + 1, col: col + 1, alive: !grid[row][col] }] });
      }
    });
    board.appendChild(cell);
    cells.push(cell);
  }
}

function render() {
  const unavailable = busy || revision === null;
  grid.flat().forEach((value, index) => {
    cells[index].classList.toggle('alive', value === 1);
    cells[index].setAttribute('aria-pressed', String(value === 1));
    cells[index].disabled = running || unavailable;
  });
  document.getElementById('generation').textContent = generation;
  document.getElementById('population').textContent = grid.flat().reduce((a, b) => a + b, 0);
  toggle.textContent = running ? 'Stop' : 'Start';
  toggle.disabled = unavailable;
  commandSubmit.disabled = unavailable;
  instruction.disabled = unavailable;
  stepButton.disabled = running || unavailable;
  randomButton.disabled = running || unavailable;
  clearButton.disabled = running || unavailable;
}

function accept(data) {
  grid = data.grid;
  generation = data.generation;
  running = data.running;
  revision = data.revision;
}

async function requestState(url, payload) {
  const response = await fetch(url, payload === undefined ? { cache: 'no-store' } : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'The operation failed.');
  return data;
}

async function mutate(url, payload) {
  if (busy || revision === null) return;
  busy = true;
  error.textContent = '';
  const isCommand = url.endsWith('/command');
  commandResult.textContent = isCommand ? 'Interpreting your instruction…' : '';
  render();
  try {
    const data = await requestState(url, { ...payload, revision });
    accept(data);
    commandResult.textContent = isCommand
      ? `${data.message} (${data.source === 'ai' ? 'AI interpretation' : 'Local interpretation'})` : data.message;
  } catch (err) {
    error.textContent = err.message;
    commandResult.textContent = '';
    try { accept(await requestState('/api/board')); } catch (_) { revision = null; }
  } finally {
    busy = false;
    render();
  }
}

async function poll() {
  if (!busy) {
    busy = true;
    try {
      accept(await requestState('/api/board'));
    } catch (_) {
      revision = null;
      error.textContent = 'Cannot reach the server. Check that Flask is running.';
    } finally {
      busy = false;
      render();
    }
  }
  setTimeout(poll, 250);
}

toggle.addEventListener('click', () => mutate('/api/board/actions', { actions: [{ action: running ? 'stop' : 'start' }] }));
stepButton.addEventListener('click', () => mutate('/api/board/actions', { actions: [{ action: 'step', steps: 1 }] }));
randomButton.addEventListener('click', () => mutate('/api/board/actions', { actions: [{ action: 'random' }] }));
clearButton.addEventListener('click', () => mutate('/api/board/actions', { actions: [{ action: 'clear' }] }));
commandForm.addEventListener('submit', (event) => {
  event.preventDefault();
  if (instruction.value.trim()) mutate('/api/board/command', { instruction: instruction.value });
});
render();
poll();
