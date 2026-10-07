"""The gameplay scene, shared by solo, hosted and joined games.

A session supplies the game state:
    LocalSession  - runs the World here (solo play)
    HostSession   - runs the World here and streams it to the other player
    ClientSession - draws snapshots streamed from the host, sends steering input

Game logic steps on a grid at `speed` moves per second; rendering runs every
frame and interpolates the snakes between cells. The board is scaled to fit
the window and letterboxed with black bars to keep its shape.
"""

import math
import random

import pygame

import graphics as gfx
import render
from apples import APPLE_TYPES_BY_NAME
from network import HOST_PLAYER_ID
from world import DOWN, GRID_HEIGHT, GRID_WIDTH, LEFT, RIGHT, UP, World

# Arrow keys, WASD and numpad (8/4/6/2) all steer the snake.
KEY_DIRECTIONS = {
    pygame.K_UP: UP, pygame.K_w: UP, pygame.K_KP8: UP,
    pygame.K_DOWN: DOWN, pygame.K_s: DOWN, pygame.K_KP2: DOWN,
    pygame.K_LEFT: LEFT, pygame.K_a: LEFT, pygame.K_KP4: LEFT,
    pygame.K_RIGHT: RIGHT, pygame.K_d: RIGHT, pygame.K_KP6: RIGHT,
}
DIRECTIONS = (UP, DOWN, LEFT, RIGHT)
RESTART_KEYS = (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER)

COUNTDOWN = 3.0
GO_TIME = 0.6
SHAKE_TIME = 0.35
GAME_OVER_FADE_TIME = 0.6


class LocalSession:
    can_restart = True
    over_hint = "Space to play again   ·   Esc for menu"

    def __init__(self, app, players, local_id=HOST_PLAYER_ID):
        self.app = app
        self.players = players
        self.local_id = local_id
        self.generation = 0  # bumps on every (re)start so the scene can clear its effects
        self.start()

    def start(self):
        self.world = World(self.players)
        self.countdown = COUNTDOWN
        self.step_timer = 0.0
        self.steps = 0
        self.generation += 1

    @property
    def t(self):
        """How far (0..1) the snakes are through their current move, for interpolation."""
        if self.world.over or self.countdown > 0:
            return 1.0
        return min(1.0, self.step_timer * self.world.speed)

    def steer(self, direction):
        self.world.queue_direction(self.local_id, direction)

    def update(self, dt):
        self.countdown = max(-GO_TIME, self.countdown - dt)
        if self.countdown > 0 or self.world.over:
            return []
        events = []
        self.step_timer += dt
        interval = 1 / self.world.speed
        while self.step_timer >= interval and not self.world.over:
            self.step_timer -= interval
            step_events = self.world.step()
            self.steps += 1
            self.after_step(step_events)
            events += step_events
            interval = 1 / self.world.speed
        return events

    def after_step(self, events):
        pass

    def restart(self):
        self.start()

    def leave(self):
        self.app.show_main_menu()


class HostSession(LocalSession):
    over_hint = "Space to play again   ·   Esc for lobby"

    def __init__(self, app):
        self.host = app.host
        super().__init__(app, list(self.host.players.items()))

    def start(self):
        super().start()
        self.host.in_game = True
        self.host.broadcast({"type": "start", "world": self.world.to_dict(), "countdown": self.countdown})

    def update(self, dt):
        for kind, player_id, data in self.host.poll():
            if kind == "message" and data.get("type") == "input":
                direction = tuple(data.get("dir") or ())
                if direction in DIRECTIONS:
                    self.world.queue_direction(player_id, direction)
            elif kind == "left":
                self.return_to_lobby(notice=f"{data} left the game")
                return []
        return super().update(dt)

    def after_step(self, events):
        self.host.broadcast({"type": "state", "world": self.world.to_dict(), "events": events})

    def leave(self):
        self.return_to_lobby()

    def return_to_lobby(self, notice=None):
        self.host.in_game = False
        self.host.broadcast({"type": "return_to_lobby"})
        self.host.broadcast_lobby()
        self.app.show_host_lobby(notice)


