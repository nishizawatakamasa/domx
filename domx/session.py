from types import TracebackType
from typing import Any, Protocol, Self

from camoufox.sync_api import Camoufox
from patchright.sync_api import (
    Browser as PatchrightBrowser,
    BrowserContext,
    Page as PatchrightPage,
    Playwright,
    sync_playwright,
)
from playwright.sync_api import Browser as PlaywrightBrowser
from playwright.sync_api import Page as PlaywrightPage

Bands = tuple[int, int, int]


def _check_span(span: int | None, name: str) -> None:
    if span is not None and span < 1:
        raise ValueError(f'{name} は 1 以上で指定してください')


def _bands_for(
    i: int,
    *,
    browser_span: int | None,
    context_span: int | None,
    page_span: int | None,
) -> Bands:
    if browser_span:
        pos_in_browser = (i - 1) % browser_span
        browser_band = (i - 1) // browser_span
    else:
        pos_in_browser = i - 1
        browser_band = 0

    if context_span:
        context_band = pos_in_browser // context_span
        pos_in_context = pos_in_browser % context_span
    else:
        context_band = 0
        pos_in_context = pos_in_browser

    if page_span:
        page_band = pos_in_context // page_span
    else:
        page_band = 0

    return browser_band, context_band, page_band


class _Backend(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def launch(self, **kw: Any) -> PatchrightBrowser | PlaywrightBrowser: ...
    def close_browser(self) -> None: ...


class _PatchrightBackend:
    def __init__(self) -> None:
        self._pw: Playwright | None = None
        self._browser: PatchrightBrowser | None = None

    def start(self) -> None:
        self._pw = sync_playwright().start()

    def stop(self) -> None:
        self.close_browser()
        if self._pw:
            self._pw.stop()
            self._pw = None

    def launch(self, **kw: Any) -> PatchrightBrowser:
        self.close_browser()
        if not self._pw:
            raise RuntimeError('patchright driver が起動していません')
        self._browser = self._pw.chromium.launch(**kw)
        return self._browser

    def close_browser(self) -> None:
        if self._browser:
            self._browser.close()
            self._browser = None


class _CamoufoxBackend:
    def __init__(self) -> None:
        self._fox: Camoufox | None = None
        self._browser: PlaywrightBrowser | None = None

    def start(self) -> None:
        pass

    def stop(self) -> None:
        self.close_browser()

    def launch(self, **kw: Any) -> PlaywrightBrowser:
        self.close_browser()
        self._fox = Camoufox(**kw)
        self._browser = self._fox.__enter__()
        return self._browser

    def close_browser(self) -> None:
        if self._fox:
            self._fox.__exit__(None, None, None)
            self._fox = None
            self._browser = None


class Session:
    def __init__(
        self,
        backend: _Backend,
        *,
        browser: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        browser_span: int | None = None,
        context_span: int | None = None,
        page_span: int | None = None,
    ) -> None:
        _check_span(browser_span, 'browser_span')
        _check_span(context_span, 'context_span')
        _check_span(page_span, 'page_span')
        self._backend = backend
        self._browser_kw = dict(browser or {})
        self._browser_span = browser_span
        self._context_kw = dict(context or {})
        self._context_span = context_span
        self._page_span = page_span
        self._browser: PatchrightBrowser | PlaywrightBrowser | None = None
        self._ctx: BrowserContext | None = None
        self._page: PatchrightPage | PlaywrightPage | None = None
        self._i = 0
        self._bands: Bands = (-1, -1, -1)
        self._active = False

    def __enter__(self) -> Self:
        self._backend.start()
        self._active = True
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._shutdown()

    def page(self) -> PatchrightPage | PlaywrightPage:
        if not self._active:
            raise RuntimeError('session は with で開いてください')
        self._i += 1
        bands = _bands_for(
            self._i,
            browser_span=self._browser_span,
            context_span=self._context_span,
            page_span=self._page_span,
        )
        if bands[0] != self._bands[0]:
            self._close_browser()
            self._browser = self._backend.launch(**self._browser_kw)
            self._open_context()
            self._open_page()
        elif bands[1] != self._bands[1]:
            self._close_context()
            self._open_context()
            self._open_page()
        elif bands[2] != self._bands[2]:
            self._close_page()
            self._open_page()
        self._bands = bands
        assert self._page is not None
        return self._page

    def _open_context(self) -> None:
        if not self._browser:
            raise RuntimeError('browser が起動していません')
        self._ctx = self._browser.new_context(**self._context_kw)

    def _open_page(self) -> None:
        if not self._ctx:
            raise RuntimeError('context が起動していません')
        self._page = self._ctx.new_page()

    def _close_page(self) -> None:
        if self._page:
            self._page.close()
            self._page = None

    def _close_context(self) -> None:
        self._close_page()
        if self._ctx:
            self._ctx.close()
            self._ctx = None

    def _close_browser(self) -> None:
        self._close_context()
        self._backend.close_browser()
        self._browser = None

    def _shutdown(self) -> None:
        if not self._active:
            return
        self._close_browser()
        self._backend.stop()
        self._active = False
        self._bands = (-1, -1, -1)
        self._i = 0


def right(
    *,
    browser: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
    browser_span: int | None = None,
    context_span: int | None = None,
    page_span: int | None = None,
) -> Session:
    return Session(
        _PatchrightBackend(),
        browser=browser,
        browser_span=browser_span,
        context=context,
        context_span=context_span,
        page_span=page_span,
    )


def fox(
    *,
    browser: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
    browser_span: int | None = None,
    context_span: int | None = None,
    page_span: int | None = None,
) -> Session:
    return Session(
        _CamoufoxBackend(),
        browser=browser,
        browser_span=browser_span,
        context=context,
        context_span=context_span,
        page_span=page_span,
    )
