# yield-aggregator-cli

A small CLI tool I built to poll, filter, and stream RSS/Atom feeds without spinning up a web server or heavy reader. Everything runs through generator pipelines so memory stays flat even with hundreds of feeds.

## Install

```bash
git clone https://github.com/author/yield-aggregator-cli.git
cd yield-aggregator-cli
pip install .
```

Or install in editable mode for development:

```bash
pip install -e .
```

## Usage

Add feeds:

```bash
yield-agg add https://news.ycombinator.com/rss --tag tech
yield-agg add https://feeds.bloomberg.com/markets/news.rss --tag finance
```

Stream new items directly to terminal:

```bash
yield-agg stream --unread
```

Filter by keyword and output JSON lines for piping into jq:

```bash
yield-agg stream --match "yield|rate" --format jsonl | jq '.title'
```

Mark everything as read or dump db stats:

```bash
yield-agg mark-read --all
yield-agg stats
```

Feeds and read state are stored in a local SQLite database at `~/.config/yield-aggregator/feeds.db` by default (configurable via `YIELD_AGG_DB` env var).

## Tests

```bash
pytest
```

## License

MIT

<!-- generated: 2026-09-11 -->
