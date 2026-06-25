from __future__ import annotations

import logging
from collections.abc import Iterator, Mapping, MutableMapping
from typing import Any, cast

from selectolax.lexbor import LexborHTMLParser, LexborNode, SelectolaxError

logger = logging.getLogger(__name__)


class HtmlText:
    def __init__(self, value: str = "", *, node: LexborNode | None = None) -> None:
        self._value = str(value)
        self._node = node

    @property
    def parent(self) -> HtmlNode | None:
        parent = self._node.parent if self._node is not None else None
        return HtmlNode(parent) if parent is not None else None

    @property
    def next_sibling(self) -> PageElement | None:
        node = self._node.next if self._node is not None else None
        return _wrap(node)

    @property
    def previous_sibling(self) -> PageElement | None:
        node = self._node.prev if self._node is not None else None
        return _wrap(node)

    def extract(self) -> HtmlText:
        if self._node is not None:
            value = str(self)
            self._node.decompose()
            self._value = value
            self._node = None
        return self

    def replace_with(self, value: object) -> HtmlText:
        if self._node is not None:
            self._node.replace_with(str(value))
        return self

    def __str__(self) -> str:
        if self._node is not None:
            return str(self._node.text() or "")
        return self._value


class HtmlComment(HtmlText):
    pass


PageElement = Any
NavigableString = HtmlText
Comment = HtmlComment


def _is_text(node: LexborNode) -> bool:
    return str(node.tag or "").lower() in {"-text", "#text"}


def _is_comment(node: LexborNode) -> bool:
    return str(node.tag or "").lower() in {"-comment", "#comment"}


def _wrap(node: LexborNode | None) -> PageElement | None:
    if node is None:
        return None
    if _is_comment(node):
        return HtmlComment(node=node)
    if _is_text(node):
        return HtmlText(node=node)
    return HtmlNode(node)


def _iter_direct(node: LexborNode) -> Iterator[PageElement]:
    current = node.child
    while current is not None:
        wrapped = _wrap(current)
        if wrapped is not None:
            yield wrapped
        current = current.next


def _direct_tag_nodes(node: LexborNode) -> Iterator[LexborNode]:
    current = node.child
    while current is not None:
        if not _is_text(current) and not _is_comment(current):
            yield current
        current = current.next


def _mutation_value(value: object) -> bytes | str | LexborNode:
    if isinstance(value, HtmlNode):
        return value.node
    if isinstance(value, HtmlText):
        return str(value)
    return str(value)


def _normalize_tags(name: object) -> set[str] | None:
    if name is True or name is None:
        return None
    if isinstance(name, str):
        return {name.lower()}
    if isinstance(name, (tuple, list, set, frozenset)):
        return {str(item).lower() for item in name}
    return {str(name).lower()}


class HtmlAttributes(MutableMapping[str, str]):
    """Mutable mapping proxy that writes attribute changes through to the DOM."""

    def __init__(self, node: LexborNode) -> None:
        self._node = node

    def __getitem__(self, key: str) -> str:
        return cast(str, self._node.attrs[key])

    def __setitem__(self, key: str, value: str) -> None:
        self._node.attrs[str(key)] = str(value)

    def __delitem__(self, key: str) -> None:
        del self._node.attrs[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._node.attributes)

    def __len__(self) -> int:
        return len(self._node.attributes)


class InvalidSelectorError(ValueError):
    """Raised when the underlying parser rejects CSS selector syntax."""


