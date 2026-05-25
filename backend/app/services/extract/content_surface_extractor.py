from __future__ import annotations

__all__ = (
    "CONTENT_DETAIL_SURFACES",
    "extract",
)

import math
import re
from typing import Any

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from app.services.config.extraction_rules import (
    CONTENT_SURFACE_CONTAINER_TAGS,
    CONTENT_SURFACE_DATE_SELECTORS,
    CONTENT_SURFACE_FORUM_BODY_SELECTORS,
    CONTENT_SURFACE_MAIN_SELECTORS,
    CONTENT_SURFACE_PROTECTED_DESCENDANT_SELECTORS,
    CONTENT_SURFACE_SANITIZE_SELECTORS,
)
from app.services.extract.table_extractor import extract_tables
from app.services.shared.field_coerce import absolute_url, clean_text

CONTENT_DETAIL_SURFACES = {"content_detail", "article_detail", "forum_detail"}


def extract(soup: BeautifulSoup, *, page_url: str, surface: str) -> dict[str, Any]:
    normalized = str(surface or "").strip().lower()
    working = BeautifulSoup(str(soup), "html.parser")
    _sanitize_dom(working)
    container = _main_container(working, normalized)
    tables = extract_tables(working, container, remove_from_dom=True)
    if normalized == "article_detail":
        record = _article_detail(working, container, page_url)
    elif normalized == "forum_detail":
        record = _forum_detail(working, container, page_url)
    else:
        record = _content_detail(working, container, page_url)
    if tables:
        record["tables"] = tables
    return {key: value for key, value in record.items() if value not in (None, "", [], {})}


def _content_detail(soup: BeautifulSoup, container: Tag, page_url: str) -> dict[str, Any]:
    content = _container_text(container)
    return {
        "title": _title(soup),
        "url": _canonical_url(soup, page_url),
        "markdown": _container_markdown(container, page_url),
        "content": content,
        "summary": _meta_description(soup) or _leading_paragraph(container),
        "headings": _headings(container),
        "word_count": _word_count(content),
        "image_url": _first_image(container, page_url),
        "language": _language(soup),
    }


def _article_detail(soup: BeautifulSoup, container: Tag, page_url: str) -> dict[str, Any]:
    content_container = _article_body_container(container) or _article_body_container(soup) or container
    content = _container_text(content_container)
    word_count = _word_count(content)
    return {
        "title": _title(soup),
        "url": _canonical_url(soup, page_url),
        "author": _selector_text(soup, [".author", "[rel='author']", "[itemprop='author']", ".byline"]),
        "publication_date": _date_text(soup),
        "markdown": _container_markdown(content_container, page_url),
        "content": content,
        "summary": _meta_description(soup) or _leading_paragraph(content_container),
        "image_url": _first_image(content_container, page_url),
        "tags": _tags(soup),
        "category": _category(soup),
        "language": _language(soup),
        "word_count": word_count,
        "reading_time": _reading_time(soup, word_count),
    }


def _forum_detail(soup: BeautifulSoup, container: Tag, page_url: str) -> dict[str, Any]:
    op_container = _first_match(
        soup,
        list(CONTENT_SURFACE_FORUM_BODY_SELECTORS),
    ) or container
    content = _container_text(op_container)
    return {
        "title": _title(soup),
        "url": _canonical_url(soup, page_url),
        "author": _selector_text(soup, [".author", "[rel='author']", "[itemprop='author']", ".username"]),
        "publication_date": _date_text(soup),
        "markdown": _container_markdown(op_container, page_url),
        "content": content,
        "summary": _meta_description(soup) or clean_text(content[:280]),
        "reply_count": _count_from_text(soup, ("reply", "replies", "comment", "comments")),
        "view_count": _count_from_text(soup, ("view", "views")),
        "tags": _tags(soup),
        "category": _category(soup),
    }


