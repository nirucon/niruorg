# First GitHub publication: nirucon/niruorg

The intended repository is https://github.com/nirucon/niruorg. The project is authored for a personal Omarchy/Arch setup. Publish **source contents**, not an extracted zip tree nested under `NIRUORG-0.3.0/` and not accumulated historical release ZIPs.

This first-publication procedure assumes the remote repository is empty. **Stop and inspect if a README/commit or unexpected files already exist**, instead of force-pushing.

## Recommended directory layout

Keep your downloaded files and historical versions outside the Git working tree:

```text
Nextcloud/Projects-Dev/niruorg/
├── NIRUORG-0.3.0.zip
├── NIRUORG-0.3.0/     # extracted release (not a Git repository)
└── niruorg-git/       # cloned repository, Git root
    ├── .git/
    ├── .github/
    ├── README.md
    ├── niruorg/
    └── install.sh
```

From a Fish prompt in `Nextcloud/Projects-Dev/niruorg`, after saving the ZIP here:

```fish
command gh auth status
command unzip -q NIRUORG-0.3.0.zip
command git clone https://github.com/nirucon/niruorg.git niruorg-git
command cp -a NIRUORG-0.3.0/. niruorg-git/
cd niruorg-git
command git status --short
```

**Before staging:** check that the working tree contains no private server configurations, SSH keys, rclone tokens, local home-directory state or large release ZIPs. This package intentionally contains generic connection examples; never copy your personal settings into the repo.

## First commit and push

```fish
command git add -A
command git diff --cached --stat
command git diff --cached --check
command git commit -m "Initial public source release: NIRUORG 0.3.0"
command git push -u origin main
```

If Git reports missing author identity, configure your preferred name/email using `git config --global user.name` and `git config --global user.email`, or use repo-local config. Avoid force-push.

## Verify GitHub Actions

```fish
command gh run list --repo nirucon/niruorg --limit 5
command gh run watch --repo nirucon/niruorg
```

Inspect failing job logs and fix the source before tagging. Some Qt/headless regressions can be platform-dependent; a green CI build still requires real Omarchy/Hyprland plus remote-transfer acceptance testing.

## Tag and create a release

After the commit, CI, and the manual local tests have passed:

```fish
command git tag -a v0.3.0 -m "NIRUORG 0.3.0"
command git push origin v0.3.0
command gh release create v0.3.0 ../NIRUORG-0.3.0.zip --repo nirucon/niruorg --title "NIRUORG 0.3.0 — Transfer Integrity & GitHub Baseline" --notes-file RELEASE_NOTES.md
```

`../NIRUORG-0.3.0.zip` is relative to `niruorg-git/`. If you need to change a release after publishing, prefer a new patch version rather than overwriting a published tagged archive.

## For subsequent versions

Work in `niruorg-git/`, create a branch, edit code, run tests, commit, push, open a pull request, and only tag after merging. The ZIP for users remains a separate release asset generated from the tested source, not a second copy of the project committed to main.
