# JudgeMe MVP - API Specification

**Version:** 1.0
**Last Updated:** 2026-01-20
**Status:** MVP Specification

---

## Overview

The MVP API provides REST endpoints for the core judging functionality. It includes:
- **7 total endpoints** covering all MVP features
- **Token-based authentication** (no user accounts)
- **JSON request/response format**
- **Standard HTTP status codes**
- **Socket.IO for real-time updates**

**Base URL:** `http://localhost:3001/api` (development)

---

## Authentication

**Token Types:**
1. **Judge Token** - Shared by all 3 judges
2. **Audience Token** - For audience display
3. **Admin Token** - For competition deletion

**Authentication Methods:**
- **Query Parameter:** `?token=<token>` (for initial page loads)
- **Authorization Header:** `Authorization: Bearer <token>` (for API calls)
- **Custom Header:** `X-Judge-Position: LEFT|CENTER|RIGHT` (for judge-specific actions)

**Token Format:**
- 32-character hex string (128-bit entropy)
- Example: `a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6`

---

## API Endpoints

### 1. Create Competition

Create a new competition and receive judge/audience URLs.

**Endpoint:** `POST /api/competitions`

**Authentication:** None required

**Request Body:**
```json
{
  "name": "Spring Open 2026",
  "date": "2026-02-15" // Optional
}
```

**Response:** `201 Created`
```json
{
  "competitionId": "uuid-123",
  "name": "Spring Open 2026",
  "date": "2026-02-15T00:00:00Z",
  "status": "ACTIVE",
  "judgeUrl": "http://localhost:5173/judge?token=a1b2c3d4...",
  "audienceUrl": "http://localhost:5173/audience?token=e5f6g7h8...",
  "adminToken": "i9j0k1l2..." // Return separately for admin to save
}
```

**Errors:**
- `400 Bad Request` - Invalid request body
  ```json
  {
    "error": "Competition name is required"
  }
  ```

**Notes:**
- Automatically creates 10 lifts (numbered 1-10)
- First lift (liftNumber=1) set to status `IN_PROGRESS`
- Competition status set to `ACTIVE`

---

### 2. Delete Competition

Admin deletes a competition and all related data.

**Endpoint:** `DELETE /api/competitions/:competitionId`

**Authentication:** Requires `adminToken`

**Headers:**
```
Authorization: Bearer i9j0k1l2m3n4o5p6...
```

**Response:** `200 OK`
```json
{
  "success": true,
  "message": "Competition deleted successfully"
}
```

**Errors:**
- `401 Unauthorized` - Missing or invalid admin token
  ```json
  {
    "error": "Invalid admin token"
  }
  ```
- `404 Not Found` - Competition not found
  ```json
  {
    "error": "Competition not found"
  }
  ```

**Notes:**
- CASCADE deletes all lifts, votes, and judge positions
- Tokens become invalid immediately
- Socket.IO emits `competition_deleted` event

---

### 3. Select Judge Position

Judge claims a position (LEFT, CENTER, or RIGHT).

**Endpoint:** `POST /api/judge/select-position`

**Authentication:** Requires `judgeToken`

**Request Body:**
```json
{
  "token": "a1b2c3d4e5f6g7h8...",
  "position": "CENTER",
  "sessionId": "browser-session-id-123"
}
```

**Response:** `200 OK`
```json
{
  "position": "CENTER",
  "sessionId": "browser-session-id-123",
  "claimedAt": "2026-02-15T14:30:00Z"
}
```

**Errors:**
- `401 Unauthorized` - Invalid judge token
  ```json
  {
    "error": "Invalid judge token"
  }
  ```
- `409 Conflict` - Position already taken
  ```json
  {
    "error": "Position already taken by another judge"
  }
  ```
- `400 Bad Request` - Invalid position
  ```json
  {
    "error": "Position must be LEFT, CENTER, or RIGHT"
  }
  ```

**Notes:**
- Server-side race condition handling (database UNIQUE constraint)
- Socket.IO emits `position_claimed` event to all clients
- Position locked until released

---

### 4. Release Judge Position

Judge releases their claimed position.

