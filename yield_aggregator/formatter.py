import json
import sys
from typing import Iterator
from yield_aggregator.parser import ParsedItem

# Basic ANSI codes for terminal rendering
_CYAN = "\033[36m"
_GREEN = "\033[32m"
_DIM = "\033[2m"
_BOLD = "\033[1m"
_RESET = "\033[0m"


def _use_color() -> bool:
    return sys.stdout.isatty()


def format_jsonl(items: Iterator[ParsedItem]) -> Iterator[str]:
    for item in items:
        data = {
            "title": item.title,
            "link": item.link,
            "guid": item.guid,
            "published_at": item.published_at.isoformat() if item.published_at else None,
            "summary": item.summary,
            "feed_title": item.feed_title,
        }
        yield json.dumps(data, ensure_ascii=False)


def format_compact(items: Iterator[ParsedItem]) -> Iterator[str]:
    use_c = _use_color()
    for item in items:
        date_str = item.published_at.strftime("%Y-%m-%d %H:%M") if item.published_at else "----/--/--"
        feed_prefix = f"[{item.feed_title}] " if item.feed_title else ""
        
        if use_c:
            line = f"{_DIM}{date_str}{_RESET} {_CYAN}{feed_prefix}{_RESET}{_BOLD}{item.title}{_RESET} {_GREEN}<{item.link}>{_RESET}"
        else:
            line = f"{date_str} {feed_prefix}{item.title} <{item.link}>"
        yield line


def format_full(items: Iterator[ParsedItem]) -> Iterator[str]:
    use_c = _use_color()
    for item in items:
        date_str = item.published_at.strftime("%a, %d %b %Y %H:%M:%S UTC") if item.published_at else "Unknown date"
        feed_hdr = f" [{item.feed_title}]" if item.feed_title else ""
        
        if use_c:
            header = f"{_BOLD}{item.title}{_RESET}{_CYAN}{feed_hdr}{_RESET}"
            meta = f"{_DIM}{date_str} | {item.link}{_RESET}"
        else:
            header = f"{item.title}{feed_hdr}"
            meta = f"{date_str} | {item.link}"
            
        # FIXME: wrap summary text nicely to terminal width
        summary = item.summary if item.summary else "(no description)"
        separator = "-" * 40
        
        yield f"{header}\n{meta}\n{summary}\n{separator}"
