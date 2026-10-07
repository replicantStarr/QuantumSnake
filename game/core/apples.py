"""Apple types for Snake.

To add your own apple:
    1. Subclass Apple.
    2. Set `color` (and optionally `spawn_weight`, `glow_strength`, `rim_color`).
    3. Implement `on_eaten(self, game)` to do whatever you like to the game.
    4. Optionally override `draw_details(...)` to decorate it.
    5. Add the class to APPLE_TYPES at the bottom of this file.

`game` exposes:
    game.snake.grow(n)   - add n segments to the snake that ate it
    game.snake.shrink(n) - remove n segments (never below 1)
    game.quantum.add_ghost() - add a ghost-block qubit to the circuit
    game.quantum.apply_green_apple() - apply a random Y rotation to all qubits
    game.quantum.measure() - measure and resolve all ghost-block qubits
    game.kill()          - kill the snake that ate it
    game.score           - number of concrete snake blocks
    game.speed           - moves per second, read/write
"""

import math
from abc import ABC, abstractmethod

from core.quantum import purple_pair_measure
from visuals import graphics as gfx

STEM_COLOR = (110, 70, 40)
LEAF_COLOR = (80, 200, 90)
POP_IN_TIME = 0.3

PURPLE_REWARD = 20  # solid blocks gained from the lucky purple twin
PURPLE_REVEALED_STEPS = 80  # how long the second twin stays once the pair is measured


class Apple(ABC):
    color = (255, 255, 255)
    spawn_weight = 1  # Higher = more likely to spawn relative to other types
    glow_strength = 0.35
    rim_color = None  # optional outline drawn just outside the apple

    def __init__(self, position):
        self.position = position
        self.age = 0.0

    @abstractmethod
    def on_eaten(self, game):
        """Called once when the snake's head lands on this apple."""

    def update(self, dt):
        self.age += dt

    def draw(self, surface, center, cell, scale=1.0):
        """Draw centred on `center` (pixels), sized for a grid cell of `cell` pixels."""
        t = self.age
        pop = gfx.ease_out_back(min(1.0, t / POP_IN_TIME))
        s = scale * pop * (1 + 0.04 * math.sin(t * 4))
        if s <= 0.01:
            return
        cx = center[0]
        cy = center[1] + math.sin(t * 3) * cell * 0.04
        r = cell * 0.36 * s

        gfx.blit_glow(surface, (cx, cy), cell * 1.1 * s, gfx.scale_color(self.color, self.glow_strength))
        gfx.aa_circle(surface, (0, 0, 0), (cx, cy + r * 0.25), r * 0.95)  # drop shadow
        if self.rim_color:
            gfx.aa_circle(surface, self.rim_color, (cx, cy), r + max(1, r * 0.08))

        # Sphere shading: concentric discs drifting towards the light (top-left).
        dark = gfx.scale_color(self.color, 0.55)
        light = gfx.lerp_color(self.color, gfx.WHITE, 0.25)
        steps = 6
        for i in range(steps):
            k = i / (steps - 1)
            offset = r * 0.28 * k
            color = gfx.lerp_color(dark, self.color, min(1, k * 1.6)) if k < 0.6 else gfx.lerp_color(self.color, light, (k - 0.6) / 0.4)
            gfx.aa_circle(surface, color, (cx - offset, cy - offset), r * (1 - 0.6 * k))
        gfx.aa_circle(surface, (255, 255, 255), (cx - r * 0.38, cy - r * 0.42), r * 0.14)

        # Stem and leaf.
        stem_top = (cx + r * 0.12, cy - r * 1.3)
        gfx.aa_polygon(surface, STEM_COLOR, [
            (cx - r * 0.07, cy - r * 0.8), (cx + r * 0.07, cy - r * 0.8),
            (stem_top[0] + r * 0.06, stem_top[1]), (stem_top[0] - r * 0.06, stem_top[1]),
        ])
        self._draw_leaf(surface, (cx + r * 0.42, cy - r * 1.05), r * 0.5, -0.5)

        self.draw_details(surface, cx, cy, r, t)

    def draw_details(self, surface, cx, cy, r, t):
        """Hook for extra decoration drawn on top of the apple."""

    @staticmethod
    def _draw_leaf(surface, center, length, angle):
        ca, sa = math.cos(angle), math.sin(angle)
        points = []
        for i in range(16):
            a = i / 16 * math.tau
            x, y = math.cos(a) * length, math.sin(a) * length * 0.42
            points.append((center[0] + x * ca - y * sa, center[1] + x * sa + y * ca))
        gfx.aa_polygon(surface, LEAF_COLOR, points)


