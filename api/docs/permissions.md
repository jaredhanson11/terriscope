# API Permissions Matrix

Mapping of every mounted route in `api/src/routers/` to its authentication and
authorization requirements. **Update this file whenever you add, remove, or
change the auth/permission checks on a route.**

Last reviewed against routers: 2026-04-30

## Permission Model

Auth and authorization are layered:

| Layer             | Source                                                                                                  | Description                                                        |
| ----------------- | ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| **Public**        | (no dependency)                                                                                         | No authentication required.                                        |
| **Authenticated** | `CurrentUserDependency` (`src/services/auth.py`)                                                        | Requires a valid `access_token` cookie; resolves to a `UserModel`. |
| **Map role**      | `PermissionService.check_for_map_access` (`src/services/permissions.py`) — backed by `UserMapRoleModel` | Roles: `OWNER`, `MEMBER`. A route lists which roles satisfy it.    |
| **Upload role**   | `PermissionService.check_for_upload_access` — backed by `UserUploadRoleModel`                           | Currently the only role is `OWNER`.                                |

Conventions used in the tables below:

- **Auth** — `Public`, `Auth` (any logged-in user), or a specific role.
- **Roles** — Map roles accepted by the route, or `—` if not applicable.
- **Notes** — Anything else relevant: side-effects, role grants, gaps.

Routes are grouped by router file and listed in the order they appear in source.

---

## Common — `src/routers/common.py`

| Method | Path            | Auth   | Roles | Notes                         |
| ------ | --------------- | ------ | ----- | ----------------------------- |
| GET    | `/heartbeat`    | Public | —     | Liveness check.               |
| GET    | `/db-heartbeat` | Public | —     | DB connectivity check.        |
| GET    | `/versions`     | Public | —     | Returns deployed API git sha. |

## Auth — `src/routers/auth.py`

| Method | Path                  | Auth   | Roles | Notes                                                            |
| ------ | --------------------- | ------ | ----- | ---------------------------------------------------------------- |
| POST   | `/auth/register`      | Public | —     | Creates user + sets access-token cookie.                         |
| POST   | `/auth/login`         | Public | —     | Sets access-token cookie; refresh-token cookie if `remember_me`. |
| POST   | `/auth/refresh-token` | Public | —     | Requires `refresh_token` cookie; rotates `access_token`.         |
| POST   | `/auth/logout`        | Public | —     | Clears auth cookies.                                             |

## Me / Accounts — `src/routers/accounts.py`

| Method | Path                         | Auth | Roles | Notes                                     |
| ------ | ---------------------------- | ---- | ----- | ----------------------------------------- |
| GET    | `/me`                        | Auth | —     | Returns the current user.                 |
| PATCH  | `/me`                        | Auth | —     | Updates the current user's name.          |
| POST   | `/me/request-password-reset` | Auth | —     | Stub — currently only logs; no email yet. |

## Docs — `src/routers/docs.py`

Hidden from OpenAPI schema (`include_in_schema=False`). All public.

| Method | Path                   | Auth   | Roles | Notes                                                   |
| ------ | ---------------------- | ------ | ----- | ------------------------------------------------------- |
| GET    | `/try`                 | Public | —     | Scalar API reference (full).                            |
| GET    | `/public-openapi.json` | Public | —     | Filtered OpenAPI spec (`public: true` operations only). |
| GET    | `/developers`          | Public | —     | Public-facing Scalar API reference.                     |

## Maps — `src/routers/maps.py`

| Method | Path             | Auth                  | Roles             | Notes                                                                |
| ------ | ---------------- | --------------------- | ----------------- | -------------------------------------------------------------------- |
| POST   | `/maps`          | Auth + Upload `OWNER` | —                 | Creates map from a parsed upload. Auto-grants Map `OWNER` to caller. |
| GET    | `/maps`          | Auth                  | —                 | Lists only maps where the user has any role.                         |
| GET    | `/maps/{map_id}` | Map                   | `OWNER`, `MEMBER` | Returns 404 (not 403) if no access.                                  |
| PATCH  | `/maps/{map_id}` | Map                   | `OWNER`           | Rename a map. Returns 404 on no access.                              |

