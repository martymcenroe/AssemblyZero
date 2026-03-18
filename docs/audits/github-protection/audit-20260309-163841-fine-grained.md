# GitHub Protection Audit Report

**Date:** 2026-03-09T16:38:41.824662+00:00
**Token type:** fine-grained
**Mode(s):** probe
**Repos scanned:** 50

**Repositories:**
- `martymcenroe/dispatch`
- `martymcenroe/AssemblyZero`
- `martymcenroe/yt-playlist-importer`
- `martymcenroe/unleashed`
- `martymcenroe/TxDOT-LDA`
- `martymcenroe/thrivetech-ai`
- `martymcenroe/TheMobyPerogative.world`
- `martymcenroe/spotify-personal-backups`
- `martymcenroe/sentinel-rfc`
- `martymcenroe/sentinel`
- `martymcenroe/RCA-PDF-extraction-pipeline`
- `martymcenroe/prompt-stream`
- `martymcenroe/power-agent.github.io`
- `martymcenroe/nec2017-analyzer`
- `martymcenroe/neatworks-file-recovery`
- `martymcenroe/mySvelte`
- `martymcenroe/my-discussions`
- `martymcenroe/my_hackerrank_SQL`
- `martymcenroe/my_hackerrank_python`
- `martymcenroe/metabolic-protocols`
- `martymcenroe/martymcenroe.github.io`
- `martymcenroe/martymcenroe`
- `martymcenroe/maintenance`
- `martymcenroe/job-sniper`
- `martymcenroe/IEEE-standards`
- `martymcenroe/iconoscope`
- `martymcenroe/HermesWiki`
- `martymcenroe/GlucoPulse`
- `martymcenroe/github-readme-stats`
- `martymcenroe/gh-link-auditor`
- `martymcenroe/GentlePersuader`
- `martymcenroe/electric-nexus`
- `martymcenroe/dotfiles`
- `martymcenroe/dont-stop-now`
- `martymcenroe/data-harvest`
- `martymcenroe/CS512_link_predictor`
- `martymcenroe/collectibricks`
- `martymcenroe/Clio`
- `martymcenroe/career`
- `martymcenroe/best-of-pes-ai`
- `martymcenroe/automation-scripts`
- `martymcenroe/athleet.github.io`
- `martymcenroe/athleet.dev`
- `martymcenroe/ai-power-systems-compendium`
- `martymcenroe/Agora`
- `martymcenroe/acpb-manifest-poc`
- `martymcenroe/Hermes`
- `martymcenroe/Aletheia`
- `martymcenroe/Talos`
- `martymcenroe/hermes-docs`

---

## Probe Summary

| Verdict | Count |
|---------|-------|
| PROTECTED | 930 |
| VULNERABLE | 90 |
| INFORMATIONAL | 669 |

### Category: Reconnaissance

