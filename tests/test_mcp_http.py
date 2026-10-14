import asyncio
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from werkzeug.serving import make_server
from app import app, next_generation
from shared_board import SharedBoard


class HTTPMCPTests(unittest.IsolatedAsyncioTestCase):
    async def test_http_session_tools_operations_and_shared_board(self):
        board = SharedBoard(next_generation)
        with patch('app.shared_board', board):
            flask = make_server('127.0.0.1', 0, app)
            thread = threading.Thread(target=flask.serve_forever, daemon=True)
            thread.start()
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            root = Path(__file__).resolve().parents[1]
            process = subprocess.Popen([sys.executable, str(root / 'mcp_server.py'),
                '--transport', 'streamable-http', '--port', str(port)],
                env={**os.environ, 'LIFE_APP_URL': f'http://127.0.0.1:{flask.server_port}'},
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            url = f'http://127.0.0.1:{port}/mcp'
            try:
                async with httpx.AsyncClient(timeout=1) as client:
                    for _ in range(100):
                        if process.poll() is not None:
                            self.fail('HTTP MCP server exited before startup')
                        try:
                            response = await client.get(url)
                            if response.status_code < 500:
                                break
                        except httpx.TransportError:
                            pass
                        await asyncio.sleep(.05)
                    else:
                        self.fail('HTTP MCP server did not start')
                    bad_host = await client.post(url, json={}, headers={'Host': 'evil.example'})
                    self.assertEqual(bad_host.status_code, 421)
                async with streamable_http_client(url) as (read, write, _):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        self.assertEqual(len((await session.list_tools()).tools), 8)
                        async def call(name, args=None):
                            result = await session.call_tool(name, args or {})
                            self.assertFalse(result.isError, result)
                            return json.loads(result.content[0].text)
                        state = await call('place_pattern', {'pattern': 'glider', 'row': 9, 'col': 9})
                        self.assertEqual(state['population'], 5)
                        state = await call('step_generation', {'steps': 10, 'revision': state['revision']})
                        self.assertEqual(state['generation'], 10)
                        self.assertEqual(app.test_client().get('/api/board').json['grid'], state['grid'])
                        invalid = await session.call_tool('set_cell', {'row': 21, 'col': 1, 'alive': True})
                        self.assertTrue(invalid.isError)
                        self.assertEqual((await call('get_board'))['population'], 5)
                        self.assertTrue((await call('start_game'))['running'])
                        self.assertFalse((await call('stop_game'))['running'])
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                flask.shutdown()
                flask.server_close()
                thread.join(timeout=2)
