#!/usr/bin/env python3
"""Render a proposed TOTEM keymap change as a self-contained HTML page.

Compares config/totem.keymap (working tree, or --new FILE) against a git ref
(default HEAD) and draws every layer the change touches on the real TOTEM
geometry: changed keys, added/removed/changed combos, old -> new labels.
The page uses T3 Code theme variables, so it can go straight to html_render.

    ./scripts/keymap-preview.py                     # working tree vs HEAD
    ./scripts/keymap-preview.py --base 51f8ffb^     # a past change
    ./scripts/keymap-preview.py --layer 0 --all-combos   # just draw layer 0
"""
import argparse
import html
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
KEYMAP_REL = "config/totem.keymap"

# Key centres and rotations, copied from keymap-drawer/totem.svg (keypos-N).
GEOMETRY = [
    (78, 113, -10), (144, 62, -4), (212, 28, 0), (271, 56, 0), (330, 65, 0),
    (520, 65, 0), (580, 56, 0), (639, 28, 0), (706, 62, 4), (773, 113, 10),
    (87, 168, -10), (148, 118, -4), (212, 84, 0), (271, 112, 0), (330, 121, 0),
    (520, 121, 0), (580, 112, 0), (639, 84, 0), (703, 118, 4), (764, 168, 10),
    (34, 209, -10), (97, 223, -10), (152, 174, -4), (212, 140, 0), (271, 168, 0),
    (330, 177, 0), (520, 177, 0), (580, 168, 0), (639, 140, 0), (699, 174, 4),
    (754, 223, 10), (817, 209, 10),
    (255, 236, 0), (320, 245, 15), (381, 270, 30),
    (470, 270, -30), (531, 245, -15), (596, 236, 0),
]
KEY_W, KEY_H = 55, 52
OUTSIDE_WORK_LAYOUT = {20, 31, 32, 37}
FULL_LAYOUT_LAYERS = {3, 4, 5}

KEY_NAMES = {
    "MINUS": "-", "EQUAL": "=", "FSLH": "/", "SLASH": "/", "BSLH": "\\", "SEMI": ";",
    "SEMICOLON": ";", "APOS": "'", "SQT": "'", "GRAVE": "`", "COMMA": ",", "DOT": ".",
    "LBKT": "[", "RBKT": "]", "LEFT_BRACKET": "[", "RIGHT_BRACKET": "]", "LBRC": "{",
    "RBRC": "}", "EXCL": "!", "AT": "@", "HASH": "#", "DLLR": "$", "PRCNT": "%",
    "CARET": "^", "AMPS": "&", "STAR": "*", "ASTRK": "*", "LPAR": "(", "RPAR": ")",
    "LEFT_PARENTHESIS": "(", "KP_RIGHT_PARENTHESIS": ")", "RIGHT_PARENTHESIS": ")",
    "PIPE": "|", "TILDE": "~", "PLUS": "+", "QUESTION": "?",
    "RET": "⏎", "ENTER": "⏎", "RETURN": "⏎", "BSPC": "⌫", "BACKSPACE": "⌫",
    "SPACE": "␣", "SPC": "␣", "TAB": "⇥", "ESC": "Esc", "ESCAPE": "Esc", "DEL": "Del",
    "UP_ARROW": "↑", "UP": "↑", "DOWN": "↓", "DOWN_ARROW": "↓", "LEFT": "←",
    "LEFT_ARROW": "←", "RIGHT": "→", "RIGHT_ARROW": "→",
    "C_VOL_UP": "Vol+", "C_VOL_DN": "Vol−", "C_MUTE": "Mute", "C_PREV": "⏮",
    "C_NEXT": "⏭", "C_PLAY_PAUSE": "⏯", "C_BRIGHTNESS_INC": "Bri+",
    "C_BRIGHTNESS_DEC": "Bri−",
}
MOD_FUNCS = {"LS": "⇧", "RS": "⇧", "LC": "⌃", "RC": "⌃", "LA": "⌥", "RA": "⌥",
             "LG": "⌘", "RG": "⌘"}


def mod_symbol(name):
    base = re.sub(r"^(LEFT_|RIGHT_|L|R)", "", name)
    for keys, sym in ((("CONTROL", "CTRL", "CTL"), "⌃"), (("ALT", "OPT"), "⌥"),
                      (("COMMAND", "CMD", "GUI", "META", "WIN"), "⌘"),
                      (("SHIFT", "SHFT", "SFT"), "⇧")):
        if base in keys:
            return sym
    return None


