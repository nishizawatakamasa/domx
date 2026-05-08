from __future__ import annotations

import html
from collections.abc import Iterator
import random
import re
import time
import unicodedata as ud
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urljoin

from loguru import logger
from patchright.sync_api import Frame as PatchFrame, Page as PatchPage, ElementHandle as PatchElementHandle, Response as PatchResponse
from playwright.sync_api import Frame as PlayFrame, Page as PlayPage, ElementHandle as PlayElementHandle, Response as PlayResponse
from selectolax.lexbor import LexborHTMLParser, LexborNode


Page = PatchPage | PlayPage
ElementHandle = PatchElementHandle | PlayElementHandle
Response = PatchResponse | PlayResponse
Frame = PatchFrame | PlayFrame

_DOMX_META_URL = 'domx:url'
_DOMX_META_SAVED_AT = 'domx:saved_at'

_UNUSABLE_INLINE_URL = re.compile(r'(?i)^(?:#|javascript:|mailto:|tel:|data:)')

_ELEMENT_NEXT = 'nextElementSibling'
_ELEMENT_PREV = 'previousElementSibling'
_ELEMENT_PARENT = 'parentElement'

_NODE_NEXT = 'next'
_NODE_PREV = 'prev'
_NODE_PARENT = 'parent'


def wrap_page(page: Page) -> WrappedPage:
    return WrappedPage(page)


class _PageScoped:
    _page: Page

    def wrap_element(self, elem: ElementHandle | None) -> WrappedElement:
        return WrappedElement(self._page, elem)

    def wrap_element_group(self, elems: list[WrappedElement]) -> WrappedElementGroup:
        return WrappedElementGroup(self._page, elems)

    def wrap_frame(self, frame: Frame | None) -> WrappedFrame:
        return WrappedFrame(self._page, frame)


def wrap_parser(parser: LexborHTMLParser) -> WrappedParser:
    return WrappedParser(parser)


def wrap_node(node: LexborNode | None) -> WrappedNode:
    return WrappedNode(node)


def wrap_node_group(nodes: list[WrappedNode]) -> WrappedNodeGroup:
    return WrappedNodeGroup(nodes)


class WrappedFrame(_PageScoped):
    def __init__(self, page: Page, frame: Frame | None) -> None:
        self._page = page
        self._frame = frame

    def __bool__(self) -> bool:
        return self._frame is not None

    @property
    def raw(self) -> Frame | None:
        return self._frame

    def s(self, selector: str) -> WrappedElement:
        if self._frame is None:
            return self.wrap_element(None)
        elem = self._frame.query_selector(selector)
        return self.wrap_element(elem)

    def ss(self, selector: str) -> WrappedElementGroup:
        if self._frame is None:
            return self.wrap_element_group([])
        elems = self._frame.query_selector_all(selector)
        return self.wrap_element_group([self.wrap_element(e) for e in elems])

    def wait(self, selector: str, state: str = 'attached', timeout: int = 15000) -> WrappedElement:
        if self._frame is None:
            return self.wrap_element(None)
        try:
            elem = self._frame.wait_for_selector(selector, state=state, timeout=timeout)
            return self.wrap_element(elem)
        except Exception as e:
            logger.warning(
                f'[wait] {type(e).__name__}: {e} | selector={selector!r} | url={self._page.url}'
            )
            return self.wrap_element(None)


