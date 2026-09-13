# Tuning decisions — TOTEM

What the timing numbers in `config/totem.keymap` and `config/totem.conf` are set to, why, and what was tried and rejected. Written 2026-09-13 after a week in which two changes were made, regressed, and reverted. Facts marked **verified** were re-derived from this machine or from ZMK's source at the pinned `v0.3` tag; facts marked **from docs** come from ZMK's published documentation and were not measured here.

## Bottom line

The keyboard is back on the settings it ran for months, plus two deliberate changes: `quick-tap-ms` raised from 100 to 150, and debounce moved from 8/8 to ZMK's stock 5/5.

Everything else that was tried in the 2026-09-08 experiment made typing worse and was reverted on 2026-09-11.

## Current settings

    &mt {
        flavor = "tap-preferred";
        tapping-term-ms = <170>;
        quick-tap-ms = <150>;
    };

    CONFIG_ZMK_KSCAN_DEBOUNCE_PRESS_MS=5
    CONFIG_ZMK_KSCAN_DEBOUNCE_RELEASE_MS=5
    CONFIG_ZMK_SLEEP=y

## The trap: `&mt` is shared with the thumb keys

This is the single most important thing on this page, because it is invisible when reading the `&mt` block alone.

`&mt` is not only the home-row mods. Two thumb keys use it too (**verified**, layer 0):

    position 33   &mt LEFT_SHIFT BSPC
    position 36   &mt RIGHT_ALT TAB

The other two thumbs use `&lt`, a separate behaviour that inherits nothing from `&mt`:

    position 34   &lt 1 SPACE
    position 35   &lt 2 RET

So **any property added to `&mt` lands on those two thumb keys as well.** On 2026-09-08 `require-prior-idle-ms = <150>` was added to `&mt` for the home row. On a thumb it means: type a letter, then hold thumb-Shift within 150 ms, and it resolves as a tap — **Backspace instead of Shift**, deleting a character instead of capitalising one. That was the "thumb keys sometimes don't work" regression.

**Do not add `require-prior-idle-ms` to `&mt`.** If it is ever wanted for the home row, it has to go on a separate behaviour used only by the ten home-row keys, the way ZMK's own documentation writes it.

## `flavor` — why `tap-preferred` and not `balanced`

`tap-preferred` never converts to a modifier because another key was pressed. It only holds if the key is genuinely held past `tapping-term-ms`. The cost is a wait before any modifier engages; the benefit is that fast typing cannot misfire a modifier.

`balanced` was tried on 2026-09-08 to remove that wait. It resolves to hold as soon as another key is pressed *and released* inside the tapping term, so same-hand rolls — `s` then `e`, positions 11 then 12, both left home row — started producing Alt. Mistypes went up. Reverted 2026-09-11.

ZMK's documented home-row-mod recipe pairs `balanced` with `hold-trigger-key-positions` (opposite hand only) and `hold-trigger-on-release`. Only the first half was applied, which is worse than either doing all of it or none of it.

**Cross-hand was offered and the owner declined it, explicitly.** It would mean a left-hand modifier only engages when the next key is on the right hand, which also removes same-hand modifier combinations entirely. Do not propose it again without being asked.

## `quick-tap-ms` — 150, chosen for "possible but not easy"

Tap a key, press it again within this window, and it holds the letter and auto-repeats instead of becoming the modifier.

Two mechanics matter, both **verified** in `zmk/app/src/behaviors/behavior_hold_tap.c` at `v0.3`:

- The window runs from the **first press**, not the release — `store_last_hold_tapped` records `hold_tap->timestamp`. A 90 ms tap inside a 150 ms window leaves roughly 60 ms to press again.
- `is_quick_tap()` requires `last_tapped.position == hold_tap->position`, so the modifier is delayed **only on the exact key just tapped**, never on the keyboard generally.

The original 100 left almost no time after a normal tap, which is why letter repeat never felt usable. 175 was tried and was too easy. 150 needs intent and will not fire by accident.

One dial, both directions: raise it to make repeat easier, lower it to reach the modifier sooner after tapping that same key.

## Debounce — history and what to do when keys double

ZMK's default is **5/5** (**verified**: the Kconfig symbols default to `-1`, which defers to the devicetree `debounce-press-ms` / `debounce-release-ms` properties, both `5`).

    8/8   before 2026-09-08   ran for months, no doubling
    1/5   2026-09-08          keys began registering twice on one press
    5/5   2026-09-11          current

