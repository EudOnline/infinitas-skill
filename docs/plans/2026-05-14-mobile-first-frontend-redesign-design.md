# Mobile-First Frontend Redesign

Date: 2026-05-14
Status: Approved

## Problem

The frontend has four systemic mobile UX issues: operations require too many steps, tables are unusable on small screens, there is no operation guidance, and no global perspective ("who am I, what do I have"). Additionally, the project lacks an archive/profile system for agents, and the frontend exposes creation flows that humans never use directly.

## Context

- Humans manage skills and tokens; they do not create skills via the UI
- Agents (using tokens) create, publish, share skills via API
- Both humans and agents need a shared archive for bidirectional collaboration
- The kawaii visual style is good and should be preserved
- Tech stack stays: Jinja2 templates, vanilla JS, Tailwind CSS, FastAPI

## Design Decisions

### 1. Information Architecture: 3-Tab Navigation

Replace the current 6 top-level pages with 3 tabs:

**Tab 1: Home (Dashboard)**
- One-line summary: active tokens count, accessible skills count, new activity count
- Quick actions: copy task prompt, recently used skill cards (swipeable)
- Status signals: expiring tokens, new share requests, agent writeback notifications
- Entry points: quick commands for agents (one-tap copy install commands)

**Tab 2: Profile (Agent Archive)**
- Per-agent personal view identified by Bearer token or cookie
- Sub-tabs: Accessible Skills, Operation History, Policy & Constraints
- Agent identity card: principal, role, token expiry, permission scopes
- Bidirectional collaboration: human sets policies, agent executes and writes back results
- Human can switch to view any agent's profile (maintainer role)

**Tab 3: Management (Human Admin)**
- Visible only to maintainer/contributor roles
- Sub-views via filter chips: Library, Tokens, Shares, Activity
- Mobile: card-based layout; Desktop: optimized tables
- All CRUD for tokens, shares, and visibility management

**Navigation changes:**
- Mobile: bottom tab bar (3 buttons, 56px height)
- Desktop: top tab bar, current position preserved
- Detail pages (object, release) accessed via card tap, breadcrumb back

### 2. Mobile Interaction Patterns

**Card flow replaces tables:**
- Each card shows one entity with primary action button + danger action (text link)
- Swipe left on card to reveal quick actions (revoke, copy)
- State signals via color: active (green), expired (gray), revoked (red)

**Operation shortcuts:**

| Operation | Before | After |
|-----------|--------|-------|
| Revoke token | Detail page -> find token -> click revoke -> confirm | Swipe card -> revoke |
| Copy install command | Home -> find button -> click copy | Home card -> one-tap copy |
| View skill detail | Nav -> Library -> find skill -> click | Profile card -> direct tap |
| Create share link | Release detail -> fill form -> submit | Management -> long-press object -> share |

**Empty state guidance:**
- Home empty -> "No agents connected yet. Copy task prompt to get started"
- Profile empty -> "This agent has no activity yet"
- Management empty -> "No skills yet. Agents will create them via API"

**Touch optimization:**
- All touch targets >= 44x44px (maintained)
- Tab bar buttons 56px height with safe area padding
- Bottom tab bar respects iPhone safe area

### 3. Agent Profile/Archive System

**Data model:** No new database tables. Profile is a view layer aggregating:
- Identity: Principal + Credential (token info)
- Accessible skills: RegistryObjects via AccessGrant
- Operation history: AuditEvents filtered by credential_id
- Policy constraints: Extended from Credential.constraints_json
- Writeback records: AuditEvents with type memory_writeback

**Pages:**
- `/profile` -- Current agent's profile (auto-detected via token/cookie)
- `/profile/{credential_id}` -- Admin view of any agent's profile

**Bidirectional collaboration:**
- Human -> Agent: Policy rules set via Management tab, stored in Credential.constraints_json. Examples: `{"max_daily_publishes": 5, "allowed_object_kinds": ["skill"], "readonly": false}`
- Agent -> Human: Writeback via API, displayed in Profile operation history with `memory_writeback` tag. Human sees summary in Management tab.

**New API endpoints:**

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/profile/me` | GET | Full profile for current agent (identity + skills + history + policy) |
| `/api/v1/profile/{credential_id}` | GET | Admin view of any agent's profile |
| `/api/v1/profile/writeback` | POST | Agent writes back operation notes/results |
| `/api/v1/credentials/{id}/policy` | PATCH | Human updates agent policy constraints |

### 4. Removed Frontend Features

| Feature | Disposition |
|---------|-------------|
| Draft create/edit/seal | Frontend removed, API only |
| Version management | Frontend removed, API only |
| Exposure CRUD forms | Frontend removed from release detail, API only |
| Review workflow UI | Frontend removed, API only |
| Object creation buttons | Frontend removed, API only |
| Release detail forms | Simplified to read-only view |

### 5. Preserved Elements

- Kawaii visual style (colors, fonts, shadows, animations)
- Tailwind + PostCSS build pipeline
- Jinja2 template engine
- All existing backend API routes (only additions, no deletions)
- i18n system (zh/en)
- Authentication flow (cookie + Bearer token dual auth)
- Database models
- Background job system

## File Changes Summary

### Removed/simplified templates
- `release-detail-v2.html` -> simplified to read-only
- `console-forbidden.html` -> kept as-is
- `error.html` -> kept as-is

### Rewritten templates
- `layout-kawaii.html` -- New navigation: top tabs (desktop) / bottom tab bar (mobile)
- `index-kawaii.html` -- Redesigned as status dashboard
- `library.html` -- Merged into Management tab, mobile card layout
- `object-detail.html` -- Simplified, read-only focus
- `access-center.html` -- Merged into Management tab, card-based tokens
- `shares.html` -- Merged into Management tab, card-based
- `activity.html` -- Merged into Management tab, timeline view

### New templates
- `profile.html` -- Agent profile page (3 sub-tabs)
- `partials/tab-bar.html` -- Bottom tab bar component for mobile
- `partials/card-token.html` -- Token card component
- `partials/card-skill.html` -- Skill card component
- `partials/card-share.html` -- Share card component
- `partials/empty-state.html` -- Empty state guidance component

### New JavaScript modules
- `js/modules/profile.js` -- Profile page interactions
- `js/modules/card-swipe.js` -- Mobile card swipe gesture library
- `js/modules/bottom-tabs.js` -- Bottom tab bar behavior

### New server modules
- `server/api/profile.py` -- Profile API routes
- Updates to `server/ui/routes.py` for new page routes

### Updated JavaScript modules
- `js/modules/lifecycle.js` -- Remove creation/exposure forms, keep read operations
- `js/modules/release-admin.js` -- Simplify to read-only display
- `js/app.js` -- Update for new navigation structure