def _sanitize_dom(soup: BeautifulSoup) -> None:
    for selector in CONTENT_SURFACE_SANITIZE_SELECTORS:
        for node in soup.select(selector):
            if _sanitize_node_is_protected_container(node):
                continue
            node.decompose()
    for node in soup.select(
        "body > header, #header-wrapper, [id*='sidebar' i], [class*='sidebar' i], #toc"
    ):
        if _sanitize_node_is_protected_container(node):
            continue
        node.decompose()


def _sanitize_node_is_protected_container(node: Tag) -> bool:
    name = str(getattr(node, "name", "") or "").strip().lower()
    if name in CONTENT_SURFACE_CONTAINER_TAGS:
        return True
    return any(node.select_one(selector) is not None for selector in CONTENT_SURFACE_PROTECTED_DESCENDANT_SELECTORS)


def _main_container(soup: BeautifulSoup, surface: str) -> Tag:
    selectors = [
        "#article-content",
        "#main-content",
        "[id='content']",
        "[id*='article-content' i]",
        *list(CONTENT_SURFACE_MAIN_SELECTORS),
    ]
    if surface == "forum_detail":
        selectors = [".thread", ".topic", ".post", *selectors]
    return _largest_text_match(soup, selectors) or soup


def _first_match(soup: BeautifulSoup | Tag, selectors: list[str]) -> Tag | None:
    for selector in selectors:
        match = soup.select_one(selector)
        if match is not None:
            return match
    return None


def _largest_text_match(soup: BeautifulSoup | Tag, selectors: list[str]) -> Tag | None:
    matches: list[Tag] = []
    for selector in selectors:
        matches.extend(node for node in soup.select(selector) if isinstance(node, Tag))
    if not matches:
        return None
    return max(matches, key=lambda node: len(_container_text(node)))


def _article_body_container(root: BeautifulSoup | Tag) -> Tag | None:
    for selectors in (
        ["[itemprop='articleBody']", ".article-body", ".post-content", ".entry-content"],
        ["article"],
        [".post"],
    ):
        match = _largest_text_match(root, selectors)
        if match is not None:
            return match
    return None


def _title(soup: BeautifulSoup) -> str:
    for selector in ("h1", "meta[property='og:title']", "title"):
        node = soup.select_one(selector)
        value = clean_text(node.get("content") if node and node.name == "meta" else node.get_text(" ", strip=True) if node else "")
        if value:
            return value
    return ""


def _canonical_url(soup: BeautifulSoup, page_url: str) -> str:
    canonical = soup.find("link", attrs={"rel": re.compile("canonical", re.I)})
    return absolute_url(page_url, canonical.get("href") if canonical else "") or page_url


def _meta_description(soup: BeautifulSoup) -> str:
    for selector in ("meta[name='description']", "meta[property='og:description']", "meta[name='twitter:description']"):
        node = soup.select_one(selector)
        value = clean_text(node.get("content") if node else "")
        if value:
            return value
    return ""


def _container_text(container: Tag) -> str:
    return clean_text(container.get_text(" ", strip=True))


# ---------------------------------------------------------------------------
# Math helpers
# ---------------------------------------------------------------------------

# Matches $$...$$ (display) then $...$ (inline) — order matters so display is
# consumed first and doesn't get split into two inline segments.
_MATH_DOLLAR_RE = re.compile(r"\$\$[\s\S]*?\$\$|\$[^$\n]*?\$")

# Matches all 4 types of math delimiters for stashing during inline cleaning
_ALL_MATH_RE = re.compile(
    r"\$\$[\s\S]*?\$\$|"       # $$...$$
    r"\$[^$\n]*?\$|"           # $...$
    r"\\\[[\s\S]*?\\\]|"       # \[...\]
    r"\\\([\s\S]*?\\\)"        # \(...\)
)

# MathJax \[...\] display and \(...\) inline delimiters.
_MATH_DISPLAY_RE = re.compile(r"\\\[\s*(.*?)\s*\\\]", re.DOTALL)
_MATH_INLINE_RE = re.compile(r"\\\(\s*(.*?)\s*\\\)", re.DOTALL)


