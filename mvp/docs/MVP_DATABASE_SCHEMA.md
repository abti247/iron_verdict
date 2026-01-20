# JudgeMe MVP - Database Schema

**Version:** 1.0
**Last Updated:** 2026-01-20
**Status:** MVP Specification

---

## Overview

The MVP database schema is **ultra-simplified** to support only the core judging functionality. It includes:
- **4 tables total** (Competition, JudgePosition, Lift, Vote)
- **NO athlete data** (no names, weights, or equipment)
- **NO groups or flights** (not needed for MVP)
- **Simple numbered lifts** (Lift 1, Lift 2, Lift 3...)

This schema supports:
- Judge position selection and locking
- Vote submission and tracking
- Timer state management
- Competition lifecycle (create/delete)

---

## Database Technology

**Database:** SQLite (single file database)
**ORM:** Prisma
**Migrations:** Prisma Migrate

**Rationale:**
- SQLite requires no separate database server
- Single file makes deployment simple
- Prisma provides type-safe database access
- Perfect for MVP scope

---

## Prisma Schema

```prisma
// This is your Prisma schema file for JudgeMe MVP

generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "sqlite"
  url      = "file:./dev.db"
}

model Competition {
  id            String   @id @default(uuid())
  name          String
  date          DateTime?
  status        String   // SETUP, ACTIVE, ENDED

  // Only 3 tokens needed for MVP
  judgeToken    String   @unique
  audienceToken String   @unique
  adminToken    String   @unique // For deletion

  createdAt     DateTime @default(now())
  endedAt       DateTime?

  lifts          Lift[]
  judgePositions JudgePosition[]
}

model JudgePosition {
  id              String   @id @default(uuid())
  competitionId   String
  position        String   // LEFT, CENTER, RIGHT
  sessionId       String   // Browser session ID
  claimedAt       DateTime @default(now())

  competition     Competition @relation(fields: [competitionId], references: [id], onDelete: Cascade)

  @@unique([competitionId, position])
  @@index([competitionId])
}

model Lift {
  id              String   @id @default(uuid())
  competitionId   String
  liftNumber      Int      // Simple sequential: 1, 2, 3, 4, 5...
  status          String   // PENDING, IN_PROGRESS, COMPLETED
  result          String?  // GOOD_LIFT, NO_LIFT (null until all 3 votes in)
  timerStartedAt  DateTime?
  timerResetCount Int      @default(0)

  competition     Competition @relation(fields: [competitionId], references: [id], onDelete: Cascade)
  votes           Vote[]

  createdAt       DateTime @default(now())
  completedAt     DateTime?

  @@index([competitionId, liftNumber])
  @@index([competitionId, status])
}

model Vote {
  id            String   @id @default(uuid())
  liftId        String
  judgePosition String   // LEFT, CENTER, RIGHT
  decision      String   // WHITE, RED
  timestamp     DateTime @default(now())

  lift          Lift     @relation(fields: [liftId], references: [id], onDelete: Cascade)

  @@unique([liftId, judgePosition])
  @@index([liftId])
}
```

---

## Table Descriptions

### Competition Table

Stores the basic competition information and access tokens.

**Fields:**
- `id` (UUID): Unique competition identifier
- `name` (String): Competition name (e.g., "Spring Open 2026")
- `date` (DateTime, optional): Competition date
- `status` (String): Competition status
  - `SETUP`: Competition created, waiting to start
  - `ACTIVE`: Competition in progress
  - `ENDED`: Competition finished
- `judgeToken` (String, unique): Shared token for all 3 judges
- `audienceToken` (String, unique): Token for audience display
- `adminToken` (String, unique): Token for admin to delete competition
- `createdAt` (DateTime): When competition was created
- `endedAt` (DateTime, optional): When competition was ended

**Relationships:**
- One-to-many with Lift
- One-to-many with JudgePosition

**Indexes:** None needed (small dataset)

---

### JudgePosition Table

Tracks which judge has claimed which position (LEFT/CENTER/RIGHT).

**Fields:**
- `id` (UUID): Unique position claim identifier
- `competitionId` (String): Foreign key to Competition
- `position` (String): Judge position
  - `LEFT`: Side referee (left)
  - `CENTER`: Head referee (center, timer controls)
  - `RIGHT`: Side referee (right)
- `sessionId` (String): Browser session ID of judge who claimed position
- `claimedAt` (DateTime): When position was claimed

**Constraints:**
- `UNIQUE(competitionId, position)`: Prevents same position being claimed twice
- `ON DELETE CASCADE`: When competition deleted, all positions deleted

**Indexes:**
- `competitionId`: Fast lookups for position availability

**Business Logic:**
- First judge to SELECT a position gets it (server-side race condition handling)
- Judge can RELEASE position (when timer not running)
- Released position becomes available for other judges

---

### Lift Table

Represents individual numbered lifts for judges to vote on.

**Fields:**
- `id` (UUID): Unique lift identifier
- `competitionId` (String): Foreign key to Competition
- `liftNumber` (Int): Sequential lift number (1, 2, 3, 4, 5...)
- `status` (String): Lift status
  - `PENDING`: Not yet active
  - `IN_PROGRESS`: Currently active, judges voting
  - `COMPLETED`: All 3 votes received, result calculated
