"""Meshtastic LoRa bridge — chat with FLORA over a mesh radio.

General rule: whatever channel or direct message a text arrives on, FLORA
processes it and replies ONLY back to that same channel/DM — never broadcasts
elsewhere. Optional node allow-list is config-driven (blank = allow everyone).

Connects to a local `meshtasticd` daemon over TCP. Optional: the whole bridge
is skipped unless MESH_ENABLED=true.
"""

from __future__ import annotations

import re
import threading
import time
from typing import Iterable, Optional, Set

try:
    from meshtastic.tcp_interface import TCPInterface
    from pubsub import pub
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False

_MARKDOWN = re.compile(r"[*_`#>]+")
_EMOJI = re.compile(r"[^\x00-\x7F]+")


def clean_for_lora(text: str, max_chars: int = 200) -> str:
    """Strip markdown/emoji and truncate to fit a LoRa payload."""
    t = _MARKDOWN.sub("", text or "")
    t = _EMOJI.sub("", t)
    t = " ".join(t.split())
    return t[: max_chars - 1] + "…" if len(t) > max_chars else t


class MeshBridge:
    def __init__(self, state, host: str = "localhost",
                 allowed_nodes: Optional[Iterable[str]] = None, reply_max_chars: int = 200):
        self.state = state
        self.host = host
        self.allowed: Optional[Set[str]] = {n.strip() for n in allowed_nodes if n.strip()} if allowed_nodes else None
        self.reply_max_chars = reply_max_chars
        self.iface: Optional["TCPInterface"] = None
        self._my_node: Optional[int] = None
        self._stop = threading.Event()
        self._lost = threading.Event()

    def start(self) -> None:
        if not _AVAILABLE:
            print("[WARN] meshtastic lib not installed — mesh bridge disabled")
            return
        threading.Thread(target=self._run, name="mesh-bridge", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()
        self._close()

    # ── connection loop ───────────────────────────────────────────────────────
    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.iface = TCPInterface(hostname=self.host)
                self._my_node = getattr(getattr(self.iface, "myInfo", None), "my_node_num", None)
                pub.subscribe(self._on_receive, "meshtastic.receive.text")
                pub.subscribe(self._on_lost, "meshtastic.connection.lost")
                print(f"[INFO] mesh bridge connected to {self.host}")
                self._lost.clear()
                while not self._stop.is_set() and not self._lost.is_set():
                    time.sleep(1)
            except Exception as e:
                print(f"[WARN] mesh bridge connect failed: {e}")
            finally:
                self._close()
            if not self._stop.is_set():
                time.sleep(5)  # backoff before reconnect

    def _close(self) -> None:
        try:
            if self.iface:
                self.iface.close()
        except Exception:
            pass
        self.iface = None

    def _on_lost(self, interface=None) -> None:
        self._lost.set()

    # ── message handling ──────────────────────────────────────────────────────
    def _on_receive(self, packet: dict, interface=None) -> None:
        try:
            text = (packet.get("decoded") or {}).get("text", "").strip()
            if not text:
                return
            from_id = packet.get("fromId") or str(packet.get("from", ""))
            if self.allowed is not None and from_id not in self.allowed:
                return
            channel = packet.get("channel", 0)
            is_dm = self._my_node is not None and packet.get("to") == self._my_node

            reply = self.state.flora.chat(text, user=f"mesh:{from_id}")
            self._reply(clean_for_lora(reply, self.reply_max_chars), from_id, channel, is_dm)
        except Exception as e:
            print(f"[WARN] mesh handle error: {e}")

    def _reply(self, text: str, from_id: str, channel: int, is_dm: bool) -> None:
        if not self.iface or not text:
            return
        try:
            if is_dm:
                self.iface.sendText(text, destinationId=from_id)         # private reply to sender
            else:
                self.iface.sendText(text, channelIndex=channel)          # same channel only
        except Exception as e:
            print(f"[WARN] mesh send error: {e}")
