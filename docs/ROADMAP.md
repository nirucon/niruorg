# Engineering roadmap after 0.4.0

The following are **not implemented** in 0.4.0 and should be approached incrementally with real SSHFS/rclone testing:

1. Remove remaining blocking FUSE metadata and directory operations from the GUI thread; introduce cancellation and bounded worker lifetimes.
2. Expand transfer activity into an inspectable queue with explicit failure/retry states and verified resume.
3. Add dry-run-only comparison plans before implementing directional sync; never silently delete/overwrite.
4. Profile large-directory navigation and debounce obsolete work on rapid tab switches.
5. Unify remote connection status with distinct offline/authentication/stale states.
6. Consolidate overlapping saved-location concepts only after a settings migration plan.
7. Split large `app.py` incrementally behind tested interfaces, rather than wholesale rewriting.
