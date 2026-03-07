# POI Review Dashboard — Comprehensive Test Plan

## 1. Feature Coverage Analysis

### 1.1 Backend API (18 Endpoints)

| # | Endpoint | Method | Feature | Priority |
|---|----------|--------|---------|----------|
| 1 | `/` | GET | Health check | P1 |
| 2 | `/api/pois` | GET | List all POIs (gzip + ETag) | P0 |
| 3 | `/api/pois/<gid>` | GET | Get single POI | P0 |
| 4 | `/api/pois` | POST | Create POI | P0 |
| 5 | `/api/pois/<gid>` | PATCH | Update POI (audit logged) | P0 |
| 6 | `/api/pois/bulk` | PATCH | Bulk update | P1 |
| 7 | `/api/pois/<gid>` | DELETE | Delete POI | P1 |
| 8 | `/api/pois/export` | GET | CSV export | P1 |
| 9 | `/api/stats` | GET | Dashboard statistics | P1 |
| 10 | `/api/login` | POST | Reviewer authentication | P0 |
| 11 | `/api/reviewers` | GET | List reviewers | P2 |
| 12 | `/api/audit-log` | GET | Audit log with filters | P1 |
| 13 | `/api/audit-log/stats` | GET | Per-reviewer stats | P2 |
| 14 | `/api/arcgis-token` | GET | ArcGIS token proxy | P1 |
| 15 | `/api/arcgis-image` | GET | Image proxy + HEIC convert | P1 |
| 16 | `/api/arcgis-search` | GET | Survey123 feature search | P1 |
| 17 | `/api/survey123-to-poi/<oid>` | POST | Create POI from Survey123 | P1 |
| 18 | `/api/validate-poi` | POST | QA validation pipeline | P0 |
| 19 | `/webhook/survey123` | POST | Survey123 webhook | P0 |
| 20 | `/api/pois/recent-updates` | GET | Unacknowledged updates | P2 |
| 21 | `/api/pois/recent-updates/ack` | POST | Acknowledge updates | P2 |

### 1.2 Frontend Views (7 Tabs)

| # | View | Features | Priority |
|---|------|----------|----------|
| 1 | Card View | Table, pagination, search, filters, bulk select | P0 |
| 2 | Excel View | Editable cells, sorting, field groups | P0 |
| 3 | Audit Log | Log table, filters, stats cards | P1 |
| 4 | Duplicates | Detection, merge, golden record, dismiss | P1 |
| 5 | Map View | Markers, clustering, popups, category filter | P2 |
| 6 | ArcGIS Media | Grid, assign modal, create POI, lazy load | P0 |
| 7 | Invoice | Pricing, budget, export | P2 |

### 1.3 Cross-Cutting Features

| # | Feature | Priority |
|---|---------|----------|
| 1 | Login / session management | P0 |
| 2 | POI detail panel (slide-in) | P0 |
| 3 | QA validation (18 GATE rules) | P0 |
| 4 | ArcGIS two-way sync | P1 |
| 5 | CSV import/export | P1 |
| 6 | Toast notifications | P2 |
| 7 | Offline/localStorage mode | P2 |

---

## 2. Test Case Design

### 2.1 Backend API Tests

#### TC-API-001: Health Check
- **Normal**: GET `/` → 200, `{status: 'ok'}`

#### TC-API-002: GET /api/pois
- **Normal**: Returns array of POIs with all fields
- **Gzip**: Request with `Accept-Encoding: gzip` → compressed response
- **ETag**: Second request with `If-None-Match` → 304 Not Modified
- **Edge**: Empty database → returns `[]`
- **Error**: DB connection failure → 500 with traceback

#### TC-API-003: GET /api/pois/<gid>
- **Normal**: Valid GlobalID → 200 with POI data
- **Not found**: Invalid GlobalID → 404
- **Edge**: GlobalID with special characters (braces, dashes)

