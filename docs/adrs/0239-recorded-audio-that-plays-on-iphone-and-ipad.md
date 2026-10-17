# ADR 0239: Recorded audio plays on iPhone and iPad only when the server answers byte ranges and the user's touch started the element

**Status:** Proposed
**Date:** 2026-10-17
**Deciders:** Operator
**Related:** #4168

---

## Decision

**A page that plays recorded audio meets two conditions, and every browser on iOS and iPadOS imposes both, because every one of them is WebKit underneath: Safari, Chrome, Firefox and the rest.**

1. **The server answers byte-range requests.** A request for an audio file carrying `Range: bytes=a-b` is answered `206 Partial Content`, with exactly those bytes, `Content-Range: bytes a-b/size` and the right `Content-Length`, and every answer for the file carries `Accept-Ranges: bytes`. A server that answers a range request with `200` and the whole file plays on a desktop browser and on no iPhone or iPad.
2. **Sound plays on an element the user's touch started.** The page keeps one `HTMLAudioElement` for its life. The first touch anywhere on the page plays a short silent clip on it, inside the touch handler itself, synchronously, before any `await`. Every later clip plays on that same element by changing its `src`. A new `Audio()` made after an `await` (a hash, a fetch, a lookup) was never started by a touch, and WebKit refuses it with `NotAllowedError`.

A refusal after the user has touched the page is shown to the user. It is never swallowed as "not a fault": that is how a page goes silent with nothing on the screen to say why.

## The Cloudflare case

On Cloudflare Workers with static assets, the asset server answers a range request for a static file with `200` and the whole file. So the Worker runs first for the audio paths (`assets.run_worker_first`, for example `["/packs/*"]`). It fetches the whole file from the `ASSETS` binding without the range, cuts the range from it, and answers `206`. A clip is a few hundred kilobytes, so this costs little. An unsatisfiable range answers `416` with `Content-Range: bytes */size`; a request for several ranges may be answered with the whole file, as RFC 9110 allows. Every other path still passes straight to the asset server.

A deploy that uploads static assets from one checkout and the Worker from another can ship the first half of this fix without the second. The check below is what catches that.

## How to verify

- **The range, mechanically:** `curl -s -D - -o /dev/null -H 'Range: bytes=0-1' <a real audio URL>` shows `206`, `content-range: bytes 0-1/<size>` and `accept-ranges: bytes`. Run it against the deployed origin after every deploy that touches serving. Before a deploy it can be run against `wrangler dev`.
- **The touch, on the device:** a play on a real iPhone or iPad, after one touch on the page.
- **Not a test of either:** a desktop browser suite. Desktop Chromium plays a `200` answer to a range request, and allows plays a touch never started, so a desktop suite passes while every iPad stays silent. A suite that counts plays should read the element's `src`, not `currentSrc`: on one shared element, `currentSrc` still names the previous clip when `play()` is called.

## Consequences

- One shared element plays one clip at a time, so a second clip replaces the first instead of playing over it.
- A product that has recordings does not fall back to the device's synthetic voice (`speechSynthesis`) in their place. A missing recording plays nothing and says so.
- The silent unlock clip is a `data:` URI; a test that counts plays leaves `data:` sources out.

## Provenance

On 2026-10-17 a fleet product's recorded audio played on every device except the operator's iPad, in Firefox and in Chrome. The first fix, one element unlocked by the first touch, was necessary but not enough. A `curl` with a `Range` header then showed production answering `200` and the whole file. The second fix, the Worker answering ranges, reached production only on a second deploy, because the first had uploaded the Worker from a different checkout than the assets. Desktop test suites passed throughout. The operator then asked for this ADR, so the knowledge is written down once.
