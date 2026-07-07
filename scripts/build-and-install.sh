#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMMIT_MESSAGE="${1:-Update keymap}"
source "${ROOT}/scripts/lib/build-lock.sh"

cd "${ROOT}"

acquire_build_lock
ZMK_BUILD_LOCK_HELD=1 ./scripts/build-firmware-github.sh "${COMMIT_MESSAGE}"
PYTHONUNBUFFERED=1 ./scripts/install-uf2-macos.py --firmware-dir "${ROOT}/firmware"
