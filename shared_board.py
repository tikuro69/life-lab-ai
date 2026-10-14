import threading
import time

from commands import CommandError, execute_actions


class Conflict(CommandError):
    pass


class SharedBoard:
    """One in-memory board per Flask process, shared by browser and MCP."""

    def __init__(self, evolve):
        self.evolve = evolve
        self.lock = threading.RLock()
        self.grid = [[0] * 20 for _ in range(20)]
        self.generation = 0
        self.running = False
        self.revision = 0
        self.last_tick = time.monotonic()

    def _sync(self):
        now = time.monotonic()
        if self.running:
            count = int((now - self.last_tick) / .25)
            for _ in range(count):
                self.grid = self.evolve(self.grid)
            self.generation += count
            self.revision += count
            self.last_tick += count * .25
        else:
            self.last_tick = now

    def snapshot(self):
        with self.lock:
            self._sync()
            return dict(grid=[row[:] for row in self.grid], generation=self.generation,
                        running=self.running, revision=self.revision,
                        population=sum(map(sum, self.grid)), size=20)

    def apply(self, actions, expected_revision=None):
        with self.lock:
            # Compare edit revisions before advancing the automatic clock.
            if expected_revision is not None and expected_revision != self.revision:
                raise Conflict('Another operation updated the board. Refresh and try again.')
            self._sync()
            result = execute_actions(self.grid, self.generation, self.running, actions, self.evolve)
            self.grid, self.generation, self.running = result['grid'], result['generation'], result['running']
            self.revision += 1
            self.last_tick = time.monotonic()
            return dict(self.snapshot(), message=result['message'])
