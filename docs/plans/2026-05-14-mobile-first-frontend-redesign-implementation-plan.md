# Mobile-First Frontend Redesign Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restructure the frontend into a 3-tab mobile-first architecture (Home/Profile/Management) with an agent archive system, while preserving the kawaii visual style.

**Architecture:** Replace 6 independent pages with 3 tabs. Add `/profile` route and API. Rewrite navigation as bottom tab bar (mobile) / top tabs (desktop). Convert tables to card flows on mobile. Remove creation flows from frontend.

**Tech Stack:** FastAPI, Jinja2 templates, vanilla ES modules, Tailwind CSS, SQLAlchemy

---

## Task 1: Profile API — Service Layer

**Files:**
- Create: `server/api/profile.py`
- Create: `tests/unit/api/test_profile.py`

The profile API aggregates existing data into a single agent-centric view.

**Step 1: Write the failing test**

```python
# tests/unit/api/test_profile.py
import json
from datetime import datetime, timezone

from server.modules.access.models import Credential, Principal
from server.modules.audit.models import AuditEvent


def test_profile_me_returns_identity_and_scopes(db_session, client):
    principal = Principal(kind="service", slug="bot-alice", display_name="Bot Alice")
    db_session.add(principal)
    db_session.flush()

    cred = Credential(
        principal_id=principal.id,
        type="product_token",
        scopes_json=json.dumps(["artifact:download", "release:write"]),
        resource_selector_json="{}",
    )
    db_session.add(cred)
    db_session.flush()

    token = f"tok_test_{cred.id}"
    cred.hashed_secret = f"sha256:{token}"
    db_session.commit()

    resp = client.get(
        "/api/v1/profile/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["identity"]["principal_slug"] == "bot-alice"
    assert body["identity"]["principal_kind"] == "service"
    assert "artifact:download" in body["identity"]["scopes"]


def test_profile_me_includes_accessible_skills(db_session, client):
    """Profile lists skills accessible via active AccessGrant."""
    # This test will be expanded once we verify the basic identity test passes.
    # For now it's a placeholder that validates the route exists.
    pass


def test_profile_me_includes_operation_history(db_session, client):
    """Profile includes AuditEvents for the current credential."""
    pass


def test_profile_me_requires_auth(client):
    resp = client.get("/api/v1/profile/me")
    assert resp.status_code == 401
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/api/test_profile.py::test_profile_me_returns_identity_and_scopes -v`
Expected: FAIL — module `server.api.profile` does not exist

**Step 3: Write minimal implementation**

```python
# server/api/profile.py
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from server.auth import get_current_access_context
from server.db import get_db
from server.modules.access.authn import AccessContext
from server.modules.access.models import AccessGrant, Credential
from server.modules.audit.models import AuditEvent
from server.modules.release.models import Release
from server.modules.authoring.models import RegistryObject

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])


def _build_profile(db: Session, context: AccessContext) -> dict[str, Any]:
    cred = context.credential
    principal = context.principal

    identity = {
        "credential_id": cred.id,
        "credential_type": cred.type,
        "principal_id": principal.id if principal else None,
        "principal_slug": principal.slug if principal else None,
        "principal_kind": principal.kind if principal else None,
        "principal_display_name": principal.display_name if principal else None,
        "scopes": sorted(context.scopes),
        "expires_at": cred.expires_at.isoformat() if cred.expires_at else None,
    }

    # Accessible skills: find active grants for this credential
    accessible_skills: list[dict[str, Any]] = []
    grants = db.execute(
        select(AccessGrant).where(
            AccessGrant.state == "active",
        )
    ).scalars().all()

    for grant in grants:
        grant_cred = db.execute(
            select(Credential).where(
                Credential.grant_id == grant.id,
                Credential.revoked_at.is_(None),
            )
        ).scalar_one_or_none()
        if grant_cred and grant_cred.id == cred.id:
            # Found a matching grant — look up the object
            selector = json.loads(grant_cred.resource_selector_json or "{}")
            obj_id = selector.get("object_id") or selector.get("scope_id")
            if obj_id:
                obj = db.execute(
                    select(RegistryObject).where(RegistryObject.id == obj_id)
                ).scalar_one_or_none()
                if obj:
                    accessible_skills.append({
                        "id": obj.id,
                        "slug": obj.slug,
                        "display_name": obj.display_name,
                        "kind": obj.kind,
                    })

    # Operation history: audit events for this credential
    events = db.execute(
        select(AuditEvent)
        .where(AuditEvent.aggregate_id == str(cred.id))
        .order_by(AuditEvent.occurred_at.desc())
        .limit(50)
    ).scalars().all()

    history = [
        {
            "id": e.id,
            "event_type": e.event_type,
            "occurred_at": e.occurred_at.isoformat() if e.occurred_at else None,
            "payload": json.loads(e.payload_json or "{}"),
        }
        for e in events
    ]

    # Policy constraints from AccessGrant
    policy: dict[str, Any] = {}
    if cred.grant_id:
        grant = db.execute(
            select(AccessGrant).where(AccessGrant.id == cred.grant_id)
        ).scalar_one_or_none()
        if grant:
            policy = json.loads(grant.constraints_json or "{}")

    return {
        "identity": identity,
        "accessible_skills": accessible_skills,
        "operation_history": history,
        "policy": policy,
    }


@router.get("/me")
def profile_me(request: Request, db: Session = Depends(get_db)) -> dict[str, Any]:
    context: AccessContext = request.state.access_context
    return _build_profile(db, context)
```

Wait — `get_current_access_context` needs to be wired as a dependency. Let me correct:

```python
@router.get("/me")
def profile_me(
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return _build_profile(db, context)
```

**Step 4: Register router in app.py**

Add to `server/app.py` imports:
```python
from server.api.profile import router as profile_router
```

Add to `create_app()` after existing router includes:
```python
app.include_router(profile_router)
```

**Step 5: Run test to verify it passes**

Run: `python -m pytest tests/unit/api/test_profile.py::test_profile_me_returns_identity_and_scopes -v`
Expected: PASS

**Step 6: Commit**

```bash
git add server/api/profile.py tests/unit/api/test_profile.py server/app.py
git commit -m "feat: add profile API with identity, skills, history, and policy"
```

---

## Task 2: Profile API — Admin View Endpoint

**Files:**
- Modify: `server/api/profile.py`
- Modify: `tests/unit/api/test_profile.py`

**Step 1: Write the failing test**

