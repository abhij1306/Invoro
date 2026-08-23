from __future__ import annotations

import asyncio
import ipaddress
from collections import OrderedDict, deque
from time import monotonic

from starlette.requests import Request


def client_identifier_from_request(
    request: Request,
    *,
    trusted_proxies: tuple[str, ...] = (),
) -> str:
    peer_host = request.client.host if request.client and request.client.host else ""
    forwarded_for = (
        request.headers.get("x-forwarded-for")
        if is_trusted_proxy(peer_host, trusted_proxies=trusted_proxies)
        else None
    )
    if forwarded_for:
        first = forwarded_for.split(",", maxsplit=1)[0].strip()
        if first:
            return first
    if peer_host:
        return peer_host
    return "unknown"


def is_trusted_proxy(proxy_ip: str, *, trusted_proxies: tuple[str, ...]) -> bool:
    candidate = str(proxy_ip or "").strip()
    if not candidate:
        return False
    try:
        address = ipaddress.ip_address(candidate)
    except ValueError:
        return candidate in {
            str(value).strip() for value in trusted_proxies if str(value).strip()
        }
    for raw_value in trusted_proxies:
        value = str(raw_value or "").strip()
        if not value:
            continue
        try:
            if address in ipaddress.ip_network(value, strict=False):
                return True
        except ValueError:
            if candidate == value:
                return True
    return False


async def consume_sliding_window_limit(
    buckets: OrderedDict[str, deque[float]],
    lock: asyncio.Lock,
    *,
    identifier: str,
    window_seconds: float,
    max_requests: int,
    max_clients: int,
) -> tuple[bool, int]:
    now = monotonic()
    async with lock:
        bucket = buckets.get(identifier)
        if bucket is None:
            bucket = deque()
            buckets[identifier] = bucket
        else:
            buckets.move_to_end(identifier)

        cutoff = now - float(window_seconds)
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= int(max_requests):
            retry_after = max(1, int(bucket[0] + float(window_seconds) - now))
            return False, retry_after

        bucket.append(now)
        while len(buckets) > int(max_clients):
            buckets.popitem(last=False)
        return True, 0
