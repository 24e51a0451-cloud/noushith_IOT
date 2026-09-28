"""
config/loader.py
-------------------
Loads config/agent_config.json and applies environment-variable
overrides, so the exact same Agent package/executable can be deployed
as PC_001, PC_002, PC_003, ... by configuration only (MASTERHUB prompt
section 16/25 - "never hard-code PC_001 / COM4").

Precedence (highest first):
    1. CLI flags (applied by agent/pc_agent.py after calling load_config())
    2. Environment variables (MASTERHUB_AGENT_* and MQTT_*)
    3. Agent-root .env file
    4. config/agent_config.json
    5. Built-in fallback defaults (only used if the JSON file is missing)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from dotenv import dotenv_values
from typing import Any, Dict

from config.validator import assert_valid_config

_HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG_PATH = os.path.join(_HERE, "agent_config.json")

_FALLBACK: Dict[str, Any] = {
    "device_id": "PC_001",
    "device_name": "PC_001",
    "transport": {
        "type": "usb",
        "port": None,
        "baudrate": 115200,
        "mqtt": {
            "broker": None,
            "port": None,
            "username": None,
            "password": None,
            "keepalive": None,
            "qos": None,
            "client_id": None,
            "tls_enabled": False,
            "tls_ca_certs": None,
            "tls_certfile": None,
            "tls_keyfile": None,
            "tls_insecure": False,
        },
    },
    "heartbeat_interval": 5.0,
    "command_timeout": 30.0,
    "command_queue_size": 100,
    "capabilities": ["desktop", "media"],
    "register_url": None,
    "automation": {
        "chrome_path": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "chrome_profile": "Default",
        "chrome_extra_args": [],
    },
}


def _bool_env(name: str, environ=None) -> bool:
    environ = os.environ if environ is None else environ
    val = environ.get(name, "").strip().lower()
    return val in ("1", "true", "yes", "on")


def _env_override(cfg: Dict[str, Any], environ=None) -> Dict[str, Any]:
    environ = os.environ if environ is None else environ
    cfg = json.loads(json.dumps(cfg))  # deep copy

    # Top-level settings
    if environ.get("MASTERHUB_AGENT_DEVICE_ID"):
        cfg["device_id"] = environ["MASTERHUB_AGENT_DEVICE_ID"]
    elif environ.get("DEVICE_ID"):
        cfg["device_id"] = environ["DEVICE_ID"]

    if environ.get("MASTERHUB_AGENT_DEVICE_NAME"):
        cfg["device_name"] = environ["MASTERHUB_AGENT_DEVICE_NAME"]
    if environ.get("MASTERHUB_AGENT_HEARTBEAT_INTERVAL"):
        cfg["heartbeat_interval"] = float(environ["MASTERHUB_AGENT_HEARTBEAT_INTERVAL"])
    if environ.get("MASTERHUB_COMMAND_TIMEOUT"):
        cfg["command_timeout"] = float(environ["MASTERHUB_COMMAND_TIMEOUT"])
    if environ.get("MASTERHUB_COMMAND_QUEUE_SIZE"):
        cfg["command_queue_size"] = int(environ["MASTERHUB_COMMAND_QUEUE_SIZE"])
    if environ.get("MASTERHUB_AGENT_REGISTER_URL"):
        cfg["register_url"] = environ["MASTERHUB_AGENT_REGISTER_URL"]
    if environ.get("MASTERHUB_AGENT_CAPABILITIES"):
        cfg["capabilities"] = [c.strip() for c in environ["MASTERHUB_AGENT_CAPABILITIES"].split(",") if c.strip()]

    # Transport settings
    transport = cfg.setdefault("transport", {})
    if environ.get("MASTERHUB_TRANSPORT"):
        transport["type"] = environ["MASTERHUB_TRANSPORT"]

    if environ.get("MASTERHUB_AGENT_PORT"):
        transport["port"] = environ["MASTERHUB_AGENT_PORT"]
    if environ.get("MASTERHUB_AGENT_BAUDRATE"):
        transport["baudrate"] = int(environ["MASTERHUB_AGENT_BAUDRATE"])

    # MQTT settings
    mqtt_cfg = transport.setdefault("mqtt", {})
    if environ.get("MQTT_BROKER"):
        mqtt_cfg["broker"] = environ["MQTT_BROKER"]
    if environ.get("MQTT_PORT"):
        mqtt_cfg["port"] = int(environ["MQTT_PORT"])
    if environ.get("MQTT_USERNAME"):
        mqtt_cfg["username"] = environ["MQTT_USERNAME"]
    if environ.get("MQTT_PASSWORD"):
        mqtt_cfg["password"] = environ["MQTT_PASSWORD"]
    if environ.get("MQTT_KEEPALIVE"):
        mqtt_cfg["keepalive"] = int(environ["MQTT_KEEPALIVE"])
    if environ.get("MQTT_QOS"):
        mqtt_cfg["qos"] = int(environ["MQTT_QOS"])
    if environ.get("MQTT_CLIENT_ID"):
        mqtt_cfg["client_id"] = environ["MQTT_CLIENT_ID"]

    if environ.get("MQTT_TLS_ENABLED"):
        mqtt_cfg["tls_enabled"] = _bool_env("MQTT_TLS_ENABLED", environ)
    if environ.get("MQTT_TLS_CA_CERTS"):
        mqtt_cfg["tls_ca_certs"] = environ["MQTT_TLS_CA_CERTS"]
    if environ.get("MQTT_TLS_CERTFILE"):
        mqtt_cfg["tls_certfile"] = environ["MQTT_TLS_CERTFILE"]
    if environ.get("MQTT_TLS_KEYFILE"):
        mqtt_cfg["tls_keyfile"] = environ["MQTT_TLS_KEYFILE"]
    if environ.get("MQTT_TLS_INSECURE"):
        mqtt_cfg["tls_insecure"] = _bool_env("MQTT_TLS_INSECURE", environ)

    # Automation
    if environ.get("MASTERHUB_AGENT_CHROME_PATH"):
        cfg.setdefault("automation", {})["chrome_path"] = environ["MASTERHUB_AGENT_CHROME_PATH"]
    if environ.get("MASTERHUB_AGENT_CHROME_PROFILE"):
        cfg.setdefault("automation", {})["chrome_profile"] = environ["MASTERHUB_AGENT_CHROME_PROFILE"]

    return cfg


def load_config(path: str = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    """Loads and returns the merged configuration."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        data = {k: v for k, v in data.items() if not k.startswith("_")}
        merged = json.loads(json.dumps(_FALLBACK))
        merged.update({k: v for k, v in data.items() if k not in ("transport", "automation")})
        if "transport" in data and isinstance(data["transport"], dict):
            # Deep merge transport.mqtt
            file_transport = data["transport"]
            for tk, tv in file_transport.items():
                if tk == "mqtt" and isinstance(tv, dict):
                    merged["transport"].setdefault("mqtt", {}).update(tv)
                else:
                    merged["transport"][tk] = tv
        if "automation" in data and isinstance(data["automation"], dict):
            merged["automation"].update(data["automation"])
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        merged = json.loads(json.dumps(_FALLBACK))

    # Resolve relative to the config package, never the caller's working directory.
    env_path = Path(path).resolve().parent.parent / '.env'
    file_env = {key: value for key, value in dotenv_values(env_path).items() if value is not None}
    return _env_override(merged, {**file_env, **os.environ})


def load_and_validate_config(path: str = DEFAULT_CONFIG_PATH, *, check_files: bool = False, strict_paths: bool = False) -> Dict[str, Any]:
    """Loads configuration and enforces validation rules."""
    cfg = load_config(path)
    assert_valid_config(cfg, check_files=check_files, strict_paths=strict_paths)
    return cfg
