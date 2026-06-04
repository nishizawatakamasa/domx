from __future__ import annotations

import random
import time

from curl_cffi import requests
from loguru import logger


def fetch_response(
    url: str | None,
    *,
    try_cnt: int = 3,
    wait_range: tuple[float, float] = (1, 3),
    sleep_after: tuple[float, float] | None = (0.5, 1),
    timeout: float = 30,
    impersonate: str = "chrome",
) -> requests.Response | None:
    if not url:
        return None
    for i in range(try_cnt):
        try:
            res = requests.get(url, impersonate=impersonate, timeout=timeout)
            if res is not None:
                if sleep_after is not None:
                    time.sleep(random.uniform(*sleep_after))
                return res
            reason = "response is None"
        except Exception as e:
            reason = f"{type(e).__name__}: {e}"
        logger.warning(f"[fetch_response] retry ({i+1}/{try_cnt}) {reason}: {url!r}")
        if i + 1 < try_cnt:
            time.sleep(random.uniform(*wait_range))
    logger.error(f"[fetch_response] retries exhausted ({try_cnt}): {url!r}")
    return None


def fetch_html(
    url: str | None,
    *,
    try_cnt: int = 3,
    wait_range: tuple[float, float] = (1, 3),
    sleep_after: tuple[float, float] | None = (0.5, 1),
    timeout: float = 30,
    impersonate: str = "chrome",
) -> str | None:
    if not (
        res := fetch_response(
            url,
            try_cnt=try_cnt,
            wait_range=wait_range,
            sleep_after=sleep_after,
            timeout=timeout,
            impersonate=impersonate,
        )
    ):
        return None
    return res.text


def fetch_bytes(
    url: str | None,
    *,
    try_cnt: int = 3,
    wait_range: tuple[float, float] = (1, 3),
    sleep_after: tuple[float, float] | None = (0.5, 1),
    timeout: float = 30,
    impersonate: str = "chrome",
) -> bytes | None:
    if not (
        res := fetch_response(
            url,
            try_cnt=try_cnt,
            wait_range=wait_range,
            sleep_after=sleep_after,
            timeout=timeout,
            impersonate=impersonate,
        )
    ):
        return None
    return res.content
