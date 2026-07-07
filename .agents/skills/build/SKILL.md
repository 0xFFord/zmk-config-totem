---
name: build
description: Project-local TOTEM ZMK workflow. Use when the user types /build, invokes $build, asks to build firmware after editing config/totem.keymap, asks to download GitHub Actions UF2 artifacts, or asks to install/flash the left and right TOTEM keyboard halves on macOS.
---

# TOTEM ZMK Build And Install

Repo-scoped skill for `/Users/ozz/Documents/GitHub/zmk-config-totem`.
Do not use or create global Codex skills for this workflow.
Use `AGENTS.md` for project-level routing rules.

## Build Only

Run:

```bash
./scripts/build-firmware-github.sh "Update keymap"
```

Commits firmware source edits from `config`, `build.yaml`,
`.github/workflows`, pushes current branch, waits for GitHub Actions,
downloads three `.uf2` files into `firmware/`: left, right, and
`settings_reset` (BLE-bond recovery firmware — never flashed by default).
If push reports everything up-to-date, script reuses existing Actions run for
HEAD commit instead of triggering duplicate.

Script validates `config/totem.keymap` before committing or pushing. Every
layer keeps exactly 38 bindings. Treat as ZMK binding slots: user uses all 38
physical keys only on gaming layers; work/typing/productivity layers are
intentionally 34-key layouts.

Build scripts share lock (`zmk-build.lock` in repo's git directory,
implemented in `scripts/lib/build-lock.sh`) so agents do not overlap
build/download/install runs. Stale lock from dead process removed
automatically.

GitHub Actions helper uses `gh auth status`, attempts `gh auth setup-git`
only when needed, disables interactive git credential prompts before pushing.
Uses compact GitHub Actions watching when installed `gh` supports it.

## Build And Install

Run:

```bash
./scripts/build-and-install.sh "Update keymap"
```

Builds through GitHub Actions, downloads UF2 files, installs left half first,
right half second. macOS installer watches `/Volumes`, prompts user to connect
each half and double-click reset, copies matching `.uf2` to bootloader volume,
syncs, tries to eject, prints/notifies completion.
Installer output line-buffered so agents see each prompt and status message
while process still running.
`XIAO-SENSE` bootloader volume can auto-disconnect immediately after UF2
upload. Installer verifies byte count before accepting disconnect as success:
`copied N bytes` plus `firmware install step complete` = flash finished;
`flash NOT complete` error = volume vanished mid-copy, reset and reflash that
half. Pass `--strict-copy` to treat any disconnect during copy as failure.
When bootloader volume appears, installer sends macOS notification so user
knows reset click worked before firmware copy starts.

If context shows one half already flashed and only other half pending, agents
may resume directly with `--half left` or `--half right` instead of asking
user to manually choose flag.

## Install Existing Firmware Only

If `firmware/*.uf2` already exists and user only wants to flash:

```bash
./scripts/install-uf2-macos.py --firmware-dir firmware
```

Use `--preflight` to validate left/right firmware file detection without
waiting for hardware.

Resume one half when context makes target clear:

```bash
./scripts/install-uf2-macos.py --firmware-dir firmware --half right
```

Installer recognizes already-mounted trusted bootloader volumes such as
`XIAO-SENSE`, so board already in bootloader mode continues without another
reset. `--bootloader-volume-name` values replace built-in trusted list
(repeat flag for several names).

To flash `settings_reset` recovery firmware onto one half (only when BLE
pairing between halves broken):

```bash
./scripts/install-uf2-macos.py --firmware-dir firmware --half left --left-pattern 'settings_reset*.uf2'
```

Afterwards reflash that half's normal firmware.

## Safety

- Editable user keymap: `config/totem.keymap`.
- Do not recreate `config/boards/shields/totem/totem.keymap`; project uses
  top-level user keymap.
- Before building after keymap edits, preserve TOTEM shape: every layer in
  `config/totem.keymap` keeps exactly 38 bindings. Run
  `./scripts/validate-keymap-shape.py config/totem.keymap` when checking
  separately from build script.
- Do not convert gaming layers to user's 34-key work layout. Full 38-key
  behavior intentional on gaming layers.
- No Docker or Colima for this project unless user explicitly asks.
- Do not create `firmware.zip`; desired outputs are the `.uf2` files.
- Do not erase or format volumes. Only copy matching UF2 to newly mounted
  bootloader volume and eject.
- If `XIAO-SENSE` disappears during or immediately after copying UF2, assume
  board accepted upload and rebooted unless installer reports
  `flash NOT complete`.
- Do not report failed flash just because installer silently waits for next
  half. Use installer status lines: `firmware install step
  complete` = that half succeeded.
- Wait for explicit user action via script prompts before each half.
