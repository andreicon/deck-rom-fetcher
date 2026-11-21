"""Redump system map (per-system EmuDeck dirs and extensions)."""

import yaml


def load_systems(config_path: str) -> dict:
    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def get_mapping(systems: dict, redump_id: str) -> dict:
    return systems[redump_id]