**Endpoint:** `DELETE /api/judge/release-position`

**Authentication:** Requires `judgeToken` + `sessionId`

**Request Body:**
```json
{
  "token": "a1b2c3d4e5f6g7h8...",
  "sessionId": "browser-session-id-123"
}
```

**Response:** `200 OK`
```json
{
  "success": true,
  "message": "Position released successfully"
}
```

**Errors:**
- `401 Unauthorized` - Invalid token or session ID
  ```json
  {
    "error": "Invalid session or not authorized to release"
  }
  ```
- `409 Conflict` - Cannot release while timer running (CENTER judge only)
  ```json
  {
    "error": "Cannot release position while timer is running"
  }
  ```

**Notes:**
- CENTER judge cannot release while timer is running
- Socket.IO emits `position_released` event
- Position becomes available for other judges

---

### 5. Submit Vote

Judge submits vote (WHITE or RED) for current lift.

**Endpoint:** `POST /api/votes`

**Authentication:** Requires `judgeToken` + judge position claimed

**Request Body:**
```json
{
  "liftId": "lift-uuid-123",
  "judgePosition": "CENTER",
  "decision": "WHITE",
  "sessionId": "browser-session-id-123"
}
```

**Response:** `201 Created`
```json
{
  "voteId": "vote-uuid-456",
  "liftId": "lift-uuid-123",
  "judgePosition": "CENTER",
  "decision": "WHITE",
  "timestamp": "2026-02-15T14:35:00Z"
}
```

**Errors:**
- `401 Unauthorized` - Invalid token or position not claimed
  ```json
  {
    "error": "Judge position not claimed"
  }
  ```
- `409 Conflict` - Judge already voted for this lift
  ```json
  {
    "error": "Judge already voted for this lift. Use PUT to change vote."
  }
  ```
- `400 Bad Request` - Invalid decision
  ```json
  {
    "error": "Decision must be WHITE or RED"
  }
  ```

**Notes:**
- Database UNIQUE constraint prevents duplicate votes
- Socket.IO emits `vote_submitted` event (internal only, not shown to audience)
- When 3rd vote received: Calculate result, emit `lift_completed` event

---

### 6. Change Vote

Judge changes their vote (before all 3 judges have voted).

**Endpoint:** `PUT /api/votes/:voteId`

**Authentication:** Requires `judgeToken` + same session ID that submitted original vote

**Request Body:**
```json
{
  "decision": "RED",
  "sessionId": "browser-session-id-123"
}
```

**Response:** `200 OK`
```json
{
  "voteId": "vote-uuid-456",
  "liftId": "lift-uuid-123",
  "judgePosition": "CENTER",
  "decision": "RED",
  "timestamp": "2026-02-15T14:35:30Z"
}
```

**Errors:**
- `401 Unauthorized` - Not authorized to change this vote
  ```json
  {
    "error": "Not authorized to change this vote"
  }
  ```
- `403 Forbidden` - All 3 votes already received, voting locked
  ```json
  {
    "error": "Cannot change vote. All 3 judges have already voted."
  }
  ```

**Notes:**
- Checks if 3 votes exist for lift before allowing change
- Socket.IO emits `vote_changed` event
- Confirmation dialog shown in UI before calling this endpoint

---

### 7. Timer Controls (CENTER Judge Only)

#### 7a. Start Clock

CENTER judge starts 60-second countdown timer.

**Endpoint:** `POST /api/lifts/:liftId/start-clock`

**Authentication:** Requires `judgeToken` + `X-Judge-Position: CENTER`

**Headers:**
```
Authorization: Bearer a1b2c3d4e5f6g7h8...
X-Judge-Position: CENTER
```

**Request Body:**
```json
{
  "sessionId": "browser-session-id-123"
}
```

**Response:** `200 OK`
```json
{
  "liftId": "lift-uuid-123",
  "timerStartedAt": "2026-02-15T14:36:00Z",
  "expiresAt": "2026-02-15T14:37:00Z"
}
```

**Errors:**
- `403 Forbidden` - Not CENTER judge
  ```json
  {
    "error": "Only CENTER judge can start timer"
  }
  ```
