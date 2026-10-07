"""Menu screens and the widgets they're built from.

Items can be used with the mouse, or with Up/Down (W/S) to select,
Left/Right (A/D) to change an option, Enter/Space to confirm and Esc to go back.
While a text box is selected, typing goes into it instead.
All sizes derive from the window size every frame, so menus stay crisp and
proportioned at any resolution.
"""

import math
import random

import pygame

import graphics as gfx
from settings import MAX_NAME_LENGTH, windowed_resolutions

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
        self.time = 0.0

    def update(self, dt, selected):
        self.time += dt
        target = 1.0 if selected else 0.0
        self.highlight += (target - self.highlight) * min(1.0, dt * 14)

    def activate(self):
        pass

    def adjust(self, step):
        pass

    def click(self, pos):
        self.activate()

    def handle_key(self, event):
        """Return True to stop the menu treating this key as navigation."""
        return False

    def draw_panel(self, surface, ui):
        level = round(self.highlight * 10) / 10  # quantised so panels cache well
        fill = gfx.lerp_color(gfx.PANEL_FILL, gfx.PANEL_FILL_HOVER, level)
        if not self.enabled:
            fill = fill[:3] + (120,)
        panel = gfx.rounded_rect(
            self.rect.size,
            round(12 * ui),
            fill,
            gfx.lerp_color(gfx.PANEL_BORDER, gfx.ACCENT, level),
            max(1, round(2 * ui)),
        )
        if level > 0:
            gfx.blit_glow(surface, self.rect.center, self.rect.w * 0.45, gfx.scale_color(gfx.ACCENT, 0.12 * level))
        surface.blit(panel, self.rect)
        return level

    def text_color(self, level):
        if not self.enabled:
            return gfx.scale_color(gfx.TEXT_DIM, 0.7)
        return gfx.lerp_color(gfx.TEXT_DIM, gfx.TEXT, max(level, 0.6))


class Button(Widget):
    def __init__(self, label, action, detail=None, enabled=True):
        super().__init__(enabled)
        self.label = label
        self.action = action
        self.detail = detail

    def activate(self):
        if self.enabled:
            self.action()

    def draw(self, surface, ui):
        level = self.draw_panel(surface, ui)
        color = self.text_color(level)
        if self.detail is None:
            gfx.draw_text(surface, self.label, 30 * ui, color, self.rect.center, anchor="center", bold=True)
            return
        pad = 24 * ui
        gfx.draw_text(surface, self.label, 26 * ui, color, (self.rect.x + pad, self.rect.centery), anchor="midleft", bold=True)
        detail_color = gfx.ACCENT if self.enabled else gfx.TEXT_DIM
        gfx.draw_text(surface, self.detail, 22 * ui, detail_color, (self.rect.right - pad, self.rect.centery), anchor="midright")


class InfoRow(Widget):
    """A non-interactive label/value row."""

    def __init__(self, label, value, value_color=gfx.TEXT):
        super().__init__(enabled=False)
        self.label = label
        self.value = value
        self.value_color = value_color

    def draw(self, surface, ui):
        self.draw_panel(surface, ui)
        pad = 24 * ui
        gfx.draw_text(surface, self.label, 22 * ui, gfx.TEXT_DIM, (self.rect.x + pad, self.rect.centery), anchor="midleft")
        gfx.draw_text(surface, self.value, 26 * ui, self.value_color, (self.rect.right - pad, self.rect.centery), anchor="midright", bold=True)


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
        self.adjust(-1 if self.rect.centerx < pos[0] < value_center else 1)

    def draw(self, surface, ui):
        level = self.draw_panel(surface, ui)
        pad = 24 * ui
        gfx.draw_text(surface, self.label, 26 * ui, self.text_color(level), (self.rect.x + pad, self.rect.centery), anchor="midleft", bold=True)

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


