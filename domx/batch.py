from collections.abc import Generator, Iterator
from contextlib import contextmanager

from camoufox.sync_api import Camoufox
from patchright.sync_api import (
    Page as PatchrightPage,
    sync_playwright,
)
from playwright.sync_api import Page as PlaywrightPage


class Batch[T]:
    def __init__(self, items: list[T]) -> None:
        self._items = items

    @staticmethod
    def _chunked_by_every(items: list[T], every: int | None) -> list[list[T]]:
        if every is None:
            return [items]
        if every < 1:
            raise ValueError('every は 1 以上で指定してください')
        return [items[i:i + every] for i in range(0, len(items), every)]

    def _iter_patchright_item_pages(
        self,
        *,
        browser_recreate_every: int | None,
        context_recreate_every: int | None,
        browser_kwargs: dict | None,
        context_kwargs: dict | None,
    ) -> Generator[tuple[T, PatchrightPage], None, None]:
        browser_kw = browser_kwargs or {}
        context_kw = context_kwargs or {}
        for browser_batch in self._chunked_by_every(self._items, browser_recreate_every):
            with sync_playwright() as pw:
                with pw.chromium.launch(**browser_kw) as browser:
                    for context_batch in self._chunked_by_every(browser_batch, context_recreate_every):
                        with browser.new_context(**context_kw) as context:
                            for item in context_batch:
                                page = context.new_page()
                                try:
                                    yield item, page
                                finally:
                                    page.close()

    def _iter_camoufox_item_pages(
        self,
        *,
        browser_recreate_every: int | None,
        context_recreate_every: int | None,
        browser_kwargs: dict | None,
        context_kwargs: dict | None,
    ) -> Generator[tuple[T, PlaywrightPage], None, None]:
        browser_kw = browser_kwargs or {}
        context_kw = context_kwargs or {}
        for browser_batch in self._chunked_by_every(self._items, browser_recreate_every):
            with Camoufox(**browser_kw) as browser:
                for context_batch in self._chunked_by_every(browser_batch, context_recreate_every):
                    with browser.new_context(**context_kw) as context:
                        for item in context_batch:
                            page = context.new_page()
                            try:
                                yield item, page
                            finally:
                                page.close()

    @contextmanager
    def attach_patchright_page(
        self,
        *,
        browser_recreate_every: int | None = None,
        context_recreate_every: int | None = None,
        browser_kwargs: dict | None = None,
        context_kwargs: dict | None = None,
    ) -> Iterator[Iterator[tuple[T, PatchrightPage]]]:
        iterator = self._iter_patchright_item_pages(
            browser_recreate_every=browser_recreate_every,
            context_recreate_every=context_recreate_every,
            browser_kwargs=browser_kwargs,
            context_kwargs=context_kwargs,
        )
        try:
            yield iterator
        finally:
            iterator.close()

    @contextmanager
    def attach_camoufox_page(
        self,
        *,
        browser_recreate_every: int | None = None,
        context_recreate_every: int | None = None,
        browser_kwargs: dict | None = None,
        context_kwargs: dict | None = None,
    ) -> Iterator[Iterator[tuple[T, PlaywrightPage]]]:
        iterator = self._iter_camoufox_item_pages(
            browser_recreate_every=browser_recreate_every,
            context_recreate_every=context_recreate_every,
            browser_kwargs=browser_kwargs,
            context_kwargs=context_kwargs,
        )
        try:
            yield iterator
        finally:
            iterator.close()


def batch[T](items: list[T]) -> Batch[T]:
    return Batch(items)
