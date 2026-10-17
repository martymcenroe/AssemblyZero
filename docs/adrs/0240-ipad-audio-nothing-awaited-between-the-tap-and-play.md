# ADR 0240: Recorded audio plays on an iPad when nothing is awaited between the tap and `play()`

**Status:** Accepted
**Date:** 2026-10-17
**Deciders:** Operator
**Supersedes:** ADR 0239
**Related:** #4170, #4168

---

## Decision

**On iOS and iPadOS, `HTMLMediaElement.play()` is called synchronously inside the handler of the user's tap. No `await`, no `.then`, no timer and no other promise hop lies between the tap and the call.** Everything `play()` needs, the clip's key and its URL among them, is computed synchronously in the handler.

This binds every browser on those devices, because every one of them is WebKit underneath: Safari, Chrome, Firefox and the rest.

- **The clip's key is computed synchronously.** Where clips are keyed by a hash of their text, the page hashes with a synchronous SHA-256 of the text's UTF-8 bytes, a few dozen lines of TypeScript tested equal to Node's `createHash`. It never awaits `crypto.subtle.digest`.
- **Each clip plays on a new element made with its URL:** `new Audio(url)`, then `play()`, with the previous clip's element paused first. No long-lived element, and no silent unlock clip.
- **A play no tap started may be refused.** A line spoken on arrival is an example, and so is a line queued after another. That is the platform's rule. It is not worked around with unlock tricks, and a refusal after the user has touched the page is shown to them where they are looking.

## What failed, and why

Three fixes were deployed to production for one silent iPad before this one, and each was wrong:

1. **Byte ranges** (ADR 0239's first claim). The server was changed to answer `Range` with `206`. It is harmless, and it was not the cause: the private predecessor, whose recordings played on the same iPad, answers every clip request with a plain `200` and supports no ranges.
2. **One element, unlocked on the first touch** (ADR 0239's second claim). One `HTMLAudioElement` was kept for the page's life, started on the first touch with a one-sample silent `data:` WAV, and each clip was swapped in by changing `src`. Still nothing played.
3. **The predecessor's player, copied exactly:** `new Audio(url)` per clip and `play()`. Still nothing, because the element was never the difference.

Two checks ruled out the server and the file in minutes. Run first, they would have saved the first fix:

- **The headers.** `curl -s -D - -o /dev/null -H 'Range: bytes=0-1' <clip>` gave the same content type and a correct answer on both products.
- **The file.** `xxd -l 48` of a clip from each product showed the same format: 24 kHz, mono, 16-bit PCM, and the same 44-byte header.

## The cause

What differed was **when `play()` ran**:

- **The predecessor** called `crypto.subtle.digest(...)` inside the tap, and called `new Audio(url).play()` in that promise's own `.then` callback.
- **The failing product** awaited an async helper that awaited the digest, then looked up its manifest, then called `play()`: two promise hops after the tap.

WebKit on iOS starts media only inside the user's gesture. It carried the gesture into the predecessor's direct callback, but not through the extra hops, and refused the play with `NotAllowedError`.

Android Chrome and desktop Chromium never show this. Once a page has been touched, they grant it sticky user activation, and any later play is allowed. That is why the product's whole Playwright suite passed while every iPad stayed silent, and why no desktop or Android suite can catch it.

The refusal was also invisible. The product announced blocked sound in small grey text at the foot of a page that, with character portraits, ran far past the iPad's screen. The operator reported "absolutely nothing happens", which was true of everything he could see.

## How to diagnose it next time

In this order:

1. **When one implementation plays on the device and another does not, diff the two at the moment of `play()`.** Ask what runs between the tap and the call, before any theory about servers, headers, codecs or unlock tricks. Port the working one's path exactly.
2. **On iOS, check the gesture chain first.** Is `play()` reached synchronously from the handler? Read every `await` and `.then` on the way. One is enough to lose the gesture.
3. **Check the server and the file once, cheaply, and drop them if they match the working one.** Use the `curl` with a `Range` header and the `xxd` of the WAV header above. Neither is a reason to keep digging when it matches.
4. **Show a refusal where the user is looking.** A notice far from the tapped control is silence on a long page.
5. **The person's device test is the acceptance test.** Desktop Chromium, Android Chrome and Playwright cannot reproduce this. Ask for the device test only after a unit test proves the chain from the tap to `play()` is synchronous.

## Tests that hold it

- **A tap reaches `play()` before the click returns.** For a speak control and for a reply button, the test calls `element.click()` and asserts on the next line, with no `await`, that the player's `playFile` was called. Both tests were proven to catch the defect: putting one `await Promise.resolve(...)` back before the lookup made exactly those two fail.
- **The synchronous hash equals Node's** `createHash('sha256')`. The cases are the empty string, `abc`, 55, 56, 64 and 1,000 bytes, and two-, three- and four-byte UTF-8, plus the published vector for `abc`.
- **Tests that leaned on the gap.** Closing an async gap surfaces tests that passed only because of it. In this case, a test read the notice state right after an action and expected it empty, while the action was still pending. Fix such a test with the right fixture, here a pack in which every line has a recording, and add the case it hid. Never restore the gap.

## Consequences

- Clip keys computed in the browser are synchronous. A hash that would be too slow to compute synchronously is precomputed before the tap: as a map ready at load, or as a key carried on the control itself.
- A test double for the hash replaces any stub of `crypto.subtle.digest`. It is an object whose method a test can stub, as the player is.
- ADR 0239's server change may stay, since byte ranges are correct HTTP and cost little, but it is no longer the fix.

## Provenance

On 2026-10-17 a private product's recordings were silent on the operator's iPad, in Firefox and then in Chrome. They played on Android Chrome and on desktop, and its private predecessor played its own recordings on the same iPad in the same browser. Three fixes reached production, and the iPad stayed silent after each. The fourth made the path from the tap to `play()` synchronous, and the operator confirmed on the device that it plays. He then ordered this ADR, so the answer and the way to find it are written down once.
