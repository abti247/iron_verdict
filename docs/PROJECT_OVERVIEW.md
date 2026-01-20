# JudgeMe - Project Overview

## What is JudgeMe?

**JudgeMe** is a simplified, session-based web application for powerlifting competitions where 3 judges vote on lift validity (white/red lights) in real-time. The system eliminates the complexity of traditional judging platforms by removing authentication requirements and focusing on ease of use.

## Core Concept

The application separates responsibilities across specialized roles for efficient competition management:

### Pre-Competition Setup
1. **Admin** creates competition (name, date) → System generates 7 shareable links
2. **Competition Manager** enters athlete data (weigh-ins, opening attempts) → Creates groups and flights
3. **Admin** distributes URLs to judges (shared), platform crew, athlete manager, and announcer

### Live Competition Flow
4. **Admin** starts competition by selecting group/flight and discipline (squat/bench/deadlift)
5. **All 3 Referees** open shared judge URL and select their positions (LEFT/CENTER/RIGHT)
6. **Center Referee** controls 60-second countdown timer and votes on lifts
7. **Side Referees** (left/right) vote on lifts from their positions (simplified interface)
8. **Athlete Manager** updates next attempt weights as athletes declare them
9. **Platform Loaders** see plate loading calculator showing exactly which plates to load
10. **Competition Host** announces athletes using real-time "on deck" information
11. **Venue Audience** watches judge vote lights appear simultaneously on big screen
12. **Remote Audience** (family at home) follows competition via simple dashboard

### Post-Competition
13. **System** saves competition data for historical dashboard and analytics

## Key Features

### For Admins (Competition Organizer)
- Create competition in under 2 minutes (just name and date)
- Generate 7 shareable URLs instantly (no authentication setup)
- Start competition by selecting group/flight + discipline
- Monitor competition progress from high-level dashboard
- Delegate setup and live management to specialized roles

### For Competition Managers (Pre-Competition Setup)
- Enter athlete data with weigh-in weights and opening attempts
- Create groups and flights with drag-and-drop interface
- Bulk import athletes via CSV
- Organize athletes into balanced flights
- Verify all data before competition starts

### For Athlete Managers (Live Weight Updates)
- Fast search by athlete name or lot number
- Update next attempt weights in < 15 seconds per athlete
- See which athletes are up next in flight
- Simple, focused interface optimized for speed
- Real-time updates broadcast to all displays

### For Platform Loaders (Weight Loading Crew)
- Visual plate loading calculator shows exactly which plates to load
- Color-coded plate diagram (25kg red, 20kg blue, 15kg yellow, etc.)
- Shows total weight on bar
- Highlights plate changes between lifts (ADD/REMOVE indicators)
- "On deck" preview shows next 2-3 athletes and upcoming weights
- Alerts for large weight jumps (>20kg) and bar changes (men's/women's)
- Distance-readable display (10-15 feet from platform)
- Eliminates mental math under pressure

### For All Referees (Shared Judge URL)
- **Single shared URL** for all 3 judges (no separate links)
- **Position selection on first load**: Choose LEFT, CENTER, or RIGHT
- **Server-side position locking**: First-come, first-served
- **Position release**: Can switch positions (disabled while timer running)

### For Center Referee (After Selecting CENTER)
- Control 60-second countdown timer (START/RESET buttons)
- Vote on lifts with large WHITE/RED buttons
- Change vote before all 3 judges have voted (fat-finger correction)
- Color-coded timer: Green → Yellow → Red
- Timer and voting controls in single interface
- RESET button stops timer and sets to 60s (does not auto-start)

### For Side Referees (After Selecting LEFT/RIGHT)
- Simplified interface with voting buttons only (no clock controls)
- Large WHITE/RED buttons optimized for mobile
- Change vote before all 3 judges have voted
- Read-only timer display for information
- Real-time lift information display

### For Competition Host (Announcer)
- See current athlete and "on deck" (next 2-3 athletes)
- Display shows name, discipline, attempt, weight
- Auto-updates with lift events and weight changes
- Timer display for timing cues
- Large, readable text from announcer booth

