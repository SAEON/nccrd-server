# NCCRD PostgreSQL Architecture Critique, Mapping & Migration Plan

## Context
The NCCRD project is building a new PostgreSQL (v14) database to replace the legacy SQL Server 2019 database.
The new DB lives in `nccrd` schema under `localhost:5432`. The old DB is `localhost:1433`, database `nccrd`.
The goal is to: (1) critique the new schema vs old, (2) produce an exact field-level translation map,
(3) fix schema bugs, (4) add missing tables, and (5) write a Python migration script.
Multi-tenancy: **keep**. Research table: **create as a proper normalized table**.

---

## Phase 1 — Architecture Critique

### What Improved in the New PostgreSQL Schema
- JSON blobs (`project`, `mitigation`, `adaptation`) → normalized relational tables with typed columns
- Native PostgreSQL types: `uuid`, `boolean`, `double precision`, `timestamp`, `jsonb`
- `geo_location JSONB` replaces flat Regions table with structured `{country, province, district, local_municipality, coordinates}`
- Soft-delete now tracks `deleted` (bool) + `deletedate` + `deletedby` (vs single `deletedAt`)
- `progress_report` table replaces `WebSubmissionFiles` with proper FK cascade
- Enum check constraints on `intervention_measurement`, `implementation_status`, `funding_type`

### Critical Gaps (blocking migration)
1. **No `user` table** — `createdby/updatedby/deletedby` integers are orphaned (no FK target)
2. **No `role`, `permission`, `permission_xref_role`** — RBAC entirely absent
3. **No `tenant` / `tenant_xref_submission`** — multi-tenancy (3 tenants, 5,594 links) is missing
4. **No `user_xref_role_xref_tenant`** — 493 user-role assignments orphaned
5. **`vocabulary` table empty, `tree` table doesn't exist** — 728 terms, 19 trees not migrated
6. **No `download_log` / `login` tables** — audit trail missing (148 + 935 rows)
7. **No `research` table** — research submissions will lose structure

### Schema Defects (fix before migration)
- `vocabulary.py`: `Trees` defined as `def Trees(Base)` not `class Trees(Base)` — table never created
- `vocabulary.py`: `VocabularyXrefTree.vocabulary_id` is `UUID` but `Vocabulary.id` is `Integer` — type mismatch
- `vocabulary.py`: `ForeignKey("vocabulary.id")` missing schema prefix → should be `"nccrd.vocabulary.id"`
- Geographic tables (`province`, `district`, `local_district`, `country`) have no PKs, no indexes
- Geometry stored as `text` WKT — not PostGIS, so no spatial queries possible
- Nearly all columns nullable with no defaults — `issubmitted`, `deleted`, `createdate` should be NOT NULL
- `submission_status` is a flat varchar — loses the `userId` (reviewer) from old JSON `{"userId":N,"term":"..."}`
- No `submission_status_updated_by` column — reviewer identity lost during migration
- No ORM `relationship()` defined on `Adaptation` / `Mitigation` back to `Submission`

---

## Phase 2 — Field Translation Map

### 2a. SQL Server `Submissions` → PostgreSQL `nccrd.submission`

| Old Column | Old Type / Notes | New Column | Transform |
|---|---|---|---|
| `id` | uniqueidentifier (GUID) | `id` (uuid) | Direct copy |
| `_id` | int auto-increment | `_id` (serial) | Direct copy; reset sequence after |
| `_projectTitle` | Denormalized nvarchar | `title` | Direct |
| `_projectDescription` | Denormalized nvarchar | `description` | Direct |
| `isSubmitted` | bit (0/1) | `issubmitted` (bool) | `bool(val)` |
| `createdBy` | int FK→Users.id | `createdby` (int) | Direct (FK valid after users migrated) |
| `createdAt` | datetime2 | `createdate` (timestamp) | Direct |
| `deletedAt` | datetime2 or NULL | `deletedate` + `deleted` | `deleted = (deletedAt IS NOT NULL)` |
| `submissionComments` | nvarchar MAX | `submission_comments` | Direct |
| `submissionStatus` | JSON `{"userId":7,"term":"Pending"}` | `submission_status` + `submission_status_updated_by` | Extract `.term` and `.userId` |
| *(new field)* | — | `updatedate` | NULL |
| *(new field)* | — | `updatedby` | NULL |
| *(new field)* | — | `deletedby` | NULL |

### 2b. `project` JSON blob → `nccrd.submission` columns

Actual JSON keys confirmed from database:

