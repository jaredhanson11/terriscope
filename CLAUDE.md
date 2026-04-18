# Terriscope — Claude Context

## Project Overview
Terriscope is a geospatial territory management web app. Users import hierarchical geographic data (e.g., zip codes rolled up into regions), view it on an interactive map, and manage territories through selection tools (lasso polygon), layer toggling, node editing, and data visualization.

## Monorepo Structure
```
terriscope-app/
├── api/          # Python FastAPI backend (PostGIS, JWT auth, MVT tiles)
├── app/          # React 19 + TypeScript frontend (MapLibre, Tailwind CSS)
├── design/       # Design assets
└── scripts/      # Utility scripts
```

---

## API (`api/`)

### Stack
- **Framework:** FastAPI (Python 3.12+)
- **ORM:** SQLAlchemy 2.0 (async) + GeoAlchemy2 + PostGIS
- **Validation:** Pydantic v2
- **Auth:** JWT (HS256) via HTTP-only cookies (access + refresh tokens)
- **Migrations:** Alembic
- **Package manager:** Poetry (`pyproject.toml`, `poetry.lock`)
- **Type checking:** Pyright (strict) | **Linting:** Ruff

### Source Layout (`api/src/`)
```
app/          # FastAPI init, config, database, CORS, logging, middleware
models/       # SQLAlchemy ORM models
routers/      # FastAPI route handlers
schemas/      # Pydantic response schemas + DTOs
services/     # Business logic (auth, graph, permissions, computation)
exceptions/   # Custom exception types
migrations/   # Alembic env + version files
```

### Key Models
| Model | Table | Description |
|---|---|---|
| UserModel | `users` | email (CITEXT, unique), bcrypt password |
| MapModel | `maps` | name |
| LayerModel | `layers` | map_id FK, name, order |
| NodeModel | `nodes` | layer_id FK, name, color, parent_node_id (self-ref), geometry (PostGIS SRID 4326), JSONB data |
| UserMapRoleModel | `user_map_roles` | user_id, map_id, role (OWNER/MEMBER) |
| ZipCodeGeography | `geography_zip_codes` | zip_code PK, geometry |

### Key Endpoints
| Method | Path | Purpose |
|---|---|---|
| POST | `/auth/register` | Register user |
| POST | `/auth/login` | Login, set JWT cookies |
| POST | `/auth/refresh-token` | Refresh access token |
| POST | `/auth/logout` | Clear cookies |
| GET | `/me` | Current user |
| GET | `/maps` | List user maps |
| POST | `/maps` | Import map with hierarchical data |
| GET | `/layers` | List layers for a map |
| POST | `/layers` | Create layer |
| GET/PUT | `/nodes`, `/nodes/{id}` | Node CRUD |
| PUT | `/nodes/bulk` | Bulk update nodes |
| DELETE | `/nodes/{id}` | Delete node |
| GET | `/tiles/{layer_id}/{z}/{x}/{y}.pbf` | Mapbox Vector Tiles |
| POST | `/spatial/select` | Lasso polygon selection |
| GET | `/heartbeat`, `/db-heartbeat` | Health checks |

### Docker
- `docker-compose.yml`: `api` (port 8000) + `postgres` (PostGIS, port 5432) + `migrations` service
- API base URL: `http://localhost:8000/v1.0`
- DB creds: user=terriscope, password=terriscope, db=app
- CORS allows: `http://localhost:5173`

### Running Locally
```bash
cd api
docker compose up          # start postgres + api + run migrations
# or for debug:
docker compose -f docker-compose.debug.yml up
```

---

## App (`app/`)

### Stack
- **Framework:** React 19 + TypeScript 5.9 (strict)
- **Build:** Vite 7
- **Routing:** React Router DOM v7
- **Server state:** TanStack React Query v5
- **API client:** openapi-fetch (typed from OpenAPI spec)
- **Forms:** Formik
- **UI components:** shadcn/ui (Base UI + Radix UI)
- **Styling:** Tailwind CSS v4 (OKLch color vars, dark mode via next-themes)
- **Map:** MapLibre GL v5 + react-map-gl v8
- **Geospatial:** Turf.js (lasso simplification)
- **Charts:** Recharts
- **File import:** XLSX (Excel parsing)
- **Icons:** Tabler Icons React
- **Package manager:** pnpm

### Source Layout (`app/src/`)
```
app/                  # App core: routes, config, providers, auth context
  providers/
    me-provider/      # AuthProvider — loads user + maps, exposes useMe()/useMaps()
features/
  auth/               # Login + register pages
  home/               # Main map workspace page
    components/map/   # MapLibre map, lasso, layer rendering (utils.ts, config.ts)
  initialize/         # 4-step wizard: import Excel → define layers → map fields → review
components/
  layout.tsx          # PageLayout compound component (.SideNav, .TopNav, .Body)
  ui/                 # 50+ shadcn UI primitives
queries/
  queries.ts          # React Query queryOptions (me, listMaps, listLayers)
  mutations.ts        # Mutations (login, register, logout, importMap, spatialSelect)
hooks/                # useIsMobile, useQueryParam
lib/
  api/v1.d.ts         # Auto-generated types from api/openapi.json
  utils.ts            # cn() tailwind merge util
fetch-client.ts       # openapi-fetch client (baseUrl from config, credentials: include)
```

