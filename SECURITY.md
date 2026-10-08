# Security

NIRUORG is a personal desktop file manager with destructive filesystem and remote-storage capabilities. It is not a security boundary around untrusted local users.

## Report vulnerabilities

Do not publish credentials, private SSH keys, API tokens or raw connection logs in a public issue. For security-sensitive reports, contact the repository owner through GitHub first or use GitHub's private vulnerability reporting feature when enabled.

## Safety model

- SFTP authentication delegates to OpenSSH/ssh-agent when available.
- FTP/FTPS and cloud integrations use rclone or the relevant external provider. Plain FTP is not encrypted; prefer SFTP/FTPS on untrusted networks.
- Saved secrets require the desktop Secret Service; settings and source packages must not include passwords.
- FUSE mounts created by the application are tracked for normal cleanup; an unresponsive remote may still require manual intervention.
- File transfers use staged publication. Resume data is verified against its source and rejects mismatches.
- No guarantee is made that FUSE, network storage or system-level crashes can never interrupt a transfer.

Before filing a bug report, remove private hostnames, usernames, secrets, local IPs and sensitive paths from diagnostic output.
