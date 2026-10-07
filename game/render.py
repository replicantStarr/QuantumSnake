"""Drawing for the playfield: snakes, particles and floating score text."""

import math
import random

import pygame

import graphics as gfx

# (head colour, tail colour) for each player, in join order.
SNAKE_PALETTES = [
    ((130, 255, 170), (20, 130, 110)),
    ((255, 190, 100), (170, 60, 50)),
]
EYE_COLOR = (250, 250, 250)
PUPIL_COLOR = (15, 20, 30)


def draw_snake(surface, snake, to_px, cell, t, palette, dead=False):
    head_color, tail_color = palette
    if dead:
        head_color, tail_color = gfx.scale_color(head_color, 0.55), gfx.scale_color(tail_color, 0.55)
    points = [to_px(p) for p in snake.render_path(t)]
    n = len(points)

    def body_color(k):
        return gfx.lerp_color(head_color, tail_color, min(1.0, k / max(8, n - 1)))

    def outline(k):
        return gfx.scale_color(body_color(k), 0.35)

    def highlight(k):
        return gfx.lerp_color(body_color(k), gfx.WHITE, 0.35)

    _draw_tube(surface, points, cell * 0.43, outline)
    _draw_tube(surface, points, cell * 0.36, body_color)
    off = -cell * 0.09
    _draw_tube(surface, [(x + off, y + off) for x, y in points], cell * 0.1, highlight)
    _draw_head(surface, points[0], snake.direction, cell, head_color, dead)


def _draw_head(surface, center, direction, cell, color, dead):
    hx, hy = center
    gfx.aa_circle(surface, gfx.scale_color(color, 0.35), (hx, hy), cell * 0.47)
    gfx.aa_circle(surface, color, (hx, hy), cell * 0.4)
    dx, dy = direction
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


def _draw_tube(surface, points, radius, color_for):
    """Thick rounded line through axis-aligned points, coloured per segment (tail drawn first)."""
    r = round(radius)
    if r < 1:
        return
    points = [(round(x), round(y)) for x, y in points]
    for k in range(len(points) - 1, -1, -1):
        x, y = points[k]
        color = color_for(k)
        if k + 1 < len(points):
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

    @property
    def done(self):
        return self.life <= 0

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

    @property
    def done(self):
        return self.age >= self.LIFETIME

    def update(self, dt):
        self.age += dt
        self.y -= dt * 1.2

    def draw(self, surface, to_px, cell):
        k = self.age / self.LIFETIME
        alpha = round(255 * (1 - k * k))
        gfx.draw_text(surface, self.text, cell * 0.8, self.color, to_px((self.x, self.y)), anchor="center", bold=True, alpha=alpha)