#### TC-API-004: POST /api/pois
- **Normal**: Create with Name_EN + Name_AR + Category → 201, returns GlobalID
- **Auto-ID**: Create without GlobalID → auto-generated UUID
- **Custom ID**: Create with explicit GlobalID → uses provided ID
- **Minimal**: Create with only Name_EN → succeeds
- **Empty**: Empty body → 400
- **Duplicate**: Same Name_EN twice → both succeed (no unique constraint)
- **Edge**: Arabic-only names, very long names (500+ chars)

#### TC-API-005: PATCH /api/pois/<gid>
- **Normal**: Update Name_EN → 200, field changed
- **Audit**: Update with `_reviewer` → audit log entry created
- **Multi-field**: Update 5 fields at once → all changed, 5 audit entries
- **Not found**: Invalid GID → 404
- **Readonly**: Try to change GlobalID → ignored
- **Edge**: Set field to empty string, set to NULL, update timestamps

#### TC-API-006: PATCH /api/pois/bulk
- **Normal**: Array of 3 updates → all succeed
- **Mixed**: Some valid, some invalid GIDs → partial success
- **Empty**: Empty array → returns updated: 0
- **Large**: 100 updates → all succeed

#### TC-API-007: DELETE /api/pois/<gid>
- **Normal**: Delete existing POI → 200
- **Not found**: Delete non-existent → 404
- **Edge**: Delete then GET → 404

#### TC-API-008: POST /api/login
- **Normal**: Valid username + password → 200 with user info
- **Wrong password**: Valid user, wrong pass → 401
- **Unknown user**: Non-existent username → 401
- **Missing fields**: No password → 401
- **Case sensitivity**: Username case matters

#### TC-API-009: POST /api/validate-poi
- **Pass**: Complete POI with all fields → PASS
- **Fail blockers**: Missing Name_AR → FAIL_BLOCKER, GATE-A1
- **Warnings**: Name_AR contains English → PASS_WITH_WARNINGS
- **Auto-fix**: Invalid floor → auto-set UNAVAILABLE
- **Coordinates**: Lat=0, Lon=0 → BLOCKER
- **Saudi bounds**: Lat=50 → BLOCKER (outside 15-35)
- **Duplicate media**: Same URL in Exterior + Interior → warning
- **F&B logic**: Restaurant without Menu_Photo → MAJOR warning
- **Boolean auto-fix**: Non-F&B with Menu='Yes' → auto-UNAPPLICABLE
- **Edge**: All fields empty, all fields valid, mixed

#### TC-API-010: POST /webhook/survey123
- **Normal**: Standard feature payload → creates/updates POI
- **Update**: Matching Name_EN exists → updates fields
- **Create**: No matching name → creates new POI
- **Geometry**: Payload with x/y → lat/lon extracted
- **Formats**: Test all 3 payload formats (feature.attributes, attributes, flat)
- **Empty**: Empty payload → 400

#### TC-API-011: GET /api/audit-log
- **Normal**: Returns paginated log entries
- **Filter reviewer**: `?reviewer=waleed` → only waleed's entries
- **Filter POI**: `?global_id={...}` → only that POI's entries
- **Pagination**: `?limit=10&offset=5` → correct window
- **Edge**: No audit entries → empty array

#### TC-API-012: CSV Export
- **Normal**: GET /api/pois/export → CSV with BOM, all POIs
- **Edge**: POIs with commas, quotes, newlines in data → properly escaped
- **Arabic**: Arabic text preserved in UTF-8

#### TC-API-013: ArcGIS Token
- **Normal**: Returns valid token
- **Caching**: Second call returns cached token (no re-auth)

#### TC-API-014: ArcGIS Image Proxy
- **Normal**: Valid ArcGIS URL → image bytes
- **HEIC**: HEIC image → JPEG conversion
- **Bad URL**: Non-ArcGIS URL → 400
- **Edge**: Missing URL param → 400

#### TC-API-015: Survey123 to POI
- **Normal**: Valid objectid → 201 with new POI
- **Duplicate**: Name matches existing POI → 409
- **Not found**: Invalid objectid → 404
- **Field mapping**: All Survey123 fields correctly mapped

### 2.2 Frontend Tests

