# API Permissions Matrix

Mapping of every mounted route in `api/src/routers/` to its authentication and
authorization requirements. **Update this file whenever you add, remove, or
change the auth/permission checks on a route.**

Last reviewed against routers: 2026-04-30

## Permission Model

Auth and authorization are layered:

| Layer | Source | Description |
| --- | --- | --- |
| **Public** | (no dependency) | No authentication required. |
| **Authenticated** | `CurrentUserDependency` (`src/services/auth.py`) | Requires a valid `access_token` cookie; resolves to a `UserModel`. |
| **Map role** | `PermissionService.check_for_map_access` (`src/services/permissions.py`) — backed by `UserMapRoleModel` | Roles: `OWNER`, `MEMBER`. A route lists which roles satisfy it. |
| **Upload role** | `PermissionService.check_for_upload_access` — backed by `UserUploadRoleModel` | Currently the only role is `OWNER`. |

> **Map roles policy (current).** `OWNER` and `MEMBER` are functionally
> equivalent on every map-scoped route. `OWNER` exists only as a label that
> identifies the user who created the map. Any route that authorizes against
> map roles accepts both. Treat the two as interchangeable when adding new
> routes.

Conventions used in the tables below:

- **Auth** — `Public`, `Auth` (any logged-in user), or a specific role.
- **Roles** — Map roles accepted by the route, or `—` if not applicable.
- **Notes** — Anything else relevant: side-effects, role grants, gaps.

Routes are grouped by router file and listed in the order they appear in source.

---

## Common — `src/routers/common.py`

| Method | Path | Auth | Roles | Notes |
| --- | --- | --- | --- | --- |
| GET | `/heartbeat` | Public | — | Liveness check. |
| GET | `/db-heartbeat` | Public | — | DB connectivity check. |
| GET | `/versions` | Public | — | Returns deployed API git sha. |

## Auth — `src/routers/auth.py`

| Method | Path | Auth | Roles | Notes |
| --- | --- | --- | --- | --- |
| POST | `/auth/register` | Public | — | Creates user + sets access-token cookie. |
| POST | `/auth/login` | Public | — | Sets access-token cookie; refresh-token cookie if `remember_me`. |
| POST | `/auth/refresh-token` | Public | — | Requires `refresh_token` cookie; rotates `access_token`. |
| POST | `/auth/logout` | Public | — | Clears auth cookies. |

## Me / Accounts — `src/routers/accounts.py`

| Method | Path | Auth | Roles | Notes |
| --- | --- | --- | --- | --- |
| GET | `/me` | Auth | — | Returns the current user. |
| PATCH | `/me` | Auth | — | Updates the current user's name. |
| POST | `/me/request-password-reset` | Auth | — | Stub — currently only logs; no email yet. |

## Docs — `src/routers/docs.py`

Hidden from OpenAPI schema (`include_in_schema=False`). All public.

| Method | Path | Auth | Roles | Notes |
| --- | --- | --- | --- | --- |
| GET | `/try` | Public | — | Scalar API reference (full). |
| GET | `/public-openapi.json` | Public | — | Filtered OpenAPI spec (`public: true` operations only). |
| GET | `/developers` | Public | — | Public-facing Scalar API reference. |

## Maps — `src/routers/maps.py`

| Method | Path | Auth | Roles | Notes |
| --- | --- | --- | --- | --- |
| POST | `/maps` | Auth + Upload `OWNER` | — | Creates map from a parsed upload. Auto-grants Map `OWNER` to caller. |
| GET | `/maps` | Auth | — | Lists only maps where the user has any role. |
| GET | `/maps/{map_id}` | Map | `OWNER`, `MEMBER` | Returns 404 (not 403) if no access. |
| PATCH | `/maps/{map_id}` | Map | `OWNER`, `MEMBER` | Rename a map. Returns 404 on no access. |

## Members — `src/routers/members.py`

| Method | Path | Auth | Roles | Notes |
| --- | --- | --- | --- | --- |
| GET | `/maps/{map_id}/members` | Map | `OWNER`, `MEMBER` | Lists all members of the map. |
| DELETE | `/maps/{map_id}/members/{user_id}` | Map | `OWNER`, `MEMBER` | Cannot remove self. Any member can remove any other (incl. the original owner). |

