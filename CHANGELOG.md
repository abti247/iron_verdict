# Changelog

All notable changes to Iron Verdict will be documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- Contrast mode for bright halls in the display settings (gear or "S"): solid light colours with a clear border and pure white, bolder texts on the black background; remembered per device
- Layout editor for the display (settings → "Edit layout"): move, resize and hide timer, lights, cards and reasons, verdict and VPortal lifter and attempt info with mouse or touch; saved per device and copyable to another display as a code
- Adjustable gap between the lights in the display layout editor (handle beside the lights), e.g. for big lights close together in the stream overlay; saved with the layout and in its code, older layouts and codes keep today's gap
- Upper limit for connected devices across all competitions on one server (`MAX_WEBSOCKETS`, default 2000): above it a new judge or display sees "Server at capacity"; a judge reconnecting to their own position always gets back in
- Break display: from the display settings (gear or "S") any display starts a break for the whole session, by minutes (countdown) or until a time of day, optionally with the next lift; all displays and the stream overlay show it big in the middle instead of timer, lights, verdict and lifter until the time is up, the head judge starts the timer or someone ends it in the settings
- Stream overlay for OBS: "Stream overlay (OBS)" on role select gives a URL for an OBS browser source that shows lights, reasons, verdict, timer and lifter info on a transparent background without controls, texts on a dark panel so they stay readable over the camera picture; it has its own layout (or one passed in the URL) and connects to VPortal from its settings ("S"); when VPortal drops out its banner says to reconnect with "S"
- Demo guide with screenshots of the judge screen picking a reason, the display result with reasons and the layout editor, plus short notes on customising the display, breaks and the stream overlay for live streams
- "?" explanations in place: in the display settings (gear or "S") for the break, layout editor, layout code and contrast mode, and beside "Stream overlay (OBS)" on role select for setting up the overlay in OBS, in English and German
- Monitoring endpoint `/metrics` for Grafana Cloud, protected by the `METRICS_TOKEN` variable (off when unset): running competitions, connected judges and displays, votes, rejected votes, dropped connections, snapshot age, errors and memory; a ready-to-import Grafana dashboard and the alert rules are in `docs/monitoring.md`
- "?" in the VPortal connect dialog that explains the connection to the competition software in every step: what it is for, which credentials, stage choice, one login per device (the stream overlay needs its own), that the dialog shows in the stream while open there, and what happens when VPortal drops out; in English and German

### Changed
- The verdict sits a little further below the cards and reasons, so in the display layout editor their labels and hide buttons no longer cover each other

### Fixed
- A device with a stored VPortal login shows it as connected after a reload, on role select too, so the connect dialog offers "Disconnect" instead of asking for the login again; switching to another session in the same tab no longer shows the previous session's connection
- A display or judge device reloaded while the session can't be checked (venue Wi-Fi drops out) still shows the VPortal button on role select, with its stored connection and "Disconnect"; in a session without VPortal the button stays hidden
- Session lookup and creation limits now count per network instead of across all competitions, so a wave of joins or reloads elsewhere can no longer lock judges out with "Too Many Requests"
- Connections that ended unexpectedly no longer stay registered: they no longer take up display slots, a judge's lost connection always shows as disconnected on the other devices, and the server log no longer repeats the same heartbeat warning every 5 seconds

### Removed
- Display zoom slider: sizes are now set per block in the layout editor; a previously set zoom is reset to the default size

## [0.3.0] - 2026-10-18

### Added
- Every release is first deployed to a staging environment on Railway and tested there; the version tag and GitHub release are only created after green staging tests and a second approval
- Rate limits for creating and looking up sessions can be set with `RATE_LIMIT_SESSION_CREATE` and `RATE_LIMIT_SESSION_LOOKUP` (defaults unchanged: 10/hour, 30/minute)
- Legal notice (Impressum) with contact address and e-mail; the footer link on the start page is now "Privacy & Legal Notice" ("Datenschutz & Impressum")

### Changed
- Pushing a version tag no longer creates a release; releases are started by merging a version bump and approving the release run
- Lights on the display and in the judges' results are only white or red; under a red light a card in the judge's colour (red, blue, yellow), with the reason text below it as before
- The lights on the display stay in place when the result, a card or a reason appears; "Waiting for judges…" is shown where the verdict will appear, and the display is a little more compact so it still fits the screen at the largest zoom
- German texts say "Plattform" instead of "Bühne", as is usual in powerlifting
- Demo guide reworded after feedback from a referee (German and English): the "Why Iron Verdict?" terms are translated, judges are no longer told what to focus on next attempt, and the IPF technical rulebook is linked (German: BVDK rules page, English: IPF rules page)
- "Show reasons on display" is now on in new sessions; the head judge can switch it off. Sessions that were already running keep their setting
- `ALLOWED_ORIGIN` is now required — the app refuses to start without it instead of silently accepting connections from any website. Set it to your domain, or explicitly to `*` for local/LAN use (as `docker-compose.yml` does); the value in use is logged at startup
- Bench press and deadlift reasons follow the rulebook wording: "Upper body thrust", "Bar contact with rack supports", "Feet touched bench", "Shoulders not behind bar", and "Head / Shoulders up" and "Hand movement" are now separate reasons (same in German). A reason picked in a session that was running during the update may be shown once as an internal name

### Fixed
- After an update, devices that had the app open before load the new version instead of mixing it with old files from the browser cache (which could leave the app stuck at "Loading …"). Once, after deploying this release: hard-reload every judge and display device (Ctrl+Shift+R, or clear the site data on phones) before the next competition
- If the browser blocks the demo's pop-up windows, the demo guide says so and explains how to continue (allow pop-ups and relaunch, or switch screens in an open window) instead of claiming four windows are open
- Demo windows show "DEMO" instead of the session code on the judge screen, also after a reload; clicking "DEMO" (now also on the display) opens the role selection
- If the session backup cannot be written (e.g. the disk is full), the error is logged and the server retries it a minute later; before, backups and the removal of expired sessions stopped silently until the next restart
- If the same judge position is reconnected from two tabs at the same moment (e.g. a duplicated tab), only one gets the position; the other is shown that the position was taken by another device instead of both acting as that judge
- The server no longer rewrites its session backup every minute when nothing changed, and saving it no longer pauses votes and connection checks for a moment
- Reasons under the lights stay centred under their light also for long (German) words, on the display and in the judge's results; on the display they now grow and shrink with the screen size and zoom like the lights
- If VPortal answers with something other than lifter data (e.g. a maintenance page), the server reports it as an upstream error (502) instead of an internal error (500) and logs the response status and type
- Long German words in reasons that do not fit next to their light break at a sensible point with a hyphen ("Hantel-ständern") instead of running past it; on phones the judge's results use a slightly smaller font
- When the VPortal login fails, the dialog says why (VPortal not reachable, no session returned, token request rejected) instead of a bare error code, and the server log records the cause
- If loading the VPortal stages fails after login, the dialog shows an error instead of "Loading stages…" forever
- A VPortal-connected display that is reloaded on a bad network shows the "VPortal disconnected" banner and fills in the lifter data on its own once the network is back, instead of staying empty until the next reload
- Switching a display to role selection and back no longer leaves extra VPortal requests running in the background

[0.3.0]: https://github.com/abti247/iron_verdict/compare/v0.2.1...v0.3.0

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
