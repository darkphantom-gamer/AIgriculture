#!/usr/bin/env python3
"""
Meshtastic -> FLORA bridge for AIgriculture.

This script listens for Meshtastic text packets and forwards them to the
existing dashboard FLORA API. It does not import or modify FLORA internals.
Replies are sent back to the sender on the same channel as short LoRa-safe
messages.
"""

from __future__ import annotations

import argparse
import html
import os
import re
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from meshtastic.tcp_interface import TCPInterface
from pubsub import pub


_HOME = Path.home()
DEFAULT_DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://127.0.0.1:8000")
DEFAULT_USER = os.getenv("ADMIN_USER", "FarmAdmin")
DEFAULT_PASS = os.getenv("ADMIN_PASS", "Admin@farm")
DEFAULT_ALLOWED_NODE = os.getenv("MESHTASTIC_ALLOWED_NODE", "")
DEFAULT_MODE = "cloud"
DEFAULT_MAX_CHARS = 180
DEFAULT_MAX_PARTS = 2
DEFAULT_TIMEOUT = 75
DEFAULT_LOG = os.getenv("MESHTASTIC_LOG", str(_HOME / "meshtastic_flora_bridge.log"))
DEFAULT_ENV = os.getenv("MESHTASTIC_ENV", str(_HOME / "meshtastic_flora_bridge.env"))

BOT_PREFIX = "FLORA:"
RECENT_TTL_SECONDS = 45
MIN_SECONDS_BETWEEN_REQUESTS = 3


@dataclass
class BridgeConfig:
    dashboard_url: str = DEFAULT_DASHBOARD_URL
    username: str = DEFAULT_USER
    password: str = DEFAULT_PASS
    allowed_nodes: set[str] | None = None
    flora_mode: str = DEFAULT_MODE
    reply_max_chars: int = DEFAULT_MAX_CHARS
    reply_max_parts: int = DEFAULT_MAX_PARTS
    request_timeout: int = DEFAULT_TIMEOUT
    log_file: str = DEFAULT_LOG
    meshtastic_host: str = "localhost"
    reply_mode: str = "direct"      # "direct" = DM the sender; "channel" = broadcast on the channel
    channel_index: int = -1         # only listen/reply on this channel index (-1 = any)


def load_env_file(path: str) -> dict[str, str]:
    values: dict[str, str] = {}
    env_path = Path(path)
    if not env_path.exists():
        return values

    for raw in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def build_config(env_path: str = DEFAULT_ENV) -> BridgeConfig:
    file_env = load_env_file(env_path)
    merged = dict(file_env)
    merged.update({k: v for k, v in os.environ.items() if k.startswith("MESH_") or k.startswith("DASHBOARD_")})

    allowed_raw = merged.get("MESH_ALLOWED_NODES", DEFAULT_ALLOWED_NODE).strip()
    allowed_nodes = None
    if allowed_raw and allowed_raw.lower() not in {"all", "*"}:
        allowed_nodes = {node.strip() for node in allowed_raw.split(",") if node.strip()}

    try:
        channel_index = int(merged.get("MESH_CHANNEL_INDEX", "-1"))
    except (TypeError, ValueError):
        channel_index = -1

    return BridgeConfig(
        dashboard_url=merged.get("DASHBOARD_URL", DEFAULT_DASHBOARD_URL).rstrip("/"),
        username=merged.get("DASHBOARD_USER", DEFAULT_USER),
        password=merged.get("DASHBOARD_PASS", DEFAULT_PASS),
        allowed_nodes=allowed_nodes,
        flora_mode=merged.get("MESH_FLORA_MODE", DEFAULT_MODE),
        reply_max_chars=max(80, int(merged.get("MESH_REPLY_MAX_CHARS", DEFAULT_MAX_CHARS))),
        reply_max_parts=max(1, int(merged.get("MESH_REPLY_MAX_PARTS", DEFAULT_MAX_PARTS))),
        request_timeout=max(10, int(merged.get("MESH_CLOUD_TIMEOUT", DEFAULT_TIMEOUT))),
        log_file=merged.get("MESH_LOG", DEFAULT_LOG),
        meshtastic_host=merged.get("MESH_HOST", "localhost"),
        reply_mode=merged.get("MESH_REPLY_MODE", "direct").strip().lower(),
        channel_index=channel_index,
    )