class HtmlNode:
    def __init__(self, node: LexborNode) -> None:
        self.node = node
        self._owner: object | None = None

    @property
    def name(self) -> str:
        return str(self.node.tag or "").lower()

    @property
    def tag(self) -> str:
        return self.name

    @property
    def attrs(self) -> MutableMapping[str, str]:
        return HtmlAttributes(self.node)

    @attrs.setter
    def attrs(self, value: Mapping[str, object]) -> None:
        current = list(self.node.attrs.keys())
        for key in current:
            del self.node.attrs[key]
        for key, item in value.items():
            self.node.attrs[str(key)] = str(item)

    @property
    def parent(self) -> HtmlNode | None:
        parent = self.node.parent
        return HtmlNode(parent) if parent is not None else None

    @property
    def children(self) -> Iterator[PageElement]:
        return _iter_direct(self.node)

    @property
    def contents(self) -> list[PageElement]:
        return list(self.children)

    @property
    def descendants(self) -> Iterator[PageElement]:
        for node in self.node.traverse(include_text=True):
            if node is self.node:
                continue
            wrapped = _wrap(node)
            if wrapped is not None:
                yield wrapped

    @property
    def next_sibling(self) -> PageElement | None:
        return _wrap(self.node.next)

    @property
    def previous_sibling(self) -> PageElement | None:
        return _wrap(self.node.prev)

    @property
    def next_siblings(self) -> Iterator[PageElement]:
        current = self.node.next
        while current is not None:
            wrapped = _wrap(current)
            if wrapped is not None:
                yield wrapped
            current = current.next

    @property
    def previous_siblings(self) -> Iterator[PageElement]:
        current = self.node.prev
        while current is not None:
            wrapped = _wrap(current)
            if wrapped is not None:
                yield wrapped
            current = current.prev

    @property
    def stripped_strings(self) -> Iterator[str]:
        for node in self.node.traverse(include_text=True):
            if not _is_text(node):
                continue
            value = " ".join(str(node.text() or "").split()).strip()
            if value:
                yield value

    @property
    def string(self) -> str | None:
        children = list(self.children)
        if len(children) == 1 and isinstance(children[0], HtmlText):
            return str(children[0])
        return None

    @property
    def text(self) -> str:
        return self.get_text()

    def get(self, name: str, default: Any = None) -> Any:
        return self.node.attributes.get(name, default)

    def has_attr(self, name: str) -> bool:
        return name in self.node.attributes

    def get_text(self, separator: str = "", strip: bool = False) -> str:
        return str(self.node.text(separator=separator, strip=strip) or "")

    def select(self, selector: str) -> list[HtmlNode]:
        if not selector:
            return []
        try:
            return [
                HtmlNode(node) for node in self.node.css(selector) if node != self.node
            ]
        except SelectolaxError:
            logger.debug("Invalid CSS selector %r", selector, exc_info=True)
            return []

    def select_one(self, selector: str) -> HtmlNode | None:
        if not selector:
            return None
        try:
            node = next(
                (item for item in self.node.css(selector) if item != self.node), None
            )
        except SelectolaxError:
            logger.debug("Invalid CSS selector %r", selector, exc_info=True)
            return None
        return HtmlNode(node) if node is not None else None

    def find_all(
        self,
        name: object = None,
        attrs: Mapping[str, object] | None = None,
        string: object = None,
        limit: int | None = None,
        recursive: bool = True,
        **kwargs: object,
    ) -> list[Any]:
        def string_matches(value: str) -> bool:
            if string is True:
                return True
            if callable(string):
                return bool(string(value))
            if hasattr(string, "search"):
                return bool(string.search(value))
            return value == string

        tags = _normalize_tags(name)
        wanted_attrs = {**(attrs or {}), **kwargs}
        has_tag_filters = name is not None or bool(wanted_attrs)
        if string is not None and not has_tag_filters:
            text_rows: list[HtmlText] = []
            items = self.descendants if recursive else self.children
            for item in items:
                if isinstance(item, HtmlText) and string_matches(str(item)):
                    text_rows.append(item)
                    if limit is not None and len(text_rows) >= limit:
                        break
            return text_rows

        node_rows: list[HtmlNode] = []
        raw_nodes = self.node.traverse() if recursive else _direct_tag_nodes(self.node)
        for raw in raw_nodes:
            if raw is self.node or _is_text(raw) or _is_comment(raw):
                continue
            candidate = HtmlNode(raw)
            if tags is not None and candidate.name not in tags:
                continue
            if not _attrs_match(candidate, wanted_attrs):
                continue
            if string is not None:
                candidate_string = candidate.string
                if candidate_string is None or not string_matches(candidate_string):
                    continue
            node_rows.append(candidate)
            if limit is not None and len(node_rows) >= limit:
                break
        return node_rows

    def find(
        self,
        name: object = None,
        attrs: Mapping[str, object] | None = None,
        **kwargs: object,
    ) -> Any | None:
        wanted_attrs = {**(attrs or {}), **kwargs}
        rows = self.find_all(name=name, attrs=wanted_attrs, limit=1)
        return rows[0] if rows else None

    def find_parent(
        self,
        name: object = None,
        attrs: Mapping[str, object] | None = None,
        **kwargs: object,
    ) -> HtmlNode | None:
        tags = _normalize_tags(name)
        wanted_attrs = {**(attrs or {}), **kwargs}
        current = self.parent
        while current is not None:
            if (tags is None or current.name in tags) and _attrs_match(
                current, wanted_attrs
            ):
                return current
            current = current.parent
        return None

    def find_next_sibling(
        self,
        name: object = None,
        attrs: Mapping[str, object] | None = None,
        **kwargs: object,
    ) -> HtmlNode | None:
        tags = _normalize_tags(name)
        wanted_attrs = {**(attrs or {}), **kwargs}
        current = self.node.next
        while current is not None:
            if not _is_text(current) and not _is_comment(current):
                candidate = HtmlNode(current)
                if (tags is None or candidate.name in tags) and _attrs_match(
                    candidate, wanted_attrs
                ):
                    return candidate
            current = current.next
        return None

    def find_previous_sibling(
        self,
        name: object = None,
        attrs: Mapping[str, object] | None = None,
        **kwargs: object,
    ) -> HtmlNode | None:
        tags = _normalize_tags(name)
        wanted_attrs = {**(attrs or {}), **kwargs}
        current = self.node.prev
        while current is not None:
            if not _is_text(current) and not _is_comment(current):
                candidate = HtmlNode(current)
                if (tags is None or candidate.name in tags) and _attrs_match(
                    candidate, wanted_attrs
                ):
                    return candidate
            current = current.prev
        return None

    def decompose(self) -> None:
        self.node.decompose()

    def extract(self) -> HtmlNode:
        detached = self.clone()
        self.node.decompose()
        return detached

    def unwrap(self) -> HtmlNode:
        self.node.unwrap()
        return self

    def clear(self) -> None:
        for child in list(self.children):
            child.extract() if isinstance(child, HtmlText) else child.decompose()

    def replace_with(self, value: object) -> HtmlNode:
        self.node.replace_with(_mutation_value(value))
        return self

    def insert_before(self, value: object) -> None:
        self.node.insert_before(_mutation_value(value))

    def insert_after(self, value: object) -> None:
        self.node.insert_after(_mutation_value(value))

    def append(self, value: object) -> None:
        template_inner_html: str | None = None
        if isinstance(value, HtmlNode) and value.name == "template":
            serialized = str(value)
            template_inner_html = serialized.partition(">")[2].rsplit("</template>", 1)[0]
        self.node.insert_child(_mutation_value(value))
        if template_inner_html is not None and self.node.last_child is not None:
            self.node.last_child.inner_html = template_inner_html

    def insert(self, index: int, value: object) -> None:
        children = list(self.children)
        if index <= 0 and children:
            children[0].insert_before(value)
            return
        if index < len(children):
            children[index].insert_before(value)
            return
        self.append(value)

    def extend(self, values: Iterator[object] | list[object]) -> None:
        for value in values:
            self.append(value)

    def __getattr__(self, name: str) -> HtmlNode | None:
        if name.startswith("_"):
            raise AttributeError(name)
        return self.find(name)

    def __getitem__(self, key: str) -> Any:
        return self.node.attrs[key]

    def __setitem__(self, key: str, value: object) -> None:
        self.node.attrs[key] = str(value)

    def __delitem__(self, key: str) -> None:
        del self.node.attrs[key]

    def matches(self, selector: str) -> bool:
        if not selector:
            return False
        root = self.node
        while root.parent is not None:
            root = root.parent
        try:
            return any(candidate == self.node for candidate in root.css(selector))
        except SelectolaxError:
            logger.debug("Invalid CSS selector %r", selector, exc_info=True)
            return False

    def clone(self) -> HtmlNode:
        document = HtmlDocument(str(self))
        clone = document.select_one(self.name)
        if clone is None:
            raise ValueError(f"Unable to clone tag {self.name!r}")
        clone._owner = document
        return clone

    def __deepcopy__(self, memo: dict[int, object]) -> HtmlNode:
        del memo
        return self.clone()

    def __eq__(self, other: object) -> bool:
        return isinstance(other, HtmlNode) and self.node == other.node

    def __hash__(self) -> int:
        return hash(self.node)

    def __str__(self) -> str:
        return str(self.node.html or "")


