# Changelog

## 0.5.0 — updates from a file (2026-10-23)

A site can keep its "Recent updates" in `source/updates.yaml`, next to its
content, instead of in a Google Sheet. Updates then live in git, appear on the
next build, and need no network access, so a site rebuilds offline and a
Google outage can no longer fail the build.

`Site.get_recent_updates()` takes the first source that applies: the file when
it exists, else the sheet named by `update_spreedsheet_id`, else nothing.

### Added

- `SiteConfig.updates_file` (default `source_dir/updates.yaml`) and
  `SiteConfig.updates_limit` (default `5`, the count that was hardcoded).
- `oxie.load_updates_file(path, config)`: reads a YAML list of `date` /
  `content` entries, newest first. Keys are case-insensitive. Dates go through
  `SiteConfig.to_datetime()`, so a date-only entry becomes noon in the site
  timezone, like a post date. A malformed entry raises `ValueError` naming the
  file and the entry number: invalid YAML, a top level that is not a list, an
  entry that is not a mapping, a missing or empty `date`/`content`, or a date
  that is not ISO 8601 (`DD/MM/YYYY` is rejected).
- `oxie init` writes a starter `source/updates.yaml` with one entry, so a new
  site shows the feature on its first build.

### Changed — output

None for existing sites. Output changes only when a site adds the file. A site
still on the sheet was rebuilt with 0.4.1 and 0.5.0 and compared with
`diff -r`: identical.

When a site moves to the file, expect differences only in whitespace inside
the updates box, since `content` is stripped. Dates from the file are
timezone-aware, so a template that renders `update.date.isoformat()` gains a
time and offset; `strftime` output is unchanged.

### Changed — packaging

- `PyYAML>=6.0` is now a declared dependency. It was already installed through
  python-frontmatter, but oxie now imports `yaml` directly.
- A scaffolded site's `requirements.txt` pins `oxie==0.5.0` from PyPI instead
  of a git tag.
- A site that moves to the file no longer needs `oxie[sheets]`, so it can drop
  pandas and numpy from its install.

## 0.4.1 — date and time handling (2026-08-23)

Front matter dates are now normalised to timezone-aware datetimes as they are
read, instead of being passed through as whatever type YAML happened to
produce. This fixes four defects and **changes generated output once**; see the
migration note below.

### Fixed

- **A timezone-aware date no longer kills the build.** `Date: 2026-08-22
  09:30:00+01:00` reached `format_datetime(..., usegmt=True)`, which raises
  `ValueError: usegmt option requires a UTC datetime` for any offset but UTC.
  `rfc822_date()` now converts to UTC before formatting, so RSS `pubDate`
  stays in GMT whatever offset the author wrote.
- **Dates are no longer stamped midnight UTC.** A date-only entry became
  `00:00:00 GMT`, which every reader west of Greenwich rendered as the
  *previous day*. Date-only entries are now placed at `default_post_time`
  (noon) in the site timezone, which lands on the intended calendar day for
  every offset from UTC−12 to UTC+11.
- **Mixing dated and timed posts no longer raises `TypeError`.** One post with
  a time and another without meant comparing a `datetime.date` with a
  `datetime.datetime` while sorting, building the feed, or collecting sitemap
  entries. All dates are converted at the boundary — `Post.parse()` and
  `IndexPage.parse()` — so the comparison sites need no special cases.
- **The post sort no longer discards the time of day.** The old key ran
  `datetime.combine(post.date, datetime.min.time())`, which ignores the time
  and tzinfo of a datetime argument, so same-day posts sorted alphabetically
  by title regardless of when they were published. It also called
  `.timestamp()` on a naive datetime, resolving it against the *builder's*
  local timezone. Posts now sort on the datetime itself, with the title kept
  as a tie-break.
- `IndexPage.parse()` no longer falls back to `datetime.now()` for an
  `index.md` with no date, which put the build date into a rendered page and
  broke reproducibility. The date is `None` instead.
- `post_jsonld()` omits `datePublished`/`dateModified` for a post with no date
  rather than raising `AttributeError`, and `Post.last_modified` is
  initialised in `__init__`, so a post with malformed front matter no longer
  fails to render.

### Added

Two `SiteConfig` fields, both used only for reading front matter:

| Field | Default | Purpose |
|---|---|---|
| `timezone` | `'UTC'` | IANA name, resolved with `zoneinfo`. A date written without an offset is read in this zone. |
| `default_post_time` | `time(12, 0)` | Time of day given to a date-only entry. |

`SiteConfig.to_datetime()` performs the conversion and `SiteConfig.tzinfo`
resolves the zone. The UTC default is short-circuited, so an ordinary site
still needs no timezone database.

`seo.iso8601_date()` formats a datetime for Schema.org.

### Changed — output

**No front matter needs editing.** Existing date-only posts keep working; they
are simply read as noon rather than midnight. That does change three generated
outputs, once:

| Output | Before | After |
|---|---|---|
| `feed.xml` `pubDate`, `lastBuildDate` | `Fri, 17 Jul 2026 00:00:00 GMT` | `Fri, 17 Jul 2026 12:00:00 GMT` |
| JSON-LD `datePublished`, `dateModified` | `2026-07-17` | `2026-07-17T12:00:00+00:00` |
| `<time datetime="…">` in bundled templates | `2026-07-17` | `2026-07-17T12:00:00+00:00` |

`sitemap.xml` is unaffected: `<lastmod>` stays a `YYYY-MM-DD` calendar day.
Visible page text is unaffected — every bundled template renders dates through
`strftime`, and only the machine-readable attribute changed.

Feed readers key items on `<guid>`, which has not changed, so shifting
`pubDate` does not re-surface old posts as unread.

If a site's own templates interpolate a date bare — `{{ post.date }}` rather
than `{{ post.date.strftime(...) }}` or `{{ post.date.isoformat() }}` — that
now renders `2026-07-17 12:00:00+00:00`. The bundled templates were audited;
a site's own templates are its own to check.

### Changed — packaging

`requires-python` is now `>=3.9`, since `zoneinfo` is stdlib only from 3.9.
The old `>=3.8` claim was never exercised by CI. On Windows, `tzdata` is
pulled in, because the platform ships no timezone database.

## 0.4.0 — SEO and syndication

Sitemap, RSS feed, robots.txt, 404 page and inline JSON-LD, via the new
`oxie/seo.py`. Fixed three behaviours carried over from the original
`build.py`: category order on the blog index is sorted rather than
set-iteration order, `IndexPage` no longer overwrites `meta_data["title"]`,
and the home page description is no longer truncated to its first character.
