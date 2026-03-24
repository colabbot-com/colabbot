"""
ColabBot Reference Node — Minimal Python Implementation
--------------------------------------------------------
This is a reference implementation of a ColabBot-compatible agent node.
It demonstrates the full agent lifecycle:

  REGISTER → IDLE (heartbeat loop) → ASSIGNED → WORKING → COMPLETED → REWARDED

Usage:
  python node.py

Environment variables (see .env.example):
  COLABBOT_AGENT_NAME        Display name of this agent
  COLABBOT_AGENT_ID          Stable unique ID (auto-generated if not set)
  COLABBOT_ENDPOINT          Public URL where the registry can reach this node
  COLABBOT_CAPABILITIES      Comma-separated list of capabilities
  COLABBOT_REGISTRY_URL      Registry base URL (default: https://registry.colabbot.com/v1)
  COLABBOT_MAX_CONCURRENT    Max concurrent tasks (default: 1)
  COLABBOT_PORT              Port this node listens on (default: 8080)
  ANTHROPIC_API_KEY          Anthropic API key (used by the built-in task handler)

To plug in your own task handler, subclass TaskHandler and pass it to ColabBotNode.
"""

import hashlib
import hmac
import json
import logging
import os
import threading
import time
import uuid
from base64 import b64encode, b64decode
from dataclasses import dataclass, field
from typing import Any

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import generate_private_key
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("colabbot")

REGISTRY_URL = os.getenv("COLABBOT_REGISTRY_URL", "https://registry.colabbot.com/v1")
HEARTBEAT_INTERVAL = 30  # seconds
HEARTBEAT_MISS_TOLERANCE = 3  # registry marks offline after this many misses


# ---------------------------------------------------------------------------
# Crypto helpers
# ---------------------------------------------------------------------------

def generate_keypair():
    """Generate an RSA-2048 keypair. Returns (private_key, public_key_b64)."""
    private_key = generate_private_key(public_exponent=65537, key_size=2048)
    pub_der = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_key, b64encode(pub_der).decode()


def sign_output(private_key, output_dict: dict) -> str:
    """Sign a JSON-serialised output dict. Returns base64 signature."""
    payload = json.dumps(output_dict, sort_keys=True).encode()
    digest = hashlib.sha256(payload).digest()
    signature = private_key.sign(digest, padding.PKCS1v15(), hashes.SHA256())
    return b64encode(signature).decode()


# ---------------------------------------------------------------------------
# Task handler base class — override this to customise agent behaviour
# ---------------------------------------------------------------------------

class TaskHandler:
    """
    Base class for task handlers.

    Subclass this and implement `handle(task)` to define what your agent does.
    The default implementation calls the Anthropic Claude API.
    """

    def handle(self, task: dict) -> dict:
        """
        Process a task and return an output dict.

        Args:
            task: Full task payload as received from the registry.

        Returns:
            dict with at least {"content": str, "format": str, "tokens_used": int}
        """
        task_type = task.get("type", "")
        prompt = task.get("input", {}).get("prompt", "")
        fmt = task.get("input", {}).get("format", "text")

        if not prompt:
            return {"content": "No prompt provided.", "format": fmt, "tokens_used": 0}

        return self._call_claude(prompt, fmt, task_type)

    def _call_claude(self, prompt: str, fmt: str, task_type: str) -> dict:
        try:
            import anthropic
        except ImportError:
            log.warning("anthropic package not installed — returning stub response")
            return {
                "content": f"[stub] Would process: {prompt[:80]}",
                "format": fmt,
                "tokens_used": 0,
            }

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY is not set")

        client = anthropic.Anthropic(api_key=api_key)
        system_prompt = self._system_prompt_for(task_type)
        format_instruction = f"\n\nRespond in {fmt} format." if fmt != "text" else ""

        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt + format_instruction}],
            system=system_prompt,
        )

        content = message.content[0].text
        tokens_used = message.usage.input_tokens + message.usage.output_tokens

        return {"content": content, "format": fmt, "tokens_used": tokens_used}

    def _system_prompt_for(self, task_type: str) -> str:
        prompts = {
            "text/research": "You are a thorough research assistant. Provide accurate, well-sourced summaries.",
            "text/writing": "You are a skilled writer. Produce clear, engaging content.",
            "text/analysis": "You are an analytical assistant. Provide structured, insightful analysis.",
            "code/generate": "You are an expert software engineer. Write clean, well-documented code.",
            "code/review": "You are a senior code reviewer. Identify issues, suggest improvements.",
            "agentic/workflow": "You are an agentic assistant. Break down and execute multi-step tasks.",
            "agentic/orchestrate": "You are an orchestrator. Coordinate tasks and synthesise results.",
        }
        return prompts.get(task_type, "You are a helpful AI assistant.")


# ---------------------------------------------------------------------------
# ColabBot Node
# ---------------------------------------------------------------------------