ZMK's docs do recommend `PRESS_MS=1` as the near-eager setting, but that assumes clean switches. It was too low for this board. The earlier `8` was not arbitrary, whatever the commit comment claimed.

**If keys double again at 5/5:** note *which* keys before changing the number. The same few keys every time means worn switches or bad hotswap sockets, and raising debounce only masks it. Random keys across the board means the number is genuinely too low — go to 8/8.

## Gaming layer

Layer 3 is clean of hold-taps: every binding is a plain `&kp` (**verified**). There is no tap-hold latency there to tune.

Fifteen combos **are** live on it — `layers = <0 3 7>` on the arrow, media and brightness combos — covering positions 5, 6, 7, 8, 9, 15, 16, 17, 18, 19, 26, 27, 28 (**verified**). That is the whole right hand.

No movement key is affected. WASD sits at positions 11, 12, 13, 23, with space at 34, LSHFT at 21 and LCTRL at 10 — all clear of every combo on that layer (**verified**). The owner was asked whether to strip the fifteen and chose to keep them, since the right hand is on the mouse.

Two combos, `test` and `question-mark`, had no `layers` property at all and were therefore live on every layer including gaming, where `test` covers position 0 (TAB). Both were restricted to `layers = <0>` on 2026-09-08.

`question-mark` was renamed `plus` on 2026-09-11 and now sends `&kp PLUS`, at positions 19 and 30.

## Latency: where the time actually goes

Ranked, with the largest first.

**A USB cable into the left half is worth about 6.5 ms** and needs no firmware change at all. `totem_left` is the central half (**verified** in `config/boards/shields/totem/Kconfig.defconfig`, which sets `ZMK_SPLIT_ROLE_CENTRAL default y` under `SHIELD_TOTEM_LEFT`), and only the central can speak USB. The right half stays on Bluetooth regardless. The 6.5 ms figure is **from docs** — ZMK's dongle page — and was not measured here.

**The split link costs the right half 3.75 ms on average, 7.5 ms worst case** (**from docs**). The left half pays nothing. WASD being on the left is therefore already the fast side.

**There is nothing to gain on the Bluetooth connection interval.** ZMK already requests the 7.5 ms Bluetooth floor, and the Mac decides what it grants — Apple's accessory guidelines set a 15 ms minimum with an exception allowing 11.25 ms for Bluetooth HID. No ZMK setting changes this.

**`CONFIG_BT_CTLR_CONN_INTERVAL_LOW_LATENCY` does not exist in ZMK v0.3.** It is recommended in forum posts and in an upstream issue, it drives the split link to 1 ms, and it is a later-Zephyr feature. Setting it here would be silently ignored, which is worse than it failing loudly.

**Radio transmit power** (`CONFIG_BT_CTLR_TX_PWR_PLUS_8`) does not reduce typical latency — it buys link margin, so fewer retransmissions and dropouts in a noisy room, at a battery cost. Offered and declined; stays at 0 dBm.

Scan mode, USB polling interval and matrix wait times are already optimal and need no attention.

## Deep sleep

`CONFIG_ZMK_SLEEP=y` at the default 15 minutes. It does not merely dim things — it disconnects Bluetooth entirely, and reconnection takes a few seconds (**from docs**). The first keypress after an idle stretch is dead air.

Offered as a latency item and deliberately kept: the comment in `totem.conf` explains that a key held down in a bag does not reset the idle timer, so this also protects against a stuck switch replaying state on reconnect.

## Debounce cannot be changed per layer, per combo, or at runtime

Asked and answered on 2026-09-11. Debounce belongs to the kscan driver, which scans the physical switch matrix *below* the keymap. By the time a press reaches a layer or a combo, debouncing has already happened.

`docs/config/kscan.md` at `v0.3` contains no mention of runtime, layer, combo or dynamic control (**verified**). ZMK Studio, the feature built specifically for changing things without flashing, covers keymap layers, behaviours, combos and conditional layers — debounce does not appear in its capability table at all (**verified**).

A firmware build is the only way. If a lower-debounce gaming image is ever wanted, it has to be a second build kept on hand.

## Not related to this keyboard, but easily confused with it

kanata, the remapper on the MacBook, **does not touch the TOTEM**. Its `macos-dev-names-include` lists only `Apple Internal Keyboard / Trackpad` and `Bluetooth Keyboard`; the Totem's HID product name is `TOTEM` (**verified** via `ioreg`). When the built-in keyboard misbehaves and the Totem does not, the fault is kanata or Karabiner, never this firmware.