| Old `project.*` key | New column | Transform |
|---|---|---|
| `title` | `title` | Cross-check with `_projectTitle` |
| `description` | `description` | Cross-check with `_projectDescription` |
| `implementationStatus` | `implementation_status` | Normalize to enum (Planned / Under Implementation / Completed / Cancelled / On Hold) |
| `implementingOrganization` | `implementation_organization` | Direct |
| `otherImplementingPartners` | `implementation_partners_other` | Direct (string) |
| `startYear` | `start_date` | `datetime(int(val), 1, 1)` |
| `endYear` | `end_date` | `datetime(int(val), 12, 31)` |
| `link` | `link` | Direct |
| `fundingOrganisation` | `funding_organization` | Direct |
| `fundingType` | `funding_type` | Normalize to enum (Grant / Loan / Own Funding / Public-Private Partnership / None / Other) |
| `actualBudget` | `funding_amount` | `float(val)` |
| `estimatedBudget` | `estimated_budget_cost` | Direct (string) |
| `province` + `districtMunicipality` + `localMunicipality` + `xy` | `geo_location` (jsonb) | Build: `{type:"Point", country:"ZAF", province:..., district:..., local_municipality:..., coordinates:[lon,lat]}` |
| `projectManagerName` | `project_manager_name` | Direct |
| `projectManagerOrganization` | `project_manager_organization` | Direct |
| `projectManagerEmail` | `project_manager_email` | Direct |
| `projectManagerTelephone` + `projectManagerMobile` | `project_manager_contact_number` | Merge: `tel / mobile` |
| `interventionType` | `intervention_measurement` | Map to enum |
| `cityOrTown` | *(no equivalent)* | Include in `geo_location` or drop |

### 2c. `mitigation` JSON blob → `nccrd.mitigation`

Actual JSON keys confirmed from database:

| Old `mitigation.*` key | New column | Notes |
|---|---|---|
| `hostSector` | `sector` | Direct |
| `hostSubSectorPrimary` | `subsector` | Direct |
| `primaryIntendedOutcome` | `primary_intended_outcome` | Direct |
| `coBenefitEnvironmentalDescription` | `environmental_co_benefit_description` | Direct |
| `coBenefitSocialDescription` | `social_co_benefit_description` | Direct |
| `coBenefitEconomicDescription` | `economic_co_benefit_description` | Direct |
| `carbonCredit` (bool) | `carbon_credit` | Direct |
| `progressData` (object) | `progress_calculator` | Serialize as JSON string |
| `fileUploads` (array) | → `nccrd.progress_report` rows | One row per file upload |
| *(no old equivalent)* | `national_policy`, `provincial_municipal`, `project_type`, `project_subtype`, `mitigation_program`, `cdm_*`, `voluntary_methodology` | NULL (new fields, future data entry) |

### 2d. `adaptation` JSON blob → `nccrd.adaptation`

Actual JSON keys confirmed from database:

| Old `adaptation.*` key | New column | Notes |
|---|---|---|
| `adaptationSector` | `sector` | Direct |
| `nationalPolicy` | `national_policy` | Direct |
| `hazard` | `hazard` | Direct |
| `observedClimateChangeImpacts` | `climate_impact` | Direct |
| `addressedClimateChangeImpact` | `address_climate_impact` | Direct |
| `responseImpact` | `impact_response` | Direct |
| `target` | `intervention_goal` | Direct |
| `regionalPolicy` | `provincial_municipal` | Direct |
| `otherHazard` | *(combine into `hazard`)* | Append to hazard string |
| `otherNationalPolicy` | *(combine into `national_policy`)* | Append |
| `fileUploads` | → `nccrd.progress_report` rows | One row per file upload |
| *(no equivalent)* | `progress_calculator` | NULL |

### 2e. `research` blob → `nccrd.research`

Old `research` keys: **empty in all sampled rows** — likely embedded in `project` JSON.
Strategy: create table with `raw_data jsonb` and store the blob as-is for now.
Normalize structure in a future migration once research JSON schema is documented.

---

## Phase 3 — Schema Fixes

### Alembic migration `0002_schema_hardening.py`
**File to create:** `nccrd-build/nccrd-server/alembic/versions/0002_schema_hardening.py`

#### 3a. Fix `vocabulary.py` bugs first
**File:** `nccrd-build/nccrd-server/nccrd/db/models/vocabulary.py`
```python
# BEFORE (bug):
def Trees(Base):

# AFTER (fix):
class Trees(Base):

# BEFORE (type mismatch):
vocabulary_id = Column(UUID, ForeignKey("vocabulary.id"))

# AFTER (correct type + schema prefix):
vocabulary_id = Column(Integer, ForeignKey("nccrd.vocabulary.id"))

# All other ForeignKeys — add schema prefix:
ForeignKey("nccrd.vocabulary.id")
ForeignKey("nccrd.trees.id")
```

