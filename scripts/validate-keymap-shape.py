#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LayerBindingCount:
    index: int
    name: str
    count: int


def strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"//.*", "", text)


def find_matching_brace(text: str, opening_brace: int) -> int:
    depth = 0
    for idx in range(opening_brace, len(text)):
        char = text[idx]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return idx
    raise ValueError("missing closing brace")


def keymap_block(text: str) -> str:
    match = re.search(r"\bkeymap\s*\{", text)
    if not match:
        raise ValueError("could not find keymap { ... } block")

    opening = text.index("{", match.start())
    closing = find_matching_brace(text, opening)
    return text[opening + 1 : closing]


def layer_blocks(keymap_text: str) -> list[tuple[str, str]]:
    layers: list[tuple[str, str]] = []
    consumed: list[tuple[int, int]] = []
    cursor = 0
    # Optional devicetree label prefix ("mylabel: node_name {") is accepted so a
    # labeled layer cannot silently escape validation.
    node_pattern = re.compile(r"(?m)^\s*(?:[A-Za-z_][A-Za-z0-9_]*\s*:\s*)?([A-Za-z_][A-Za-z0-9_]*)\s*\{")

    while True:
        match = node_pattern.search(keymap_text, cursor)
        if not match:
            break

        name = match.group(1)
        opening = keymap_text.index("{", match.start())
        closing = find_matching_brace(keymap_text, opening)
        layers.append((name, keymap_text[opening + 1 : closing]))
        end = closing + 1
        trailing = re.match(r"\s*;", keymap_text[end:])
        if trailing:
            end += trailing.end()
        consumed.append((match.start(), end))
        cursor = end

    leftover = keymap_text
    for start, end in reversed(consumed):
        leftover = leftover[:start] + leftover[end:]
    leftover = re.sub(r"compatible\s*=[^;]*;", "", leftover)
    leftover = leftover.strip()
    if leftover:
        raise ValueError(f"unrecognized content in keymap block (validator fails closed): {leftover[:80]!r}")

    return layers


def count_layer_bindings(layer_text: str) -> int:
    # (?<![\w-]) keeps "sensor-bindings" from matching as a second bindings block.
    binding_blocks = re.findall(r"(?<![\w-])bindings\s*=\s*<(.*?)>\s*;", layer_text, flags=re.DOTALL)
    if len(binding_blocks) != 1:
        raise ValueError(f"expected exactly one bindings block, found {len(binding_blocks)}")
    return len(re.findall(r"&[A-Za-z_][A-Za-z0-9_]*", binding_blocks[0]))


def validate_keymap(path: Path, expected_bindings: int, expected_layers: int) -> list[LayerBindingCount]:
    text = strip_comments(path.read_text())
    layers = layer_blocks(keymap_block(text))
    if not layers:
        raise ValueError("no layer nodes found in keymap block")
    if expected_layers and len(layers) != expected_layers:
        raise ValueError(f"expected {expected_layers} layers, found {len(layers)}")

    counts: list[LayerBindingCount] = []
    for index, (name, layer_text) in enumerate(layers):
        counts.append(LayerBindingCount(index=index, name=name, count=count_layer_bindings(layer_text)))

    mismatches = [layer for layer in counts if layer.count != expected_bindings]
    if mismatches:
        lines = "\n".join(
            f"  layer {layer.index} {layer.name}: {layer.count} bindings, expected {expected_bindings}"
            for layer in mismatches
        )
        raise ValueError(f"invalid TOTEM keymap shape:\n{lines}")

    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate that each ZMK keymap layer keeps the TOTEM binding shape.")
    parser.add_argument("keymap", nargs="?", type=Path, default=Path("config/totem.keymap"))
    parser.add_argument("--expected-bindings", type=int, default=38)
    parser.add_argument(
        "--expected-layers",
        type=int,
        default=9,
        help="Expected number of keymap layers; 0 disables the count check.",
    )
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    try:
        counts = validate_keymap(args.keymap, args.expected_bindings, args.expected_layers)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"{args.keymap}: {exc}") from exc

    if not args.quiet:
        for layer in counts:
            print(f"layer {layer.index}: {layer.name}: {layer.count} bindings")
        print(f"Validated {len(counts)} layers with {args.expected_bindings} bindings each.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