class WrappedPage(_PageScoped):
    def __init__(self, page: Page) -> None:
        self._page = page

    @property
    def raw(self) -> Page:
        return self._page

    def s(self, selector: str) -> WrappedElement:
        elem = self._page.query_selector(selector)
        return self.wrap_element(elem)

    def ss(self, selector: str) -> WrappedElementGroup:
        elems = self._page.query_selector_all(selector)
        return self.wrap_element_group([self.wrap_element(e) for e in elems])

    def frame(self, iframe_selector: str) -> WrappedFrame:
        iframe_elem = self._page.query_selector(iframe_selector)
        if iframe_elem is None:
            return self.wrap_frame(None)
        try:
            fr = iframe_elem.content_frame()
            return self.wrap_frame(fr)
        except Exception as e:
            logger.error(f'[frame] {type(e).__name__}: {e} | iframe_selector={iframe_selector!r}')
            return self.wrap_frame(None)

    def goto(
        self,
        url: str | None,
        try_cnt: int = 3,
        wait_range: tuple[float, float] = (3, 5),
        sleep_after: tuple[float, float] | None = (1, 2),
    ) -> Response | None:
        if not url:
            return None
        for i in range(try_cnt):
            try:
                response = self._page.goto(url)
                if response is not None:
                    if sleep_after is not None:
                        time.sleep(random.uniform(*sleep_after))
                    return response
                reason = 'response is None'
            except Exception as e:
                reason = f'{type(e).__name__}: {e}'
            logger.warning(f'[goto] {url} ({i+1}/{try_cnt}) {reason}')
            if i + 1 < try_cnt:
                time.sleep(random.uniform(*wait_range))
        logger.error(f'[goto] giving up: {url}')
        return None

    def wait(self, selector: str, state: str = 'attached', timeout: int = 15000) -> WrappedElement:
        try:
            elem = self._page.wait_for_selector(selector, state=state, timeout=timeout)
            return self.wrap_element(elem)
        except Exception as e:
            logger.warning(f'[wait] {type(e).__name__}: {e} | selector={selector!r} | url={self._page.url}')
            return self.wrap_element(None)

    def html(self, with_url: bool = False, with_saved_at: bool = False) -> str:
        content = self._page.content()
        metas: list[str] = []
        if with_url:
            metas.append(
                f'<meta name="{_DOMX_META_URL}" content="{html.escape(self._page.url)}">'
            )
        if with_saved_at:
            ts = datetime.now(timezone.utc).isoformat()
            metas.append(f'<meta name="{_DOMX_META_SAVED_AT}" content="{ts}">')
        return ''.join(metas) + content


class WrappedElement(_PageScoped):
    def __init__(self, page: Page, elem: ElementHandle | None) -> None:
        self._page = page
        self._elem = elem

    def __bool__(self) -> bool:
        return self._elem is not None

    @property
    def raw(self) -> ElementHandle | None:
        return self._elem

    def s(self, selector: str) -> WrappedElement:
        elem = self._elem.query_selector(selector) if self._elem else None
        return self.wrap_element(elem)

    def ss(self, selector: str) -> WrappedElementGroup:
        elems = self._elem.query_selector_all(selector) if self._elem else []
        return self.wrap_element_group([self.wrap_element(e) for e in elems])

    def frame(self, iframe_selector: str | None = None) -> WrappedFrame:
        if self._elem is None:
            return self.wrap_frame(None)
        try:
            if iframe_selector is None:
                fr = self._elem.content_frame()
            else:
                iframe_elem = self._elem.query_selector(iframe_selector)
                if iframe_elem is None:
                    return self.wrap_frame(None)
                fr = iframe_elem.content_frame()
            return self.wrap_frame(fr)
        except Exception as e:
            logger.error(
                f'[frame] {type(e).__name__}: {e} | iframe_selector={iframe_selector!r}'
            )
            return self.wrap_frame(None)

    def _walk_relative(self, selector: str, axis: str, label: str) -> WrappedElement:
        if self._elem is None:
            return self.wrap_element(None)
        try:
            elem = self._elem.evaluate_handle(
                '''(el, args) => {
                    const [sel, axis] = args;
                    let cur = el[axis];
                    while (cur) {
                        if (cur.matches(sel)) return cur;
                        cur = cur[axis];
                    }
                    return null;
                }''',
                [selector, axis],
            ).as_element()
            return self.wrap_element(elem)
        except Exception as e:
            logger.error(f'[{label}] {self._elem} {type(e).__name__}: {e}')
            return self.wrap_element(None)

    def next(self, selector: str) -> WrappedElement:
        return self._walk_relative(selector, _ELEMENT_NEXT, 'next')

    def prev(self, selector: str) -> WrappedElement:
        return self._walk_relative(selector, _ELEMENT_PREV, 'prev')

    def parent(self, selector: str) -> WrappedElement:
        return self._walk_relative(selector, _ELEMENT_PARENT, 'parent')

    @property
    def text(self) -> str | None:
        if self._elem is None:
            return None
        return text if (text := self._elem.text_content()) else None

    def attr(self, attr_name: str) -> str | None:
        if self._elem is None:
            return None
        return attr if (attr := self._elem.get_attribute(attr_name)) else None

    def _resolved_url_from_attr(self, attr_name: str) -> str | None:
        if self._elem is None:
            return None
        if not (attr := self._elem.get_attribute(attr_name)):
            return None
        if not (a := attr.strip()):
            return None
        if _UNUSABLE_INLINE_URL.search(a):
            return None
        return urljoin(self._page.url, a)

    @property
    def url(self) -> str | None:
        return self._resolved_url_from_attr('href')

    @property
    def src(self) -> str | None:
        return self._resolved_url_from_attr('src')

    def scroll_into_view(self) -> None:
        if self._elem is None:
            logger.warning('[scroll_into_view] element is None')
            return
        try:
            self._elem.evaluate(
                '''(el) => el.scrollIntoView({ behavior: "smooth", block: "center", inline: "nearest" });'''
            )
            self._elem.wait_for_element_state('stable')
        except Exception as e:
            logger.warning(f'[scroll_into_view] {type(e).__name__}: {e} | url={self._page.url!r}')

    @staticmethod
    def _isolate_visibility_css(scope: str, attr: str) -> str:
        return (
            f'{scope} * {{\n'
            f'  visibility: hidden !important;\n'
            f'}}\n'
            f'[{attr}],\n'
            f'[{attr}] * {{\n'
            f'  visibility: visible !important;\n'
            f'}}\n'
        )

    def _isolate_apply(self, attr: str, css: str, style_id: str) -> None:
        self._elem.evaluate(
            '''(el, args) => {
                const [attr, css, styleId] = args;
                el.setAttribute(attr, '');
                const s = document.createElement('style');
                s.id = styleId;
                s.textContent = css;
                (document.head || document.documentElement).appendChild(s);
            }''',
            [attr, css, style_id],
        )

    def _isolate_remove(self, attr: str, style_id: str) -> None:
        try:
            self._elem.evaluate(
                '''(el, args) => {
                    const [attr, styleId] = args;
                    el.removeAttribute(attr);
                    const node = document.getElementById(styleId);
                    if (node) node.remove();
                }''',
                [attr, style_id],
            )
        except Exception as e:
            logger.warning(
                f'[screenshot isolate cleanup] {type(e).__name__}: {e} | url={self._page.url!r}'
            )

    def screenshot(
        self,
        path: Path,
        image_type: Literal['png', 'jpeg'] = 'png',
        *,
        isolate: bool = False,
        isolate_scope: str = 'body',
        isolate_attr: str = 'data-domx-screenshot-root',
        isolate_style_id: str = 'domx-screenshot-isolate',
    ) -> bool:
        if self._elem is None:
            logger.warning('[screenshot] element is None')
            return False
        if isolate:
            style_id = f'{isolate_style_id}-{time.time_ns()}'
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if isolate:
                css = self._isolate_visibility_css(isolate_scope, isolate_attr)
                self._isolate_apply(isolate_attr, css, style_id)
            self._elem.screenshot(
                path=path,
                type=image_type,
                animations='disabled',
            )
            return True
        except Exception as e:
            logger.warning(f'[screenshot] {type(e).__name__}: {e} | url={self._page.url!r}')
            return False
        finally:
            if isolate:
                self._isolate_remove(isolate_attr, style_id)


