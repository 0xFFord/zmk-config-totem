#!/usr/bin/env bash
# Make origin/gui-edits ready for a Keymap Editor session (see AGENTS.md, GUI Workflow).
#   - missing          -> create it at origin/master
#   - behind master    -> fast-forward it to origin/master
#   - has own commits  -> leave it alone and report them (GUI edits awaiting review)
set -euo pipefail
cd "$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"

git fetch -q origin
master=$(git rev-parse origin/master)

if ! git rev-parse -q --verify origin/gui-edits >/dev/null; then
  git push -q origin "origin/master:refs/heads/gui-edits"
  echo "gui-edits ready (created at $(git rev-parse --short "$master"))"
  exit 0
fi

pending=$(git rev-list --count origin/master..origin/gui-edits -- config)
if [ "$pending" -gt 0 ]; then
  echo "gui-edits has $pending unmerged keymap commit(s):"
  git log --oneline origin/master..origin/gui-edits -- config
  exit 0
fi

if git merge-base --is-ancestor origin/gui-edits origin/master; then
  if [ "$(git rev-parse origin/gui-edits)" != "$master" ]; then
    git push -q origin "origin/master:refs/heads/gui-edits"
  fi
  echo "gui-edits ready (at $(git rev-parse --short "$master"))"
else
  # Only non-keymap commits (keymap-drawer renders) diverge: safe to reset.
  git push -q --force-with-lease=gui-edits:"$(git rev-parse origin/gui-edits)" \
    origin "origin/master:refs/heads/gui-edits"
  echo "gui-edits ready (reset to $(git rev-parse --short "$master"); dropped render-only commits)"
fi
