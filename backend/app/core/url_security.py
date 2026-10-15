from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urldefrag, urlparse, urlunparse


class UnsafeUrlError(ValueError):
    """Raised when a URL is not safe for crawler access."""


@dataclass(frozen=True)
class UrlSafetyPolicy:
    allow_local_urls: bool = False
    allowed_schemes: tuple[str, ...] = ("http", "https")


BLOCKED_HOSTS = {"localhost", "metadata.google.internal"}
BLOCKED_IPS = {ipaddress.ip_address("169.254.169.254")}


def normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if not parsed.scheme or not parsed.netloc:
        raise UnsafeUrlError("URL must include scheme and host")

    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower()
    port = f":{parsed.port}" if parsed.port else ""
    path = parsed.path or "/"
    normalized = parsed._replace(scheme=scheme, netloc=f"{hostname}{port}", path=path)
    without_fragment, _fragment = urldefrag(urlunparse(normalized))
    return without_fragment


def validate_crawl_url(url: str, policy: UrlSafetyPolicy | None = None) -> str:
    policy = policy or UrlSafetyPolicy()
    normalized = normalize_url(url)
    parsed = urlparse(normalized)

    if parsed.scheme not in policy.allowed_schemes:
        raise UnsafeUrlError(f"URL scheme is not allowed: {parsed.scheme}")

    host = parsed.hostname
    if not host:
        raise UnsafeUrlError("URL host is required")

    if policy.allow_local_urls:
        return normalized

    _validate_hostname(host)
    return normalized


def _validate_hostname(host: str) -> None:
    hostname = host.lower().rstrip(".")
    if hostname in BLOCKED_HOSTS:
        raise UnsafeUrlError("Local or metadata hostnames are not allowed")

    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        _validate_resolved_addresses(hostname)
        return

    _validate_ip_address(ip)


def _validate_resolved_addresses(hostname: str) -> None:
    try:
        address_info = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise UnsafeUrlError("URL hostname could not be resolved safely") from exc

    for info in address_info:
        ip = ipaddress.ip_address(info[4][0])
        _validate_ip_address(ip)


def _validate_ip_address(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
    if ip in BLOCKED_IPS:
        raise UnsafeUrlError("Cloud metadata addresses are not allowed")

    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_unspecified
        or ip.is_reserved
    ):
        raise UnsafeUrlError("Internal network addresses are not allowed")