class ClientSession:
    can_restart = False
    over_hint = "Waiting for the host to play again   ·   Esc to leave"

    def __init__(self, app, start_message):
        self.app = app
        self.client = app.client
        self.local_id = self.client.player_id
        self.generation = 0
        self._start(start_message)

    def _start(self, message):
        self.world = World.from_dict(message["world"])
        self.countdown = message.get("countdown", COUNTDOWN)
        self.since_state = 0.0
        self.steps = 0
        self.generation += 1

    @property
    def t(self):
        if self.world.over or self.countdown > 0:
            return 1.0
        return min(1.0, self.since_state * self.world.speed)

    def steer(self, direction):
        if not self.world.over:
            self.client.send({"type": "input", "dir": direction})

    def update(self, dt):
        self.countdown = max(-GO_TIME, self.countdown - dt)
        self.since_state += dt
        events = []
        for kind, data in self.client.poll():
            if kind == "closed":
                self.app.show_main_menu(notice=data)
                return []
            message_type = data.get("type")
            if message_type == "state":
                self.world = World.from_dict(data["world"], previous=self.world)
                self.since_state = 0.0
                self.steps += 1
                events += data["events"]
            elif message_type == "start":
                self._start(data)
                events = []
            elif message_type == "return_to_lobby":
                self.app.show_client_lobby()
                return []
        return events

    def restart(self):
        pass

    def leave(self):
        self.app.show_main_menu()


