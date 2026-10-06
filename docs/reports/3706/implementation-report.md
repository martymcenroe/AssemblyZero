# Implementation Report: N4.5 halts when the build hook fails (#3706)

Landed in the same PR as #3705; the full report is `docs/reports/3705/implementation-report.md`. The #3706 part: a non-zero hook exit, an unreadable `.unleashed.json` or a hook that cannot start sets `error_message`, `route_after_mechanical_hooks` sends the run to HALT, both `# fail-open:` tags are removed, the atlas names the HALT successor, and the gate registry carries row `impl.build_hook_failed` with the ratchet baseline raised by one in the same PR under the operator's rule of 2026-09-25 (#3585).
