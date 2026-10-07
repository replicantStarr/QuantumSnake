"""LAN multiplayer: server discovery over UDP broadcast, gameplay over WebSockets.

The host is authoritative: it runs the World and sends a snapshot after every
step. Clients only send their steering input. All socket work happens on
background threads; the game thread talks to them through `poll()` (drain
incoming events) and `send()`/`broadcast()` (queue outgoing JSON messages).

Messages (JSON objects with a "type"):
    client -> host: hello {game, version, name}, input {dir}
    host -> client: welcome {player_id}, rejected {reason}, lobby {players},
                    start {world, countdown}, state {world, events}, return_to_lobby
"""

import asyncio
import json
import queue
import socket
import threading
import time
import uuid

import websockets
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve

from settings import MAX_NAME_LENGTH

GAME_ID = "quantum-snake"
PROTOCOL_VERSION = 1
GAME_PORT = 47800
DISCOVERY_PORT = 47801
BEACON_INTERVAL = 1.0
SERVER_TIMEOUT = 3.5  # seconds without a beacon before a server drops off the list
MAX_PLAYERS = 2
HOST_PLAYER_ID = 0


def local_ip():
    """Best guess at this machine's LAN address (no packets are sent)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))  # picks the default-route interface
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def _broadcast_targets():
    targets = {"255.255.255.255", "127.0.0.1"}
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if not ip.startswith("127."):
                targets.add(ip.rsplit(".", 1)[0] + ".255")  # assumes a /24 network
    except OSError:
        pass
    return targets


class _LoopThread:
    """An asyncio event loop running on a daemon thread."""

    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self._thread.start()

    def run(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def call(self, fn, *args):
        self.loop.call_soon_threadsafe(fn, *args)

    def stop(self):
        self.loop.call_soon_threadsafe(self.loop.stop)


class Host:
    """Accepts players over WebSockets and announces itself on the LAN."""

    def __init__(self, name):
        self.name = name
        self.id = uuid.uuid4().hex
        self.players = {HOST_PLAYER_ID: name}  # player id -> name, in join order
        self.in_game = False
        self._events = queue.Queue()
        self._outboxes = {}  # player id -> asyncio.Queue (loop thread only)
        self._next_id = HOST_PLAYER_ID + 1
        self._loop = _LoopThread()
        try:
            self.port = self._loop.run(self._start()).result(timeout=5)
        except Exception:
            self._loop.stop()
            raise
        self.address = local_ip()
        self._stop_beacon = threading.Event()
        threading.Thread(target=self._beacon, daemon=True).start()

    async def _start(self):
        try:
            self._server = await serve(self._handle, "0.0.0.0", GAME_PORT)
        except OSError:
            self._server = await serve(self._handle, "0.0.0.0", 0)  # preferred port busy: any free one
        return self._server.sockets[0].getsockname()[1]

    async def _handle(self, ws):
        player_id = None
        outbox = asyncio.Queue()
        sender = asyncio.create_task(self._send_loop(ws, outbox))
        try:
            hello = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            if hello.get("type") != "hello" or hello.get("game") != GAME_ID:
                return
            if hello.get("version") != PROTOCOL_VERSION:
                await ws.send(json.dumps({"type": "rejected", "reason": "Game versions don't match"}))
                return
            player_id = self._next_id
            self._next_id += 1
            self._outboxes[player_id] = outbox
            name = str(hello.get("name") or "Player")[:MAX_NAME_LENGTH]
            self._events.put(("hello", player_id, name))
            async for raw in ws:
                self._events.put(("message", player_id, json.loads(raw)))
        except (websockets.ConnectionClosed, asyncio.TimeoutError, ValueError):
            pass
        finally:
            sender.cancel()
            if player_id is not None:
                self._outboxes.pop(player_id, None)
                self._events.put(("closed", player_id, None))

    @staticmethod
    async def _send_loop(ws, outbox):
        try:
            while (data := await outbox.get()) is not None:
                await ws.send(data)
            await ws.close()
        except websockets.ConnectionClosed:
            pass

    def _queue(self, player_id, data):
        outbox = self._outboxes.get(player_id)
        if outbox:
            outbox.put_nowait(data)

    def send(self, player_id, message):
        self._loop.call(self._queue, player_id, json.dumps(message))

    def broadcast(self, message):
        data = json.dumps(message)
        for player_id in self.players:
            if player_id != HOST_PLAYER_ID:
                self._loop.call(self._queue, player_id, data)

    def kick(self, player_id):
        self._loop.call(self._queue, player_id, None)

    def broadcast_lobby(self):
        self.broadcast({"type": "lobby", "players": [{"id": pid, "name": n} for pid, n in self.players.items()]})

    def poll(self):
        """Handle joins and leaves; returns [(kind, player_id, data)] for "joined", "left" and "message"."""
        out = []
        while True:
            try:
                kind, player_id, data = self._events.get_nowait()
            except queue.Empty:
                return out
            if kind == "hello":
                if self.in_game or len(self.players) >= MAX_PLAYERS:
                    reason = "That game has already started" if self.in_game else "That game is full"
                    self.send(player_id, {"type": "rejected", "reason": reason})
                    self.kick(player_id)
                    continue
                self.players[player_id] = data
                self.send(player_id, {"type": "welcome", "player_id": player_id})
                self.broadcast_lobby()
                out.append(("joined", player_id, data))
            elif kind == "closed" and player_id in self.players:
                name = self.players.pop(player_id)
                self.broadcast_lobby()
                out.append(("left", player_id, name))
            elif kind == "message" and player_id in self.players:
                out.append(("message", player_id, data))

    def _beacon(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            targets = _broadcast_targets()
            while not self._stop_beacon.is_set():
                beacon = json.dumps({
                    "game": GAME_ID, "version": PROTOCOL_VERSION, "id": self.id, "name": self.name,
                    "port": self.port, "players": len(self.players), "max": MAX_PLAYERS, "in_game": self.in_game,
                }).encode()
                for target in targets:
                    try:
                        sock.sendto(beacon, (target, DISCOVERY_PORT))
                    except OSError:
                        pass
                self._stop_beacon.wait(BEACON_INTERVAL)

    def close(self):
        self._stop_beacon.set()

        async def shutdown():
            self._server.close()
            await self._server.wait_closed()

        try:
            self._loop.run(shutdown()).result(timeout=2)
        except Exception:
            pass
        self._loop.stop()


class Client:
    """A connection to a Host. Check `poll()` for "message" and "closed" events."""

    def __init__(self, address, port, name):
        self.address = address
        self.port = port
        self.player_id = None
        self.lobby_players = []
        self.connected = False
        self._events = queue.Queue()
        self._outbox = None
        self._ws = None
        self._rejected_reason = None
        self._requeued = []
        self._loop = _LoopThread()
        self._task = self._loop.run(self._main(name))

    async def _main(self, name):
        self._outbox = asyncio.Queue()
        try:
            async with connect(f"ws://{self.address}:{self.port}", open_timeout=5) as ws:
                self._ws = ws
                await ws.send(json.dumps({"type": "hello", "game": GAME_ID, "version": PROTOCOL_VERSION, "name": name}))
                sender = asyncio.create_task(Host._send_loop(ws, self._outbox))
                try:
                    async for raw in ws:
                        self._events.put(("message", json.loads(raw)))
                finally:
                    sender.cancel()
            reason = "The host closed the game"
        except websockets.ConnectionClosed:
            reason = "Lost connection to the host"
        except (OSError, asyncio.TimeoutError, websockets.InvalidHandshake, websockets.InvalidURI, ValueError):
            reason = f"Couldn't connect to {self.address}:{self.port}"
        self._events.put(("closed", reason))

    def send(self, message):
        data = json.dumps(message)
        self._loop.call(lambda: self._outbox and self._outbox.put_nowait(data))

    def poll(self):
        """Returns [(kind, data)]: ("message", msg) for game messages, ("closed", reason) when disconnected."""
        out, self._requeued = self._requeued, []
        while True:
            try:
                kind, data = self._events.get_nowait()
            except queue.Empty:
                return out
            if kind == "message":
                msg_type = data.get("type")
                if msg_type == "welcome":
                    self.player_id = data["player_id"]
                    self.connected = True
                elif msg_type == "rejected":
                    self._rejected_reason = data.get("reason")
                elif msg_type == "lobby":
                    self.lobby_players = data["players"]
            elif kind == "closed" and self._rejected_reason:
                data = self._rejected_reason
            out.append((kind, data))

    def requeue(self, events):
        """Put already-polled events back so the next poll() returns them first."""
        self._requeued = list(events) + self._requeued

    def close(self):
        async def shutdown():
            if self._ws:
                await self._ws.close()

        try:
            self._loop.run(shutdown()).result(timeout=1)
        except Exception:
            pass
        self._task.cancel()
        self._loop.stop()


class Discovery:
    """Listens for Host beacons. `servers()` lists the hosts heard from recently."""

    def __init__(self):
        self.error = None
        self._servers = {}  # host id -> info dict
        self._lock = threading.Lock()
        self._stop = threading.Event()
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.bind(("", DISCOVERY_PORT))
            self._sock.settimeout(0.5)
        except OSError as e:
            self.error = str(e)
            return
        threading.Thread(target=self._listen, daemon=True).start()

    def _listen(self):
        while not self._stop.is_set():
            try:
                raw, (address, _) = self._sock.recvfrom(4096)
                info = json.loads(raw)
            except (socket.timeout, ValueError):
                continue
            except OSError:
                break
            if not isinstance(info, dict) or info.get("game") != GAME_ID or "id" not in info:
                continue
            with self._lock:
                existing = self._servers.get(info["id"])
                # The same host can be heard over loopback and the LAN; prefer the LAN address.
                if existing and address.startswith("127.") and not existing["address"].startswith("127."):
                    address = existing["address"]
                info.update(address=address, seen=time.monotonic())
                self._servers[info["id"]] = info

    def servers(self):
        now = time.monotonic()
        with self._lock:
            return sorted(
                (s for s in self._servers.values() if now - s["seen"] < SERVER_TIMEOUT),
                key=lambda s: (s["name"].lower(), s["id"]),
            )

    def close(self):
        self._stop.set()
        if not self.error:
            self._sock.close()
