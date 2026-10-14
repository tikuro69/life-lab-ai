from flask import Flask, jsonify, render_template, request
from commands import CommandError, ai_actions, execute_actions, local_actions
import os
from shared_board import Conflict, SharedBoard

app = Flask(__name__)
SIZE = 20


def next_generation(grid):
    """Finite board: cells outside the edges are dead."""
    result = [[0] * SIZE for _ in range(SIZE)]
    for row in range(SIZE):
        for col in range(SIZE):
            neighbors = sum(
                grid[r][c]
                for r in range(max(0, row - 1), min(SIZE, row + 2))
                for c in range(max(0, col - 1), min(SIZE, col + 2))
                if (r, c) != (row, col)
            )
            result[row][col] = int(neighbors == 3 or (grid[row][col] == 1 and neighbors == 2))
    return result


@app.get("/")
def index():
    return render_template("index.html", size=SIZE, ai_enabled=bool(os.environ.get('OPENAI_API_KEY')))


shared_board = SharedBoard(next_generation)


@app.get('/api/board')
def get_board():
    return jsonify(shared_board.snapshot())


@app.post('/api/board/actions')
def board_actions():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error='Provide operations as JSON.'), 400
    revision = data.get('revision')
    if revision is not None and (type(revision) is not int or revision < 0):
        return jsonify(error='Revision must be a nonnegative integer.'), 400
    try:
        return jsonify(shared_board.apply(data.get('actions'), revision))
    except Conflict as exc:
        return jsonify(error=str(exc)), 409
    except CommandError as exc:
        return jsonify(error=str(exc)), 400


@app.post('/api/board/command')
def shared_command():
    data = request.get_json(silent=True)
    text = data.get('instruction') if isinstance(data, dict) else None
    revision = data.get('revision') if isinstance(data, dict) else None
    if not isinstance(text, str) or not 1 <= len(text.strip()) <= 500:
        return jsonify(error='Instructions must contain 1 to 500 characters.'), 400
    if type(revision) is not int or revision < 0:
        return jsonify(error='Provide the current board revision.'), 400
    try:
        actions = local_actions(text)
        source = 'local' if actions is not None else 'ai'
        if actions is None:
            actions = ai_actions(text)
        return jsonify(**shared_board.apply(actions, revision), source=source)
    except Conflict as exc:
        return jsonify(error=str(exc)), 409
    except CommandError as exc:
        return jsonify(error=str(exc)), 400


def valid_grid(grid):
    return (
        isinstance(grid, list) and len(grid) == SIZE
        and all(isinstance(row, list) and len(row) == SIZE
                and all(type(cell) is int and cell in (0, 1) for cell in row)
                for row in grid)
    )


@app.post("/api/step")
def step():
    data = request.get_json(silent=True)
    grid = data.get("grid") if isinstance(data, dict) else None
    if not valid_grid(grid):
        return jsonify(error="The grid must be a 20x20 array of integer zeros and ones."), 400
    return jsonify(grid=next_generation(grid))


@app.post('/api/command')
def command():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not valid_grid(data.get('grid')):
        return jsonify(error='The grid must be a 20x20 array of integer zeros and ones.'), 400
    text, generation, running = data.get('instruction'), data.get('generation'), data.get('running')
    if not isinstance(text, str) or not 1 <= len(text.strip()) <= 500:
        return jsonify(error='Instructions must contain 1 to 500 characters.'), 400
    if type(generation) is not int or not 0 <= generation <= 10**9 or type(running) is not bool:
        return jsonify(error='Invalid generation counter or playback state.'), 400
    try:
        actions = local_actions(text)
        source = 'local' if actions is not None else 'ai'
        if actions is None:
            actions = ai_actions(text)
        result = execute_actions(data['grid'], generation, running, actions, next_generation)
        return jsonify(**result, source=source)
    except CommandError as exc:
        return jsonify(error=str(exc)), 400


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
