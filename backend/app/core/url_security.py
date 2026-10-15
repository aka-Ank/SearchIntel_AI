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


BLOCKED_IPS = {ipaddress.ip_address("169.254.169.254")}


def normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if not parsed.scheme or not parsed.netloc:
        raise UnsafeUrlError("URL must include scheme and host")

    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower()
    port = f":{parsed.port}" if parsed.port else ""
    netloc_host = f"[{hostname}]" if ":" in hostname else hostname
    path = parsed.path or "/"
    normalized = parsed._replace(scheme=scheme, netloc=f"{netloc_host}{port}", path=path)
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
        if host.lower().rstrip(".") == "metadata.google.internal":
            raise UnsafeUrlError("Local or metadata hostnames are not allowed")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            if _is_metadata_ip(address):
                raise UnsafeUrlError("Cloud metadata addresses are not allowed")
        return normalized

    resolve_crawl_addresses(host, policy)
    return normalized


def resolve_crawl_addresses(
    host: str, policy: UrlSafetyPolicy | None = None
) -> tuple[ipaddress.IPv4Address | ipaddress.IPv6Address, ...]:
    """Resolve a crawl host once and return only addresses permitted by its safety policy."""
    policy = policy or UrlSafetyPolicy()
    hostname = host.lower().rstrip(".")
    if hostname == "metadata.google.internal":
        raise UnsafeUrlError("Local or metadata hostnames are not allowed")

    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        try:
            address_info = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise UnsafeUrlError("URL hostname could not be resolved safely") from exc
        addresses = tuple(dict.fromkeys(ipaddress.ip_address(info[4][0]) for info in address_info))
        if not addresses:
            raise UnsafeUrlError("URL hostname did not resolve to an address") from None
    else:
        addresses = (ip,)

    for address in addresses:
        if _is_metadata_ip(address):
            raise UnsafeUrlError("Cloud metadata addresses are not allowed")
        if not policy.allow_local_urls:
            _validate_ip_address(address)
    return addresses


def _validate_ip_address(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
    if (
        not ip.is_global
        or ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_unspecified
        or ip.is_reserved
    ):
        raise UnsafeUrlError("Internal network addresses are not allowed")


def _is_metadata_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return ip in BLOCKED_IPS or (
        isinstance(ip, ipaddress.IPv6Address)
        and ip.ipv4_mapped is not None
        and ip.ipv4_mapped in BLOCKED_IPS
    )
