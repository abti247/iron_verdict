# JudgeMe

**A simplified, role-separated powerlifting competition management system**

> Real-time judging and competition management with no authentication required. Create a competition, share links, start competing.

---

## 📋 Project Status

**Current Phase:** Requirements & Design
**Status:** Documentation complete, ready for implementation

---

## 🎯 What is JudgeMe?

JudgeMe is a comprehensive web application that streamlines powerlifting competition management by separating responsibilities into dedicated roles. Admins create competitions and share simple URL links with different roles - no accounts, no passwords, no complicated setup.

### Key Features

- ✅ **No User-Dependent Deployment** - Share URLs, start judging immediately
- ✅ **Role Separation** - 10 personas with dedicated interfaces optimized for their tasks
- ✅ **Real-Time Updates** - Socket.IO synchronizes all displays instantly
- ✅ **Session-Based** - Each competition is independent with unique secure links
- ✅ **Mobile-First** - Large touch buttons optimized for smartphones and tablets
- ✅ **Judge Position Selection** - Single shared judge URL, judges select LEFT/CENTER/RIGHT
- ✅ **Center Judge Controls** - Head referee manages lift progression and timer
- ✅ **Platform Loader Display** - Visual plate calculator with IPF color-coded plates
- ✅ **Break Management** - Admin can set breaks with countdown timers
- ✅ **Audience Display** - Simultaneous vote reveal for dramatic suspense
- ✅ **Athlete Manager** - Fast weight updates during competition (< 15 sec target)

---

## 📖 Documentation

All project documentation is located in the [`/docs`](./docs) directory:

### Core Documentation Files

1. **[PROJECT_OVERVIEW.md](./docs/PROJECT_OVERVIEW.md)**
   High-level project description, core concept, technical highlights, 10-persona system

2. **[PERSONAS.md](./docs/PERSONAS.md)**
   10 detailed user personas:
   - Admin (Sarah) - Competition oversight
   - Competition Manager (David) - Pre-competition setup
   - Athlete Manager (Lisa) - Live weight updates
   - Platform Loader (Jake) - Plate loading calculator
   - Head Referee (Marcus) - CENTER position with timer + progression control
   - Side Referees (Jessica) - LEFT/RIGHT positions
   - Competition Host (Kilian) - Announcer
   - Venue Audience (Alex) - Big screen display
   - Remote Audience (Grandma) - Home dashboard
   - Athlete (Emma) - Results viewer

3. **[USE_CASES.md](./docs/USE_CASES.md)**
   12 detailed use cases with flows, alternatives, and success metrics:
   - UC1: Admin creates competition (7 URLs)
   - UC1a: Competition Manager enters athletes
   - UC1b: Competition Manager creates groups/flights
   - UC2: Judge selects position
   - UC2a: Judge votes on lift
   - UC3: Admin starts flight
   - UC3a: Athlete Manager updates weights
   - UC3b: Platform Loader views plate calculator
   - UC4a: Venue Audience display
   - UC4b: Remote Audience dashboard
   - UC5: Historical dashboard
   - UC6: Competition Host announcer display

4. **[REQUIREMENTS.md](./docs/REQUIREMENTS.md)**
   Complete requirements specification with 30+ functional requirements covering:
   - Session management (7 URLs per competition)
   - Competition setup (groups, flights, athlete data with rack/safety heights)
   - Judge position selection (shared URL with runtime position claiming)
   - Center judge lift progression control
   - Admin break functionality
   - Athlete Manager fast weight updates
   - Platform Loader plate calculator (20kg bar + 2.5kg collars)
   - Venue and remote audience displays
   - Historical dashboard

5. **[CLOCK_TIMER_REQUIREMENTS.md](./docs/CLOCK_TIMER_REQUIREMENTS.md)**
   Detailed timer specifications:
   - 60-second countdown timer
   - Center judge START/RESET clock controls
   - NEXT ATHLETE button for lift progression
   - Real-time clock synchronization across all displays