## Members — `src/routers/members.py`

| Method | Path                               | Auth | Roles             | Notes                         |
| ------ | ---------------------------------- | ---- | ----------------- | ----------------------------- |
| GET    | `/maps/{map_id}/members`           | Map  | `OWNER`, `MEMBER` | Lists all members of the map. |
| DELETE | `/maps/{map_id}/members/{user_id}` | Map  | `OWNER`           | Cannot remove self.           |

## Invites (map-scoped) — `src/routers/invites.py`

| Method | Path                                 | Auth | Roles   | Notes                              |
| ------ | ------------------------------------ | ---- | ------- | ---------------------------------- |
| GET    | `/maps/{map_id}/invites`             | Map  | `OWNER` | Lists pending invites for the map. |
| POST   | `/maps/{map_id}/invites`             | Map  | `OWNER` | Creates a pending invite by email. |
| DELETE | `/maps/{map_id}/invites/{invite_id}` | Map  | `OWNER` | Revokes a pending invite.          |

## Invites (me-scoped) — `src/routers/invites.py`

These routes don't use map roles — authorization is the email match between the
current user and the invite row.

| Method | Path                              | Auth               | Roles | Notes                                                        |
| ------ | --------------------------------- | ------------------ | ----- | ------------------------------------------------------------ |
| GET    | `/me/invites`                     | Auth               | —     | Pending invites whose `invited_email == current_user.email`. |
| POST   | `/me/invites/{invite_id}/accept`  | Auth (email match) | —     | Grants Map `MEMBER` to caller; marks invite `accepted`.      |
| POST   | `/me/invites/{invite_id}/decline` | Auth (email match) | —     | Marks invite `declined`.                                     |

## Graph — Layers — `src/routers/graph.py`

| Method | Path                 | Auth | Roles             | Notes                        |
| ------ | -------------------- | ---- | ----------------- | ---------------------------- |
| POST   | `/layers`            | Map  | `OWNER`           | Create a new layer.          |
| GET    | `/layers?map_id=`    | Map  | `OWNER`, `MEMBER` | List layers for a map.       |
| GET    | `/layers/{layer_id}` | Map  | `OWNER`, `MEMBER` | **BROKEN** — see Known Gaps. |

## Graph — Nodes — `src/routers/graph.py`

| Method | Path                   | Auth | Roles             | Notes                                                         |
| ------ | ---------------------- | ---- | ----------------- | ------------------------------------------------------------- |
| POST   | `/nodes`               | Map  | `OWNER`, `MEMBER` | Create a new node in an order ≥ 1 layer.                      |
| POST   | `/nodes/query`         | Map  | `OWNER`           | Filtered list of nodes (replaces GET /nodes).                 |
| GET    | `/nodes/{node_id}`     | Map  | `OWNER`, `MEMBER` | Includes ancestor chain.                                      |
| PUT    | `/nodes/{node_id}`     | Map  | `OWNER`, `MEMBER` | **Note:** weaker than other write endpoints — see Known Gaps. |
| DELETE | `/nodes/{node_id}`     | Map  | `OWNER`           | order ≥ 1 only.                                               |
| PUT    | `/nodes/bulk`          | Auth | —                 | **GAP** — does not check map access. See Known Gaps.          |
| PUT    | `/nodes/bulk/reparent` | Map  | `OWNER`           | Checked per affected map.                                     |
| POST   | `/nodes/merge`         | Map  | `OWNER`           | Checked per affected map.                                     |
| DELETE | `/nodes/bulk`          | Map  | `OWNER`           | Checked per affected map.                                     |

## Graph — Zip Assignments — `src/routers/graph.py`

