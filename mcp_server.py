"""stdio / Streamable HTTP MCP bridge to the local Flask application."""
import argparse
import json
import os
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from mcp.server.fastmcp import FastMCP

mcp = FastMCP('Life Lab')
BASE_URL = os.environ.get('LIFE_APP_URL', 'http://127.0.0.1:5000').rstrip('/')
parsed = urlsplit(BASE_URL)
if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost') or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
    raise ValueError('LIFE_APP_URL must be a local HTTP URL, e.g. http://127.0.0.1:5000')


def app_request(path, payload=None):
    request = Request(BASE_URL + path, data=None if payload is None else json.dumps(payload).encode(),
                      headers={'Content-Type': 'application/json'})
    try:
        with urlopen(request, timeout=10) as response:
            return json.load(response)
    except HTTPError as exc:
        try:
            message = json.load(exc).get('error', 'The operation was rejected.')
        except (ValueError, AttributeError):
            message = 'The operation was rejected.'
        raise ValueError(message) from None
    except (URLError, TimeoutError):
        raise ValueError('Start Flask and check the port in LIFE_APP_URL.') from None


def apply(action, revision=None):
    return app_request('/api/board/actions', {'actions': [action], 'revision': revision})


@mcp.tool()
def get_board() -> dict:
    """Read the shared 20x20 grid, generation, population, running and revision."""
    return app_request('/api/board')


@mcp.tool()
def set_cell(row: int, col: int, alive: bool, revision: int | None = None) -> dict:
    """Set one cell. Row/col are 1-20. Stops playback. Optional revision prevents stale edits."""
    return apply(dict(action='set_cell', row=row, col=col, alive=alive), revision)


@mcp.tool()
def place_pattern(pattern: Literal['glider', 'blinker', 'block'], row: int = 9, col: int = 9,
                  revision: int | None = None) -> dict:
    """Add a pattern without clearing existing cells. Row/col specify its top-left, 1-based. Stops playback."""
    return apply(dict(action='pattern', pattern=pattern, row=row, col=col), revision)


@mcp.tool()
def step_generation(steps: int = 1, revision: int | None = None) -> dict:
    """Advance 1-100 generations and stop playback."""
    return apply(dict(action='step', steps=steps), revision)


@mcp.tool()
def clear_board(revision: int | None = None) -> dict:
    """Clear every cell, reset generation to zero and stop playback."""
    return apply(dict(action='clear'), revision)


@mcp.tool()
def randomize_board(revision: int | None = None) -> dict:
    """Replace the board with about 30% live cells, reset generation and stop playback."""
    return apply(dict(action='random'), revision)


@mcp.tool()
def start_game() -> dict:
    """Start playback at four generations per second; shared with every browser."""
    return apply(dict(action='start'))


@mcp.tool()
def stop_game() -> dict:
    """Stop automatic playback."""
    return apply(dict(action='stop'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--transport', choices=['stdio', 'streamable-http'], default='stdio')
    parser.add_argument('--port', type=int, default=8000, help='HTTP listen port (default: 8000)')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('--port must be between 1 and 65535')
    mcp.settings.host = '127.0.0.1'
    mcp.settings.port = args.port
    mcp.settings.json_response = True
    mcp.run(transport=args.transport)
