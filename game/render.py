"""Drawing for the playfield: snakes, particles and floating score text."""

import math
import random
from fractions import Fraction

import pygame

import graphics as gfx

# (head colour, tail colour) for each player, in join order.
SNAKE_PALETTES = [
    ((130, 255, 170), (20, 130, 110)),
    ((255, 190, 100), (170, 60, 50)),
]
EYE_COLOR = (250, 250, 250)
PUPIL_COLOR = (15, 20, 30)
GHOST_FILL_COLOR = (0, 0, 0)
GHOST_OUTLINE_COLOR = (0, 255, 0)
GHOST_LOW_PHASE_COLOR = (0, 100, 0)  # Ry angle below pi/2
GHOST_HIGH_PHASE_COLOR = (40, 110, 255)  # Ry angle pi/2 and above
H_GATE_COLOR = (110, 70, 170)
WIRE_COLOR = (90, 105, 130)
SMALL_GATE_CELL = 24  # below this cell size (px), gate boxes are too small for an angle label


def ghost_colors(phase):
    """(fill, outline) for a ghost block whose latest Ry angle is `phase` (None if not yet rotated)."""
    if phase is None:
        return GHOST_FILL_COLOR, GHOST_OUTLINE_COLOR
    fill = GHOST_LOW_PHASE_COLOR if phase < math.pi / 2 else GHOST_HIGH_PHASE_COLOR
    return fill, gfx.scale_color(fill, 0.35)


def angle_label(angle):
    """An angle as a multiple of pi, e.g. 3*pi/4 -> '3π/4'."""
    ratio = Fraction(angle / math.pi).limit_denominator(16)
    numerator = "" if ratio.numerator == 1 else str(ratio.numerator)
    return f"{numerator}π" if ratio.denominator == 1 else f"{numerator}π/{ratio.denominator}"


def draw_snake(surface, snake, to_px, cell, t, palette, ghost_phases, dead=False):
    head_color, tail_color = palette
    if dead:
        head_color, tail_color = gfx.scale_color(head_color, 0.55), gfx.scale_color(tail_color, 0.55)
    points = [to_px(p) for p in snake.render_path(t)]
    n = len(points)
    # Resolving a ghost to 0 removes it from the middle of the body, leaving a gap.
    cells = list(snake.body)
    joined = [
        k + 1 >= len(cells) or abs(cells[k][0] - cells[k + 1][0]) + abs(cells[k][1] - cells[k + 1][1]) == 1
        for k in range(n)
    ]

    def block_type(k):
        return snake.block_types[min(k, len(snake.block_types) - 1)]

    def body_color(k):
        if block_type(k) is not None:
            return ghost_colors(ghost_phases.get(block_type(k)))[0]
        return gfx.lerp_color(head_color, tail_color, min(1.0, k / max(8, n - 1)))

    def outline(k):
        if block_type(k) is not None:
            return ghost_colors(ghost_phases.get(block_type(k)))[1]
        return gfx.scale_color(body_color(k), 0.35)

    def highlight(k):
        return gfx.lerp_color(body_color(k), gfx.WHITE, 0.35)

    _draw_tube(surface, points, cell * 0.43, outline, joined)
    _draw_tube(surface, points, cell * 0.36, body_color, joined)
    off = -cell * 0.09
    _draw_tube(surface, [(x + off, y + off) for x, y in points], cell * 0.1, highlight, joined)
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


