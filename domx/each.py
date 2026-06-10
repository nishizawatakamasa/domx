from collections.abc import Generator
from typing import Any

from camoufox.sync_api import Camoufox
from patchright.sync_api import (
    Page as PatchrightPage,
    sync_playwright,
)
from playwright.sync_api import Page as PlaywrightPage

_SPAN = 'span'


def _split_options(options: dict[str, Any] | None) -> tuple[int | None, dict[str, Any]]:
    opts = dict(options or {})
    span = opts.pop(_SPAN, None)
    if span is not None and span < 1:
        raise ValueError('span は 1 以上で指定してください')
    return span, opts


class Each[T]:
    def __init__(self, items: list[T]) -> None:
        self._items = items

    @staticmethod
    def _chunked_by_span(items: list[T], span: int | None) -> list[list[T]]:
        if span is None:
            return [items]
        return [items[i:i + span] for i in range(0, len(items), span)]

    def _iter_patchright_item_pages(
        self,
        *,
        browser: dict[str, Any] | None,
        context: dict[str, Any] | None,
        page: dict[str, Any] | None,
    ) -> Generator[tuple[T, PatchrightPage], None, None]:
        browser_span, browser_kw = _split_options(browser)
        context_span, context_kw = _split_options(context)
        page_span, _ = _split_options(page)
        for browser_batch in self._chunked_by_span(self._items, browser_span):
            with sync_playwright() as pw:
                with pw.chromium.launch(**browser_kw) as browser_instance:
                    for context_batch in self._chunked_by_span(browser_batch, context_span):
                        with browser_instance.new_context(**context_kw) as ctx:
                            for page_batch in self._chunked_by_span(context_batch, page_span):
                                page_instance = ctx.new_page()
                                try:
                                    for item in page_batch:
                                        yield item, page_instance
                                finally:
                                    page_instance.close()

    def _iter_camoufox_item_pages(
        self,
        *,
        browser: dict[str, Any] | None,
        context: dict[str, Any] | None,
        page: dict[str, Any] | None,
    ) -> Generator[tuple[T, PlaywrightPage], None, None]:
        browser_span, browser_kw = _split_options(browser)
        context_span, context_kw = _split_options(context)
        page_span, _ = _split_options(page)
        for browser_batch in self._chunked_by_span(self._items, browser_span):
            with Camoufox(**browser_kw) as browser_instance:
                for context_batch in self._chunked_by_span(browser_batch, context_span):
                    with browser_instance.new_context(**context_kw) as ctx:
                        for page_batch in self._chunked_by_span(context_batch, page_span):
                            page_instance = ctx.new_page()
                            try:
                                for item in page_batch:
                                    yield item, page_instance
                            finally:
                                page_instance.close()

    def patchright(
        self,
        *,
        browser: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        page: dict[str, Any] | None = None,
    ) -> Generator[tuple[T, PatchrightPage], None, None]:
        gen = self._iter_patchright_item_pages(browser=browser, context=context, page=page)
        try:
            yield from gen
        finally:
            gen.close()

    def camoufox(
        self,
        *,
        browser: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        page: dict[str, Any] | None = None,
    ) -> Generator[tuple[T, PlaywrightPage], None, None]:
        gen = self._iter_camoufox_item_pages(browser=browser, context=context, page=page)
        try:
            yield from gen
        finally:
            gen.close()


def each[T](items: list[T]) -> Each[T]:
    return Each(items)