Tag = HtmlNode


def _attrs_match(node: HtmlNode, attrs: Mapping[str, object]) -> bool:
    for key, expected in attrs.items():
        normalized_key = "class" if str(key) == "class_" else str(key)
        actual = node.get(normalized_key)
        if callable(expected):
            if not expected(actual):
                return False
        elif hasattr(expected, "search"):
            if not expected.search(str(actual or "")):
                return False
        elif normalized_key == "class" and isinstance(expected, str):
            if expected not in str(actual or "").split():
                return False
        elif isinstance(expected, (tuple, list, set, frozenset)):
            if actual not in expected:
                return False
        elif expected is True:
            if not node.has_attr(normalized_key):
                return False
        elif expected is False:
            if node.has_attr(normalized_key):
                return False
        elif str(actual or "") != str(expected):
            return False
    return True


class HtmlDocument(HtmlNode):
    def __init__(self, html: str = "", parser: str | None = None) -> None:
        del parser
        self.parser = LexborHTMLParser(str(html or ""))
        root = self.parser.root
        if root is None:
            raise ValueError("HTML parser did not produce a root node")
        super().__init__(root)

    @classmethod
    def from_parser(cls, parser: LexborHTMLParser) -> HtmlDocument:
        instance = cls.__new__(cls)
        instance.parser = parser
        root = parser.root
        if root is None:
            raise ValueError("HTML parser did not produce a root node")
        HtmlNode.__init__(instance, root)
        return instance

    def new_string(self, value: object) -> HtmlText:
        return HtmlText(str(value))

    def new_tag(
        self,
        name: str,
        attrs: Mapping[str, object] | None = None,
        **kwargs: object,
    ) -> HtmlNode:
        normalized_name = str(name or "").strip().lower()
        wrappers = {
            "tbody": "table",
            "thead": "table",
            "tfoot": "table",
            "tr": "table><tbody",
            "td": "table><tbody><tr",
            "th": "table><tbody><tr",
            "option": "select",
        }
        wrapper = wrappers.get(normalized_name)
        if wrapper:
            opening = "".join(f"<{part}>" for part in wrapper.split("><"))
            closing = "".join(f"</{part}>" for part in reversed(wrapper.split("><")))
            fragment_html = f"{opening}<{normalized_name}></{normalized_name}>{closing}"
        else:
            fragment_html = f"<{normalized_name}></{normalized_name}>"
        fragment = LexborHTMLParser(fragment_html)
        node = fragment.css_first(normalized_name)
        if node is None:
            raise ValueError(f"Unable to create tag {name!r}")
        wrapped = HtmlNode(node)
        wrapped._owner = fragment
        for key, value in {**(attrs or {}), **kwargs}.items():
            wrapped[str(key)] = value
        return wrapped


BeautifulSoup = HtmlDocument
