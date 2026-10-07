"""Apple types for Snake.

To add your own apple:
    1. Subclass Apple.
    2. Set `color` (and optionally `spawn_weight`).
    3. Implement `on_eaten(self, game)` to do whatever you like to the game.
    4. Add the class to APPLE_TYPES at the bottom of this file.

`game` exposes:
    game.snake.grow(n)   - add n segments
    game.snake.shrink(n) - remove n segments (never below 1)
    game.quantum.add_ghost() - add a ghost-block qubit to the circuit
    game.quantum.apply_green_apple() - apply a random Y rotation to all qubits
    game.quantum.measure() - measure and resolve all ghost-block qubits
    game.score           - number of concrete snake blocks
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
        ghost_id = game.quantum.add_ghost()
        game.snake.grow(1, ghost_id=ghost_id)


class GreenApple(Apple):
    color = (50, 180, 70)
    spawn_weight = 2

    def on_eaten(self, game):
        game.quantum.apply_green_apple()


class BlackApple(Apple):
    color = (10, 10, 10)
    spawn_weight = 2

    def draw(self, surface, cell_size):
        x, y = self.position
        rect = pygame.Rect(x * cell_size, y * cell_size, cell_size, cell_size)
        pygame.draw.ellipse(surface, self.color, rect)
        pygame.draw.ellipse(surface, (220, 220, 220), rect, 2)

    def on_eaten(self, game):
        game.collapse_ghosts()


APPLE_TYPES = [RedApple, GreenApple, BlackApple]
