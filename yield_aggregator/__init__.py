"""Pipeline-based feed aggregator."""

from yield_aggregator.feed import stream_feed, merge_streams

__version__ = "0.2.0"
__all__ = ["stream_feed", "merge_streams", "__version__"]
