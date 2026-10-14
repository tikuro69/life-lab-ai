"""Interpret instructions as a small allowlist; never execute generated code."""
import json
from pathlib import Path
import os
import random
import re
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

JAPANESE = json.loads((Path(__file__).parent / 'locales' / 'ja.json').read_text(encoding='utf-8'))

SIZE = 20
PATTERNS = {
    'glider': [(0, 1), (1, 2), (2, 0), (2, 1), (2, 2)],
    'blinker': [(0, 0), (0, 1), (0, 2)],
    'block': [(0, 0), (0, 1), (1, 0), (1, 1)],
}


class CommandError(ValueError):
    pass


def local_actions(text):
    text = unicodedata.normalize('NFKC', text).strip().lower().rstrip('.!')
    text = re.sub(r'^please\s+', '', text)
    for action, pattern in {
        'clear': r'(?:clear(?: the board)?|reset)',
        'random': r'(?:random|randomize(?: the board)?)',
        'start': r'(?:start|play|resume)',
        'stop': r'(?:stop|pause)',
    }.items():
        if re.fullmatch(pattern, text):
            return [{'action': action}]
    match = re.fullmatch(r'(?:advance|step)(?: by)? (\d+)(?: generations?)?', text)
    if match:
        return [{'action': 'step', 'steps': int(match[1])}]
    match = re.fullmatch(r'(?:place|add) (?:a )?(glider|blinker|block)(?: (?:in|at) (?:the )?(center|top left|top right|bottom left|bottom right))?', text)
    if match:
        name, position = match.groups()
        points = PATTERNS[name]
        height = max(r for r, _ in points) + 1
        width = max(c for _, c in points) + 1
        row = 1 if position in ('top left', 'top right') else SIZE - height + 1 if position in ('bottom left', 'bottom right') else (SIZE - height) // 2 + 1
        col = 1 if position in ('top left', 'bottom left') else SIZE - width + 1 if position in ('top right', 'bottom right') else (SIZE - width) // 2 + 1
        return [{'action': 'pattern', 'pattern': name, 'row': row, 'col': col}]
    match = re.fullmatch(r'set (?:cell (?:at )?)?row (\d+)[, ]+column (\d+) (?:to )?(alive|dead)', text)
    if match:
        row, col, state = match.groups()
        return [{'action': 'set_cell', 'row': int(row), 'col': int(col), 'alive': state == 'alive'}]
    return japanese_actions(text)


def japanese_actions(text):
    text = unicodedata.normalize('NFKC', text).strip().lower().rstrip(JAPANESE['punctuation'])
    suffix = JAPANESE['polite_suffix']
    for action, phrases in {
        'clear': JAPANESE['clear_expression'],
        'random': JAPANESE['random_expression'],
        'start': JAPANESE['start_expression'],
        'stop': JAPANESE['stop_expression'],
    }.items():
        if re.fullmatch(phrases + suffix, text):
            return [{'action': action}]
    match = re.fullmatch(JAPANESE['step_expression'] + suffix, text)
    if match:
        return [{'action': 'step', 'steps': int(match[1])}]
    match = re.fullmatch(
        JAPANESE['pattern_expression'] +
        JAPANESE['placement_suffix'] + suffix, text)
    if match:
        position, name = match.groups()
        pattern = {JAPANESE['glider']: 'glider', JAPANESE['blinker']: 'blinker', JAPANESE['block']: 'block'}[name]
        points = PATTERNS[pattern]
        height = max(r for r, _ in points) + 1
        width = max(c for _, c in points) + 1
        row = 1 if position in (JAPANESE['top_left'], JAPANESE['top_right']) else SIZE - height + 1 if position in (JAPANESE['bottom_left'], JAPANESE['bottom_right']) else (SIZE - height) // 2 + 1
        col = 1 if position in (JAPANESE['top_left'], JAPANESE['bottom_left']) else SIZE - width + 1 if position in (JAPANESE['top_right'], JAPANESE['bottom_right']) else (SIZE - width) // 2 + 1
        return [{'action': 'pattern', 'pattern': pattern, 'row': row, 'col': col}]
    match = re.fullmatch(JAPANESE['cell_expression'] + suffix, text)
    if match:
        row, col, state = match.groups()
        return [{'action': 'set_cell', 'row': int(row), 'col': int(col), 'alive': state == JAPANESE['alive']}]
    return None


