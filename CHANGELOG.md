# Changelog

All notable changes to Iron Verdict will be documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

### Changed
- German texts say "Plattform" instead of "Bühne", as is usual in powerlifting
- "Show reasons on display" is now on in new sessions; the chief referee can switch it off. Sessions that were already running keep their setting

### Fixed
- When the VPortal login fails, the dialog says why (VPortal not reachable, no session returned, token request rejected) instead of a bare error code, and the server log records the cause
- If loading the VPortal stages fails after login, the dialog shows an error instead of "Loading stages…" forever

### Removed


## [0.2.1] - 2026-10-13

### Changed
- Judges see "Sending…" after LOCK IN; "Vote Locked" appears only once the server has confirmed the vote

### Fixed
- VPortal login works again on BVDK staging (it failed with an error after a VPortal update) and keeps working on BVDK and ÖVK production when they receive the same update
- A judge device whose position was taken by another device while it was offline no longer keeps trying to reconnect forever — after about 25 seconds it shows the role selection with a notice that the position is signed in elsewhere
- A single dropped connection to VPortal no longer interrupts the lifter overlay; if VPortal stays unreachable, the server reports it as an upstream error (502) instead of an internal error (500)
- After a page reload, judges and displays see "Connecting to session …" with a Cancel button until their screen is back — the start page no longer flashes up; if the session has ended meanwhile, the start page says so instead of showing a popup
- While the app is loading, only a loading indicator is shown — the VPortal login dialog and other screens no longer flash up; if the app cannot start, a message with a reload button appears after 10 seconds instead of a blank screen
- The app starts and runs a full competition on venue Wi-Fi without internet, and no longer waits for slow external servers on start — scripts and fonts are served by the app itself
- After a connection loss (e.g. a server restart), judges and displays retry at least every 3 seconds instead of waiting up to 16 seconds, and reconnect at once when the device is back online or the app comes back to the foreground
- A judge or display whose connection silently stops working (e.g. the device switches Wi-Fi access points) now notices within about 15 seconds, shows "reconnecting" and reconnects, instead of looking connected for up to 70 seconds
- A vote cast while a judge's connection was down (or before a page reload) is no longer lost — it is sent automatically once the connection is back
- A vote the server rejects (e.g. the next lift already started, or a reason became mandatory) unlocks the judge screen with an explanation instead of staying locked
- A vote sent for a lift that has already ended is always reported as "next lift started" and cleared, even if reasons became mandatory in the meantime — it can no longer be completed with a reason and counted for the new lift

[0.2.1]: https://github.com/abti247/iron_verdict/compare/v0.2.0...v0.2.1

## [0.2.0] - 2026-10-11

### Added
- Every tested commit on `main` is published as a Docker image (`ghcr.io/abti247/iron_verdict:sha-<commit>`); releases reuse that exact image under `vX.Y.Z` and come with GitHub release notes
- Release, deploy and rollback runbook with a pre-competition checklist (`docs/release.md`)

### Changed
- App footer shows the commit the running image was built from (`sha-<commit>`)

[0.2.0]: https://github.com/abti247/iron_verdict/compare/v0.1.4-beta...v0.2.0

## [0.1.4-beta] - 2026-05-20

### Added
- Browser back button now steps back through app screens (judge or display to role-select, role-select to landing) instead of leaving the app
- Optional VPortal integration: sessions created via `/vportal` can connect to the BVDK/ÖVK competition-management software and overlay the current lifter (name, club, weight class, age category, discipline, attempt, weight) on the display screen
- Display screen scales to viewport and supports a manual size adjustment via a settings panel (gear icon top-left of display, or `S` key)
- Display zoom preference persists per browser

### Changed
- VPortal lifter info on the display screen (name, club, age/weight class, lift, attempt, weight) is now clearly readable from across the room
- Display screen session name in the corner is now clickable, returning to role selection
- Reloading on the role-select screen now keeps you there instead of dropping back to the landing page
- Browser back from a judge or display screen after a reload now returns to role selection (and back again to landing)

### Fixed
- Swipe-back on a phone after reloading a judge screen now returns to role selection instead of exiting iron-verdict back to the launching app
- App load no longer flashes through unstyled screens, raw translation keys, or fallback fonts before rendering
- App loads faster on slow networks (mobile data, conference Wi-Fi) — connections to external font and script CDNs are warmed up during initial HTML parsing instead of serially after
- Joining with an invalid or unknown session code now shows an inline error on the landing screen instead of failing later at role selection

[0.1.4-beta]: https://github.com/abti247/iron_verdict/compare/v0.1.3-beta...v0.1.4-beta

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
