import unittest

from app import SIZE, app, next_generation


def board(points):
    grid = [[0] * SIZE for _ in range(SIZE)]
    for row, col in points:
        grid[row][col] = 1
    return grid


class LifeTests(unittest.TestCase):
    def test_block_is_stable(self):
        grid = board([(8, 8), (8, 9), (9, 8), (9, 9)])
        self.assertEqual(next_generation(grid), grid)

    def test_blinker_oscillates(self):
        horizontal = board([(10, 9), (10, 10), (10, 11)])
        vertical = board([(9, 10), (10, 10), (11, 10)])
        self.assertEqual(next_generation(horizontal), vertical)
        self.assertEqual(next_generation(vertical), horizontal)

    def test_edges_do_not_wrap(self):
        grid = board([(19, 19), (19, 0), (0, 19)])
        self.assertEqual(next_generation(grid), board([]))

    def test_api_and_page(self):
        client = app.test_client()
        self.assertEqual(client.get('/').status_code, 200)
        grid = board([(0, 0)])
        response = client.post('/api/step', json={'grid': grid})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['grid'], board([]))

    def test_invalid_input(self):
        client = app.test_client()
        for payload in [None, [], {}, {'grid': []}, {'grid': [[2] * SIZE] * SIZE}]:
            self.assertEqual(client.post('/api/step', json=payload).status_code, 400)


if __name__ == '__main__':
    unittest.main()