class RedApple(Apple):
    color = (230, 50, 60)
    spawn_weight = 14

    def on_eaten(self, game):
        ghost_id = game.quantum.add_ghost()
        game.snake.grow(1, ghost_id=ghost_id)


class GreenApple(Apple):
    color = (50, 180, 70)
    spawn_weight = 4

    def on_eaten(self, game):
        game.quantum.apply_green_apple()


class BlackApple(Apple):
    color = (10, 10, 10)
    spawn_weight = 2
    glow_strength = 0  # black has no glow; the rim makes it visible instead
    rim_color = (220, 220, 220)

    def on_eaten(self, game):
        game.collapse_ghosts()


class PurpleApple(Apple):
    """One half of an entangled pair. Neither twin's fate (+20 or death) exists until one is eaten.

    The World spawns these two at a time with `entangled_pair()`; they are not in APPLE_TYPES.
    """

    UNMEASURED_COLOR = (170, 80, 240)
    REWARD_COLOR = (250, 200, 60)
    DEADLY_COLOR = (70, 15, 35)
    DEADLY_MARK_COLOR = (235, 60, 75)

    def __init__(self, position, qubit=0, outcome=None):
        super().__init__(position)
        self.qubit = qubit  # which qubit of the pair's circuit this apple is
        self.outcome = outcome  # None until measured, then 1 (+20 points) or 0 (deadly)
        self.twin = None
        self.steps_left = PURPLE_REVEALED_STEPS  # only counts down once measured

    @classmethod
    def entangled_pair(cls, first_position, second_position):
        first, second = cls(first_position, qubit=0), cls(second_position, qubit=1)
        first.twin, second.twin = second, first
        return [first, second]

    @property
    def color(self):
        return {None: self.UNMEASURED_COLOR, 1: self.REWARD_COLOR, 0: self.DEADLY_COLOR}[self.outcome]

    @property
    def rim_color(self):
        return self.DEADLY_MARK_COLOR if self.outcome == 0 else None

    def on_eaten(self, game):
        if self.outcome is None:
            outcomes = purple_pair_measure()
            self.outcome = outcomes[self.qubit]
            if self.twin:
                self.twin.outcome = outcomes[self.twin.qubit]
        if self.outcome:
            game.snake.grow(PURPLE_REWARD)
        else:
            game.kill()

    def draw_details(self, surface, cx, cy, r, t):
        if self.outcome != 0:
            return
        # A cross marks the deadly twin.
        half, width = r * 0.42, r * 0.11
        for sy in (1, -1):
            x0, y0, x1, y1 = cx - half, cy - half * sy, cx + half, cy + half * sy
            length = math.hypot(x1 - x0, y1 - y0)
            nx, ny = (y0 - y1) / length * width, (x1 - x0) / length * width
            gfx.aa_polygon(surface, self.DEADLY_MARK_COLOR, [
                (x0 + nx, y0 + ny), (x1 + nx, y1 + ny), (x1 - nx, y1 - ny), (x0 - nx, y0 - ny),
            ])


APPLE_TYPES = [RedApple, GreenApple, BlackApple]
APPLE_TYPES_BY_NAME = {apple_type.__name__: apple_type for apple_type in APPLE_TYPES + [PurpleApple]}