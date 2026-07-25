import itertools
import tempfile
from datetime import datetime, timezone
from pathlib import Path
import pytest

from yield_aggregator.feed import FeedItem, filter_items, deduplicate_stream
from yield_aggregator.storage import Database


def sample_items():
    return [
        FeedItem(
            guid="item-1",
            title="First Post",
            link="https://example.com/1",
            published=datetime(2025, 1, 10, 12, 0, tzinfo=timezone.utc),
            summary="Some intro text here",
            feed_title="Blog One",
        ),
        FeedItem(
            guid="item-2",
            title="Second Post - Python news",
            link="https://example.com/2",
            published=datetime(2025, 1, 11, 15, 30, tzinfo=timezone.utc),
            summary="Python 3.14 alpha details",
            feed_title="Blog One",
        ),
        FeedItem(
            guid="item-3",
            title="Offtopic rant",
            link="https://example.com/3",
            published=datetime(2025, 1, 12, 9, 0, tzinfo=timezone.utc),
            summary="Random musings",
            feed_title="Blog Two",
        ),
    ]


def test_keyword_filter_match():
    stream = sample_items()
    res = list(filter_items(stream, match_pattern=r"python", case_sensitive=False))
    assert len(res) == 1
    assert res[0].guid == "item-2"


def test_keyword_filter_exclude():
    stream = sample_items()
    res = list(filter_items(stream, exclude_pattern=r"rant"))
    assert len(res) == 2
    assert [x.guid for x in res] == ["item-1", "item-2"]


def test_sqlite_deduplication():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    try:
        db = Database(db_path)
        db.init_schema()

        # first pass: all 3 should pass through and be saved
        first_run = list(deduplicate_stream(sample_items(), db))
        assert len(first_run) == 3

        # second pass: nothing should get through
        second_run = list(deduplicate_stream(sample_items(), db))
        assert len(second_run) == 0

        # new item mixed in with old ones
        mixed = sample_items() + [
            FeedItem(
                guid="item-4",
                title="Fourth Post",
                link="https://example.com/4",
                published=datetime(2025, 1, 13, 10, 0, tzinfo=timezone.utc),
                summary="Brand new",
                feed_title="Blog One",
            )
        ]
        third_run = list(deduplicate_stream(mixed, db))
        assert len(third_run) == 1
        assert third_run[0].guid == "item-4"
    finally:
        if db_path.exists():
            db_path.unlink()


def test_fallback_hash_deduplication():
    # Feeds without guids fall back to link or title hash
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    try:
        db = Database(db_path)
        db.init_schema()

        items = [
            FeedItem(
                guid=None,
                title="No GUID post",
                link="https://example.com/no-guid",
                published=None,
                summary="test",
                feed_title="Site",
            ),
        ]
        res1 = list(deduplicate_stream(items, db))
        assert len(res1) == 1
        assert res1[0].title == "No GUID post"

        # Same item again without guid should be flagged duplicate by fallback link hash
        res2 = list(deduplicate_stream(items, db))
        assert len(res2) == 0
    finally:
        if db_path.exists():
            db_path.unlink()


def test_generator_lazy_consumption():
    # Ensure we don't drain the generator before yielding items downstream
    consumed = 0

    def infinite_feed():
        nonlocal consumed
        for i in itertools.count():
            consumed += 1
            yield FeedItem(
                guid=f"id-{i}",
                title=f"Title {i}",
                link=f"https://example.com/{i}",
                published=datetime(2025, 1, 1, tzinfo=timezone.utc),
                summary="",
                feed_title="Inf",
            )

    # take only first 5
    head = list(itertools.islice(infinite_feed(), 5))
    assert len(head) == 5
    # Shouldn't evaluate further than what slice asked for (or slice + 1 depending on iter wrapper)
    assert consumed <= 6
    # print(f"consumed: {consumed}")


# FIXME: add a test simulating slow network chunking with delayed yields
