"""Passive Canvas HTML previews, separate from retrieval chunks.

Retain document structure and bounded presentation styles. Drop executable
content, form controls and automatic remote requests. Links require a deliberate
click; authenticated media stays available through the canonical Canvas page.
"""

import re
from html import escape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

TAGS = {
    "p",
    "div",
    "span",
    "br",
    "hr",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "s",
    "del",
    "sub",
    "sup",
    "ul",
    "ol",
    "li",
    "dl",
    "dt",
    "dd",
    "blockquote",
    "pre",
    "code",
    "table",
    "caption",
    "colgroup",
    "col",
    "thead",
    "tbody",
    "tfoot",
    "tr",
    "th",
    "td",
    "a",
    "figure",
    "figcaption",
}
DROP = {
    "script",
    "style",
    "iframe",
    "object",
    "embed",
    "svg",
    "math",
    "template",
    "form",
    "input",
    "textarea",
    "select",
    "button",
    "link",
    "meta",
    "base",
}
VOID = {"br", "hr", "col"}
STYLES = {
    "text-align": r"(left|right|center|justify|start|end)",
    "font-weight": r"(normal|bold|[1-9]00)",
    "font-style": r"(normal|italic)",
    "text-decoration": r"(none|underline|line-through)",
    "font-size": r"(\d{1,2}(\.\d{1,2})?(px|pt|em|rem|%)|small|medium|large|x-large)",
    "line-height": r"\d{1,2}(\.\d{1,2})?(px|pt|em|rem|%)?",
    "margin-left": r"\d{1,3}(\.\d{1,2})?(px|pt|em|rem|%)",
    "color": r"(#[a-fA-F0-9]{3,8}|black|blue|red|green|gray|grey)",
    "background-color": r"(#[a-fA-F0-9]{3,8}|white|transparent)",
    "white-space": r"(normal|pre-wrap|pre-line)",
}


def safe_link(value):
    try:
        url = urljoin("https://canvas.ust.hk/", value.strip())
        parts = urlsplit(url)
        if (
            parts.scheme in {"http", "https"}
            and parts.hostname
            and not parts.username
            and not parts.password
            and not any(ord(c) < 32 for c in url)
        ):
            return url
    except ValueError:
        pass
    return None


class PreviewHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.output = []
        self.hidden = []

    def handle_starttag(self, tag, attrs):
        if tag in DROP:
            if tag not in {"input", "embed", "link", "meta", "base"}:
                self.hidden.append(tag)
            return
        if self.hidden:
            return
        values = dict(attrs)
        if tag == "img":
            self.output.append(
                '<span class="source-media-note">['
                + escape(values.get("alt") or "Image")
                + " — open in Canvas]</span>"
            )
            return
        if tag not in TAGS:
            return
        clean = []
        if tag == "a" and (href := safe_link(values.get("href") or "")):
            clean += [
                ("href", href),
                ("target", "_blank"),
                ("rel", "noopener noreferrer"),
                ("referrerpolicy", "no-referrer"),
            ]
        if values.get("dir") in {"ltr", "rtl", "auto"}:
            clean.append(("dir", values["dir"]))
        for key in ("colspan", "rowspan", "start"):
            if values.get(key, "").isdigit() and 0 < int(values[key]) <= 1000:
                clean.append((key, values[key]))
        declarations = []
        for declaration in (values.get("style") or "").split(";"):
            prop, _, value = declaration.partition(":")
            prop, value = prop.strip().lower(), value.strip()
            if prop in STYLES and re.fullmatch(STYLES[prop], value):
                declarations.append(f"{prop}:{value}")
        if declarations:
            clean.append(("style", ";".join(declarations)))
        self.output.append(
            "<"
            + tag
            + "".join(
                " " + key + '="' + escape(value, quote=True) + '"'
                for key, value in clean
            )
            + ">"
        )

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID and tag not in {
            "img",
            "input",
            "embed",
            "link",
            "meta",
            "base",
        }:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if self.hidden:
            if tag in self.hidden:
                self.hidden = self.hidden[
                    : len(self.hidden) - 1 - self.hidden[::-1].index(tag)
                ]
            return
        if tag in TAGS and tag not in VOID:
            self.output.append("</" + tag + ">")

    def handle_data(self, data):
        if not self.hidden:
            self.output.append(escape(data))


def canvas_html(body):
    parser = PreviewHTML()
    parser.feed(str(body)[:2_000_000])
    parser.close()
    return "".join(parser.output)


def reading_text(chunks):
    """Remove retrieval overlap; keep paragraph/page/heading breaks."""
    groups = []
    locator = None
    for chunk in chunks:
        here = {k: v for k, v in chunk["locator"].items() if k != "offset"}
        offset = chunk["locator"].get("offset", 0)
        if groups and here == locator and offset > 0:
            current = groups[-1]
            # Chunk boundaries strip whitespace; align the actual text overlap.
            overlap = min(160, len(current), len(chunk["text"]))
            while overlap and current[-overlap:] != chunk["text"][:overlap]:
                overlap -= 1
            groups[-1] += chunk["text"][overlap:] if overlap else "\n" + chunk["text"]
        else:
            groups.append(chunk["text"])
        locator = here
    return "\n\n".join(groups)