class TextInput(Widget):
    """An editable text box. Typing goes here while it's selected; Enter submits."""

    def __init__(self, label, text="", on_change=None, on_submit=None, max_length=24, allowed=None, placeholder=""):
        super().__init__()
        self.label = label
        self.text = text
        self.on_change = on_change
        self.on_submit = on_submit
        self.max_length = max_length
        self.allowed = allowed
        self.placeholder = placeholder

    def insert(self, text):
        for char in text:
            if char.isprintable() and (self.allowed is None or char in self.allowed) and len(self.text) < self.max_length:
                self.text += char
        if self.on_change:
            self.on_change(self.text)

    def handle_key(self, event):
        if event.key == pygame.K_BACKSPACE:
            self.text = self.text[:-1]
            if self.on_change:
                self.on_change(self.text)
            return True
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.activate()
            return True
        # Printable keys arrive separately as TEXTINPUT; don't let W/A/S/D navigate.
        return bool(event.unicode) and event.unicode.isprintable()

    def activate(self):
        if self.on_submit:
            self.on_submit()

    def click(self, pos):
        pass  # clicking just selects it

    def draw(self, surface, ui):
        level = self.draw_panel(surface, ui)
        pad = 24 * ui
        gfx.draw_text(surface, self.label, 26 * ui, self.text_color(level), (self.rect.x + pad, self.rect.centery), anchor="midleft", bold=True)

        box = pygame.Rect(0, 0, self.rect.w * 0.5, self.rect.h - 16 * ui)
        box.midright = (self.rect.right - 10 * ui, self.rect.centery)
        surface.blit(gfx.rounded_rect(box.size, round(8 * ui), (8, 12, 22, 200), gfx.PANEL_BORDER, 1), box)
        text_pos = (box.x + 14 * ui, box.centery)
        if self.text:
            rect = gfx.draw_text(surface, self.text, 24 * ui, gfx.TEXT, text_pos, anchor="midleft", shadow=False)
            caret_x = rect.right + 2 * ui
        else:
            gfx.draw_text(surface, self.placeholder, 24 * ui, gfx.scale_color(gfx.TEXT_DIM, 0.7), text_pos, anchor="midleft", shadow=False)
            caret_x = text_pos[0]
        if self.highlight > 0.5 and (self.time * 2) % 2 < 1.2:
            h = 26 * ui
            pygame.draw.line(surface, gfx.ACCENT, (caret_x, box.centery - h / 2), (caret_x, box.centery + h / 2), max(1, round(2 * ui)))


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
        for r, brightness in ((radius * 1.2, 0.12), (radius, 0.3)):
            for i in range(samples):
                k = i / (samples - 1)  # 0 = tail, 1 = head
                p = self._snake_point(self.time - 2.5 * (1 - k), w, h)
                color = gfx.scale_color(gfx.lerp_color((20, 130, 110), (130, 255, 170), k), brightness)
                gfx.aa_circle(surface, color, p, r * (0.55 + 0.45 * k))