6. **[USER_FLOWS.md](./docs/USER_FLOWS.md)**
   15 comprehensive Mermaid diagrams showing:
   - Admin creates competition (7 URLs)
   - Judge position selection and voting
   - Venue audience display with simultaneous vote reveal
   - Admin controls (starts flights, sets breaks, ends competition)
   - Competition Manager athlete entry and groups/flights creation
   - Athlete Manager live weight updates
   - Platform Loader plate loading calculator
   - Competition Host announcer display
   - Remote Audience dashboard
   - Database state management
   - Error handling (network reconnection)

---

## 🏗️ Architecture Overview

### Tech Stack

**Frontend:**
- React 18 + TypeScript
- Vite (build tool)
- Socket.IO Client (real-time)
- Native CSS or minimal Tailwind

**Backend:**
- Node.js + Express + TypeScript
- Socket.IO (WebSocket server)
- Prisma ORM
- SQLite database (single file)

**Why This Stack?**
- **Simplicity** - Minimal dependencies, easy to understand
- **Portability** - SQLite = no database server needed
- **Performance** - Real-time updates via WebSockets
- **Type Safety** - TypeScript throughout

### System Architecture

```
┌─────────────────────────────────────────┐
│         CLIENT DEVICES                   │
├──────────┬──────────┬───────────────────┤
│  Admin   │  Judges  │  Audience Display │
│  Laptop  │ (3 phones)│   (Projector)    │
└────┬─────┴─────┬────┴─────┬─────────────┘
     │           │           │
     └───────────┴───────────┘
               │
      [WebSocket + HTTP]
               │
     ┌─────────┴──────────┐
     │  Node.js Express   │
     │  - REST API        │
     │  - Socket.IO       │
     │  - Static files    │
     └─────────┬──────────┘
               │
     ┌─────────┴──────────┐
     │   SQLite Database  │
     │  (competitions.db) │
     └────────────────────┘
```

---

## 🎨 User Roles (10 Personas)

### 1. Admin (Sarah) - Competition Oversight
- Creates competition (name + date)
- Distributes 7 URLs to appropriate roles
- Starts flights by selecting group/discipline
- Sets breaks with duration or end time
- Ends competition
- Monitors overall progress

### 2. Competition Manager (David) - Pre-Competition Setup
- Enters athlete data (name, weigh-in, opening attempts, rack heights, safety heights)
- Creates groups and flights
- Organizes athletes via drag-and-drop
- Bulk CSV import support
- Finalizes competition structure

### 3. Athlete Manager (Lisa) - Live Weight Updates
- Updates next attempt weights during competition
- Fast search by name or lot number
- Last 3 athletes quick access
- < 15 seconds per weight update target
- Works at athlete check-in table

### 4. Platform Loader (Jake) - Plate Loading
- Views visual plate loading calculator
- Sees total weight, bar (20kg), collars (2.5kg each side)
- Color-coded IPF standard plates
- ADD/REMOVE indicators for weight changes
- Rack and safety height display
- Eliminates mental math errors

### 5. Head Referee (Marcus) - CENTER Position
- Selects CENTER position on shared judge URL
- Controls 60-second timer (START/RESET)
- Advances to next athlete (NEXT ATHLETE button)
- Votes on lifts (WHITE/RED)
- Can change vote before all 3 judges vote

### 6. Side Referees (Jessica) - LEFT/RIGHT Positions
- Selects LEFT or RIGHT position on shared judge URL
- Votes on lifts (WHITE/RED)
- Views timer (read-only)
- Can change vote before all 3 judges vote
- Simplified interface (no clock controls)

### 7. Competition Host (Kilian) - Announcer
- Views current athlete + "on deck" queue (next 2-3)
- Auto-updates with lift events and weight changes
- Announces to audience
- Optimized for quick glances while speaking

### 8. Venue Audience (Alex) - Big Screen Display
- Views all 3 vote lights SIMULTANEOUSLY (after all judges vote)
- Large display optimized for 30+ feet viewing
- Sees current athlete, weight, timer
- Break countdown display
- Maintains dramatic suspense

