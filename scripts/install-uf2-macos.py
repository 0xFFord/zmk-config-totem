#!/usr/bin/env python3
from __future__ import annotations

import argparse
import errno
import os
from pathlib import Path
import subprocess
import sys
import time


DEFAULT_BOOTLOADER_VOLUME_NAMES = ("XIAO-SENSE", "UF2BOOT", "NICENANO", "NRF52BOOT")


def configure_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(line_buffering=True)


def notify(message: str, *, title: str = "TOTEM firmware") -> None:
    script = f'display notification "{message}" with title "{title}"'
    subprocess.run(["osascript", "-e", script], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def find_one_firmware(firmware_dir: Path, pattern: str) -> Path:
    matches = sorted(path for path in firmware_dir.glob(pattern) if path.is_file())
    if len(matches) != 1:
        found = "\n".join(f"  {path}" for path in matches) or "  none"
        raise SystemExit(f"Expected exactly one firmware file matching {pattern!r} in {firmware_dir}; found:\n{found}")
    return matches[0]


def snapshot_volumes() -> dict[str, Path]:
    root = Path("/Volumes")
    if not root.exists():
        raise SystemExit("/Volumes does not exist. This installer is for macOS.")

    volumes: dict[str, Path] = {}
    for path in root.iterdir():
        if path.name.startswith("."):
            continue
        if path.is_dir() and os.access(path, os.W_OK):
            volumes[path.name] = path
    return volumes


def choose_volume(candidates: list[Path]) -> Path:
    if len(candidates) == 1:
        return candidates[0]

    print("\nMultiple new writable volumes appeared:")
    for idx, path in enumerate(candidates, start=1):
        print(f"  {idx}. {path}")

    while True:
        try:
            choice = input("Select the keyboard bootloader volume number: ").strip()
        except (EOFError, KeyboardInterrupt) as exc:
            raise SystemExit(
                "multiple candidate volumes and no interactive stdin -- pass --half or --bootloader-volume-name"
            ) from exc
        if choice.isdigit():
            index = int(choice)
            if 1 <= index <= len(candidates):
                return candidates[index - 1]
        print("Invalid selection.")


def bootloader_candidates(volumes: dict[str, Path], bootloader_volume_names: list[str]) -> list[Path]:
    expected_names = {name.upper() for name in bootloader_volume_names}
    return [volumes[name] for name in sorted(volumes) if name.upper() in expected_names]


def wait_for_bootloader_volume(label: str, timeout_seconds: int, bootloader_volume_names: list[str]) -> Path:
    baseline = snapshot_volumes()
    existing_candidates = bootloader_candidates(baseline, bootloader_volume_names)
    if existing_candidates:
        volume = choose_volume(existing_candidates)
        print(f"\n{label}: using already-mounted bootloader volume: {volume}")
        notify(f"{label} bootloader volume appeared. Reset worked.")
        return volume

    print(f"\n{label}: connect this half, then double-click reset to enter the UF2 bootloader.")
    print("Waiting for a bootloader volume to appear in /Volumes ...")
    notify(f"Connect {label.lower()} half and double-click reset.")

    start = time.monotonic()
    while True:
        current = snapshot_volumes()
        new_names = sorted(set(current) - set(baseline))
        new_volumes = {name: current[name] for name in new_names}
        candidates = bootloader_candidates(new_volumes, bootloader_volume_names)
        if not candidates:
            candidates = [new_volumes[name] for name in new_names]

        if candidates:
            volume = choose_volume(candidates)
            print(f"Detected bootloader volume: {volume}")
            notify(f"{label} bootloader volume appeared. Reset worked.")
            return volume

        if timeout_seconds and time.monotonic() - start > timeout_seconds:
            raise SystemExit(f"Timed out waiting for {label} bootloader volume.")

        time.sleep(1)


def wait_for_disappear(volume: Path, timeout_seconds: int = 45) -> bool:
    start = time.monotonic()
    while volume.exists() and time.monotonic() - start <= timeout_seconds:
        time.sleep(1)
    return not volume.exists()


def expected_auto_disconnect_error(error: OSError) -> bool:
    # The UF2 bootloader reboots and drops the mass-storage volume the instant it
    # accepts the image, so the copy's final flush/fsync/close can fail with one
    # of these. macOS most often surfaces this as EIO (Errno 5). This is only
    # treated as success when the full source size was written (see
    # copy_firmware_file); a mid-transfer error still fails as an incomplete flash.
    expected_errnos = {
        errno.ENOENT,
        getattr(errno, "EIO", -1),
        getattr(errno, "ENOTCONN", -1),
        getattr(errno, "ENXIO", -1),
    }
    return error.errno in expected_errnos


def copy_firmware_file(source: Path, destination: Path, accept_auto_disconnect: bool) -> int:
    source_size = source.stat().st_size
    bytes_written = 0

    try:
        with source.open("rb") as source_file, destination.open("wb") as destination_file:
            while True:
                chunk = source_file.read(1024 * 1024)
                if not chunk:
                    break
                destination_file.write(chunk)
                bytes_written += len(chunk)
            destination_file.flush()
            os.fsync(destination_file.fileno())
    except OSError as exc:
        if accept_auto_disconnect and expected_auto_disconnect_error(exc):
            if bytes_written == source_size:
                return bytes_written
            raise SystemExit(
                f"volume disappeared after {bytes_written} of {source_size} bytes -- "
                "flash NOT complete, re-enter bootloader and retry"
            ) from exc
        raise

    return bytes_written


def flash_half(
    label: str,
    firmware: Path,
    timeout_seconds: int,
    dry_run: bool,
    bootloader_volume_names: list[str],
    accept_auto_disconnect: bool,
) -> None:
    volume = wait_for_bootloader_volume(label, timeout_seconds, bootloader_volume_names)
    destination = volume / firmware.name

    print(f"Installing {firmware.name} to {volume} ...")
    if dry_run:
        print(f"Dry run: would copy {firmware} -> {destination}")
        return

    copy_error: OSError | None = None
    bytes_copied = 0
    try:
        bytes_copied = copy_firmware_file(firmware, destination, accept_auto_disconnect)
        os.sync()
    except OSError as exc:
        copy_error = exc

    time.sleep(2)

    if copy_error is not None:
        disappeared = wait_for_disappear(volume, timeout_seconds=8)
        if accept_auto_disconnect and disappeared and expected_auto_disconnect_error(copy_error):
            print(f"{label}: bootloader volume disappeared during copy; treating this as expected UF2 reboot.")
        else:
            raise SystemExit(f"{label}: failed to copy {firmware.name} to {volume}: {copy_error}") from copy_error
    elif volume.exists():
        subprocess.run(["diskutil", "eject", str(volume)], check=False)
        if not wait_for_disappear(volume):
            raise SystemExit(f"{label}: bootloader volume did not disappear after copy/eject: {volume}")
    else:
        print(f"{label}: bootloader volume disappeared after copy; treating this as expected UF2 reboot.")

    print(f"{label}: copied {bytes_copied} bytes.")
    print(f"{label} firmware install step complete.")
    notify(f"{label} firmware install step complete.")


def main() -> int:
    configure_output()

    parser = argparse.ArgumentParser(description="Install TOTEM UF2 firmware files on macOS.")
    parser.add_argument("--firmware-dir", type=Path, default=Path(__file__).resolve().parents[1] / "firmware")
    parser.add_argument("--left-pattern", default="*left*.uf2")
    parser.add_argument("--right-pattern", default="*right*.uf2")
    parser.add_argument("--half", choices=("both", "left", "right"), default="both")
    parser.add_argument(
        "--bootloader-volume-name",
        dest="bootloader_volume_names",
        action="append",
        default=None,
        help=(
            "Writable bootloader volume name to trust if already mounted. "
            "Can be passed more than once; provided values replace the built-in list."
        ),
    )
    parser.add_argument("--timeout", type=int, default=0, help="Seconds to wait for each half; 0 waits forever.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--preflight", action="store_true", help="Validate firmware file selection and exit.")
    parser.add_argument(
        "--strict-copy",
        action="store_true",
        help="Fail if the bootloader volume disappears during copy instead of treating it as a UF2 reboot.",
    )
    args = parser.parse_args()
    if args.bootloader_volume_names is None:
        args.bootloader_volume_names = list(DEFAULT_BOOTLOADER_VOLUME_NAMES)

    if sys.platform != "darwin":
        raise SystemExit("This installer is for macOS because it watches /Volumes and uses diskutil.")

    firmware_dir = args.firmware_dir.expanduser().resolve()
    install_left = args.half in ("both", "left")
    install_right = args.half in ("both", "right")
    left = find_one_firmware(firmware_dir, args.left_pattern) if install_left else None
    right = find_one_firmware(firmware_dir, args.right_pattern) if install_right else None

    print("Firmware files:")
    if left is not None:
        print(f"  left:  {left}")
    if right is not None:
        print(f"  right: {right}")
    if args.half == "both":
        print("\nOrder: left half first, then right half.")
    else:
        print(f"\nInstall target: {args.half} half only.")

    if args.preflight:
        return 0

    if left is not None:
        flash_half(
            "Left half",
            left,
            args.timeout,
            args.dry_run,
            args.bootloader_volume_names,
            not args.strict_copy,
        )

    if args.half == "both":
        print("\nDisconnect the left half. Connect the right half when ready.")

    if right is not None:
        flash_half(
            "Right half",
            right,
            args.timeout,
            args.dry_run,
            args.bootloader_volume_names,
            not args.strict_copy,
        )

    if args.half == "both":
        print("\nBoth keyboard halves are installed.")
        notify("Both keyboard halves are installed.")
    else:
        print(f"\n{args.half.capitalize()} half is installed.")
        notify(f"{args.half.capitalize()} half is installed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