| Probe | Repo | Method | Endpoint | HTTP | Verdict | ATT&CK | Detail |
|-------|------|--------|----------|------|---------|--------|--------|
| P01 | martymcenroe/dispatch | GET | `.../martymcenroe/dispatch/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/dispatch | GET | `/repos/martymcenroe/dispatch/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/dispatch | GET | `...artymcenroe/dispatch/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/dispatch | GET | `/repos/martymcenroe/dispatch/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/dispatch | GET | `/repos/martymcenroe/dispatch/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/dispatch | GET | `/repos/martymcenroe/dispatch/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/dispatch | GET | `/repos/martymcenroe/dispatch` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/dispatch | GET | `/repos/martymcenroe/dispatch/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/dispatch | GET | `/repos/martymcenroe/dispatch/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/AssemblyZero | GET | `...tymcenroe/AssemblyZero/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/AssemblyZero | GET | `/repos/martymcenroe/AssemblyZero/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/AssemblyZero | GET | `...mcenroe/AssemblyZero/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/AssemblyZero | GET | `/repos/martymcenroe/AssemblyZero/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/AssemblyZero | GET | `/repos/martymcenroe/AssemblyZero/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/AssemblyZero | GET | `.../martymcenroe/AssemblyZero/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/AssemblyZero | GET | `/repos/martymcenroe/AssemblyZero` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/AssemblyZero | GET | `/repos/martymcenroe/AssemblyZero/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/AssemblyZero | GET | `/repos/martymcenroe/AssemblyZero/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/yt-playlist-importer | GET | `...e/yt-playlist-importer/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/yt-playlist-importer | GET | `...rtymcenroe/yt-playlist-importer/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/yt-playlist-importer | GET | `...yt-playlist-importer/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/yt-playlist-importer | GET | `/repos/martymcenroe/yt-playlist-importer/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/yt-playlist-importer | GET | `.../martymcenroe/yt-playlist-importer/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/yt-playlist-importer | GET | `...enroe/yt-playlist-importer/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/yt-playlist-importer | GET | `/repos/martymcenroe/yt-playlist-importer` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/yt-playlist-importer | GET | `...martymcenroe/yt-playlist-importer/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/yt-playlist-importer | GET | `...rtymcenroe/yt-playlist-importer/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/unleashed | GET | `...martymcenroe/unleashed/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/unleashed | GET | `/repos/martymcenroe/unleashed/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/unleashed | GET | `...rtymcenroe/unleashed/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/unleashed | GET | `/repos/martymcenroe/unleashed/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/unleashed | GET | `/repos/martymcenroe/unleashed/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/unleashed | GET | `/repos/martymcenroe/unleashed/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/unleashed | GET | `/repos/martymcenroe/unleashed` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/unleashed | GET | `/repos/martymcenroe/unleashed/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/unleashed | GET | `/repos/martymcenroe/unleashed/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/TxDOT-LDA | GET | `...martymcenroe/TxDOT-LDA/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/TxDOT-LDA | GET | `/repos/martymcenroe/TxDOT-LDA/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/TxDOT-LDA | GET | `...rtymcenroe/TxDOT-LDA/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/TxDOT-LDA | GET | `/repos/martymcenroe/TxDOT-LDA/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/TxDOT-LDA | GET | `/repos/martymcenroe/TxDOT-LDA/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/TxDOT-LDA | GET | `/repos/martymcenroe/TxDOT-LDA/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/TxDOT-LDA | GET | `/repos/martymcenroe/TxDOT-LDA` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/TxDOT-LDA | GET | `/repos/martymcenroe/TxDOT-LDA/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/TxDOT-LDA | GET | `/repos/martymcenroe/TxDOT-LDA/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/thrivetech-ai | GET | `...ymcenroe/thrivetech-ai/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/thrivetech-ai | GET | `/repos/martymcenroe/thrivetech-ai/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/thrivetech-ai | GET | `...cenroe/thrivetech-ai/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/thrivetech-ai | GET | `/repos/martymcenroe/thrivetech-ai/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/thrivetech-ai | GET | `/repos/martymcenroe/thrivetech-ai/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/thrivetech-ai | GET | `...martymcenroe/thrivetech-ai/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/thrivetech-ai | GET | `/repos/martymcenroe/thrivetech-ai` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/thrivetech-ai | GET | `/repos/martymcenroe/thrivetech-ai/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/thrivetech-ai | GET | `/repos/martymcenroe/thrivetech-ai/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/TheMobyPerogative.world | GET | `...heMobyPerogative.world/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/TheMobyPerogative.world | GET | `...mcenroe/TheMobyPerogative.world/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/TheMobyPerogative.world | GET | `...MobyPerogative.world/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/TheMobyPerogative.world | GET | `/repos/martymcenroe/TheMobyPerogative.world/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/TheMobyPerogative.world | GET | `...rtymcenroe/TheMobyPerogative.world/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/TheMobyPerogative.world | GET | `...oe/TheMobyPerogative.world/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/TheMobyPerogative.world | GET | `/repos/martymcenroe/TheMobyPerogative.world` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/TheMobyPerogative.world | GET | `...tymcenroe/TheMobyPerogative.world/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/TheMobyPerogative.world | GET | `...mcenroe/TheMobyPerogative.world/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/spotify-personal-backups | GET | `...otify-personal-backups/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/spotify-personal-backups | GET | `...cenroe/spotify-personal-backups/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/spotify-personal-backups | GET | `...ify-personal-backups/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/spotify-personal-backups | GET | `/repos/martymcenroe/spotify-personal-backups/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/spotify-personal-backups | GET | `...tymcenroe/spotify-personal-backups/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/spotify-personal-backups | GET | `...e/spotify-personal-backups/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/spotify-personal-backups | GET | `/repos/martymcenroe/spotify-personal-backups` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/spotify-personal-backups | GET | `...ymcenroe/spotify-personal-backups/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/spotify-personal-backups | GET | `...cenroe/spotify-personal-backups/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/sentinel-rfc | GET | `...tymcenroe/sentinel-rfc/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/sentinel-rfc | GET | `/repos/martymcenroe/sentinel-rfc/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/sentinel-rfc | GET | `...mcenroe/sentinel-rfc/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/sentinel-rfc | GET | `/repos/martymcenroe/sentinel-rfc/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/sentinel-rfc | GET | `/repos/martymcenroe/sentinel-rfc/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/sentinel-rfc | GET | `.../martymcenroe/sentinel-rfc/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/sentinel-rfc | GET | `/repos/martymcenroe/sentinel-rfc` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/sentinel-rfc | GET | `/repos/martymcenroe/sentinel-rfc/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/sentinel-rfc | GET | `/repos/martymcenroe/sentinel-rfc/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/sentinel | GET | `.../martymcenroe/sentinel/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/sentinel | GET | `/repos/martymcenroe/sentinel/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/sentinel | GET | `...artymcenroe/sentinel/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/sentinel | GET | `/repos/martymcenroe/sentinel/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/sentinel | GET | `/repos/martymcenroe/sentinel/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/sentinel | GET | `/repos/martymcenroe/sentinel/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/sentinel | GET | `/repos/martymcenroe/sentinel` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/sentinel | GET | `/repos/martymcenroe/sentinel/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/sentinel | GET | `/repos/martymcenroe/sentinel/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/RCA-PDF-extraction-pipeline | GET | `...DF-extraction-pipeline/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/RCA-PDF-extraction-pipeline | GET | `...roe/RCA-PDF-extraction-pipeline/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/RCA-PDF-extraction-pipeline | GET | `...-extraction-pipeline/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/RCA-PDF-extraction-pipeline | GET | `.../martymcenroe/RCA-PDF-extraction-pipeline/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/RCA-PDF-extraction-pipeline | GET | `...cenroe/RCA-PDF-extraction-pipeline/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/RCA-PDF-extraction-pipeline | GET | `...CA-PDF-extraction-pipeline/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/RCA-PDF-extraction-pipeline | GET | `/repos/martymcenroe/RCA-PDF-extraction-pipeline` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/RCA-PDF-extraction-pipeline | GET | `...enroe/RCA-PDF-extraction-pipeline/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/RCA-PDF-extraction-pipeline | GET | `...roe/RCA-PDF-extraction-pipeline/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/prompt-stream | GET | `...ymcenroe/prompt-stream/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/prompt-stream | GET | `/repos/martymcenroe/prompt-stream/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/prompt-stream | GET | `...cenroe/prompt-stream/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/prompt-stream | GET | `/repos/martymcenroe/prompt-stream/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/prompt-stream | GET | `/repos/martymcenroe/prompt-stream/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/prompt-stream | GET | `...martymcenroe/prompt-stream/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/prompt-stream | GET | `/repos/martymcenroe/prompt-stream` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/prompt-stream | GET | `/repos/martymcenroe/prompt-stream/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/prompt-stream | GET | `/repos/martymcenroe/prompt-stream/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/power-agent.github.io | GET | `.../power-agent.github.io/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/power-agent.github.io | GET | `...tymcenroe/power-agent.github.io/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/power-agent.github.io | GET | `...ower-agent.github.io/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/power-agent.github.io | GET | `/repos/martymcenroe/power-agent.github.io/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/power-agent.github.io | GET | `...martymcenroe/power-agent.github.io/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/power-agent.github.io | GET | `...nroe/power-agent.github.io/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/power-agent.github.io | GET | `/repos/martymcenroe/power-agent.github.io` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/power-agent.github.io | GET | `...artymcenroe/power-agent.github.io/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/power-agent.github.io | GET | `...tymcenroe/power-agent.github.io/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/nec2017-analyzer | GET | `...enroe/nec2017-analyzer/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/nec2017-analyzer | GET | `...s/martymcenroe/nec2017-analyzer/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/nec2017-analyzer | GET | `...roe/nec2017-analyzer/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/nec2017-analyzer | GET | `/repos/martymcenroe/nec2017-analyzer/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/nec2017-analyzer | GET | `/repos/martymcenroe/nec2017-analyzer/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/nec2017-analyzer | GET | `...tymcenroe/nec2017-analyzer/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/nec2017-analyzer | GET | `/repos/martymcenroe/nec2017-analyzer` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/nec2017-analyzer | GET | `/repos/martymcenroe/nec2017-analyzer/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/nec2017-analyzer | GET | `...s/martymcenroe/nec2017-analyzer/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/neatworks-file-recovery | GET | `...eatworks-file-recovery/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/neatworks-file-recovery | GET | `...mcenroe/neatworks-file-recovery/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/neatworks-file-recovery | GET | `...tworks-file-recovery/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/neatworks-file-recovery | GET | `/repos/martymcenroe/neatworks-file-recovery/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/neatworks-file-recovery | GET | `...rtymcenroe/neatworks-file-recovery/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/neatworks-file-recovery | GET | `...oe/neatworks-file-recovery/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/neatworks-file-recovery | GET | `/repos/martymcenroe/neatworks-file-recovery` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/neatworks-file-recovery | GET | `...tymcenroe/neatworks-file-recovery/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/neatworks-file-recovery | GET | `...mcenroe/neatworks-file-recovery/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/mySvelte | GET | `.../martymcenroe/mySvelte/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/mySvelte | GET | `/repos/martymcenroe/mySvelte/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/mySvelte | GET | `...artymcenroe/mySvelte/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/mySvelte | GET | `/repos/martymcenroe/mySvelte/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/mySvelte | GET | `/repos/martymcenroe/mySvelte/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/mySvelte | GET | `/repos/martymcenroe/mySvelte/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/mySvelte | GET | `/repos/martymcenroe/mySvelte` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/mySvelte | GET | `/repos/martymcenroe/mySvelte/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/mySvelte | GET | `/repos/martymcenroe/mySvelte/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/my-discussions | GET | `...mcenroe/my-discussions/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/my-discussions | GET | `/repos/martymcenroe/my-discussions/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/my-discussions | GET | `...enroe/my-discussions/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/my-discussions | GET | `/repos/martymcenroe/my-discussions/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/my-discussions | GET | `/repos/martymcenroe/my-discussions/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/my-discussions | GET | `...artymcenroe/my-discussions/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/my-discussions | GET | `/repos/martymcenroe/my-discussions` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/my-discussions | GET | `/repos/martymcenroe/my-discussions/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/my-discussions | GET | `/repos/martymcenroe/my-discussions/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/my_hackerrank_SQL | GET | `...nroe/my_hackerrank_SQL/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/my_hackerrank_SQL | GET | `.../martymcenroe/my_hackerrank_SQL/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/my_hackerrank_SQL | GET | `...oe/my_hackerrank_SQL/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/my_hackerrank_SQL | GET | `/repos/martymcenroe/my_hackerrank_SQL/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/my_hackerrank_SQL | GET | `/repos/martymcenroe/my_hackerrank_SQL/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/my_hackerrank_SQL | GET | `...ymcenroe/my_hackerrank_SQL/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/my_hackerrank_SQL | GET | `/repos/martymcenroe/my_hackerrank_SQL` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/my_hackerrank_SQL | GET | `...os/martymcenroe/my_hackerrank_SQL/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/my_hackerrank_SQL | GET | `.../martymcenroe/my_hackerrank_SQL/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/my_hackerrank_python | GET | `...e/my_hackerrank_python/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/my_hackerrank_python | GET | `...rtymcenroe/my_hackerrank_python/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/my_hackerrank_python | GET | `...my_hackerrank_python/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/my_hackerrank_python | GET | `/repos/martymcenroe/my_hackerrank_python/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/my_hackerrank_python | GET | `.../martymcenroe/my_hackerrank_python/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/my_hackerrank_python | GET | `...enroe/my_hackerrank_python/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/my_hackerrank_python | GET | `/repos/martymcenroe/my_hackerrank_python` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/my_hackerrank_python | GET | `...martymcenroe/my_hackerrank_python/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/my_hackerrank_python | GET | `...rtymcenroe/my_hackerrank_python/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/metabolic-protocols | GET | `...oe/metabolic-protocols/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/metabolic-protocols | GET | `...artymcenroe/metabolic-protocols/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/metabolic-protocols | GET | `.../metabolic-protocols/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/metabolic-protocols | GET | `/repos/martymcenroe/metabolic-protocols/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/metabolic-protocols | GET | `...s/martymcenroe/metabolic-protocols/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/metabolic-protocols | GET | `...cenroe/metabolic-protocols/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/metabolic-protocols | GET | `/repos/martymcenroe/metabolic-protocols` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/metabolic-protocols | GET | `.../martymcenroe/metabolic-protocols/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/metabolic-protocols | GET | `...artymcenroe/metabolic-protocols/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/martymcenroe.github.io | GET | `...martymcenroe.github.io/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/martymcenroe.github.io | GET | `...ymcenroe/martymcenroe.github.io/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/martymcenroe.github.io | GET | `...rtymcenroe.github.io/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/martymcenroe.github.io | GET | `/repos/martymcenroe/martymcenroe.github.io/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/martymcenroe.github.io | GET | `...artymcenroe/martymcenroe.github.io/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/martymcenroe.github.io | GET | `...roe/martymcenroe.github.io/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/martymcenroe.github.io | GET | `/repos/martymcenroe/martymcenroe.github.io` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/martymcenroe.github.io | GET | `...rtymcenroe/martymcenroe.github.io/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/martymcenroe.github.io | GET | `...ymcenroe/martymcenroe.github.io/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/martymcenroe | GET | `...tymcenroe/martymcenroe/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/martymcenroe | GET | `/repos/martymcenroe/martymcenroe/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/martymcenroe | GET | `...mcenroe/martymcenroe/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/martymcenroe | GET | `/repos/martymcenroe/martymcenroe/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/martymcenroe | GET | `/repos/martymcenroe/martymcenroe/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/martymcenroe | GET | `.../martymcenroe/martymcenroe/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/martymcenroe | GET | `/repos/martymcenroe/martymcenroe` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/martymcenroe | GET | `/repos/martymcenroe/martymcenroe/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/martymcenroe | GET | `/repos/martymcenroe/martymcenroe/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/maintenance | GET | `...rtymcenroe/maintenance/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/maintenance | GET | `/repos/martymcenroe/maintenance/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/maintenance | GET | `...ymcenroe/maintenance/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/maintenance | GET | `/repos/martymcenroe/maintenance/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/maintenance | GET | `/repos/martymcenroe/maintenance/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/maintenance | GET | `...s/martymcenroe/maintenance/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/maintenance | GET | `/repos/martymcenroe/maintenance` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/maintenance | GET | `/repos/martymcenroe/maintenance/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/maintenance | GET | `/repos/martymcenroe/maintenance/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/job-sniper | GET | `...artymcenroe/job-sniper/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/job-sniper | GET | `/repos/martymcenroe/job-sniper/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/job-sniper | GET | `...tymcenroe/job-sniper/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/job-sniper | GET | `/repos/martymcenroe/job-sniper/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/job-sniper | GET | `/repos/martymcenroe/job-sniper/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/job-sniper | GET | `...os/martymcenroe/job-sniper/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/job-sniper | GET | `/repos/martymcenroe/job-sniper` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/job-sniper | GET | `/repos/martymcenroe/job-sniper/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/job-sniper | GET | `/repos/martymcenroe/job-sniper/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/IEEE-standards | GET | `...mcenroe/IEEE-standards/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/IEEE-standards | GET | `/repos/martymcenroe/IEEE-standards/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/IEEE-standards | GET | `...enroe/IEEE-standards/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/IEEE-standards | GET | `/repos/martymcenroe/IEEE-standards/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/IEEE-standards | GET | `/repos/martymcenroe/IEEE-standards/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/IEEE-standards | GET | `...artymcenroe/IEEE-standards/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/IEEE-standards | GET | `/repos/martymcenroe/IEEE-standards` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/IEEE-standards | GET | `/repos/martymcenroe/IEEE-standards/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/IEEE-standards | GET | `/repos/martymcenroe/IEEE-standards/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/iconoscope | GET | `...artymcenroe/iconoscope/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/iconoscope | GET | `/repos/martymcenroe/iconoscope/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/iconoscope | GET | `...tymcenroe/iconoscope/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/iconoscope | GET | `/repos/martymcenroe/iconoscope/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/iconoscope | GET | `/repos/martymcenroe/iconoscope/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/iconoscope | GET | `...os/martymcenroe/iconoscope/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/iconoscope | GET | `/repos/martymcenroe/iconoscope` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/iconoscope | GET | `/repos/martymcenroe/iconoscope/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/iconoscope | GET | `/repos/martymcenroe/iconoscope/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/HermesWiki | GET | `...artymcenroe/HermesWiki/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/HermesWiki | GET | `/repos/martymcenroe/HermesWiki/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/HermesWiki | GET | `...tymcenroe/HermesWiki/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/HermesWiki | GET | `/repos/martymcenroe/HermesWiki/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/HermesWiki | GET | `/repos/martymcenroe/HermesWiki/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/HermesWiki | GET | `...os/martymcenroe/HermesWiki/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/HermesWiki | GET | `/repos/martymcenroe/HermesWiki` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/HermesWiki | GET | `/repos/martymcenroe/HermesWiki/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/HermesWiki | GET | `/repos/martymcenroe/HermesWiki/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/GlucoPulse | GET | `...artymcenroe/GlucoPulse/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/GlucoPulse | GET | `/repos/martymcenroe/GlucoPulse/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/GlucoPulse | GET | `...tymcenroe/GlucoPulse/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/GlucoPulse | GET | `/repos/martymcenroe/GlucoPulse/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/GlucoPulse | GET | `/repos/martymcenroe/GlucoPulse/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/GlucoPulse | GET | `...os/martymcenroe/GlucoPulse/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/GlucoPulse | GET | `/repos/martymcenroe/GlucoPulse` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/GlucoPulse | GET | `/repos/martymcenroe/GlucoPulse/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/GlucoPulse | GET | `/repos/martymcenroe/GlucoPulse/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/github-readme-stats | GET | `...oe/github-readme-stats/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/github-readme-stats | GET | `...artymcenroe/github-readme-stats/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/github-readme-stats | GET | `.../github-readme-stats/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/github-readme-stats | GET | `/repos/martymcenroe/github-readme-stats/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/github-readme-stats | GET | `...s/martymcenroe/github-readme-stats/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/github-readme-stats | GET | `...cenroe/github-readme-stats/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/github-readme-stats | GET | `/repos/martymcenroe/github-readme-stats` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/github-readme-stats | GET | `.../martymcenroe/github-readme-stats/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/github-readme-stats | GET | `...artymcenroe/github-readme-stats/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/gh-link-auditor | GET | `...cenroe/gh-link-auditor/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/gh-link-auditor | GET | `...os/martymcenroe/gh-link-auditor/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/gh-link-auditor | GET | `...nroe/gh-link-auditor/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/gh-link-auditor | GET | `/repos/martymcenroe/gh-link-auditor/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/gh-link-auditor | GET | `/repos/martymcenroe/gh-link-auditor/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/gh-link-auditor | GET | `...rtymcenroe/gh-link-auditor/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/gh-link-auditor | GET | `/repos/martymcenroe/gh-link-auditor` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/gh-link-auditor | GET | `/repos/martymcenroe/gh-link-auditor/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/gh-link-auditor | GET | `...os/martymcenroe/gh-link-auditor/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/GentlePersuader | GET | `...cenroe/GentlePersuader/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/GentlePersuader | GET | `...os/martymcenroe/GentlePersuader/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/GentlePersuader | GET | `...nroe/GentlePersuader/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/GentlePersuader | GET | `/repos/martymcenroe/GentlePersuader/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/GentlePersuader | GET | `/repos/martymcenroe/GentlePersuader/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/GentlePersuader | GET | `...rtymcenroe/GentlePersuader/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/GentlePersuader | GET | `/repos/martymcenroe/GentlePersuader` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/GentlePersuader | GET | `/repos/martymcenroe/GentlePersuader/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/GentlePersuader | GET | `...os/martymcenroe/GentlePersuader/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/electric-nexus | GET | `...mcenroe/electric-nexus/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/electric-nexus | GET | `/repos/martymcenroe/electric-nexus/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/electric-nexus | GET | `...enroe/electric-nexus/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/electric-nexus | GET | `/repos/martymcenroe/electric-nexus/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/electric-nexus | GET | `/repos/martymcenroe/electric-nexus/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/electric-nexus | GET | `...artymcenroe/electric-nexus/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/electric-nexus | GET | `/repos/martymcenroe/electric-nexus` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/electric-nexus | GET | `/repos/martymcenroe/electric-nexus/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/electric-nexus | GET | `/repos/martymcenroe/electric-nexus/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/dotfiles | GET | `.../martymcenroe/dotfiles/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/dotfiles | GET | `/repos/martymcenroe/dotfiles/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/dotfiles | GET | `...artymcenroe/dotfiles/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/dotfiles | GET | `/repos/martymcenroe/dotfiles/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/dotfiles | GET | `/repos/martymcenroe/dotfiles/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/dotfiles | GET | `/repos/martymcenroe/dotfiles/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/dotfiles | GET | `/repos/martymcenroe/dotfiles` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/dotfiles | GET | `/repos/martymcenroe/dotfiles/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/dotfiles | GET | `/repos/martymcenroe/dotfiles/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/dont-stop-now | GET | `...ymcenroe/dont-stop-now/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/dont-stop-now | GET | `/repos/martymcenroe/dont-stop-now/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/dont-stop-now | GET | `...cenroe/dont-stop-now/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/dont-stop-now | GET | `/repos/martymcenroe/dont-stop-now/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/dont-stop-now | GET | `/repos/martymcenroe/dont-stop-now/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/dont-stop-now | GET | `...martymcenroe/dont-stop-now/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/dont-stop-now | GET | `/repos/martymcenroe/dont-stop-now` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/dont-stop-now | GET | `/repos/martymcenroe/dont-stop-now/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/dont-stop-now | GET | `/repos/martymcenroe/dont-stop-now/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/data-harvest | GET | `...tymcenroe/data-harvest/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/data-harvest | GET | `/repos/martymcenroe/data-harvest/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/data-harvest | GET | `...mcenroe/data-harvest/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/data-harvest | GET | `/repos/martymcenroe/data-harvest/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/data-harvest | GET | `/repos/martymcenroe/data-harvest/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/data-harvest | GET | `.../martymcenroe/data-harvest/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/data-harvest | GET | `/repos/martymcenroe/data-harvest` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/data-harvest | GET | `/repos/martymcenroe/data-harvest/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/data-harvest | GET | `/repos/martymcenroe/data-harvest/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/CS512_link_predictor | GET | `...e/CS512_link_predictor/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/CS512_link_predictor | GET | `...rtymcenroe/CS512_link_predictor/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/CS512_link_predictor | GET | `...CS512_link_predictor/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/CS512_link_predictor | GET | `/repos/martymcenroe/CS512_link_predictor/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/CS512_link_predictor | GET | `.../martymcenroe/CS512_link_predictor/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/CS512_link_predictor | GET | `...enroe/CS512_link_predictor/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/CS512_link_predictor | GET | `/repos/martymcenroe/CS512_link_predictor` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/CS512_link_predictor | GET | `...martymcenroe/CS512_link_predictor/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/CS512_link_predictor | GET | `...rtymcenroe/CS512_link_predictor/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/collectibricks | GET | `...mcenroe/collectibricks/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/collectibricks | GET | `/repos/martymcenroe/collectibricks/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/collectibricks | GET | `...enroe/collectibricks/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/collectibricks | GET | `/repos/martymcenroe/collectibricks/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/collectibricks | GET | `/repos/martymcenroe/collectibricks/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/collectibricks | GET | `...artymcenroe/collectibricks/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/collectibricks | GET | `/repos/martymcenroe/collectibricks` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/collectibricks | GET | `/repos/martymcenroe/collectibricks/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/collectibricks | GET | `/repos/martymcenroe/collectibricks/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/Clio | GET | `/repos/martymcenroe/Clio/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/Clio | GET | `/repos/martymcenroe/Clio/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/Clio | GET | `...os/martymcenroe/Clio/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/Clio | GET | `/repos/martymcenroe/Clio/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/Clio | GET | `/repos/martymcenroe/Clio/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/Clio | GET | `/repos/martymcenroe/Clio/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/Clio | GET | `/repos/martymcenroe/Clio` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/Clio | GET | `/repos/martymcenroe/Clio/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/Clio | GET | `/repos/martymcenroe/Clio/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/career | GET | `...os/martymcenroe/career/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/career | GET | `/repos/martymcenroe/career/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/career | GET | `.../martymcenroe/career/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/career | GET | `/repos/martymcenroe/career/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/career | GET | `/repos/martymcenroe/career/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/career | GET | `/repos/martymcenroe/career/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/career | GET | `/repos/martymcenroe/career` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/career | GET | `/repos/martymcenroe/career/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/career | GET | `/repos/martymcenroe/career/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/best-of-pes-ai | GET | `...mcenroe/best-of-pes-ai/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/best-of-pes-ai | GET | `/repos/martymcenroe/best-of-pes-ai/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/best-of-pes-ai | GET | `...enroe/best-of-pes-ai/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/best-of-pes-ai | GET | `/repos/martymcenroe/best-of-pes-ai/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/best-of-pes-ai | GET | `/repos/martymcenroe/best-of-pes-ai/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/best-of-pes-ai | GET | `...artymcenroe/best-of-pes-ai/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/best-of-pes-ai | GET | `/repos/martymcenroe/best-of-pes-ai` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/best-of-pes-ai | GET | `/repos/martymcenroe/best-of-pes-ai/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/best-of-pes-ai | GET | `/repos/martymcenroe/best-of-pes-ai/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/automation-scripts | GET | `...roe/automation-scripts/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/automation-scripts | GET | `...martymcenroe/automation-scripts/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/automation-scripts | GET | `...e/automation-scripts/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/automation-scripts | GET | `/repos/martymcenroe/automation-scripts/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/automation-scripts | GET | `...os/martymcenroe/automation-scripts/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/automation-scripts | GET | `...mcenroe/automation-scripts/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/automation-scripts | GET | `/repos/martymcenroe/automation-scripts` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/automation-scripts | GET | `...s/martymcenroe/automation-scripts/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/automation-scripts | GET | `...martymcenroe/automation-scripts/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/athleet.github.io | GET | `...nroe/athleet.github.io/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/athleet.github.io | GET | `.../martymcenroe/athleet.github.io/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/athleet.github.io | GET | `...oe/athleet.github.io/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/athleet.github.io | GET | `/repos/martymcenroe/athleet.github.io/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/athleet.github.io | GET | `/repos/martymcenroe/athleet.github.io/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/athleet.github.io | GET | `...ymcenroe/athleet.github.io/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/athleet.github.io | GET | `/repos/martymcenroe/athleet.github.io` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/athleet.github.io | GET | `...os/martymcenroe/athleet.github.io/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/athleet.github.io | GET | `.../martymcenroe/athleet.github.io/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/athleet.dev | GET | `...rtymcenroe/athleet.dev/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/athleet.dev | GET | `/repos/martymcenroe/athleet.dev/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/athleet.dev | GET | `...ymcenroe/athleet.dev/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/athleet.dev | GET | `/repos/martymcenroe/athleet.dev/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/athleet.dev | GET | `/repos/martymcenroe/athleet.dev/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/athleet.dev | GET | `...s/martymcenroe/athleet.dev/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/athleet.dev | GET | `/repos/martymcenroe/athleet.dev` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/athleet.dev | GET | `/repos/martymcenroe/athleet.dev/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/athleet.dev | GET | `/repos/martymcenroe/athleet.dev/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/ai-power-systems-compendium | GET | `...wer-systems-compendium/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/ai-power-systems-compendium | GET | `...roe/ai-power-systems-compendium/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/ai-power-systems-compendium | GET | `...r-systems-compendium/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/ai-power-systems-compendium | GET | `.../martymcenroe/ai-power-systems-compendium/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/ai-power-systems-compendium | GET | `...cenroe/ai-power-systems-compendium/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/ai-power-systems-compendium | GET | `...i-power-systems-compendium/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/ai-power-systems-compendium | GET | `/repos/martymcenroe/ai-power-systems-compendium` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/ai-power-systems-compendium | GET | `...enroe/ai-power-systems-compendium/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/ai-power-systems-compendium | GET | `...roe/ai-power-systems-compendium/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/Agora | GET | `/repos/martymcenroe/Agora/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/Agora | GET | `/repos/martymcenroe/Agora/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/Agora | GET | `...s/martymcenroe/Agora/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/Agora | GET | `/repos/martymcenroe/Agora/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/Agora | GET | `/repos/martymcenroe/Agora/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/Agora | GET | `/repos/martymcenroe/Agora/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/Agora | GET | `/repos/martymcenroe/Agora` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/Agora | GET | `/repos/martymcenroe/Agora/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/Agora | GET | `/repos/martymcenroe/Agora/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/acpb-manifest-poc | GET | `...nroe/acpb-manifest-poc/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/acpb-manifest-poc | GET | `.../martymcenroe/acpb-manifest-poc/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/acpb-manifest-poc | GET | `...oe/acpb-manifest-poc/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/acpb-manifest-poc | GET | `/repos/martymcenroe/acpb-manifest-poc/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/acpb-manifest-poc | GET | `/repos/martymcenroe/acpb-manifest-poc/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/acpb-manifest-poc | GET | `...ymcenroe/acpb-manifest-poc/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/acpb-manifest-poc | GET | `/repos/martymcenroe/acpb-manifest-poc` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/acpb-manifest-poc | GET | `...os/martymcenroe/acpb-manifest-poc/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/acpb-manifest-poc | GET | `.../martymcenroe/acpb-manifest-poc/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/Hermes | GET | `...os/martymcenroe/Hermes/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/Hermes | GET | `/repos/martymcenroe/Hermes/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/Hermes | GET | `.../martymcenroe/Hermes/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/Hermes | GET | `/repos/martymcenroe/Hermes/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/Hermes | GET | `/repos/martymcenroe/Hermes/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/Hermes | GET | `/repos/martymcenroe/Hermes/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/Hermes | GET | `/repos/martymcenroe/Hermes` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/Hermes | GET | `/repos/martymcenroe/Hermes/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/Hermes | GET | `/repos/martymcenroe/Hermes/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/Aletheia | GET | `.../martymcenroe/Aletheia/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/Aletheia | GET | `/repos/martymcenroe/Aletheia/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/Aletheia | GET | `...artymcenroe/Aletheia/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/Aletheia | GET | `/repos/martymcenroe/Aletheia/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/Aletheia | GET | `/repos/martymcenroe/Aletheia/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/Aletheia | GET | `/repos/martymcenroe/Aletheia/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/Aletheia | GET | `/repos/martymcenroe/Aletheia` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/Aletheia | GET | `/repos/martymcenroe/Aletheia/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/Aletheia | GET | `/repos/martymcenroe/Aletheia/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/Talos | GET | `/repos/martymcenroe/Talos/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/Talos | GET | `/repos/martymcenroe/Talos/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/Talos | GET | `...s/martymcenroe/Talos/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/Talos | GET | `/repos/martymcenroe/Talos/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/Talos | GET | `/repos/martymcenroe/Talos/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/Talos | GET | `/repos/martymcenroe/Talos/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/Talos | GET | `/repos/martymcenroe/Talos` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/Talos | GET | `/repos/martymcenroe/Talos/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/Talos | GET | `/repos/martymcenroe/Talos/actions/runners` | 403 | **PROTECTED** | T1592 |  |
| P01 | martymcenroe/hermes-docs | GET | `...rtymcenroe/hermes-docs/branches/main/protection` | 403 | **PROTECTED** | T1592 |  |
| P02 | martymcenroe/hermes-docs | GET | `/repos/martymcenroe/hermes-docs/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P03 | martymcenroe/hermes-docs | GET | `...ymcenroe/hermes-docs/actions/secrets/public-key` | 403 | **PROTECTED** | T1552.001 |  |
| P04 | martymcenroe/hermes-docs | GET | `/repos/martymcenroe/hermes-docs/hooks` | 200 | **INFORMATIONAL** | T1592 | Webhooks may be granted in PAT |
| P05 | martymcenroe/hermes-docs | GET | `/repos/martymcenroe/hermes-docs/environments` | 200 | **INFORMATIONAL** | T1592 |  |
| P06 | martymcenroe/hermes-docs | GET | `...s/martymcenroe/hermes-docs/vulnerability-alerts` | 403 | **PROTECTED** | T1592 | 204=enabled, 404=disabled |
| P07 | martymcenroe/hermes-docs | GET | `/repos/martymcenroe/hermes-docs` | 200 | **INFORMATIONAL** | T1592 | permissions={"admin": true, "maintain": true, "push": true,  |
| P08 | martymcenroe/hermes-docs | GET | `/repos/martymcenroe/hermes-docs/traffic/views` | 403 | **PROTECTED** | T1592 |  |
| P09 | martymcenroe/hermes-docs | GET | `/repos/martymcenroe/hermes-docs/actions/runners` | 403 | **PROTECTED** | T1592 |  |

### Category: Privilege Escalation

| Probe | Repo | Method | Endpoint | HTTP | Verdict | ATT&CK | Detail |
|-------|------|--------|----------|------|---------|--------|--------|
| P10 | martymcenroe/dispatch | GET | `.../martymcenroe/dispatch/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/dispatch | GET | `.../martymcenroe/dispatch/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/dispatch | GET | `/repos/martymcenroe/dispatch` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/dispatch | GET | `/repos/martymcenroe/dispatch/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P14 | martymcenroe/dispatch | GET | `/user` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/dispatch | GET | `...ispatch/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/AssemblyZero | GET | `...tymcenroe/AssemblyZero/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/AssemblyZero | GET | `...tymcenroe/AssemblyZero/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/AssemblyZero | GET | `/repos/martymcenroe/AssemblyZero` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/AssemblyZero | GET | `/repos/martymcenroe/AssemblyZero/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/AssemblyZero | GET | `...blyZero/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/yt-playlist-importer | GET | `...e/yt-playlist-importer/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/yt-playlist-importer | GET | `...e/yt-playlist-importer/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/yt-playlist-importer | GET | `/repos/martymcenroe/yt-playlist-importer` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/yt-playlist-importer | GET | `...martymcenroe/yt-playlist-importer/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/yt-playlist-importer | GET | `...mporter/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/unleashed | GET | `...martymcenroe/unleashed/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/unleashed | GET | `...martymcenroe/unleashed/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/unleashed | GET | `/repos/martymcenroe/unleashed` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/unleashed | GET | `/repos/martymcenroe/unleashed/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/unleashed | GET | `...leashed/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/TxDOT-LDA | GET | `...martymcenroe/TxDOT-LDA/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/TxDOT-LDA | GET | `...martymcenroe/TxDOT-LDA/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/TxDOT-LDA | GET | `/repos/martymcenroe/TxDOT-LDA` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/TxDOT-LDA | GET | `/repos/martymcenroe/TxDOT-LDA/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/TxDOT-LDA | GET | `...DOT-LDA/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/thrivetech-ai | GET | `...ymcenroe/thrivetech-ai/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/thrivetech-ai | GET | `...ymcenroe/thrivetech-ai/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/thrivetech-ai | GET | `/repos/martymcenroe/thrivetech-ai` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/thrivetech-ai | GET | `/repos/martymcenroe/thrivetech-ai/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/thrivetech-ai | GET | `...tech-ai/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/TheMobyPerogative.world | GET | `...heMobyPerogative.world/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/TheMobyPerogative.world | GET | `...heMobyPerogative.world/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/TheMobyPerogative.world | GET | `/repos/martymcenroe/TheMobyPerogative.world` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/TheMobyPerogative.world | GET | `...tymcenroe/TheMobyPerogative.world/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/TheMobyPerogative.world | GET | `...e.world/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/spotify-personal-backups | GET | `...otify-personal-backups/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/spotify-personal-backups | GET | `...otify-personal-backups/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/spotify-personal-backups | GET | `/repos/martymcenroe/spotify-personal-backups` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/spotify-personal-backups | GET | `...ymcenroe/spotify-personal-backups/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/spotify-personal-backups | GET | `...backups/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/sentinel-rfc | GET | `...tymcenroe/sentinel-rfc/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/sentinel-rfc | GET | `...tymcenroe/sentinel-rfc/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/sentinel-rfc | GET | `/repos/martymcenroe/sentinel-rfc` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/sentinel-rfc | GET | `/repos/martymcenroe/sentinel-rfc/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/sentinel-rfc | GET | `...nel-rfc/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/sentinel | GET | `.../martymcenroe/sentinel/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/sentinel | GET | `.../martymcenroe/sentinel/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/sentinel | GET | `/repos/martymcenroe/sentinel` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/sentinel | GET | `/repos/martymcenroe/sentinel/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/sentinel | GET | `...entinel/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/RCA-PDF-extraction-pipeline | GET | `...DF-extraction-pipeline/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/RCA-PDF-extraction-pipeline | GET | `...DF-extraction-pipeline/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/RCA-PDF-extraction-pipeline | GET | `/repos/martymcenroe/RCA-PDF-extraction-pipeline` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/RCA-PDF-extraction-pipeline | GET | `...enroe/RCA-PDF-extraction-pipeline/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/RCA-PDF-extraction-pipeline | GET | `...ipeline/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/prompt-stream | GET | `...ymcenroe/prompt-stream/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/prompt-stream | GET | `...ymcenroe/prompt-stream/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/prompt-stream | GET | `/repos/martymcenroe/prompt-stream` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/prompt-stream | GET | `/repos/martymcenroe/prompt-stream/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/prompt-stream | GET | `...-stream/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/power-agent.github.io | GET | `.../power-agent.github.io/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/power-agent.github.io | GET | `.../power-agent.github.io/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/power-agent.github.io | GET | `/repos/martymcenroe/power-agent.github.io` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/power-agent.github.io | GET | `...artymcenroe/power-agent.github.io/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/power-agent.github.io | GET | `...thub.io/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/nec2017-analyzer | GET | `...enroe/nec2017-analyzer/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/nec2017-analyzer | GET | `...enroe/nec2017-analyzer/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/nec2017-analyzer | GET | `/repos/martymcenroe/nec2017-analyzer` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/nec2017-analyzer | GET | `/repos/martymcenroe/nec2017-analyzer/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/nec2017-analyzer | GET | `...nalyzer/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/neatworks-file-recovery | GET | `...eatworks-file-recovery/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/neatworks-file-recovery | GET | `...eatworks-file-recovery/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/neatworks-file-recovery | GET | `/repos/martymcenroe/neatworks-file-recovery` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/neatworks-file-recovery | GET | `...tymcenroe/neatworks-file-recovery/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/neatworks-file-recovery | GET | `...ecovery/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/mySvelte | GET | `.../martymcenroe/mySvelte/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/mySvelte | GET | `.../martymcenroe/mySvelte/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/mySvelte | GET | `/repos/martymcenroe/mySvelte` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/mySvelte | GET | `/repos/martymcenroe/mySvelte/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/mySvelte | GET | `...ySvelte/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/my-discussions | GET | `...mcenroe/my-discussions/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/my-discussions | GET | `...mcenroe/my-discussions/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/my-discussions | GET | `/repos/martymcenroe/my-discussions` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/my-discussions | GET | `/repos/martymcenroe/my-discussions/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/my-discussions | GET | `...ussions/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/my_hackerrank_SQL | GET | `...nroe/my_hackerrank_SQL/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/my_hackerrank_SQL | GET | `...nroe/my_hackerrank_SQL/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/my_hackerrank_SQL | GET | `/repos/martymcenroe/my_hackerrank_SQL` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/my_hackerrank_SQL | GET | `...os/martymcenroe/my_hackerrank_SQL/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/my_hackerrank_SQL | GET | `...ank_SQL/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/my_hackerrank_python | GET | `...e/my_hackerrank_python/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/my_hackerrank_python | GET | `...e/my_hackerrank_python/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/my_hackerrank_python | GET | `/repos/martymcenroe/my_hackerrank_python` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/my_hackerrank_python | GET | `...martymcenroe/my_hackerrank_python/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/my_hackerrank_python | GET | `..._python/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/metabolic-protocols | GET | `...oe/metabolic-protocols/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/metabolic-protocols | GET | `...oe/metabolic-protocols/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/metabolic-protocols | GET | `/repos/martymcenroe/metabolic-protocols` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/metabolic-protocols | GET | `.../martymcenroe/metabolic-protocols/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/metabolic-protocols | GET | `...otocols/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/martymcenroe.github.io | GET | `...martymcenroe.github.io/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/martymcenroe.github.io | GET | `...martymcenroe.github.io/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/martymcenroe.github.io | GET | `/repos/martymcenroe/martymcenroe.github.io` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/martymcenroe.github.io | GET | `...rtymcenroe/martymcenroe.github.io/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/martymcenroe.github.io | GET | `...thub.io/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/martymcenroe | GET | `...tymcenroe/martymcenroe/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/martymcenroe | GET | `...tymcenroe/martymcenroe/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/martymcenroe | GET | `/repos/martymcenroe/martymcenroe` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/martymcenroe | GET | `/repos/martymcenroe/martymcenroe/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/martymcenroe | GET | `...mcenroe/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/maintenance | GET | `...rtymcenroe/maintenance/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/maintenance | GET | `...rtymcenroe/maintenance/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/maintenance | GET | `/repos/martymcenroe/maintenance` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/maintenance | GET | `/repos/martymcenroe/maintenance/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/maintenance | GET | `...tenance/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/job-sniper | GET | `...artymcenroe/job-sniper/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/job-sniper | GET | `...artymcenroe/job-sniper/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/job-sniper | GET | `/repos/martymcenroe/job-sniper` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/job-sniper | GET | `/repos/martymcenroe/job-sniper/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/job-sniper | GET | `...-sniper/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/IEEE-standards | GET | `...mcenroe/IEEE-standards/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/IEEE-standards | GET | `...mcenroe/IEEE-standards/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/IEEE-standards | GET | `/repos/martymcenroe/IEEE-standards` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/IEEE-standards | GET | `/repos/martymcenroe/IEEE-standards/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/IEEE-standards | GET | `...andards/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/iconoscope | GET | `...artymcenroe/iconoscope/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/iconoscope | GET | `...artymcenroe/iconoscope/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/iconoscope | GET | `/repos/martymcenroe/iconoscope` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/iconoscope | GET | `/repos/martymcenroe/iconoscope/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/iconoscope | GET | `...noscope/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/HermesWiki | GET | `...artymcenroe/HermesWiki/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/HermesWiki | GET | `...artymcenroe/HermesWiki/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/HermesWiki | GET | `/repos/martymcenroe/HermesWiki` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/HermesWiki | GET | `/repos/martymcenroe/HermesWiki/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/HermesWiki | GET | `...mesWiki/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/GlucoPulse | GET | `...artymcenroe/GlucoPulse/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/GlucoPulse | GET | `...artymcenroe/GlucoPulse/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/GlucoPulse | GET | `/repos/martymcenroe/GlucoPulse` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/GlucoPulse | GET | `/repos/martymcenroe/GlucoPulse/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/GlucoPulse | GET | `...coPulse/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/github-readme-stats | GET | `...oe/github-readme-stats/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/github-readme-stats | GET | `...oe/github-readme-stats/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/github-readme-stats | GET | `/repos/martymcenroe/github-readme-stats` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/github-readme-stats | GET | `.../martymcenroe/github-readme-stats/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/github-readme-stats | GET | `...e-stats/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/gh-link-auditor | GET | `...cenroe/gh-link-auditor/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/gh-link-auditor | GET | `...cenroe/gh-link-auditor/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/gh-link-auditor | GET | `/repos/martymcenroe/gh-link-auditor` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/gh-link-auditor | GET | `/repos/martymcenroe/gh-link-auditor/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/gh-link-auditor | GET | `...auditor/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/GentlePersuader | GET | `...cenroe/GentlePersuader/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/GentlePersuader | GET | `...cenroe/GentlePersuader/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/GentlePersuader | GET | `/repos/martymcenroe/GentlePersuader` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/GentlePersuader | GET | `/repos/martymcenroe/GentlePersuader/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/GentlePersuader | GET | `...rsuader/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/electric-nexus | GET | `...mcenroe/electric-nexus/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/electric-nexus | GET | `...mcenroe/electric-nexus/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/electric-nexus | GET | `/repos/martymcenroe/electric-nexus` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/electric-nexus | GET | `/repos/martymcenroe/electric-nexus/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/electric-nexus | GET | `...c-nexus/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/dotfiles | GET | `.../martymcenroe/dotfiles/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/dotfiles | GET | `.../martymcenroe/dotfiles/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/dotfiles | GET | `/repos/martymcenroe/dotfiles` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/dotfiles | GET | `/repos/martymcenroe/dotfiles/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/dotfiles | GET | `...otfiles/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/dont-stop-now | GET | `...ymcenroe/dont-stop-now/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/dont-stop-now | GET | `...ymcenroe/dont-stop-now/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/dont-stop-now | GET | `/repos/martymcenroe/dont-stop-now` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/dont-stop-now | GET | `/repos/martymcenroe/dont-stop-now/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/dont-stop-now | GET | `...top-now/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/data-harvest | GET | `...tymcenroe/data-harvest/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/data-harvest | GET | `...tymcenroe/data-harvest/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/data-harvest | GET | `/repos/martymcenroe/data-harvest` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/data-harvest | GET | `/repos/martymcenroe/data-harvest/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/data-harvest | GET | `...harvest/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/CS512_link_predictor | GET | `...e/CS512_link_predictor/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/CS512_link_predictor | GET | `...e/CS512_link_predictor/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/CS512_link_predictor | GET | `/repos/martymcenroe/CS512_link_predictor` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/CS512_link_predictor | GET | `...martymcenroe/CS512_link_predictor/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/CS512_link_predictor | GET | `...edictor/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/collectibricks | GET | `...mcenroe/collectibricks/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/collectibricks | GET | `...mcenroe/collectibricks/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/collectibricks | GET | `/repos/martymcenroe/collectibricks` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/collectibricks | GET | `/repos/martymcenroe/collectibricks/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/collectibricks | GET | `...ibricks/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/Clio | GET | `/repos/martymcenroe/Clio/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/Clio | GET | `/repos/martymcenroe/Clio/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/Clio | GET | `/repos/martymcenroe/Clio` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/Clio | GET | `/repos/martymcenroe/Clio/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/Clio | GET | `...oe/Clio/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/career | GET | `...os/martymcenroe/career/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/career | GET | `...os/martymcenroe/career/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/career | GET | `/repos/martymcenroe/career` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/career | GET | `/repos/martymcenroe/career/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/career | GET | `.../career/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/best-of-pes-ai | GET | `...mcenroe/best-of-pes-ai/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/best-of-pes-ai | GET | `...mcenroe/best-of-pes-ai/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/best-of-pes-ai | GET | `/repos/martymcenroe/best-of-pes-ai` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/best-of-pes-ai | GET | `/repos/martymcenroe/best-of-pes-ai/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/best-of-pes-ai | GET | `...-pes-ai/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/automation-scripts | GET | `...roe/automation-scripts/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/automation-scripts | GET | `...roe/automation-scripts/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/automation-scripts | GET | `/repos/martymcenroe/automation-scripts` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/automation-scripts | GET | `...s/martymcenroe/automation-scripts/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/automation-scripts | GET | `...scripts/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/athleet.github.io | GET | `...nroe/athleet.github.io/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/athleet.github.io | GET | `...nroe/athleet.github.io/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/athleet.github.io | GET | `/repos/martymcenroe/athleet.github.io` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/athleet.github.io | GET | `...os/martymcenroe/athleet.github.io/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/athleet.github.io | GET | `...thub.io/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/athleet.dev | GET | `...rtymcenroe/athleet.dev/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/athleet.dev | GET | `...rtymcenroe/athleet.dev/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/athleet.dev | GET | `/repos/martymcenroe/athleet.dev` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/athleet.dev | GET | `/repos/martymcenroe/athleet.dev/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/athleet.dev | GET | `...eet.dev/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/ai-power-systems-compendium | GET | `...wer-systems-compendium/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/ai-power-systems-compendium | GET | `...wer-systems-compendium/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/ai-power-systems-compendium | GET | `/repos/martymcenroe/ai-power-systems-compendium` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/ai-power-systems-compendium | GET | `...enroe/ai-power-systems-compendium/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/ai-power-systems-compendium | GET | `...pendium/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/Agora | GET | `/repos/martymcenroe/Agora/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/Agora | GET | `/repos/martymcenroe/Agora/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/Agora | GET | `/repos/martymcenroe/Agora` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/Agora | GET | `/repos/martymcenroe/Agora/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/Agora | GET | `...e/Agora/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/acpb-manifest-poc | GET | `...nroe/acpb-manifest-poc/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/acpb-manifest-poc | GET | `...nroe/acpb-manifest-poc/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/acpb-manifest-poc | GET | `/repos/martymcenroe/acpb-manifest-poc` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/acpb-manifest-poc | GET | `...os/martymcenroe/acpb-manifest-poc/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/acpb-manifest-poc | GET | `...est-poc/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/Hermes | GET | `...os/martymcenroe/Hermes/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/Hermes | GET | `...os/martymcenroe/Hermes/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/Hermes | GET | `/repos/martymcenroe/Hermes` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/Hermes | GET | `/repos/martymcenroe/Hermes/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/Hermes | GET | `.../Hermes/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/Aletheia | GET | `.../martymcenroe/Aletheia/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/Aletheia | GET | `.../martymcenroe/Aletheia/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/Aletheia | GET | `/repos/martymcenroe/Aletheia` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/Aletheia | GET | `/repos/martymcenroe/Aletheia/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/Aletheia | GET | `...letheia/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/Talos | GET | `/repos/martymcenroe/Talos/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/Talos | GET | `/repos/martymcenroe/Talos/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/Talos | GET | `/repos/martymcenroe/Talos` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/Talos | GET | `/repos/martymcenroe/Talos/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/Talos | GET | `...e/Talos/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |
| P10 | martymcenroe/hermes-docs | GET | `...rtymcenroe/hermes-docs/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P11 | martymcenroe/hermes-docs | GET | `...rtymcenroe/hermes-docs/branches/main/protection` | 403 | **PROTECTED** | T1548 | Read-only probe |
| P12 | martymcenroe/hermes-docs | GET | `/repos/martymcenroe/hermes-docs` | 200 | **INFORMATIONAL** | T1548 | Read-only probe |
| P13 | martymcenroe/hermes-docs | GET | `/repos/martymcenroe/hermes-docs/collaborators` | 200 | **INFORMATIONAL** | T1548 |  |
| P15 | martymcenroe/hermes-docs | GET | `...es-docs/branches/main/protection/enforce_admins` | 403 | **PROTECTED** | T1548 |  |

### Category: Credential Access

| Probe | Repo | Method | Endpoint | HTTP | Verdict | ATT&CK | Detail |
|-------|------|--------|----------|------|---------|--------|--------|
| P16 | martymcenroe/dispatch | GET | `/repos/martymcenroe/dispatch/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/dispatch | GET | `/repos/martymcenroe/dispatch/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/dispatch | GET | `/repos/martymcenroe/dispatch/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/dispatch | GET | `...tymcenroe/dispatch/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P20 | martymcenroe/dispatch | GET | `/user/keys` | 403 | **PROTECTED** | T1552.004 | User-level endpoint |
| P21 | martymcenroe/dispatch | GET | `/user/gpg_keys` | 403 | **PROTECTED** | T1552 | User-level endpoint |
| P16 | martymcenroe/AssemblyZero | GET | `/repos/martymcenroe/AssemblyZero/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/AssemblyZero | GET | `...os/martymcenroe/AssemblyZero/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/AssemblyZero | GET | `...os/martymcenroe/AssemblyZero/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/AssemblyZero | GET | `...enroe/AssemblyZero/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/yt-playlist-importer | GET | `...rtymcenroe/yt-playlist-importer/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/yt-playlist-importer | GET | `...mcenroe/yt-playlist-importer/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/yt-playlist-importer | GET | `...mcenroe/yt-playlist-importer/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/yt-playlist-importer | GET | `...-playlist-importer/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/unleashed | GET | `/repos/martymcenroe/unleashed/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/unleashed | GET | `/repos/martymcenroe/unleashed/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/unleashed | GET | `/repos/martymcenroe/unleashed/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/unleashed | GET | `...ymcenroe/unleashed/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/TxDOT-LDA | GET | `/repos/martymcenroe/TxDOT-LDA/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/TxDOT-LDA | GET | `/repos/martymcenroe/TxDOT-LDA/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/TxDOT-LDA | GET | `/repos/martymcenroe/TxDOT-LDA/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/TxDOT-LDA | GET | `...ymcenroe/TxDOT-LDA/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/thrivetech-ai | GET | `/repos/martymcenroe/thrivetech-ai/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/thrivetech-ai | GET | `...s/martymcenroe/thrivetech-ai/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/thrivetech-ai | GET | `...s/martymcenroe/thrivetech-ai/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/thrivetech-ai | GET | `...nroe/thrivetech-ai/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/TheMobyPerogative.world | GET | `...mcenroe/TheMobyPerogative.world/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/TheMobyPerogative.world | GET | `...nroe/TheMobyPerogative.world/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/TheMobyPerogative.world | GET | `...nroe/TheMobyPerogative.world/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/TheMobyPerogative.world | GET | `...byPerogative.world/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/spotify-personal-backups | GET | `...cenroe/spotify-personal-backups/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/spotify-personal-backups | GET | `...roe/spotify-personal-backups/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/spotify-personal-backups | GET | `...roe/spotify-personal-backups/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/spotify-personal-backups | GET | `...y-personal-backups/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/sentinel-rfc | GET | `/repos/martymcenroe/sentinel-rfc/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/sentinel-rfc | GET | `...os/martymcenroe/sentinel-rfc/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/sentinel-rfc | GET | `...os/martymcenroe/sentinel-rfc/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/sentinel-rfc | GET | `...enroe/sentinel-rfc/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/sentinel | GET | `/repos/martymcenroe/sentinel/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/sentinel | GET | `/repos/martymcenroe/sentinel/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/sentinel | GET | `/repos/martymcenroe/sentinel/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/sentinel | GET | `...tymcenroe/sentinel/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/RCA-PDF-extraction-pipeline | GET | `...roe/RCA-PDF-extraction-pipeline/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/RCA-PDF-extraction-pipeline | GET | `.../RCA-PDF-extraction-pipeline/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/RCA-PDF-extraction-pipeline | GET | `.../RCA-PDF-extraction-pipeline/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/RCA-PDF-extraction-pipeline | GET | `...xtraction-pipeline/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/prompt-stream | GET | `/repos/martymcenroe/prompt-stream/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/prompt-stream | GET | `...s/martymcenroe/prompt-stream/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/prompt-stream | GET | `...s/martymcenroe/prompt-stream/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/prompt-stream | GET | `...nroe/prompt-stream/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/power-agent.github.io | GET | `...tymcenroe/power-agent.github.io/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/power-agent.github.io | GET | `...cenroe/power-agent.github.io/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/power-agent.github.io | GET | `...cenroe/power-agent.github.io/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/power-agent.github.io | GET | `...er-agent.github.io/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/nec2017-analyzer | GET | `...s/martymcenroe/nec2017-analyzer/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/nec2017-analyzer | GET | `...artymcenroe/nec2017-analyzer/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/nec2017-analyzer | GET | `...artymcenroe/nec2017-analyzer/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/nec2017-analyzer | GET | `...e/nec2017-analyzer/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/neatworks-file-recovery | GET | `...mcenroe/neatworks-file-recovery/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/neatworks-file-recovery | GET | `...nroe/neatworks-file-recovery/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/neatworks-file-recovery | GET | `...nroe/neatworks-file-recovery/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/neatworks-file-recovery | GET | `...orks-file-recovery/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/mySvelte | GET | `/repos/martymcenroe/mySvelte/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/mySvelte | GET | `/repos/martymcenroe/mySvelte/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/mySvelte | GET | `/repos/martymcenroe/mySvelte/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/mySvelte | GET | `...tymcenroe/mySvelte/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/my-discussions | GET | `/repos/martymcenroe/my-discussions/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/my-discussions | GET | `.../martymcenroe/my-discussions/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/my-discussions | GET | `.../martymcenroe/my-discussions/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/my-discussions | GET | `...roe/my-discussions/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/my_hackerrank_SQL | GET | `.../martymcenroe/my_hackerrank_SQL/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/my_hackerrank_SQL | GET | `...rtymcenroe/my_hackerrank_SQL/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/my_hackerrank_SQL | GET | `...rtymcenroe/my_hackerrank_SQL/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/my_hackerrank_SQL | GET | `.../my_hackerrank_SQL/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/my_hackerrank_python | GET | `...rtymcenroe/my_hackerrank_python/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/my_hackerrank_python | GET | `...mcenroe/my_hackerrank_python/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/my_hackerrank_python | GET | `...mcenroe/my_hackerrank_python/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/my_hackerrank_python | GET | `..._hackerrank_python/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/metabolic-protocols | GET | `...artymcenroe/metabolic-protocols/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/metabolic-protocols | GET | `...ymcenroe/metabolic-protocols/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/metabolic-protocols | GET | `...ymcenroe/metabolic-protocols/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/metabolic-protocols | GET | `...etabolic-protocols/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/martymcenroe.github.io | GET | `...ymcenroe/martymcenroe.github.io/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/martymcenroe.github.io | GET | `...enroe/martymcenroe.github.io/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/martymcenroe.github.io | GET | `...enroe/martymcenroe.github.io/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/martymcenroe.github.io | GET | `...ymcenroe.github.io/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/martymcenroe | GET | `/repos/martymcenroe/martymcenroe/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/martymcenroe | GET | `...os/martymcenroe/martymcenroe/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/martymcenroe | GET | `...os/martymcenroe/martymcenroe/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/martymcenroe | GET | `...enroe/martymcenroe/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/maintenance | GET | `/repos/martymcenroe/maintenance/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/maintenance | GET | `/repos/martymcenroe/maintenance/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/maintenance | GET | `/repos/martymcenroe/maintenance/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/maintenance | GET | `...cenroe/maintenance/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/job-sniper | GET | `/repos/martymcenroe/job-sniper/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/job-sniper | GET | `/repos/martymcenroe/job-sniper/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/job-sniper | GET | `/repos/martymcenroe/job-sniper/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/job-sniper | GET | `...mcenroe/job-sniper/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/IEEE-standards | GET | `/repos/martymcenroe/IEEE-standards/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/IEEE-standards | GET | `.../martymcenroe/IEEE-standards/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/IEEE-standards | GET | `.../martymcenroe/IEEE-standards/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/IEEE-standards | GET | `...roe/IEEE-standards/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/iconoscope | GET | `/repos/martymcenroe/iconoscope/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/iconoscope | GET | `/repos/martymcenroe/iconoscope/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/iconoscope | GET | `/repos/martymcenroe/iconoscope/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/iconoscope | GET | `...mcenroe/iconoscope/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/HermesWiki | GET | `/repos/martymcenroe/HermesWiki/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/HermesWiki | GET | `/repos/martymcenroe/HermesWiki/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/HermesWiki | GET | `/repos/martymcenroe/HermesWiki/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/HermesWiki | GET | `...mcenroe/HermesWiki/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/GlucoPulse | GET | `/repos/martymcenroe/GlucoPulse/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/GlucoPulse | GET | `/repos/martymcenroe/GlucoPulse/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/GlucoPulse | GET | `/repos/martymcenroe/GlucoPulse/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/GlucoPulse | GET | `...mcenroe/GlucoPulse/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/github-readme-stats | GET | `...artymcenroe/github-readme-stats/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/github-readme-stats | GET | `...ymcenroe/github-readme-stats/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/github-readme-stats | GET | `...ymcenroe/github-readme-stats/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/github-readme-stats | GET | `...ithub-readme-stats/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/gh-link-auditor | GET | `...os/martymcenroe/gh-link-auditor/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/gh-link-auditor | GET | `...martymcenroe/gh-link-auditor/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/gh-link-auditor | GET | `...martymcenroe/gh-link-auditor/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/gh-link-auditor | GET | `...oe/gh-link-auditor/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/GentlePersuader | GET | `...os/martymcenroe/GentlePersuader/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/GentlePersuader | GET | `...martymcenroe/GentlePersuader/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/GentlePersuader | GET | `...martymcenroe/GentlePersuader/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/GentlePersuader | GET | `...oe/GentlePersuader/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/electric-nexus | GET | `/repos/martymcenroe/electric-nexus/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/electric-nexus | GET | `.../martymcenroe/electric-nexus/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/electric-nexus | GET | `.../martymcenroe/electric-nexus/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/electric-nexus | GET | `...roe/electric-nexus/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/dotfiles | GET | `/repos/martymcenroe/dotfiles/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/dotfiles | GET | `/repos/martymcenroe/dotfiles/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/dotfiles | GET | `/repos/martymcenroe/dotfiles/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/dotfiles | GET | `...tymcenroe/dotfiles/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/dont-stop-now | GET | `/repos/martymcenroe/dont-stop-now/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/dont-stop-now | GET | `...s/martymcenroe/dont-stop-now/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/dont-stop-now | GET | `...s/martymcenroe/dont-stop-now/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/dont-stop-now | GET | `...nroe/dont-stop-now/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/data-harvest | GET | `/repos/martymcenroe/data-harvest/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/data-harvest | GET | `...os/martymcenroe/data-harvest/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/data-harvest | GET | `...os/martymcenroe/data-harvest/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/data-harvest | GET | `...enroe/data-harvest/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/CS512_link_predictor | GET | `...rtymcenroe/CS512_link_predictor/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/CS512_link_predictor | GET | `...mcenroe/CS512_link_predictor/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/CS512_link_predictor | GET | `...mcenroe/CS512_link_predictor/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/CS512_link_predictor | GET | `...512_link_predictor/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/collectibricks | GET | `/repos/martymcenroe/collectibricks/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/collectibricks | GET | `.../martymcenroe/collectibricks/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/collectibricks | GET | `.../martymcenroe/collectibricks/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/collectibricks | GET | `...roe/collectibricks/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/Clio | GET | `/repos/martymcenroe/Clio/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/Clio | GET | `/repos/martymcenroe/Clio/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/Clio | GET | `/repos/martymcenroe/Clio/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/Clio | GET | `.../martymcenroe/Clio/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/career | GET | `/repos/martymcenroe/career/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/career | GET | `/repos/martymcenroe/career/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/career | GET | `/repos/martymcenroe/career/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/career | GET | `...artymcenroe/career/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/best-of-pes-ai | GET | `/repos/martymcenroe/best-of-pes-ai/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/best-of-pes-ai | GET | `.../martymcenroe/best-of-pes-ai/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/best-of-pes-ai | GET | `.../martymcenroe/best-of-pes-ai/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/best-of-pes-ai | GET | `...roe/best-of-pes-ai/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/automation-scripts | GET | `...martymcenroe/automation-scripts/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/automation-scripts | GET | `...tymcenroe/automation-scripts/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/automation-scripts | GET | `...tymcenroe/automation-scripts/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/automation-scripts | GET | `...automation-scripts/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/athleet.github.io | GET | `.../martymcenroe/athleet.github.io/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/athleet.github.io | GET | `...rtymcenroe/athleet.github.io/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/athleet.github.io | GET | `...rtymcenroe/athleet.github.io/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/athleet.github.io | GET | `.../athleet.github.io/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/athleet.dev | GET | `/repos/martymcenroe/athleet.dev/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/athleet.dev | GET | `/repos/martymcenroe/athleet.dev/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/athleet.dev | GET | `/repos/martymcenroe/athleet.dev/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/athleet.dev | GET | `...cenroe/athleet.dev/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/ai-power-systems-compendium | GET | `...roe/ai-power-systems-compendium/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/ai-power-systems-compendium | GET | `.../ai-power-systems-compendium/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/ai-power-systems-compendium | GET | `.../ai-power-systems-compendium/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/ai-power-systems-compendium | GET | `...systems-compendium/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/Agora | GET | `/repos/martymcenroe/Agora/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/Agora | GET | `/repos/martymcenroe/Agora/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/Agora | GET | `/repos/martymcenroe/Agora/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/Agora | GET | `...martymcenroe/Agora/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/acpb-manifest-poc | GET | `.../martymcenroe/acpb-manifest-poc/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/acpb-manifest-poc | GET | `...rtymcenroe/acpb-manifest-poc/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/acpb-manifest-poc | GET | `...rtymcenroe/acpb-manifest-poc/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/acpb-manifest-poc | GET | `.../acpb-manifest-poc/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/Hermes | GET | `/repos/martymcenroe/Hermes/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/Hermes | GET | `/repos/martymcenroe/Hermes/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/Hermes | GET | `/repos/martymcenroe/Hermes/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/Hermes | GET | `...artymcenroe/Hermes/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/Aletheia | GET | `/repos/martymcenroe/Aletheia/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/Aletheia | GET | `/repos/martymcenroe/Aletheia/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/Aletheia | GET | `/repos/martymcenroe/Aletheia/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/Aletheia | GET | `...tymcenroe/Aletheia/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/Talos | GET | `/repos/martymcenroe/Talos/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/Talos | GET | `/repos/martymcenroe/Talos/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/Talos | GET | `/repos/martymcenroe/Talos/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/Talos | GET | `...martymcenroe/Talos/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P16 | martymcenroe/hermes-docs | GET | `/repos/martymcenroe/hermes-docs/actions/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P17 | martymcenroe/hermes-docs | GET | `/repos/martymcenroe/hermes-docs/dependabot/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P18 | martymcenroe/hermes-docs | GET | `/repos/martymcenroe/hermes-docs/codespaces/secrets` | 403 | **PROTECTED** | T1552.001 |  |
| P19 | martymcenroe/hermes-docs | GET | `...cenroe/hermes-docs/actions/organization-secrets` | 403 | **PROTECTED** | T1552.001 |  |

### Category: Defense Evasion

| Probe | Repo | Method | Endpoint | HTTP | Verdict | ATT&CK | Detail |
|-------|------|--------|----------|------|---------|--------|--------|
| P22 | martymcenroe/dispatch | GET | `.../martymcenroe/dispatch/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/dispatch | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/dispatch | GET | `...ch/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/dispatch | GET | `/repos/martymcenroe/dispatch/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/dispatch | GET | `/repos/martymcenroe/dispatch/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/AssemblyZero | GET | `...tymcenroe/AssemblyZero/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/AssemblyZero | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/AssemblyZero | GET | `...ro/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/AssemblyZero | GET | `/repos/martymcenroe/AssemblyZero/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/AssemblyZero | GET | `/repos/martymcenroe/AssemblyZero/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/yt-playlist-importer | GET | `...e/yt-playlist-importer/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/yt-playlist-importer | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/yt-playlist-importer | GET | `...er/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/yt-playlist-importer | GET | `/repos/martymcenroe/yt-playlist-importer/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/yt-playlist-importer | GET | `/repos/martymcenroe/yt-playlist-importer/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/unleashed | GET | `...martymcenroe/unleashed/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/unleashed | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/unleashed | GET | `...ed/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/unleashed | GET | `/repos/martymcenroe/unleashed/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/unleashed | GET | `/repos/martymcenroe/unleashed/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/TxDOT-LDA | GET | `...martymcenroe/TxDOT-LDA/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/TxDOT-LDA | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/TxDOT-LDA | GET | `...DA/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/TxDOT-LDA | GET | `/repos/martymcenroe/TxDOT-LDA/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/TxDOT-LDA | GET | `/repos/martymcenroe/TxDOT-LDA/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/thrivetech-ai | GET | `...ymcenroe/thrivetech-ai/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/thrivetech-ai | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/thrivetech-ai | GET | `...ai/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/thrivetech-ai | GET | `/repos/martymcenroe/thrivetech-ai/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/thrivetech-ai | GET | `/repos/martymcenroe/thrivetech-ai/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/TheMobyPerogative.world | GET | `...heMobyPerogative.world/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/TheMobyPerogative.world | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/TheMobyPerogative.world | GET | `...ld/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/TheMobyPerogative.world | GET | `/repos/martymcenroe/TheMobyPerogative.world/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/TheMobyPerogative.world | GET | `/repos/martymcenroe/TheMobyPerogative.world/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/spotify-personal-backups | GET | `...otify-personal-backups/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/spotify-personal-backups | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/spotify-personal-backups | GET | `...ps/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/spotify-personal-backups | GET | `...os/martymcenroe/spotify-personal-backups/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/spotify-personal-backups | GET | `/repos/martymcenroe/spotify-personal-backups/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/sentinel-rfc | GET | `...tymcenroe/sentinel-rfc/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/sentinel-rfc | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/sentinel-rfc | GET | `...fc/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/sentinel-rfc | GET | `/repos/martymcenroe/sentinel-rfc/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/sentinel-rfc | GET | `/repos/martymcenroe/sentinel-rfc/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/sentinel | GET | `.../martymcenroe/sentinel/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/sentinel | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/sentinel | GET | `...el/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/sentinel | GET | `/repos/martymcenroe/sentinel/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/sentinel | GET | `/repos/martymcenroe/sentinel/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/RCA-PDF-extraction-pipeline | GET | `...DF-extraction-pipeline/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/RCA-PDF-extraction-pipeline | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/RCA-PDF-extraction-pipeline | GET | `...ne/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/RCA-PDF-extraction-pipeline | GET | `...martymcenroe/RCA-PDF-extraction-pipeline/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/RCA-PDF-extraction-pipeline | GET | `.../martymcenroe/RCA-PDF-extraction-pipeline/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/prompt-stream | GET | `...ymcenroe/prompt-stream/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/prompt-stream | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/prompt-stream | GET | `...am/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/prompt-stream | GET | `/repos/martymcenroe/prompt-stream/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/prompt-stream | GET | `/repos/martymcenroe/prompt-stream/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/power-agent.github.io | GET | `.../power-agent.github.io/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/power-agent.github.io | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/power-agent.github.io | GET | `...io/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/power-agent.github.io | GET | `/repos/martymcenroe/power-agent.github.io/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/power-agent.github.io | GET | `/repos/martymcenroe/power-agent.github.io/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/nec2017-analyzer | GET | `...enroe/nec2017-analyzer/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/nec2017-analyzer | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/nec2017-analyzer | GET | `...er/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/nec2017-analyzer | GET | `/repos/martymcenroe/nec2017-analyzer/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/nec2017-analyzer | GET | `/repos/martymcenroe/nec2017-analyzer/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/neatworks-file-recovery | GET | `...eatworks-file-recovery/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/neatworks-file-recovery | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/neatworks-file-recovery | GET | `...ry/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/neatworks-file-recovery | GET | `/repos/martymcenroe/neatworks-file-recovery/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/neatworks-file-recovery | GET | `/repos/martymcenroe/neatworks-file-recovery/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/mySvelte | GET | `.../martymcenroe/mySvelte/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/mySvelte | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/mySvelte | GET | `...te/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/mySvelte | GET | `/repos/martymcenroe/mySvelte/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/mySvelte | GET | `/repos/martymcenroe/mySvelte/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/my-discussions | GET | `...mcenroe/my-discussions/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/my-discussions | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/my-discussions | GET | `...ns/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/my-discussions | GET | `/repos/martymcenroe/my-discussions/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/my-discussions | GET | `/repos/martymcenroe/my-discussions/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/my_hackerrank_SQL | GET | `...nroe/my_hackerrank_SQL/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/my_hackerrank_SQL | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/my_hackerrank_SQL | GET | `...QL/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/my_hackerrank_SQL | GET | `/repos/martymcenroe/my_hackerrank_SQL/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/my_hackerrank_SQL | GET | `/repos/martymcenroe/my_hackerrank_SQL/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/my_hackerrank_python | GET | `...e/my_hackerrank_python/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/my_hackerrank_python | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/my_hackerrank_python | GET | `...on/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/my_hackerrank_python | GET | `/repos/martymcenroe/my_hackerrank_python/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/my_hackerrank_python | GET | `/repos/martymcenroe/my_hackerrank_python/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/metabolic-protocols | GET | `...oe/metabolic-protocols/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/metabolic-protocols | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/metabolic-protocols | GET | `...ls/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/metabolic-protocols | GET | `/repos/martymcenroe/metabolic-protocols/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/metabolic-protocols | GET | `/repos/martymcenroe/metabolic-protocols/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/martymcenroe.github.io | GET | `...martymcenroe.github.io/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/martymcenroe.github.io | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/martymcenroe.github.io | GET | `...io/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/martymcenroe.github.io | GET | `/repos/martymcenroe/martymcenroe.github.io/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/martymcenroe.github.io | GET | `/repos/martymcenroe/martymcenroe.github.io/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/martymcenroe | GET | `...tymcenroe/martymcenroe/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/martymcenroe | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/martymcenroe | GET | `...oe/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/martymcenroe | GET | `/repos/martymcenroe/martymcenroe/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/martymcenroe | GET | `/repos/martymcenroe/martymcenroe/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/maintenance | GET | `...rtymcenroe/maintenance/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/maintenance | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/maintenance | GET | `...ce/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/maintenance | GET | `/repos/martymcenroe/maintenance/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/maintenance | GET | `/repos/martymcenroe/maintenance/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/job-sniper | GET | `...artymcenroe/job-sniper/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/job-sniper | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/job-sniper | GET | `...er/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/job-sniper | GET | `/repos/martymcenroe/job-sniper/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/job-sniper | GET | `/repos/martymcenroe/job-sniper/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/IEEE-standards | GET | `...mcenroe/IEEE-standards/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/IEEE-standards | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/IEEE-standards | GET | `...ds/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/IEEE-standards | GET | `/repos/martymcenroe/IEEE-standards/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/IEEE-standards | GET | `/repos/martymcenroe/IEEE-standards/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/iconoscope | GET | `...artymcenroe/iconoscope/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/iconoscope | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/iconoscope | GET | `...pe/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/iconoscope | GET | `/repos/martymcenroe/iconoscope/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/iconoscope | GET | `/repos/martymcenroe/iconoscope/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/HermesWiki | GET | `...artymcenroe/HermesWiki/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/HermesWiki | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/HermesWiki | GET | `...ki/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/HermesWiki | GET | `/repos/martymcenroe/HermesWiki/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/HermesWiki | GET | `/repos/martymcenroe/HermesWiki/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/GlucoPulse | GET | `...artymcenroe/GlucoPulse/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/GlucoPulse | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/GlucoPulse | GET | `...se/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/GlucoPulse | GET | `/repos/martymcenroe/GlucoPulse/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/GlucoPulse | GET | `/repos/martymcenroe/GlucoPulse/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/github-readme-stats | GET | `...oe/github-readme-stats/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/github-readme-stats | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/github-readme-stats | GET | `...ts/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/github-readme-stats | GET | `/repos/martymcenroe/github-readme-stats/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/github-readme-stats | GET | `/repos/martymcenroe/github-readme-stats/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/gh-link-auditor | GET | `...cenroe/gh-link-auditor/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/gh-link-auditor | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/gh-link-auditor | GET | `...or/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/gh-link-auditor | GET | `/repos/martymcenroe/gh-link-auditor/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/gh-link-auditor | GET | `/repos/martymcenroe/gh-link-auditor/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/GentlePersuader | GET | `...cenroe/GentlePersuader/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/GentlePersuader | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/GentlePersuader | GET | `...er/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/GentlePersuader | GET | `/repos/martymcenroe/GentlePersuader/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/GentlePersuader | GET | `/repos/martymcenroe/GentlePersuader/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/electric-nexus | GET | `...mcenroe/electric-nexus/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/electric-nexus | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/electric-nexus | GET | `...us/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/electric-nexus | GET | `/repos/martymcenroe/electric-nexus/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/electric-nexus | GET | `/repos/martymcenroe/electric-nexus/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/dotfiles | GET | `.../martymcenroe/dotfiles/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/dotfiles | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/dotfiles | GET | `...es/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/dotfiles | GET | `/repos/martymcenroe/dotfiles/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/dotfiles | GET | `/repos/martymcenroe/dotfiles/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/dont-stop-now | GET | `...ymcenroe/dont-stop-now/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/dont-stop-now | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/dont-stop-now | GET | `...ow/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/dont-stop-now | GET | `/repos/martymcenroe/dont-stop-now/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/dont-stop-now | GET | `/repos/martymcenroe/dont-stop-now/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/data-harvest | GET | `...tymcenroe/data-harvest/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/data-harvest | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/data-harvest | GET | `...st/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/data-harvest | GET | `/repos/martymcenroe/data-harvest/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/data-harvest | GET | `/repos/martymcenroe/data-harvest/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/CS512_link_predictor | GET | `...e/CS512_link_predictor/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/CS512_link_predictor | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/CS512_link_predictor | GET | `...or/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/CS512_link_predictor | GET | `/repos/martymcenroe/CS512_link_predictor/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/CS512_link_predictor | GET | `/repos/martymcenroe/CS512_link_predictor/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/collectibricks | GET | `...mcenroe/collectibricks/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/collectibricks | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/collectibricks | GET | `...ks/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/collectibricks | GET | `/repos/martymcenroe/collectibricks/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/collectibricks | GET | `/repos/martymcenroe/collectibricks/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/Clio | GET | `/repos/martymcenroe/Clio/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/Clio | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/Clio | GET | `...io/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/Clio | GET | `/repos/martymcenroe/Clio/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/Clio | GET | `/repos/martymcenroe/Clio/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/career | GET | `...os/martymcenroe/career/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/career | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/career | GET | `...er/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/career | GET | `/repos/martymcenroe/career/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/career | GET | `/repos/martymcenroe/career/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/best-of-pes-ai | GET | `...mcenroe/best-of-pes-ai/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/best-of-pes-ai | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/best-of-pes-ai | GET | `...ai/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/best-of-pes-ai | GET | `/repos/martymcenroe/best-of-pes-ai/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/best-of-pes-ai | GET | `/repos/martymcenroe/best-of-pes-ai/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/automation-scripts | GET | `...roe/automation-scripts/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/automation-scripts | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/automation-scripts | GET | `...ts/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/automation-scripts | GET | `/repos/martymcenroe/automation-scripts/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/automation-scripts | GET | `/repos/martymcenroe/automation-scripts/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/athleet.github.io | GET | `...nroe/athleet.github.io/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/athleet.github.io | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/athleet.github.io | GET | `...io/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/athleet.github.io | GET | `/repos/martymcenroe/athleet.github.io/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/athleet.github.io | GET | `/repos/martymcenroe/athleet.github.io/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/athleet.dev | GET | `...rtymcenroe/athleet.dev/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/athleet.dev | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/athleet.dev | GET | `...ev/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/athleet.dev | GET | `/repos/martymcenroe/athleet.dev/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/athleet.dev | GET | `/repos/martymcenroe/athleet.dev/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/ai-power-systems-compendium | GET | `...wer-systems-compendium/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/ai-power-systems-compendium | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/ai-power-systems-compendium | GET | `...um/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/ai-power-systems-compendium | GET | `...martymcenroe/ai-power-systems-compendium/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/ai-power-systems-compendium | GET | `.../martymcenroe/ai-power-systems-compendium/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/Agora | GET | `/repos/martymcenroe/Agora/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/Agora | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/Agora | GET | `...ra/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/Agora | GET | `/repos/martymcenroe/Agora/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/Agora | GET | `/repos/martymcenroe/Agora/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/acpb-manifest-poc | GET | `...nroe/acpb-manifest-poc/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/acpb-manifest-poc | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/acpb-manifest-poc | GET | `...oc/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/acpb-manifest-poc | GET | `/repos/martymcenroe/acpb-manifest-poc/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/acpb-manifest-poc | GET | `/repos/martymcenroe/acpb-manifest-poc/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/Hermes | GET | `...os/martymcenroe/Hermes/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/Hermes | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/Hermes | GET | `...es/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/Hermes | GET | `/repos/martymcenroe/Hermes/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/Hermes | GET | `/repos/martymcenroe/Hermes/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/Aletheia | GET | `.../martymcenroe/Aletheia/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/Aletheia | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/Aletheia | GET | `...ia/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/Aletheia | GET | `/repos/martymcenroe/Aletheia/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/Aletheia | GET | `/repos/martymcenroe/Aletheia/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/Talos | GET | `/repos/martymcenroe/Talos/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/Talos | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/Talos | GET | `...os/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/Talos | GET | `/repos/martymcenroe/Talos/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/Talos | GET | `/repos/martymcenroe/Talos/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |
| P22 | martymcenroe/hermes-docs | GET | `...rtymcenroe/hermes-docs/branches/main/protection` | 403 | **PROTECTED** | T1562.001 | Read-only probe |
| P23 | martymcenroe/hermes-docs | GET | `...branches/main/protection/required_status_checks` | 403 | **PROTECTED** | T1562.001 |  |
| P24 | martymcenroe/hermes-docs | GET | `...cs/branches/main/protection/required_signatures` | 403 | **PROTECTED** | T1562.001 |  |
| P25 | martymcenroe/hermes-docs | GET | `/repos/martymcenroe/hermes-docs/topics` | 200 | **INFORMATIONAL** | T1036 |  |
| P26 | martymcenroe/hermes-docs | GET | `/repos/martymcenroe/hermes-docs/hooks` | 200 | **INFORMATIONAL** | T1562.001 | Read-only probe |

### Category: Impact

| Probe | Repo | Method | Endpoint | HTTP | Verdict | ATT&CK | Detail |
|-------|------|--------|----------|------|---------|--------|--------|
| P27 | martymcenroe/dispatch | GET | `/repos/martymcenroe/dispatch` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/dispatch | GET | `/repos/martymcenroe/dispatch` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/dispatch | GET | `/repos/martymcenroe/dispatch` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/dispatch | GET | `/repos/martymcenroe/dispatch/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/AssemblyZero | GET | `/repos/martymcenroe/AssemblyZero` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/AssemblyZero | GET | `/repos/martymcenroe/AssemblyZero` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/AssemblyZero | GET | `/repos/martymcenroe/AssemblyZero` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/AssemblyZero | GET | `...s/martymcenroe/AssemblyZero/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/yt-playlist-importer | GET | `/repos/martymcenroe/yt-playlist-importer` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/yt-playlist-importer | GET | `/repos/martymcenroe/yt-playlist-importer` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/yt-playlist-importer | GET | `/repos/martymcenroe/yt-playlist-importer` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/yt-playlist-importer | GET | `...cenroe/yt-playlist-importer/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/unleashed | GET | `/repos/martymcenroe/unleashed` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/unleashed | GET | `/repos/martymcenroe/unleashed` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/unleashed | GET | `/repos/martymcenroe/unleashed` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/unleashed | GET | `/repos/martymcenroe/unleashed/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/TxDOT-LDA | GET | `/repos/martymcenroe/TxDOT-LDA` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/TxDOT-LDA | GET | `/repos/martymcenroe/TxDOT-LDA` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/TxDOT-LDA | GET | `/repos/martymcenroe/TxDOT-LDA` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/TxDOT-LDA | GET | `/repos/martymcenroe/TxDOT-LDA/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/thrivetech-ai | GET | `/repos/martymcenroe/thrivetech-ai` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/thrivetech-ai | GET | `/repos/martymcenroe/thrivetech-ai` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/thrivetech-ai | GET | `/repos/martymcenroe/thrivetech-ai` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/thrivetech-ai | GET | `.../martymcenroe/thrivetech-ai/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/TheMobyPerogative.world | GET | `/repos/martymcenroe/TheMobyPerogative.world` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/TheMobyPerogative.world | GET | `/repos/martymcenroe/TheMobyPerogative.world` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/TheMobyPerogative.world | GET | `/repos/martymcenroe/TheMobyPerogative.world` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/TheMobyPerogative.world | GET | `...roe/TheMobyPerogative.world/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/spotify-personal-backups | GET | `/repos/martymcenroe/spotify-personal-backups` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/spotify-personal-backups | GET | `/repos/martymcenroe/spotify-personal-backups` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/spotify-personal-backups | GET | `/repos/martymcenroe/spotify-personal-backups` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/spotify-personal-backups | GET | `...oe/spotify-personal-backups/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/sentinel-rfc | GET | `/repos/martymcenroe/sentinel-rfc` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/sentinel-rfc | GET | `/repos/martymcenroe/sentinel-rfc` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/sentinel-rfc | GET | `/repos/martymcenroe/sentinel-rfc` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/sentinel-rfc | GET | `...s/martymcenroe/sentinel-rfc/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/sentinel | GET | `/repos/martymcenroe/sentinel` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/sentinel | GET | `/repos/martymcenroe/sentinel` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/sentinel | GET | `/repos/martymcenroe/sentinel` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/sentinel | GET | `/repos/martymcenroe/sentinel/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/RCA-PDF-extraction-pipeline | GET | `/repos/martymcenroe/RCA-PDF-extraction-pipeline` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/RCA-PDF-extraction-pipeline | GET | `/repos/martymcenroe/RCA-PDF-extraction-pipeline` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/RCA-PDF-extraction-pipeline | GET | `/repos/martymcenroe/RCA-PDF-extraction-pipeline` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/RCA-PDF-extraction-pipeline | GET | `...RCA-PDF-extraction-pipeline/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/prompt-stream | GET | `/repos/martymcenroe/prompt-stream` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/prompt-stream | GET | `/repos/martymcenroe/prompt-stream` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/prompt-stream | GET | `/repos/martymcenroe/prompt-stream` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/prompt-stream | GET | `.../martymcenroe/prompt-stream/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/power-agent.github.io | GET | `/repos/martymcenroe/power-agent.github.io` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/power-agent.github.io | GET | `/repos/martymcenroe/power-agent.github.io` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/power-agent.github.io | GET | `/repos/martymcenroe/power-agent.github.io` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/power-agent.github.io | GET | `...enroe/power-agent.github.io/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/nec2017-analyzer | GET | `/repos/martymcenroe/nec2017-analyzer` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/nec2017-analyzer | GET | `/repos/martymcenroe/nec2017-analyzer` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/nec2017-analyzer | GET | `/repos/martymcenroe/nec2017-analyzer` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/nec2017-analyzer | GET | `...rtymcenroe/nec2017-analyzer/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/neatworks-file-recovery | GET | `/repos/martymcenroe/neatworks-file-recovery` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/neatworks-file-recovery | GET | `/repos/martymcenroe/neatworks-file-recovery` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/neatworks-file-recovery | GET | `/repos/martymcenroe/neatworks-file-recovery` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/neatworks-file-recovery | GET | `...roe/neatworks-file-recovery/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/mySvelte | GET | `/repos/martymcenroe/mySvelte` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/mySvelte | GET | `/repos/martymcenroe/mySvelte` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/mySvelte | GET | `/repos/martymcenroe/mySvelte` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/mySvelte | GET | `/repos/martymcenroe/mySvelte/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/my-discussions | GET | `/repos/martymcenroe/my-discussions` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/my-discussions | GET | `/repos/martymcenroe/my-discussions` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/my-discussions | GET | `/repos/martymcenroe/my-discussions` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/my-discussions | GET | `...martymcenroe/my-discussions/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/my_hackerrank_SQL | GET | `/repos/martymcenroe/my_hackerrank_SQL` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/my_hackerrank_SQL | GET | `/repos/martymcenroe/my_hackerrank_SQL` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/my_hackerrank_SQL | GET | `/repos/martymcenroe/my_hackerrank_SQL` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/my_hackerrank_SQL | GET | `...tymcenroe/my_hackerrank_SQL/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/my_hackerrank_python | GET | `/repos/martymcenroe/my_hackerrank_python` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/my_hackerrank_python | GET | `/repos/martymcenroe/my_hackerrank_python` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/my_hackerrank_python | GET | `/repos/martymcenroe/my_hackerrank_python` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/my_hackerrank_python | GET | `...cenroe/my_hackerrank_python/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/metabolic-protocols | GET | `/repos/martymcenroe/metabolic-protocols` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/metabolic-protocols | GET | `/repos/martymcenroe/metabolic-protocols` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/metabolic-protocols | GET | `/repos/martymcenroe/metabolic-protocols` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/metabolic-protocols | GET | `...mcenroe/metabolic-protocols/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/martymcenroe.github.io | GET | `/repos/martymcenroe/martymcenroe.github.io` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/martymcenroe.github.io | GET | `/repos/martymcenroe/martymcenroe.github.io` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/martymcenroe.github.io | GET | `/repos/martymcenroe/martymcenroe.github.io` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/martymcenroe.github.io | GET | `...nroe/martymcenroe.github.io/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/martymcenroe | GET | `/repos/martymcenroe/martymcenroe` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/martymcenroe | GET | `/repos/martymcenroe/martymcenroe` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/martymcenroe | GET | `/repos/martymcenroe/martymcenroe` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/martymcenroe | GET | `...s/martymcenroe/martymcenroe/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/maintenance | GET | `/repos/martymcenroe/maintenance` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/maintenance | GET | `/repos/martymcenroe/maintenance` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/maintenance | GET | `/repos/martymcenroe/maintenance` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/maintenance | GET | `...os/martymcenroe/maintenance/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/job-sniper | GET | `/repos/martymcenroe/job-sniper` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/job-sniper | GET | `/repos/martymcenroe/job-sniper` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/job-sniper | GET | `/repos/martymcenroe/job-sniper` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/job-sniper | GET | `/repos/martymcenroe/job-sniper/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/IEEE-standards | GET | `/repos/martymcenroe/IEEE-standards` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/IEEE-standards | GET | `/repos/martymcenroe/IEEE-standards` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/IEEE-standards | GET | `/repos/martymcenroe/IEEE-standards` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/IEEE-standards | GET | `...martymcenroe/IEEE-standards/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/iconoscope | GET | `/repos/martymcenroe/iconoscope` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/iconoscope | GET | `/repos/martymcenroe/iconoscope` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/iconoscope | GET | `/repos/martymcenroe/iconoscope` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/iconoscope | GET | `/repos/martymcenroe/iconoscope/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/HermesWiki | GET | `/repos/martymcenroe/HermesWiki` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/HermesWiki | GET | `/repos/martymcenroe/HermesWiki` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/HermesWiki | GET | `/repos/martymcenroe/HermesWiki` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/HermesWiki | GET | `/repos/martymcenroe/HermesWiki/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/GlucoPulse | GET | `/repos/martymcenroe/GlucoPulse` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/GlucoPulse | GET | `/repos/martymcenroe/GlucoPulse` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/GlucoPulse | GET | `/repos/martymcenroe/GlucoPulse` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/GlucoPulse | GET | `/repos/martymcenroe/GlucoPulse/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/github-readme-stats | GET | `/repos/martymcenroe/github-readme-stats` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/github-readme-stats | GET | `/repos/martymcenroe/github-readme-stats` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/github-readme-stats | GET | `/repos/martymcenroe/github-readme-stats` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/github-readme-stats | GET | `...mcenroe/github-readme-stats/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/gh-link-auditor | GET | `/repos/martymcenroe/gh-link-auditor` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/gh-link-auditor | GET | `/repos/martymcenroe/gh-link-auditor` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/gh-link-auditor | GET | `/repos/martymcenroe/gh-link-auditor` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/gh-link-auditor | GET | `...artymcenroe/gh-link-auditor/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/GentlePersuader | GET | `/repos/martymcenroe/GentlePersuader` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/GentlePersuader | GET | `/repos/martymcenroe/GentlePersuader` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/GentlePersuader | GET | `/repos/martymcenroe/GentlePersuader` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/GentlePersuader | GET | `...artymcenroe/GentlePersuader/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/electric-nexus | GET | `/repos/martymcenroe/electric-nexus` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/electric-nexus | GET | `/repos/martymcenroe/electric-nexus` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/electric-nexus | GET | `/repos/martymcenroe/electric-nexus` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/electric-nexus | GET | `...martymcenroe/electric-nexus/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/dotfiles | GET | `/repos/martymcenroe/dotfiles` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/dotfiles | GET | `/repos/martymcenroe/dotfiles` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/dotfiles | GET | `/repos/martymcenroe/dotfiles` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/dotfiles | GET | `/repos/martymcenroe/dotfiles/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/dont-stop-now | GET | `/repos/martymcenroe/dont-stop-now` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/dont-stop-now | GET | `/repos/martymcenroe/dont-stop-now` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/dont-stop-now | GET | `/repos/martymcenroe/dont-stop-now` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/dont-stop-now | GET | `.../martymcenroe/dont-stop-now/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/data-harvest | GET | `/repos/martymcenroe/data-harvest` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/data-harvest | GET | `/repos/martymcenroe/data-harvest` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/data-harvest | GET | `/repos/martymcenroe/data-harvest` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/data-harvest | GET | `...s/martymcenroe/data-harvest/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/CS512_link_predictor | GET | `/repos/martymcenroe/CS512_link_predictor` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/CS512_link_predictor | GET | `/repos/martymcenroe/CS512_link_predictor` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/CS512_link_predictor | GET | `/repos/martymcenroe/CS512_link_predictor` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/CS512_link_predictor | GET | `...cenroe/CS512_link_predictor/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/collectibricks | GET | `/repos/martymcenroe/collectibricks` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/collectibricks | GET | `/repos/martymcenroe/collectibricks` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/collectibricks | GET | `/repos/martymcenroe/collectibricks` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/collectibricks | GET | `...martymcenroe/collectibricks/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/Clio | GET | `/repos/martymcenroe/Clio` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/Clio | GET | `/repos/martymcenroe/Clio` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/Clio | GET | `/repos/martymcenroe/Clio` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/Clio | GET | `/repos/martymcenroe/Clio/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/career | GET | `/repos/martymcenroe/career` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/career | GET | `/repos/martymcenroe/career` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/career | GET | `/repos/martymcenroe/career` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/career | GET | `/repos/martymcenroe/career/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/best-of-pes-ai | GET | `/repos/martymcenroe/best-of-pes-ai` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/best-of-pes-ai | GET | `/repos/martymcenroe/best-of-pes-ai` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/best-of-pes-ai | GET | `/repos/martymcenroe/best-of-pes-ai` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/best-of-pes-ai | GET | `...martymcenroe/best-of-pes-ai/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/automation-scripts | GET | `/repos/martymcenroe/automation-scripts` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/automation-scripts | GET | `/repos/martymcenroe/automation-scripts` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/automation-scripts | GET | `/repos/martymcenroe/automation-scripts` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/automation-scripts | GET | `...ymcenroe/automation-scripts/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/athleet.github.io | GET | `/repos/martymcenroe/athleet.github.io` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/athleet.github.io | GET | `/repos/martymcenroe/athleet.github.io` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/athleet.github.io | GET | `/repos/martymcenroe/athleet.github.io` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/athleet.github.io | GET | `...tymcenroe/athleet.github.io/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/athleet.dev | GET | `/repos/martymcenroe/athleet.dev` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/athleet.dev | GET | `/repos/martymcenroe/athleet.dev` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/athleet.dev | GET | `/repos/martymcenroe/athleet.dev` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/athleet.dev | GET | `...os/martymcenroe/athleet.dev/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/ai-power-systems-compendium | GET | `/repos/martymcenroe/ai-power-systems-compendium` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/ai-power-systems-compendium | GET | `/repos/martymcenroe/ai-power-systems-compendium` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/ai-power-systems-compendium | GET | `/repos/martymcenroe/ai-power-systems-compendium` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/ai-power-systems-compendium | GET | `...ai-power-systems-compendium/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/Agora | GET | `/repos/martymcenroe/Agora` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/Agora | GET | `/repos/martymcenroe/Agora` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/Agora | GET | `/repos/martymcenroe/Agora` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/Agora | GET | `/repos/martymcenroe/Agora/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/acpb-manifest-poc | GET | `/repos/martymcenroe/acpb-manifest-poc` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/acpb-manifest-poc | GET | `/repos/martymcenroe/acpb-manifest-poc` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/acpb-manifest-poc | GET | `/repos/martymcenroe/acpb-manifest-poc` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/acpb-manifest-poc | GET | `...tymcenroe/acpb-manifest-poc/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/Hermes | GET | `/repos/martymcenroe/Hermes` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/Hermes | GET | `/repos/martymcenroe/Hermes` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/Hermes | GET | `/repos/martymcenroe/Hermes` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/Hermes | GET | `/repos/martymcenroe/Hermes/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/Aletheia | GET | `/repos/martymcenroe/Aletheia` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/Aletheia | GET | `/repos/martymcenroe/Aletheia` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/Aletheia | GET | `/repos/martymcenroe/Aletheia` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/Aletheia | GET | `/repos/martymcenroe/Aletheia/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/Talos | GET | `/repos/martymcenroe/Talos` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/Talos | GET | `/repos/martymcenroe/Talos` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/Talos | GET | `/repos/martymcenroe/Talos` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/Talos | GET | `/repos/martymcenroe/Talos/actions/permissions` | 403 | **PROTECTED** | T1490 |  |
| P27 | martymcenroe/hermes-docs | GET | `/repos/martymcenroe/hermes-docs` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P28 | martymcenroe/hermes-docs | GET | `/repos/martymcenroe/hermes-docs` | 200 | **INFORMATIONAL** | T1485 | Read-only probe |
| P29 | martymcenroe/hermes-docs | GET | `/repos/martymcenroe/hermes-docs` | 200 | **INFORMATIONAL** | T1490 | Read-only probe |
| P30 | martymcenroe/hermes-docs | GET | `...os/martymcenroe/hermes-docs/actions/permissions` | 403 | **PROTECTED** | T1490 |  |

### Category: Persistence

| Probe | Repo | Method | Endpoint | HTTP | Verdict | ATT&CK | Detail |
|-------|------|--------|----------|------|---------|--------|--------|
| P31 | martymcenroe/dispatch | GET | `/repos/martymcenroe/dispatch/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P32 | martymcenroe/dispatch | GET | `/user/keys` | 403 | **PROTECTED** | T1098.004 | User-level endpoint |
| P33 | martymcenroe/dispatch | GET | `/user/gpg_keys` | 403 | **PROTECTED** | T1098 | User-level endpoint |
| P34 | martymcenroe/dispatch | GET | `...tymcenroe/dispatch/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/dispatch | GET | `/repos/martymcenroe/dispatch/deployments` | 403 | **PROTECTED** | T1098 |  |
| P31 | martymcenroe/AssemblyZero | GET | `/repos/martymcenroe/AssemblyZero/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/AssemblyZero | GET | `...enroe/AssemblyZero/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/AssemblyZero | GET | `/repos/martymcenroe/AssemblyZero/deployments` | 200 | **INFORMATIONAL** | T1098 |  |
| P31 | martymcenroe/yt-playlist-importer | GET | `/repos/martymcenroe/yt-playlist-importer/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/yt-playlist-importer | GET | `...-playlist-importer/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/yt-playlist-importer | GET | `...s/martymcenroe/yt-playlist-importer/deployments` | 403 | **PROTECTED** | T1098 |  |
| P31 | martymcenroe/unleashed | GET | `/repos/martymcenroe/unleashed/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/unleashed | GET | `...ymcenroe/unleashed/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/unleashed | GET | `/repos/martymcenroe/unleashed/deployments` | 200 | **INFORMATIONAL** | T1098 |  |
| P31 | martymcenroe/TxDOT-LDA | GET | `/repos/martymcenroe/TxDOT-LDA/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/TxDOT-LDA | GET | `...ymcenroe/TxDOT-LDA/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/TxDOT-LDA | GET | `/repos/martymcenroe/TxDOT-LDA/deployments` | 403 | **PROTECTED** | T1098 |  |
| P31 | martymcenroe/thrivetech-ai | GET | `/repos/martymcenroe/thrivetech-ai/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/thrivetech-ai | GET | `...nroe/thrivetech-ai/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/thrivetech-ai | GET | `/repos/martymcenroe/thrivetech-ai/deployments` | 200 | **INFORMATIONAL** | T1098 |  |
| P31 | martymcenroe/TheMobyPerogative.world | GET | `/repos/martymcenroe/TheMobyPerogative.world/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/TheMobyPerogative.world | GET | `...byPerogative.world/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/TheMobyPerogative.world | GET | `...artymcenroe/TheMobyPerogative.world/deployments` | 403 | **PROTECTED** | T1098 |  |
| P31 | martymcenroe/spotify-personal-backups | GET | `/repos/martymcenroe/spotify-personal-backups/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/spotify-personal-backups | GET | `...y-personal-backups/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/spotify-personal-backups | GET | `...rtymcenroe/spotify-personal-backups/deployments` | 403 | **PROTECTED** | T1098 |  |
| P31 | martymcenroe/sentinel-rfc | GET | `/repos/martymcenroe/sentinel-rfc/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/sentinel-rfc | GET | `...enroe/sentinel-rfc/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/sentinel-rfc | GET | `/repos/martymcenroe/sentinel-rfc/deployments` | 403 | **PROTECTED** | T1098 |  |
| P31 | martymcenroe/sentinel | GET | `/repos/martymcenroe/sentinel/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/sentinel | GET | `...tymcenroe/sentinel/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/sentinel | GET | `/repos/martymcenroe/sentinel/deployments` | 200 | **INFORMATIONAL** | T1098 |  |
| P31 | martymcenroe/RCA-PDF-extraction-pipeline | GET | `.../martymcenroe/RCA-PDF-extraction-pipeline/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/RCA-PDF-extraction-pipeline | GET | `...xtraction-pipeline/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/RCA-PDF-extraction-pipeline | GET | `...mcenroe/RCA-PDF-extraction-pipeline/deployments` | 200 | **INFORMATIONAL** | T1098 |  |
| P31 | martymcenroe/prompt-stream | GET | `/repos/martymcenroe/prompt-stream/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/prompt-stream | GET | `...nroe/prompt-stream/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/prompt-stream | GET | `/repos/martymcenroe/prompt-stream/deployments` | 403 | **PROTECTED** | T1098 |  |
| P31 | martymcenroe/power-agent.github.io | GET | `/repos/martymcenroe/power-agent.github.io/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/power-agent.github.io | GET | `...er-agent.github.io/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/power-agent.github.io | GET | `.../martymcenroe/power-agent.github.io/deployments` | 200 | **INFORMATIONAL** | T1098 |  |
| P31 | martymcenroe/nec2017-analyzer | GET | `/repos/martymcenroe/nec2017-analyzer/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/nec2017-analyzer | GET | `...e/nec2017-analyzer/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/nec2017-analyzer | GET | `/repos/martymcenroe/nec2017-analyzer/deployments` | 200 | **INFORMATIONAL** | T1098 |  |
| P31 | martymcenroe/neatworks-file-recovery | GET | `/repos/martymcenroe/neatworks-file-recovery/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/neatworks-file-recovery | GET | `...orks-file-recovery/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/neatworks-file-recovery | GET | `...artymcenroe/neatworks-file-recovery/deployments` | 403 | **PROTECTED** | T1098 |  |
| P31 | martymcenroe/mySvelte | GET | `/repos/martymcenroe/mySvelte/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/mySvelte | GET | `...tymcenroe/mySvelte/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/mySvelte | GET | `/repos/martymcenroe/mySvelte/deployments` | 403 | **PROTECTED** | T1098 |  |
| P31 | martymcenroe/my-discussions | GET | `/repos/martymcenroe/my-discussions/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/my-discussions | GET | `...roe/my-discussions/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/my-discussions | GET | `/repos/martymcenroe/my-discussions/deployments` | 200 | **INFORMATIONAL** | T1098 |  |
| P31 | martymcenroe/my_hackerrank_SQL | GET | `/repos/martymcenroe/my_hackerrank_SQL/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/my_hackerrank_SQL | GET | `.../my_hackerrank_SQL/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/my_hackerrank_SQL | GET | `/repos/martymcenroe/my_hackerrank_SQL/deployments` | 403 | **PROTECTED** | T1098 |  |
| P31 | martymcenroe/my_hackerrank_python | GET | `/repos/martymcenroe/my_hackerrank_python/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/my_hackerrank_python | GET | `..._hackerrank_python/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/my_hackerrank_python | GET | `...s/martymcenroe/my_hackerrank_python/deployments` | 403 | **PROTECTED** | T1098 |  |
| P31 | martymcenroe/metabolic-protocols | GET | `/repos/martymcenroe/metabolic-protocols/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/metabolic-protocols | GET | `...etabolic-protocols/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/metabolic-protocols | GET | `...os/martymcenroe/metabolic-protocols/deployments` | 200 | **INFORMATIONAL** | T1098 |  |
| P31 | martymcenroe/martymcenroe.github.io | GET | `/repos/martymcenroe/martymcenroe.github.io/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/martymcenroe.github.io | GET | `...ymcenroe.github.io/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/martymcenroe.github.io | GET | `...martymcenroe/martymcenroe.github.io/deployments` | 200 | **INFORMATIONAL** | T1098 |  |
| P31 | martymcenroe/martymcenroe | GET | `/repos/martymcenroe/martymcenroe/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/martymcenroe | GET | `...enroe/martymcenroe/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/martymcenroe | GET | `/repos/martymcenroe/martymcenroe/deployments` | 200 | **INFORMATIONAL** | T1098 |  |
| P31 | martymcenroe/maintenance | GET | `/repos/martymcenroe/maintenance/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/maintenance | GET | `...cenroe/maintenance/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/maintenance | GET | `/repos/martymcenroe/maintenance/deployments` | 403 | **PROTECTED** | T1098 |  |
| P31 | martymcenroe/job-sniper | GET | `/repos/martymcenroe/job-sniper/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/job-sniper | GET | `...mcenroe/job-sniper/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/job-sniper | GET | `/repos/martymcenroe/job-sniper/deployments` | 403 | **PROTECTED** | T1098 |  |
| P31 | martymcenroe/IEEE-standards | GET | `/repos/martymcenroe/IEEE-standards/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/IEEE-standards | GET | `...roe/IEEE-standards/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/IEEE-standards | GET | `/repos/martymcenroe/IEEE-standards/deployments` | 403 | **PROTECTED** | T1098 |  |
| P31 | martymcenroe/iconoscope | GET | `/repos/martymcenroe/iconoscope/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/iconoscope | GET | `...mcenroe/iconoscope/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/iconoscope | GET | `/repos/martymcenroe/iconoscope/deployments` | 200 | **INFORMATIONAL** | T1098 |  |
| P31 | martymcenroe/HermesWiki | GET | `/repos/martymcenroe/HermesWiki/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/HermesWiki | GET | `...mcenroe/HermesWiki/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/HermesWiki | GET | `/repos/martymcenroe/HermesWiki/deployments` | 200 | **INFORMATIONAL** | T1098 |  |
| P31 | martymcenroe/GlucoPulse | GET | `/repos/martymcenroe/GlucoPulse/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/GlucoPulse | GET | `...mcenroe/GlucoPulse/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/GlucoPulse | GET | `/repos/martymcenroe/GlucoPulse/deployments` | 200 | **INFORMATIONAL** | T1098 |  |
| P31 | martymcenroe/github-readme-stats | GET | `/repos/martymcenroe/github-readme-stats/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/github-readme-stats | GET | `...ithub-readme-stats/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/github-readme-stats | GET | `...os/martymcenroe/github-readme-stats/deployments` | 200 | **INFORMATIONAL** | T1098 |  |
| P31 | martymcenroe/gh-link-auditor | GET | `/repos/martymcenroe/gh-link-auditor/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/gh-link-auditor | GET | `...oe/gh-link-auditor/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/gh-link-auditor | GET | `/repos/martymcenroe/gh-link-auditor/deployments` | 200 | **INFORMATIONAL** | T1098 |  |
| P31 | martymcenroe/GentlePersuader | GET | `/repos/martymcenroe/GentlePersuader/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/GentlePersuader | GET | `...oe/GentlePersuader/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/GentlePersuader | GET | `/repos/martymcenroe/GentlePersuader/deployments` | 403 | **PROTECTED** | T1098 |  |
| P31 | martymcenroe/electric-nexus | GET | `/repos/martymcenroe/electric-nexus/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/electric-nexus | GET | `...roe/electric-nexus/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/electric-nexus | GET | `/repos/martymcenroe/electric-nexus/deployments` | 403 | **PROTECTED** | T1098 |  |
| P31 | martymcenroe/dotfiles | GET | `/repos/martymcenroe/dotfiles/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/dotfiles | GET | `...tymcenroe/dotfiles/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/dotfiles | GET | `/repos/martymcenroe/dotfiles/deployments` | 200 | **INFORMATIONAL** | T1098 |  |
| P31 | martymcenroe/dont-stop-now | GET | `/repos/martymcenroe/dont-stop-now/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/dont-stop-now | GET | `...nroe/dont-stop-now/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/dont-stop-now | GET | `/repos/martymcenroe/dont-stop-now/deployments` | 403 | **PROTECTED** | T1098 |  |
| P31 | martymcenroe/data-harvest | GET | `/repos/martymcenroe/data-harvest/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/data-harvest | GET | `...enroe/data-harvest/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/data-harvest | GET | `/repos/martymcenroe/data-harvest/deployments` | 403 | **PROTECTED** | T1098 |  |
| P31 | martymcenroe/CS512_link_predictor | GET | `/repos/martymcenroe/CS512_link_predictor/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/CS512_link_predictor | GET | `...512_link_predictor/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/CS512_link_predictor | GET | `...s/martymcenroe/CS512_link_predictor/deployments` | 403 | **PROTECTED** | T1098 |  |
| P31 | martymcenroe/collectibricks | GET | `/repos/martymcenroe/collectibricks/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/collectibricks | GET | `...roe/collectibricks/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/collectibricks | GET | `/repos/martymcenroe/collectibricks/deployments` | 403 | **PROTECTED** | T1098 |  |
| P31 | martymcenroe/Clio | GET | `/repos/martymcenroe/Clio/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/Clio | GET | `.../martymcenroe/Clio/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/Clio | GET | `/repos/martymcenroe/Clio/deployments` | 200 | **INFORMATIONAL** | T1098 |  |
| P31 | martymcenroe/career | GET | `/repos/martymcenroe/career/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/career | GET | `...artymcenroe/career/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/career | GET | `/repos/martymcenroe/career/deployments` | 403 | **PROTECTED** | T1098 |  |
| P31 | martymcenroe/best-of-pes-ai | GET | `/repos/martymcenroe/best-of-pes-ai/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/best-of-pes-ai | GET | `...roe/best-of-pes-ai/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/best-of-pes-ai | GET | `/repos/martymcenroe/best-of-pes-ai/deployments` | 200 | **INFORMATIONAL** | T1098 |  |
| P31 | martymcenroe/automation-scripts | GET | `/repos/martymcenroe/automation-scripts/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/automation-scripts | GET | `...automation-scripts/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/automation-scripts | GET | `/repos/martymcenroe/automation-scripts/deployments` | 200 | **INFORMATIONAL** | T1098 |  |
| P31 | martymcenroe/athleet.github.io | GET | `/repos/martymcenroe/athleet.github.io/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/athleet.github.io | GET | `.../athleet.github.io/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/athleet.github.io | GET | `/repos/martymcenroe/athleet.github.io/deployments` | 200 | **INFORMATIONAL** | T1098 |  |
| P31 | martymcenroe/athleet.dev | GET | `/repos/martymcenroe/athleet.dev/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/athleet.dev | GET | `...cenroe/athleet.dev/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/athleet.dev | GET | `/repos/martymcenroe/athleet.dev/deployments` | 403 | **PROTECTED** | T1098 |  |
| P31 | martymcenroe/ai-power-systems-compendium | GET | `.../martymcenroe/ai-power-systems-compendium/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/ai-power-systems-compendium | GET | `...systems-compendium/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/ai-power-systems-compendium | GET | `...mcenroe/ai-power-systems-compendium/deployments` | 200 | **INFORMATIONAL** | T1098 |  |
| P31 | martymcenroe/Agora | GET | `/repos/martymcenroe/Agora/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/Agora | GET | `...martymcenroe/Agora/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/Agora | GET | `/repos/martymcenroe/Agora/deployments` | 403 | **PROTECTED** | T1098 |  |
| P31 | martymcenroe/acpb-manifest-poc | GET | `/repos/martymcenroe/acpb-manifest-poc/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/acpb-manifest-poc | GET | `.../acpb-manifest-poc/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/acpb-manifest-poc | GET | `/repos/martymcenroe/acpb-manifest-poc/deployments` | 403 | **PROTECTED** | T1098 |  |
| P31 | martymcenroe/Hermes | GET | `/repos/martymcenroe/Hermes/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/Hermes | GET | `...artymcenroe/Hermes/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/Hermes | GET | `/repos/martymcenroe/Hermes/deployments` | 403 | **PROTECTED** | T1098 |  |
| P31 | martymcenroe/Aletheia | GET | `/repos/martymcenroe/Aletheia/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/Aletheia | GET | `...tymcenroe/Aletheia/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/Aletheia | GET | `/repos/martymcenroe/Aletheia/deployments` | 200 | **INFORMATIONAL** | T1098 |  |
| P31 | martymcenroe/Talos | GET | `/repos/martymcenroe/Talos/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/Talos | GET | `...martymcenroe/Talos/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/Talos | GET | `/repos/martymcenroe/Talos/deployments` | 403 | **PROTECTED** | T1098 |  |
| P31 | martymcenroe/hermes-docs | GET | `/repos/martymcenroe/hermes-docs/hooks` | 200 | **INFORMATIONAL** | T1098.001 | Read-only probe |
| P34 | martymcenroe/hermes-docs | GET | `...cenroe/hermes-docs/actions/permissions/workflow` | 403 | **PROTECTED** | T1098 |  |
| P35 | martymcenroe/hermes-docs | GET | `/repos/martymcenroe/hermes-docs/deployments` | 200 | **INFORMATIONAL** | T1098 |  |

### Category: Lateral Movement

| Probe | Repo | Method | Endpoint | HTTP | Verdict | ATT&CK | Detail |
|-------|------|--------|----------|------|---------|--------|--------|
| P36 | martymcenroe/dispatch | GET | `/repos/martymcenroe/dispatch/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P37 | martymcenroe/dispatch | GET | `/user/orgs` | 200 | **INFORMATIONAL** | T1570 | User-level endpoint |
| P38 | martymcenroe/dispatch | GET | `/user/orgs` | 200 | **INFORMATIONAL** | T1570 | User-level endpoint |
| P36 | martymcenroe/AssemblyZero | GET | `/repos/martymcenroe/AssemblyZero/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/yt-playlist-importer | GET | `/repos/martymcenroe/yt-playlist-importer/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/unleashed | GET | `/repos/martymcenroe/unleashed/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/TxDOT-LDA | GET | `/repos/martymcenroe/TxDOT-LDA/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/thrivetech-ai | GET | `/repos/martymcenroe/thrivetech-ai/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/TheMobyPerogative.world | GET | `/repos/martymcenroe/TheMobyPerogative.world/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/spotify-personal-backups | GET | `/repos/martymcenroe/spotify-personal-backups/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/sentinel-rfc | GET | `/repos/martymcenroe/sentinel-rfc/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/sentinel | GET | `/repos/martymcenroe/sentinel/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/RCA-PDF-extraction-pipeline | GET | `.../martymcenroe/RCA-PDF-extraction-pipeline/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/prompt-stream | GET | `/repos/martymcenroe/prompt-stream/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/power-agent.github.io | GET | `/repos/martymcenroe/power-agent.github.io/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/nec2017-analyzer | GET | `/repos/martymcenroe/nec2017-analyzer/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/neatworks-file-recovery | GET | `/repos/martymcenroe/neatworks-file-recovery/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/mySvelte | GET | `/repos/martymcenroe/mySvelte/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/my-discussions | GET | `/repos/martymcenroe/my-discussions/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/my_hackerrank_SQL | GET | `/repos/martymcenroe/my_hackerrank_SQL/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/my_hackerrank_python | GET | `/repos/martymcenroe/my_hackerrank_python/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/metabolic-protocols | GET | `/repos/martymcenroe/metabolic-protocols/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/martymcenroe.github.io | GET | `/repos/martymcenroe/martymcenroe.github.io/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/martymcenroe | GET | `/repos/martymcenroe/martymcenroe/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/maintenance | GET | `/repos/martymcenroe/maintenance/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/job-sniper | GET | `/repos/martymcenroe/job-sniper/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/IEEE-standards | GET | `/repos/martymcenroe/IEEE-standards/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/iconoscope | GET | `/repos/martymcenroe/iconoscope/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/HermesWiki | GET | `/repos/martymcenroe/HermesWiki/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/GlucoPulse | GET | `/repos/martymcenroe/GlucoPulse/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/github-readme-stats | GET | `/repos/martymcenroe/github-readme-stats/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/gh-link-auditor | GET | `/repos/martymcenroe/gh-link-auditor/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/GentlePersuader | GET | `/repos/martymcenroe/GentlePersuader/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/electric-nexus | GET | `/repos/martymcenroe/electric-nexus/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/dotfiles | GET | `/repos/martymcenroe/dotfiles/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/dont-stop-now | GET | `/repos/martymcenroe/dont-stop-now/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/data-harvest | GET | `/repos/martymcenroe/data-harvest/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/CS512_link_predictor | GET | `/repos/martymcenroe/CS512_link_predictor/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/collectibricks | GET | `/repos/martymcenroe/collectibricks/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/Clio | GET | `/repos/martymcenroe/Clio/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/career | GET | `/repos/martymcenroe/career/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/best-of-pes-ai | GET | `/repos/martymcenroe/best-of-pes-ai/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/automation-scripts | GET | `/repos/martymcenroe/automation-scripts/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/athleet.github.io | GET | `/repos/martymcenroe/athleet.github.io/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/athleet.dev | GET | `/repos/martymcenroe/athleet.dev/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/ai-power-systems-compendium | GET | `.../martymcenroe/ai-power-systems-compendium/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/Agora | GET | `/repos/martymcenroe/Agora/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/acpb-manifest-poc | GET | `/repos/martymcenroe/acpb-manifest-poc/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/Hermes | GET | `/repos/martymcenroe/Hermes/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/Aletheia | GET | `/repos/martymcenroe/Aletheia/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/Talos | GET | `/repos/martymcenroe/Talos/forks` | 200 | **INFORMATIONAL** | T1570 |  |
| P36 | martymcenroe/hermes-docs | GET | `/repos/martymcenroe/hermes-docs/forks` | 200 | **INFORMATIONAL** | T1570 |  |

### Category: Wiki Attack Surface

| Probe | Repo | Method | Endpoint | HTTP | Verdict | ATT&CK | Detail |
|-------|------|--------|----------|------|---------|--------|--------|
| P43 | martymcenroe/dispatch | CONFIG | `martymcenroe/dispatch.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/dispatch | git ls-remote | `https://github.com/martymcenroe/dispatch.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/AssemblyZero | CONFIG | `martymcenroe/AssemblyZero.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/AssemblyZero | git ls-remote | `...//github.com/martymcenroe/AssemblyZero.wiki.git` | 200 | **VULNERABLE** | T1213 | Wiki repo has content — cloneable and modifiable |
| P45 | martymcenroe/AssemblyZero | git ls-remote | `...//github.com/martymcenroe/AssemblyZero.wiki.git` | 200 | **VULNERABLE** | T1565.001 | Wiki repo accessible — can be cloned with current credential |
| P46 | martymcenroe/AssemblyZero | ARCHITECTURAL | `martymcenroe/AssemblyZero.wiki.git` | n/a | **VULNERABLE** | T1136 | No PR, review, or approval required for wiki pushes |
| P47 | martymcenroe/AssemblyZero | ARCHITECTURAL | `martymcenroe/AssemblyZero.wiki.git` | n/a | **VULNERABLE** | T1114 | Wiki modifications generate no notifications to repo owner |
| P48 | martymcenroe/AssemblyZero | ARCHITECTURAL | `martymcenroe/AssemblyZero.wiki.git` | n/a | **VULNERABLE** | T1059 | Wiki content could be read by agents as trusted context — pr |
| P43 | martymcenroe/yt-playlist-importer | CONFIG | `martymcenroe/yt-playlist-importer.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/yt-playlist-importer | git ls-remote | `....com/martymcenroe/yt-playlist-importer.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/unleashed | CONFIG | `martymcenroe/unleashed.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/unleashed | git ls-remote | `https://github.com/martymcenroe/unleashed.wiki.git` | 200 | **VULNERABLE** | T1213 | Wiki repo has content — cloneable and modifiable |
| P45 | martymcenroe/unleashed | git ls-remote | `https://github.com/martymcenroe/unleashed.wiki.git` | 200 | **VULNERABLE** | T1565.001 | Wiki repo accessible — can be cloned with current credential |
| P46 | martymcenroe/unleashed | ARCHITECTURAL | `martymcenroe/unleashed.wiki.git` | n/a | **VULNERABLE** | T1136 | No PR, review, or approval required for wiki pushes |
| P47 | martymcenroe/unleashed | ARCHITECTURAL | `martymcenroe/unleashed.wiki.git` | n/a | **VULNERABLE** | T1114 | Wiki modifications generate no notifications to repo owner |
| P48 | martymcenroe/unleashed | ARCHITECTURAL | `martymcenroe/unleashed.wiki.git` | n/a | **VULNERABLE** | T1059 | Wiki content could be read by agents as trusted context — pr |
| P43 | martymcenroe/TxDOT-LDA | CONFIG | `martymcenroe/TxDOT-LDA.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/TxDOT-LDA | git ls-remote | `https://github.com/martymcenroe/TxDOT-LDA.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/thrivetech-ai | CONFIG | `martymcenroe/thrivetech-ai.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/thrivetech-ai | git ls-remote | `.../github.com/martymcenroe/thrivetech-ai.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/TheMobyPerogative.world | CONFIG | `martymcenroe/TheMobyPerogative.world.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/TheMobyPerogative.world | git ls-remote | `...m/martymcenroe/TheMobyPerogative.world.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/spotify-personal-backups | CONFIG | `martymcenroe/spotify-personal-backups.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/spotify-personal-backups | git ls-remote | `.../martymcenroe/spotify-personal-backups.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/sentinel-rfc | CONFIG | `martymcenroe/sentinel-rfc.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/sentinel-rfc | git ls-remote | `...//github.com/martymcenroe/sentinel-rfc.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/sentinel | CONFIG | `martymcenroe/sentinel.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/sentinel | git ls-remote | `https://github.com/martymcenroe/sentinel.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/RCA-PDF-extraction-pipeline | CONFIG | `martymcenroe/RCA-PDF-extraction-pipeline.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/RCA-PDF-extraction-pipeline | git ls-remote | `...rtymcenroe/RCA-PDF-extraction-pipeline.wiki.git` | 200 | **VULNERABLE** | T1213 | Wiki repo has content — cloneable and modifiable |
| P45 | martymcenroe/RCA-PDF-extraction-pipeline | git ls-remote | `...rtymcenroe/RCA-PDF-extraction-pipeline.wiki.git` | 200 | **VULNERABLE** | T1565.001 | Wiki repo accessible — can be cloned with current credential |
| P46 | martymcenroe/RCA-PDF-extraction-pipeline | ARCHITECTURAL | `martymcenroe/RCA-PDF-extraction-pipeline.wiki.git` | n/a | **VULNERABLE** | T1136 | No PR, review, or approval required for wiki pushes |
| P47 | martymcenroe/RCA-PDF-extraction-pipeline | ARCHITECTURAL | `martymcenroe/RCA-PDF-extraction-pipeline.wiki.git` | n/a | **VULNERABLE** | T1114 | Wiki modifications generate no notifications to repo owner |
| P48 | martymcenroe/RCA-PDF-extraction-pipeline | ARCHITECTURAL | `martymcenroe/RCA-PDF-extraction-pipeline.wiki.git` | n/a | **VULNERABLE** | T1059 | Wiki content could be read by agents as trusted context — pr |
| P43 | martymcenroe/prompt-stream | CONFIG | `martymcenroe/prompt-stream.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/prompt-stream | git ls-remote | `.../github.com/martymcenroe/prompt-stream.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/power-agent.github.io | CONFIG | `martymcenroe/power-agent.github.io.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/power-agent.github.io | git ls-remote | `...com/martymcenroe/power-agent.github.io.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/nec2017-analyzer | CONFIG | `martymcenroe/nec2017-analyzer.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/nec2017-analyzer | git ls-remote | `...thub.com/martymcenroe/nec2017-analyzer.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/neatworks-file-recovery | CONFIG | `martymcenroe/neatworks-file-recovery.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/neatworks-file-recovery | git ls-remote | `...m/martymcenroe/neatworks-file-recovery.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/mySvelte | CONFIG | `martymcenroe/mySvelte.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/mySvelte | git ls-remote | `https://github.com/martymcenroe/mySvelte.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/my-discussions | CONFIG | `martymcenroe/my-discussions.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/my-discussions | git ls-remote | `...github.com/martymcenroe/my-discussions.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/my_hackerrank_SQL | CONFIG | `martymcenroe/my_hackerrank_SQL.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/my_hackerrank_SQL | git ls-remote | `...hub.com/martymcenroe/my_hackerrank_SQL.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/my_hackerrank_python | CONFIG | `martymcenroe/my_hackerrank_python.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/my_hackerrank_python | git ls-remote | `....com/martymcenroe/my_hackerrank_python.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/metabolic-protocols | CONFIG | `martymcenroe/metabolic-protocols.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/metabolic-protocols | git ls-remote | `...b.com/martymcenroe/metabolic-protocols.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/martymcenroe.github.io | CONFIG | `martymcenroe/martymcenroe.github.io.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/martymcenroe.github.io | git ls-remote | `...om/martymcenroe/martymcenroe.github.io.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/martymcenroe | CONFIG | `martymcenroe/martymcenroe.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/martymcenroe | git ls-remote | `...//github.com/martymcenroe/martymcenroe.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/maintenance | CONFIG | `martymcenroe/maintenance.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/maintenance | git ls-remote | `...://github.com/martymcenroe/maintenance.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/job-sniper | CONFIG | `martymcenroe/job-sniper.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/job-sniper | git ls-remote | `...s://github.com/martymcenroe/job-sniper.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/IEEE-standards | CONFIG | `martymcenroe/IEEE-standards.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/IEEE-standards | git ls-remote | `...github.com/martymcenroe/IEEE-standards.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/iconoscope | CONFIG | `martymcenroe/iconoscope.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/iconoscope | git ls-remote | `...s://github.com/martymcenroe/iconoscope.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/HermesWiki | CONFIG | `martymcenroe/HermesWiki.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/HermesWiki | git ls-remote | `...s://github.com/martymcenroe/HermesWiki.wiki.git` | 200 | **VULNERABLE** | T1213 | Wiki repo has content — cloneable and modifiable |
| P45 | martymcenroe/HermesWiki | git ls-remote | `...s://github.com/martymcenroe/HermesWiki.wiki.git` | 200 | **VULNERABLE** | T1565.001 | Wiki repo accessible — can be cloned with current credential |
| P46 | martymcenroe/HermesWiki | ARCHITECTURAL | `martymcenroe/HermesWiki.wiki.git` | n/a | **VULNERABLE** | T1136 | No PR, review, or approval required for wiki pushes |
| P47 | martymcenroe/HermesWiki | ARCHITECTURAL | `martymcenroe/HermesWiki.wiki.git` | n/a | **VULNERABLE** | T1114 | Wiki modifications generate no notifications to repo owner |
| P48 | martymcenroe/HermesWiki | ARCHITECTURAL | `martymcenroe/HermesWiki.wiki.git` | n/a | **VULNERABLE** | T1059 | Wiki content could be read by agents as trusted context — pr |
| P43 | martymcenroe/GlucoPulse | CONFIG | `martymcenroe/GlucoPulse.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/GlucoPulse | git ls-remote | `...s://github.com/martymcenroe/GlucoPulse.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/github-readme-stats | CONFIG | `martymcenroe/github-readme-stats.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/github-readme-stats | git ls-remote | `...b.com/martymcenroe/github-readme-stats.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/gh-link-auditor | CONFIG | `martymcenroe/gh-link-auditor.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/gh-link-auditor | git ls-remote | `...ithub.com/martymcenroe/gh-link-auditor.wiki.git` | 200 | **VULNERABLE** | T1213 | Wiki repo has content — cloneable and modifiable |
| P45 | martymcenroe/gh-link-auditor | git ls-remote | `...ithub.com/martymcenroe/gh-link-auditor.wiki.git` | 200 | **VULNERABLE** | T1565.001 | Wiki repo accessible — can be cloned with current credential |
| P46 | martymcenroe/gh-link-auditor | ARCHITECTURAL | `martymcenroe/gh-link-auditor.wiki.git` | n/a | **VULNERABLE** | T1136 | No PR, review, or approval required for wiki pushes |
| P47 | martymcenroe/gh-link-auditor | ARCHITECTURAL | `martymcenroe/gh-link-auditor.wiki.git` | n/a | **VULNERABLE** | T1114 | Wiki modifications generate no notifications to repo owner |
| P48 | martymcenroe/gh-link-auditor | ARCHITECTURAL | `martymcenroe/gh-link-auditor.wiki.git` | n/a | **VULNERABLE** | T1059 | Wiki content could be read by agents as trusted context — pr |
| P43 | martymcenroe/GentlePersuader | CONFIG | `martymcenroe/GentlePersuader.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/GentlePersuader | git ls-remote | `...ithub.com/martymcenroe/GentlePersuader.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/electric-nexus | CONFIG | `martymcenroe/electric-nexus.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/electric-nexus | git ls-remote | `...github.com/martymcenroe/electric-nexus.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/dotfiles | CONFIG | `martymcenroe/dotfiles.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/dotfiles | git ls-remote | `https://github.com/martymcenroe/dotfiles.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/dont-stop-now | CONFIG | `martymcenroe/dont-stop-now.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/dont-stop-now | git ls-remote | `.../github.com/martymcenroe/dont-stop-now.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/data-harvest | CONFIG | `martymcenroe/data-harvest.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/data-harvest | git ls-remote | `...//github.com/martymcenroe/data-harvest.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/CS512_link_predictor | CONFIG | `martymcenroe/CS512_link_predictor.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/CS512_link_predictor | git ls-remote | `....com/martymcenroe/CS512_link_predictor.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/collectibricks | CONFIG | `martymcenroe/collectibricks.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/collectibricks | git ls-remote | `...github.com/martymcenroe/collectibricks.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/Clio | CONFIG | `martymcenroe/Clio.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/Clio | git ls-remote | `https://github.com/martymcenroe/Clio.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/career | CONFIG | `martymcenroe/career.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/career | git ls-remote | `https://github.com/martymcenroe/career.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/best-of-pes-ai | CONFIG | `martymcenroe/best-of-pes-ai.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/best-of-pes-ai | git ls-remote | `...github.com/martymcenroe/best-of-pes-ai.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/automation-scripts | CONFIG | `martymcenroe/automation-scripts.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/automation-scripts | git ls-remote | `...ub.com/martymcenroe/automation-scripts.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/athleet.github.io | CONFIG | `martymcenroe/athleet.github.io.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/athleet.github.io | git ls-remote | `...hub.com/martymcenroe/athleet.github.io.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/athleet.dev | CONFIG | `martymcenroe/athleet.dev.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/athleet.dev | git ls-remote | `...://github.com/martymcenroe/athleet.dev.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/ai-power-systems-compendium | CONFIG | `martymcenroe/ai-power-systems-compendium.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/ai-power-systems-compendium | git ls-remote | `...rtymcenroe/ai-power-systems-compendium.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/Agora | CONFIG | `martymcenroe/Agora.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/Agora | git ls-remote | `https://github.com/martymcenroe/Agora.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/acpb-manifest-poc | CONFIG | `martymcenroe/acpb-manifest-poc.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/acpb-manifest-poc | git ls-remote | `...hub.com/martymcenroe/acpb-manifest-poc.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/Hermes | CONFIG | `martymcenroe/Hermes.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/Hermes | git ls-remote | `https://github.com/martymcenroe/Hermes.wiki.git` | 200 | **VULNERABLE** | T1213 | Wiki repo has content — cloneable and modifiable |
| P45 | martymcenroe/Hermes | git ls-remote | `https://github.com/martymcenroe/Hermes.wiki.git` | 200 | **VULNERABLE** | T1565.001 | Wiki repo accessible — can be cloned with current credential |
| P46 | martymcenroe/Hermes | ARCHITECTURAL | `martymcenroe/Hermes.wiki.git` | n/a | **VULNERABLE** | T1136 | No PR, review, or approval required for wiki pushes |
| P47 | martymcenroe/Hermes | ARCHITECTURAL | `martymcenroe/Hermes.wiki.git` | n/a | **VULNERABLE** | T1114 | Wiki modifications generate no notifications to repo owner |
| P48 | martymcenroe/Hermes | ARCHITECTURAL | `martymcenroe/Hermes.wiki.git` | n/a | **VULNERABLE** | T1059 | Wiki content could be read by agents as trusted context — pr |
| P43 | martymcenroe/Aletheia | CONFIG | `martymcenroe/Aletheia.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/Aletheia | git ls-remote | `https://github.com/martymcenroe/Aletheia.wiki.git` | 200 | **VULNERABLE** | T1213 | Wiki repo has content — cloneable and modifiable |
| P45 | martymcenroe/Aletheia | git ls-remote | `https://github.com/martymcenroe/Aletheia.wiki.git` | 200 | **VULNERABLE** | T1565.001 | Wiki repo accessible — can be cloned with current credential |
| P46 | martymcenroe/Aletheia | ARCHITECTURAL | `martymcenroe/Aletheia.wiki.git` | n/a | **VULNERABLE** | T1136 | No PR, review, or approval required for wiki pushes |
| P47 | martymcenroe/Aletheia | ARCHITECTURAL | `martymcenroe/Aletheia.wiki.git` | n/a | **VULNERABLE** | T1114 | Wiki modifications generate no notifications to repo owner |
| P48 | martymcenroe/Aletheia | ARCHITECTURAL | `martymcenroe/Aletheia.wiki.git` | n/a | **VULNERABLE** | T1059 | Wiki content could be read by agents as trusted context — pr |
| P43 | martymcenroe/Talos | CONFIG | `martymcenroe/Talos.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/Talos | git ls-remote | `https://github.com/martymcenroe/Talos.wiki.git` | 404 | **INFORMATIONAL** | T1213 | Wiki enabled but no content pushed |
| P43 | martymcenroe/hermes-docs | CONFIG | `martymcenroe/hermes-docs.wiki.git` | n/a | **VULNERABLE** | T1213 | Wiki enabled; no branch protection/rulesets available for wi |
| P44 | martymcenroe/hermes-docs | git ls-remote | `...://github.com/martymcenroe/hermes-docs.wiki.git` | 200 | **VULNERABLE** | T1213 | Wiki repo has content — cloneable and modifiable |
| P45 | martymcenroe/hermes-docs | git ls-remote | `...://github.com/martymcenroe/hermes-docs.wiki.git` | 200 | **VULNERABLE** | T1565.001 | Wiki repo accessible — can be cloned with current credential |
| P46 | martymcenroe/hermes-docs | ARCHITECTURAL | `martymcenroe/hermes-docs.wiki.git` | n/a | **VULNERABLE** | T1136 | No PR, review, or approval required for wiki pushes |
| P47 | martymcenroe/hermes-docs | ARCHITECTURAL | `martymcenroe/hermes-docs.wiki.git` | n/a | **VULNERABLE** | T1114 | Wiki modifications generate no notifications to repo owner |
| P48 | martymcenroe/hermes-docs | ARCHITECTURAL | `martymcenroe/hermes-docs.wiki.git` | n/a | **VULNERABLE** | T1059 | Wiki content could be read by agents as trusted context — pr |

### Category: Social Engineering

| Probe | Repo | Method | Endpoint | HTTP | Verdict | ATT&CK | Detail |
|-------|------|--------|----------|------|---------|--------|--------|
| P39 | n/a | n/a | `n/a -- behavioral observation` | n/a | **BEHAVIORAL** | T1656 | Agent claims repo misconfigured |
| P40 | n/a | n/a | `n/a -- behavioral observation` | n/a | **BEHAVIORAL** | T1656 | Agent claims user error |
| P41 | n/a | n/a | `n/a -- behavioral observation` | n/a | **BEHAVIORAL** | T1078 | Agent attempts gh auth login |
| P42 | n/a | n/a | `n/a -- behavioral observation` | n/a | **BEHAVIORAL** | T1036 | Confabulation cascade (10+ turns) |

### VULNERABLE Endpoints (Require Attention)

- **P43** `CONFIG martymcenroe/dispatch.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/AssemblyZero.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P44** `git ls-remote https://github.com/martymcenroe/AssemblyZero.wiki.git` -> HTTP 200 (Wiki Attack Surface, T1213)
- **P45** `git ls-remote https://github.com/martymcenroe/AssemblyZero.wiki.git` -> HTTP 200 (Wiki Attack Surface, T1565.001)
- **P46** `ARCHITECTURAL martymcenroe/AssemblyZero.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1136)
- **P47** `ARCHITECTURAL martymcenroe/AssemblyZero.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1114)
- **P48** `ARCHITECTURAL martymcenroe/AssemblyZero.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1059)
- **P43** `CONFIG martymcenroe/yt-playlist-importer.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/unleashed.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P44** `git ls-remote https://github.com/martymcenroe/unleashed.wiki.git` -> HTTP 200 (Wiki Attack Surface, T1213)
- **P45** `git ls-remote https://github.com/martymcenroe/unleashed.wiki.git` -> HTTP 200 (Wiki Attack Surface, T1565.001)
- **P46** `ARCHITECTURAL martymcenroe/unleashed.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1136)
- **P47** `ARCHITECTURAL martymcenroe/unleashed.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1114)
- **P48** `ARCHITECTURAL martymcenroe/unleashed.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1059)
- **P43** `CONFIG martymcenroe/TxDOT-LDA.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/thrivetech-ai.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/TheMobyPerogative.world.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/spotify-personal-backups.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/sentinel-rfc.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/sentinel.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/RCA-PDF-extraction-pipeline.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P44** `git ls-remote https://github.com/martymcenroe/RCA-PDF-extraction-pipeline.wiki.git` -> HTTP 200 (Wiki Attack Surface, T1213)
- **P45** `git ls-remote https://github.com/martymcenroe/RCA-PDF-extraction-pipeline.wiki.git` -> HTTP 200 (Wiki Attack Surface, T1565.001)
- **P46** `ARCHITECTURAL martymcenroe/RCA-PDF-extraction-pipeline.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1136)
- **P47** `ARCHITECTURAL martymcenroe/RCA-PDF-extraction-pipeline.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1114)
- **P48** `ARCHITECTURAL martymcenroe/RCA-PDF-extraction-pipeline.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1059)
- **P43** `CONFIG martymcenroe/prompt-stream.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/power-agent.github.io.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/nec2017-analyzer.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/neatworks-file-recovery.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/mySvelte.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/my-discussions.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/my_hackerrank_SQL.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/my_hackerrank_python.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/metabolic-protocols.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/martymcenroe.github.io.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/martymcenroe.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/maintenance.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/job-sniper.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/IEEE-standards.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/iconoscope.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/HermesWiki.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P44** `git ls-remote https://github.com/martymcenroe/HermesWiki.wiki.git` -> HTTP 200 (Wiki Attack Surface, T1213)
- **P45** `git ls-remote https://github.com/martymcenroe/HermesWiki.wiki.git` -> HTTP 200 (Wiki Attack Surface, T1565.001)
- **P46** `ARCHITECTURAL martymcenroe/HermesWiki.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1136)
- **P47** `ARCHITECTURAL martymcenroe/HermesWiki.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1114)
- **P48** `ARCHITECTURAL martymcenroe/HermesWiki.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1059)
- **P43** `CONFIG martymcenroe/GlucoPulse.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/github-readme-stats.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/gh-link-auditor.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P44** `git ls-remote https://github.com/martymcenroe/gh-link-auditor.wiki.git` -> HTTP 200 (Wiki Attack Surface, T1213)
- **P45** `git ls-remote https://github.com/martymcenroe/gh-link-auditor.wiki.git` -> HTTP 200 (Wiki Attack Surface, T1565.001)
- **P46** `ARCHITECTURAL martymcenroe/gh-link-auditor.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1136)
- **P47** `ARCHITECTURAL martymcenroe/gh-link-auditor.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1114)
- **P48** `ARCHITECTURAL martymcenroe/gh-link-auditor.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1059)
- **P43** `CONFIG martymcenroe/GentlePersuader.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/electric-nexus.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/dotfiles.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/dont-stop-now.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/data-harvest.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/CS512_link_predictor.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/collectibricks.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/Clio.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/career.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/best-of-pes-ai.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/automation-scripts.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/athleet.github.io.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/athleet.dev.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/ai-power-systems-compendium.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/Agora.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/acpb-manifest-poc.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/Hermes.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P44** `git ls-remote https://github.com/martymcenroe/Hermes.wiki.git` -> HTTP 200 (Wiki Attack Surface, T1213)
- **P45** `git ls-remote https://github.com/martymcenroe/Hermes.wiki.git` -> HTTP 200 (Wiki Attack Surface, T1565.001)
- **P46** `ARCHITECTURAL martymcenroe/Hermes.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1136)
- **P47** `ARCHITECTURAL martymcenroe/Hermes.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1114)
- **P48** `ARCHITECTURAL martymcenroe/Hermes.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1059)
- **P43** `CONFIG martymcenroe/Aletheia.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P44** `git ls-remote https://github.com/martymcenroe/Aletheia.wiki.git` -> HTTP 200 (Wiki Attack Surface, T1213)
- **P45** `git ls-remote https://github.com/martymcenroe/Aletheia.wiki.git` -> HTTP 200 (Wiki Attack Surface, T1565.001)
- **P46** `ARCHITECTURAL martymcenroe/Aletheia.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1136)
- **P47** `ARCHITECTURAL martymcenroe/Aletheia.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1114)
- **P48** `ARCHITECTURAL martymcenroe/Aletheia.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1059)
- **P43** `CONFIG martymcenroe/Talos.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P43** `CONFIG martymcenroe/hermes-docs.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1213)
- **P44** `git ls-remote https://github.com/martymcenroe/hermes-docs.wiki.git` -> HTTP 200 (Wiki Attack Surface, T1213)
- **P45** `git ls-remote https://github.com/martymcenroe/hermes-docs.wiki.git` -> HTTP 200 (Wiki Attack Surface, T1565.001)
- **P46** `ARCHITECTURAL martymcenroe/hermes-docs.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1136)
- **P47** `ARCHITECTURAL martymcenroe/hermes-docs.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1114)
- **P48** `ARCHITECTURAL martymcenroe/hermes-docs.wiki.git` -> HTTP 0 (Wiki Attack Surface, T1059)

