# Changelog

All notable changes to Iron Verdict will be documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Head judge screen shows live connectivity status (L/C/R) for all three judges
- Head judge Next Lift button is always active; shows a confirmation prompt if results haven't been shown yet

### Fixed
- A judge who reloads the page after voting can no longer submit a second vote that overwrites their original decision
- Judges can seamlessly rejoin their role after accidental disconnect (e.g. mobile back-swipe) without getting a "Role already taken" error or the session getting stuck
- Session no longer gets stuck when a judge disconnects mid-round
- Permission denied error when saving session snapshots to Railway volume on shutdown

### Removed

## [0.1.1-beta] - 2026-02-26

### Added
- Information of used rule set in the demo text

### Fixed
- Scaling of font and orb sizes on the decision/reasons depiction on judge screens 

[0.1.1-beta]: https://github.com/abti247/iron_verdict/compare/v0.1.0-beta...v0.1.1-beta

## [0.1.0-beta] - 2026-02-26

### Added
- Real-time judging for 3 judges with White/Red/Blue/Yellow light decisions and optional reasons
- Live display screen synchronized to all judge decisions
- 60-second countdown timer controlled by head judge
- Session system with 8-character codes — no accounts required
- Head judge controls: require reasons, toggle reason visibility on display, next lift, end session
- QR code generation on role-select screen for easy device onboarding
- `?session=` URL parameter as QR code entry point
- Auto-rejoin session on page reload via `sessionStorage`
- Back button on role-select screen
- Connection status dot on display screen
- "Server restarting" notification on graceful server shutdown
- In-memory session storage with optional JSON snapshot persistence across restarts
- Session expiration after 4 hours of inactivity
- Docker deployment support with volume mount for persistence
- Railway deployment support
- Structured JSON logging with configurable log level
- SRI integrity hash on CDN scripts

[0.1.0-beta]: https://github.com/abti247/iron_verdict/releases/tag/v0.1.0-beta
