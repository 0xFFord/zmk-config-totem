# Project Instructions

User's personal TOTEM ZMK keymap project. These files = agent-facing workflow
instructions, not user documentation.

## Repository Facts

- Keyboard: TOTEM split keyboard, `seeeduino_xiao_ble` controllers.
- Primary editable keymap: `config/totem.keymap`.
- Build matrix: `build.yaml`.
- ZMK manifest: `config/west.yml`.
- Firmware output directory: `firmware/`.

## Source Of Truth

- Edit only `config/totem.keymap` for layout changes.
- Every keymap layer: exactly 38 bindings.
- Check shape with `./scripts/validate-keymap-shape.py config/totem.keymap`
  before building or when auditing keymap edits.
- Distinguish ZMK binding slots from active physical-key layouts: every layer
  needs 38 binding slots, but user uses all 38 physical keys only on gaming
  layers. Work, typing, navigation, productivity layers: intended active
  layout = 34 keys.
- On work/productivity layers, physical key positions `20 32 37 31` sit
  outside intended active layout. Keep binding slots present for shape; assign
  no core typing, layer, or shortcut behavior there unless user explicitly
  asks.
- Keep layer node names parser-friendly for Nick Coutsos' keymap editor: start
  with letter or underscore, underscores not hyphens, no leading digits.
- Prefer layer node names `<purpose>_layer_<number>`, where `<number>` matches
  layer's zero-based order in `keymap`.
- Do not recreate `config/boards/shields/totem/totem.keymap`; project uses
  top-level user keymap.
- Leave `firmware/` outputs untracked.

## Layout Context

- `asergo` = user's primary custom layout. User does not type QWERTY; never
  infer intended key positions from QWERTY when changing typing-layer
  behavior.
- If QWERTY-compatible reference layer ever added, treat as alternate/reference
  layer, not user's preferred layout. (None exists now; do not grep for
  `base_layer`.)
- Work layout = 34 active keys. Positions `20 32 37 31` outside intended work
  layout even though each ZMK layer has 38 binding slots.
- Gaming layers exception: user uses full 38 physical keys there. Do not remove
  or neutralize intentional gaming behavior at positions `20 32 37 31` on game
  layers.
- `asergo` name: home-row sequence `A S E R G`, plus `O` for playful `aser go`.

## Layer References

- ZMK behavior references `&lt`, `&mo`, `&sl`, `&tog` use numeric layer
  indexes, not layer node names. After reordering, inserting, deleting, or
  renaming layers, audit every numeric layer reference.
- Comment trigger details when helpful (held key, physical key position that
  activates layer). No physical key positions in layer names unless same
  logical layer has multiple triggers that would otherwise be ambiguous.
- Conditional layers = layer-state combinations: multiple layers active
  together, ZMK activates another automatically. Prefer ordinary behaviors or
  combos when trigger is specific key or combo. If adding conditional layers,
  keep `then-layer` higher priority than `if-layers`; document relationship
  near declaration.

## Gaming Workflow

- `gaming_layer_3` = low-latency game mode. Keep movement, held modifiers,
  zoom/client keys, jump as plain `&kp` bindings.
- `gaming_plus_layer_4` = held hotbar/util layer from gaming thumb key. Key
  placement intentional, user-tuned; do not redesign or "optimize" unless user
  explicitly asks.
- `hyper_oneshot_layer_5` = one-shot Hyper-modified keys
  (`LS(LA(LC(LG(...))))` on base-layout positions), reached via `&sl 5`.
- Gaming layers and variants may use all 38 physical key positions. Do not
  "normalize" to 34-key work layout.
- Keep productivity combos away from layers `3 4 5`; combos on game-critical
  physical positions add timeout latency or fire accidental shortcuts during
  games.

## Build Skill

On `/build`, `$build`, build firmware, download UF2 artifacts, or
install/flash requests:

1. Use repo-local `build` skill from `.agents/skills/build`.
2. Follow the skill's `SKILL.md` for full workflow.
3. Prefer project scripts over reimplementing build, download, or install
   steps.

Default command for build and install:

```sh
./scripts/build-and-install.sh "Update keymap"
```

Build/download only:

```sh
./scripts/build-firmware-github.sh "Update keymap"
```

Install existing firmware only:

```sh
./scripts/install-uf2-macos.py --firmware-dir firmware
```

Resume a single half only when context makes the target clear:

```sh
./scripts/install-uf2-macos.py --firmware-dir firmware --half right
```

## Firmware Workflow

- Build with GitHub Actions, not local Docker or Colima, unless user
  explicitly asks for local builds.
- Build scripts take shared lock (`zmk-build.lock` in repo's git directory,
  via `scripts/lib/build-lock.sh`); do not start overlapping
  build/download/install runs.
- Download only extracted `.uf2` files into `firmware/`; do not create
  `firmware.zip`. Artifact contains three files: left, right, and
  `settings_reset` UF2 used only to clear BLE bonds when halves stop pairing.
- Build helper auto-commits only `config`, `build.yaml`, `.github/workflows`.
  Edits to `scripts/`, `.agents/`, or Markdown docs need manual commit.
- Install left half first, then right half.
- macOS installer notifies when keyboard bootloader volume appears, so user
  knows reset click worked before firmware copy starts.
- `firmware install step complete` = success marker for that half; do not
  infer failure from later wait for other half.
- `XIAO-SENSE` bootloader disk can auto-disconnect immediately after UF2 copy.
  Expected when installer reports upload completed or volume disappeared
  during copy.
- `GITHUB_BUILD.md` = supporting detail for GitHub Actions helper scripts
  only; `AGENTS.md` and `build` skill are routing source of truth.