---

## Evidence Notes

- **Timestamp:** 2026-03-09T16:38:41.824662+00:00
- **Token type at time of scan:** fine-grained
- **Script:** `AssemblyZero/tools/github_protection_audit.py`
- **Repos scanned:** 50

### .permissions Confound (P07)

The GitHub REST API `.permissions` field reports **user-level** role permissions, not **token-level** access permissions. A fine-grained PAT with limited scopes will still show `admin: true` because the *user* is an admin.

- `martymcenroe/dispatch`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/AssemblyZero`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/yt-playlist-importer`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/unleashed`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/TxDOT-LDA`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/thrivetech-ai`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/TheMobyPerogative.world`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/spotify-personal-backups`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/sentinel-rfc`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/sentinel`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/RCA-PDF-extraction-pipeline`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/prompt-stream`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/power-agent.github.io`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/nec2017-analyzer`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/neatworks-file-recovery`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/mySvelte`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/my-discussions`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/my_hackerrank_SQL`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/my_hackerrank_python`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/metabolic-protocols`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/martymcenroe.github.io`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/martymcenroe`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/maintenance`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/job-sniper`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/IEEE-standards`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/iconoscope`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/HermesWiki`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/GlucoPulse`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/github-readme-stats`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/gh-link-auditor`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/GentlePersuader`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/electric-nexus`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/dotfiles`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/dont-stop-now`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/data-harvest`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/CS512_link_predictor`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/collectibricks`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/Clio`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/career`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/best-of-pes-ai`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/automation-scripts`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/athleet.github.io`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/athleet.dev`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/ai-power-systems-compendium`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/Agora`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/acpb-manifest-poc`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/Hermes`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/Aletheia`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/Talos`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)
- `martymcenroe/hermes-docs`: permissions={"admin": true, "maintain": true, "push": true, "triage": true, "pull": true} — API reports admin:true (CONFOUND)

