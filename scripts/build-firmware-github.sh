#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKFLOW="${GITHUB_WORKFLOW_FILE:-build.yml}"
ARTIFACT="${GITHUB_FIRMWARE_ARTIFACT:-firmware}"
DOWNLOAD_DIR="${GITHUB_FIRMWARE_DIR:-${ROOT}/firmware}"
COMMIT_MESSAGE="${1:-}"
DEFAULT_COMMIT_PATHS=(config build.yaml .github/workflows)
source "${ROOT}/scripts/lib/build-lock.sh"

cd "${ROOT}"
export GIT_TERMINAL_PROMPT=0

acquire_build_lock

if ! command -v gh >/dev/null 2>&1; then
  echo "GitHub CLI (gh) was not found." >&2
  exit 127
fi

gh auth status >/dev/null
if [ "${GITHUB_FIRMWARE_SKIP_AUTH_SETUP:-}" = "1" ]; then
  :
elif git config --global --get-all credential."https://github.com".helper 2>/dev/null | grep -q 'gh'; then
  :
elif ! gh auth setup-git >/dev/null 2>&1; then
  echo "Warning: could not update git credential setup from gh auth; continuing." >&2
fi
./scripts/validate-keymap-shape.py --quiet config/totem.keymap

branch="$(git branch --show-current)"
if [ -z "${branch}" ]; then
  echo "Cannot build from a detached HEAD. Check out a branch first." >&2
  exit 1
fi

remote_url="$(git remote get-url origin)"
repo="$(printf '%s\n' "${remote_url}" | sed -E 's#^git@github.com:##; s#^https://github.com/##; s#\.git$##')"

if [ -z "${repo}" ]; then
  echo "Could not determine GitHub repo from origin remote: ${remote_url}" >&2
  exit 1
fi

if [ -n "${GITHUB_FIRMWARE_COMMIT_PATHS:-}" ]; then
  read -r -a commit_paths <<< "${GITHUB_FIRMWARE_COMMIT_PATHS}"
else
  commit_paths=("${DEFAULT_COMMIT_PATHS[@]}")
fi

firmware_changes=false
if ! git diff --quiet -- "${commit_paths[@]}" ||
  ! git diff --cached --quiet -- "${commit_paths[@]}" ||
  [ -n "$(git ls-files --others --exclude-standard -- "${commit_paths[@]}")" ]; then
  firmware_changes=true
fi

if [ "${firmware_changes}" = true ]; then
  if [ -z "${COMMIT_MESSAGE}" ]; then
    cat >&2 <<'EOF'
There are uncommitted firmware source changes.

Commit them first, or pass a commit message:

  ./scripts/build-firmware-github.sh "Update keymap"
EOF
    exit 1
  fi

  git add -- "${commit_paths[@]}"
  git commit -m "${COMMIT_MESSAGE}" -- "${commit_paths[@]}"
fi

sha="$(git rev-parse HEAD)"

echo "Pushing ${branch} to ${repo}..."
if ! push_output="$(git push -u origin "${branch}" 2>&1)"; then
  printf '%s\n' "${push_output}"
  exit 1
fi
printf '%s\n' "${push_output}"

run_id=""
for _ in $(seq 1 20); do
  run_id="$(gh run list \
    --repo "${repo}" \
    --workflow "${WORKFLOW}" \
    --commit "${sha}" \
    --limit 1 \
    --json databaseId \
    --jq '.[0].databaseId // ""')"

  if [ -n "${run_id}" ]; then
    break
  fi

  sleep 3
done

if [ -z "${run_id}" ]; then
  echo "No push-triggered run found for ${sha}; triggering workflow_dispatch on ${branch}..."
  gh workflow run "${WORKFLOW}" --repo "${repo}" --ref "${branch}"

  for _ in $(seq 1 20); do
    run_id="$(gh run list \
      --repo "${repo}" \
      --workflow "${WORKFLOW}" \
      --branch "${branch}" \
      --event workflow_dispatch \
      --limit 1 \
      --json databaseId,headSha \
      --jq ".[] | select(.headSha == \"${sha}\") | .databaseId")"

    if [ -n "${run_id}" ]; then
      break
    fi

    sleep 3
  done
fi

if [ -z "${run_id}" ]; then
  echo "Could not find or create a GitHub Actions run for ${sha}." >&2
  exit 1
fi

echo "Watching GitHub Actions run ${run_id}..."
watch_args=("${run_id}" --repo "${repo}" --exit-status)
if gh run watch --help 2>/dev/null | grep -q -- '--compact'; then
  watch_args+=(--compact)
fi
gh run watch "${watch_args[@]}"

rm -rf "${DOWNLOAD_DIR}"
mkdir -p "${DOWNLOAD_DIR}"

echo "Downloading artifact '${ARTIFACT}' into ${DOWNLOAD_DIR}..."
gh run download "${run_id}" --repo "${repo}" --name "${ARTIFACT}" --dir "${DOWNLOAD_DIR}"

echo "Downloaded firmware files:"
find "${DOWNLOAD_DIR}" -maxdepth 1 -type f -name '*.uf2' -print | sort
