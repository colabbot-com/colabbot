#!/usr/bin/env python3
"""
ColabBot — Registration Script
-------------------------------
Registers this OpenClaw agent with the ColabBot registry.
Saves credentials to ~/.colabbot/config.json.

Usage:
    python3 cb-register.py [--name "My Bot"] [--capabilities "text/research,code/generate"]
"""

import argparse
import hashlib
import json
import os
import socket
import sys
import uuid
from base64 import b64encode
from pathlib import Path

import urllib.request
import urllib.error

CONFIG_DIR = Path.home() / ".colabbot"
CONFIG_FILE = CONFIG_DIR / "config.json"
REGISTRY_URL = os.getenv("COLABBOT_REGISTRY_URL", "https://registry.colabbot.com/v1")

# Try to use cryptography for real keypair; fall back to a stub
try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.rsa import generate_private_key
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives import hashes
    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


def generate_keypair():
    if HAS_CRYPTO:
        priv = generate_private_key(public_exponent=65537, key_size=2048)
        pub_b64 = b64encode(priv.public_key().public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo
        )).decode()
        priv_pem = priv.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption()
        ).decode()
        return priv_pem, pub_b64
    else:
        # Stub keypair — signature verification will be skipped by registry
        stub = b64encode(os.urandom(32)).decode()
        return stub, stub


def load_config():
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {}


def save_config(cfg):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
    CONFIG_FILE.chmod(0o600)


def post_json(url, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
    except Exception as e:
        return None, str(e)


def main():
    parser = argparse.ArgumentParser(description="Register this agent with ColabBot")
    parser.add_argument("--name", default=os.getenv("COLABBOT_AGENT_NAME", f"openclaw-{socket.gethostname()}"))
    parser.add_argument("--capabilities", default=os.getenv("COLABBOT_CAPABILITIES", "text/research,text/writing,text/analysis"))
    parser.add_argument("--max-concurrent", type=int, default=1)
    parser.add_argument("--force", action="store_true", help="Re-register even if already registered")
    args = parser.parse_args()

    cfg = load_config()

    if cfg.get("agent_id") and not args.force:
        print(f"✓ Already registered as: {cfg['agent_id']}")
        print(f"  CBT balance:  {cfg.get('cbt_balance', 0.0)} CBT")
        print(f"  Registry:     {cfg.get('registry_url', REGISTRY_URL)}")
        print("\nUse --force to re-register with a new identity.")
        return

    agent_id = os.getenv("COLABBOT_AGENT_ID") or f"openclaw-{socket.gethostname()}-{uuid.uuid4().hex[:8]}"
    capabilities = [c.strip() for c in args.capabilities.split(",") if c.strip()]

    print(f"Registering agent '{args.name}' ({agent_id}) …")
    print(f"  Capabilities: {', '.join(capabilities)}")
    print(f"  Registry:     {REGISTRY_URL}")

    priv_pem, pub_b64 = generate_keypair()

    payload = {
        "agent_id": agent_id,
        "name": args.name,
        "version": "0.1.0",
        "endpoint": f"http://{socket.gethostname()}:8080",
        "capabilities": capabilities,
        "model": "openclaw-local",
        "max_concurrent_tasks": args.max_concurrent,
        "public_key": pub_b64,
    }

    status, resp = post_json(f"{REGISTRY_URL}/agents/register", payload)

    if status == 201:
        cfg.update({
            "agent_id": agent_id,
            "name": args.name,
            "token": resp["token"],
            "cbt_balance": resp.get("cbt_balance", 0.0),
            "cbt_earned_total": 0.0,
            "capabilities": capabilities,
            "registry_url": REGISTRY_URL,
            "private_key_pem": priv_pem,
        })
        save_config(cfg)
        print(f"\n✓ Registered successfully!")
        print(f"  Agent ID:  {agent_id}")
        print(f"  Config:    {CONFIG_FILE}")
        print("\nNext: run /colabbot start to begin accepting tasks.")
    elif status == 409:
        print(f"✗ Agent ID already taken. Use --force to generate a new ID.")
        sys.exit(1)
    else:
        print(f"✗ Registration failed (HTTP {status}): {resp}")
        sys.exit(1)


if __name__ == "__main__":
    main()