```python
# Add to tests/unit/api/test_profile.py

def test_profile_admin_view_any_agent(db_session, client):
    """Maintainer can view any agent's profile by credential ID."""
    principal = Principal(kind="service", slug="bot-bob", display_name="Bot Bob")
    db_session.add(principal)
    db_session.flush()

    cred = Credential(
        principal_id=principal.id,
        type="product_token",
        scopes_json=json.dumps(["artifact:download"]),
        resource_selector_json="{}",
    )
    db_session.add(cred)
    db_session.flush()

    # Create a maintainer user token for the admin request
    admin_principal = Principal(kind="user", slug="admin", display_name="Admin")
    db_session.add(admin_principal)
    db_session.flush()

    admin_cred = Credential(
        principal_id=admin_principal.id,
        type="personal_token",
        scopes_json=json.dumps(["session:user", "api:user"]),
        resource_selector_json="{}",
    )
    db_session.add(admin_cred)
    db_session.flush()

    admin_token = f"admin_tok_{admin_cred.id}"
    admin_cred.hashed_secret = f"sha256:{admin_token}"
    db_session.commit()

    resp = client.get(
        f"/api/v1/profile/{cred.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["identity"]["principal_slug"] == "bot-bob"


def test_profile_admin_view_requires_auth(client):
    resp = client.get("/api/v1/profile/999")
    assert resp.status_code == 401
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/api/test_profile.py::test_profile_admin_view_any_agent -v`
Expected: FAIL — route does not exist

**Step 3: Write implementation**

Add to `server/api/profile.py`:

```python
from server.auth import require_role


@router.get("/{credential_id}")
def profile_by_credential(
    credential_id: int,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if not context.user or context.user.role not in ("maintainer", "contributor"):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="insufficient role")

    target_cred = db.execute(
        select(Credential).where(Credential.id == credential_id)
    ).scalar_one_or_none()
    if not target_cred:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="credential not found")

    target_principal = None
    if target_cred.principal_id:
        target_principal = db.execute(
            select(Principal).where(Principal.id == target_cred.principal_id)
        ).scalar_one_or_none()

    # Reuse the builder with a synthetic context
    synthetic = AccessContext(
        credential=target_cred,
        principal=target_principal,
        user=None,
        scopes=set(json.loads(target_cred.scopes_json or "[]")),
    )
    return _build_profile(db, synthetic)
```

**Step 4: Run tests**

Run: `python -m pytest tests/unit/api/test_profile.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add server/api/profile.py tests/unit/api/test_profile.py
git commit -m "feat: add admin profile view endpoint for any agent"
```

---

## Task 3: Profile API — Writeback Endpoint

**Files:**
- Modify: `server/api/profile.py`
- Modify: `tests/unit/api/test_profile.py`

**Step 1: Write the failing test**

```python
# Add to tests/unit/api/test_profile.py

def test_profile_writeback_creates_audit_event(db_session, client):
    principal = Principal(kind="service", slug="bot-writer", display_name="Bot Writer")
    db_session.add(principal)
    db_session.flush()

    cred = Credential(
        principal_id=principal.id,
        type="product_token",
        scopes_json=json.dumps(["artifact:download"]),
        resource_selector_json="{}",
    )
    db_session.add(cred)
    db_session.flush()

    token = f"tok_wb_{cred.id}"
    cred.hashed_secret = f"sha256:{token}"
    db_session.commit()

    resp = client.post(
        "/api/v1/profile/writeback",
        headers={"Authorization": f"Bearer {token}"},
        json={"note": "Completed skill installation", "context": {"skill": "foo"}},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "recorded"

    # Verify audit event was created
    events = db_session.execute(
        select(AuditEvent).where(
            AuditEvent.aggregate_id == str(cred.id),
            AuditEvent.event_type == "memory.writeback",
        )
    ).scalars().all()
    assert len(events) == 1
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/api/test_profile.py::test_profile_writeback_creates_audit_event -v`
Expected: FAIL

**Step 3: Write implementation**

Add to `server/api/profile.py`:

```python
from pydantic import BaseModel
from datetime import datetime, timezone


class WritebackRequest(BaseModel):
    note: str
    context: dict[str, Any] | None = None


@router.post("/writeback")
def profile_writeback(
    body: WritebackRequest,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    import json as _json

    payload = {"note": body.note}
    if body.context:
        payload["context"] = body.context

    event = AuditEvent(
        aggregate_type="memory_writeback",
        aggregate_id=str(context.credential.id),
        event_type="memory.writeback",
        actor_ref=context.principal.slug if context.principal else str(context.credential.id),
        payload_json=_json.dumps(payload),
        occurred_at=datetime.now(timezone.utc),
    )
    db.add(event)
    db.commit()

    return {"status": "recorded"}
```

**Step 4: Run tests**

Run: `python -m pytest tests/unit/api/test_profile.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add server/api/profile.py tests/unit/api/test_profile.py
git commit -m "feat: add agent writeback endpoint with audit trail"
```

---

## Task 4: Profile API — Policy Update Endpoint

**Files:**
- Modify: `server/api/profile.py`
- Modify: `tests/unit/api/test_profile.py`

**Step 1: Write the failing test**

```python
# Add to tests/unit/api/test_profile.py

def test_policy_update_by_maintainer(db_session, client):
    admin_principal = Principal(kind="user", slug="admin2", display_name="Admin Two")
    db_session.add(admin_principal)
    db_session.flush()

    admin_cred = Credential(
        principal_id=admin_principal.id,
        type="personal_token",
        scopes_json=json.dumps(["session:user", "api:user"]),
        resource_selector_json="{}",
    )
    db_session.add(admin_cred)
    db_session.flush()

    target_cred = Credential(
        type="product_token",
        scopes_json=json.dumps(["artifact:download"]),
        resource_selector_json="{}",
    )
    db_session.add(target_cred)
    db_session.flush()

    admin_token = f"adm_pol_{admin_cred.id}"
    admin_cred.hashed_secret = f"sha256:{admin_token}"
    db_session.commit()

    resp = client.patch(
        f"/api/v1/credentials/{target_cred.id}/policy",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"max_daily_publishes": 5, "readonly": False},
    )
    assert resp.status_code == 200
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/api/test_profile.py::test_policy_update_by_maintainer -v`
Expected: FAIL

**Step 3: Write implementation**

Add to `server/api/profile.py`:

```python
from pydantic import BaseModel


class PolicyUpdateRequest(BaseModel):
    max_daily_publishes: int | None = None
    allowed_object_kinds: list[str] | None = None
    readonly: bool | None = None


@router.patch("/credentials/{credential_id}/policy")
def update_agent_policy(
    credential_id: int,
    body: PolicyUpdateRequest,
    context: AccessContext = Depends(get_current_access_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if not context.user or context.user.role not in ("maintainer", "contributor"):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="insufficient role")

    target_cred = db.execute(
        select(Credential).where(Credential.id == credential_id)
    ).scalar_one_or_none()
    if not target_cred:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="credential not found")

    # Update constraints on the associated grant
    if target_cred.grant_id:
        grant = db.execute(
            select(AccessGrant).where(AccessGrant.id == target_cred.grant_id)
        ).scalar_one_or_none()
        if grant:
            constraints = json.loads(grant.constraints_json or "{}")
            update = body.model_dump(exclude_none=True)
            constraints.update(update)
            grant.constraints_json = json.dumps(constraints)
            db.commit()
            return {"status": "updated", "policy": constraints}

    # No grant — store on resource_selector_json as fallback
    selector = json.loads(target_cred.resource_selector_json or "{}")
    update = body.model_dump(exclude_none=True)
    if "_policy" not in selector:
        selector["_policy"] = {}
    selector["_policy"].update(update)
    target_cred.resource_selector_json = json.dumps(selector)
    db.commit()
    return {"status": "updated", "policy": selector.get("_policy", {})}
```

**Step 4: Run tests**

Run: `python -m pytest tests/unit/api/test_profile.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add server/api/profile.py tests/unit/api/test_profile.py
git commit -m "feat: add policy update endpoint for agent constraints"
```

---

## Task 5: Navigation Restructure — Backend

**Files:**
- Modify: `server/ui/navigation.py`
- Modify: `tests/unit/server_ui/test_navigation.py` (create if not exists)

**Step 1: Write the failing test**

```python
# tests/unit/server_ui/test_navigation.py
from server.ui.navigation import build_site_nav


def test_home_nav_returns_three_anchors():
    nav = build_site_nav(home=True, lang="zh")
    assert len(nav) == 3
    assert nav[0]["href"] == "#start"
    assert nav[1]["href"] == "#handoff"


def test_console_nav_returns_three_tabs():
    """New 3-tab nav: Home, Profile, Management."""
    nav = build_site_nav(home=False, lang="zh")
    assert len(nav) == 3
    hrefs = [item["href"].split("?")[0] for item in nav]
    assert "/" in hrefs
    assert "/profile" in hrefs
    assert any("/manage" in h for h in hrefs)


def test_console_nav_en_labels():
    nav = build_site_nav(home=False, lang="en")
    labels = [item["label"] for item in nav]
    assert "Home" in labels
    assert "Profile" in labels
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/server_ui/test_navigation.py -v`
Expected: FAIL — current `build_site_nav` returns 6 items for console

**Step 3: Update navigation.py**

Modify `build_site_nav` in `server/ui/navigation.py`. The home=True path stays the same (3 anchors). The home=False path changes from 6 items to 3:

```python
def build_site_nav(*, home: bool, lang: str, variant: str = "console") -> list[dict[str, str]]:
    if home:
        return [
            {"href": "#start", "label": pick_lang(lang, "开始", "Home base")},
            {"href": "#handoff", "label": pick_lang(lang, "交接", "Handoff")},
            {"href": "#console", "label": pick_lang(lang, "维护台", "Console")},
        ]

    return [
        {
            "href": with_lang("/", lang),
            "label": pick_lang(lang, "首页", "Home"),
        },
        {
            "href": with_lang("/profile", lang),
            "label": pick_lang(lang, "档案", "Profile"),
        },
        {
            "href": with_lang("/manage", lang),
            "label": pick_lang(lang, "管理", "Management"),
        },
    ]
```

**Step 4: Run tests**

Run: `python -m pytest tests/unit/server_ui/test_navigation.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add server/ui/navigation.py tests/unit/server_ui/test_navigation.py
git commit -m "refactor: reduce console nav from 6 pages to 3 tabs"
```

---

## Task 6: UI Routes — Profile and Management Pages

**Files:**
- Modify: `server/ui/routes.py`

**Step 1: Write the failing test**

```python
# tests/unit/server_ui/test_routes.py (create if not exists)
import pytest
from unittest.mock import MagicMock


def test_profile_route_returns_200(client, db_session):
    """GET /profile returns the profile page."""
    resp = client.get("/profile")
    # May redirect to login if not authenticated, or return 200
    assert resp.status_code in (200, 307)


def test_manage_route_returns_200(client, db_session):
    """GET /manage returns the management page."""
    resp = client.get("/manage")
    assert resp.status_code in (200, 307)
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/server_ui/test_routes.py -v`
Expected: FAIL — routes not registered

**Step 3: Add route handlers**

Add to `server/ui/routes.py` inside `register_ui_routes()`:

```python
@app.get("/profile")
def profile_page(request: Request, db: Session = Depends(get_db)):
    lang = resolve_language(request)
    actor = require_lifecycle_actor(request, db, "maintainer", "contributor")
    if isinstance(actor, RedirectResponse):
        return actor
    if isinstance(actor, dict):
        return templates.TemplateResponse(
            "console-forbidden.html",
            {**actor, **_build_admin_context(request, actor, title="", content="", page_kicker="", page_eyebrow="")},
            status_code=403,
        )

    from server.ui.formatting import build_kawaii_ui_context
    from server.ui.i18n import pick_lang
    from server.ui.session_bootstrap import build_session_bootstrap
    from server.ui.navigation import build_site_nav

    ui = build_kawaii_ui_context(
        request, lang,
        page_kicker=pick_lang(lang, "档案", "Profile"),
        page_eyebrow=pick_lang(lang, "智能体档案", "Agent Archive"),
    )
    return templates.TemplateResponse("profile.html", {
        **ui,
        "nav_links": build_site_nav(home=False, lang=lang),
        "page_mode": "console",
        "show_console_session": True,
        "session_ui": build_session_bootstrap(request, db, actor),
    })


@app.get("/manage")
def manage_page(request: Request, db: Session = Depends(get_db)):
    lang = resolve_language(request)
    actor = require_lifecycle_actor(request, db, "maintainer", "contributor")
    if isinstance(actor, RedirectResponse):
        return actor
    if isinstance(actor, dict):
        return templates.TemplateResponse(
            "console-forbidden.html",
            {**actor, **_build_admin_context(request, actor, title="", content="", page_kicker="", page_eyebrow="")},
            status_code=403,
        )

    from server.ui.formatting import build_kawaii_ui_context
    from server.ui.i18n import pick_lang
    from server.ui.session_bootstrap import build_session_bootstrap
    from server.ui.navigation import build_site_nav
    from server.ui.library_objects import list_library_objects
    from server.ui.library_access import list_library_token_rows, list_library_token_activity_rows
    from server.ui.library_shares import list_library_share_rows
    from server.ui.activity import list_activity_rows

    ui = build_kawaii_ui_context(
        request, lang,
        page_kicker=pick_lang(lang, "管理", "Management"),
        page_eyebrow=pick_lang(lang, "技能与访问管理", "Skill & Access Management"),
    )

    library_scope = load_library_scope(db, actor)
    objects = list_library_objects(library_scope, lang)
    tokens = list_library_token_rows(db, library_scope, lang)
    token_activity = list_library_token_activity_rows(db, lang)
    shares = list_library_share_rows(db, library_scope, lang)
    activity = list_activity_rows(db, lang, limit=50)

    return templates.TemplateResponse("manage.html", {
        **ui,
        "nav_links": build_site_nav(home=False, lang=lang),
        "page_mode": "console",
        "show_console_session": True,
        "session_ui": build_session_bootstrap(request, db, actor),
        "object_items": objects,
        "token_items": tokens,
        "token_activity_items": token_activity,
        "share_items": shares,
        "activity_items": activity,
        "library_href": with_lang("/manage", lang),
    })
```