All checked via `_check_layer_access`, which requires Map `OWNER` (note:
`MEMBER` cannot read zip assignments).

| Method | Path                                               | Auth | Roles   | Notes                                    |
| ------ | -------------------------------------------------- | ---- | ------- | ---------------------------------------- |
| GET    | `/zip-assignments?layer_id=`                       | Map  | `OWNER` | Paginated list.                          |
| POST   | `/zip-assignments/query`                           | Map  | `OWNER` | LEFT JOIN against `geography_zip_codes`. |
| PUT    | `/zip-assignments/{layer_id}/bulk`                 | Map  | `OWNER` | Primary post-lasso operation.            |
| PUT    | `/zip-assignments/{layer_id}/{zip_code}`           | Map  | `OWNER` | Single assign / unassign.                |
| DELETE | `/zip-assignments/{layer_id}/{zip_code}`           | Map  | `OWNER` | Reset to default.                        |
| GET    | `/zip-assignments/{layer_id}/{zip_code}`           | Map  | `OWNER` | 404 if zip implicitly unassigned.        |
| GET    | `/zip-assignments/{layer_id}/{zip_code}/geography` | Map  | `OWNER` | Falls back to geography defaults.        |

## Graph — Search — `src/routers/graph.py`

| Method | Path                 | Auth | Roles   | Notes                                                                     |
| ------ | -------------------- | ---- | ------- | ------------------------------------------------------------------------- |
| GET    | `/search?map_id=&q=` | Map  | `OWNER` | **Note:** `MEMBER` cannot search; inconsistent with other read endpoints. |

## MVT (Vector Tiles) — `src/routers/mvt.py`

| Method | Path                                | Auth   | Roles | Notes                                                |
| ------ | ----------------------------------- | ------ | ----- | ---------------------------------------------------- |
| GET    | `/tiles/{layer_id}/{z}/{x}/{y}.pbf` | Public | —     | **GAP** — no auth. See Known Gaps.                   |
| GET    | `/tiles/warm?map_id=`               | Public | —     | **GAP** — no auth; enqueues a Celery task on demand. |

## Spatial — `src/routers/spatial.py`

| Method | Path              | Auth   | Roles | Notes                                                   |
| ------ | ----------------- | ------ | ----- | ------------------------------------------------------- |
| POST   | `/spatial/select` | Public | —     | **GAP** — no auth, no map access check. See Known Gaps. |

## Uploads — `src/routers/uploads.py`

| Method | Path                          | Auth   | Roles   | Notes                                            |
| ------ | ----------------------------- | ------ | ------- | ------------------------------------------------ |
| POST   | `/maps/uploads`               | Auth   | —       | Auto-grants Upload `OWNER` to caller on success. |
| GET    | `/maps/uploads/{document_id}` | Upload | `OWNER` | Used to poll parse status.                       |

## Exports — `src/routers/exports.py`

| Method | Path                        | Auth | Roles   | Notes                                     |
| ------ | --------------------------- | ---- | ------- | ----------------------------------------- |
| GET    | `/maps/{map_id}/export/ztt` | Map  | `OWNER` | Streams an .xlsx zip-to-territory export. |

## PPT Exports — `src/routers/ppt_exports.py`

All routes require Map `OWNER`.

| Method | Path                                                       | Auth | Roles   | Notes                                     |
| ------ | ---------------------------------------------------------- | ---- | ------- | ----------------------------------------- |
| POST   | `/maps/{map_id}/exports/ppt`                               | Map  | `OWNER` | Creates export + pre-computes slide rows. |
| GET    | `/maps/{map_id}/exports/ppt/{export_id}/next`              | Map  | `OWNER` | Returns next slide capture instruction.   |
| POST   | `/maps/{map_id}/exports/ppt/{export_id}/slides/{slide_id}` | Map  | `OWNER` | Uploads slide screenshot to S3.           |
| POST   | `/maps/{map_id}/exports/ppt/{export_id}/generate`          | Map  | `OWNER` | Enqueues async .pptx assembly.            |
| GET    | `/maps/{map_id}/exports/ppt/{export_id}`                   | Map  | `OWNER` | Status + presigned download URL.          |
| DELETE | `/maps/{map_id}/exports/ppt/{export_id}`                   | Map  | `OWNER` | Cancels and cleans up.                    |