def _clean_math_text(math_text: str) -> str:
    """Normalize typographical characters inside math segments to standard LaTeX equivalents."""
    # Replace curly apostrophes/quotes with standard straight ones
    math_text = math_text.replace("’", "'").replace("‘", "'")
    math_text = math_text.replace("”", '"').replace("“", '"')
    # Replace typography dashes (en-dash, em-dash) with standard hyphens/minus signs
    math_text = math_text.replace("—", "-").replace("–", "-")
    return math_text


def _stash_math(text: str) -> tuple[str, dict[str, str]]:
    """Replace only dollar-delimited math segments with placeholders. Used during normalization."""
    stash: dict[str, str] = {}

    def _replace(m: re.Match) -> str:
        key = f"\x00M{len(stash):04d}\x00"
        stash[key] = m.group(0)
        return key

    return _MATH_DOLLAR_RE.sub(_replace, text), stash


def _stash_all_math(text: str) -> tuple[str, dict[str, str]]:
    """Replace all math segments ($, $$, \\(, \\[) with placeholders. Used during inline cleaning."""
    stash: dict[str, str] = {}

    def _replace(m: re.Match) -> str:
        key = f"\x00M{len(stash):04d}\x00"
        stash[key] = m.group(0)
        return key

    return _ALL_MATH_RE.sub(_replace, text), stash


def _restore_math(text: str, stash: dict[str, str]) -> str:
    for key, val in stash.items():
        text = text.replace(key, val)
    return text


def _normalize_math(text: str) -> str:
    """Convert MathJax \\[…\\] / \\(…\\) delimiters to $$…$$ / $…$ and clean math text."""
    # Stash existing $...$ math first so we don't double-convert.
    text, stash = _stash_math(text)
    
    # Also clean the stashed math content
    clean_stash = {}
    for key, val in stash.items():
        clean_stash[key] = _clean_math_text(val)
        
    text = _MATH_DISPLAY_RE.sub(lambda m: f"$$\n{_clean_math_text(m.group(1))}\n$$", text)
    text = _MATH_INLINE_RE.sub(lambda m: f"${_clean_math_text(m.group(1))}$", text)
    return _restore_math(text, clean_stash)


# ---------------------------------------------------------------------------
# Code block helpers
# ---------------------------------------------------------------------------

def _collapse_tokenized_code_block(body: str) -> str:
    """Collapse span-per-token code blocks back to proper lines.

    Syntax-highlighted pages (e.g. Firecrawl docs) emit one <span> per token;
    get_text() turns each span into its own line.  The heuristic fires when
    avg line length <= 20 chars and >= 60% of lines are single-token.
    """
    lines = body.split("\n")
    non_empty = [ln for ln in lines if ln.strip()]
    if not non_empty:
        return body
    avg_len = sum(len(ln.strip()) for ln in non_empty) / len(non_empty)
    single_token = sum(1 for ln in non_empty if len(ln.strip().split()) <= 2)
    if avg_len > 20 or single_token / len(non_empty) < 0.6:
        return body

    BREAK_AFTER = re.compile(r"[;{},]$")
    BREAK_BEFORE = re.compile(r"^(def |class |if |for |while |return |#|import |from )")
    result: list[str] = []
    current: list[str] = []
    for raw in lines:
        token = raw.rstrip()
        stripped = token.strip()
        if not stripped:
            if current:
                result.append(" ".join(current))
                current = []
            result.append("")
            continue
        if current and BREAK_BEFORE.match(stripped):
            result.append(" ".join(current))
            current = []
        current.append(stripped)
        if BREAK_AFTER.search(stripped) or stripped.startswith("#"):
            result.append(" ".join(current))
            current = []
    if current:
        result.append(" ".join(current))
    return "\n".join(result)


_FENCED_CODE_BLOCK_RE = re.compile(r"(```[^\n]*)\n(.*?)\n(```)", re.DOTALL)


