import json
import os
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from app import app
from commands import CommandError, ai_actions, execute_actions, local_actions
from tests.test_app import board
from app import next_generation


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.payload = dict(grid=board([]), generation=0, running=False)

    def command(self, instruction):
        return self.client.post('/api/command', json=dict(self.payload, instruction=instruction))

    def test_local_commands_do_not_call_ai(self):
        with patch('app.ai_actions') as ai:
            response = self.command('place a glider in the center')
        ai.assert_not_called()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['source'], 'local')
        self.assertEqual(sum(map(sum, response.json['grid'])), 5)
        self.assertEqual(response.json['grid'][9][10], 1)

    def test_japanese_compatibility(self):
        from commands import JAPANESE
        text = JAPANESE['start_expression'].removeprefix('(?:').removesuffix(')').split('|')[0]
        self.assertEqual(local_actions(text), [{'action': 'start'}])
        self.assertEqual(local_actions(JAPANESE['glider']),
                         [{'action': 'pattern', 'pattern': 'glider', 'row': 9, 'col': 9}])

    def test_set_cell_preserves_other_cells(self):
        self.payload['grid'] = board([(0, 0)])
        response = self.command('set row 3 column 5 alive')
        self.assertEqual(response.json['grid'][2][4], 1)
        self.assertEqual(response.json['grid'][0][0], 1)

    def test_step_and_run_controls(self):
        self.payload.update(grid=board([(10, 9), (10, 10), (10, 11)]), generation=7, running=True)
        response = self.command('advance 1 generation')
        self.assertEqual(response.json['grid'], board([(9, 10), (10, 10), (11, 10)]))
        self.assertEqual(response.json['generation'], 8)
        self.assertFalse(response.json['running'])
        self.assertTrue(self.command('start').json['running'])
        self.assertFalse(self.command('stop').json['running'])
        self.assertEqual(self.command('clear').json['grid'], board([]))
        self.assertEqual(self.command('clear').json['generation'], 0)

    def test_invalid_and_unknown_commands(self):
        with patch.dict(os.environ, {}, clear=True):
            for text in ['', 'x' * 501, 'advance 0 generations', 'advance 101 generations',
                         'set row 21 column 5 alive', 'execute arbitrary code',
                         'clear then do something unsupported']:
                self.assertEqual(self.command(text).status_code, 400, text)

    def test_ai_actions_applied_in_order(self):
        self.payload['grid'] = board([(0, 0)])
        actions = [{'action': 'clear'}, {'action': 'pattern', 'pattern': 'block', 'row': 9, 'col': 9}]
        with patch('app.ai_actions', return_value=actions):
            response = self.command('empty the board then create a square near the center')
        self.assertEqual(response.json['source'], 'ai')
        self.assertEqual(response.json['grid'], board([(8, 8), (8, 9), (9, 8), (9, 9)]))

    def test_invalid_ai_output_is_rejected_atomically(self):
        original = board([(0, 0)])
        for item in [dict(action='pattern', pattern='glider', row=20, col=20),
                     dict(action='set_cell', row=True, col=1, alive=True),
                     dict(action=[]), dict(action='clear', steps=100),
                     dict(action='unsupported')]:
            with self.assertRaises(CommandError):
                execute_actions(original, 0, False, [dict(action='clear'), item], next_generation)
            self.assertEqual(original, board([(0, 0)]))

    def test_invalid_request_state(self):
        for key, value in [('grid', []), ('generation', True), ('running', 'true')]:
            payload = dict(self.payload, instruction='clear')
            payload[key] = value
            self.assertEqual(self.client.post('/api/command', json=payload).status_code, 400)

    def test_openai_request_and_failure(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({
            'status': 'completed', 'output': [{'content': [{'type': 'output_text',
            'text': json.dumps({'actions': [{'action': 'stop'}]})}]}],
        }).encode()
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}), patch('commands.urlopen', return_value=response) as opener:
            self.assertEqual(ai_actions('halt movement for a moment'), [{'action': 'stop'}])
            request = opener.call_args.args[0]
            payload = json.loads(request.data)
            self.assertEqual(payload['input'], 'halt movement for a moment')
            self.assertFalse(payload['store'])
            self.assertNotIn('grid', payload)
            self.assertTrue(payload['text']['format']['strict'])
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}), patch('commands.urlopen', side_effect=URLError('offline')):
            with self.assertRaises(CommandError):
                ai_actions('halt movement for a moment')

    def test_incomplete_ai_response(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"status":"incomplete"}'
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}), patch('commands.urlopen', return_value=response):
            with self.assertRaises(CommandError):
                ai_actions('instruction')


if __name__ == '__main__':
    unittest.main()
