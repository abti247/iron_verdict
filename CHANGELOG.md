# Changelog

All notable changes to Iron Verdict will be documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

### Changed

### Fixed

### Removed

## [0.1.3-beta] - 2026-04-25

### Added
- Scroll indicator on the judge reason list shows when more options are available below
- Multi-language support (English + German) — each device resolves its own language from browser settings or a manual toggle
- Language switcher on the landing page (footer) and role-select screen (pill toggle)
- Reason cards and verdict labels now translate per device, so a German display can coexist with English judges
- Discreet "Privacy" / "Datenschutz" footer link on the landing page opens a privacy notice screen covering server logs, session data, language preference, analytics, and cookie policy
- WebSocket heartbeat keeps judge and display connections alive through reverse-proxy idle timeouts

### Fixed
- Judges now see the correct lift type and reasons immediately on join or reconnect, even if the head judge changed the lift while they were disconnected
- Starting a new session no longer inherits the lift type from a previous session — new sessions always start with Squat

[0.1.3-beta]: https://github.com/abti247/iron_verdict/compare/v0.1.2-beta...v0.1.3-beta

## [0.1.2-beta] - 2026-03-04

### Added
- Information for demo to be run on desktop
- Head judge screen shows live connectivity status (L/R) for the other two judges, displayed inline with the Head Judge Controls title
- Head judge Next Lift button is always active; shows a confirmation prompt if results haven't been shown yet
- Playwright E2E test suite (31 tests) covering competition flow, judge reconnection, double-vote prevention, role protection, connectivity indicators, stuck states, display resilience, and session end

### Changed
- Updated reasons based on IPF technical rule book (effective date 01 March 2026 - version 3)
- Results are no longer displayed until all three judges have locked in a vote, matching IPF simultaneous-lights rule

### Fixed
- Timer no longer resets to 60 when a judge rejoins after all votes are locked — the frozen time at the moment of the last vote is preserved
- A judge who reloads the page after voting can no longer submit a second vote that overwrites their original decision
- Judges who reload or navigate back after voting now see their vote correctly locked in on the judge screen
- Judges can seamlessly rejoin their role after accidental disconnect (e.g. mobile back-swipe) without getting a "Role already taken" error or the session getting stuck
- Session no longer gets stuck when a judge disconnects mid-round
- Permission denied error when saving session snapshots to Railway volume on shutdown
- Submitting a vote with an unrecognised judge position now returns a clear error instead of crashing
- Attempting to join a role already occupied by another judge again shows a "Role already taken" error instead of silently doing nothing

[0.1.2-beta]: https://github.com/abti247/iron_verdict/compare/v0.1.1-beta...v0.1.2-beta

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
