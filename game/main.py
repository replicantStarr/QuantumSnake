"""Quantum Snake: window management, networking lifetime and switching between scenes.

A scene is any object with handle_event(event), update(dt) and draw(surface),
and optionally close() to release resources when it's replaced.
"""

import os

# Render at the monitor's real pixel resolution rather than letting Windows
# scale (and blur) the window, and centre new windows. Must be set before init.
os.environ.setdefault("SDL_WINDOWS_DPI_AWARENESS", "permonitorv2")
os.environ.setdefault("SDL_VIDEO_CENTERED", "1")

import pygame  # noqa: E402

import graphics as gfx  # noqa: E402
from game import GameScene, HostSession, LocalSession, LocalVersusSession  # noqa: E402
from lobby import ClientLobby, HostLobby, ServerBrowser  # noqa: E402
from menu import HowToPlayMenu, MainMenu, MenuBackground, MultiplayerMenu, SettingsMenu, ui_scale  # noqa: E402
from network import HOST_PLAYER_ID, Client, Host  # noqa: E402
from settings import Settings  # noqa: E402

WINDOW_TITLE = "Quantum Snake"
FPS = 120
MAX_FRAME_TIME = 0.1  # seconds; stops the game jumping ahead after a stall
NOTICE_TIME = 4.0

class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption(WINDOW_TITLE)
        pygame.key.start_text_input()
        self.settings = Settings.load()
        self.screen = None
        self.apply_display_settings()
        self.clock = pygame.time.Clock()
        self.menu_background = MenuBackground()
        self.host = None
        self.client = None
        self.notice = None
        self.notice_time = 0.0
        self.running = True
        self.scene = None
        self.set_scene(MainMenu(self))

    def desktop_size(self):
        return pygame.display.get_desktop_sizes()[0]

    def apply_display_settings(self):
        if self.settings.fullscreen:
            self.screen = pygame.display.set_mode(self.desktop_size(), pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode(self.settings.resolution, pygame.RESIZABLE)
        self.settings.save()

    # --- Scenes ----------------------------------------------------------

    def set_scene(self, scene):
        if self.scene is not None and hasattr(self.scene, "close"):
            self.scene.close()
        self.scene = scene

    def show_notice(self, text):
        if text:
            self.notice = text
            self.notice_time = NOTICE_TIME

    def show_main_menu(self, notice=None):
        self.close_network()
        self.set_scene(MainMenu(self))
        self.show_notice(notice)

    def show_multiplayer_menu(self, notice=None):
        self.close_network()
        self.set_scene(MultiplayerMenu(self))
        self.show_notice(notice)

    def show_settings(self):
        self.set_scene(SettingsMenu(self))

    def show_how_to_play(self):
        self.set_scene(HowToPlayMenu(self))

    def start_game(self):
        self.set_scene(GameScene(self, LocalSession(self, [(HOST_PLAYER_ID, self.settings.player_name)])))

    def start_local_versus(self):
        self.set_scene(GameScene(self, LocalVersusSession(self)))

    def host_game(self):
        self.close_network()
        try:
            self.host = Host(self.settings.player_name)
        except Exception as e:
            self.show_notice(f"Couldn't start a server: {e}")
            return
        self.set_scene(HostLobby(self))

    def show_host_lobby(self, notice=None):
        self.set_scene(HostLobby(self))
        self.show_notice(notice)

    def start_hosted_game(self):
        self.set_scene(GameScene(self, HostSession(self)))

    def show_server_browser(self, notice=None):
        self.close_network()
        self.set_scene(ServerBrowser(self))
        self.show_notice(notice)

    def join_game(self, address, port):
        self.close_network()
        self.client = Client(address, port, self.settings.player_name)
        self.set_scene(ClientLobby(self))

    def show_client_lobby(self):
        self.set_scene(ClientLobby(self))

    def close_network(self):
        if self.host:
            self.host.close()
            self.host = None
        if self.client:
            self.client.close()
            self.client = None

    def quit(self):
        self.running = False

    # --- Main loop -------------------------------------------------------

    def draw_notice(self, surface):
        if self.notice_time <= 0:
            return
        ui = ui_scale(surface.get_size())
        alpha = round(255 * min(1.0, self.notice_time / 0.4))
        font_size = 22 * ui
        text_w = gfx.font(font_size).size(self.notice)[0]
        size = (round(text_w + 48 * ui), round(48 * ui))
        panel = gfx.rounded_rect(size, round(size[1] / 2), (40, 24, 30, 235), (200, 80, 100), max(1, round(2 * ui))).copy()
        panel.set_alpha(alpha)
        rect = panel.get_rect(midbottom=(surface.get_width() // 2, surface.get_height() - 64 * ui))
        surface.blit(panel, rect)
        gfx.draw_text(surface, self.notice, font_size, gfx.TEXT, rect.center, anchor="center", alpha=alpha)

    def run(self):
        while self.running:
            dt = min(self.clock.tick(FPS) / 1000, MAX_FRAME_TIME)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.quit()
                elif event.type == pygame.VIDEORESIZE and not self.settings.fullscreen:
                    self.settings.resolution = (event.w, event.h)
                self.scene.handle_event(event)
            self.screen = pygame.display.get_surface()
            self.scene.update(dt)
            self.notice_time = max(0.0, self.notice_time - dt)
            self.scene.draw(self.screen)
            self.draw_notice(self.screen)
            pygame.display.flip()
        self.set_scene(None)
        self.close_network()
        self.settings.save()
        pygame.quit()


if __name__ == "__main__":
    App().run()