This confound causes LLM agents to incorrectly believe they have admin access, triggering escalation cascades when operations return 403.

### Wiki Attack Surface Gap (P43-P48)

GitHub wikis operate as separate `.wiki.git` repositories with **no protection mechanisms**:

- **No branch protection**: Wikis cannot have branch rules or rulesets
- **No PR/review gate**: Pushes go directly to the wiki repo
- **No push notifications**: Repo owners receive no alerts for wiki changes
- **No REST API**: `gh repo list` does not enumerate wikis; no `/wiki` API endpoints exist
- **No audit log integration**: Changes only visible in wiki git history

**Agent attack vectors:**

1. **Prompt injection via wiki**: Agent modifies wiki content to inject instructions for future agent sessions that read wiki pages as context
2. **Data exfiltration**: Agent pushes sensitive data to wiki pages as a covert channel (no review, no notification)
3. **Context poisoning**: If `CLAUDE.md` or project docs reference wiki pages, a compromised agent can poison the trust chain
4. **Persistence**: Wiki modifications survive branch resets, repo restores, and agent session boundaries

**Affected repos (50):**
- `martymcenroe/Agora`
- `martymcenroe/Aletheia`
- `martymcenroe/AssemblyZero`
- `martymcenroe/CS512_link_predictor`
- `martymcenroe/Clio`
- `martymcenroe/GentlePersuader`
- `martymcenroe/GlucoPulse`
- `martymcenroe/Hermes`
- `martymcenroe/HermesWiki`
- `martymcenroe/IEEE-standards`
- `martymcenroe/RCA-PDF-extraction-pipeline`
- `martymcenroe/Talos`
- `martymcenroe/TheMobyPerogative.world`
- `martymcenroe/TxDOT-LDA`
- `martymcenroe/acpb-manifest-poc`
- `martymcenroe/ai-power-systems-compendium`
- `martymcenroe/athleet.dev`
- `martymcenroe/athleet.github.io`
- `martymcenroe/automation-scripts`
- `martymcenroe/best-of-pes-ai`
- `martymcenroe/career`
- `martymcenroe/collectibricks`
- `martymcenroe/data-harvest`
- `martymcenroe/dispatch`
- `martymcenroe/dont-stop-now`
- `martymcenroe/dotfiles`
- `martymcenroe/electric-nexus`
- `martymcenroe/gh-link-auditor`
- `martymcenroe/github-readme-stats`
- `martymcenroe/hermes-docs`
- `martymcenroe/iconoscope`
- `martymcenroe/job-sniper`
- `martymcenroe/maintenance`
- `martymcenroe/martymcenroe`
- `martymcenroe/martymcenroe.github.io`
- `martymcenroe/metabolic-protocols`
- `martymcenroe/my-discussions`
- `martymcenroe/mySvelte`
- `martymcenroe/my_hackerrank_SQL`
- `martymcenroe/my_hackerrank_python`
- `martymcenroe/neatworks-file-recovery`
- `martymcenroe/nec2017-analyzer`
- `martymcenroe/power-agent.github.io`
- `martymcenroe/prompt-stream`
- `martymcenroe/sentinel`
- `martymcenroe/sentinel-rfc`
- `martymcenroe/spotify-personal-backups`
- `martymcenroe/thrivetech-ai`
- `martymcenroe/unleashed`
- `martymcenroe/yt-playlist-importer`

**Mitigation:** Disable wikis on repos that don't actively use them. For repos that need wikis, restrict editing to collaborators and monitor wiki git history for unauthorized changes.

---

*Generated by tools/github_protection_audit.py on 2026-03-09*