def _collapse_tokenized_code_blocks(markdown: str) -> str:
    """Apply _collapse_tokenized_code_block to every fenced code block."""
    def _replace(m: re.Match) -> str:
        return f"{m.group(1)}\n{_collapse_tokenized_code_block(m.group(2))}\n{m.group(3)}"
    return _FENCED_CODE_BLOCK_RE.sub(_replace, markdown)


# Map common <code class="language-*"> / highlight.js class names to fence labels.
_LANG_CLASS_RE = re.compile(r"\blanguage-(\w+)\b|^(\w+)$")

def _code_language(node: Tag) -> str:
    """Extract a language hint from a <pre> or its first <code> child."""
    for candidate in (node, node.find("code")):
        if not isinstance(candidate, Tag):
            continue
        classes = candidate.get("class") or []
        for cls in (classes if isinstance(classes, list) else classes.split()):
            m = _LANG_CLASS_RE.match(str(cls))
            if m:
                lang = m.group(1) or m.group(2)
                # Skip generic classes like "highlight", "code", "hljs"
                if lang.lower() not in {"highlight", "code", "hljs", "prettyprint", "sourceCode"}:
                    return lang
    return ""


# ---------------------------------------------------------------------------
# Markdown assembly
# ---------------------------------------------------------------------------

# Detects lines that begin a list item (bullet or ordered).
_LIST_ITEM_RE = re.compile(r"^(-|\d+\.)\s")


def _container_markdown(container: Tag, page_url: str) -> str:
    lines = _markdown_lines(container, page_url)

    result: list[str] = []
    prev_is_list = False

    for line in lines:
        text = line.rstrip()

        if not text:
            if result and result[-1]:  # deduplicate consecutive blank lines
                result.append("")
            prev_is_list = False
            continue

        is_list = bool(_LIST_ITEM_RE.match(text))

        if result:
            last_nonempty = next((l for l in reversed(result) if l), None)
            needs_blank = (
                last_nonempty is not None
                and not (is_list and prev_is_list)  # keep list items tight
            )
            if needs_blank and result[-1]:
                result.append("")

        result.append(text)
        prev_is_list = is_list

    raw = "\n".join(result).strip()
    # Collapse any 3+ consecutive blank lines down to two.
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    raw = _normalize_math(raw)
    return _collapse_tokenized_code_blocks(raw)


