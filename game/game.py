"""The Snake gameplay scene.

Game logic runs on a fixed GRID_WIDTH x GRID_HEIGHT grid at `speed` moves per
second. Rendering runs every frame and interpolates the snake between grid
cells, so movement looks smooth at any frame rate. The board is scaled to fit
the window and letterboxed with black bars to keep its shape.
"""

import math
import random
from collections import deque

import pygame

import graphics as gfx
from apples import APPLE_TYPES
from Quantum import QuantumState

GRID_WIDTH = 25
GRID_HEIGHT = 20
START_SPEED = 8  # moves per second

SNAKE_HEAD_COLOR = (130, 255, 170)
SNAKE_TAIL_COLOR = (20, 130, 110)
EYE_COLOR = (250, 250, 250)
PUPIL_COLOR = (15, 20, 30)
GHOST_FILL_COLOR = (0, 0, 0)
GHOST_OUTLINE_COLOR = (0, 255, 0)
GHOST_LOW_PHASE_COLOR = (0, 100, 0)  # Ry angle below pi/2
GHOST_HIGH_PHASE_COLOR = (40, 110, 255)  # Ry angle pi/2 and above

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
RESTART_KEYS = (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER)

MAX_QUEUED_TURNS = 2
SHAKE_TIME = 0.35
GAME_OVER_FADE_TIME = 0.6


class Snake:
    def __init__(self, start, quantum=None):
        self.body = deque([start])
        # Parallel to body: None for a concrete block, else the block's ghost id.
        self.block_types = deque([None])
        self.quantum = quantum
        self.direction = RIGHT
        self._turns = deque()
        self._pending_growth_types = [None, None]
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

    def would_collide_with_self(self, position):
        # The tail moves out of the way this step unless the snake is growing.
        body = list(self.body)
        if not self._pending_growth_types:
            body = body[:-1]
        return position in body

    def move(self):
        self._prev_body = list(self.body)
        new_head = self.next_head()
        if self._turns:
            self.direction = self._turns.popleft()
        self.body.appendleft(new_head)
        if self._pending_growth_types:
            self.block_types.append(self._pending_growth_types.pop(0))
        else:
            self.body.pop()

    def settle(self):
        """Stop interpolating: draw the snake exactly where it is."""
        self._prev_body = list(self.body)

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
            # Keep the interpolation source aligned so the tail doesn't jump.
            if index < len(self._prev_body):
                del self._prev_body[index]

    def ghost_at(self, position):
        return any(
            cell == position and block_type is not None
            for cell, block_type in zip(self.body, self.block_types)
        )

    def occupies(self, position):
        return position in self.body

    def render_path(self, t):
        """Centre-line of the snake in grid units, `t` (0..1) of the way through the current move."""
        cur = [(x + 0.5, y + 0.5) for x, y in self.body]
        prev = [(x + 0.5, y + 0.5) for x, y in self._prev_body]
        (px, py), (cx, cy) = prev[0], cur[0]
        path = [(gfx.lerp(px, cx, t), gfx.lerp(py, cy, t))] + cur[1:]
        if len(prev) == len(cur):
            # Tail is sliding out of its old cell.
            (px, py), (cx, cy) = prev[-1], cur[-1]
            path.append((gfx.lerp(px, cx, t), gfx.lerp(py, cy, t)))
        return path

    def draw(self, surface, to_px, cell, t, ghost_phases, dead=False):
        points = [to_px(p) for p in self.render_path(t)]
        n = len(points)
        # Resolving a ghost to 0 removes it from the middle of the body, leaving a gap.
        cells = list(self.body)
        joined = [
            k + 1 >= len(cells) or abs(cells[k][0] - cells[k + 1][0]) + abs(cells[k][1] - cells[k + 1][1]) == 1
            for k in range(n)
        ]

        def block_type(k):
            return self.block_types[min(k, len(self.block_types) - 1)]

        def ghost_color(k):
            phase = ghost_phases.get(block_type(k))
            if phase is None:
                return GHOST_FILL_COLOR
            return GHOST_LOW_PHASE_COLOR if phase < math.pi / 2 else GHOST_HIGH_PHASE_COLOR

        def body_color(k):
            if block_type(k) is not None:
                return ghost_color(k)
            return gfx.lerp_color(SNAKE_HEAD_COLOR, SNAKE_TAIL_COLOR, min(1.0, k / max(8, n - 1)))

        def outline(k):
            if block_type(k) is not None and ghost_phases.get(block_type(k)) is None:
                return GHOST_OUTLINE_COLOR
            return gfx.scale_color(body_color(k), 0.35)

        def highlight(k):
            return gfx.lerp_color(body_color(k), gfx.WHITE, 0.35)

        _draw_tube(surface, points, cell * 0.43, outline, joined)
        _draw_tube(surface, points, cell * 0.36, body_color, joined)
        off = -cell * 0.09
        _draw_tube(surface, [(x + off, y + off) for x, y in points], cell * 0.1, highlight, joined)

        self._draw_head(surface, points[0], cell, dead)

    def _draw_head(self, surface, center, cell, dead):
        hx, hy = center
        gfx.aa_circle(surface, gfx.scale_color(SNAKE_HEAD_COLOR, 0.35), (hx, hy), cell * 0.47)
        gfx.aa_circle(surface, SNAKE_HEAD_COLOR, (hx, hy), cell * 0.4)
        dx, dy = self.direction
        px, py = -dy, dx  # perpendicular
        for side in (-1, 1):
            ex = hx + dx * cell * 0.12 + px * side * cell * 0.18
            ey = hy + dy * cell * 0.12 + py * side * cell * 0.18
            gfx.aa_circle(surface, EYE_COLOR, (ex, ey), cell * 0.12)
            if dead:
                s = cell * 0.07
                w = max(1, round(cell * 0.04))
                pygame.draw.line(surface, PUPIL_COLOR, (ex - s, ey - s), (ex + s, ey + s), w)
                pygame.draw.line(surface, PUPIL_COLOR, (ex - s, ey + s), (ex + s, ey - s), w)
            else:
                gfx.aa_circle(surface, PUPIL_COLOR, (ex + dx * cell * 0.04, ey + dy * cell * 0.04), cell * 0.065)


