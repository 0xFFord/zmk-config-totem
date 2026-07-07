# GitHub Actions Build Notes For Agents

Supporting detail for project scripts. For task routing, follow `AGENTS.md`
first. For `/build`, `$build`, build, download, and install requests, use
repo-local `build` skill in `.agents/skills/build`.

## Workflow

`.github/workflows/build.yml` uses ZMK's reusable user-config build workflow.
Markdown-only and `keymap-drawer/` commits do not trigger firmware builds.
`build.yaml` defines three firmware targets:

```text
seeeduino_xiao_ble + totem_left
seeeduino_xiao_ble + totem_right
seeeduino_xiao_ble + settings_reset
```

`settings_reset` = recovery firmware, wipes BLE bonds; flash only when halves
stop pairing, then reflash that half's normal firmware.

Other workflows: `lint.yml` (shellcheck, Python syntax, keymap shape check),
`draw.yml` (keymap-drawer SVG render on keymap changes), `release.yml`
(builds and attaches renamed UF2s to GitHub Release on `v*` tags).

Expected GitHub Actions artifact name:

```text
firmware
```

## Helper Behavior

Run for build/download-only requests:

```sh
./scripts/build-firmware-github.sh "Update keymap"
```

The helper:

- Takes shared build lock (`scripts/lib/build-lock.sh`) so runs never overlap;
  stale locks from dead processes removed automatically.
- Validates keymap shape with `scripts/validate-keymap-shape.py` before
  committing or pushing.
- Detects current branch and `origin` GitHub repository; skips
  `gh auth setup-git` when git credentials already configured for `gh` (or
  when `GITHUB_FIRMWARE_SKIP_AUTH_SETUP=1`).
- Commits firmware source edits under `config`, `build.yaml`,
  `.github/workflows` when commit message provided. Edits elsewhere
  (`scripts/`, docs) never auto-committed.
- Pushes branch.
- Looks for existing GitHub Actions run for HEAD commit — even when push
  reports everything up-to-date — and triggers `workflow_dispatch` only if
  none exists.
- Downloads extracted artifact contents into `firmware/`.

Expected local files after download:

```text
firmware/totem_left-seeeduino_xiao_ble-zmk.uf2
firmware/totem_right-seeeduino_xiao_ble-zmk.uf2
firmware/settings_reset-seeeduino_xiao_ble-zmk.uf2
```

Do not create `firmware.zip`. GitHub stores artifacts as ZIP internally, but
`gh run download` extracts them for this workflow.

## Build And Install

For build plus flashing:

```sh
./scripts/build-and-install.sh "Update keymap"
```

Runs GitHub build helper, then flashes with:

```sh
./scripts/install-uf2-macos.py --firmware-dir firmware
```

Installer is macOS-specific. Watches `/Volumes`, prompts for each half, copies
matching UF2 to bootloader volume with byte-count verification (incomplete
copy fails loudly instead of reporting success), syncs, tries to eject.
Install order: left half first, then right half.
`settings_reset` UF2 never flashed by default; to flash it, target one half
explicitly, e.g.
`./scripts/install-uf2-macos.py --half left --left-pattern 'settings_reset*.uf2'`.

## Preconditions

- `gh` installed and authenticated.
- Current branch pushable to `origin`.
- Network access available.
- macOS required for install script.
