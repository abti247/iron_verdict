# Changelog

All notable changes to Iron Verdict will be documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- `ConnectionManager.get_connection()` to look up a registered WebSocket by session code and role
- `reconnect_token` (16-byte hex) generated on judge join, stored in session state, excluded from snapshots, and survives `reset_for_next_lift`
- Connection replacement: judge with a valid `reconnect_token` can evict a stale connection and re-join the same role
- Identity guard in disconnect handler: stale disconnects from replaced connections are ignored, preventing false `connected=false` state
- `judge_status_update` broadcasts to other session clients when a judge joins or disconnects
- `reconnect_token` included in `join_success` response; excluded from `session_state` before sending to clients

### Fixed
- Permission denied error when saving session snapshots to Railway volume on shutdown

### Changed

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