#### TC-UI-001: Login Flow
- Login with valid credentials → dashboard loads
- Login with wrong password → error message
- Skip login → guest mode (no audit, no save to DB)
- Refresh page → session restored from localStorage
- Logout → login overlay shown, localStorage cleared

#### TC-UI-002: Card View
- Page loads → first 50 POIs shown
- Search "restaurant" → filtered results
- Category filter → only matching POIs
- Click row → detail panel opens
- Pagination → next/prev pages work
- Bulk select → checkbox state tracks

#### TC-UI-003: Excel View
- Switch to Excel tab → spreadsheet rendered
- Click cell → becomes editable
- Edit value → cell turns green (modified)
- Sort column → ascending/descending toggle
- Field group tabs → correct columns shown
- Save → PATCH API called

#### TC-UI-004: Detail Panel
- Click POI → panel slides in from right
- All fields displayed with correct values
- Edit field → save → API called → value updated
- Flag POI → Review_Flag set
- Approve POI → Review_Status = 'Reviewed'
- Next/Prev navigation
- Photos tab → images load (HEIC converted)
- Close button → panel slides out

#### TC-UI-005: ArcGIS Media Tab
- Switch to tab → spinner shown → grid loads
- Filter by type → only matching media shown
- Search by name → debounced filter
- Click card → assign modal opens
- Assign as Exterior → card turns green → fades out → DB verified
- "Load More" button → next 24 cards appended
- [NOT IN DB] label → "Create POI from Survey123" button visible
- Create POI → new POI added to allPois

#### TC-UI-006: Duplicate Detection
- Click Duplicates tab → detection runs
- Groups shown with member count
- Expand group → comparison table
- Set golden record → star icon updates
- Merge → golden kept, others removed
- Undo merge → POIs restored

#### TC-UI-007: Bulk Operations
- Select 5 POIs → "5 POIs selected" shown
- Bulk approve → all 5 set to Reviewed
- Bulk flag → all 5 flagged with reason
- Select all page → all 50 on page selected
- Clear selection → count resets to 0

#### TC-UI-008: Validation
- Run validation → cells highlighted (red/orange/yellow)
- Hover highlighted cell → tooltip shows error
- Fix error → cell color clears on re-validate

#### TC-UI-009: Map View
- Switch to Map → markers plotted
- Click marker → popup with POI info
- Category filter → markers update
- Cluster zoom → individual markers shown

#### TC-UI-010: Invoice Calculator
- Switch to Invoice tab → pricing table shown
- Summary cards: Total, Avg, Max values correct
- Budget remaining = 50,000 - Total
- Completion % matches filled vs total fields

---

## 3. Types of Testing

### 3.1 Unit Tests (pytest)
- Individual API endpoint responses
- QA validation rules (each GATE rule independently)
- Password hashing
- Field mapping functions
- CSV generation logic

### 3.2 Integration Tests (pytest + test client)
- Create POI → verify in DB → update → verify audit log
- Login → make authenticated change → verify reviewer in audit
- Survey123 webhook → verify POI created/updated → verify audit trail
- Bulk update → verify all POIs changed

### 3.3 System Tests (Playwright)
- Full user workflows: login → search → edit → save → verify
- Media assignment: browse → select → assign → verify in detail panel
- Duplicate detection → merge → verify merged POI

### 3.4 Regression Tests
- After each deployment: all P0 endpoints return expected responses
- Smoke test: login → load POIs → edit one → save → verify

### 3.5 Performance Tests
- GET /api/pois with 1200+ POIs: response time < 3s
- Gzip compression ratio > 8:1
- Frontend: initial load < 5s on 3G
- Duplicate detection: < 2s for 1200 POIs
- Media grid: render 24 cards < 500ms

### 3.6 Security Tests
- SQL injection: GlobalID with `'; DROP TABLE--`
- XSS: Name_EN with `<script>alert(1)</script>`
- Auth bypass: API calls without login
- CORS: Verify allowed origins
- Token exposure: ArcGIS credentials not in frontend

### 3.7 Usability Tests
- Tab navigation works correctly
- Modal close (X, Escape, overlay click)
- Mobile responsive layout
- Arabic text renders correctly (RTL)
- Toast messages visible and auto-dismiss