- `result` (String, optional): Lift result (null until all 3 votes in)
  - `GOOD_LIFT`: 2 or 3 WHITE votes
  - `NO_LIFT`: 2 or 3 RED votes
- `timerStartedAt` (DateTime, optional): When CENTER judge started timer
- `timerResetCount` (Int): How many times timer was reset (for statistics)
- `createdAt` (DateTime): When lift was created
- `completedAt` (DateTime, optional): When lift was completed (all 3 votes in)

**Constraints:**
- `ON DELETE CASCADE`: When competition deleted, all lifts deleted

**Indexes:**
- `(competitionId, liftNumber)`: Find specific lift by number
- `(competitionId, status)`: Find active lift in competition

**Business Logic:**
- Lifts created automatically when competition starts (e.g., 10 lifts)
- CENTER judge activates next lift with "NEXT LIFT" button
- Result calculated when 3rd vote submitted

---

### Vote Table

Stores judge votes (WHITE or RED light) for each lift.

**Fields:**
- `id` (UUID): Unique vote identifier
- `liftId` (String): Foreign key to Lift
- `judgePosition` (String): Which judge voted
  - `LEFT`, `CENTER`, or `RIGHT`
- `decision` (String): Vote decision
  - `WHITE`: Good lift
  - `RED`: No lift
- `timestamp` (DateTime): When vote was submitted

**Constraints:**
- `UNIQUE(liftId, judgePosition)`: Each judge can only vote once per lift (prevents duplicates)
- `ON DELETE CASCADE`: When lift deleted, all votes deleted

**Indexes:**
- `liftId`: Fast vote lookups for result calculation

**Business Logic:**
- Judges can CHANGE vote before 3rd vote submitted (UPDATE operation)
- After 3rd vote: Result calculated, voting locked (403 Forbidden on changes)

---

## Entity Relationship Diagram

```
┌─────────────────────┐
│    Competition      │
│                     │
│ - id (PK)           │
│ - name              │
│ - date              │
│ - status            │
│ - judgeToken        │
│ - audienceToken     │
│ - adminToken        │
│ - createdAt         │
│ - endedAt           │
└──────┬──────────────┘
       │
       │ 1:N
       ├────────────────────────────────┐
       │                                │
       │                                │
┌──────▼──────────────┐     ┌───────────▼────────────┐
│   JudgePosition     │     │        Lift            │
│                     │     │                        │
│ - id (PK)           │     │ - id (PK)              │
│ - competitionId (FK)│     │ - competitionId (FK)   │
│ - position          │     │ - liftNumber           │
│ - sessionId         │     │ - status               │
│ - claimedAt         │     │ - result               │
│                     │     │ - timerStartedAt       │
│ UNIQUE:             │     │ - timerResetCount      │
│ (competitionId,     │     │ - createdAt            │
│  position)          │     │ - completedAt          │
└─────────────────────┘     └────────┬───────────────┘
                                     │
                                     │ 1:N
                                     │
                             ┌───────▼────────────┐
                             │       Vote         │
                             │                    │
                             │ - id (PK)          │
                             │ - liftId (FK)      │
                             │ - judgePosition    │
                             │ - decision         │
                             │ - timestamp        │
                             │                    │
                             │ UNIQUE:            │
                             │ (liftId,           │
                             │  judgePosition)    │
                             └────────────────────┘
```

---

## Database Initialization

When a competition is created:

1. **Competition record created** with name, date, tokens
2. **10 lifts auto-created** with status `PENDING`
   - Lift numbers: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10
   - First lift (liftNumber=1) set to status `IN_PROGRESS`
3. **Competition status** set to `ACTIVE`

Example initialization SQL:

```sql
-- Create competition
INSERT INTO Competition (id, name, date, status, judgeToken, audienceToken, adminToken, createdAt)
VALUES ('uuid-1', 'Test Competition', '2026-02-01', 'ACTIVE', 'judge-token-abc', 'audience-token-xyz', 'admin-token-123', datetime('now'));

-- Create 10 lifts (first one active)
INSERT INTO Lift (id, competitionId, liftNumber, status, createdAt) VALUES
  ('lift-1', 'uuid-1', 1, 'IN_PROGRESS', datetime('now')),
  ('lift-2', 'uuid-1', 2, 'PENDING', datetime('now')),
  ('lift-3', 'uuid-1', 3, 'PENDING', datetime('now')),
  ('lift-4', 'uuid-1', 4, 'PENDING', datetime('now')),
  ('lift-5', 'uuid-1', 5, 'PENDING', datetime('now')),
  ('lift-6', 'uuid-1', 6, 'PENDING', datetime('now')),
  ('lift-7', 'uuid-1', 7, 'PENDING', datetime('now')),
  ('lift-8', 'uuid-1', 8, 'PENDING', datetime('now')),
  ('lift-9', 'uuid-1', 9, 'PENDING', datetime('now')),
  ('lift-10', 'uuid-1', 10, 'PENDING', datetime('now'));
```

---

## Comparison to Full System Schema

