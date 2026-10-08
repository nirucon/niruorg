# NIRUORG 0.3.0 — Transfer Integrity & GitHub Baseline

A substantial stabilization release, based on 0.2.0, prepared for the first public GitHub source release.

### Improvements

- **Safer file resume:** a pre-existing `.niruorg-part` must match the beginning of the source exactly. Corrupt/mismatched partials are preserved and reported, not reused blindly.
- **Safer Replace:** an existing file is no longer unlinked before the new file finishes transferring. File and directory updates are staged, with directory rollback on failed publication.
- **Safer directory operations:** no recursive self-copy; directory staging is cancelled without destroying an existing destination. Symlinks are preserved without following their targets.
- **Safer Undo:** automatic Undo refuses replacements and remote paths where it cannot safely reconstruct the previous state.
- **UI fixes:** a malformed Qt polygon draw call is corrected, and the published keyboard reference matches actual shortcuts.
- **Installer hardening:** upgrades no longer install optional system packages implicitly, and the active release is protected from accidental in-place replacement.
- **SSH key handling:** the temporary askpass script is now created with a unique, restrictive file creation operation.
- **Project quality:** Qt-free transfer-integrity regression tests, GitHub Actions checks, English docs, release/rollback guidance, repository hygiene and documentation (licensing remains the owner’s decision).

### Upgrade

Install with `./install.sh`. Settings, saved connections and previous installed releases are kept. The installer refuses activation if a required check fails. Review the output and try a small **Local → SFTP → Local** round trip before transferring critical data.

### Important limitations

- Real Hyprland/Wayland interaction and SSHFS/rclone behavior require testing on a desktop with actual endpoints; GitHub CI cannot certify those environments.
- Existing remotely mounted paths can still block a few less-used UI operations. NIRUORG is not an automatic two-way synchronization tool.
- Previously saved partials may now fail verification if the original source changed. This is intentional data protection; handle partial files explicitly.
