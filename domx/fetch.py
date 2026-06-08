from __future__ import annotations

import random
import time
from typing import Any

from curl_cffi import requests
from loguru import logger

__all__ = ["WrappedResponse", "wrap_response", "fetch"]


class WrappedResponse:
    def __init__(self, res: requests.Response | None) -> None:
        self._res = res

    def __bool__(self) -> bool:
        return self._res is not None

    @property
    def raw(self) -> requests.Response | None:
        return self._res

    @property
    def ok(self) -> bool:
        return self._res is not None and self._res.ok

    @property
    def url(self) -> str | None:
        return None if self._res is None else self._res.url

    @property
    def status_code(self) -> int | None:
        return None if self._res is None else self._res.status_code

    @property
    def text(self) -> str | None:
        return None if self._res is None else self._res.text

    @property
    def content(self) -> bytes | None:
        return None if self._res is None else self._res.content

    def json(self) -> Any | None:
        if self._res is None:
            return None
        try:
            return self._res.json()
        except Exception as e:
            logger.error(f"[fetch] json {type(e).__name__}: {e} | url={self.url!r}")
            return None


def wrap_response(res: requests.Response | None) -> WrappedResponse:
    return WrappedResponse(res)


def fetch(
    url: str,
    *,
    impersonate: str = "chrome",
    timeout: float = 30,
    sleep_after: tuple[float, float] | None = (0.5, 1),
) -> WrappedResponse:
    try:
        res = requests.get(url, impersonate=impersonate, timeout=timeout)
        if sleep_after is not None:
            time.sleep(random.uniform(*sleep_after))
        return wrap_response(res)
    except Exception as e:
        logger.error(f"[fetch] {type(e).__name__}: {e} | url={url!r}")
        return wrap_response(None)