def key_label(expr):
    """LS(LA(LG(RET))) -> '⇧⌥⌘⏎'; plain names via KEY_NAMES."""
    mods = ""
    while True:
        m = re.fullmatch(r"(L[SCAG]|R[SCAG])\((.*)\)", expr)
        if not m:
            break
        mods += MOD_FUNCS[m.group(1)]
        expr = m.group(2)
    sym = mod_symbol(expr)
    if sym:
        return "".join(sorted(set(mods + sym), key="⌃⌥⇧⌘".index))
    mods = "".join(sorted(set(mods), key="⌃⌥⇧⌘".index))
    if mods == "⌃⌥⇧⌘":
        mods = "Hyper "
    if re.fullmatch(r"N\d", expr):
        expr = expr[1]
    return mods + KEY_NAMES.get(expr, expr)


def describe(binding, layer_names):
    """Return (tap, hold) labels for one binding string."""
    parts = binding.split()
    beh, args = parts[0], parts[1:]
    lname = lambda n: f"L{n} {layer_names[int(n)].split('_')[0]}" if n.isdigit() and int(n) < len(layer_names) else f"L{n}"
    if beh == "&kp":
        return key_label(args[0]), ""
    if beh == "&mt":
        return key_label(args[1]), key_label(args[0])
    if beh == "&lt":
        return key_label(args[1]), lname(args[0])
    if beh == "&trans":
        return "▽", ""
    if beh == "&none":
        return "✕", ""
    if beh in ("&mo", "&tog", "&sl", "&to"):
        return f"L{args[0]}", f"{beh[1:]} {lname(args[0]).split(' ')[-1]}"
    if beh == "&bt":
        return " ".join(a.replace("BT_", "") for a in args), "BT"
    if beh == "&out":
        return args[0].replace("OUT_", ""), "out"
    return " ".join([beh[1:]] + args), ""


def strip_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"//[^\n]*", "", text)


def block_after(text, marker):
    i = text.find(marker)
    if i < 0:
        return ""
    start = text.rfind("{", 0, i) + 1
    depth, j = 1, start
    while depth and j < len(text):
        depth += {"{": 1, "}": -1}.get(text[j], 0)
        j += 1
    return text[start:j - 1]


def parse(text):
    text = strip_comments(text)
    layers = []
    for name, body in re.findall(r"(\w+)\s*\{([^{}]*)\}", block_after(text, '"zmk,keymap"')):
        m = re.search(r"bindings\s*=\s*<(.*?)>\s*;", body, re.S)
        if m:
            tokens = m.group(1).split()
            binds = []
            for t in tokens:
                if t.startswith("&"):
                    binds.append(t)
                else:
                    binds[-1] += " " + t
            layers.append((name, binds))
    combos = {}
    for name, body in re.findall(r"([\w-]+)\s*\{([^{}]*)\}", block_after(text, '"zmk,combos"')):
        props = dict(re.findall(r"([\w-]+)\s*=\s*<([^>]*)>\s*;", body))
        if "key-positions" not in props:
            continue
        combos[name] = {
            "binding": " ".join(props.get("bindings", "").split()),
            "positions": [int(p) for p in props["key-positions"].split()],
            "layers": [int(p) for p in props["layers"].split()] if "layers" in props else None,
            "timeout": props.get("timeout-ms", "").strip() or None,
        }
    return layers, combos


def git_show(ref):
    return subprocess.run(["git", "-C", str(REPO), "show", f"{ref}:{KEYMAP_REL}"],
                          check=True, capture_output=True, text=True).stdout


def esc(s):
    return html.escape(str(s), quote=True)


