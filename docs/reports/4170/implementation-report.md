# Implementation Report — Issue #4170

`docs/adrs/0240-ipad-audio-nothing-awaited-between-the-tap-and-play.md` is new, with Status Accepted. It decides that on iOS and iPadOS `play()` is called synchronously inside the tap's handler, with everything it needs computed synchronously. It records the three fixes that failed on a real iPad and why, the cause, the order in which to diagnose it next time, and the tests that hold it.

`docs/adrs/0239-recorded-audio-that-plays-on-iphone-and-ipad.md` changes only its Status line, which now says it is superseded by ADR 0240 and that neither of its two conditions made a clip play.

Neither file names a private repository, product, domain or issue. No other file changed.