def _markdown_lines(node: Tag, page_url: str) -> list[str]:
    lines: list[str] = []
    for child in node.children:
        if isinstance(child, NavigableString):
            if isinstance(child, Comment):
                continue
            text = clean_text(str(child))
            if text:
                lines.append(text)
            continue
        if not isinstance(child, Tag):
            continue
        name = str(child.name or "").lower()

        # ------------------------------------------------------------------ #
        # Script — only care about MathJax embedded LaTeX                     #
        # ------------------------------------------------------------------ #
        if name == "script":
            script_type = (child.get("type") or "").lower()
            if "math/tex" in script_type:
                latex = clean_text(child.get_text())
                if latex:
                    if "display" in script_type:
                        lines.append(f"\\[{latex}\\]")
                    else:
                        lines.append(f"\\({latex}\\)")
            continue

        if name in {"style", "noscript", "template"}:
            continue

        # ------------------------------------------------------------------ #
        # Headings                                                             #
        # ------------------------------------------------------------------ #
        if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            level = int(name[1])
            text = _inline_markdown(child, page_url)
            if text:
                lines.append(f"{'#' * level} {text}")
            continue

        # ------------------------------------------------------------------ #
        # Paragraphs / summary                                                 #
        # ------------------------------------------------------------------ #
        if name in {"p", "summary"}:
            text = _inline_markdown(child, page_url)
            if text:
                lines.append(text)
            continue

        # ------------------------------------------------------------------ #
        # Standalone anchor                                                    #
        # ------------------------------------------------------------------ #
        if name == "a":
            text = _inline_markdown(child, page_url)
            href = absolute_url(page_url, child.get("href"))
            if text:
                lines.append(f"[{clean_text(text)}]({href})" if href else clean_text(text))
            continue

        # ------------------------------------------------------------------ #
        # Images                                                               #
        # ------------------------------------------------------------------ #
        if name == "img":
            src = absolute_url(page_url, child.get("src") or child.get("data-src"))
            alt = clean_text(child.get("alt") or "")
            if src:
                lines.append(f"![{alt}]({src})")
            continue

        # ------------------------------------------------------------------ #
        # Lists — handle ol/ul explicitly to preserve numbering and avoid     #
        # double-nesting when li items contain block children.                #
        # ------------------------------------------------------------------ #
        if name == "ul":
            for item in child.find_all("li", recursive=False):
                text = _inline_markdown(item, page_url)
                if text:
                    lines.append(f"- {text}")
            continue

        if name == "ol":
            for idx, item in enumerate(child.find_all("li", recursive=False), start=1):
                text = _inline_markdown(item, page_url)
                if text:
                    lines.append(f"{idx}. {text}")
            continue

        # Bare <li> outside a list container (malformed HTML) — treat as bullet
        if name == "li":
            text = _inline_markdown(child, page_url)
            if text:
                lines.append(f"- {text}")
            continue

        # ------------------------------------------------------------------ #
        # Preformatted / code blocks                                           #
        # ------------------------------------------------------------------ #
        if name == "pre":
            lang = _code_language(child)
            # Use inner <code> text when present so we strip the wrapper tag.
            code_node = child.find("code")
            raw_text = (code_node if isinstance(code_node, Tag) else child).get_text("\n", strip=False)
            # Normalise trailing whitespace per line but keep empty lines.
            text = "\n".join(ln.rstrip() for ln in raw_text.splitlines()).strip()
            if text:
                lines.append(f"```{lang}\n{text}\n```")
            continue

        # ------------------------------------------------------------------ #
        # Blockquote                                                           #
        # ------------------------------------------------------------------ #
        if name == "blockquote":
            inner_lines = _markdown_lines(child, page_url)
            for inner in inner_lines:
                if inner.strip():
                    lines.append("\n".join(f"> {part}" for part in inner.splitlines()))
                else:
                    lines.append(">")
            continue

        # ------------------------------------------------------------------ #
        # Generic container — recurse if it has block children                #
        # ------------------------------------------------------------------ #
        if not _has_markdown_block_child(child):
            text = _inline_markdown(child, page_url)
            if text:
                lines.append(text)
            continue

        lines.extend(_markdown_lines(child, page_url))
    return lines


def _has_markdown_block_child(node: Tag) -> bool:
    block_names = {
        "article", "blockquote", "div",
        "h1", "h2", "h3", "h4", "h5", "h6",
        "li", "ol", "p", "pre", "section", "table", "ul",
    }
    return any(
        isinstance(child, Tag)
        and str(child.name or "").lower() in block_names
        and _node_has_markdown_signal(child)
        for child in node.children
    )


def _node_has_markdown_signal(node: Tag) -> bool:
    return bool(clean_text(node.get_text(" ", strip=True)) or node.find("img") or node.name == "img")


def _inline_markdown(node: Tag, page_url: str) -> str:
    parts: list[str] = []
    for child in node.children:
        if isinstance(child, Comment):
            continue
        if isinstance(child, NavigableString):
            parts.append(str(child))
            continue
        if not isinstance(child, Tag):
            continue
        name = str(child.name or "").lower()

        if name == "br":
            parts.append("\n")
            continue

        if name == "script":
            script_type = (child.get("type") or "").lower()
            if "math/tex" in script_type:
                latex = clean_text(child.get_text())
                if latex:
                    if "display" in script_type:
                        parts.append(f"\\[{latex}\\]")
                    else:
                        parts.append(f"\\({latex}\\)")
            continue

        if name in {"style", "noscript", "template"}:
            continue

        text = _inline_markdown(child, page_url) or child.get_text(" ", strip=True)
        if not text:
            continue

        if name == "a":
            href = absolute_url(page_url, child.get("href"))
            parts.append(f"[{clean_text(text)}]({href})" if href else text)
        elif name == "img":
            src = absolute_url(page_url, child.get("src") or child.get("data-src"))
            alt = clean_text(child.get("alt") or "")
            if src:
                parts.append(f"![{alt}]({src})")
        elif name == "code":
            parts.append(f"`{clean_text(text)}`")
        elif name in {"strong", "b"}:
            parts.append(f"**{clean_text(text)}**")
        elif name in {"em", "i"}:
            parts.append(f"*{clean_text(text)}*")
        else:
            parts.append(text)

    return _clean_markdown_inline("".join(parts))


