"""Shared drawing helpers and colour palette.

Everything is drawn at the window's native resolution with anti-aliased
primitives, so the game stays sharp at any size. Expensive surfaces
(gradients, glows, rounded panels) are cached by size and colour.
"""

import functools
import math

import pygame
import pygame.gfxdraw

# Palette
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
TEXT = (235, 240, 245)
TEXT_DIM = (140, 150, 165)
ACCENT = (90, 240, 160)
ACCENT_DARK = (30, 120, 90)

MENU_TOP = (16, 22, 38)
MENU_BOTTOM = (5, 7, 14)

FIELD_A = (18, 24, 36)
FIELD_B = (21, 28, 42)
FIELD_BORDER = (40, 60, 80)

PANEL_FILL = (24, 32, 48, 220)
PANEL_FILL_HOVER = (30, 62, 58, 235)
PANEL_BORDER = (55, 70, 95)

FONT_NAMES = "bahnschrift,segoeui,helveticaneue,arial"


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_color(c1, c2, t):
    return tuple(round(lerp(a, b, t)) for a, b in zip(c1, c2))


def scale_color(color, factor):
    return tuple(max(0, min(255, round(c * factor))) for c in color[:3])


def ease_out_back(t):
    c = 1.70158
    return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2


@functools.lru_cache(maxsize=64)
def font(size, bold=False):
    return pygame.font.SysFont(FONT_NAMES, max(8, int(size)), bold=bold)


def draw_text(surface, text, size, color, pos, anchor="topleft", bold=False, shadow=True, alpha=255):
    f = font(size, bold)
    image = f.render(text, True, color)
    rect = image.get_rect(**{anchor: (round(pos[0]), round(pos[1]))})
    if shadow:
        shadow_image = f.render(text, True, BLACK)
        shadow_image.set_alpha(round(alpha * 0.6))
        offset = max(1, round(size / 18))
        surface.blit(shadow_image, rect.move(offset, offset))
    if alpha < 255:
        image.set_alpha(alpha)
    surface.blit(image, rect)
    return rect


def aa_circle(surface, color, center, radius):
    r = round(radius)
    if r < 1:
        return
    x, y = round(center[0]), round(center[1])
    pygame.gfxdraw.aacircle(surface, x, y, r, color)
    pygame.gfxdraw.filled_circle(surface, x, y, r, color)


def aa_polygon(surface, color, points):
    points = [(round(x), round(y)) for x, y in points]
    pygame.gfxdraw.aapolygon(surface, points, color)
    pygame.gfxdraw.filled_polygon(surface, points, color)


@functools.lru_cache(maxsize=8)
def vertical_gradient(size, top, bottom):
    w, h = size
    surf = pygame.Surface(size)
    for y in range(h):
        pygame.draw.line(surf, lerp_color(top, bottom, y / max(1, h - 1)), (0, y), (w, y))
    return surf


@functools.lru_cache(maxsize=128)
def _glow_surface(radius, color):
    surf = pygame.Surface((radius * 2, radius * 2))
    steps = max(6, radius // 2)
    for i in range(steps):
        k = i / steps
        intensity = k * k
        pygame.draw.circle(surf, scale_color(color, intensity), (radius, radius), max(1, round(radius * (1 - k))))
    return surf


def blit_glow(surface, center, radius, color):
    """Additive soft glow; `color` sets both hue and brightness."""
    radius = max(2, round(radius))
    glow = _glow_surface(radius, tuple(color[:3]))
    surface.blit(glow, (round(center[0]) - radius, round(center[1]) - radius), special_flags=pygame.BLEND_RGB_ADD)


@functools.lru_cache(maxsize=256)
def rounded_rect(size, radius, fill, border=None, border_width=0):
    """Anti-aliased rounded rectangle, supersampled then scaled down."""
    ss = 3
    w, h = size
    big = pygame.Surface((w * ss, h * ss), pygame.SRCALPHA)
    rect = big.get_rect()
    if border and border_width:
        pygame.draw.rect(big, border, rect, border_radius=radius * ss)
        rect = rect.inflate(-2 * border_width * ss, -2 * border_width * ss)
        radius = max(0, radius - border_width)
    pygame.draw.rect(big, fill, rect, border_radius=radius * ss)
    return pygame.transform.smoothscale(big, size)


@functools.lru_cache(maxsize=32)
def glow_text(text, size, color, glow_color):
    """Returns (glow, image, pad): blit glow additively at pos - pad, then image at pos."""
    f = font(size, True)
    image = f.render(text, True, color)
    pad = max(4, size // 2)
    w, h = image.get_size()
    canvas = pygame.Surface((w + pad * 2, h + pad * 2))
    canvas.blit(f.render(text, True, glow_color), (pad, pad))
    small = pygame.transform.smoothscale(canvas, (max(1, canvas.get_width() // 10), max(1, canvas.get_height() // 10)))
    glow = pygame.transform.smoothscale(small, canvas.get_size())
    return glow, image, pad


def draw_glow_text(surface, text, size, color, glow_color, center):
    glow, image, pad = glow_text(text, max(8, round(size)), color, glow_color)
    rect = image.get_rect(center=(round(center[0]), round(center[1])))
    surface.blit(glow, (rect.x - pad, rect.y - pad), special_flags=pygame.BLEND_RGB_ADD)
    surface.blit(glow, (rect.x - pad, rect.y - pad), special_flags=pygame.BLEND_RGB_ADD)
    surface.blit(image, rect)
    return rect


@functools.lru_cache(maxsize=4)
def playfield_background(cell, grid_w, grid_h):
    w, h = cell * grid_w, cell * grid_h
    surf = pygame.Surface((w, h))
    for gx in range(grid_w):
        for gy in range(grid_h):
            color = FIELD_A if (gx + gy) % 2 == 0 else FIELD_B
            surf.fill(color, (gx * cell, gy * cell, cell, cell))

    # Darken the edges a little so the eye is drawn to the middle.
    n = 48
    vignette = pygame.Surface((n, n), pygame.SRCALPHA)
    for x in range(n):
        for y in range(n):
            dx, dy = (x + 0.5) / n * 2 - 1, (y + 0.5) / n * 2 - 1
            d = min(1.0, math.hypot(dx, dy) / math.sqrt(2))
            vignette.set_at((x, y), (0, 0, 0, round(150 * d ** 2.2)))
    surf.blit(pygame.transform.smoothscale(vignette, (w, h)), (0, 0))

    pygame.draw.rect(surf, FIELD_BORDER, surf.get_rect(), width=max(1, cell // 12))
    return surf