class MenuScene:
    title = TITLE
    item_width = 340
    footer = "Arrows / mouse to select   ·   Enter to confirm   ·   Esc to go back"

    def __init__(self, app):
        self.app = app
        self.items = []
        self.selected = 0

    @property
    def subtitle(self):
        return None

    def back(self):
        pass

    def set_items(self, items):
        """Replace the items, keeping the selection and hover animation where possible."""
        current = self.items[self.selected] if self.items else None
        old_by_key = {getattr(item, "key", None) or item.label: item for item in self.items}
        for item in items:
            old = old_by_key.get(getattr(item, "key", None) or item.label)
            if old:
                item.highlight = old.highlight
                item.time = old.time
        self.items = items
        if current is not None:
            current_key = getattr(current, "key", None) or current.label
            for i, item in enumerate(items):
                if (getattr(item, "key", None) or item.label) == current_key:
                    self.selected = i
                    break
        self.selected = min(self.selected, len(items) - 1)
        self._ensure_selectable()

    def _ensure_selectable(self):
        if self.items and not self.items[self.selected].enabled:
            self._move_selection(1)

    def _move_selection(self, step):
        for _ in range(len(self.items)):
            self.selected = (self.selected + step) % len(self.items)
            if self.items[self.selected].enabled:
                return

    def handle_event(self, event):
        if not self.items:
            return
        item = self.items[self.selected]
        if event.type == pygame.MOUSEMOTION:
            for i, other in enumerate(self.items):
                if other.enabled and other.rect.collidepoint(event.pos):
                    self.selected = i
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, other in enumerate(self.items):
                if other.enabled and other.rect.collidepoint(event.pos):
                    self.selected = i
                    other.click(event.pos)
                    return
        elif event.type == pygame.TEXTINPUT:
            if isinstance(item, TextInput):
                item.insert(event.text)
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.back()
            elif item.handle_key(event):
                pass
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
        self._ensure_selectable()
        for i, item in enumerate(self.items):
            item.update(dt, i == self.selected)

    def layout(self, size, ui):
        w, h = size
        item_w, item_h, gap = round(self.item_width * ui), round(58 * ui), round(14 * ui)
        total = len(self.items) * item_h + max(0, len(self.items) - 1) * gap
        y = round(max(h * 0.38, h * 0.64 - total / 2))
        for item in self.items:
            item.rect = pygame.Rect(0, 0, item_w, item_h)
            item.rect.midtop = (w // 2, y)
            y += item_h + gap

    def draw(self, surface):
        size = surface.get_size()
        ui = ui_scale(size)
        self.app.menu_background.draw(surface)
        self.layout(size, ui)
        title_y = size[1] * 0.2
        gfx.draw_glow_text(surface, self.title, 96 * ui, gfx.TEXT, gfx.ACCENT_DARK, (size[0] / 2, title_y))
        if self.subtitle:
            gfx.draw_text(surface, self.subtitle, 24 * ui, gfx.TEXT_DIM, (size[0] / 2, title_y + 80 * ui), anchor="center")
        for item in self.items:
            item.draw(surface, ui)
        gfx.draw_text(surface, self.footer, 18 * ui, gfx.TEXT_DIM, (size[0] / 2, size[1] - 28 * ui), anchor="center", alpha=170)


class MainMenu(MenuScene):
    def __init__(self, app):
        super().__init__(app)
        self.set_items([
            Button("Play Solo", app.start_game),
            Button("Host Game", app.host_game),
            Button("Join Game", app.show_server_browser),
            Button("Settings", app.show_settings),
            Button("Exit", app.quit),
        ])

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
        name_row = TextInput("Player name", settings.player_name, on_change=self.set_name, max_length=MAX_NAME_LENGTH)
        display_row = OptionRow("Display mode", ["Windowed", "Fullscreen"], int(settings.fullscreen), self.set_fullscreen)
        if settings.fullscreen:
            w, h = self.app.screen.get_size()
            resolution_row = OptionRow("Resolution", [f"{w} × {h}"], 0, lambda i: None, enabled=False)
        else:
            self.resolutions = windowed_resolutions(self.app.desktop_size(), settings.resolution)
            labels = [f"{w} × {h}" for w, h in self.resolutions]
            resolution_row = OptionRow("Resolution", labels, self.resolutions.index(tuple(settings.resolution)), self.set_resolution)
        self.set_items([name_row, display_row, resolution_row, Button("Back", self.back)])

    def set_name(self, text):
        self.app.settings.player_name = text

    def set_fullscreen(self, index):
        self.app.settings.fullscreen = bool(index)
        self.app.apply_display_settings()
        self.build_items()

    def set_resolution(self, index):
        self.app.settings.resolution = self.resolutions[index]
        self.app.apply_display_settings()
        self.build_items()

    def back(self):
        self.app.settings.player_name = self.app.settings.player_name.strip() or self.app.settings.default_name()
        self.app.settings.save()
        self.app.show_main_menu()
