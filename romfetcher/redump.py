"""Redump catalog: parse datfiles, search local releases first."""

import re
import xml.etree.ElementTree as ET

REGION_WORDS = {
    "usa", "europe", "japan", "australia", "asia", "brazil", "canada",
    "china", "france", "germany", "italy", "korea", "netherlands",
    "russia", "spain", "sweden", "uk", "ireland", "mexico", "taiwan",
    "hong kong", "new zealand", "norway", "denmark", "finland", "greece",
    "poland", "portugal", "czech", "hungary", "israel",
}
VERSION_RE = re.compile(r"\(v(\d[\d.]*)\)")
PAREN_RE = re.compile(r"\(([^()]*)\)")


def split_release(name: str) -> tuple:
    """Split a Redump name into (base title, region, version)."""
    region, version = "", ""
    match = VERSION_RE.search(name)
    if match:
        version = match.group(1)
    for group in PAREN_RE.findall(name):
        low = group.strip().lower()
        if any(word in low for word in REGION_WORDS):
            region = group.strip()
            break
    base = PAREN_RE.sub("", name).strip()
    base = re.sub(r"\s{2,}", " ", base)
    return base, region, version


def parse_entry(name: str, roms: list, category: str = "") -> dict:
    title, region, version = split_release(name)
    discs = [{"name": r.get("name", ""), "size": int(r.get("size") or 0),
              "sha1": r.get("sha1", "")} for r in roms]
    return {"name": name, "title": title, "region": region,
            "version": version, "category": category, "discs": discs}


def parse_datfile(path: str) -> dict:
    """Parse a Redump Logiqx datfile into a catalog dict."""
    releases = []
    version = ""
    count = 0
    for _event, elem in ET.iterparse(path, events=("end",)):
        if elem.tag == "version" and not version:
            version = (elem.text or "").strip()
        elif elem.tag == "game":
            name = elem.get("name", "")
            category = ""
            roms = []
            for child in elem:
                if child.tag == "category" and child.text:
                    category = child.text.strip()
                elif child.tag == "rom":
                    roms.append(child.attrib)
            if name:
                releases.append(parse_entry(name, roms, category))
                count += 1
            elem.clear()
    return {"meta": {"version": version, "count": count},
            "releases": releases}


def search_catalog(query: str, catalog: list, limit: int = 50) -> list:
    """Substring search over local releases; title-prefix hits first."""
    q = query.strip().casefold()
    if not q:
        return []
    starts, contains = [], []
    for entry in catalog:
        name = entry.get("name", "").casefold()
        if name.startswith(q):
            starts.append(entry)
        elif q in name:
            contains.append(entry)
        if len(starts) + len(contains) >= limit * 4:
            pass
    return (starts + contains)[:limit]
