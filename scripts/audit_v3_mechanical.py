#!/usr/bin/env python3
"""Mechanical V3 spec audit: candidate defects for human review, not proof of correctness.

Checks:
  M1 section references ("Layer N §x.y" and same-file "§x.y") that match no numbered heading;
  M2 backticked CamelCase identifiers that no authoritative layer defines;
  M3 closed Literal aliases and dataclasses defined more than once with different content.
Output is Markdown on stdout.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = json.loads((ROOT / "docs/specs/v3/contract_registry.json").read_text(encoding="utf-8"))
LAYERS = REGISTRY["authoritative_layers"]
ORIENTATION = REGISTRY["orientation_only"]

HEADING = re.compile(r"^#{1,6} (\d+(?:\.\d+)*)\.?\s", re.MULTILINE)
LAYER_REF = re.compile(r"Layer[ -]([0-8])\s*§\s*(\d+(?:\.\d+)*)")
BARE_REF = re.compile(r"(?<![\w-])§\s*(\d+(?:\.\d+)*)")
TICKED = re.compile(r"`([A-Z][A-Za-z0-9]*[a-z][A-Za-z0-9]*)`")
CLASS_DEF = re.compile(r"^class ([A-Z]\w*)", re.MULTILINE)
ALIAS_DEF = re.compile(r"^([A-Z]\w*)\s*=\s*", re.MULTILINE)
LITERAL_DEF = re.compile(r"^([A-Z]\w*)\s*=\s*Literal\[(.*?)\]", re.MULTILINE | re.DOTALL)
PYTHON_NAMES = {"True", "False", "None", "NaN", "Any", "Callable", "Decimal", "Fraction", "Literal",
                "Optional", "ValueError", "State"}
DATACLASS = re.compile(r"^class ([A-Z]\w*)[^\n]*:\n((?:[ \t]+[^\n]*\n|\n)+)", re.MULTILINE)


def layer_number(path: str) -> str | None:
    match = re.search(r"layer(\d)_", path)
    return match.group(1) if match else None


def line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def strip_comment(line: str) -> str:
    return line.split("#", 1)[0].rstrip()


def main() -> None:
    texts = {path: (ROOT / path).read_text(encoding="utf-8") for path in LAYERS + ORIENTATION}
    headings = {path: set(HEADING.findall(texts[path])) for path in LAYERS}
    by_layer = {layer_number(path): path for path in LAYERS}

    print("# Mechanical audit output\n")

    print("## M1 Unresolved section references\n")
    m1 = 0
    for path, text in texts.items():
        own = layer_number(path)
        for match in LAYER_REF.finditer(text):
            target = by_layer.get(match.group(1))
            if target and match.group(2) not in headings[target]:
                m1 += 1
                print(f"- `{path}:{line_of(text, match.start())}` → Layer {match.group(1)} §{match.group(2)}")
        if own is None:
            continue
        for match in BARE_REF.finditer(text):
            prefix = text[max(0, match.start() - 12):match.start()]
            if re.search(r"Layer[ -]\d\s*$", prefix):
                continue
            # A bare reference may continue a nearby "Layer N" mention in the same paragraph.
            window = text[max(0, match.start() - 300):match.start()].split("\n\n")[-1]
            nearby = {by_layer.get(n) for n in re.findall(r"Layer[ -]([0-8])", window)} - {None}
            candidates = {path} | nearby
            if not any(match.group(1) in headings[c] for c in candidates):
                m1 += 1
                print(f"- `{path}:{line_of(text, match.start())}` → §{match.group(1)} (own or nearby layer)")
    print(f"\nTotal M1: {m1}\n")

    print("## M2 Backticked identifiers with no definition in an authoritative layer\n")
    defined: set[str] = set(PYTHON_NAMES)
    for path in LAYERS:
        defined.update(CLASS_DEF.findall(texts[path]))
        defined.update(ALIAS_DEF.findall(texts[path]))
        # A construct introduced by a heading (prose definition) counts as defined.
        for heading in re.findall(r"^#{1,6} (.+)$", texts[path], re.MULTILINE):
            defined.update(TICKED.findall(heading))
    uses: dict[str, list[str]] = defaultdict(list)
    for path, text in texts.items():
        for match in TICKED.finditer(text):
            name = match.group(1)
            if name not in defined:
                uses[name].append(f"{path}:{line_of(text, match.start())}")
    for name in sorted(uses):
        refs = uses[name]
        print(f"- `{name}` ({len(refs)}): " + ", ".join(f"`{ref}`" for ref in refs[:4])
              + (" …" if len(refs) > 4 else ""))
    print(f"\nTotal M2 identifiers: {len(uses)}\n")

    print("## M3 Types defined more than once with different content\n")
    literals: dict[str, set[tuple[str, ...]]] = defaultdict(set)
    literal_sites: dict[str, list[str]] = defaultdict(list)
    classes: dict[str, set[tuple[str, ...]]] = defaultdict(set)
    class_sites: dict[str, list[str]] = defaultdict(list)
    for path in LAYERS:
        text = texts[path]
        for match in LITERAL_DEF.finditer(text):
            values = tuple(sorted(re.findall(r'"([^"]+)"', match.group(2))))
            literals[match.group(1)].add(values)
            literal_sites[match.group(1)].append(f"{path}:{line_of(text, match.start())}")
        for match in DATACLASS.finditer(text):
            fields = tuple(
                strip_comment(line).strip()
                for line in match.group(2).splitlines()
                if strip_comment(line).strip()
            )
            classes[match.group(1)].add(fields)
            class_sites[match.group(1)].append(f"{path}:{line_of(text, match.start())}")
    m3 = 0
    for name, variants in sorted(literals.items()):
        if len(variants) > 1:
            m3 += 1
            print(f"- Literal `{name}`: {len(variants)} variants at " + ", ".join(f"`{s}`" for s in literal_sites[name]))
    for name, variants in sorted(classes.items()):
        if len(variants) > 1:
            m3 += 1
            print(f"- class `{name}`: {len(variants)} variants at " + ", ".join(f"`{s}`" for s in class_sites[name]))
    print(f"\nTotal M3: {m3}")


if __name__ == "__main__":
    main()
