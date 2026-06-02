# Security Policy

## Supported Versions

We generally support the latest released version. Older versions may receive security fixes on a best-effort basis.

## Reporting a Vulnerability

Please report security issues privately by opening a GitHub Security Advisory (preferred) or emailing the maintainer via the GitHub profile contact.

**Do not** open public issues for vulnerabilities.

## What to Expect

- Acknowledgement within 48 hours
- Investigation and patch timeline communicated
- Credit in release notes (unless you prefer anonymity)

## Design Notes (relevant to security)

- All destructive operations (`prune`, `restore`, `backup` overwrites) default to `--dry-run` and require explicit confirmation.
- `backup restore` and `skills unpack` use `safe_extract_tar` which performs path traversal (zip-slip) prevention before extraction.
- Manifest SHA-256 verification is performed after restore when present.
- No network activity in most commands (MCP `test`/`doctor` do limited local subprocess delegation to your local `grok` binary only when present).
- The tools read from (and in controlled cases write to) your real `~/.grok` directory — treat backups and restores with the same care you would any user data migration.

Thank you for helping keep the Grok Build ecosystem safe.
