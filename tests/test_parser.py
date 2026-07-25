import pytest
from datetime import datetime, timezone
from yield_aggregator.parser import parse_pubdate, strip_html, normalize_item


def test_strip_html():
    raw = "<p>Hello <b>World</b>! &amp; welcome</p>"
    assert strip_html(raw) == "Hello World ! & welcome"
    assert strip_html("") == ""
    assert strip_html(None) == ""


def test_parse_pubdate_rfc822():
    date_str = "Mon, 02 Jan 2023 15:04:05 +0000"
    expected = datetime(2023, 1, 2, 15, 4, 5, tzinfo=timezone.utc)
    assert parse_pubdate(date_str) == expected


def test_parse_pubdate_abbreviated_tz():
    date_str = "Wed, 14 Jun 2023 12:00:00 EDT"
    # EDT is UTC-4 -> 16:00 UTC
    expected = datetime(2023, 6, 14, 16, 0, 0, tzinfo=timezone.utc)
    assert parse_pubdate(date_str) == expected


def test_parse_pubdate_iso8601():
    date_str = "2023-01-02T15:04:05Z"
    expected = datetime(2023, 1, 2, 15, 4, 5, tzinfo=timezone.utc)
    assert parse_pubdate(date_str) == expected

    date_str_tz = "2023-01-02T16:04:05+01:00"
    assert parse_pubdate(date_str_tz) == expected


def test_parse_pubdate_garbage():
    assert parse_pubdate("not a date string") is None
    assert parse_pubdate("") is None
    assert parse_pubdate(None) is None


def test_normalize_item_basic():
    payload = {
        "title": "Sample Post &amp; News",
        "link": "https://example.com/post/1",
        "id": "tag:example.com,2023:1",
        "published": "2023-05-10T10:00:00Z",
        "summary": "<p>Just a test</p>"
    }
    item = normalize_item(payload, default_feed_title="My Feed")
    assert item.title == "Sample Post & News"
    assert item.link == "https://example.com/post/1"
    assert item.guid == "tag:example.com,2023:1"
    assert item.published_at == datetime(2023, 5, 10, 10, 0, 0, tzinfo=timezone.utc)
    assert item.summary == "Just a test"
    assert item.feed_title == "My Feed"


def test_normalize_item_fallback_guid():
    payload = {
        "title": "Missing ID Post",
        "link": "https://example.com/no-id-post",
    }
    item = normalize_item(payload)
    # should use link when available
    assert item.guid == "https://example.com/no-id-post"

    payload_no_link = {
        "title": "No Link Post",
    }
    item_no_link = normalize_item(payload_no_link)
    assert item_no_link.guid.startswith("gen:")