def draw_ghost_panel(surface, panel, cell, ghost_gates, ghost_phases):
    """List every ghost block with its id and the circuit applied to its qubit."""
    border = max(1, cell // 16)
    surface.blit(gfx.rounded_rect(panel.size, round(cell * 0.4), gfx.PANEL_FILL, gfx.PANEL_BORDER, border), panel.topleft)
    pad = cell * 0.5
    left, right = panel.x + pad, panel.right - pad
    y = panel.y + pad * 0.8

    gfx.draw_text(surface, "GHOST BLOCKS", cell * 0.55, gfx.TEXT_DIM, (left, y))
    gfx.draw_text(surface, str(len(ghost_gates)), cell * 0.55, gfx.TEXT_DIM, (right, y), anchor="topright")
    y += cell * 1.2

    if not ghost_gates:
        gfx.draw_text(surface, "None yet - red apples add them", cell * 0.45, gfx.TEXT_DIM, (left, y))
        return

    # When the list overflows, keep the newest ghosts and summarise the rest.
    rows = list(ghost_gates.items())
    row_h = cell * 1.5
    available = panel.bottom - pad - y
    if len(rows) * row_h > available:
        more_h = cell * 0.8
        shown = max(0, int((available - more_h) // row_h))
        hidden = len(rows) - shown
        rows = rows[hidden:]
        gfx.draw_text(surface, f"+{hidden} earlier", cell * 0.45, gfx.TEXT_DIM, (left, y))
        y += more_h

    for ghost_id, operations in rows:
        _draw_ghost_row(surface, ghost_id, operations, ghost_phases.get(ghost_id), left, right, y + row_h / 2, cell)
        y += row_h


def _draw_ghost_row(surface, ghost_id, operations, phase, left, right, mid, cell):
    # Swatch matching how this block looks on the snake, then its id.
    fill, outline = ghost_colors(phase)
    swatch = (left + cell * 0.3, mid)
    gfx.aa_circle(surface, outline, swatch, cell * 0.3)
    gfx.aa_circle(surface, fill, swatch, cell * 0.22)
    gfx.draw_text(surface, f"#{ghost_id}", cell * 0.55, gfx.TEXT, (left + cell * 0.8, mid), anchor="midleft", bold=True)

    # Circuit: |0> on a wire, then one box per gate. The fonts lack a ket bracket, so draw it.
    x = left + cell * 2.4
    ket = gfx.draw_text(surface, "|0", cell * 0.5, gfx.TEXT, (x, mid), anchor="midleft")
    w = max(1, round(cell * 0.05))
    bx, half = ket.right + cell * 0.08, ket.height * 0.3
    pygame.draw.line(surface, gfx.TEXT, (bx, mid - half), (bx + half * 0.5, mid), w)
    pygame.draw.line(surface, gfx.TEXT, (bx + half * 0.5, mid), (bx, mid + half), w)
    x = bx + half * 0.5 + cell * 0.2
    pygame.draw.line(surface, WIRE_COLOR, (x, mid), (right, mid), max(1, cell // 14))

    box_w, box_h, spacing = round(cell * 1.15), round(cell * 1.1), cell * 0.25
    fits = max(1, int((right - x) // (box_w + spacing)))
    if len(operations) > fits:
        # Show the most recent gates; an ellipsis on the wire marks the earlier ones.
        centre = x + spacing + box_w / 2
        for i in (-1, 0, 1):
            gfx.aa_circle(surface, gfx.TEXT, (centre + i * cell * 0.25, mid), max(1, cell * 0.07))
        x += spacing + box_w
        operations = operations[len(operations) - fits + 1:]
    for gate, angle in operations:
        x += spacing
        box = pygame.Rect(round(x), round(mid - box_h / 2), box_w, box_h)
        color = H_GATE_COLOR if gate == "h" else ghost_colors(angle)[0]
        surface.blit(gfx.rounded_rect(box.size, round(cell * 0.18), color, gfx.lerp_color(color, gfx.WHITE, 0.4), max(1, cell // 20)), box.topleft)
        if gate == "h":
            gfx.draw_text(surface, "H", cell * 0.6, gfx.TEXT, box.center, anchor="center", bold=True)
        elif cell < SMALL_GATE_CELL:
            gfx.draw_text(surface, "Ry", cell * 0.5, gfx.TEXT, box.center, anchor="center", bold=True, shadow=False)
        else:
            gfx.draw_text(surface, "Ry", cell * 0.42, gfx.TEXT, (box.centerx, box.centery - cell * 0.02), anchor="midbottom", bold=True)
            gfx.draw_text(surface, angle_label(angle), cell * 0.36, gfx.TEXT, (box.centerx, box.centery), anchor="midtop")
        x += box_w


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