def _clean_markdown_inline(value: str) -> str:
    """Normalise whitespace in inline markdown while preserving math segments."""
    text = str(value or "").replace("\xa0", " ")

    # Stash all math segments so the whitespace normalisations below cannot
    # corrupt LaTeX content (e.g. stripping the space in `\neg (x)`).
    text, stash = _stash_all_math(text)

    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    # Strip extraneous space before punctuation — safe now that math is stashed.
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)

    return _restore_math(text, stash).strip()


# ---------------------------------------------------------------------------
# Field helpers
# ---------------------------------------------------------------------------

def _leading_paragraph(container: Tag) -> str:
    for paragraph in container.find_all("p"):
        value = clean_text(paragraph.get_text(" ", strip=True))
        if len(value) >= 40:
            return value
    return ""


def _headings(container: Tag) -> list[str]:
    return list(dict.fromkeys(
        clean_text(node.get_text(" ", strip=True))
        for node in container.find_all(["h2", "h3"])
        if clean_text(node.get_text(" ", strip=True))
    ))


def _word_count(value: str) -> int:
    return len(re.findall(r"\w+", value or ""))


def _first_image(container: Tag, page_url: str) -> str:
    for img in container.find_all("img"):
        src = img.get("src") or img.get("data-src")
        resolved = absolute_url(page_url, src)
        if resolved:
            return resolved
    return ""


def _language(soup: BeautifulSoup) -> str:
    html = soup.find("html")
    return clean_text(html.get("lang") if html else "")


def _selector_text(soup: BeautifulSoup, selectors: list[str]) -> str:
    node = _first_match(soup, selectors)
    return clean_text(node.get_text(" ", strip=True) if node else "")


def _date_text(soup: BeautifulSoup) -> str:
    for selector in CONTENT_SURFACE_DATE_SELECTORS:
        node = soup.select_one(selector)
        if node is None:
            continue
        value = clean_text(node.get("datetime") or node.get("content") or node.get_text(" ", strip=True))
        if value:
            return value
    return ""


def _tags(soup: BeautifulSoup) -> list[str]:
    values = []
    for node in soup.select("[rel='tag'], .tag, .tags a"):
        value = clean_text(node.get_text(" ", strip=True))
        if value:
            values.append(value)
    return list(dict.fromkeys(values))


def _category(soup: BeautifulSoup) -> str:
    return _selector_text(soup, [".category", "[rel='category']", ".breadcrumb"])


def _reading_time(soup: BeautifulSoup, word_count: int) -> int | None:
    node = _first_match(soup, [".reading-time", "[itemprop='timeRequired']", "[data-reading-time]"])
    raw = clean_text((node.get("content") or node.get("data-reading-time") or node.get_text(" ", strip=True)) if node else "")
    match = re.search(r"\d+", raw)
    if match:
        return int(match.group(0))
    if word_count:
        return int(math.ceil(word_count / 200))
    return None


def _count_from_text(soup: BeautifulSoup, labels: tuple[str, ...]) -> int | None:
    text = clean_text(soup.get_text(" ", strip=True)).lower()
    for label in labels:
        match = re.search(rf"(\d[\d,]*)\s+{re.escape(label)}\b", text)
        if match:
            return int(match.group(1).replace(",", ""))
    return None