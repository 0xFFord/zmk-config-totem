# zmk-config-totem

Personal [ZMK](https://zmk.dev) firmware configuration for the
[GEIGEIGEIST TOTEM](https://github.com/GEIGEIGEIST/TOTEM), a 38-key
column-staggered split keyboard, running on Seeed XIAO nRF52840 BLE
controllers.

The keymap lives in [config/totem.keymap](config/totem.keymap). The primary
typing layer is a custom layout ("Asergo"), not QWERTY. A rendered diagram is
generated automatically into `keymap-drawer/` on every keymap change.

## Building

Firmware is built by GitHub Actions using ZMK's reusable user-config workflow,
pinned to ZMK `v0.3`. Every push builds three UF2 images: `totem_left`,
`totem_right`, and `settings_reset` (a recovery image that clears BLE bonds if
the halves stop pairing). Download them from the workflow run's `firmware`
artifact, or from a GitHub Release when a `v*` tag is pushed.

There is no local build setup; CI is the build authority.

## Flashing (macOS)

Put a half into bootloader mode by double-tapping its reset button, then drag
the matching UF2 onto the mounted bootloader volume — or use the helper, which
waits for the volume, verifies the copy, and handles both halves in order:

```sh
./scripts/install-uf2-macos.py --firmware-dir firmware
```

`./scripts/build-and-install.sh "commit message"` runs the full loop: commit,
push, wait for CI, download the artifact, flash both halves.

## Repository notes

The shield definition in `config/boards/shields/totem/` mirrors the upstream
[GEIGEIGEIST/zmk-config-totem](https://github.com/GEIGEIGEIST/zmk-config-totem)
shield (TOTEM is not part of mainline ZMK). `AGENTS.md` and
`.agents/skills/build/` contain agent-facing workflow instructions rather than
user documentation.
