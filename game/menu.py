"""Main menu and settings screens, plus the widgets they're built from.

Items can be used with the mouse, or with Up/Down (W/S) to select,
Left/Right (A/D) to change an option, Enter/Space to confirm and Esc to go back.
All sizes derive from the window size every frame, so menus stay crisp and
proportioned at any resolution.
"""

import math
import random

import pygame

import graphics as gfx
from settings import windowed_resolutions

CONFIRM_KEYS = (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE)
UP_KEYS = (pygame.K_UP, pygame.K_w, pygame.K_KP8)
DOWN_KEYS = (pygame.K_DOWN, pygame.K_s, pygame.K_KP2)
LEFT_KEYS = (pygame.K_LEFT, pygame.K_a, pygame.K_KP4)
RIGHT_KEYS = (pygame.K_RIGHT, pygame.K_d, pygame.K_KP6)

TITLE = "QUANTUM SNAKE"


def ui_scale(size):
    w, h = size
    return min(w / 1280, h / 720)


class Widget:
    def __init__(self, enabled=True):
        self.rect = pygame.Rect(0, 0, 0, 0)
        self.enabled = enabled
        self.highlight = 0.0  # animates 0..1 while selected

    def update(self, dt, selected):
        target = 1.0 if selected else 0.0
        self.highlight += (target - self.highlight) * min(1.0, dt * 14)

    def activate(self):
        pass

    def adjust(self, step):
        pass

    def click(self, pos):
        self.activate()

    def draw_panel(self, surface, ui):
        level = round(self.highlight * 10) / 10  # quantised so panels cache well
        panel = gfx.rounded_rect(
            self.rect.size,
            round(12 * ui),
            gfx.lerp_color(gfx.PANEL_FILL, gfx.PANEL_FILL_HOVER, level),
            gfx.lerp_color(gfx.PANEL_BORDER, gfx.ACCENT, level),
            max(1, round(2 * ui)),
        )
        if level > 0:
            gfx.blit_glow(surface, self.rect.center, self.rect.w * 0.45, gfx.scale_color(gfx.ACCENT, 0.12 * level))
        surface.blit(panel, self.rect)
        return level


class Button(Widget):
    def __init__(self, label, action):
        super().__init__()
        self.label = label
        self.action = action

    def activate(self):
        self.action()

    def draw(self, surface, ui):
        level = self.draw_panel(surface, ui)
        color = gfx.lerp_color(gfx.TEXT_DIM, gfx.TEXT, max(level, 0.6))
        gfx.draw_text(surface, self.label, 30 * ui, color, self.rect.center, anchor="center", bold=True)


class OptionRow(Widget):
    """A label with a value that cycles through `options` (strings)."""

    def __init__(self, label, options, index, on_change, enabled=True):
        super().__init__(enabled)
        self.label = label
        self.options = options
        self.index = index
        self.on_change = on_change

    def adjust(self, step):
        if not self.enabled or len(self.options) < 2:
            return
        self.index = (self.index + step) % len(self.options)
        self.on_change(self.index)

    def activate(self):
        self.adjust(1)

    def click(self, pos):
        value_center = self.rect.right - self.rect.w * 0.25
        self.adjust(-1 if pos[0] < value_center and pos[0] > self.rect.centerx else 1)

    def draw(self, surface, ui):
        level = self.draw_panel(surface, ui)
        pad = 24 * ui
        label_color = gfx.lerp_color(gfx.TEXT_DIM, gfx.TEXT, max(level, 0.6)) if self.enabled else gfx.scale_color(gfx.TEXT_DIM, 0.6)
        gfx.draw_text(surface, self.label, 26 * ui, label_color, (self.rect.x + pad, self.rect.centery), anchor="midleft", bold=True)

        value_color = gfx.ACCENT if self.enabled else gfx.TEXT_DIM
        vx = self.rect.right - self.rect.w * 0.25
        cy = self.rect.centery
        gfx.draw_text(surface, self.options[self.index], 26 * ui, value_color, (vx, cy), anchor="center")
        if self.enabled and len(self.options) > 1:
            arrow_color = gfx.lerp_color(gfx.TEXT_DIM, gfx.ACCENT, level)
            s = 8 * ui
            spread = self.rect.w * 0.2
            for direction in (-1, 1):
                ax = vx + direction * spread
                gfx.aa_polygon(surface, arrow_color, [(ax + direction * s, cy), (ax - direction * s * 0.6, cy - s), (ax - direction * s * 0.6, cy + s)])


