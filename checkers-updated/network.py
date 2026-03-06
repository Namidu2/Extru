"""
network.py – LAN multiplayer networking for Checkers.

Protocol (all messages are newline-terminated JSON):
  {"type": "move",    "from": [x, y], "to": [x, y]}
  {"type": "capture", "from": [x, y], "to": [x, y]}
  {"type": "ready"}      # handshake
  {"type": "ping"}       # keep-alive
  {"type": "quit"}       # opponent left
"""

import socket
import threading
import json
import queue
import time

DEFAULT_PORT = 55555
BUFFER = 4096
TIMEOUT = 120   # seconds before connection is considered dead


class Network:
    """Thread-safe wrapper around a single TCP connection."""

    def __init__(self):
        self.sock: socket.socket | None = None
        self.connected = False
        self.role = None          # "host" or "client"
        self.in_queue: queue.Queue = queue.Queue()   # messages received from peer
        self._recv_thread: threading.Thread | None = None
        self._ping_thread: threading.Thread | None = None
        self._partial = ""        # leftover bytes between packets

    # ------------------------------------------------------------------
    # Public – setup
    # ------------------------------------------------------------------

    def host(self, port=DEFAULT_PORT, status_callback=None):
        """Open a server socket and wait for one client to connect."""
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("", port))
            server.listen(1)
            server.settimeout(TIMEOUT)

            local_ip = self._get_local_ip()
            if status_callback:
                status_callback(f"Hosting on {local_ip}:{port}\nWaiting for opponent…")

            conn, addr = server.accept()
            server.close()

            self.sock = conn
            # Performance & Stability options
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            self.sock.settimeout(None)   # blocking recv in thread
            
            self.connected = True
            self.role = "host"
            self._start_threads()

            # Handshake
            self._send_raw({"type": "ready"})
            return True, addr[0]

        except socket.timeout:
            return False, "Timed out waiting for player."
        except Exception as e:
            return False, str(e)

    def join(self, host_ip: str, port=DEFAULT_PORT, status_callback=None):
        """Connect to a host."""
        try:
            if status_callback:
                status_callback(f"Connecting to {host_ip}:{port}…")

            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            self.sock.settimeout(10)
            self.sock.connect((host_ip, port))
            self.sock.settimeout(None)
            
            self.connected = True
            self.role = "client"
            self._start_threads()
            return True, ""

        except Exception as e:
            return False, str(e)

    def disconnect(self):
        """Gracefully close the connection."""
        self.connected = False
        if self.sock:
            try:
                self._send_raw({"type": "quit"})
                self.sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None

    # ------------------------------------------------------------------
    # Public – send / receive
    # ------------------------------------------------------------------

    def send_move(self, from_pos, to_pos, finished=True):
        self._send_raw({"type": "move",
                         "from": [int(from_pos.x), int(from_pos.y)],
                         "to":   [int(to_pos.x),   int(to_pos.y)],
                         "finished": finished})

    def send_capture(self, from_pos, to_pos, finished=True):
        self._send_raw({"type": "capture",
                         "from": [int(from_pos.x), int(from_pos.y)],
                         "to":   [int(to_pos.x),   int(to_pos.y)],
                         "finished": finished})

    def poll(self):
        """Return next message dict from peer, or None if queue is empty."""
        try:
            return self.in_queue.get_nowait()
        except queue.Empty:
            return None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _send_raw(self, obj: dict):
        if not self.connected or not self.sock:
            return
        try:
            # Framing: newline-delimited JSON
            data = json.dumps(obj).encode("utf-8") + b"\n"
            self.sock.sendall(data)
        except Exception as e:
            print(f"Socket send error: {e}")
            self.connected = False

    def _start_threads(self):
        self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._recv_thread.start()
        self._ping_thread = threading.Thread(target=self._ping_loop, daemon=True)
        self._ping_thread.start()

    def _ping_loop(self):
        """Send periodic pings to keep the connection alive."""
        while self.connected:
            time.sleep(5)
            if self.connected:
                self._send_raw({"type": "ping"})

    def _recv_loop(self):
        while self.connected:
            try:
                chunk = self.sock.recv(BUFFER)
                if not chunk:
                    break
                self._partial += chunk.decode("utf-8")
                while "\n" in self._partial:
                    line, self._partial = self._partial.split("\n", 1)
                    line = line.strip()
                    if line:
                        try:
                            msg = json.loads(line)
                            # Heartbeat check
                            if msg.get("type") == "ping":
                                continue  # Ignore heartbeat packets
                            
                            self.in_queue.put(msg)
                        except json.JSONDecodeError as e:
                            print(f"JSON Parsing Error on line: '{line}'. Error: {e}")
            except Exception as e:
                print(f"Socket read error or closed: {e}")
                break
        self.connected = False
        self.in_queue.put({"type": "quit"})   # notify game loop

    @staticmethod
    def _get_local_ip() -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