- `409 Conflict` - Timer already running
  ```json
  {
    "error": "Timer already running"
  }
  ```

**Notes:**
- Socket.IO emits `clock_started` event
- Server emits `clock_tick` events every second (60, 59, 58... 0)
- At 0 seconds: Emits `clock_expired` event (does NOT auto-fail lift)

---

#### 7b. Reset Clock

CENTER judge resets timer to 60 seconds.

**Endpoint:** `POST /api/lifts/:liftId/reset-clock`

**Authentication:** Requires `judgeToken` + `X-Judge-Position: CENTER`

**Headers:**
```
Authorization: Bearer a1b2c3d4e5f6g7h8...
X-Judge-Position: CENTER
```

**Request Body:**
```json
{
  "sessionId": "browser-session-id-123"
}
```

**Response:** `200 OK`
```json
{
  "liftId": "lift-uuid-123",
  "timerReset": true,
  "timerResetCount": 1
}
```

**Errors:**
- `403 Forbidden` - Not CENTER judge
  ```json
  {
    "error": "Only CENTER judge can reset timer"
  }
  ```

**Notes:**
- Stops countdown, returns timer to 60 seconds
- Increments `timerResetCount` in database
- Socket.IO emits `clock_reset` event
- CENTER judge must press START again to restart countdown

---

#### 7c. Complete Lift (Next Lift)

CENTER judge advances to next lift after voting complete.

**Endpoint:** `POST /api/lifts/:liftId/complete`

**Authentication:** Requires `judgeToken` + `X-Judge-Position: CENTER`

**Headers:**
```
Authorization: Bearer a1b2c3d4e5f6g7h8...
X-Judge-Position: CENTER
```

**Request Body:**
```json
{
  "sessionId": "browser-session-id-123"
}
```

**Response:** `200 OK`
```json
{
  "currentLiftId": "lift-uuid-123",
  "currentLiftNumber": 5,
  "nextLiftId": "lift-uuid-124",
  "nextLiftNumber": 6
}
```

**Response (Last Lift):** `200 OK`
```json
{
  "currentLiftId": "lift-uuid-130",
  "currentLiftNumber": 10,
  "nextLiftId": null,
  "message": "Competition complete. All lifts finished."
}
```

**Errors:**
- `403 Forbidden` - Not CENTER judge
  ```json
  {
    "error": "Only CENTER judge can advance to next lift"
  }
  ```
- `409 Conflict` - Current lift not yet completed (less than 3 votes)
  ```json
  {
    "error": "Cannot advance. Current lift not yet completed (need 3 votes)"
  }
  ```

**Notes:**
- Marks current lift as `COMPLETED`
- Sets next lift to `IN_PROGRESS`
- Timer remains at 60 seconds (not started)
- Socket.IO emits `next_lift_started` event
- If last lift: No next lift created, competition ready to end

---

## Socket.IO Events

### Server → Client Events

#### `position_claimed`
Emitted when a judge claims a position.

```json
{
  "competitionId": "uuid-123",
  "position": "CENTER",
  "claimedAt": "2026-02-15T14:30:00Z"
}
```

#### `position_released`
Emitted when a judge releases a position.

```json
{
  "competitionId": "uuid-123",
  "position": "CENTER",
  "releasedAt": "2026-02-15T14:40:00Z"
}
```

#### `clock_started`
Emitted when CENTER judge starts timer.

```json
{
  "liftId": "lift-uuid-123",
  "startTime": "2026-02-15T14:36:00Z",
  "duration": 60
}
```

#### `clock_tick`
Emitted every second during countdown.

```json
{
  "liftId": "lift-uuid-123",
  "remainingSeconds": 45
}
```

#### `clock_reset`
Emitted when CENTER judge resets timer.

```json
{
  "liftId": "lift-uuid-123"
}
```

#### `clock_expired`
Emitted when timer reaches 0.

```json
{
  "liftId": "lift-uuid-123",
  "expiredAt": "2026-02-15T14:37:00Z"
}
```

#### `vote_submitted` (Internal Only)
Emitted when a judge votes (not shown to audience).