def ai_actions(text):
    key = os.environ.get('OPENAI_API_KEY')
    if not key:
        raise CommandError('Instruction not recognized locally. Try an example or set OPENAI_API_KEY.')
    properties = {
        'action': {'type': 'string', 'enum': ['clear', 'random', 'pattern', 'set_cell', 'step', 'start', 'stop', 'unsupported']},
        'pattern': {'type': ['string', 'null'], 'enum': [*PATTERNS, None]},
        'row': {'type': ['integer', 'null']},
        'col': {'type': ['integer', 'null']},
        'alive': {'type': ['boolean', 'null']},
        'steps': {'type': ['integer', 'null']},
    }
    payload = {
        'model': os.environ.get('OPENAI_MODEL', 'gpt-4o-mini'),
        'store': False,
        'instructions': (
            'Convert instructions into operations on a finite 20x20 Game of Life board. Coordinates are 1-20. '
            'Patterns are added without clearing; row/col specify the top-left. Glider is 3x3, blinker 1x3, block 2x2. '
            'Center patterns if the position is omitted or specified as center. '
            'Step allows 1-100 generations; random uses a 30% live-cell probability. '
            'Unused fields must be null. Return at most 10 operations in the requested order. '
            'For unsupported, ambiguous, or board-observation requests, return only unsupported. '
            'Do not add clear or any other operation unless explicitly requested.'
        ),
        'input': text,
        'max_output_tokens': 1500,
        'text': {'format': {
            'type': 'json_schema', 'name': 'life_actions', 'strict': True,
            'schema': {
                'type': 'object', 'properties': {'actions': {
                    'type': 'array', 'items': {'type': 'object', 'properties': properties,
                    'required': list(properties), 'additionalProperties': False}}},
                'required': ['actions'], 'additionalProperties': False,
            },
        }},
    }
    request = Request('https://api.openai.com/v1/responses',
                      data=json.dumps(payload).encode(),
                      headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'})
    try:
        with urlopen(request, timeout=20) as response:
            data = json.load(response)
        if data.get('status') != 'completed':
            raise CommandError('AI interpretation did not complete. Try a shorter instruction.')
        output = ''.join(part['text'] for item in data.get('output', [])
                         for part in item.get('content', []) if part.get('type') == 'output_text')
        return json.loads(output)['actions']
    except (HTTPError, URLError, TimeoutError):
        raise CommandError('Cannot connect to AI. Check your API key, model, and connection.') from None
    except (ValueError, KeyError, TypeError):
        raise CommandError('Invalid AI response. The board has not been changed.') from None


def validate_actions(actions):
    if not isinstance(actions, list) or not 1 <= len(actions) <= 10:
        raise CommandError('Provide between 1 and 10 operations.')
    for item in actions:
        if not isinstance(item, dict):
            raise CommandError('Invalid operation format.')
        action = item.get('action')
        allowed = {
            'clear': set(), 'random': set(), 'start': set(), 'stop': set(),
            'step': {'steps'}, 'pattern': {'pattern', 'row', 'col'},
            'set_cell': {'row', 'col', 'alive'},
        }
        if not isinstance(action, str) or action not in allowed:
            raise CommandError('Unsupported instruction. See the examples.')
        if any(k != 'action' and (k not in allowed[action]) and v is not None for k, v in item.items()):
            raise CommandError('The operation contains unexpected parameters.')
        if action == 'step' and (type(item.get('steps')) is not int or not 1 <= item['steps'] <= 100):
            raise CommandError('Advance between 1 and 100 generations per operation.')
        if action in ('pattern', 'set_cell'):
            if any(type(item.get(k)) is not int or not 1 <= item[k] <= SIZE for k in ('row', 'col')):
                raise CommandError('Rows and columns must be integers from 1 to 20.')
        if action == 'set_cell' and type(item.get('alive')) is not bool:
            raise CommandError('Cell state must be a boolean.')
        if action == 'pattern':
            name = item.get('pattern')
            if not isinstance(name, str) or name not in PATTERNS:
                raise CommandError('Supported patterns: glider, blinker, block.')
            if any(item['row'] + r > SIZE or item['col'] + c > SIZE for r, c in PATTERNS[name]):
                raise CommandError('The pattern extends outside the board. Choose another position.')
    return actions


def execute_actions(grid, generation, running, actions, next_generation):
    validate_actions(actions)
    grid = [row[:] for row in grid]
    messages = []
    for item in actions:
        action = item['action']
        if action in ('clear', 'random'):
            grid = [[int(action == 'random' and random.random() < .3) for _ in range(SIZE)] for _ in range(SIZE)]
            generation, running = 0, False
            messages.append('Board cleared.' if action == 'clear' else 'Board randomized.')
        elif action == 'step':
            for _ in range(item['steps']):
                grid = next_generation(grid)
            generation += item['steps']
            running = False
            messages.append(f"Advanced {item['steps']} generations.")
        elif action == 'pattern':
            for r, c in PATTERNS[item['pattern']]:
                grid[item['row'] - 1 + r][item['col'] - 1 + c] = 1
            running = False
            label = item['pattern']
            messages.append(f"Added {label} at row {item['row']}, column {item['col']}.")
        elif action == 'set_cell':
            grid[item['row'] - 1][item['col'] - 1] = int(item['alive'])
            running = False
            messages.append(f"Set row {item['row']}, column {item['col']} to {'alive' if item['alive'] else 'dead'}.")
        else:
            running = action == 'start'
            messages.append('Playback started.' if running else 'Playback stopped.')
    return dict(grid=grid, generation=generation, running=running, message=' '.join(messages))
