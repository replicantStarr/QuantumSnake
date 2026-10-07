"""Multiplayer menus: finding a game, and the lobby before it starts."""

import graphics as gfx
import render
from game import ClientSession, GameScene
from menu import Button, InfoRow, MenuScene, TextInput
from network import GAME_PORT, HOST_PLAYER_ID, MAX_PLAYERS, Discovery

IP_CHARACTERS = "0123456789.:abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ-"


def player_rows(players, local_id=None):
    """Lobby slots: one row per player (in their snake's colour), padded with empty slots."""
    rows = []
    for index in range(MAX_PLAYERS):
        if index < len(players):
            player = players[index]
            label = f"Player {index + 1}" + ("  (you)" if player["id"] == local_id else "")
            color = render.SNAKE_PALETTES[index % len(render.SNAKE_PALETTES)][0]
            row = InfoRow(label, player["name"], color)
        else:
            row = InfoRow(f"Player {index + 1}", "Waiting for player…", gfx.TEXT_DIM)
        row.key = f"slot{index}"
        rows.append(row)
    return rows


class ServerBrowser(MenuScene):
    title = "JOIN GAME"
    item_width = 600

    def __init__(self, app):
        super().__init__(app)
        self.discovery = Discovery()
        self.servers = []
        self._servers_key = None
        self.ip_input = TextInput(
            "Join by IP", on_submit=self.join_by_ip, max_length=40,
            allowed=IP_CHARACTERS, placeholder="192.168.1.20",
        )
        self.refresh()

    @property
    def subtitle(self):
        if self.discovery.error:
            return "Can't search the network right now. Join by IP instead."
        if not self.servers:
            return "Searching your network for games…"
        return "Games on your network"

    def refresh(self):
        self.servers = self.discovery.servers()
        key = [(s["id"], s["name"], s["players"], s["in_game"]) for s in self.servers]
        if key == self._servers_key:
            return
        first_servers = not self._servers_key and self.servers
        self._servers_key = key
        items = []
        for server in self.servers:
            joinable = not server["in_game"] and server["players"] < server["max"]
            status = "In game" if server["in_game"] else f"{server['players']}/{server['max']} players"
            button = Button(server["name"], lambda s=server: self.app.join_game(s["address"], s["port"]), detail=status, enabled=joinable)
            button.key = server["id"]
            items.append(button)
        self.set_items(items + [self.ip_input, Button("Back", self.back)])
        if first_servers:
            self.selected = 0
            self._ensure_selectable()

    def join_by_ip(self):
        text = self.ip_input.text.strip()
        if not text:
            return
        address, _, port = text.partition(":")
        if port and not port.isdigit():
            self.app.show_notice("That port isn't a number")
            return
        self.app.join_game(address, int(port) if port else GAME_PORT)

    def update(self, dt):
        self.refresh()
        super().update(dt)

    def back(self):
        self.app.show_main_menu()

    def close(self):
        self.discovery.close()


class HostLobby(MenuScene):
    title = "LOBBY"
    item_width = 600

    def __init__(self, app):
        super().__init__(app)
        self.host = app.host
        self.build_items()

    @property
    def subtitle(self):
        return f"Hosting on {self.host.address}:{self.host.port}"

    def build_items(self):
        players = [{"id": pid, "name": name} for pid, name in self.host.players.items()]
        ready = len(players) >= MAX_PLAYERS
        start = Button("Start Game" if ready else "Waiting for a player…", self.app.start_hosted_game, enabled=ready)
        start.key = "start"
        was_ready = getattr(self, "_ready", False)
        self._ready = ready
        self.set_items(player_rows(players, local_id=HOST_PLAYER_ID) + [start, Button("Close Lobby", self.back)])
        if ready and not was_ready:
            self.selected = self.items.index(start)

    def update(self, dt):
        if any(kind in ("joined", "left") for kind, _, _ in self.host.poll()):
            self.build_items()
        super().update(dt)

    def back(self):
        self.app.show_main_menu()


class ClientLobby(MenuScene):
    title = "LOBBY"
    item_width = 600

    def __init__(self, app):
        super().__init__(app)
        self.client = app.client
        self.build_items()

    @property
    def subtitle(self):
        if not self.client.connected:
            return f"Connecting to {self.client.address}:{self.client.port}…"
        return "Waiting for the host to start the game…"

    def build_items(self):
        rows = player_rows(self.client.lobby_players, local_id=self.client.player_id) if self.client.connected else []
        self.set_items(rows + [Button("Leave", self.back)])

    def update(self, dt):
        events = self.client.poll()
        for i, (kind, data) in enumerate(events):
            if kind == "closed":
                self.app.show_server_browser(notice=data)
                return
            if data.get("type") == "start":
                self.client.requeue(events[i + 1:])  # e.g. the first state update
                self.app.set_scene(GameScene(self.app, ClientSession(self.app, data)))
                return
            if data.get("type") in ("welcome", "lobby"):
                self.build_items()
        super().update(dt)

    def back(self):
        self.app.show_server_browser()