def svg_layer(idx, name, binds, old_binds, combos_here, layer_names):
    out = ['<svg viewBox="0 -4 860 340" class="kb" role="img" '
           f'aria-label="{esc(name)}">']
    dim_outer = idx not in FULL_LAYOUT_LAYERS
    marked = {}
    for c in combos_here:
        for p in c["positions"]:
            marked.setdefault(p, c["status"])
    for pos, (x, y, r) in enumerate(GEOMETRY):
        tap, hold = describe(binds[pos], layer_names)
        changed = old_binds is not None and old_binds[pos] != binds[pos]
        cls = ["key"]
        if changed:
            cls.append("changed")
        if pos in marked:
            cls.append("combo-" + marked[pos])
        if dim_outer and pos in OUTSIDE_WORK_LAYOUT:
            cls.append("outer")
        if tap == "▽":
            cls.append("trans")
        title = f"pos {pos}: {binds[pos]}"
        if changed:
            title += f"  (was {old_binds[pos]})"
        size = 15 if len(tap) <= 3 else 12 if len(tap) <= 6 else 9
        out.append(
            f'<g class="{" ".join(cls)}" transform="translate({x} {y}) rotate({r})">'
            f"<title>{esc(title)}</title>"
            f'<rect x="{-KEY_W/2}" y="{-KEY_H/2}" width="{KEY_W}" height="{KEY_H}" rx="7"/>'
            f'<text class="tap" y="{-2 if hold else 2}" font-size="{size}">{esc(tap)}</text>'
            + (f'<text class="hold" y="18">{esc(hold)}</text>' if hold else "")
            + f'<text class="pos" x="{-KEY_W/2+4}" y="{-KEY_H/2+9}">{pos}</text>'
            + (f'<text class="was" y="-17">was {esc(describe(old_binds[pos], layer_names)[0])}</text>'
               if changed else "")
            + "</g>")
    for c in combos_here:
        pts = [GEOMETRY[p][:2] for p in c["positions"]]
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        label = describe(c["binding"], layer_names)[0] if c["binding"] else "?"
        w = max(40, 12 * len(label) + 18)
        lines = "".join(f'<line x1="{cx}" y1="{cy}" x2="{px}" y2="{py}"/>' for px, py in pts)
        out.append(
            f'<g class="combo {c["status"]}"><title>{esc(c["name"])}: {esc(c["binding"])} '
            f'on {esc(c["positions"])}</title>{lines}'
            f'<rect x="{cx-w/2}" y="{cy-14}" width="{w}" height="28" rx="14"/>'
            f'<text x="{cx}" y="{cy+1}">{esc(label)}</text></g>')
    out.append("</svg>")
    return "".join(out)


