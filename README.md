# JudgeMe

**A simplified, session-based powerlifting judging application**

> Real-time judging with no authentication required. Create a competition, share links, start judging.

---

## 📋 Project Status

**Current Phase:** Requirements & Design
**Status:** Documentation complete, awaiting review before implementation

---

## 🎯 What is JudgeMe?

JudgeMe is a web application that streamlines powerlifting competition judging by eliminating the complexity of traditional systems. Admins create competitions and share simple URL links with judges - no accounts, no passwords, no complicated setup.

### Key Features

- ✅ **No Authentication** - Share URLs, start judging immediately
- ✅ **Real-Time Voting** - Judges vote on mobile devices, results appear instantly
- ✅ **Session-Based** - Each competition is independent with unique secure links
- ✅ **Mobile-First** - Large touch buttons optimized for smartphones
- ✅ **Audience Display** - Real-time vote visualization on projector/TV
- ✅ **Historical Dashboard** - View past competition statistics

---

## 📖 Documentation

All project documentation is located in the [`/docs`](./docs) directory:

### Core Documentation Files

1. **[PROJECT_OVERVIEW.md](./docs/PROJECT_OVERVIEW.md)**
   High-level project description, core concept, technical highlights

2. **[PERSONAS.md](./docs/PERSONAS.md)**
   User personas: Admin (Sarah), Judge (Marcus), Audience (Alex), Athlete (Emma)

3. **[USE_CASES.md](./docs/USE_CASES.md)**
   Detailed use cases with flows, alternatives, and success metrics:
   - UC1: Create Competition Session
   - UC2: Judge Votes on Lift
   - UC3: Admin Controls Competition Flow
   - UC4: View Audience Display
   - UC5: View Historical Dashboard

4. **[REQUIREMENTS.md](./docs/REQUIREMENTS.md)**
   Complete requirements specification:
   - 30 Functional Requirements (FR1-FR30)
   - 20 Non-Functional Requirements (NFR1-NFR20)
   - Data, Interface, and Constraint requirements
   - Acceptance criteria and success metrics

5. **[USER_FLOWS.md](./docs/USER_FLOWS.md)**
   Visual Mermaid diagrams showing:
   - Admin creates competition flow
   - Judge voting process
   - Real-time audience display updates
   - Admin control panel decisions
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

## 🎨 User Roles

### 1. Admin (Competition Organizer)
- Creates competitions with athlete names
- Shares judge URLs via SMS/email
- Controls competition flow (starts lifts)
- Views real-time voting status
- Accesses historical statistics

### 2. Judge (3 per competition)
- Receives unique URL (LEFT, CENTER, or RIGHT position)
- Votes WHITE or RED on each lift
- Sees current lifter and lift information
- No login or account required

### 3. Audience (Spectators)
- Views public display URL (usually projected)
- Sees real-time vote lights
- Watches results appear as judges vote
- No special access needed

---

## 🚀 Implementation Plan

### Timeline Estimate
- **Part-time developer (20 hrs/week):** 3-4 weeks
- **Full-time developer (40 hrs/week):** 2 weeks

### Development Phases

1. **Foundation** (Days 1-2)
   Project setup, database schema, basic server

2. **Competition Creation** (Days 3-4)
   Admin creates competitions, generates secure URLs

3. **Real-Time Voting** (Days 5-7)
   Socket.IO integration, judge voting, result calculation

4. **Admin Control Panel** (Days 8-9)
   Lift queue management, start lift functionality

5. **Audience Display** (Days 10-11)
   Public display with vote lights and results

6. **Historical Dashboard** (Days 12-13)
   Statistics and past competition data

7. **Polish & Testing** (Days 14-15)
   Error handling, responsive design, testing

8. **Deployment** (Day 16+)
   Production deployment (Railway, Render, or VPS)

---

## 🔒 Security Model

### Token-Based Access

JudgeMe uses **cryptographically secure random tokens** instead of traditional authentication:

- **Admin token:** Full control over competition
- **Judge tokens (3):** Vote access for specific position
- **Audience token:** Read-only display access

**Security Properties:**
- 128-bit entropy (2^128 possible tokens)
- Immune to brute-force attacks
- No password resets needed
- Tokens expire when competition ends (or can be manually revoked)

---

## 📊 Database Schema (Simplified)

```
Competition
├── id
├── name
├── adminToken, judgeTokenLeft, judgeTokenCenter, judgeTokenRight, audienceToken
├── status (SETUP, ACTIVE, ENDED)
├── currentLiftId
└── timestamps

Athlete
├── id
├── competitionId
├── name
└── lotNumber

Lift
├── id
├── competitionId
├── athleteId
├── liftType (SQUAT, BENCH, DEADLIFT)
├── attemptNumber (1, 2, 3)
├── weight
├── status (PENDING, IN_PROGRESS, COMPLETED)
└── result (GOOD_LIFT, NO_LIFT)

Vote
├── id
├── liftId
├── judgePosition (LEFT, CENTER, RIGHT)
├── decision (WHITE, RED)
└── timestamp
```

---

## 🎯 MVP Scope

### Included in MVP ✅
- Single platform per competition
- 3 judges (left, center, right positions)
- Real-time voting and display
- Admin control panel
- Historical dashboard
- Mobile-responsive judge interface

### Not Included in MVP ❌
- Multi-platform support
- Video replay
- Athlete accounts
- Federation integration
- Hardware judge buttons
- Native mobile apps
- Multi-language support

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

1. **Admin:** Open homepage → Create competition → Get 5 URLs
2. **Admin:** Share judge URLs via text to 3 judges
3. **Judges:** Click link → Vote with big WHITE/RED buttons
4. **Audience:** Project audience URL on screen → Watch votes in real-time
5. **Admin:** Start each lift → See judges vote → Proceed to next lift

**No accounts. No passwords. Just judging.**

---

**Last Updated:** January 14, 2026
**Status:** Requirements & design documentation complete
