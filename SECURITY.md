# Security Policy

## Supported versions

The latest release on PyPI receives security fixes.

## Reporting a vulnerability

Please report suspected vulnerabilities privately through GitHub's
security advisories: open the repository's Security tab and choose
"Report a vulnerability". Do not open a public issue for anything you
believe has security impact.

You can expect an acknowledgment within a few days. Please include a
minimal reproduction if you can.

## Scope notes

- statgate makes no network calls and executes no code from results
  files. Adapters treat input strictly as data.
- `statgate sequential --run` executes the command template you supply
  through the system shell. That command comes from you, the operator;
  never wire untrusted text into it.
- The GitHub Action passes all inputs through environment variables
  rather than interpolating them into scripts.
