import re
import html
import hashlib
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from typing import Optional, NamedTuple


class ParsedItem(NamedTuple):
    title: str
    link: str
    guid: str
    published_at: Optional[datetime]
    summary: str
    feed_title: Optional[str] = None


_TAG_RE = re.compile(r"<[^>]+>")

# Some weird feeds use military timezone letters or 3-letter abbreviations
# that email.utils chokes on if they aren't standard RFC 2822.
_TZ_FIXES = {
    "EDT": "-0400",
    "EST": "-0500",
    "CDT": "-0500",
    "CST": "-0600",
    "MDT": "-0600",
    "MST": "-0700",
    "PDT": "-0700",
    "PST": "-0800",
    "UT": "+0000",
    "GMT": "+0000",
}


def strip_html(text: Optional[str]) -> str:
    if not text:
        return ""
    clean = _TAG_RE.sub(" ", text)
    clean = html.unescape(clean)
    return re.sub(r"\s+", " ", clean).strip()


def parse_pubdate(raw: Optional[str]) -> Optional[datetime]:
    """Parse standard RSS (RFC 822/2822) or Atom (ISO 8601) timestamps into UTC."""
    if not raw:
        return None
    raw = raw.strip()
    
    # Swap non-standard tz abbreviation at end if present
    parts = raw.split()
    if parts and parts[-1].upper() in _TZ_FIXES:
        parts[-1] = _TZ_FIXES[parts[-1].upper()]
        raw_normalized = " ".join(parts)
    else:
        raw_normalized = raw

    # Try RFC 822 / 2822 first (common in RSS 2.0)
    try:
        dt = parsedate_to_datetime(raw_normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        pass

    # Try ISO-8601 (Atom)
    try:
        iso_raw = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
        dt = datetime.fromisoformat(iso_raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        pass

    # print(f"DEBUG: failed to parse date: {raw}")
    return None


def _make_fallback_guid(title: str, link: str) -> str:
    src = f"{title}|{link}".encode("utf-8")
    return "gen:" + hashlib.sha1(src).hexdigest()[:16]


def normalize_item(raw_dict: dict, default_feed_title: Optional[str] = None) -> ParsedItem:
    title = strip_html(raw_dict.get("title", "")) or "(no title)"
    link = (raw_dict.get("link") or "").strip()
    
    guid = raw_dict.get("id") or raw_dict.get("guid")
    if isinstance(guid, dict):
        # Some XML parsers leave attrs in a dict under 'guid'
        guid = guid.get("#text") or guid.get("value")
    
    if not guid or not str(guid).strip():
        guid = link if link else _make_fallback_guid(title, link)

    pub = raw_dict.get("published") or raw_dict.get("pubDate") or raw_dict.get("updated")
    published_at = parse_pubdate(pub)

    summary = raw_dict.get("summary") or raw_dict.get("description") or ""
    
    return ParsedItem(
        title=title,
        link=link,
        guid=str(guid).strip(),
        published_at=published_at,
        summary=strip_html(summary),
        feed_title=raw_dict.get("feed_title") or default_feed_title
    )