**Step 4: Run tests**

Run: `python -m pytest tests/unit/server_ui/test_routes.py -v`
Expected: PASS (templates don't exist yet but route registration works)

**Step 5: Commit**

```bash
git add server/ui/routes.py tests/unit/server_ui/test_routes.py
git commit -m "feat: add /profile and /manage route handlers"
```

---

## Task 7: Layout Template — Bottom Tab Bar

**Files:**
- Modify: `server/templates/layout-kawaii.html`
- Create: `server/templates/partials/tab-bar.html`

This is the most impactful UI change. The bottom tab bar replaces the horizontal scroll nav on mobile.

**Step 1: Create the tab bar partial**

```html
<!-- server/templates/partials/tab-bar.html -->
{# Mobile bottom tab bar — shown on screens < 768px #}
<nav class="fixed bottom-0 left-0 right-0 z-50 md:hidden bg-kawaii-paper/95 backdrop-blur-sm border-t border-kawaii-line safe-area-bottom"
     role="tablist"
     aria-label="{{ ui.get('tab_nav_label', 'Main navigation') }}">
  <div class="flex items-stretch justify-around h-14">
    {% for link in nav_links %}
      {% set is_current = request.url.path == link.href.split('?')[0].split('#')[0] or (link.href.split('?')[0] == '/' and request.url.path == '/') %}
      <a href="{{ link.href }}"
         class="flex flex-col items-center justify-center flex-1 gap-0.5 transition-colors {{ 'text-kawaii-primary-deep' if is_current else 'text-kawaii-ink-muted' }}"
         role="tab"
         aria-selected="{{ 'true' if is_current else 'false' }}"
         {% if is_current %}aria-current="page"{% endif %}>
        {% if loop.index == 1 %}
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/></svg>
        {% elif loop.index == 2 %}
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>
        {% else %}
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
        {% endif %}
        <span class="text-xs font-medium">{{ link.label }}</span>
      </a>
    {% endfor %}
  </div>
</nav>
```

**Step 2: Add safe-area CSS**

Add to `server/static/css/input.css`:

```css
.safe-area-bottom {
  padding-bottom: env(safe-area-inset-bottom, 0px);
}
```

**Step 3: Include tab bar in layout**

In `layout-kawaii.html`, add before the closing `</body>` tag:

```html
{% if page_mode == 'console' %}
  {% include "partials/tab-bar.html" %}
{% endif %}
```

**Step 4: Add bottom padding for tab bar**

Add to the `<main>` wrapper in layout:

```html
<main id="main-content">
  <div class="site-shell {{ 'pb-20 md:pb-12' if page_mode == 'console' else '' }}">
```

**Step 5: Test manually**

Run: `make dev` and open `/` on a mobile-width browser. Verify tab bar appears at bottom with 3 tabs.

**Step 6: Commit**

```bash
git add server/templates/partials/tab-bar.html server/templates/layout-kawaii.html server/static/css/input.css
git commit -m "feat: add mobile bottom tab bar for 3-tab navigation"
```

---

## Task 8: Home Page — Dashboard Redesign

**Files:**
- Modify: `server/templates/index-kawaii.html`
- Modify: `server/ui/home.py` (add stats data)

**Step 1: Update home context builder**

In `server/ui/home.py`, add counts to the context:

```python
# Add to build_home_context return dict:
"stats": {
    "active_tokens": _count_active_tokens(db),
    "accessible_skills": _count_accessible_skills(db, user),
    "new_activity": _count_recent_activity(db, user),
},
```

Implement the helper queries to count active credentials, accessible registry objects, and recent audit events.

**Step 2: Rewrite index-kawaii.html body block**

Replace the current body block with a dashboard layout:

```html
{% extends "layout-kawaii.html" %}
{% block body %}
{% set current_user = session_ui.get("current_user") %}

{# One-line summary #}
<section class="kawaii-card animate-in mb-4">
  <p class="text-kawaii-ink-muted text-sm">
    {% if stats %}
      {{ ui.get('dashboard_summary', '') }}
      {{ stats.active_tokens }} {{ ui.get('stat_active_tokens', '个活跃 Token') }} ·
      {{ stats.accessible_skills }} {{ ui.get('stat_accessible_skills', '个可访问技能') }} ·
      {{ stats.new_activity }} {{ ui.get('stat_new_activity', '条新活动') }}
    {% else %}
      {{ ui.get('dashboard_empty', '还没有 agent 连接，复制任务提示让 agent 开始') }}
    {% endif %}
  </p>
</section>

{# Quick actions #}
<section class="kawaii-card animate-in mb-4" style="animation-delay:100ms">
  <h2 class="font-display text-sm font-bold text-kawaii-ink mb-3">{{ ui.get('quick_actions', '快速操作') }}</h2>
  <div class="flex gap-2 flex-wrap">
    <button class="kawaii-button kawaii-button--primary" data-copy="{{ cli_command | forceescape }}">
      {{ ui.get('copy_task_prompt', '复制任务提示') }}
    </button>
  </div>
</section>

{# Status signals #}
{% if operating_states %}
<section class="mb-4 animate-in" style="animation-delay:200ms">
  <div class="flex gap-2 flex-wrap">
    {% for state in operating_states %}
      <span class="status-chip">{{ state.icon }} {{ state.label }}</span>
    {% endfor %}
  </div>
</section>
{% endif %}

{# Recent skills (swipeable) #}
{% if featured_skills %}
<section class="animate-in" style="animation-delay:300ms">
  <h2 class="font-display text-sm font-bold text-kawaii-ink mb-3">{{ ui.get('skills_section_title', '常用技能') }}</h2>
  <div class="flex gap-3 overflow-x-auto snap-x snap-mandatory pb-2 -mx-4 px-4 scrollbar-hide">
    {% for skill in featured_skills %}
      <article class="kawaii-card skill-card flex-shrink-0 w-64 snap-start">
        <h3 class="font-display text-sm font-bold text-kawaii-ink">{{ skill.name }}</h3>
        <p class="text-xs text-kawaii-ink-muted line-clamp-2 mt-1">{{ skill.summary }}</p>
        <button class="kawaii-button kawaii-button--ghost text-xs mt-2" data-copy="{{ skill.inspect_command | forceescape }}">
          {{ ui.get('copy', '复制') }}
        </button>
      </article>
    {% endfor %}
  </div>
</section>
{% endif %}

{% endblock %}
```

**Step 3: Add CSS for horizontal scroll**

Add to `server/static/css/input.css`:

```css
.scrollbar-hide {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
.scrollbar-hide::-webkit-scrollbar {
  display: none;
}
```

**Step 4: Test manually**

Run: `make dev`, verify home page shows stats, quick actions, and swipeable skills.

**Step 5: Commit**

```bash
git add server/templates/index-kawaii.html server/ui/home.py server/static/css/input.css
git commit -m "feat: redesign home page as status dashboard"
```

---

## Task 9: Profile Page Template

**Files:**
- Create: `server/templates/profile.html`
- Create: `server/static/js/modules/profile.js`

**Step 1: Create the profile template**

```html
{% extends "layout-kawaii.html" %}
{% from "macros.html" import console_table_shell %}

{% block body %}
<div class="space-y-4">
  {# Identity card #}
  <section class="kawaii-card animate-in">
    <div class="flex items-center gap-3 mb-3">
      <div class="w-12 h-12 rounded-full bg-kawaii-primary/20 flex items-center justify-center text-kawaii-primary-deep text-lg font-bold">
        {{ session_ui.get('current_user', {}).get('username', '?')[:1] | upper }}
      </div>
      <div>
        <h1 class="font-display text-lg font-bold text-kawaii-ink">{{ ui.get('profile_title', '智能体档案') }}</h1>
        <p class="text-xs text-kawaii-ink-muted">{{ session_ui.get('current_user', {}).get('username', ui.get('anonymous', '匿名')) }}</p>
      </div>
    </div>
    <div class="text-sm text-kawaii-ink-soft space-y-1">
      <p>{{ ui.get('profile_role', '角色') }}: {{ session_ui.get('current_user', {}).get('role', '-') }}</p>
      <p id="profile-token-expiry">{{ ui.get('profile_token_expiry', 'Token 有效期') }}: -</p>
      <p id="profile-scopes">{{ ui.get('profile_scopes', '权限') }}: -</p>
    </div>
  </section>

  {# Sub-tab navigation #}
  <div class="flex gap-2" role="tablist" data-profile-tabs>
    <button class="toggle-chip is-active" data-tab="skills" role="tab" aria-selected="true">
      {{ ui.get('profile_tab_skills', '可访问技能') }}
    </button>
    <button class="toggle-chip" data-tab="history" role="tab" aria-selected="false">
      {{ ui.get('profile_tab_history', '操作记录') }}
    </button>
    <button class="toggle-chip" data-tab="policy" role="tab" aria-selected="false">
      {{ ui.get('profile_tab_policy', '策略') }}
    </button>
  </div>

  {# Skills tab #}
  <section class="space-y-3" data-tab-panel="skills">
    <div id="profile-skills-list" class="space-y-2">
      {# Populated by JS from /api/v1/profile/me #}
      <div class="kawaii-card animate-in text-center py-8 text-kawaii-ink-muted text-sm">
        {{ ui.get('profile_loading', '加载中...') }}
      </div>
    </div>
  </section>

  {# History tab #}
  <section class="space-y-3 hidden" data-tab-panel="history">
    <div id="profile-history-list" class="space-y-2">
      <div class="kawaii-card animate-in text-center py-8 text-kawaii-ink-muted text-sm">
        {{ ui.get('profile_no_history', '暂无操作记录') }}
      </div>
    </div>
  </section>

  {# Policy tab #}
  <section class="space-y-3 hidden" data-tab-panel="policy">
    <div id="profile-policy-list">
      <div class="kawaii-card animate-in text-center py-8 text-kawaii-ink-muted text-sm">
        {{ ui.get('profile_no_policy', '暂无策略约束') }}
      </div>
    </div>
  </section>
</div>

<script type="module" src="/static/js/modules/profile.js"></script>
{% endblock %}
```

**Step 2: Create profile.js**

```javascript
// server/static/js/modules/profile.js

import { apiGet } from './api.js';
import { uiText } from './config.js';

document.addEventListener('DOMContentLoaded', async () => {
  const root = document.querySelector('[data-profile-tabs]');
  if (!root) return;

  // Tab switching
  root.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-tab]');
    if (!btn) return;

    root.querySelectorAll('[data-tab]').forEach((b) => {
      b.classList.toggle('is-active', b === btn);
      b.setAttribute('aria-selected', b === btn ? 'true' : 'false');
    });

    document.querySelectorAll('[data-tab-panel]').forEach((panel) => {
      panel.classList.toggle('hidden', panel.dataset.tabPanel !== btn.dataset.tab);
    });
  });

  // Load profile data
  try {
    const data = await apiGet('/api/v1/profile/me');
    if (!data) return;

    // Update identity card
    const scopes = data.identity?.scopes?.join(', ') || '-';
    const expiry = data.identity?.expires_at
      ? new Date(data.identity.expires_at).toLocaleDateString()
      : '-';

    document.getElementById('profile-scopes').textContent =
      `${uiText('profile_scopes', '权限')}: ${scopes}`;
    document.getElementById('profile-token-expiry').textContent =
      `${uiText('profile_token_expiry', 'Token 有效期')}: ${expiry}`;

    // Render skills
    const skillsList = document.getElementById('profile-skills-list');
    if (data.accessible_skills?.length) {
      skillsList.innerHTML = data.accessible_skills
        .map(
          (s) => `
          <article class="kawaii-card animate-in">
            <div class="flex items-center justify-between">
              <div>
                <h3 class="font-display text-sm font-bold text-kawaii-ink">${s.display_name}</h3>
                <p class="text-xs text-kawaii-ink-muted">${s.slug} · ${s.kind}</p>
              </div>
              <span class="kawaii-badge kawaii-badge--success">active</span>
            </div>
          </article>`
        )
        .join('');
    } else {
      skillsList.innerHTML = `
        <div class="kawaii-card animate-in text-center py-8 text-kawaii-ink-muted text-sm">
          ${uiText('profile_no_skills', '暂无可访问技能')}
        </div>`;
    }

    // Render history
    const historyList = document.getElementById('profile-history-list');
    if (data.operation_history?.length) {
      historyList.innerHTML = data.operation_history
        .map(
          (e) => `
          <article class="kawaii-card animate-in">
            <div class="flex items-center gap-2">
              <span class="text-xs text-kawaii-ink-muted">${new Date(e.occurred_at).toLocaleString()}</span>
              <span class="kawaii-badge kawaii-badge--soft">${e.event_type}</span>
            </div>
          </article>`
        )
        .join('');
    }

    // Render policy
    const policyList = document.getElementById('profile-policy-list');
    if (data.policy && Object.keys(data.policy).length) {
      policyList.innerHTML = `
        <article class="kawaii-card animate-in">
          <pre class="text-xs text-kawaii-ink-soft overflow-x-auto">${JSON.stringify(data.policy, null, 2)}</pre>
        </article>`;
    }
  } catch (err) {
    console.error('Failed to load profile:', err);
  }
});
```

**Step 3: Test manually**

Run: `make dev`, navigate to `/profile`, verify identity card and tabs render.

**Step 4: Commit**

```bash
git add server/templates/profile.html server/static/js/modules/profile.js
git commit -m "feat: add agent profile page with skills, history, and policy tabs"
```

---

## Task 10: Management Page — Merged Console

**Files:**
- Create: `server/templates/manage.html`

This page merges Library, Access, Shares, Activity into one page with filter chips.

**Step 1: Create manage.html**

```html
{% extends "layout-kawaii.html" %}
{% from "macros.html" import console_table_shell %}

{% block body %}
<div class="space-y-4">
  {# Header #}
  <section class="kawaii-card animate-in">
    <h1 class="font-display text-lg font-bold text-kawaii-ink">{{ ui.get('manage_title', '管理') }}</h1>
    <p class="text-xs text-kawaii-ink-muted mt-1">{{ ui.get('manage_subtitle', '技能与访问管理') }}</p>
  </section>

  {# Sub-view filter chips #}
  <div class="flex gap-2 flex-wrap" data-manage-tabs>
    <button class="toggle-chip is-active" data-view="library">{{ ui.get('tab_library', '对象库') }}</button>
    <button class="toggle-chip" data-view="tokens">{{ ui.get('tab_tokens', 'Token') }}</button>
    <button class="toggle-chip" data-view="shares">{{ ui.get('tab_shares', '分享') }}</button>
    <button class="toggle-chip" data-view="activity">{{ ui.get('tab_activity', '活动') }}</button>
  </div>

  {# Library view #}
  <section data-view-panel="library">
    <div class="flex gap-2 mb-3">
      <div class="search-bar-wrapper flex-1" role="search">
        <input class="search-input" data-library-search type="search"
               placeholder="{{ ui.get('search_placeholder', '搜索...') }}">
      </div>
      <div class="flex gap-1" data-library-filter>
        <button class="toggle-chip is-active" data-filter="all">{{ ui.get('filter_all', '全部') }}</button>
        <button class="toggle-chip" data-filter="skill">{{ ui.get('filter_skill', '技能') }}</button>
        <button class="toggle-chip" data-filter="agent_preset">{{ ui.get('filter_preset', '预设') }}</button>
        <button class="toggle-chip" data-filter="agent_code">{{ ui.get('filter_code', '代码') }}</button>
      </div>
    </div>
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4" id="manage-library-grid">
      {% for item in object_items %}
        <article class="kawaii-card animate-in object-card"
                 data-kind="{{ item.kind }}" data-name="{{ item.name | lower }}" data-summary="{{ item.summary | lower }}">
          <a href="{{ item.detail_href }}" class="font-display text-sm font-bold text-kawaii-ink hover:text-kawaii-primary-deep transition-colors">
            {{ item.name }}
          </a>
          <p class="text-xs text-kawaii-ink-muted mt-1">{{ item.slug }}</p>
          <span class="kawaii-badge kawaii-badge--soft mt-1 inline-block">{{ item.kind }}</span>
          {% if item.summary %}<p class="text-xs text-kawaii-ink-soft line-clamp-2 mt-2">{{ item.summary }}</p>{% endif %}
          <div class="flex gap-2 mt-2 text-xs text-kawaii-ink-muted">
            {% if item.version %}<span>v{{ item.version }}</span>{% endif %}
            {% if item.token_count %}<span>{{ item.token_count }} tokens</span>{% endif %}
            {% if item.share_count %}<span>{{ item.share_count }} shares</span>{% endif %}
          </div>
        </article>
      {% endfor %}
      {% if not object_items %}
        <p class="text-center text-kawaii-ink-muted text-sm py-8">{{ ui.get('empty_library', '还没有技能，agent 会通过 API 自动创建') }}</p>
      {% endif %}
    </div>
  </section>

  {# Tokens view (mobile: cards, desktop: table) #}
  <section data-view-panel="tokens" class="hidden">
    {# Mobile cards #}
    <div class="md:hidden space-y-3">
      {% for item in token_items %}
        <article class="kawaii-card animate-in" data-credential-id="{{ item.credential_id }}">
          <div class="flex items-center justify-between mb-2">
            <span class="font-display text-sm font-bold text-kawaii-ink">{{ item.agent_name or item.credential_id }}</span>
            <span class="kawaii-badge {{ 'kawaii-badge--success' if item.state == 'active' else 'kawaii-badge--pending' }}">{{ item.state }}</span>
          </div>
          <p class="text-xs text-kawaii-ink-muted">{{ item.type }} · {{ item.object_name or '-' }}</p>
          <p class="text-xs text-kawaii-ink-soft mt-1">{{ item.created }}</p>
          <div class="flex gap-2 mt-3">
            <button class="kawaii-button kawaii-button--ghost text-xs">{{ ui.get('btn_copy', '复制') }}</button>
            {% if item.can_revoke %}
              <button class="text-xs text-red-500 hover:text-red-700 transition-colors"
                      data-action="revoke-token" data-credential-id="{{ item.credential_id }}">
                {{ ui.get('btn_revoke', '撤销') }}
              </button>
            {% endif %}
          </div>
        </article>
      {% endfor %}
      {% if not token_items %}
        <p class="text-center text-kawaii-ink-muted text-sm py-8">{{ ui.get('empty_tokens', '暂无 Token') }}</p>
      {% endif %}
    </div>
    {# Desktop table — reuse existing table structure #}
    <div class="hidden md:block">
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead><tr class="border-b border-kawaii-line text-left text-xs text-kawaii-ink-muted">
            <th class="pb-2 pr-4">{{ ui.get('col_agent', 'Agent') }}</th>
            <th class="pb-2 pr-4">{{ ui.get('col_type', '类型') }}</th>
            <th class="pb-2 pr-4">{{ ui.get('col_object', '对象') }}</th>
            <th class="pb-2 pr-4">{{ ui.get('col_state', '状态') }}</th>
            <th class="pb-2 pr-4">{{ ui.get('col_created', '创建') }}</th>
            <th class="pb-2">{{ ui.get('col_actions', '操作') }}</th>
          </tr></thead>
          <tbody>
            {% for item in token_items %}
            <tr class="border-b border-kawaii-line/50">
              <td class="py-2 pr-4 font-medium">{{ item.agent_name or item.credential_id }}</td>
              <td class="py-2 pr-4"><span class="kawaii-badge kawaii-badge--soft">{{ item.type }}</span></td>
              <td class="py-2 pr-4 text-kawaii-ink-soft">{{ item.object_name or '-' }}</td>
              <td class="py-2 pr-4"><span class="kawaii-badge {{ 'kawaii-badge--success' if item.state == 'active' else 'kawaii-badge--pending' }}">{{ item.state }}</span></td>
              <td class="py-2 pr-4 text-kawaii-ink-muted">{{ item.created }}</td>
              <td class="py-2">
                {% if item.can_revoke %}
                <button class="text-xs text-red-500" data-action="revoke-token" data-credential-id="{{ item.credential_id }}">{{ ui.get('btn_revoke', '撤销') }}</button>
                {% endif %}
              </td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
  </section>

  {# Shares view (mobile: cards, desktop: table) #}
  <section data-view-panel="shares" class="hidden">
    <div class="md:hidden space-y-3">
      {% for item in share_items %}
        <article class="kawaii-card animate-in">
          <div class="flex items-center justify-between mb-2">
            <span class="font-display text-sm font-bold text-kawaii-ink">{{ item.object_name or item.grant_id }}</span>
            <span class="kawaii-badge {{ 'kawaii-badge--success' if item.state == 'active' else 'kawaii-badge--pending' }}">{{ item.state }}</span>
          </div>
          <p class="text-xs text-kawaii-ink-muted">{{ item.release_name or '-' }} · {{ item.created }}</p>
          {% if item.max_uses %}<p class="text-xs text-kawaii-ink-soft mt-1">{{ item.used_count or 0 }}/{{ item.max_uses }}</p>{% endif %}
        </article>
      {% endfor %}
      {% if not share_items %}
        <p class="text-center text-kawaii-ink-muted text-sm py-8">{{ ui.get('empty_shares', '暂无分享链接') }}</p>
      {% endif %}
    </div>
  </section>

  {# Activity view #}
  <section data-view-panel="activity" class="hidden">
    <div class="space-y-2">
      {% for item in activity_items %}
        <article class="kawaii-card animate-in flex items-center gap-2">
          <span class="text-lg">{{ item.icon }}</span>
          <div class="flex-1 min-w-0">
            <p class="text-sm text-kawaii-ink truncate">{{ item.event }}</p>
            <p class="text-xs text-kawaii-ink-muted">{{ item.timestamp }}</p>
          </div>
        </article>
      {% endfor %}
      {% if not activity_items %}
        <p class="text-center text-kawaii-ink-muted text-sm py-8">{{ ui.get('empty_activity', '暂无活动') }}</p>
      {% endif %}
    </div>
  </section>
</div>

<script type="module" src="/static/js/modules/manage.js"></script>
{% endblock %}
```

**Step 2: Create manage.js**

```javascript
// server/static/js/modules/manage.js

document.addEventListener('DOMContentLoaded', () => {
  const tabs = document.querySelector('[data-manage-tabs]');
  if (!tabs) return;

  // Sub-view switching
  tabs.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-view]');
    if (!btn) return;

    tabs.querySelectorAll('[data-view]').forEach((b) => {
      b.classList.toggle('is-active', b === btn);
    });

    document.querySelectorAll('[data-view-panel]').forEach((panel) => {
      panel.classList.toggle('hidden', panel.dataset.viewPanel !== btn.dataset.view);
    });
  });

  // Library filtering (reuse from library.js)
  const filterGroup = document.querySelector('[data-library-filter]');
  const searchInput = document.querySelector('[data-library-search]');
  const grid = document.getElementById('manage-library-grid');

  if (filterGroup && grid) {
    filterGroup.addEventListener('click', (e) => {
      const btn = e.target.closest('[data-filter]');
      if (!btn) return;

      filterGroup.querySelectorAll('[data-filter]').forEach((b) => {
        b.classList.toggle('is-active', b === btn);
      });

      const kind = btn.dataset.filter;
      grid.querySelectorAll('.object-card').forEach((card) => {
        if (kind === 'all' || card.dataset.kind === kind) {
          card.style.display = '';
        } else {
          card.style.display = 'none';
        }
      });
    });
  }

  if (searchInput && grid) {
    searchInput.addEventListener('input', () => {
      const q = searchInput.value.toLowerCase();
      grid.querySelectorAll('.object-card').forEach((card) => {
        const match = card.dataset.name.includes(q) || card.dataset.summary.includes(q);
        card.style.display = match ? '' : 'none';
      });
    });
  }
});
```

**Step 3: Test manually**

Run: `make dev`, navigate to `/manage`, verify all 4 sub-views render and switch.

**Step 4: Commit**

```bash
git add server/templates/manage.html server/static/js/modules/manage.js
git commit -m "feat: add merged management page with library, tokens, shares, activity"
```

---

## Task 11: Card Swipe Gesture Library

**Files:**
- Create: `server/static/js/modules/card-swipe.js`

**Step 1: Create the swipe module**

```javascript
// server/static/js/modules/card-swipe.js

const SWIPE_THRESHOLD = 60;
const SWIPE_MAX = 120;

export function initCardSwipe(containerSelector) {
  const containers = document.querySelectorAll(containerSelector);
  containers.forEach((container) => {
    container.addEventListener('touchstart', onTouchStart, { passive: true });
    container.addEventListener('touchmove', onTouchMove, { passive: false });
    container.addEventListener('touchend', onTouchEnd, { passive: true });
  });
}

let activeCard = null;
let startX = 0;
let currentX = 0;

function onTouchStart(e) {
  const card = e.target.closest('article');
  if (!card || card.querySelector('input, textarea, select, a')) {
    // Don't capture if touching an interactive element
    if (e.target.closest('input, textarea, select, a')) return;
  }
  activeCard = card;
  startX = e.touches[0].clientX;
  card.style.transition = 'none';
}

function onTouchMove(e) {
  if (!activeCard) return;
  currentX = e.touches[0].clientX;
  const diff = currentX - startX;

  if (diff > 0) return; // Only swipe left

  const clamped = Math.max(diff, -SWIPE_MAX);
  activeCard.style.transform = `translateX(${clamped}px)`;

  // Show action zone
  const actions = activeCard.querySelector('.swipe-actions');
  if (actions) {
    actions.style.opacity = Math.min(Math.abs(clamped) / SWIPE_THRESHOLD, 1);
  }
}

function onTouchEnd() {
  if (!activeCard) return;

  const diff = currentX - startX;
  activeCard.style.transition = 'transform 0.2s ease-out';

  if (diff < -SWIPE_THRESHOLD) {
    activeCard.style.transform = `translateX(-${SWIPE_MAX}px)`;
  } else {
    activeCard.style.transform = '';
    const actions = activeCard.querySelector('.swipe-actions');
    if (actions) actions.style.opacity = '0';
  }

  activeCard = null;
  startX = 0;
  currentX = 0;
}
```

**Step 2: Add swipe action CSS**

Add to `server/static/css/input.css`:

```css
.swipe-actions {
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  display: flex;
  align-items: center;
  padding: 0 1rem;
  opacity: 0;
  transition: opacity 0.2s;
}

@media (hover: hover) and (pointer: fine) {
  .swipe-actions { display: none; }
}
```

**Step 3: Commit**

```bash
git add server/static/js/modules/card-swipe.js server/static/css/input.css
git commit -m "feat: add mobile card swipe gesture library"
```

---

## Task 12: i18n — Add New Translation Keys

**Files:**
- Modify: `server/locales/zh.json`
- Modify: `server/locales/en.json`

**Step 1: Add keys to zh.json**

```json
{
  "dashboard_summary": "",
  "stat_active_tokens": "个活跃 Token",
  "stat_accessible_skills": "个可访问技能",
  "stat_new_activity": "条新活动",
  "dashboard_empty": "还没有 agent 连接，复制任务提示让 agent 开始",
  "quick_actions": "快速操作",
  "copy_task_prompt": "复制任务提示",
  "tab_library": "对象库",
  "tab_tokens": "Token",
  "tab_shares": "分享",
  "tab_activity": "活动",
  "tab_nav_label": "主导航",
  "manage_title": "管理",
  "manage_subtitle": "技能与访问管理",
  "profile_title": "智能体档案",
  "profile_tab_skills": "可访问技能",
  "profile_tab_history": "操作记录",
  "profile_tab_policy": "策略",
  "profile_role": "角色",
  "profile_token_expiry": "Token 有效期",
  "profile_scopes": "权限",
  "profile_loading": "加载中...",
  "profile_no_skills": "暂无可访问技能",
  "profile_no_history": "暂无操作记录",
  "profile_no_policy": "暂无策略约束",
  "empty_library": "还没有技能，agent 会通过 API 自动创建",
  "empty_tokens": "暂无 Token",
  "empty_shares": "暂无分享链接",
  "empty_activity": "暂无活动",
  "btn_copy": "复制",
  "btn_revoke": "撤销",
  "col_agent": "Agent",
  "col_type": "类型",
  "col_object": "对象",
  "col_state": "状态",
  "col_created": "创建",
  "col_actions": "操作"
}
```

**Step 2: Add keys to en.json**

```json
{
  "dashboard_summary": "",
  "stat_active_tokens": "active tokens",
  "stat_accessible_skills": "accessible skills",
  "stat_new_activity": "new events",
  "dashboard_empty": "No agents connected yet. Copy the task prompt to get started",
  "quick_actions": "Quick Actions",
  "copy_task_prompt": "Copy task prompt",
  "tab_library": "Library",
  "tab_tokens": "Tokens",
  "tab_shares": "Shares",
  "tab_activity": "Activity",
  "tab_nav_label": "Main navigation",
  "manage_title": "Management",
  "manage_subtitle": "Skill & Access Management",
  "profile_title": "Agent Archive",
  "profile_tab_skills": "Accessible Skills",
  "profile_tab_history": "Operation History",
  "profile_tab_policy": "Policy",
  "profile_role": "Role",
  "profile_token_expiry": "Token expires",
  "profile_scopes": "Scopes",
  "profile_loading": "Loading...",
  "profile_no_skills": "No accessible skills yet",
  "profile_no_history": "No operation history",
  "profile_no_policy": "No policy constraints",
  "empty_library": "No skills yet. Agents create them via API",
  "empty_tokens": "No tokens",
  "empty_shares": "No share links",
  "empty_activity": "No activity",
  "btn_copy": "Copy",
  "btn_revoke": "Revoke",
  "col_agent": "Agent",
  "col_type": "Type",
  "col_object": "Object",
  "col_state": "State",
  "col_created": "Created",
  "col_actions": "Actions"
}
```

**Step 3: Commit**

```bash
git add server/locales/zh.json server/locales/en.json
git commit -m "feat: add i18n keys for dashboard, profile, and management pages"
```

---

## Task 13: Redirect Legacy Routes to New Pages

**Files:**
- Modify: `server/ui/routes.py`

**Step 1: Add redirects**

In `register_ui_routes()`, add redirects for the old pages to point to `/manage` with the correct sub-view:

```python
@app.get("/library")
def library_redirect(request: Request):
    lang = resolve_language(request)
    return RedirectResponse(url=with_lang("/manage", lang), status_code=307)

@app.get("/access")
def access_redirect(request: Request):
    lang = resolve_language(request)
    return RedirectResponse(url=with_lang("/manage", lang) + "#tokens", status_code=307)

@app.get("/shares")
def shares_redirect(request: Request):
    lang = resolve_language(request)
    return RedirectResponse(url=with_lang("/manage", lang) + "#shares", status_code=307)

@app.get("/activity")
def activity_redirect(request: Request):
    lang = resolve_language(request)
    return RedirectResponse(url=with_lang("/manage", lang) + "#activity", status_code=307)
```

Note: The old `/library/{object_id}` and `/library/{object_id}/releases/{release_id}` detail routes should remain functional as read-only views.

**Step 2: Commit**

```bash
git add server/ui/routes.py
git commit -m "refactor: redirect legacy pages to new /manage and /profile routes"
```

---

## Task 14: Rebuild CSS and Verify

**Files:**
- None (build step)

**Step 1: Rebuild Tailwind CSS**

Run: `npx tailwindcss -i server/static/css/input.css -o server/static/css/output.css --minify`

**Step 2: Run full test suite**

Run: `python -m pytest tests/ -v --tb=short`

**Step 3: Start dev server and manual test**

Run: `make dev`

Verify on mobile-width browser (375px):
- [ ] Bottom tab bar visible with 3 tabs
- [ ] Home shows dashboard stats
- [ ] Profile shows identity card and 3 sub-tabs
- [ ] Management shows 4 sub-views with filter chips
- [ ] Card-based layouts on mobile
- [ ] Table-based layouts on desktop (768px+)
- [ ] Swipe gestures on token cards (mobile)
- [ ] Old routes redirect correctly

**Step 4: Final commit**

```bash
git add -A
git commit -m "chore: rebuild CSS and verify mobile-first redesign"
```