### 9. Remote Audience (Grandma) - Home Viewing
- Mobile-friendly dashboard
- Current standings and "up next" section
- Recent results feed
- Search for specific athlete
- Watches competition from home

### 10. Athlete (Emma) - Competitor
- Views current flight order
- Sees personal lift history
- Understands when they're "on deck"

---

## 🚀 Implementation Plan

### Timeline Estimate
- **Part-time developer (20 hrs/week):** 3-4 weeks
- **Full-time developer (40 hrs/week):** 2 weeks

### Development Phases

**Phase 1: Foundation (Week 1)**
- Initialize Node.js + Express + TypeScript project
- Set up Prisma with SQLite database
- Create database schema with all tables (Competition, Group, Flight, Athlete, Lift, Vote, JudgePosition)
- Implement token generation (7 URLs)
- Test API endpoint: POST /api/competitions

**Phase 2: Core Competition Flow (Week 2)**
- Competition Manager athlete entry (manual + CSV import)
- Competition Manager groups/flights creation (drag-and-drop)
- Admin control panel (start flight, set break, end competition)
- Basic Socket.IO setup for real-time updates

**Phase 3: Live Competition (Week 3)**
- Judge position selection + voting (shared URL)
- Head Referee timer controls (START/RESET)
- Center judge NEXT ATHLETE button (lift progression)
- Athlete Manager weight updates (< 15 sec target)
- Platform Loader plate calculator (20kg bar + 2.5kg collars)
- Venue Audience display (simultaneous vote reveal)
- Break display functionality

**Phase 4: Polish (Week 4)**
- Competition Host announcer display
- Error handling and edge cases
- Mobile responsiveness across all interfaces
- Network reconnection handling
- Testing and bug fixes
- Historical dashboard
- Deployment (Railway, Render, or VPS)

---

## 🔒 Security Model

### Token-Based Access

JudgeMe uses **cryptographically secure random tokens** instead of traditional authentication. Each competition generates **7 unique URLs**:

1. **Admin token:** Start flights, set breaks, end competition
2. **Competition Manager token:** Enter athletes, create groups/flights
3. **Athlete Manager token:** Update attempt weights during competition
4. **Platform Loader token:** View plate loading calculator
5. **Judge token (shared):** All 3 judges use same URL, select position on first load
6. **Venue Audience token:** Big screen display
7. **Competition Host token:** Announcer display

**Security Properties:**
- 128-bit entropy (2^128 possible tokens)
- Immune to brute-force attacks
- No password resets needed
- Tokens expire when competition ends
- Judge position locking prevents conflicts (server-side transactions)

---

## 📊 Database Schema (Simplified)

```
Competition
├── id
├── name
├── date
├── adminToken, competitionManagerToken, athleteManagerToken, loaderToken
├── judgeToken (shared), audienceToken, competitionHostToken
├── status (SETUP, READY, ACTIVE, ENDED)
├── activeFlightId
└── timestamps

Group
├── id
├── competitionId
├── name
└── flights[]

Flight
├── id
├── groupId
├── name
└── athletes[]

Athlete
├── id
├── flightId
├── name
├── lotNumber
├── weighInWeight
├── squatOpener, benchOpener, deadliftOpener
├── rackHeightSquat, rackHeightBench
└── safetyHeightBench

Lift
├── id
├── competitionId
├── athleteId
├── liftType (SQUAT, BENCH, DEADLIFT)
├── attemptNumber (1, 2, 3)
├── weight
├── status (PENDING, IN_PROGRESS, COMPLETED, SKIPPED)
├── result (GOOD_LIFT, NO_LIFT)
├── timerStartedAt
└── timerResetCount

Vote
├── id
├── liftId
├── judgePosition (LEFT, CENTER, RIGHT)
├── decision (WHITE, RED)
└── timestamp

JudgePosition
├── competitionId
├── position (LEFT, CENTER, RIGHT)
├── claimedAt
└── sessionId
└── UNIQUE(competitionId, position)
```

---