## Invites (map-scoped) — `src/routers/invites.py`

| Method | Path | Auth | Roles | Notes |
| --- | --- | --- | --- | --- |
| GET | `/maps/{map_id}/invites` | Map | `OWNER`, `MEMBER` | Lists pending invites for the map. |
| POST | `/maps/{map_id}/invites` | Map | `OWNER`, `MEMBER` | Creates a pending invite by email. |
| DELETE | `/maps/{map_id}/invites/{invite_id}` | Map | `OWNER`, `MEMBER` | Revokes a pending invite. |

## Invites (me-scoped) — `src/routers/invites.py`

These routes don't use map roles — authorization is the email match between the
current user and the invite row.

| Method | Path | Auth | Roles | Notes |
| --- | --- | --- | --- | --- |
| GET | `/me/invites` | Auth | — | Pending invites whose `invited_email == current_user.email`. |
| POST | `/me/invites/{invite_id}/accept` | Auth (email match) | — | Grants Map `MEMBER` to caller; marks invite `accepted`. |
| POST | `/me/invites/{invite_id}/decline` | Auth (email match) | — | Marks invite `declined`. |

## Graph — Layers — `src/routers/graph.py`

| Method | Path | Auth | Roles | Notes |
| --- | --- | --- | --- | --- |
| POST | `/layers` | Map | `OWNER`, `MEMBER` | Create a new layer. |
| GET | `/layers?map_id=` | Map | `OWNER`, `MEMBER` | List layers for a map. |
| GET | `/layers/{layer_id}` | Map | `OWNER`, `MEMBER` | Single-layer fetch. |

## Graph — Nodes — `src/routers/graph.py`

| Method | Path | Auth | Roles | Notes |
| --- | --- | --- | --- | --- |
| POST | `/nodes/query` | Map | `OWNER`, `MEMBER` | Filtered list of nodes (replaces GET /nodes). |
| GET | `/nodes/{node_id}` | Map | `OWNER`, `MEMBER` | Includes ancestor chain. |
| PUT | `/nodes/{node_id}` | Map | `OWNER`, `MEMBER` | Update node name/color/parent. |
| DELETE | `/nodes/{node_id}` | Map | `OWNER`, `MEMBER` | order ≥ 1 only. |
| PUT | `/nodes/bulk` | Map | `OWNER`, `MEMBER` | Checked per affected map. |
| PUT | `/nodes/bulk/reparent` | Map | `OWNER`, `MEMBER` | Checked per affected map. |
| POST | `/nodes/merge` | Map | `OWNER`, `MEMBER` | Checked per affected map. |
| DELETE | `/nodes/bulk` | Map | `OWNER`, `MEMBER` | Checked per affected map. |

## Graph — Zip Assignments — `src/routers/graph.py`

All checked via `_check_layer_access`, which accepts any map role.

| Method | Path | Auth | Roles | Notes |
| --- | --- | --- | --- | --- |
| GET | `/zip-assignments?layer_id=` | Map | `OWNER`, `MEMBER` | Paginated list. |
| POST | `/zip-assignments/query` | Map | `OWNER`, `MEMBER` | LEFT JOIN against `geography_zip_codes`. |
| PUT | `/zip-assignments/{layer_id}/bulk` | Map | `OWNER`, `MEMBER` | Primary post-lasso operation. |
| PUT | `/zip-assignments/{layer_id}/{zip_code}` | Map | `OWNER`, `MEMBER` | Single assign / unassign. |
| DELETE | `/zip-assignments/{layer_id}/{zip_code}` | Map | `OWNER`, `MEMBER` | Reset to default. |
| GET | `/zip-assignments/{layer_id}/{zip_code}` | Map | `OWNER`, `MEMBER` | 404 if zip implicitly unassigned. |
| GET | `/zip-assignments/{layer_id}/{zip_code}/geography` | Map | `OWNER`, `MEMBER` | Falls back to geography defaults. |

## Graph — Search — `src/routers/graph.py`

| Method | Path | Auth | Roles | Notes |
| --- | --- | --- | --- | --- |
| GET | `/search?map_id=&q=` | Map | `OWNER`, `MEMBER` | Searches node names + zip codes within the map. |

## MVT (Vector Tiles) — `src/routers/mvt.py`

