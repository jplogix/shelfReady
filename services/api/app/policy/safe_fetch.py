"""Bounded HTTP fetch for manufacturer pages and images. Not a general crawler."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import httpx

ALLOWED_HOSTS = frozenset({"www.seikowatches.com", "seikowatches.com"})
MAX_HTML_BYTES = 2 * 1024 * 1024
MAX_IMAGE_BYTES = 8 * 1024 * 1024
DEFAULT_TIMEOUT = 12.0
USER_AGENT = "ShelfReady/1.0 (catalog demonstration; manufacturer-source retrieval)"


class FetchError(ValueError):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(code)
        self.code = code
        self.detail = detail


def _host_allowed(host: str) -> bool:
    return host.lower().rstrip(".") in ALLOWED_HOSTS


def _is_public_ip(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    return not (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )


def assert_safe_url(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    if parsed.scheme not in {"https"}:
        raise FetchError("unsafe_scheme", parsed.scheme or "missing")
    host = parsed.hostname or ""
    if not _host_allowed(host):
        raise FetchError("host_not_allowed", host)
    if parsed.username or parsed.password:
        raise FetchError("credentials_in_url")
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise FetchError("dns_failed", str(exc)) from exc
    for info in infos:
        ip = info[4][0]
        if not _is_public_ip(ip):
            raise FetchError("private_destination", ip)
    return host, parsed.geturl()


def resolve_redirect(request_url: str, location: str | None) -> str:
    if not location:
        raise FetchError("empty_redirect")
    next_url = urljoin(request_url, location)
    assert_safe_url(next_url)
    return next_url


def fetch_bytes(
    url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    max_bytes: int = MAX_HTML_BYTES,
    allowed_types: frozenset[str] | None = None,
) -> tuple[bytes, str, str]:
    """Return (body, final_url, content_type). Validates hosts and private destinations."""
    current = url
    assert_safe_url(current)
    last_error: Exception | None = None
    for _attempt in range(3):
        try:
            with httpx.Client(
                timeout=timeout,
                follow_redirects=False,
                headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
            ) as client:
                for _hop in range(4):
                    assert_safe_url(current)
                    response = client.get(current)
                    if response.status_code in {301, 302, 303, 307, 308}:
                        current = resolve_redirect(current, response.headers.get("location"))
                        continue
                    if response.status_code >= 400:
                        raise FetchError("http_error", str(response.status_code))
                    ctype = (response.headers.get("content-type") or "").split(";")[0].strip().lower()
                    if allowed_types and ctype not in allowed_types:
                        raise FetchError("unsupported_content_type", ctype)
                    body = response.content
                    if len(body) > max_bytes:
                        raise FetchError("response_too_large", str(len(body)))
                    return body, str(response.url), ctype
                raise FetchError("too_many_redirects")
        except FetchError:
            raise
        except httpx.TimeoutException as exc:
            last_error = exc
            continue
        except httpx.HTTPError as exc:
            last_error = exc
            continue
    raise FetchError("timeout_or_network", str(last_error) if last_error else "")
