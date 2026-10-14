import json
import os
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from werkzeug.serving import make_server

from app import app, next_generation
from shared_board import SharedBoard


class MCPIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_stdio_session_and_shared_flask_board(self):
        board = SharedBoard(next_generation)
        with patch('app.shared_board', board):
            server = make_server('127.0.0.1', 0, app)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                root = Path(__file__).resolve().parents[1]
                params = StdioServerParameters(command=sys.executable, args=[str(root / 'mcp_server.py')],
                    env={**os.environ, 'LIFE_APP_URL': f'http://127.0.0.1:{server.server_port}'})
                async with stdio_client(params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        tools = await session.list_tools()
                        self.assertEqual({t.name for t in tools.tools}, {
                            'get_board', 'set_cell', 'place_pattern', 'step_generation',
                            'clear_board', 'randomize_board', 'start_game', 'stop_game'})
                        async def call(name, args=None):
                            result = await session.call_tool(name, args or {})
                            self.assertFalse(result.isError, result)
                            return json.loads(result.content[0].text)
                        self.assertEqual((await call('get_board'))['population'], 0)
                        state = await call('place_pattern', dict(pattern='glider', row=9, col=9))
                        self.assertEqual(state['population'], 5)
                        self.assertEqual(app.test_client().get('/api/board').json['grid'], state['grid'])
                        self.assertEqual((await call('step_generation', dict(steps=10)))['generation'], 10)
                        invalid = await session.call_tool('set_cell', dict(row=21, col=1, alive=True))
                        self.assertTrue(invalid.isError)
                        self.assertEqual((await call('get_board'))['population'], 5)
                        self.assertTrue((await call('start_game'))['running'])
                        self.assertFalse((await call('stop_game'))['running'])
                        state = await call('randomize_board')
                        self.assertEqual(state['generation'], 0)
                        self.assertEqual((await call('clear_board'))['population'], 0)
                        state = await call('get_board')
                        await call('set_cell', dict(row=3, col=5, alive=True, revision=state['revision']))
                        conflict = await session.call_tool('clear_board', dict(revision=state['revision']))
                        self.assertTrue(conflict.isError)
                        self.assertEqual((await call('get_board'))['population'], 1)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)