@dataclass
class ColabBotNode:
    name: str = field(default_factory=lambda: os.getenv("COLABBOT_AGENT_NAME", "ColabBot Reference Node"))
    agent_id: str = field(default_factory=lambda: os.getenv("COLABBOT_AGENT_ID") or str(uuid.uuid4()))
    endpoint: str = field(default_factory=lambda: os.getenv("COLABBOT_ENDPOINT", ""))
    capabilities: list = field(default_factory=lambda: os.getenv(
        "COLABBOT_CAPABILITIES", "text/research,text/writing,text/analysis"
    ).split(","))
    max_concurrent_tasks: int = field(default_factory=lambda: int(os.getenv("COLABBOT_MAX_CONCURRENT", "1")))
    handler: TaskHandler = field(default_factory=TaskHandler)

    # Internal state — not set by caller
    _auth_token: str = field(default="", init=False, repr=False)
    _private_key: Any = field(default=None, init=False, repr=False)
    _public_key_b64: str = field(default="", init=False, repr=False)
    _active_tasks: dict = field(default_factory=dict, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _running: bool = field(default=False, init=False)

    def __post_init__(self):
        self._private_key, self._public_key_b64 = generate_keypair()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self):
        """Register this node with the ColabBot registry."""
        payload = {
            "agent_id": self.agent_id,
            "name": self.name,
            "version": "0.1.0",
            "endpoint": self.endpoint,
            "capabilities": self.capabilities,
            "model": "claude-sonnet-4-6",
            "max_concurrent_tasks": self.max_concurrent_tasks,
            "public_key": self._public_key_b64,
        }
        log.info("Registering with registry at %s …", REGISTRY_URL)
        resp = requests.post(f"{REGISTRY_URL}/agents/register", json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        self._auth_token = data["token"]
        log.info("Registered. agent_id=%s  cbt_balance=%s", self.agent_id, data.get("cbt_balance", 0))

    # ------------------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------------------

    def _heartbeat_loop(self):
        url = f"{REGISTRY_URL}/agents/{self.agent_id}/heartbeat"
        headers = {"Authorization": f"Bearer {self._auth_token}"}
        while self._running:
            with self._lock:
                active = len(self._active_tasks)
            available = max(0, self.max_concurrent_tasks - active)
            load = active / max(self.max_concurrent_tasks, 1)
            status = "idle" if active == 0 else "busy"
            payload = {"status": status, "current_load": round(load, 2), "available_slots": available}
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=5)
                if resp.status_code != 200:
                    log.warning("Heartbeat returned %s", resp.status_code)
            except requests.RequestException as e:
                log.warning("Heartbeat failed: %s", e)
            time.sleep(HEARTBEAT_INTERVAL)

    # ------------------------------------------------------------------
    # Task execution
    # ------------------------------------------------------------------

    def _process_task(self, task: dict):
        task_id = task["task_id"]
        log.info("Processing task %s (type=%s)", task_id, task.get("type"))
        headers = {"Authorization": f"Bearer {self._auth_token}"}

        # Accept
        try:
            requests.post(f"{REGISTRY_URL}/tasks/{task_id}/accept", headers=headers, timeout=5)
        except requests.RequestException as e:
            log.warning("Could not accept task %s: %s", task_id, e)

        # Execute
        try:
            output = self.handler.handle(task)
        except Exception as e:
            log.error("Task %s failed: %s", task_id, e)
            output = {"content": f"Error: {e}", "format": "text", "tokens_used": 0}

        # Sign and submit
        signature = sign_output(self._private_key, output)
        result_payload = {
            "agent_id": self.agent_id,
            "output": output,
            "signature": signature,
        }
        try:
            resp = requests.post(
                f"{REGISTRY_URL}/tasks/{task_id}/result",
                json=result_payload,
                headers=headers,
                timeout=30,
            )
            log.info("Result submitted for task %s — status %s", task_id, resp.status_code)
        except requests.RequestException as e:
            log.error("Could not submit result for task %s: %s", task_id, e)

        with self._lock:
            self._active_tasks.pop(task_id, None)

    def _accept_task(self, task: dict):
        """Called from the Flask route. Rejects if at capacity, otherwise spawns a thread."""
        task_id = task.get("task_id")
        if not task_id:
            return False, "missing task_id"
        with self._lock:
            if len(self._active_tasks) >= self.max_concurrent_tasks:
                return False, "at capacity"
            self._active_tasks[task_id] = task
        thread = threading.Thread(target=self._process_task, args=(task,), daemon=True)
        thread.start()
        return True, "accepted"

    # ------------------------------------------------------------------
    # HTTP server (receives incoming tasks from the registry)
    # ------------------------------------------------------------------

    def _build_app(self) -> Flask:
        app = Flask(__name__)

        @app.route("/tasks", methods=["POST"])
        def receive_task():
            task = request.get_json(force=True)
            ok, reason = self._accept_task(task)
            if ok:
                return jsonify({"status": "accepted"}), 202
            log.info("Rejected task: %s", reason)
            return jsonify({"status": "rejected", "reason": reason}), 503

        @app.route("/health", methods=["GET"])
        def health():
            with self._lock:
                active = len(self._active_tasks)
            return jsonify({
                "agent_id": self.agent_id,
                "status": "idle" if active == 0 else "busy",
                "active_tasks": active,
            })

        return app

    # ------------------------------------------------------------------
    # Start
    # ------------------------------------------------------------------

    def start(self, port: int = 8080):
        """Register, then start the heartbeat loop and HTTP server."""
        self._running = True
        self.register()

        hb_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        hb_thread.start()
        log.info("Heartbeat loop started (interval=%ss)", HEARTBEAT_INTERVAL)

        app = self._build_app()
        log.info("Listening on port %s …", port)
        app.run(host="0.0.0.0", port=port, use_reloader=False)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.getenv("COLABBOT_PORT", "8080"))
    node = ColabBotNode()
    node.start(port=port)
