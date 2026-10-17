# Implementation Report — Issue #4168

`docs/adrs/0239-recorded-audio-that-plays-on-iphone-and-ipad.md` is new, with Status Proposed. It states the two conditions WebKit imposes on every browser on iOS and iPadOS. First, the server answers byte-range requests with `206`. Second, sound plays on one element that the user's touch started, inside the touch. The ADR then covers the Cloudflare Workers static-assets case, how to verify each condition, its consequences, and its provenance. It names no private repository. No other file changed.
