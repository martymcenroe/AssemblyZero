# Why Windows? A Development Environment Decision

## The Accidental Adventure

AssemblyZero was built on Windows not by grand design, but by circumstance. The development machine is a Dell Alienware with a capable GPU - originally acquired for playing the latest Civilization. Using Claude Code on it became its own adventure game, one that quickly took over.

## The Deliberate Choice

Beyond the accident of hardware, there was intention: **get out of the macOS-only world for a while.**

For years, the pattern was:
- macOS for personal development
- Linux (RedHat) for work servers
- Windows as "that other thing"

Building AssemblyZero on Windows with Git Bash revealed friction that macOS developers never see. This friction became valuable - it forced documentation of edge cases, path format rules, and permission patterns that would otherwise remain invisible.

## The Current Setup

| Machine | OS | Purpose |
|---------|-----|---------|
| Dell Alienware | Windows 11 | Primary dev, gaming |
| Dell (older, no TPM) | Windows 10 (for now) | Future Linux candidate |
| (Future) | macOS | When opportunity presents |

## On WSL and Docker

**WSL:** Not compelling. Git Bash provides the Unix-like shell experience without the overhead of running a full Linux kernel. The translation issues (path formats, permission patterns) are real but manageable.

**Docker:** Understood as a mechanism to run whatever OS you want, isolated. Not a replacement for native development - more of a deployment/testing tool.

## Future Plans

1. **macOS compatibility:** When the right opportunity arises (perhaps a top-end Mac Mini for work), ensure AssemblyZero works seamlessly on macOS. The permission friction documentation will inform what needs adjustment.

2. **Linux exploration:** The TPM-blocked Dell will likely become a Linux machine eventually. Not urgent, but good to have options.

## What This Taught Us

The Windows/Git Bash environment exposed assumptions in Claude Code's design:
- Permission allowlists assume native Unix paths
- Pattern matching breaks on Git Bash's hybrid paths
- Most AI coding tools are macOS-first

AssemblyZero adapted with:
- Visible self-check protocol (document the friction)
- Dual path format rules in CLAUDE.md
- Platform-specific dependency markers

**The friction became the feature.** By developing on the "weird" platform, we caught cross-platform issues early.

---

*"The reason for going was to look at dragons, in the wild. They needed to be looked at by an expert."*
— Equal Rites

Sometimes you choose the harder path because that's where the dragons are.
