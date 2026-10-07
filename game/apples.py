"""Apple types for Snake.

To add your own apple:
    1. Subclass Apple.
    2. Set `color` (and optionally `spawn_weight`, `glow_strength`).
    3. Implement `on_eaten(self, game)` to do whatever you like to the game.
    4. Optionally override `draw_details(...)` to decorate it.
    5. Add the class to APPLE_TYPES at the bottom of this file.

`game` exposes:
    game.snake.grow(n)   - add n segments to the snake that ate it
    game.snake.shrink(n) - remove n segments (never below 1)
    game.score           - that snake's player's score, read/write
    game.speed           - moves per second (shared by all snakes), read/write
"""

import math
from abc import ABC, abstractmethod

import graphics as gfx

STEM_COLOR = (110, 70, 40)
LEAF_COLOR = (80, 200, 90)
POP_IN_TIME = 0.3


class Apple(ABC):
    color = (255, 255, 255)
    spawn_weight = 1  # Higher = more likely to spawn relative to other types
    glow_strength = 0.35

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
    spawn_weight = 10

    def on_eaten(self, game):
        game.snake.grow(1)
        game.score += 1


class GoldenApple(Apple):
    color = (255, 200, 40)
    spawn_weight = 2
    glow_strength = 0.6

    def on_eaten(self, game):
        game.snake.grow(3)
        game.score += 5

    def draw_details(self, surface, cx, cy, r, t):
        # Orbiting twinkles.
        for i in range(3):
            a = t * 1.5 + i * math.tau / 3
            twinkle = 0.5 + 0.5 * math.sin(t * 6 + i * 2)
            x, y = cx + math.cos(a) * r * 1.5, cy + math.sin(a) * r * 1.5
            size = r * 0.35 * twinkle
            if size < 1:
                continue
            color = gfx.lerp_color((255, 220, 120), gfx.WHITE, twinkle)
            gfx.aa_polygon(surface, color, [
                (x, y - size), (x + size * 0.25, y - size * 0.25), (x + size, y), (x + size * 0.25, y + size * 0.25),
                (x, y + size), (x - size * 0.25, y + size * 0.25), (x - size, y), (x - size * 0.25, y - size * 0.25),
            ])


class SpeedApple(Apple):
    color = (60, 140, 255)
    spawn_weight = 2
    glow_strength = 0.5

    def on_eaten(self, game):
        game.snake.grow(1)
        game.score += 2
        game.speed += 2

    def draw_details(self, surface, cx, cy, r, t):
        bolt = [(0.15, -0.65), (-0.35, 0.08), (-0.02, 0.08), (-0.15, 0.65), (0.35, -0.1), (0.02, -0.1)]
        gfx.aa_polygon(surface, (255, 245, 170), [(cx + x * r, cy + y * r) for x, y in bolt])


APPLE_TYPES = [RedApple, GoldenApple, SpeedApple]
APPLE_TYPES_BY_NAME = {apple_type.__name__: apple_type for apple_type in APPLE_TYPES}
