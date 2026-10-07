"""Game rules for one or more snakes, independent of rendering and networking.

In multiplayer the host runs the World and sends `to_dict()` snapshots to
clients, which rebuild a read-only copy with `World.from_dict()` to draw.
"""

import random
from collections import deque

from apples import APPLE_TYPES, APPLE_TYPES_BY_NAME

GRID_WIDTH = 25
GRID_HEIGHT = 20
START_SPEED = 8  # moves per second

UP = (0, -1)
DOWN = (0, 1)
LEFT = (-1, 0)
RIGHT = (1, 0)

MAX_QUEUED_TURNS = 2

SOLO_SPAWN = ((GRID_WIDTH // 4, GRID_HEIGHT // 2), RIGHT)
VERSUS_SPAWNS = [
    ((GRID_WIDTH // 4, GRID_HEIGHT // 3), RIGHT),
    ((GRID_WIDTH * 3 // 4, GRID_HEIGHT * 2 // 3), LEFT),
]


class Snake:
    def __init__(self, start, direction=RIGHT):
        self.body = deque([start])
        self.direction = direction
        self._turns = deque()
        self.pending_growth = 2
        self._prev_body = list(self.body)

    @property
    def head(self):
        return self.body[0]

    def queue_direction(self, direction):
        # Buffer quick successive turns, validating each against the one before
        # it so the snake can never reverse into itself.
        last = self._turns[-1] if self._turns else self.direction
        if direction in (last, (-last[0], -last[1])):
            return
        if len(self._turns) < MAX_QUEUED_TURNS:
            self._turns.append(direction)

    def next_head(self):
        dx, dy = self._turns[0] if self._turns else self.direction
        x, y = self.head
        return x + dx, y + dy

    def cells_blocking_next_step(self):
        # The tail moves out of the way this step unless the snake is growing.
        body = list(self.body)
        return body if self.pending_growth > 0 else body[:-1]

    def move(self):
        self._prev_body = list(self.body)
        new_head = self.next_head()
        if self._turns:
            self.direction = self._turns.popleft()
        self.body.appendleft(new_head)
        if self.pending_growth > 0:
            self.pending_growth -= 1
        else:
            self.body.pop()

    def settle(self):
        """Stop interpolating: draw the snake exactly where it is."""
        self._prev_body = list(self.body)

    def grow(self, amount=1):
        self.pending_growth += amount

    def shrink(self, amount=1):
        for _ in range(amount):
            if len(self.body) > 1:
                self.body.pop()

    def occupies(self, position):
        return position in self.body

    def render_path(self, t):
        """Centre-line of the snake in grid units, `t` (0..1) of the way through the current move."""
        cur = [(x + 0.5, y + 0.5) for x, y in self.body]
        prev = [(x + 0.5, y + 0.5) for x, y in self._prev_body]
        (px, py), (cx, cy) = prev[0], cur[0]
        path = [(px + (cx - px) * t, py + (cy - py) * t)] + cur[1:]
        if len(prev) == len(cur):
            # Tail is sliding out of its old cell.
            (px, py), (cx, cy) = prev[-1], cur[-1]
            path.append((px + (cx - px) * t, py + (cy - py) * t))
        return path

    def to_dict(self):
        return {
            "body": list(self.body),
            "prev": self._prev_body,
            "dir": self.direction,
            "growth": self.pending_growth,
        }

    @classmethod
    def from_dict(cls, data):
        snake = cls.__new__(cls)
        snake.body = deque(tuple(cell) for cell in data["body"])
        snake._prev_body = [tuple(cell) for cell in data["prev"]]
        snake.direction = tuple(data["dir"])
        snake.pending_growth = data["growth"]
        snake._turns = deque()
        return snake


class Player:
    def __init__(self, player_id, name, snake, score=0, alive=True):
        self.id = player_id
        self.name = name
        self.snake = snake
        self.score = score
        self.alive = alive


class _EatContext:
    """What an apple's `on_eaten(game)` sees: the eater's snake and score, plus the shared speed."""

    def __init__(self, world, player):
        self._world = world
        self._player = player

    @property
    def snake(self):
        return self._player.snake

    @property
    def score(self):
        return self._player.score

    @score.setter
    def score(self, value):
        self._player.score = value

    @property
    def speed(self):
        return self._world.speed

    @speed.setter
    def speed(self, value):
        self._world.speed = value


class World:
    def __init__(self, players):
        """`players` is a list of (player_id, name)."""
        spawns = [SOLO_SPAWN] if len(players) == 1 else VERSUS_SPAWNS
        self.players = [
            Player(pid, name, Snake(*spawns[i % len(spawns)]))
            for i, (pid, name) in enumerate(players)
        ]
        self.speed = START_SPEED
        self.over = False
        self.apple = self.spawn_apple()

    @property
    def versus(self):
        return len(self.players) > 1

    @property
    def alive_players(self):
        return [p for p in self.players if p.alive]

    def player(self, player_id):
        return next((p for p in self.players if p.id == player_id), None)

    @property
    def winner(self):
        """The last snake standing in a finished versus game, or None for a draw."""
        alive = self.alive_players
        return alive[0] if self.versus and self.over and len(alive) == 1 else None

    def queue_direction(self, player_id, direction):
        player = self.player(player_id)
        if player and player.alive:
            player.snake.queue_direction(direction)

    def spawn_apple(self):
        free_cells = [
            (x, y)
            for x in range(GRID_WIDTH)
            for y in range(GRID_HEIGHT)
            if not any(p.snake.occupies((x, y)) for p in self.players if p.alive)
        ]
        if not free_cells:
            return None
        weights = [apple_type.spawn_weight for apple_type in APPLE_TYPES]
        apple_type = random.choices(APPLE_TYPES, weights=weights)[0]
        return apple_type(random.choice(free_cells))

    def step(self):
        """Advance every snake one cell. Returns a list of event dicts for effects."""
        alive = self.alive_players
        heads = {p.id: p.snake.next_head() for p in alive}
        blocked = set()
        for p in alive:
            blocked.update(p.snake.cells_blocking_next_step())

        events = []
        for p in alive:
            x, y = heads[p.id]
            out_of_bounds = not (0 <= x < GRID_WIDTH and 0 <= y < GRID_HEIGHT)
            head_on = any(heads[o.id] == (x, y) for o in alive if o is not p)
            if out_of_bounds or (x, y) in blocked or head_on:
                p.alive = False
                events.append({"type": "die", "player": p.id})

        for p in alive:
            if p.alive:
                p.snake.move()
            else:
                p.snake.settle()

        for p in alive:
            if p.alive and self.apple and p.snake.head == self.apple.position:
                apple = self.apple
                score_before = p.score
                apple.on_eaten(_EatContext(self, p))
                events.append({
                    "type": "eat",
                    "player": p.id,
                    "apple": type(apple).__name__,
                    "pos": apple.position,
                    "gained": p.score - score_before,
                })
                self.apple = self.spawn_apple()

        survivors_needed = 2 if self.versus else 1
        self.over = len(self.alive_players) < survivors_needed
        return events

    def to_dict(self):
        apple = self.apple
        return {
            "speed": self.speed,
            "over": self.over,
            "apple": {"type": type(apple).__name__, "pos": apple.position} if apple else None,
            "players": [
                {"id": p.id, "name": p.name, "score": p.score, "alive": p.alive, "snake": p.snake.to_dict()}
                for p in self.players
            ],
        }

    @classmethod
    def from_dict(cls, data, previous=None):
        """Rebuild a world from a snapshot, keeping `previous`'s apple object (and its animation) if unchanged."""
        world = cls.__new__(cls)
        world.speed = data["speed"]
        world.over = data["over"]
        world.players = [
            Player(p["id"], p["name"], Snake.from_dict(p["snake"]), p["score"], p["alive"])
            for p in data["players"]
        ]
        world.apple = None
        if data["apple"]:
            apple_type = APPLE_TYPES_BY_NAME[data["apple"]["type"]]
            pos = tuple(data["apple"]["pos"])
            old = previous.apple if previous else None
            world.apple = old if old and type(old) is apple_type and old.position == pos else apple_type(pos)
        return world