#### 3b. Fix `submission.py`
**File:** `nccrd-build/nccrd-server/nccrd/db/models/submission.py`
```python
# Add new column:
submission_status_updated_by = Column(Integer, ForeignKey("nccrd.user.id"), nullable=True)

# Add ORM relationships:
Submission.adaptations = relationship("Adaptation", back_populates="submission", cascade="all, delete-orphan")
Submission.mitigations = relationship("Mitigation", back_populates="submission", cascade="all, delete-orphan")
Adaptation.submission = relationship("Submission", back_populates="adaptations")
Mitigation.submission = relationship("Submission", back_populates="mitigations")
```

#### 3c. New tables to create in migration `0002`

```sql
nccrd.user                       -- id serial PK, uuid UUID unique, name, email unique, saeon_id, id_token, created_at, deleted bool
nccrd.role                       -- id serial PK, name unique, description
nccrd.permission                 -- id serial PK, name unique, description
nccrd.permission_xref_role       -- id serial PK, permission_id→permission, role_id→role, UNIQUE(permission_id, role_id)
nccrd.tenant                     -- id serial PK, hostname unique, title, theme jsonb, contact_email, is_default bool, include_unbounded bool
nccrd.tenant_xref_submission     -- tenant_id→tenant, submission_id uuid→submission.id, PK composite
nccrd.user_xref_role_xref_tenant -- id serial PK, user_id→user, role_id→role, tenant_id→tenant, UNIQUE(user_id,role_id,tenant_id)
nccrd.tree                       -- id serial PK, name unique, description
nccrd.vocabulary_xref_tree       -- id serial PK, vocabulary_id→vocabulary, tree_id→tree, UNIQUE(vocabulary_id,tree_id)
nccrd.vocabulary_xref_vocabulary -- id serial PK, parent_id→vocabulary, child_id→vocabulary, tree_id→tree, UNIQUE(child_id,tree_id)
nccrd.vocabulary_xref_region     -- id serial PK, vocabulary_id→vocabulary, region_code varchar
nccrd.download_log               -- id serial PK, user_id→user, timestamp, submission_ids jsonb, submission_search text
nccrd.login                      -- id serial PK, user_id→user, timestamp
nccrd.research                   -- id serial PK, submission_id uuid→submission.id, raw_data jsonb
```

#### 3d. Alter existing tables + add indexes

```sql
-- submission: enforce NOT NULL with defaults
ALTER COLUMN issubmitted SET NOT NULL, SET DEFAULT FALSE
ALTER COLUMN deleted SET NOT NULL, SET DEFAULT FALSE
ALTER COLUMN createdate SET NOT NULL, SET DEFAULT NOW()
ADD COLUMN submission_status_updated_by INTEGER REFERENCES nccrd.user(id)
ADD CONSTRAINT fk_submission_createdby FOREIGN KEY (createdby) REFERENCES nccrd.user(id)

-- Indexes for common query patterns
CREATE INDEX idx_submission_createdate ON nccrd.submission(createdate DESC)
CREATE INDEX idx_submission_createdby ON nccrd.submission(createdby)
CREATE INDEX idx_submission_deleted ON nccrd.submission(deleted) WHERE deleted = FALSE
CREATE INDEX idx_submission_issubmitted ON nccrd.submission(issubmitted) WHERE issubmitted = TRUE
CREATE INDEX idx_submission_geo_location ON nccrd.submission USING GIN(geo_location)
CREATE INDEX idx_mitigation_submission_id ON nccrd.mitigation(submission_id)
CREATE INDEX idx_adaptation_submission_id ON nccrd.adaptation(submission_id)
CREATE INDEX idx_province_name ON nccrd.province("PR_NAME")
CREATE INDEX idx_district_province ON nccrd.district("PROVINCE")
CREATE INDEX idx_local_district_province ON nccrd.local_district("PROVINCE")
```

---

## Phase 4 — Migration Script

**File to create:** `mysql nccrd/migrate_nccrd.py`

### Step 0: Pre-flight validation
1. Connect to both DBs; assert connectivity
2. Count all source rows; store as expected counts for post-migration comparison
3. Build vocab lookup dict `{old_id: term_string}` from SQL Server `Vocabulary`
4. Build region lookup dict `{code: {name, level, parentCode}}` from SQL Server `Regions`