def _draw_tube(surface, points, radius, color_for, joined):
    """Thick rounded line through axis-aligned points, coloured per segment (tail drawn first).

    `joined[k]` says whether point k connects to point k + 1."""
    r = round(radius)
    if r < 1:
        return
    points = [(round(x), round(y)) for x, y in points]
    for k in range(len(points) - 1, -1, -1):
        x, y = points[k]
        color = color_for(k)
        if k + 1 < len(points) and joined[k]:
            x2, y2 = points[k + 1]
            # Match the circle's 2r+1 pixel diameter so joints don't bulge.
            if y == y2:
                pygame.draw.rect(surface, color, (min(x, x2), y - r, abs(x - x2), 2 * r + 1))
            elif x == x2:
                pygame.draw.rect(surface, color, (x - r, min(y, y2), 2 * r + 1, abs(y - y2)))
            else:
                pygame.draw.line(surface, color, (x, y), (x2, y2), 2 * r + 1)
        gfx.aa_circle(surface, color, (x, y), r)


class Particle:
    def __init__(self, pos, color):
        angle = random.uniform(0, math.tau)
        speed = random.uniform(2.0, 7.0)
        self.x, self.y = pos
        self.vx, self.vy = math.cos(angle) * speed, math.sin(angle) * speed
        self.color = color
        self.life = self.max_life = random.uniform(0.35, 0.7)
        self.size = random.uniform(0.07, 0.15)

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.vx *= 0.9 ** (dt * 60)
        self.vy *= 0.9 ** (dt * 60)
        self.life -= dt

    def draw(self, surface, to_px, cell):
        k = max(0.0, self.life / self.max_life)
        gfx.aa_circle(surface, gfx.lerp_color(gfx.FIELD_A, self.color, k), to_px((self.x, self.y)), self.size * cell * (0.4 + 0.6 * k))


class ScorePopup:
    LIFETIME = 0.8

    def __init__(self, pos, text, color):
        self.x, self.y = pos
        self.text = text
        self.color = color
        self.age = 0.0

    def update(self, dt):
        self.age += dt
        self.y -= dt * 1.2

    def draw(self, surface, to_px, cell):
        k = self.age / self.LIFETIME
        alpha = round(255 * (1 - k * k))
        gfx.draw_text(surface, self.text, cell * 0.8, self.color, to_px((self.x, self.y)), anchor="center", bold=True, alpha=alpha)