| Method | Path | Auth | Roles | Notes |
| --- | --- | --- | --- | --- |
| GET | `/tiles/{layer_id}/{z}/{x}/{y}.pbf` | Map | `OWNER`, `MEMBER` | Auth precedes cache lookup; ~1 extra indexed PK lookup per tile. `Cache-Control` is `private`. |
| GET | `/tiles/warm?map_id=` | Map | `OWNER`, `MEMBER` | Enqueues a Celery cache-warming task. |

## Spatial — `src/routers/spatial.py`

| Method | Path | Auth | Roles | Notes |
| --- | --- | --- | --- | --- |
| POST | `/spatial/select` | Map | `OWNER`, `MEMBER` | Resolves `map_id` from `selection.layer_id` to authorize. |

## Uploads — `src/routers/uploads.py`

| Method | Path | Auth | Roles | Notes |
| --- | --- | --- | --- | --- |
| POST | `/maps/uploads` | Auth | — | Auto-grants Upload `OWNER` to caller on success. |
| GET | `/maps/uploads/{document_id}` | Upload | `OWNER` | Used to poll parse status. |

## Exports — `src/routers/exports.py`

| Method | Path | Auth | Roles | Notes |
| --- | --- | --- | --- | --- |
| GET | `/maps/{map_id}/export/ztt` | Map | `OWNER`, `MEMBER` | Streams an .xlsx zip-to-territory export. |

## PPT Exports — `src/routers/ppt_exports.py`

All routes accept any map role.

| Method | Path | Auth | Roles | Notes |
| --- | --- | --- | --- | --- |
| POST | `/maps/{map_id}/exports/ppt` | Map | `OWNER`, `MEMBER` | Creates export + pre-computes slide rows. |
| GET | `/maps/{map_id}/exports/ppt/{export_id}/next` | Map | `OWNER`, `MEMBER` | Returns next slide capture instruction. |
| POST | `/maps/{map_id}/exports/ppt/{export_id}/slides/{slide_id}` | Map | `OWNER`, `MEMBER` | Uploads slide screenshot to S3. |
| POST | `/maps/{map_id}/exports/ppt/{export_id}/generate` | Map | `OWNER`, `MEMBER` | Enqueues async .pptx assembly. |
| GET | `/maps/{map_id}/exports/ppt/{export_id}` | Map | `OWNER`, `MEMBER` | Status + presigned download URL. |
| DELETE | `/maps/{map_id}/exports/ppt/{export_id}` | Map | `OWNER`, `MEMBER` | Cancels and cleans up. |

## Diagnostics — `src/routers/diagnostics.py` (NOT MOUNTED)

This router is **not** registered in `src/__init__.py`, so its routes are
unreachable in the running app. Listed here for completeness; keep this
section in sync if the router is mounted later.

| Method | Path | Auth | Roles | Notes |
| --- | --- | --- | --- | --- |
| GET | `/diagnostics/geometry-stats` | (none) | — | Currently unreachable. |
| GET | `/diagnostics/problematic-nodes` | (none) | — | Currently unreachable. |
| GET | `/diagnostics/node-stats/{node_id}` | (none) | — | Currently unreachable. |

---

## Known Gaps & Inconsistencies

None currently flagged. Re-add entries here when audit reveals new gaps, then
remove once fixed.

### Open questions worth a follow-up

- **Member management is symmetric.** Because every map-scoped route accepts
  both `OWNER` and `MEMBER`, any member can remove any other member (including
  the original owner) and revoke/issue invites. If you want member management
  to be tighter than data operations, restore `OWNER`-only on
  `DELETE /maps/{map_id}/members/{user_id}` and the three
  `/maps/{map_id}/invites` routes.
- **MVT auth cost.** Every tile request now performs a layer PK lookup +
  permission lookup before checking the tile cache. Cheap today; revisit if
  tile QPS climbs (e.g. add a small in-process layer→map_id cache, or move
  auth to an API gateway).

---

## How to update this file

When adding or modifying a route:

1. Find the section for the router file (or add a new one).
2. Add/update the row with method, path, auth, and roles.
3. If the route bypasses the standard pattern (no `CurrentUserDependency`,
   custom check, side-effects on roles, etc.), call it out in **Notes**.
4. If you fix one of the gaps above, remove it from the **Known Gaps** list.
5. Update the "Last reviewed against routers" date at the top.