def log(config: BridgeConfig, message: str) -> None:
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{stamp}] {message}"
    print(line, flush=True)
    try:
        Path(config.log_file).parent.mkdir(parents=True, exist_ok=True)
        with open(config.log_file, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def clean_for_lora(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[*_`#>\[\]]", "", text)
    text = re.sub(r"https?://\S+", "", text)
    text = text.replace("\r", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()

    # Meshtastic handles UTF-8, but plain ASCII is safer over low-bandwidth LoRa.
    text = text.encode("ascii", "ignore").decode("ascii")
    return text.strip()


def split_reply(text: str, max_chars: int, max_parts: int) -> list[str]:
    text = clean_for_lora(text)
    if not text:
        text = "No response from FLORA."

    budget = max_chars - len(BOT_PREFIX) - 1
    max_total = budget * max_parts
    if len(text) > max_total:
        text = text[: max(0, max_total - 3)].rstrip() + "..."

    parts: list[str] = []
    remaining = text
    while remaining and len(parts) < max_parts:
        if len(remaining) <= budget:
            parts.append(remaining)
            break

        split_at = remaining.rfind(" ", 0, budget)
        if split_at < 60:
            split_at = budget
        parts.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()

    if len(parts) == 1:
        return [f"{BOT_PREFIX} {parts[0]}"]
    return [f"{BOT_PREFIX} ({idx + 1}/{len(parts)}) {part}" for idx, part in enumerate(parts)]


class FloraClient:
    def __init__(self, config: BridgeConfig) -> None:
        self.config = config
        self.session = requests.Session()
        self.logged_in = False

    def login(self) -> None:
        resp = self.session.post(
            f"{self.config.dashboard_url}/auth/login",
            data={"username": self.config.username, "password": self.config.password},
            timeout=8,
        )
        if resp.status_code not in {200, 302}:
            raise RuntimeError(f"dashboard login failed: HTTP {resp.status_code}")
        self.logged_in = True

    def ask(self, text: str) -> str:
        if not self.logged_in:
            self.login()

        # Send the RAW user message (no wrapper) so FLORA's intent detection and
        # deterministic action execution see exactly what the user typed. The
        # `brief` flag tells FLORA to keep the reply to one short radio sentence.
        payload = {"content": text, "mode": self.config.flora_mode, "brief": True}
        resp = self.session.post(
            f"{self.config.dashboard_url}/api/flora/chat",
            json=payload,
            timeout=self.config.request_timeout,
        )
        if resp.status_code == 401:
            self.logged_in = False
            self.login()
            resp = self.session.post(
                f"{self.config.dashboard_url}/api/flora/chat",
                json=payload,
                timeout=self.config.request_timeout,
            )
        resp.raise_for_status()

        data = resp.json()
        answer = (data.get("response") or "").strip()
        if answer:
            return answer

        for event in reversed(data.get("events", [])):
            if event.get("type") == "response" and event.get("content"):
                return str(event["content"])
            if event.get("type") == "tool_result" and event.get("result"):
                return str(event["result"])
        return "FLORA completed the request."


class MeshtasticFloraBridge:
    def __init__(self, config: BridgeConfig) -> None:
        self.config = config
        self.client = FloraClient(config)
        self.interface: TCPInterface | None = None
        self.recent_packets: dict[str, float] = {}
        self.last_sender_time: dict[str, float] = {}
        self.lock = threading.Lock()
        self._conn_lost = threading.Event()

    def packet_key(self, packet: dict[str, Any], sender: str, text: str, channel: int) -> str:
        packet_id = packet.get("id")
        if packet_id is not None:
            return f"id:{packet_id}"
        return f"{sender}:{channel}:{text}:{int(time.time() // 15)}"

    def should_ignore(self, packet: dict[str, Any], sender: str, text: str, channel: int) -> bool:
        if not text or text.startswith(BOT_PREFIX) or text.lower().startswith("/noreply"):
            return True
        if sender in {"!62b6e9f7", "!67c2eb08"}:
            return True
        if self.config.allowed_nodes is not None and sender not in self.config.allowed_nodes:
            log(self.config, f"ignored message from unauthorized node {sender}")
            return True
        if self.config.channel_index >= 0 and channel != self.config.channel_index:
            log(self.config, f"ignored message on channel {channel} "
                             f"(FLORA only answers on channel {self.config.channel_index})")
            return True

        now = time.time()
        key = self.packet_key(packet, sender, text, channel)
        with self.lock:
            self.recent_packets = {k: v for k, v in self.recent_packets.items() if now - v < RECENT_TTL_SECONDS}
            if key in self.recent_packets:
                return True
            self.recent_packets[key] = now

            last = self.last_sender_time.get(sender, 0)
            if now - last < MIN_SECONDS_BETWEEN_REQUESTS:
                log(self.config, f"rate-limited message from {sender}")
                return True
            self.last_sender_time[sender] = now
        return False

    def send_parts(self, sender: str, channel: int, parts: list[str]) -> None:
        if self.interface is None:
            raise RuntimeError("Meshtastic interface is not connected")
        # Always reply on the SAME channel the request arrived on, so the
        # conversation stays in that channel (never crosses to another).
        for part in parts:
            if self.config.reply_mode == "channel":
                # Broadcast back on the originating channel.
                self.interface.sendText(part, channelIndex=channel, wantAck=False)
            else:
                # Direct reply to the requesting device, on its channel.
                self.interface.sendText(part, destinationId=sender, channelIndex=channel, wantAck=False)
            log(self.config, f"replied ({self.config.reply_mode}) to {sender} ch={channel}: {part}")
            time.sleep(1.2)

    def handle_message(self, packet: dict[str, Any], interface: TCPInterface) -> None:
        decoded = packet.get("decoded") or {}
        text = str(decoded.get("text") or "").strip()
        sender = str(packet.get("fromId") or packet.get("from") or "unknown")
        channel = int(packet.get("channel") or 0)

        if self.should_ignore(packet, sender, text, channel):
            return

        log(self.config, f"message from {sender} ch={channel}: {text}")
        try:
            response = self.client.ask(text)
        except Exception as exc:  # Keep bridge alive even if dashboard/cloud fails.
            log(self.config, f"FLORA request failed: {type(exc).__name__}: {exc}")
            response = "FLORA is temporarily unavailable. Dashboard or cloud may be busy; try again shortly."

        parts = split_reply(response, self.config.reply_max_chars, self.config.reply_max_parts)
        try:
            self.send_parts(sender, channel, parts)
        except Exception as exc:
            log(self.config, f"send failed: {type(exc).__name__}: {exc}")

    def _on_connection_lost(self, interface: TCPInterface | None = None) -> None:
        # Published by the meshtastic library when the TCP link to meshtasticd drops.
        # We can't reconnect a dead TCPInterface in place, so exit and let the
        # supervisor (systemd Restart=always) respawn us with a fresh connection.
        log(self.config, "meshtastic connection lost; exiting for supervisor restart")
        self._conn_lost.set()

    def start(self) -> None:
        log(self.config, f"connecting to Meshtastic TCP host {self.config.meshtastic_host}")
        self.interface = TCPInterface(hostname=self.config.meshtastic_host)
        pub.subscribe(self.handle_message, "meshtastic.receive.text")
        pub.subscribe(self._on_connection_lost, "meshtastic.connection.lost")
        allowed = "all nodes" if self.config.allowed_nodes is None else ",".join(sorted(self.config.allowed_nodes))
        chan = "any" if self.config.channel_index < 0 else str(self.config.channel_index)
        log(self.config, f"bridge ready; allowed={allowed}; channel={chan}; reply={self.config.reply_mode}; "
                         f"dashboard={self.config.dashboard_url}; mode={self.config.flora_mode}")
        try:
            while not self._conn_lost.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            log(self.config, "bridge stopped by keyboard interrupt")
            return
        finally:
            try:
                self.interface.close()
            except Exception:
                pass
        # Only reached when the link was lost: signal a restart to the supervisor.
        raise SystemExit(1)


def run_self_test(config: BridgeConfig, message: str) -> int:
    log(config, f"self-test request: {message}")
    try:
        response = FloraClient(config).ask(message)
    except Exception as exc:
        print(f"SELF_TEST_FAILED: {type(exc).__name__}: {exc}")
        return 1
    parts = split_reply(response, config.reply_max_chars, config.reply_max_parts)
    print("FLORA_RESPONSE:")
    print(clean_for_lora(response))
    print("LORA_PARTS:")
    for part in parts:
        print(part)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Bridge Meshtastic messages to FLORA.")
    parser.add_argument("--env", default=DEFAULT_ENV, help="Path to optional env config file.")
    parser.add_argument("--self-test", nargs="?", const="farm status short", help="Call FLORA once and print LoRa-safe reply.")
    args = parser.parse_args()

    config = build_config(args.env)
    if args.self_test is not None:
        return run_self_test(config, args.self_test)

    MeshtasticFloraBridge(config).start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