CSS = """
:root{--ink:var(--foreground);--soft:var(--muted-foreground);--line:var(--border);
--chg:var(--warning);--add:var(--success);--del:var(--destructive);--old:var(--info)}
body{margin:0;color:var(--ink);background:var(--background);
font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
h3{font-size:16px;margin:18px 0 4px}
.legend{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:13px;color:var(--soft);margin:4px 0 8px}
.legend span::before{content:"";display:inline-block;width:11px;height:11px;border-radius:3px;
margin-right:5px;vertical-align:-1px;border:2px solid currentColor}
.l-chg{color:var(--chg)}.l-add{color:var(--add)}.l-del{color:var(--del)}.l-old{color:var(--soft)}
svg.kb{width:100%;height:auto;display:block}
.key rect{fill:var(--card);stroke:var(--line);stroke-width:1.2}
.key text{text-anchor:middle;dominant-baseline:middle;fill:var(--ink);
font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
.key .hold{font-size:11px;fill:var(--soft)}
.key .pos{font-size:8px;text-anchor:start;fill:var(--soft);opacity:.7}
.key .was{font-size:8px;fill:var(--chg)}
.key.trans .tap{fill:var(--soft)}
.key.outer{opacity:.35}
.key.changed rect{fill:color-mix(in srgb,var(--chg) 22%,var(--card));stroke:var(--chg);stroke-width:3}
.key.combo-added rect{stroke:var(--add);stroke-width:3}
.key.combo-changed rect{stroke:var(--chg);stroke-width:3}
.key.combo-removed rect{stroke:var(--del);stroke-width:3;stroke-dasharray:5 3}
.combo line{stroke-width:2}
.combo text{text-anchor:middle;dominant-baseline:middle;font:700 16px ui-monospace,Menlo,monospace}
.combo rect{fill:var(--background);stroke-width:2.5}
.combo.added line,.combo.added rect{stroke:var(--add)}.combo.added text{fill:var(--add)}
.combo.changed line,.combo.changed rect{stroke:var(--chg)}.combo.changed text{fill:var(--chg)}
.combo.removed line{stroke:var(--del);stroke-dasharray:4 3}
.combo.removed rect{stroke:var(--del);stroke-dasharray:4 3}
.combo.removed text{fill:var(--del);text-decoration:line-through}
.combo.existing line{stroke:var(--soft);opacity:.5}.combo.existing rect{stroke:var(--line)}
.combo.existing text{fill:var(--soft);font-weight:500;font-size:12px}
.changes{overflow-x:auto}
table{border-collapse:collapse;font-size:14px;width:100%}
th,td{text-align:left;padding:5px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{background:var(--secondary);font-weight:600}
code{font:13px ui-monospace,Menlo,monospace;background:var(--secondary);padding:0 4px;border-radius:4px}
.tag{font-size:12px;font-weight:600;padding:1px 7px;border-radius:9px;white-space:nowrap}
.tag.added{background:color-mix(in srgb,var(--add) 18%,transparent);color:var(--add)}
.tag.removed{background:color-mix(in srgb,var(--del) 18%,transparent);color:var(--del)}
.tag.changed{background:color-mix(in srgb,var(--chg) 18%,transparent);color:var(--chg)}
p.note{margin:6px 0 0}
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="HEAD", help="git ref to compare against (default HEAD)")
    ap.add_argument("--new", help="keymap file to preview (default: working-tree config/totem.keymap)")
    ap.add_argument("--layer", type=int, action="append", help="always draw this layer index (repeatable)")
    ap.add_argument("--all-combos", action="store_true", help="also draw unchanged combos on drawn layers")
    ap.add_argument("--note", help="one-line note shown under the diagrams")
    ap.add_argument("-o", "--out", help="write HTML here instead of stdout")
    a = ap.parse_args()

    new_text = Path(a.new or REPO / KEYMAP_REL).read_text()
    new_layers, new_combos = parse(new_text)
    old_layers, old_combos = parse(git_show(a.base))
    names = [n for n, _ in new_layers]
    for n, b in new_layers:
        if len(b) != len(GEOMETRY):
            sys.exit(f"{n}: {len(b)} bindings, expected {len(GEOMETRY)}")

    rows, draw = [], set(a.layer or [])
    old_by_name = dict(old_layers)
    for idx, (n, binds) in enumerate(new_layers):
        ob = old_by_name.get(n)
        if ob is None:
            rows.append(("added", f"Layer {idx} <code>{esc(n)}</code>", "new layer"))
            draw.add(idx)
            continue
        for pos, (o, b) in enumerate(zip(ob, binds)):
            if o != b:
                rows.append(("changed", f"Layer {idx} <code>{esc(n)}</code>, key {pos}",
                             f"<code>{esc(o)}</code> → <code>{esc(b)}</code>"))
                draw.add(idx)
    for n in old_by_name.keys() - set(names):
        rows.append(("removed", f"Layer <code>{esc(n)}</code>", "layer removed"))

    combo_status = {}
    for n in new_combos.keys() | old_combos.keys():
        o, c = old_combos.get(n), new_combos.get(n)
        status = "added" if o is None else "removed" if c is None else "changed" if o != c else None
        if not status:
            continue
        combo_status[n] = status
        cur = c or o
        keys = " + ".join(f"{p} ({describe(new_layers[cur['layers'][0] if cur['layers'] else 0][1][p], names)[0]})"
                          for p in cur["positions"])
        on = ", ".join(str(i) for i in cur["layers"]) if cur["layers"] else "all layers"
        detail = f"keys {keys} → <code>{esc(cur['binding'])}</code>; layers {on}"
        if cur["timeout"]:
            detail += f"; timeout {cur['timeout']} ms"
        if status == "changed":
            diffs = [k for k in o if o[k] != c[k]]
            detail += "; changed: " + ", ".join(
                f"{k} <code>{esc(o[k])}</code> → <code>{esc(c[k])}</code>" for k in diffs)
        rows.append((status, f"Combo <code>{esc(n)}</code>", detail))
        draw.add(cur["layers"][0] if cur["layers"] else 0)

    sections = []
    for idx in sorted(draw):
        n, binds = new_layers[idx]
        here = []
        for cn, c in list(new_combos.items()) + [(k, v) for k, v in old_combos.items() if k not in new_combos]:
            on = c["layers"] is None or idx in c["layers"]
            st = combo_status.get(cn)
            if on and (st or a.all_combos):
                here.append(dict(c, name=cn, status=st or "existing"))
        here.sort(key=lambda c: c["status"] != "existing")
        sections.append(f"<h3>Layer {idx} · {esc(n)}</h3>"
                        + svg_layer(idx, n, binds, old_by_name.get(n), here, names))

    legend = ('<div class="legend"><span class="l-chg">changed key</span>'
              '<span class="l-add">new combo</span><span class="l-del">removed combo</span>'
              + ('<span class="l-old">existing combo</span>' if a.all_combos else "")
              + "</div>")
    table = ("<div class='changes'><table><tr><th></th><th>What</th><th>Detail</th></tr>"
             + "".join(f"<tr><td><span class='tag {s}'>{s}</span></td><td>{w}</td><td>{d}</td></tr>"
                       for s, w, d in rows)
             + "</table></div>") if rows else "<p>No differences from <code>" + esc(a.base) + "</code>.</p>"
    note = f"<p class='note'>{esc(a.note)}</p>" if a.note else ""
    page = (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<style>{CSS}</style></head><body>{legend}{''.join(sections)}{table}{note}"
            f"</body></html>")
    if a.out:
        Path(a.out).write_text(page)
    else:
        sys.stdout.write(page)


if __name__ == "__main__":
    main()
