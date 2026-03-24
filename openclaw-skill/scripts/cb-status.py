#!/usr/bin/env python3
"""
ColabBot — Status Script
--------------------------
Shows the current registration status, daemon state, and CBT balance.
"""

import json
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

CONFIG_FILE = Path.home() / ".colabbot" / "config.json"


def is_daemon_running():
    try:
        result = subprocess.run(["tmux", "has-session", "-t", "colabbot-daemon"],
                                capture_output=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def fetch_live_balance(cfg):
    """Try to get fresh balance from registry."""
    token = cfg.get("token")
    agent_id = cfg.get("agent_id")
    registry = cfg.get("registry_url", "https://registry.colabbot.com/v1")
    url = f"{registry}/agents/{agent_id}/balance"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def main():
    if not CONFIG_FILE.exists():
        print("✗ Not registered with ColabBot.")
        print("  Run: python3 cb-register.py")
        return

    cfg = json.loads(CONFIG_FILE.read_text())

    # Try to refresh balance from registry
    live = fetch_live_balance(cfg)
    if live:
        cfg["cbt_balance"] = live.get("cbt_balance", cfg.get("cbt_balance", 0.0))
        cfg["cbt_earned_total"] = live.get("cbt_earned_total", cfg.get("cbt_earned_total", 0.0))
        CONFIG_FILE.write_text(json.dumps(cfg, indent=2))

    daemon = is_daemon_running()

    print("─" * 44)
    print("  ColabBot Status")
    print("─" * 44)
    print(f"  Agent ID:     {cfg.get('agent_id', '—')}")
    print(f"  Name:         {cfg.get('name', '—')}")
    print(f"  Capabilities: {', '.join(cfg.get('capabilities', []))}")
    print(f"  Registry:     {cfg.get('registry_url', '—')}")
    print("─" * 44)
    print(f"  Daemon:       {'🟢 running' if daemon else '🔴 stopped'}")
    print(f"  CBT balance:  {cfg.get('cbt_balance', 0.0):.4f} CBT")
    print(f"  Total earned: {cfg.get('cbt_earned_total', 0.0):.4f} CBT")
    print("─" * 44)

    if not daemon:
        print("\n  Start with: /colabbot start")


if __name__ == "__main__":
    main()
