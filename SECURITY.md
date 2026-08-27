# Security Policy

## Supported Versions

Before the first stable release, security fixes are made on the default branch
only. After 1.0, the latest minor release of the current major version receives
security fixes. Older minor releases may require upgrading to receive a fix.
Support for an older major version, if any, will be listed here explicitly.

Python versions and platforms follow [the support policy](docs/support.md).

## Reporting a Vulnerability

Report suspected vulnerabilities through GitHub's private vulnerability
reporting flow for `Revolution1/pygotpl`. Include:

- the affected version or commit;
- the relevant template, data shape, function registry, and policy;
- observed and expected behavior;
- impact and a minimal reproduction; and
- whether the issue is already public or actively exploited.

Do not open a public issue for an undisclosed vulnerability. If private
reporting is unavailable, contact the repository owner through their GitHub
profile without including exploit details and request a private channel.

The project aims to acknowledge a report within five business days and provide
an initial assessment or request for more information within ten business days.
Resolution timing depends on severity, compatibility impact, and coordinated
disclosure needs. Reporters will receive material status changes before public
disclosure where practical.

## Security Boundary

Contextual HTML escaping, the opt-in template sandbox, execution budgets, and
operating-system isolation are separate controls. The in-process sandbox cannot
enforce hard CPU, wall-time, process-memory, or all regular-expression limits.
Untrusted multi-tenant rendering requires a resource-limited worker process.

Non-hermetic function profiles may access environment state, DNS, randomness,
cryptography, or serializers. Optional dependencies are imported only when the
corresponding function is called, but installing an extra does not grant a
template permission. Review [sandboxing](docs/sandbox.md) and the
[Sprig security boundary](docs/sprig-security.md) before accepting untrusted
templates.

Security reports concerning Go, Sprig, Slim-Sprig, Sprout, Helm, PyYAML,
cryptography, or another dependency should also identify whether the behavior
exists upstream. Upstream behavior does not automatically make an unsafe
default acceptable, but it can affect remediation and disclosure coordination.
