# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[semantic versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-09-17

First release.

### Added

- `Site`: one declaration of a site's crawlable surface, producing the per-URL
  `<head>`, the crawlable body, `robots.txt`, `sitemap.xml` and `llms.txt`.
- `render_shell`, `head_block`, `robots_txt`, `sitemap_xml`, `llms_txt` and
  `page_url` as plain functions, for use without `Site` or without FastAPI.
- `crawlableseo.integrations.fastapi.router`: the crawler-facing endpoints and
  the SPA catch-all as an `APIRouter`.
- `IndexNow`: submit changed URLs, and serve the key file that authorises it.
- `Page.index` and `Page.follow` as separate flags, so `noindex, follow` is
  expressible.
- `NotFound`, so a URL with no content answers 404 instead of a 200 with an
  empty screen.

[Unreleased]: https://github.com/kulykivska/crawlableseo/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/kulykivska/crawlableseo/releases/tag/v0.1.0
