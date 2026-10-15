# ADR 003: Block Internal Network Crawling by Default

## Context

Users provide URLs for crawling. Crawlers can become SSRF vectors if they fetch localhost, private networks, or cloud metadata endpoints.

## Decision

Validate crawl URLs before fetching. Only HTTP and HTTPS are allowed. Localhost, loopback, private networks, link-local ranges, multicast, unspecified addresses, and cloud metadata IPs are blocked unless local crawling is explicitly enabled for development.

## Alternatives

- Trust user-provided URLs.
- Rely only on outbound firewall rules.

## Tradeoffs

Strict URL validation may block some legitimate local development workflows, but it is the safer default for a multi-tenant crawler. Local development can opt in through configuration.
