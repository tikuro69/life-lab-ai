import unittest
from unittest.mock import patch

from app import app, next_generation
from shared_board import SharedBoard, Conflict
from commands import CommandError


class SharedBoardTests(unittest.TestCase):
    def setUp(self):
        self.board = SharedBoard(next_generation)

    def test_state_is_shared_and_snapshot_is_copy(self):
        state = self.board.apply([dict(action='set_cell', row=1, col=1, alive=True)])
        state['grid'][0][0] = 0
        self.assertEqual(self.board.snapshot()['population'], 1)

    def test_conflict_and_atomic_invalid_operation(self):
        self.board.apply([dict(action='set_cell', row=1, col=1, alive=True)])
        with self.assertRaises(Conflict):
            self.board.apply([dict(action='clear')], 0)
        with self.assertRaises(CommandError):
            self.board.apply([dict(action='clear'), dict(action='step', steps=101)])
        self.assertEqual(self.board.snapshot()['population'], 1)

    def test_server_clock_advances_without_browser_step(self):
        with patch('shared_board.time.monotonic', return_value=100):
            self.board.apply([dict(action='start')])
        with patch('shared_board.time.monotonic', return_value=101):
            self.assertEqual(self.board.snapshot()['generation'], 4)
            self.board.apply([dict(action='stop')])
        with patch('shared_board.time.monotonic', return_value=110):
            self.assertEqual(self.board.snapshot()['generation'], 4)

    def test_http_and_natural_language_share_same_board(self):
        with patch('app.shared_board', self.board):
            client = app.test_client()
            self.assertEqual(client.get('/api/board').json['population'], 0)
            response = client.post('/api/board/command', json=dict(instruction='place a glider in the center', revision=0))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(client.get('/api/board').json['population'], 5)
            response = client.post('/api/board/actions', json=dict(actions=[dict(action='clear')], revision=0))
            self.assertEqual(response.status_code, 409)
            self.assertEqual(client.get('/api/board').json['population'], 5)