### Routes
| Path | Auth | Page |
|---|---|---|
| `/` | Protected | Home — main map workspace |
| `/new` | Protected | Initialize — import wizard |
| `/login` | Public | Login |
| `/register` | Public | Register |
| `/versions` | Protected | Debug/versions |

Protected routes: redirect to `/login` if unauthenticated; redirect to `/initialize` if no maps.

### Auth Flow
- Cookie-based sessions (credentials: "include")
- `AuthProvider` fetches `/me` and `/maps` on load
- Redirect logic lives in `me-provider/index.tsx`

### Map Workspace (Home Page)
- MapLibre GL canvas with vector tile layers from backend
- Sidebar: active layer selector, selection counter, node actions (assign/move/merge/split/delete), base map style toggle
- Lasso drawing: polygon drawn on map → `POST /spatial/select` → highlights selected nodes
- Layer rendering: fill (opacity by selection state), outline, label layers per map layer

### API Type Generation
```bash
cd app
pnpm openapi:generate        # regenerate src/lib/api/v1.d.ts from ../api/openapi.json
pnpm openapi:generate:watch  # watch mode
```

### Running Locally
```bash
cd app
pnpm install
pnpm dev     # starts on http://localhost:5173
```

---

## Development Notes

### Conventions
- Path alias `@/*` → `app/src/*` (no relative imports rule enforced by ESLint)
- Feature-driven folder structure under `features/`
- All server queries/mutations live in `queries/` — not inline
- Strict TypeScript: `noUnusedLocals`, `noUnusedParameters`

### Key Files to Know
- `api/src/app/config.py` — all environment settings
- `api/src/models/graph.py` — core NodeModel/LayerModel/MapModel
- `api/src/services/graph.py` — GraphService (main business logic)
- `api/src/routers/spatial.py` — lasso selection logic
- `api/src/routers/mvt.py` — vector tile generation
- `app/src/features/home/page.tsx` — main workspace state & layout
- `app/src/features/home/components/map/index.tsx` — map rendering + lasso
- `app/src/features/initialize/page.tsx` — import wizard
- `app/src/queries/mutations.ts` — all API mutations
- `app/src/app/providers/me-provider/index.tsx` — auth guard logic

---

## Geometry Recomputation

### When geometry must be recomputed
Any operation that changes which zip codes belong to which territory, or which nodes belong to which parent, invalidates the pre-computed PostGIS geometry on affected nodes. This includes:
- **Bulk zip assign/unassign** (`PUT /zip-assignments/{layer_id}/bulk`) — changes territory shape
- **Node reparent** (`PUT /nodes/bulk/reparent`) — changes parent node's child set
- **Node merge** (`POST /nodes/merge`) — creates new node with inherited children
- **Bulk delete** (`DELETE /nodes/bulk`) — orphans or reparents children
- Single-node edits (not yet triggering recompute — TODO)

### How to trigger recompute from a router endpoint
```python
# 1. Run the service call (mutates nodes/zips in session)
graph_service.some_operation(data)

# 2. Stage the job record (do NOT commit yet)
job_id = _enqueue_recompute(db, map_id)   # helper in routers/graph.py

# 3. Commit changes + job record together
db.commit()

# 4. Dispatch the Celery task AFTER commit (worker must see committed rows)
from src.workers.tasks.maps import recompute_map_task
recompute_map_task.delay(job_id, map_id)
```

### Celery tasks
- `import_map_task` — full recompute with `force=True`; used on initial import
- `recompute_map_task` — incremental recompute with `force=False`; used after edits.
  Skips nodes whose input signature (child zip set or child geom hashes) hasn't changed.
  Both tasks are defined in `api/src/workers/tasks/maps.py` and share `_run_map_computation()`.

### Job types and frontend display
`MapJobModel.job_type` is `"import"` or `"recompute"`. The home page sidebar polls
`GET /maps/{id}` every 2 s while a job is active (`refetchInterval` in `queries.getMap`)
and shows job-type-aware labels:
- Pending/processing: step string, or `"Computing…"` (import) / `"Recomputing…"` (recompute)
- Failed: `"Import failed"` or `"Recompute failed"`

After any bulk mutation, the frontend calls `queryClient.invalidateQueries` on the
`getMap` query key so the "Recomputing…" status appears immediately without waiting
for the next poll cycle.

### TODO — single-node operations not yet triggering recompute
`PUT /nodes/{node_id}`, `DELETE /nodes/{node_id}`, `PUT /zip-assignments/{layer_id}/{zip_code}`
do not yet enqueue a recompute. Add `_enqueue_recompute` + `recompute_map_task.delay`
following the same pattern above when implementing those.
