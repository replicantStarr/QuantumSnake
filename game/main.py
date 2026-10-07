"""Quantum Snake: window management and switching between scenes.

A scene is any object with handle_event(event), update(dt) and draw(surface).
"""

import os

# Render at the monitor's real pixel resolution rather than letting Windows
# scale (and blur) the window, and centre new windows. Must be set before init.
os.environ.setdefault("SDL_WINDOWS_DPI_AWARENESS", "permonitorv2")
os.environ.setdefault("SDL_VIDEO_CENTERED", "1")

import pygame  # noqa: E402

from game import Game  # noqa: E402
from menu import MainMenu, MenuBackground, SettingsMenu  # noqa: E402
from settings import Settings  # noqa: E402

WINDOW_TITLE = "Quantum Snake"
FPS = 120
MAX_FRAME_TIME = 0.1  # seconds; stops the game jumping ahead after a stall

class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption(WINDOW_TITLE)
        self.settings = Settings.load()
        self.screen = None
        self.apply_display_settings()
        self.clock = pygame.time.Clock()
        self.menu_background = MenuBackground()
        self.running = True
        self.scene = MainMenu(self)

    def desktop_size(self):
        return pygame.display.get_desktop_sizes()[0]

    def apply_display_settings(self):
        if self.settings.fullscreen:
            self.screen = pygame.display.set_mode(self.desktop_size(), pygame.FULLSCREEN)
        else:
            self.screen = pygame.display.set_mode(self.settings.resolution, pygame.RESIZABLE)
        self.settings.save()

    def start_game(self):
        self.scene = Game(self)

    def show_main_menu(self):
        self.scene = MainMenu(self)

    def show_settings(self):
        self.scene = SettingsMenu(self)

    def quit(self):
        self.running = False

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
            self.scene.draw(self.screen)
            pygame.display.flip()
        self.settings.save()
        pygame.quit()


if __name__ == "__main__":
    App().run()
