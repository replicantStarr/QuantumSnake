import math
import random
from collections import deque

import pygame

from apples import APPLE_TYPES
from Quantum import QuantumState

CELL_SIZE = 24
GRID_WIDTH = 25
GRID_HEIGHT = 20
START_SPEED = 8  # moves per second

BG_COLOR = (173, 216, 230)
SNAKE_COLOR = (60, 200, 90)
HEAD_COLOR = (120, 240, 140)
GHOST_OUTLINE_COLOR = (0, 255, 0)
TEXT_COLOR = (30, 40, 50)

UP = (0, -1)
DOWN = (0, 1)
LEFT = (-1, 0)
RIGHT = (1, 0)

# Arrow keys, WASD and numpad (8/4/6/2) all steer the snake.
KEY_DIRECTIONS = {
    pygame.K_UP: UP, pygame.K_w: UP, pygame.K_KP8: UP,
    pygame.K_DOWN: DOWN, pygame.K_s: DOWN, pygame.K_KP2: DOWN,
    pygame.K_LEFT: LEFT, pygame.K_a: LEFT, pygame.K_KP4: LEFT,
    pygame.K_RIGHT: RIGHT, pygame.K_d: RIGHT, pygame.K_KP6: RIGHT,
}


class Snake:
    def __init__(self, start, quantum=None):
        self.body = deque([start])
        self.block_types = deque([None])
        self.quantum = quantum
        self.direction = RIGHT
        self._next_direction = RIGHT
        self._pending_growth_types = [None, None]

    @property
    def head(self):
        return self.body[0]

    def set_direction(self, direction):
        # Compare against the direction actually moved last, so two quick
        # key presses can't reverse the snake into itself.
        dx, dy = direction
        if (dx, dy) != (-self.direction[0], -self.direction[1]):
            self._next_direction = direction

    def move(self):
        self.direction = self._next_direction
        x, y = self.head
        self.body.appendleft((x + self.direction[0], y + self.direction[1]))
        is_growing = bool(self._pending_growth_types)
        if is_growing:
            self.block_types.append(self._pending_growth_types.pop(0))
        else:
            self.body.pop()

    def grow(self, amount=1, ghost_id=None):
        self._pending_growth_types.extend([ghost_id] * amount)

    def shrink(self, amount=1):
        for _ in range(amount):
            if len(self.body) > 1:
                self.body.pop()
                self._remove_block_type(self.block_types.pop())

    def _remove_block_type(self, block_type):
        if block_type is not None and self.quantum is not None:
            self.quantum.remove_ghost(block_type)

    def resolve_ghost(self, ghost_id, outcome):
        if ghost_id in self._pending_growth_types:
            self._pending_growth_types.remove(ghost_id)
        try:
            index = self.block_types.index(ghost_id)
        except ValueError:
            return
        if outcome:
            self.block_types[index] = None
        else:
            del self.block_types[index]
            del self.body[index]

    def hits_itself(self):
        return self.head in list(self.body)[1:]

    def occupies(self, position):
        return position in self.body

    def draw(self, surface, cell_size, ghost_phases):
        for i, (x, y) in enumerate(self.body):
            rect = pygame.Rect(x * cell_size, y * cell_size, cell_size, cell_size)
            block_type = self.block_types[i]
            block_rect = rect.inflate(-2, -2)
            if block_type is not None:
                phase = ghost_phases.get(block_type)
                if phase is None:
                    pygame.draw.rect(surface, (0, 0, 0), block_rect)
                    pygame.draw.rect(surface, GHOST_OUTLINE_COLOR, block_rect, 2)
                else:
                    color = (0, 100, 0) if phase < math.pi / 2 else (40, 110, 255)
                    pygame.draw.rect(surface, color, block_rect)
            else:
                color = HEAD_COLOR if i == 0 else SNAKE_COLOR
                pygame.draw.rect(surface, color, block_rect)


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((GRID_WIDTH * CELL_SIZE, GRID_HEIGHT * CELL_SIZE))
        pygame.display.set_caption("Snake")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont(None, 28)
        self.reset()

    def reset(self):
        self.quantum = QuantumState()
        self.snake = Snake((GRID_WIDTH // 4, GRID_HEIGHT // 2), self.quantum)
        self.speed = START_SPEED
        self.game_over = False
        self.apple = self.spawn_apple()

    @property
    def score(self):
        return sum(block_type is None for block_type in self.snake.block_types)

    def spawn_apple(self):
        free_cells = [
            (x, y)
            for x in range(GRID_WIDTH)
            for y in range(GRID_HEIGHT)
            if not self.snake.occupies((x, y))
        ]
        if not free_cells:
            return None
        weights = [apple_type.spawn_weight for apple_type in APPLE_TYPES]
        apple_type = random.choices(APPLE_TYPES, weights=weights)[0]
        return apple_type(random.choice(free_cells))

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                if self.game_over and event.key in (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER):
                    self.reset()
                elif event.key in KEY_DIRECTIONS:
                    self.snake.set_direction(KEY_DIRECTIONS[event.key])
        return True

    def update(self):
        if self.game_over:
            return
        dx, dy = self.snake._next_direction
        next_head = (self.snake.head[0] + dx, self.snake.head[1] + dy)
        if any(
            position == next_head and block_type is not None
            for position, block_type in zip(self.snake.body, self.snake.block_types)
        ):
            self.collapse_ghosts()

        self.snake.move()
        x, y = self.snake.head
        out_of_bounds = not (0 <= x < GRID_WIDTH and 0 <= y < GRID_HEIGHT)
        if out_of_bounds or self.snake.hits_itself():
            self.game_over = True
            return
        if self.apple and self.snake.head == self.apple.position:
            self.apple.on_eaten(self)
            self.apple = self.spawn_apple()

    def collapse_ghosts(self):
        for ghost_id, outcome in self.quantum.measure().items():
            self.snake.resolve_ghost(ghost_id, outcome)

    def draw(self):
        self.screen.fill(BG_COLOR)
        if self.apple:
            self.apple.draw(self.screen, CELL_SIZE)
        self.snake.draw(self.screen, CELL_SIZE, self.quantum.ghost_phases)
        self.draw_text(f"Score: {self.score}", (8, 8))
        if self.game_over:
            self.draw_text("Game Over - press Space to restart", center=True)
        pygame.display.flip()

    def draw_text(self, text, pos=(0, 0), center=False):
        image = self.font.render(text, True, TEXT_COLOR)
        if center:
            pos = image.get_rect(center=self.screen.get_rect().center).topleft
        self.screen.blit(image, pos)

    def run(self):
        running = True
        while running:
            running = self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(self.speed)
        pygame.quit()


if __name__ == "__main__":
    Game().run()
