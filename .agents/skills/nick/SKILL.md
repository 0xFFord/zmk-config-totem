---
name: nick
description: Open Nick Coutsos' Keymap Editor for this TOTEM repo in T3 Code's browser — GitHub source, repo zmk-config-totem, branch gui-edits. Use when the owner types /nick or asks to open the keymap editor or GUI.
---

# /nick — open the keymap GUI

The GUI is the owner's tool (`AGENTS.md` → GUI Workflow). This skill prepares
the branch and opens the editor for him; the owner does all clicking, editing
and saving.

## Steps

1. **Sync the branch:** `./scripts/gui-branch-sync.sh`. Done when it prints
   `gui-edits ready …`, or lists unmerged keymap commits. Unmerged commits
   are earlier GUI edits still waiting for review: tell the owner, and offer
   the GUI Workflow review before he edits further.
2. **Open the editor:**
   `preview_open({url: "https://nickcoutsos.github.io/keymap-editor/", reuseExistingTab: false, open: true})`.
   Keep the returned `tabId` for every later call.
3. **Preset source, repo and branch** with `preview_evaluate` in that tab:

   ```js
   (() => {
     const set = (k, v) => { localStorage.setItem(k, v); sessionStorage.setItem(k, v); };
     set('selectedSource', 'github');
     set('selectedGithubRepository', '1185364380');
     set('selectedGithubBranch:1185364380', JSON.stringify('gui-edits'));
     setTimeout(() => location.reload(), 100);
     return 'ok';
   })()
   ```

4. **Check the result:** after ~5 s, `preview_evaluate`
   `document.body.innerText.slice(0, 600)`. Done when the text matches one case:
   - contains `zmk-config-totem` and `gui-edits` → tell the owner the editor
     is ready in the browser pane, on branch `gui-edits`.
   - contains `Login with GitHub` → this tab has no GitHub login. Tell the
     owner to click **Login with GitHub** in the browser pane; the preset
     from step 3 survives the login.
   - contains `zmk-config-totem` with another branch (e.g. `master`) → tell
     the owner to pick `gui-edits` in the branch selector before saving.

## How the preset works

- The editor reads `selectedSource`, `selectedGithubRepository` and
  `selectedGithubBranch:<repo id>` from sessionStorage first, then
  localStorage; values for the repo and branch keys are JSON. Setting both
  storages is what makes the preset stick.
- `1185364380` is the GitHub id of `0xFFord/zmk-config-totem`
  (`gh api repos/0xFFord/zmk-config-totem --jq .id`).
- A tab the agent opens can start with its own browser storage, without the
  owner's GitHub login — hence the login case in step 4.
- When the browser is unreachable (`No preview automation host …`), give the
  owner the URL and the branch to pick instead.
