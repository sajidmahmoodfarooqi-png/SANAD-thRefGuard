# Security policy

SANAD is **local-first**: the engine binds to `127.0.0.1` only, requires a per-launch bearer token
on every request, enforces a strict Host allow-list (anti DNS-rebinding), scopes CORS to the
add-in's own origin, and makes no outbound connections. Your library and documents never leave your
machine.

## Reporting a vulnerability

Please report security issues **privately**, not in a public issue:

- Use GitHub's **[Report a vulnerability](https://github.com/sajidmahmoodfarooqi-png/SANAD-thRefGuard/security/advisories/new)**
  (Security → Advisories), or
- email the maintainer via the address on the GitHub profile
  [@sajidmahmoodfarooqi-png](https://github.com/sajidmahmoodfarooqi-png).

Please include the version, your OS, and steps to reproduce. We'll acknowledge as quickly as we can,
keep you updated, and credit you in the release notes unless you'd rather stay anonymous.

## Scope

Most relevant: anything that could let a web page, another local process, or a document cause the
Core to read or write outside its own data, reach the network, or bypass the token / Host / CORS
checks — or anything that could make SANAD write outside its own citation/bibliography fields.

## Supported versions

SANAD is pre-1.0; fixes land on the latest release. Please test against the newest version before
reporting.