class WrappedElementGroup(_PageScoped):
    def __init__(self, page: Page, elems: list[WrappedElement]) -> None:
        self._page = page
        self._elems = elems

    def __iter__(self) -> Iterator[WrappedElement]:
        return iter(self._elems)

    def __len__(self) -> int:
        return len(self._elems)

    def __getitem__(self, key: int | slice) -> WrappedElement | WrappedElementGroup:
        if isinstance(key, slice):
            return WrappedElementGroup(self._page, self._elems[key])
        return self._elems[key]

    def __add__(self, other: WrappedElementGroup) -> WrappedElementGroup:
        if not isinstance(other, WrappedElementGroup):
            raise TypeError(
                'WrappedElementGroup 同士のみ + で結合できます '
                f'（右辺は {type(other).__name__}）'
            )
        if self._page is not other._page:
            raise ValueError('異なる Page に紐づいた WrappedElementGroup は結合できません')
        return WrappedElementGroup(self._page, self._elems + other._elems)

    @property
    def raw(self) -> list[WrappedElement]:
        return self._elems

    @property
    def re(self) -> ElementGrep:
        pairs: list[tuple[str, WrappedElement]] = []
        for e in self._elems:
            if (t := e.text):
                pairs.append((ud.normalize('NFKC', t), e))
        return ElementGrep(self._page, pairs)

    @property
    def urls(self) -> list[str]:
        return [u for e in self._elems if (u := e.url)]


class ElementGrep(_PageScoped):
    def __init__(self, page: Page, pairs: list[tuple[str, WrappedElement]]) -> None:
        self._page = page
        self._pairs = pairs

    def s(self, pattern: str) -> WrappedElement:
        try:
            prog = re.compile(pattern)
            for text, e in self._pairs:
                if prog.search(text):
                    return e
        except Exception as e:
            logger.warning(f'[grep] {type(e).__name__}: {e} | pattern={pattern!r}')
        return self.wrap_element(None)

    def ss(self, pattern: str) -> WrappedElementGroup:
        try:
            prog = re.compile(pattern)
            filtered = [e for text, e in self._pairs if prog.search(text)]
            return self.wrap_element_group(filtered)
        except Exception as e:
            logger.warning(f'[grep] {type(e).__name__}: {e} | pattern={pattern!r}')
            return self.wrap_element_group([])