class Game:
    def __init__(self, app):
        self.app = app
        self.reset()

    def reset(self):
        self.quantum = QuantumState()
        self.snake = Snake((GRID_WIDTH // 4, GRID_HEIGHT // 2), self.quantum)
        self.speed = START_SPEED
        self.game_over = False
        self.game_over_time = 0.0
        self.step_timer = 0.0
        self.shake = 0.0
        self.particles = []
        self.popups = []
        self.eaten_apple = None
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

    # --- Scene interface -------------------------------------------------

    def handle_event(self, event):
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_ESCAPE:
            self.app.show_main_menu()
        elif self.game_over:
            if event.key in RESTART_KEYS:
                self.reset()
        elif event.key in KEY_DIRECTIONS:
            self.snake.queue_direction(KEY_DIRECTIONS[event.key])

    def update(self, dt):
        if self.apple:
            self.apple.update(dt)
        for effect_list in (self.particles, self.popups):
            for effect in effect_list:
                effect.update(dt)
        self.particles = [p for p in self.particles if p.life > 0]
        self.popups = [p for p in self.popups if p.age < ScorePopup.LIFETIME]
        self.shake = max(0.0, self.shake - dt)

        if self.game_over:
            self.game_over_time += dt
            return

        self.step_timer += dt
        interval = 1 / self.speed
        while self.step_timer >= interval and not self.game_over:
            self.step_timer -= interval
            self.eaten_apple = None
            self.step()
            interval = 1 / self.speed

    def step(self):
        x, y = self.snake.next_head()
        if self.snake.ghost_at((x, y)):
            self.collapse_ghosts()
        out_of_bounds = not (0 <= x < GRID_WIDTH and 0 <= y < GRID_HEIGHT)
        if out_of_bounds or self.snake.would_collide_with_self((x, y)):
            self.game_over = True
            self.snake.settle()
            self.shake = SHAKE_TIME
            return
        self.snake.move()
        if self.apple and self.snake.head == self.apple.position:
            self.eat(self.apple)
            self.apple = self.spawn_apple()

    def collapse_ghosts(self):
        for ghost_id, outcome in self.quantum.measure().items():
            self.snake.resolve_ghost(ghost_id, outcome)

    def eat(self, apple):
        score_before = self.score
        apple.on_eaten(self)
        center = (apple.position[0] + 0.5, apple.position[1] + 0.5)
        self.particles.extend(Particle(center, apple.color) for _ in range(22))
        gained = self.score - score_before
        if gained:
            self.popups.append(ScorePopup((center[0], center[1] - 0.6), f"{gained:+d}", apple.color))
        # Keep drawing it, shrinking, until the head visually reaches it.
        self.eaten_apple = apple

    # --- Drawing ---------------------------------------------------------

    @staticmethod
    def layout(screen_size):
        w, h = screen_size
        cell = max(2, min(w // GRID_WIDTH, h // GRID_HEIGHT))
        field = pygame.Rect(0, 0, cell * GRID_WIDTH, cell * GRID_HEIGHT)
        field.center = (w // 2, h // 2)
        return cell, field

    def draw(self, surface):
        surface.fill(gfx.BLACK)
        cell, field = self.layout(surface.get_size())
        if self.shake > 0:
            amount = cell * 0.3 * (self.shake / SHAKE_TIME)
            field = field.move(round(random.uniform(-amount, amount)), round(random.uniform(-amount, amount)))

        def to_px(p):
            return field.x + p[0] * cell, field.y + p[1] * cell

        t = 1.0 if self.game_over else min(1.0, self.step_timer * self.speed)

        surface.blit(gfx.playfield_background(cell, GRID_WIDTH, GRID_HEIGHT), field.topleft)
        surface.set_clip(field)
        if self.apple:
            self.apple.draw(surface, to_px((self.apple.position[0] + 0.5, self.apple.position[1] + 0.5)), cell)
        if self.eaten_apple and t < 1:
            ex, ey = self.eaten_apple.position
            self.eaten_apple.draw(surface, to_px((ex + 0.5, ey + 0.5)), cell, scale=1 - t)
        self.snake.draw(surface, to_px, cell, t, self.quantum.ghost_phases, dead=self.game_over)
        for effect in self.particles + self.popups:
            effect.draw(surface, to_px, cell)
        surface.set_clip(None)

        pad = cell * 0.5
        gfx.draw_text(surface, "SCORE", cell * 0.55, gfx.TEXT_DIM, (field.x + pad, field.y + pad * 0.8))
        gfx.draw_text(surface, str(self.score), cell * 1.1, gfx.TEXT, (field.x + pad, field.y + pad * 0.8 + cell * 0.55), bold=True)

        if self.game_over:
            self.draw_game_over(surface, field, cell)

    def draw_game_over(self, surface, field, cell):
        k = min(1.0, self.game_over_time / GAME_OVER_FADE_TIME)
        overlay = pygame.Surface(field.size, pygame.SRCALPHA)
        overlay.fill((0, 0, 0, round(160 * k)))
        surface.blit(overlay, field.topleft)
        if k < 0.3:
            return
        cx, cy = field.center
        gfx.draw_glow_text(surface, "GAME OVER", cell * 2.4, gfx.TEXT, (220, 60, 80), (cx, cy - cell * 1.6))
        gfx.draw_text(surface, f"Score  {self.score}", cell * 1.1, gfx.ACCENT, (cx, cy + cell * 0.4), anchor="center", bold=True)
        pulse = round(170 + 85 * math.sin(self.game_over_time * 4))
        gfx.draw_text(surface, "Space to play again   ·   Esc for menu", cell * 0.7, gfx.TEXT_DIM, (cx, cy + cell * 2.2), anchor="center", alpha=pulse)