---

## 4. Automation Strategy

### 4.1 Tools & Frameworks

| Layer | Tool | Purpose |
|-------|------|---------|
| Backend Unit | **pytest** + **Flask test client** | API endpoints, validation logic |
| Frontend E2E | **Playwright** | UI interactions, visual regression |
| Performance | **locust** or pytest benchmarks | Load testing, response times |
| CI/CD | **GitHub Actions** | Automated test runs on push |

### 4.2 Test File Structure
```
tests/
  conftest.py              # pytest fixtures (app, client, db)
  test_api_health.py       # Health check
  test_api_pois.py         # CRUD operations
  test_api_auth.py         # Login, reviewers
  test_api_audit.py        # Audit log
  test_api_validation.py   # QA validation pipeline
  test_api_survey123.py    # Webhook, Survey123-to-POI
  test_api_export.py       # CSV export
  test_api_performance.py  # Response time benchmarks
  test_api_security.py     # Injection, auth bypass
```

### 4.3 Automation Priority
1. **Phase 1** (Now): Backend API tests with pytest — highest ROI
2. **Phase 2**: QA validation rule tests — critical business logic
3. **Phase 3**: Playwright E2E for critical user flows
4. **Phase 4**: Performance benchmarks

---

## 5. Test Environment Setup

### 5.1 Local Test Environment
- Python 3.11+ with pytest, Flask
- PostgreSQL (local or Docker): `postgresql://postgres:postgres@localhost:5432/poi_test`
- Test database: Separate `poi_test` DB with schema from `final_delivery_dump.sql`
- `.env.test` with test-specific config

### 5.2 Test Data
- **Seed data**: 5 sample POIs covering all edge cases
- **Reviewers**: Pre-seeded from `_seed_reviewers()`
- **Media**: Mock ArcGIS catalogue responses

### 5.3 Mocking
- ArcGIS API calls: Mocked via `unittest.mock.patch`
- Token generation: Returns fixed test token
- Image proxy: Returns test image bytes

---

## 6. Defect Tracking and Reporting

### 6.1 Severity Levels
- **S1 Critical**: Data loss, security breach, complete feature failure
- **S2 Major**: Feature partially broken, workaround exists
- **S3 Minor**: Cosmetic, UX inconvenience
- **S4 Trivial**: Typo, formatting

### 6.2 Defect Template
```
Title: [S1] PATCH /api/pois returns 500 on empty body
Steps: 1. Send PATCH with empty JSON {}
Expected: 400 Bad Request
Actual: 500 Internal Server Error
Environment: Render production
Severity: S2
Priority: P1
```

### 6.3 Reporting
- Test results output: JUnit XML (for CI integration)
- Coverage report: pytest-cov HTML report
- Failed tests trigger GitHub Actions notification

---

## 7. Metrics and Evaluation

### 7.1 Coverage Metrics
| Metric | Target |
|--------|--------|
| API endpoint coverage | 100% (all 21 routes tested) |
| QA validation rule coverage | 100% (all 18 GATE rules) |
| Code line coverage (backend) | > 80% |
| Critical path coverage | 100% (CRUD + auth + validation) |

### 7.2 Quality Metrics
| Metric | Target |
|--------|--------|
| P0 test pass rate | 100% |
| P1 test pass rate | > 95% |
| Defect density (per endpoint) | < 2 |
| Mean time to detect regression | < 5 min (CI pipeline) |

### 7.3 Performance Targets
| Metric | Target |
|--------|--------|
| GET /api/pois (gzipped) | < 3s |
| PATCH /api/pois/<gid> | < 1s |
| POST /api/validate-poi | < 2s |
| Frontend initial load | < 5s |
| Media grid render (24 items) | < 500ms |

### 7.4 Readiness Checklist
- [ ] All P0 tests passing
- [ ] All P1 tests passing (>95%)
- [ ] No S1 defects open
- [ ] No S2 defects in critical paths
- [ ] Performance targets met
- [ ] Security scan clean (no injection vulnerabilities)