```json
{
  "liftId": "lift-uuid-123",
  "voteCount": 2
}
```

#### `lift_completed` (Public)
Emitted when all 3 votes received. **Shown to audience.**

```json
{
  "liftId": "lift-uuid-123",
  "liftNumber": 5,
  "result": "GOOD_LIFT",
  "votes": [
    { "position": "LEFT", "decision": "WHITE" },
    { "position": "CENTER", "decision": "WHITE" },
    { "position": "RIGHT", "decision": "RED" }
  ],
  "completedAt": "2026-02-15T14:35:30Z"
}
```

#### `next_lift_started`
Emitted when CENTER judge advances to next lift.

```json
{
  "liftId": "lift-uuid-124",
  "liftNumber": 6
}
```

#### `competition_deleted`
Emitted when admin deletes competition.

```json
{
  "competitionId": "uuid-123",
  "message": "Competition has been deleted"
}
```

---

### Client → Server Events

#### `join_competition`
Client subscribes to competition updates.

```json
{
  "competitionId": "uuid-123",
  "token": "a1b2c3d4e5f6g7h8..."
}
```

#### `leave_competition`
Client unsubscribes from competition updates.

```json
{
  "competitionId": "uuid-123"
}
```

---

## Error Handling

**Standard Error Response Format:**
```json
{
  "error": "Human-readable error message",
  "code": "ERROR_CODE",
  "details": {} // Optional additional details
}
```

**HTTP Status Codes:**
- `200 OK` - Request successful
- `201 Created` - Resource created successfully
- `400 Bad Request` - Invalid request body or parameters
- `401 Unauthorized` - Missing or invalid authentication
- `403 Forbidden` - Not authorized for this action
- `404 Not Found` - Resource not found
- `409 Conflict` - Conflict with current state (position taken, timer running, etc.)
- `500 Internal Server Error` - Server error

---

## Rate Limiting

**MVP:** No rate limiting implemented

**Future Enhancement:**
- 100 requests per minute per IP
- 1000 requests per hour per IP
- Vote submissions: 10 per minute per judge

---

## CORS Configuration

**Development:**
```javascript
app.use(cors({
  origin: 'http://localhost:5173', // Vite dev server
  credentials: true
}))
```

**Production:**
```javascript
app.use(cors({
  origin: process.env.FRONTEND_URL,
  credentials: true
}))
```

---

## API Testing Examples

### cURL Examples

**Create Competition:**
```bash
curl -X POST http://localhost:3001/api/competitions \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Competition","date":"2026-02-15"}'
```

**Select Judge Position:**
```bash
curl -X POST http://localhost:3001/api/judge/select-position \
  -H "Content-Type: application/json" \
  -d '{"token":"a1b2c3d4...","position":"CENTER","sessionId":"session-123"}'
```

**Submit Vote:**
```bash
curl -X POST http://localhost:3001/api/votes \
  -H "Content-Type: application/json" \
  -d '{"liftId":"lift-uuid-123","judgePosition":"CENTER","decision":"WHITE","sessionId":"session-123"}'
```

**Start Clock:**
```bash
curl -X POST http://localhost:3001/api/lifts/lift-uuid-123/start-clock \
  -H "Authorization: Bearer a1b2c3d4..." \
  -H "X-Judge-Position: CENTER" \
  -H "Content-Type: application/json" \
  -d '{"sessionId":"session-123"}'
```

---

## Summary

The MVP API provides **7 REST endpoints** covering:
- ✅ Competition creation and deletion
- ✅ Judge position selection and release
- ✅ Vote submission and changing
- ✅ Timer controls (CENTER judge only)
- ✅ Lift progression (CENTER judge only)

**Socket.IO real-time events:**
- ✅ Position claiming/releasing
- ✅ Timer countdown (every second)
- ✅ Vote submission (internal)
- ✅ Lift completion (public, simultaneous reveal)
- ✅ Next lift activation

**Not included in MVP:**
- ❌ Athlete management endpoints
- ❌ Weight update endpoints
- ❌ Platform loader endpoints
- ❌ Competition Manager endpoints
- ❌ Historical statistics endpoints
