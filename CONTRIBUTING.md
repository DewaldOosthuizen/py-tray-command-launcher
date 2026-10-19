# Contributing

Contributions are welcome. Please read the [Contributing Guide](docs/contributing.md)
for the full workflow, including development setup, code standards, branch naming,
local validation steps, and the pull request process.

### Dependency updates

Dependency version updates are managed automatically by Dependabot (`.github/dependabot.yml`),
which opens pull requests for outdated pip packages every Monday.
A `pip-audit` step in the lint workflow scans all installed packages for known CVEs on every
push and pull request. When merging a Dependabot PR, confirm the audit step passes before
approving.