### For Venue Audience (Big Screen at Competition)
- Judge vote lights appear **simultaneously** after all 3 judges vote (LEFT/CENTER/RIGHT labeled)
- Maintains suspense - no partial votes shown
- Result banner displays "GOOD LIFT" or "NO LIFT" after lights appear
- Both vote lights and result banner remain visible for transparency
- Large, TV-optimized display (readable from 30+ feet)
- Timer countdown visible to audience

### For Remote Audience (Watching from Home)
- Simple dashboard with current standings/leaderboard
- "Up Next" section shows who's lifting soon
- Recent results feed (last 5 lifts)
- Search for specific athlete (e.g., grandma finds her granddaughter)
- Mobile-friendly interface with large text

## What Makes JudgeMe Different?

### 1. No Authentication Required
Traditional systems require judges to create accounts, remember passwords, and go through login flows. JudgeMe uses cryptographically secure tokens embedded in URLs - share the link, start judging. This applies to all roles: judges, competition managers, athlete managers, announcers, and audience members.

### 2. Role Separation for Efficiency
Instead of overwhelming the admin with all tasks, JudgeMe separates responsibilities:
- **Admin** focuses on high-level oversight (create competition, start flights, monitor progress)
- **Competition Manager** handles pre-competition athlete data entry and flight organization
- **Athlete Manager** manages live weight updates during competition
- **Platform Loaders** see plate loading calculator to eliminate loading errors
- **All 3 Referees** share single URL and select positions (LEFT/CENTER/RIGHT) on first load
- **Center Referee** controls timing and votes (adaptive UI with timer controls)
- **Side Referees** focus purely on voting (simplified UI without timer controls)
- **Competition Host** handles announcements with real-time data
- Each role gets a specialized, focused interface

### 3. Suspense-Driven Audience Experience
Venue audience members see all 3 judge vote lights **simultaneously** after all judges vote - maintaining the drama and suspense of traditional physical judge lights. No partial votes shown during judging.

### 4. Vote Changing for Fat-Finger Errors
Judges can change their vote before all 3 judges have voted, preventing embarrassing mistakes from accidental button presses while maintaining result integrity once all votes are in.

### 5. Groups and Flights Organization
Competitions are organized hierarchically: Competition → Groups → Flights → Athletes. This matches real-world powerlifting structure and allows admins to run flights sequentially by discipline (squat → bench → deadlift).

### 6. Simplified Tech Stack
- SQLite database (single file, no server)
- Single Node.js process (backend + static serving)
- Minimal dependencies
- Easy deployment (Railway, Render, or any VPS)

### 7. Mobile-First Design
Judges, athlete managers, and competition managers primarily use smartphones and tablets. JudgeMe prioritizes large touch targets (80px+ buttons), responsive design, and fast load times on mobile networks.

## Technical Highlights

- **Real-time updates** via Socket.IO WebSocket connections
- **Automatic reconnection** handling for network interruptions
- **Type-safe** codebase with TypeScript
- **Fast development** with Vite build tool
- **Simple deployment** with single-file SQLite database

## Use Cases

1. **Local Competitions** - Small to medium powerlifting meets (10-50 athletes)
2. **Training Meets** - Gym practice competitions
3. **High School/College Meets** - School-level competitions
4. **Remote Judging** - Judges in different locations voting on video submissions

## Limitations (MVP Scope)

- **Single platform only** - No multi-platform support in MVP
- **No video playback** - Judges vote on live lifts only
- **No athlete accounts** - Athletes don't log in or track their own progress
- **No federation integration** - Standalone system, not integrated with IPF/USAPL databases

## Future Enhancements

Planned features for post-launch:
- Competition replay functionality
- Advanced statistics and analytics
- Multi-language support
- Hardware integration (physical judge buttons/lights)
- Live streaming integration
- Native mobile apps
- Federation-specific presets

## Target Timeline

**Intermediate developer, part-time:** 3-4 weeks
**Intermediate developer, full-time:** 2 weeks

## Technology Stack

### Frontend
- React 18 + TypeScript
- Vite (build tool)
- Socket.IO Client (real-time)
- Native CSS or minimal Tailwind

### Backend
- Node.js + Express + TypeScript
- Socket.IO (WebSocket server)
- Prisma ORM
- SQLite database

### Deployment
- Railway.app, Render.com, or VPS
- Single server process
- No separate database server needed
