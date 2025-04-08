## Changelog

**v1.7.0...main**

### Bug Fixes

*   **(js-sdk):** Fixed import issues related to `isows`. Removed `isows` dependency as native websocket support is available in Node.js 21 and later. (FIR-1586) (FIR-1536) (#1411)
*   **(rust-sdk):** Removed `rustfmt` due to deprecation and dependency on an outdated `extprim` crate, which caused test failures. (#1392)
*   **(unvisitedUrls):** Filter unvisited URLs with the crawler. Fixes #1410
*   **(llmExtract):** Fixed an issue where arbitrary objects caused errors in `llmExtract`.

### Other

*   Send notifications for crawl and batch scrape events.
*   Updated rate limiter.
*   Queue jobs and worker service updates.