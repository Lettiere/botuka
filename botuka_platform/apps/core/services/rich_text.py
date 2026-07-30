"""Sanitização conservadora de HTML produzido por editores internos."""

from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse

ALLOWED_TAGS = {
    "p", "br", "strong", "b", "em", "i", "h2", "h3", "ul", "ol", "li",
    "blockquote", "a", "hr", "div",
}
VOID_TAGS = {"br", "hr"}
DROP_WITH_CONTENT = {"script", "style", "iframe", "object", "embed", "svg", "math"}


class _Sanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.output, self.open_tags, self.drop_depth = [], [], 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in DROP_WITH_CONTENT:
            self.drop_depth += 1
            return
        if self.drop_depth or tag not in ALLOWED_TAGS:
            return
        attrs = dict(attrs)
        clean = []
        if tag == "a":
            href = (attrs.get("href") or "").strip()
            parsed = urlparse(href)
            if href.startswith(("#", "/")) or parsed.scheme in {"http", "https", "mailto"}:
                clean.extend([("href", href), ("rel", "noopener noreferrer")])
                if attrs.get("target") == "_blank":
                    clean.append(("target", "_blank"))
        alignment = (attrs.get("style") or "").replace(" ", "").lower()
        existing_class = (attrs.get("class") or "").strip()
        if tag in {"p", "div"} and alignment in {"text-align:left", "text-align:center", "text-align:right"}:
            clean.append(("class", f"richtext-align-{alignment.rsplit(':', 1)[1]}"))
        elif tag in {"p", "div"} and existing_class in {
            "richtext-align-left", "richtext-align-center", "richtext-align-right",
        }:
            clean.append(("class", existing_class))
        rendered = "".join(f' {name}="{escape(value, quote=True)}"' for name, value in clean)
        self.output.append(f"<{tag}{rendered}>")
        if tag not in VOID_TAGS:
            self.open_tags.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in DROP_WITH_CONTENT:
            self.drop_depth = max(0, self.drop_depth - 1)
            return
        if self.drop_depth or tag not in self.open_tags:
            return
        while self.open_tags:
            current = self.open_tags.pop()
            self.output.append(f"</{current}>")
            if current == tag:
                break

    def handle_data(self, data):
        if not self.drop_depth:
            self.output.append(escape(data))

    def close(self):
        super().close()
        while self.open_tags:
            self.output.append(f"</{self.open_tags.pop()}>")


def sanitizar_html_rico(value):
    sanitizer = _Sanitizer()
    sanitizer.feed(value or "")
    sanitizer.close()
    return "".join(sanitizer.output).strip()
