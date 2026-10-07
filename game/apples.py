"""Apple types for Snake.

To add your own apple:
    1. Subclass Apple.
    2. Set `color` (and optionally `spawn_weight`).
    3. Implement `on_eaten(self, game)` to do whatever you like to the game.
    4. Add the class to APPLE_TYPES at the bottom of this file.

`game` exposes:
    game.snake.grow(n)   - add n segments
    game.snake.shrink(n) - remove n segments (never below 1)
    game.score           - int, read/write
    game.speed           - moves per second, read/write
"""

from abc import ABC, abstractmethod

import pygame


class Apple(ABC):
    color = (255, 255, 255)
    spawn_weight = 1  # Higher = more likely to spawn relative to other types

    def __init__(self, position):
        self.position = position

    @abstractmethod
    def on_eaten(self, game):
        """Called once when the snake's head lands on this apple."""

    def draw(self, surface, cell_size):
        x, y = self.position
        rect = pygame.Rect(x * cell_size, y * cell_size, cell_size, cell_size)
        pygame.draw.ellipse(surface, self.color, rect)


class RedApple(Apple):
    color = (220, 40, 40)
    spawn_weight = 10

    def on_eaten(self, game):
        game.snake.grow(1)
        game.score += 1


class GoldenApple(Apple):
    color = (255, 200, 0)
    spawn_weight = 2

    def on_eaten(self, game):
        game.snake.grow(3)
        game.score += 5


class SpeedApple(Apple):
    color = (60, 140, 255)
    spawn_weight = 2

    def on_eaten(self, game):
        game.snake.grow(1)
        game.score += 2
        game.speed += 2


APPLE_TYPES = [RedApple, GoldenApple, SpeedApple]
