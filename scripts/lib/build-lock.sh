#!/usr/bin/env bash

if [ -z "${LOCK_DIR:-}" ]; then
  git_dir="$(git -C "${ROOT}" rev-parse --git-dir 2>/dev/null || echo "${ROOT}/.git")"
  case "${git_dir}" in
    /*) ;;
    *) git_dir="${ROOT}/${git_dir}" ;;
  esac
  LOCK_DIR="${ZMK_BUILD_LOCK_DIR:-${git_dir}/zmk-build.lock}"
fi

acquire_build_lock() {
  if [ "${ZMK_BUILD_LOCK_HELD:-}" = "1" ]; then
    return
  fi

  local lock_pid=""
  local attempt=""

  for attempt in 1 2 3 4 5; do
    if mkdir "${LOCK_DIR}" 2>/dev/null; then
      printf '%s\n' "$$" > "${LOCK_DIR}/pid"
      trap 'rm -rf "${LOCK_DIR}"' EXIT
      return
    fi

    lock_pid=""
    if [ -f "${LOCK_DIR}/pid" ]; then
      lock_pid="$(cat "${LOCK_DIR}/pid" 2>/dev/null || true)"
    fi

    if [ -n "${lock_pid}" ] && kill -0 "${lock_pid}" 2>/dev/null; then
      echo "Another build/install is already running (pid ${lock_pid})." >&2
      exit 1
    fi

    if [ -n "${lock_pid}" ]; then
      echo "Removing stale build lock from process ${lock_pid}."
    else
      echo "Removing stale build lock with missing pid."
    fi

    rm -rf "${LOCK_DIR}" 2>/dev/null || true
  done

  echo "Could not acquire build/install lock after removing stale lock: ${LOCK_DIR}" >&2
  exit 1
}
