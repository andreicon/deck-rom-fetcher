"""Redump system map + title lists."""

import csv

import yaml


def load_systems(config_path: str) -> dict:
    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def get_mapping(systems: dict, redump_id: str) -> dict:
    return systems[redump_id]


def list_redump_titles(tsv_path: str) -> list:
    with open(tsv_path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))