## Diagnostics — `src/routers/diagnostics.py` (NOT MOUNTED)

This router is **not** registered in `src/__init__.py`, so its routes are
unreachable in the running app. Listed here for completeness; keep this
section in sync if the router is mounted later.

| Method | Path                                | Auth   | Roles | Notes                  |
| ------ | ----------------------------------- | ------ | ----- | ---------------------- |
| GET    | `/diagnostics/geometry-stats`       | (none) | —     | Currently unreachable. |
| GET    | `/diagnostics/problematic-nodes`    | (none) | —     | Currently unreachable. |
| GET    | `/diagnostics/node-stats/{node_id}` | (none) | —     | Currently unreachable. |

---

## Known Gaps & Inconsistencies

Flagged when this matrix was first compiled (2026-04-30). Re-evaluate when
fixed and remove from this list.

1. **`PUT /nodes/bulk` has no map-access check.** It uses `CurrentUserDependency`
   for auth but never calls `permission_service.check_for_map_access`. Any
   authenticated user can rename/recolor any nodes by ID. Other bulk node
   endpoints (`/nodes/bulk/reparent`, `/nodes/merge`, `DELETE /nodes/bulk`)
   correctly check OWNER per affected map — `PUT /nodes/bulk` should match.

2. **`GET /layers/{layer_id}` is broken.** The permission check is inverted
   (`if layer and check_for_map_access(...): raise HTTPException(403)`) and the
   handler body references `graph_service` and `node_data`, which are not
   parameters of the function. The route is non-functional — calls will raise
   `NameError` or 403 depending on access. Fix: invert the check and return a
   `Layer` response.

3. **`PUT /nodes/{node_id}` accepts `MEMBER`.** Single-node updates allow
   `MEMBER` access, while every other write path (delete, bulk, reparent,
   merge, zip operations) is `OWNER`-only. Either tighten this to `OWNER` or
   widen the others to `MEMBER`, but pick one.

4. **MVT tile endpoints are public.** `GET /tiles/{layer_id}/{z}/{x}/{y}.pbf`
   and `GET /tiles/warm` have no auth at all. Anyone who can guess a
   `layer_id` can fetch its tiles, including data fields baked into tile
   properties. Consider whether tiles need to honor map roles — a public read
   pattern can coexist with a private layer flag, but today both are public.

5. **`POST /spatial/select` is public.** No auth, no map/layer access check.
   Anyone can run lasso intersection queries against any layer's geometry.

6. **`GET /search` requires `OWNER`.** Read-only search excludes `MEMBER`,
   which is inconsistent with `GET /maps/{map_id}` and `GET /layers`
   (both allow `MEMBER`). Likely should be `OWNER, MEMBER`.

7. **Zip-assignment reads require `OWNER`.** `GET /zip-assignments`,
   `POST /zip-assignments/query`, and the per-zip GETs all go through
   `_check_layer_access` which is `OWNER`-only. If `MEMBER` is meant to be a
   read-only role, these reads should accept `MEMBER` too.

---

## How to update this file

When adding or modifying a route:

1. Find the section for the router file (or add a new one).
2. Add/update the row with method, path, auth, and roles.
3. If the route bypasses the standard pattern (no `CurrentUserDependency`,
   custom check, side-effects on roles, etc.), call it out in **Notes**.
4. If you fix one of the gaps above, remove it from the **Known Gaps** list.
5. Update the "Last reviewed against routers" date at the top.