**Tables REMOVED from full system:**
- ❌ `Group` - No grouping in MVP
- ❌ `Flight` - No flight organization in MVP
- ❌ `Athlete` - No athlete data in MVP
- ❌ `CompetitionManager` - Not needed for MVP
- ❌ `AthleteManager` - Not needed for MVP
- ❌ `PlatformLoader` - Not needed for MVP

**Fields REMOVED from Competition:**
- ❌ `competitionManagerToken` - Not used in MVP
- ❌ `athleteManagerToken` - Not used in MVP
- ❌ `loaderToken` - Not used in MVP
- ❌ `competitionHostToken` - Not used in MVP

**Fields REMOVED from Lift:**
- ❌ `athleteId` - No athletes in MVP
- ❌ `liftType` - No lift types in MVP
- ❌ `attemptNumber` - No attempts in MVP
- ❌ `weight` - No weights in MVP

**MVP Simplification Summary:**
- 4 tables instead of 10+
- 3 tokens instead of 7
- Simple numbered lifts instead of complex athlete/flight/group hierarchy

---

## Migration Strategy

### Initial Migration

```bash
npx prisma migrate dev --name init_mvp
```

Creates the 4 tables with all constraints and indexes.

### Future Migrations

To migrate from MVP to full system:
1. Add `Group` and `Flight` tables
2. Add `Athlete` table
3. Add athlete-related fields to `Lift` table
4. Add additional tokens to `Competition` table
5. Migrate existing data (if any MVP competitions exist)

---

## Performance Considerations

**Expected Dataset Sizes:**
- **Competition:** 1-100 records (lifetime)
- **JudgePosition:** 3 records per competition
- **Lift:** 10-50 records per competition
- **Vote:** 30-150 records per competition (3 votes × 10-50 lifts)

**Indexes:**
- Minimal indexes needed due to small dataset
- Primary keys (UUID) auto-indexed
- Foreign keys indexed for JOIN performance
- Unique constraints auto-indexed

**Query Performance:**
- All queries < 10ms expected (SQLite in-memory + small dataset)
- No complex JOINs needed for MVP
- Socket.IO real-time updates reduce database polling

---

## Data Retention

**Competition Deletion:**
- Admin can manually delete competition via admin token
- CASCADE deletes all related data:
  - All lifts deleted
  - All votes deleted
  - All judge positions deleted
- Tokens become invalid immediately

**Future Feature (Not in MVP):**
- Auto-deletion after 3 days
- Archive completed competitions
- Export competition results to JSON/CSV

---

## Validation Rules

**Competition:**
- `name`: Required, max 200 characters
- `status`: Must be SETUP, ACTIVE, or ENDED
- `judgeToken`, `audienceToken`, `adminToken`: Must be unique, minimum 32 characters

**JudgePosition:**
- `position`: Must be LEFT, CENTER, or RIGHT
- `sessionId`: Required, minimum 8 characters
- UNIQUE constraint enforced at database level

**Lift:**
- `liftNumber`: Must be positive integer
- `status`: Must be PENDING, IN_PROGRESS, or COMPLETED
- `result`: Must be GOOD_LIFT or NO_LIFT (or null)
- `timerResetCount`: Must be non-negative integer

**Vote:**
- `judgePosition`: Must be LEFT, CENTER, or RIGHT
- `decision`: Must be WHITE or RED
- UNIQUE constraint prevents duplicate votes

---

## Testing Data

For development/testing, seed the database with:

```typescript
// prisma/seed.ts
import { PrismaClient } from '@prisma/client'
import { randomBytes } from 'crypto'

const prisma = new PrismaClient()

async function main() {
  // Create test competition
  const competition = await prisma.competition.create({
    data: {
      name: 'Test Competition',
      date: new Date('2026-02-01'),
      status: 'ACTIVE',
      judgeToken: randomBytes(16).toString('hex'),
      audienceToken: randomBytes(16).toString('hex'),
      adminToken: randomBytes(16).toString('hex'),
    },
  })

  // Create 10 test lifts
  for (let i = 1; i <= 10; i++) {
    await prisma.lift.create({
      data: {
        competitionId: competition.id,
        liftNumber: i,
        status: i === 1 ? 'IN_PROGRESS' : 'PENDING',
      },
    })
  }

  console.log('Seeded test competition with 10 lifts')
}

main()
  .catch((e) => {
    console.error(e)
    process.exit(1)
  })
  .finally(async () => {
    await prisma.$disconnect()
  })
```

Run with: `npx prisma db seed`

---

## Summary

The MVP database schema is **deliberately minimal** to focus on core judging functionality:
- **4 tables** (Competition, JudgePosition, Lift, Vote)
- **3 tokens** (judge, audience, admin)
- **Numbered lifts** (no athlete data)
- **Simple relationships** (no groups/flights)

This schema supports:
✅ Judge position selection
✅ Vote submission and tracking
✅ Timer state management
✅ Competition lifecycle
✅ Admin deletion

**Not supported (out of MVP scope):**
❌ Athlete data management
❌ Weight tracking
❌ Groups and flights
❌ Multiple platforms
❌ Historical statistics