## 🎯 MVP Scope

### Included in MVP ✅
- Single platform per competition
- 7 URLs per competition (10 personas total)
- Judge position selection (shared URL)
- Center judge controls lift progression
- Competition Manager athlete data entry (manual + CSV)
- Groups and flights organization
- Athlete Manager live weight updates
- Platform Loader visual plate calculator (20kg bar + 2.5kg collars)
- Admin break functionality (duration or end time)
- 60-second timer with START/RESET controls
- Real-time Socket.IO synchronization
- Venue Audience display (simultaneous vote reveal)
- Competition Host announcer display
- Mobile-responsive interfaces
- Historical dashboard

### Nice-to-Have (Post-MVP)
- Remote Audience dashboard (home viewing)
- Multi-platform support (multiple platforms per competition)
- Advanced statistics and analytics
- Live streaming integration
- Multi-language support

### Not Included ❌
- Video replay
- Athlete accounts
- Federation-specific integrations
- Hardware judge buttons/lights
- Native mobile apps
- Competition replay functionality

---

## 🧪 Testing Strategy

### Manual Testing Scenarios

1. **End-to-End Competition**
   - Create competition with 3 athletes
   - Share judge links to 3 devices
   - Start lift, have all judges vote
   - Verify result calculation (2 WHITE = GOOD LIFT)
   - Complete all lifts
   - End competition and view dashboard

2. **Network Resilience**
   - Disconnect judge device during voting
   - Reconnect and verify Socket.IO reconnects
   - Submit vote successfully after reconnect

3. **Mobile Usability**
   - Test on iPhone SE (320px width)
   - Verify vote buttons are easily pressable
   - Check display on various Android devices

---

## 📈 Success Metrics

**Development:**
- MVP complete in target timeline (2-4 weeks)

**Performance:**
- Vote submission latency < 300ms
- Real-time updates appear < 500ms
- Support 100 concurrent audience viewers

**Usability:**
- Admin creates competition in < 2 minutes
- Judges vote without errors
- Zero data loss during competitions

---

## 🛠️ Development Setup (Future)

> Note: Implementation hasn't started yet. These instructions will be valid after Phase 1.

```bash
# Clone repository
git clone https://github.com/yourusername/judgeme.git
cd judgeme

# Install backend dependencies
cd backend
npm install
npx prisma migrate dev --name init
npm run dev

# Install frontend dependencies (in new terminal)
cd frontend
npm install
npm run dev
```

**Access points:**
- Frontend: http://localhost:5173
- Backend API: http://localhost:3001

---

## 🤝 Contributing

This project is currently in the design phase. Contributions will be welcome once implementation begins.

---

## 📝 License

MIT License (or your chosen license)

---

## 📞 Contact

For questions or feedback about this project design, please open an issue.

---

## 🎉 Quick Start (After Implementation)

### Pre-Competition
1. **Admin:** Create competition (name + date) → Get 7 URLs
2. **Admin:** Share Competition Manager URL → David enters athletes, creates groups/flights
3. **Admin:** Share Athlete Manager, Platform Loader, Judge, Audience, Host URLs

### Competition Day
1. **Admin:** Start flight (select group/flight/discipline)
2. **Judges:** Open shared judge URL → Select position (LEFT/CENTER/RIGHT)
3. **Center Judge (HEAD REF):**
   - Press START CLOCK (60 seconds)
   - All judges vote (WHITE/RED)
   - Press NEXT ATHLETE when ready
   - Repeat for each lift
4. **Athlete Manager:** Update next attempt weights (< 15 sec/athlete)
5. **Platform Loader:** Follow visual plate calculator (20kg bar + 2.5kg collars + plates)
6. **Competition Host:** Announce athletes using "on deck" display
7. **Venue Audience:** Watch big screen → See all 3 votes simultaneously
8. **Admin:** Set breaks as needed → End competition when done

**No accounts. No passwords. No user management. Just competing.**

---

**Last Updated:** January 20, 2026
**Status:** Requirements & design documentation complete, ready for implementation