class MenuBackground:
    """Gradient backdrop with drifting motes and a snake slithering behind the menu."""

    def __init__(self):
        self.time = 0.0
        self.motes = [[random.random(), random.random(), random.uniform(0.01, 0.04), random.uniform(0, math.tau)] for _ in range(40)]

    def update(self, dt):
        self.time += dt
        for mote in self.motes:
            mote[1] -= mote[2] * dt
            if mote[1] < -0.05:
                mote[0], mote[1] = random.random(), 1.05

    def draw(self, surface):
        size = surface.get_size()
        w, h = size
        ui = ui_scale(size)
        surface.blit(gfx.vertical_gradient(size, gfx.MENU_TOP, gfx.MENU_BOTTOM), (0, 0))

        for x, y, speed, phase in self.motes:
            twinkle = 0.5 + 0.5 * math.sin(self.time * 2 + phase)
            gfx.blit_glow(surface, (x * w, y * h), 14 * ui, gfx.scale_color(gfx.ACCENT, 0.15 + 0.2 * twinkle))

        self._draw_snake(surface, w, h, ui)

    def _snake_point(self, s, w, h):
        x = 0.5 + 0.4 * math.sin(0.31 * s + 0.6 * math.sin(0.17 * s))
        y = 0.55 + 0.33 * math.sin(0.47 * s + 1.3)
        return x * w, y * h

    def _draw_snake(self, surface, w, h, ui):
        samples = 70
        radius = 16 * ui
        for layer, (r, brightness) in enumerate(((radius * 1.2, 0.12), (radius, 0.3))):
            for i in range(samples):
                k = i / (samples - 1)  # 0 = tail, 1 = head
                p = self._snake_point(self.time - 2.5 * (1 - k), w, h)
                color = gfx.scale_color(gfx.lerp_color((20, 130, 110), (130, 255, 170), k), brightness)
                gfx.aa_circle(surface, color, p, r * (0.55 + 0.45 * k))


class MenuScene:
    title = TITLE
    item_width = 340

    def __init__(self, app):
        self.app = app
        self.items = []
        self.selected = 0

    def back(self):
        pass

    def _move_selection(self, step):
        for _ in range(len(self.items)):
            self.selected = (self.selected + step) % len(self.items)
            if self.items[self.selected].enabled:
                return

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            for i, item in enumerate(self.items):
                if item.enabled and item.rect.collidepoint(event.pos):
                    self.selected = i
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, item in enumerate(self.items):
                if item.enabled and item.rect.collidepoint(event.pos):
                    self.selected = i
                    item.click(event.pos)
                    return
        elif event.type == pygame.KEYDOWN:
            item = self.items[self.selected]
            if event.key == pygame.K_ESCAPE:
                self.back()
            elif event.key in UP_KEYS:
                self._move_selection(-1)
            elif event.key in DOWN_KEYS:
                self._move_selection(1)
            elif event.key in LEFT_KEYS:
                item.adjust(-1)
            elif event.key in RIGHT_KEYS:
                item.adjust(1)
            elif event.key in CONFIRM_KEYS:
                item.activate()

    def update(self, dt):
        self.app.menu_background.update(dt)
        for i, item in enumerate(self.items):
            item.update(dt, i == self.selected)

    def layout(self, size, ui):
        w, h = size
        item_w, item_h, gap = round(self.item_width * ui), round(64 * ui), round(16 * ui)
        y = round(h * 0.45)
        for item in self.items:
            item.rect = pygame.Rect(0, 0, item_w, item_h)
            item.rect.midtop = (w // 2, y)
            y += item_h + gap

    def draw(self, surface):
        size = surface.get_size()
        ui = ui_scale(size)
        self.app.menu_background.draw(surface)
        self.layout(size, ui)
        gfx.draw_glow_text(surface, self.title, 96 * ui, gfx.TEXT, gfx.ACCENT_DARK, (size[0] / 2, size[1] * 0.25))
        for item in self.items:
            item.draw(surface, ui)
        gfx.draw_text(
            surface, "Arrows / mouse to select   ·   Enter to confirm   ·   Esc to go back",
            18 * ui, gfx.TEXT_DIM, (size[0] / 2, size[1] - 28 * ui), anchor="center", alpha=170,
        )


class MainMenu(MenuScene):
    def __init__(self, app):
        super().__init__(app)
        self.items = [
            Button("Play", app.start_game),
            Button("Settings", app.show_settings),
            Button("Exit", app.quit),
        ]

    def back(self):
        self.app.quit()


class SettingsMenu(MenuScene):
    title = "SETTINGS"
    item_width = 600

    def __init__(self, app):
        super().__init__(app)
        self.build_items()

    def build_items(self):
        settings = self.app.settings
        display_row = OptionRow("Display mode", ["Windowed", "Fullscreen"], int(settings.fullscreen), self.set_fullscreen)
        if settings.fullscreen:
            w, h = self.app.screen.get_size()
            resolution_row = OptionRow("Resolution", [f"{w} × {h}"], 0, lambda i: None, enabled=False)
        else:
            self.resolutions = windowed_resolutions(self.app.desktop_size(), settings.resolution)
            labels = [f"{w} × {h}" for w, h in self.resolutions]
            resolution_row = OptionRow("Resolution", labels, self.resolutions.index(tuple(settings.resolution)), self.set_resolution)
        new_items = [display_row, resolution_row, Button("Back", self.back)]
        for old, new in zip(self.items, new_items):
            new.highlight = old.highlight
        self.items = new_items

    def set_fullscreen(self, index):
        self.app.settings.fullscreen = bool(index)
        self.app.apply_display_settings()
        self.build_items()

    def set_resolution(self, index):
        self.app.settings.resolution = self.resolutions[index]
        self.app.apply_display_settings()
        self.build_items()

    def back(self):
        self.app.show_main_menu()
