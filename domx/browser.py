from collections.abc import Iterator
from contextlib import contextmanager

from camoufox.sync_api import Camoufox
from patchright.sync_api import Page as PatchrightPage, sync_playwright
from playwright.sync_api import Page as PlaywrightPage

Page = PatchrightPage | PlaywrightPage


_VIEWPORT_FULL_HD: dict[str, int] = {'width': 1920, 'height': 1080}


@contextmanager
def patchright_page(*, large_viewport: bool = False) -> Iterator[Page]:
    with sync_playwright() as pw:
        with pw.chromium.launch(
            channel='chrome',
            headless=False,
        ) as browser:
            ctx_kw: dict = {}
            if large_viewport:
                ctx_kw['viewport'] = _VIEWPORT_FULL_HD
            with browser.new_context(**ctx_kw) as context:
                page = context.new_page()
                yield page


@contextmanager
def camoufox_page(*, large_viewport: bool = False) -> Iterator[Page]:
    with Camoufox(
        headless=False,
        humanize=True,
    ) as browser:
        if large_viewport:
            page = browser.new_page(viewport=_VIEWPORT_FULL_HD)
        else:
            page = browser.new_page()
        yield page
