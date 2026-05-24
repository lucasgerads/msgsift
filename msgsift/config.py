import os
import tomllib
from pathlib import Path


def config_dir() -> Path:
    env = os.environ.get("MSGSIFT_CONFIG_DIR")
    if env:
        return Path(env).expanduser()
    base = os.environ.get("XDG_CONFIG_HOME", "~/.config")
    return Path(base).expanduser() / "msgsift"


def load_config() -> dict:
    directory = config_dir()
    config_path = directory / "config.toml"
    if not config_path.exists():
        raise FileNotFoundError(
            f"No config found at {config_path}. "
            "Copy config.example.toml there (and credentials.toml for secrets)."
        )
    with open(config_path, "rb") as f:
        config = tomllib.load(f)

    cred_path = directory / "credentials.toml"
    if cred_path.exists():
        with open(cred_path, "rb") as f:
            _deep_merge(config, tomllib.load(f))
    return config


def _deep_merge(base: dict, override: dict) -> None:
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