class GameScene:
    def __init__(self, app, session):
        self.app = app
        self.session = session
        self.reset_effects()

    def reset_effects(self):
        self.generation = self.session.generation
        self.particles = []
        self.popups = []
        self.eaten_apple = None
        self.eaten_step = -1
        self.shake = 0.0
        self.game_over_time = 0.0

    def palette_for(self, index):
        return render.SNAKE_PALETTES[index % len(render.SNAKE_PALETTES)]

    # --- Scene interface -------------------------------------------------

    def handle_event(self, event):
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_ESCAPE:
            self.session.leave()
        elif self.session.world.over:
            if event.key in RESTART_KEYS and self.session.can_restart:
                self.session.restart()
        elif event.key in KEY_DIRECTIONS:
            self.session.steer(KEY_DIRECTIONS[event.key])

    def update(self, dt):
        events = self.session.update(dt)
        if self.app.scene is not self:
            return  # the session switched scenes (e.g. disconnected)
        if self.session.generation != self.generation:
            self.reset_effects()

        world = self.session.world
        if world.apple:
            world.apple.update(dt)
        for effect in self.particles + self.popups:
            effect.update(dt)
        self.particles = [p for p in self.particles if not p.done]
        self.popups = [p for p in self.popups if not p.done]
        self.shake = max(0.0, self.shake - dt)
        self.game_over_time = self.game_over_time + dt if world.over else 0.0

        for event in events:
            if event["type"] == "die":
                self.shake = SHAKE_TIME
            elif event["type"] == "eat":
                self.on_eat(event)

    def on_eat(self, event):
        apple = APPLE_TYPES_BY_NAME[event["apple"]](tuple(event["pos"]))
        apple.age = 1.0  # skip the pop-in animation
        center = (apple.position[0] + 0.5, apple.position[1] + 0.5)
        self.particles.extend(render.Particle(center, apple.color) for _ in range(22))
        if event["gained"]:
            self.popups.append(render.ScorePopup((center[0], center[1] - 0.6), f"{event['gained']:+d}", apple.color))
        # Keep drawing it, shrinking, until the head visually reaches it.
        self.eaten_apple = apple
        self.eaten_step = self.session.steps

    # --- Drawing ---------------------------------------------------------

    @staticmethod
    def layout(screen_size):
        w, h = screen_size
        cell = max(2, min(w // GRID_WIDTH, h // GRID_HEIGHT))
        field = pygame.Rect(0, 0, cell * GRID_WIDTH, cell * GRID_HEIGHT)
        field.center = (w // 2, h // 2)
        return cell, field

    def draw(self, surface):
        world = self.session.world
        t = self.session.t
        surface.fill(gfx.BLACK)
        cell, field = self.layout(surface.get_size())
        if self.shake > 0:
            amount = cell * 0.3 * (self.shake / SHAKE_TIME)
            field = field.move(round(random.uniform(-amount, amount)), round(random.uniform(-amount, amount)))

        def to_px(p):
            return field.x + p[0] * cell, field.y + p[1] * cell

        surface.blit(gfx.playfield_background(cell, GRID_WIDTH, GRID_HEIGHT), field.topleft)
        surface.set_clip(field)
        if world.apple:
            ax, ay = world.apple.position
            world.apple.draw(surface, to_px((ax + 0.5, ay + 0.5)), cell)
        if self.eaten_apple and self.eaten_step == self.session.steps and t < 1:
            ex, ey = self.eaten_apple.position
            self.eaten_apple.draw(surface, to_px((ex + 0.5, ey + 0.5)), cell, scale=1 - t)
        # Dead snakes underneath, then the others, with your own snake on top.
        order = sorted(enumerate(world.players), key=lambda ip: (ip[1].alive, ip[1].id == self.session.local_id))
        for index, player in order:
            render.draw_snake(surface, player.snake, to_px, cell, t, self.palette_for(index), player.ghost_phases, dead=not player.alive)
        for effect in self.particles + self.popups:
            effect.draw(surface, to_px, cell)
        surface.set_clip(None)

        self.draw_hud(surface, field, cell, world)
        if self.session.countdown > -GO_TIME and not world.over:
            self.draw_countdown(surface, field, cell)
        if world.over:
            self.draw_game_over(surface, field, cell, world)

    def draw_hud(self, surface, field, cell, world):
        pad = cell * 0.5
        top = field.y + pad * 0.8
        if not world.versus:
            gfx.draw_text(surface, "SCORE", cell * 0.55, gfx.TEXT_DIM, (field.x + pad, top))
            gfx.draw_text(surface, str(world.players[0].score), cell * 1.1, gfx.TEXT, (field.x + pad, top + cell * 0.55), bold=True)
            return
        for index, player in enumerate(world.players[:2]):
            color = self.palette_for(index)[0] if player.alive else gfx.TEXT_DIM
            name = player.name + ("  (you)" if player.id == self.session.local_id else "")
            x, anchor = (field.x + pad, "topleft") if index == 0 else (field.right - pad, "topright")
            gfx.draw_text(surface, name.upper(), cell * 0.55, color, (x, top), anchor=anchor)
            gfx.draw_text(surface, str(player.score), cell * 1.1, gfx.TEXT, (x, top + cell * 0.55), anchor=anchor, bold=True)

    def draw_countdown(self, surface, field, cell):
        remaining = self.session.countdown
        cx, cy = field.center
        if remaining > 0:
            frac = remaining - math.floor(remaining)
            size = cell * 4 * (1 + 0.35 * frac ** 3)
            gfx.draw_glow_text(surface, str(math.ceil(remaining)), size, gfx.TEXT, gfx.ACCENT_DARK, (cx, cy))
        else:
            k = -remaining / GO_TIME
            gfx.draw_text(surface, "GO!", cell * 4 * (1 + 0.4 * k), gfx.ACCENT, (cx, cy), anchor="center", bold=True, alpha=round(255 * (1 - k)))

    def draw_game_over(self, surface, field, cell, world):
        k = min(1.0, self.game_over_time / GAME_OVER_FADE_TIME)
        overlay = pygame.Surface(field.size, pygame.SRCALPHA)
        overlay.fill((0, 0, 0, round(160 * k)))
        surface.blit(overlay, field.topleft)
        if k < 0.3:
            return
        cx, cy = field.center
        if world.versus:
            winner = world.winner
            if winner is None:
                title, glow = "DRAW", (90, 110, 160)
            elif winner.id == self.session.local_id:
                title, glow = "YOU WIN", gfx.ACCENT_DARK
            else:
                title, glow = "YOU LOSE", (220, 60, 80)
            gfx.draw_glow_text(surface, title, cell * 2.4, gfx.TEXT, glow, (cx, cy - cell * 1.8))
            for index, player in enumerate(world.players):
                y = cy + cell * (0.2 + index * 1.1)
                gfx.draw_text(surface, f"{player.name}   {player.score}", cell * 0.9, self.palette_for(index)[0], (cx, y), anchor="center", bold=True)
            hint_y = cy + cell * (0.6 + len(world.players) * 1.1)
        else:
            gfx.draw_glow_text(surface, "GAME OVER", cell * 2.4, gfx.TEXT, (220, 60, 80), (cx, cy - cell * 1.6))
            gfx.draw_text(surface, f"Score  {world.players[0].score}", cell * 1.1, gfx.ACCENT, (cx, cy + cell * 0.4), anchor="center", bold=True)
            hint_y = cy + cell * 2.2
        pulse = round(170 + 85 * math.sin(self.game_over_time * 4))
        gfx.draw_text(surface, self.session.over_hint, cell * 0.7, gfx.TEXT_DIM, (cx, hint_y), anchor="center", alpha=pulse)
