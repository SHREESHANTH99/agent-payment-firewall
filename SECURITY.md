# Security Policy

## Supported Versions
Only the latest commit on the `main` branch of this repository is supported for security fixes.

| Version | Supported          |
| ------- | ------------------ |
| `main`  | :white_check_mark: |

## Reporting a Vulnerability
We welcome responsible security disclosures. If you discover a security vulnerability in the Agent Payment Firewall, please do **NOT** open a public GitHub issue.

Instead, please send an encrypted or direct email to the project maintainers with:
- A description of the vulnerability and attack vector.
- Steps to reproduce or proof-of-concept payload.
- Affected components (backend, rules engine, canary honeypot, judge, or dashboard).

Maintainers will acknowledge receipt within 48 hours and work on a coordinated fix.

## Security Constraints
- **Sandbox Only**: This project connects exclusively to the PayPal Sandbox environment (`https://api-m.sandbox.paypal.com`). Live production credentials and live settlement endpoints must never be used.
- **Fail-Closed Design**: If an AI risk layer (canary or judge) suffers an API outage, timeout, or quota breach, the firewall fails closed by holding or denying the transaction.
