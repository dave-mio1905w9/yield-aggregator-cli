import time
import random
import logging
from typing import Generator, Any, Dict
import httpx
from yield_aggregator.parser import parse_feed_chunk

log = logging.getLogger("yield_aggregator")


def fetch_feed_stream(
    url: str,
    etag: str | None = None,
    last_modified: str | None = None,
    client: httpx.Client | None = None,
) -> Generator[bytes, None, tuple[str | None, str | None]]:
    """Stream raw response bytes and return latest caching headers on exit."""
    owns_client = False
    if client is None:
        # Default connect timeout is lower so broken endpoints don't stall the whole loop
        timeout_config = httpx.Timeout(15.0, connect=5.0)
        client = httpx.Client(follow_redirects=True, timeout=timeout_config)
        owns_client = True

    headers = {"User-Agent": "yield-aggregator/0.2.0"}
    if etag:
        headers["If-None-Match"] = etag
    if last_modified:
        headers["If-Modified-Since"] = last_modified

    new_etag = etag
    new_last_mod = last_modified

    try:
        with client.stream("GET", url, headers=headers) as resp:
            if resp.status_code == 429:
                # Standard backoff + random jitter to prevent thundering herd
                retry_val = resp.headers.get("Retry-After", "5")
                try:
                    retry_sec = float(retry_val)
                except ValueError:
                    retry_sec = 5.0
                log.warning("rate limited on %s, pausing %.1fs", url, retry_sec)
                time.sleep(retry_sec + random.uniform(0.5, 1.5))
                return (etag, last_modified)

            if resp.status_code == 304:
                return (etag, last_modified)

            if resp.status_code >= 400:
                log.warning("unexpected status %d for %s", resp.status_code, url)
                return (etag, last_modified)

            # Save caching headers for next round
            new_etag = resp.headers.get("ETag", etag)
            new_last_mod = resp.headers.get("Last-Modified", last_modified)

            for chunk in resp.iter_bytes(chunk_size=4096):
                if chunk:
                    yield chunk

    except (httpx.ConnectTimeout, httpx.ReadTimeout) as err:
        log.warning("timeout polling %s: %s", url, err)
    except httpx.RequestError as exc:
        log.warning("network failure polling %s: %s", url, exc)
    finally:
        if owns_client:
            client.close()

    return (new_etag, new_last_mod)


def stream_feed(url: str, etag: str | None = None, last_mod: str | None = None) -> Generator[Dict[str, Any], None, tuple[str | None, str | None]]:
    chunk_gen = fetch_feed_stream(url, etag=etag, last_modified=last_mod)
    # FIXME: Some feeds send broken ISO 8601 with timezone offsets like '+0000' missing colon
    yield from parse_feed_chunk(chunk_gen)
    return (None, None)


def merge_streams(*generators: Generator[Dict[str, Any], None, Any]) -> Generator[Dict[str, Any], None, None]:
    active = list(generators)
    while active:
        next_active = []
        for gen in active:
            try:
                item = next(gen)
                yield item
                next_active.append(gen)
            except StopIteration:
                pass
            except Exception as e:
                log.error("stream worker threw unexpected exception: %s", e)
        active = next_active


def live_feed_watcher(urls: list[str], interval: int = 300) -> Generator[Dict[str, Any], None, None]:
    # Keep track of caching metadata per URL to minimize bandwidth during polling
    cache_meta: dict[str, dict[str, str | None]] = {
        u: {"etag": None, "last_mod": None} for u in urls
    }
    
    with httpx.Client(follow_redirects=True, timeout=httpx.Timeout(15.0, connect=5.0)) as shared_client:
        while True:
            start_cycle = time.monotonic()
            for url in urls:
                meta = cache_meta[url]
                stream = fetch_feed_stream(
                    url,
                    etag=meta["etag"],
                    last_modified=meta["last_mod"],
                    client=shared_client,
                )
                try:
                    for item in parse_feed_chunk(stream):
                        yield item
                except Exception as err:
                    log.debug("error during feed parse step for %s: %s", url, err)

            elapsed = time.monotonic() - start_cycle
            wait_time = max(1.0, interval - elapsed)
            time.sleep(wait_time)