class WrappedParser:
    def __init__(self, parser: LexborHTMLParser) -> None:
        self._parser = parser

    @property
    def raw(self) -> LexborHTMLParser:
        return self._parser

    def s(self, selector: str) -> WrappedNode:
        node = self._parser.css_first(selector)
        return wrap_node(node)

    def ss(self, selector: str) -> WrappedNodeGroup:
        nodes = self._parser.css(selector)
        return wrap_node_group([wrap_node(n) for n in nodes])

    @property
    def url(self) -> str | None:
        node = self._parser.css_first(f'meta[name="{_DOMX_META_URL}"]')
        if node is None:
            return None
        return node.attributes.get('content') or None

    @property
    def saved_at(self) -> str | None:
        node = self._parser.css_first(f'meta[name="{_DOMX_META_SAVED_AT}"]')
        if node is None:
            return None
        return node.attributes.get('content') or None


class WrappedNode:
    def __init__(self, node: LexborNode | None) -> None:
        self._node = node

    def __bool__(self) -> bool:
        return self._node is not None

    @property
    def raw(self) -> LexborNode | None:
        return self._node

    def s(self, selector: str) -> WrappedNode:
        node = self._node.css_first(selector) if self._node else None
        return wrap_node(node)

    def ss(self, selector: str) -> WrappedNodeGroup:
        nodes = self._node.css(selector) if self._node else []
        return wrap_node_group([wrap_node(n) for n in nodes])

    def _walk_relative(self, selector: str, axis: str) -> WrappedNode:
        if self._node is None:
            return wrap_node(None)
        cur = getattr(self._node, axis)
        while cur is not None:
            if cur.is_element_node and cur.css_matches(selector):
                return wrap_node(cur)
            cur = getattr(cur, axis)
        return wrap_node(None)

    def next(self, selector: str) -> WrappedNode:
        return self._walk_relative(selector, _NODE_NEXT)

    def prev(self, selector: str) -> WrappedNode:
        return self._walk_relative(selector, _NODE_PREV)

    def parent(self, selector: str) -> WrappedNode:
        return self._walk_relative(selector, _NODE_PARENT)

    @property
    def text(self) -> str | None:
        if self._node is None:
            return None
        return text if (text := self._node.text()) else None

    def attr(self, attr_name: str) -> str | None:
        if self._node is None:
            return None
        return attr if (attr := self._node.attributes.get(attr_name)) else None


class WrappedNodeGroup:
    def __init__(self, nodes: list[WrappedNode]) -> None:
        self._nodes = nodes

    def __iter__(self) -> Iterator[WrappedNode]:
        return iter(self._nodes)

    def __len__(self) -> int:
        return len(self._nodes)

    def __getitem__(self, key: int | slice) -> WrappedNode | WrappedNodeGroup:
        if isinstance(key, slice):
            return WrappedNodeGroup(self._nodes[key])
        return self._nodes[key]

    def __add__(self, other: WrappedNodeGroup) -> WrappedNodeGroup:
        if not isinstance(other, WrappedNodeGroup):
            raise TypeError(
                'WrappedNodeGroup 同士のみ + で結合できます '
                f'（右辺は {type(other).__name__}）'
            )
        return WrappedNodeGroup(self._nodes + other._nodes)

    @property
    def raw(self) -> list[WrappedNode]:
        return self._nodes

    @property
    def re(self) -> NodeGrep:
        pairs: list[tuple[str, WrappedNode]] = []
        for n in self._nodes:
            if (t := n.text):
                pairs.append((ud.normalize('NFKC', t), n))
        return NodeGrep(pairs)


class NodeGrep:
    def __init__(self, pairs: list[tuple[str, WrappedNode]]) -> None:
        self._pairs = pairs

    def s(self, pattern: str) -> WrappedNode:
        try:
            prog = re.compile(pattern)
            for text, n in self._pairs:
                if prog.search(text):
                    return n
        except Exception as e:
            logger.warning(f'[grep] {type(e).__name__}: {e} | pattern={pattern!r}')
        return wrap_node(None)

    def ss(self, pattern: str) -> WrappedNodeGroup:
        try:
            prog = re.compile(pattern)
            filtered = [n for text, n in self._pairs if prog.search(text)]
            return wrap_node_group(filtered)
        except Exception as e:
            logger.warning(f'[grep] {type(e).__name__}: {e} | pattern={pattern!r}')
            return wrap_node_group([])