### Step 1: Reference data (no FK dependencies)
`Vocabulary` (728) → `nccrd.vocabulary`
`Trees` (19) → `nccrd.tree`
`VocabularyXrefTree` (751) → `nccrd.vocabulary_xref_tree`
`VocabularyXrefVocabulary` (730) → `nccrd.vocabulary_xref_vocabulary`

### Step 2: Users (must run before submissions — FK dependency)
`Users` (257) → `nccrd.user` — **preserve original integer IDs**
`Logins` (935) → `nccrd.login`

### Step 3: Roles, Permissions, Tenants
`Roles` (5) → `nccrd.role`
`Permissions` (27) → `nccrd.permission`
`PermissionXrefRole` (71) → `nccrd.permission_xref_role`
`Tenants` (3) → `nccrd.tenant`
`UserXrefRoleXrefTenant` (493) → `nccrd.user_xref_role_xref_tenant`

### Step 4: Submissions — transaction-per-row

For each of 2,427 old submission rows:
```
1. Parse submissionStatus JSON → extract term (→ submission_status) and userId (→ submission_status_updated_by)
2. Parse project JSON → map all fields per Section 2b
3. INSERT nccrd.submission

4. If mitigation JSON non-empty → INSERT nccrd.mitigation (Section 2c)
   - For each fileUploads entry → INSERT nccrd.progress_report

5. If adaptation JSON non-empty → INSERT nccrd.adaptation (Section 2d)
   - For each fileUploads entry → INSERT nccrd.progress_report

6. If research JSON non-empty → INSERT nccrd.research (raw_data = JSON blob)
```
Each submission + its children = one PostgreSQL transaction.
On failure: rollback, log to `migration_errors.csv` (old_id, error, raw JSON), continue next row.

### Step 5: Cross-references + audit tables
`TenantXrefSubmission` (5,594) → `nccrd.tenant_xref_submission`
`DownloadLog` (148) → `nccrd.download_log`
`WebSubmissionFiles` (18) → `nccrd.progress_report`

### Step 6: Post-migration verification
- Row count check: expected vs actual for every table
- Spot-check 10 random submissions: old JSON blob vs new relational rows
- FK integrity: JOIN all child tables back to parent; report orphans
- Print final summary report

---

## Execution Order

| # | Action | File |
|---|---|---|
| 1 | Fix bugs in `vocabulary.py` | `nccrd/db/models/vocabulary.py` |
| 2 | Add `submission_status_updated_by` + relationships to `submission.py` | `nccrd/db/models/submission.py` |
| 3 | Write alembic migration `0002_schema_hardening.py` | `alembic/versions/0002_schema_hardening.py` |
| 4 | Run `alembic upgrade head` | (shell command) |
| 5 | Run migration script Step 0 (pre-flight + inspect) | `mysql nccrd/migrate_nccrd.py` |
| 6 | Run migration Steps 1–3 (reference data, users, roles/tenants) | same |
| 7 | Run migration Step 4 (submissions — the main migration) | same |
| 8 | Run migration Steps 5–6 (cross-refs + verification) | same |

---

## Source vs Target Row Count Summary

| Source Table (SQL Server) | Rows | Target Table (PostgreSQL) |
|---|---|---|
| Users | 257 | nccrd.user |
| Roles | 5 | nccrd.role |
| Permissions | 27 | nccrd.permission |
| PermissionXrefRole | 71 | nccrd.permission_xref_role |
| Tenants | 3 | nccrd.tenant |
| TenantXrefSubmission | 5,594 | nccrd.tenant_xref_submission |
| UserXrefRoleXrefTenant | 493 | nccrd.user_xref_role_xref_tenant |
| Vocabulary | 728 | nccrd.vocabulary |
| Trees | 19 | nccrd.tree |
| VocabularyXrefTree | 751 | nccrd.vocabulary_xref_tree |
| VocabularyXrefVocabulary | 730 | nccrd.vocabulary_xref_vocabulary |
| Submissions | 2,427 | nccrd.submission |
| Submissions (mitigation blob) | ~2,427 | nccrd.mitigation |
| Submissions (adaptation blob) | ~2,427 | nccrd.adaptation |
| Submissions (research blob) | varies | nccrd.research |
| Logins | 935 | nccrd.login |
| DownloadLog | 148 | nccrd.download_log |
| WebSubmissionFiles | 18 | nccrd.progress_report |
| **TOTAL** | **~12,600+** | |
