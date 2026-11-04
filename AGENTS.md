# Agent assignment: NIRUORG 0.6.0, a one-shot correctness, repository and maintainability update

## 0. Quick start

1. Read this file, `README.md`, `SECURITY.md`, `CONTRIBUTING.md`, `docs/`,
   `niruorg/app.py`, `niruorg/transfer_safety.py`, `niruorg/core`, `niruorg/services` and
   `regression-suite.py`. The audit baseline is `2cf657f` (0.5.1, pinned as a NIRUX extra).
   Revalidate each item against current HEAD and skip items that are already fixed, noting
   that you did.
2. Implement **O1–O6, then U1–U4, then M1 last**. Commit per item. Keep
   `python regression-suite.py --non-qt`, `python regression-suite.py` (60/60 at baseline)
   and `niruorg/app.py --self-test` green.
3. Pass the gates in §4, release in §5 and report in §6.

This is an **execution** assignment. Do not stop after a plan or a branch. Make sensible
decisions, document them, and continue without routine questions.

## 1. Invariants (file safety comes first)

- No operation may lose or silently overwrite user data. Keep the transfer integrity
  rules (copy/replace/resume/cancel, symlink and self-copy protection), Trash by
  default, the confirmed permanent delete, and the undo of the last transfer.
- Keep the SSH helper safety: secrets go through an inherited FD, temp paths are
  unpredictable, and there is no secret in argv or logs. Keep the Nextcloud and mount
  lifecycle.
- Python and PySide6 (≥ 6.7) requirements stay as today. Add no new required dependency.
- Every test runs on temporary directories. Never run destructive tests in the owner's
  real home, mounts or servers.

## 2. Findings (verified 2026-11-04 on niruxwork, in a separate Xvfb with a temporary HOME)

### O1: The status bar item count is wrong
Opening a directory with 30 000 files showed every row, but the status bar said
**"0 item(s)"**. The count is probably computed before the async listing finishes and
never updated. **Fix:** update the count, size and selection summary when the
listing completes and on every incremental batch and filter change. Add a test.

### O2: Large directory performance
Measure the time to first rows and to a complete listing for 30 000 and 100 000 entries,
local and over SFTP using a local test sshd or the existing fake. Make sure that:
- rows appear incrementally within 300 ms,
- sorting and filtering do not block the UI for more than 100 ms per step,
- and memory stays bounded.

Fix the bottlenecks you find, for example per-row `stat` on the UI thread, mimetype
lookups, or icon loading. Report the numbers.

### O3: Breadcrumbs hide the path
In a deep path, every segment is middle-truncated: `L…ork`, `clau…1000`, `tmp…tWB`, so
the path cannot be read. **Fix:**
- Show the first segment, an `…` menu with the collapsed middle segments, and the last
  2–3 segments in full.
- The endpoint chip shows the full host name in a tooltip.
- Clicking the path makes it an editable location field (Ctrl+L).

### O4: The repository root is cluttered
More than 50 `*-test.py` files sit in the repository root next to the app. **Fix:**
- Move them to `tests/`, with an `__init__` or path setup as needed.
- Update `regression-suite.py`, CI and `CONTRIBUTING.md`.
- Keep the file names, so that the history stays searchable.

### O5: Stale branches
`feat/phase-1…4`, `fix/phase-0-split-settings`, `refactor/phase-5-modules` and
`release/0.5.0` are merged into `main`, so delete them.
`chore/mit-license-2026` is **not** merged. Check whether `main` already has the MIT
license (`LICENSE`). If it does, delete the branch. Otherwise merge only the license
change, and mention it in the report.

### O6: No GitHub release objects
`v0.5.0` and `v0.5.1` exist as tags, but there are no releases, and NIRUX pins by
tarball checksum. **Fix:** create GitHub releases for the existing tags with the notes
from `RELEASE_NOTES.md`/`CHANGELOG.md`. Do not move the tags. Add a small release
workflow for future tags.

## 3. UX

### U1: Show what is happening
Transfers already have activity. Also show a non-modal progress indicator for slow
listings ("Listing… 12 400 items") and for Nextcloud/SFTP connects, each with a Cancel
button.

### U2: Readable sidebar labels
"Add / manage clou…" is cut off at the default width. Shorten the labels ("Cloud
accounts…", "Add server…"), give the sidebar a sensible minimum width, and make it
resizable with the width remembered.

### U3: Keyboard
Add type-ahead find in the list (typing jumps to a matching name), Backspace = up,
Alt+Left/Right = back/forward, F5 = refresh, and Ctrl+L = location (O3). Document them in
Help → Shortcuts. Keep the existing shortcuts.

### U4: Empty and error states
Show a clear message in the pane instead of an empty list for: permission denied, a
disconnected mount, a server unreachable, and an empty folder. Each comes with one
relevant action (Retry, Reconnect, Open terminal here).

### M1: Readable source (last, behavior-neutral)
`niruorg/app.py` is about 3 570 lines with **103 lines over 300 characters**: whole menus
and widgets are written as `;`-joined one-liners. The "modules" refactor left almost
everything in `app.py`.
- Reformat in mechanical commits (`ruff format`/`black` as a dev-only tool).
- Then move the panes, dialogs, transfer UI, remote connections and the menu/actions into
  modules under `niruorg/ui/`.
- No logic change, and all 60+ tests green after each commit.

Out of scope: new cloud providers, sync, and a preview/thumbnail engine rewrite.

## 4. Gates

Automated:
- The existing suite.
- New tests: the O1 count after an async listing, the O2 incremental listing (fake
  directory iterator of 100 000 entries, asserting the UI-thread budget), O3 breadcrumb
  collapsing, U3 type-ahead, and the U4 states.

Native, on **niruxwork** (the owner allows local testing):
- Use a temporary HOME and test directories.
- Run the O2 measurements locally, and over SFTP to `localhost` or an owner-authorized
  host (othala, algiz or void) with a test directory that you create and remove.
- Check the U1–U4 flows.
- Do not connect to the owner's saved servers or cloud accounts in a way that changes
  them, and do not touch the owner's running NIRUORG, if any.

## 5. Release

Bump `VERSION` to **0.6.0** and update `CHANGELOG.md` and `RELEASE_NOTES.md`. Tag
`v0.6.0` and create the GitHub release (O6). Update the NIRUX extras pin in
`nirucon/nirux`: `docs/EXTRAS.md` and the version/checksum line in `nirux`
(`niruorg niruorg 0.5.1 <sha256>`), with the new tarball checksum. Install through the
NIRUX extras update and verify `niruorg --version`.

## 6. Final report

For each item O1–O6, U1–U4 and M1: the change, the tests and the evidence (listing times
and memory before and after, screenshots of the breadcrumbs and empty states). Include
the branch cleanup, release URLs, pinned versions and remaining limits. Mark anything
unfinished as **PARTIAL** and give the exact remaining steps.
