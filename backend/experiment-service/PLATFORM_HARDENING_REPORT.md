# PIHUB Experiment Service Platform Hardening Report

## Scope

This sprint hardened existing experiment-service infrastructure only. It did not add new Experiment Engine workflows, AI behavior, runtime execution, marketplace behavior, P2P transfer, voice, or Math Studio functionality.

## Changes Implemented

### Database Reliability

- Centralized SQLite connection/bootstrap is used for experiment-service stores.
- SQLite hardening is verified on startup:
  - `journal_mode = wal`
  - `foreign_keys = 1`
  - `busy_timeout = 5000`
- Startup logs now emit `[DATABASE] STARTUP_HEALTH_CHECK=...` for each hardened store.
- Added additional classroom indexes for teacher/session and student/submission lookup patterns.

### Transaction Safety

- Builder manifest create/update/delete, publish/archive, revision save, and import draft use the shared transaction helper.
- Sharing analytics increments and package hash records use transactions.
- Classroom session, assignment, and submission writes use transactions.
- Classroom submission creation and student enrollment are atomic in one transaction.

### Payload Protection

- Payload limits are configurable and enforced by middleware.
- Supported environment variables:
  - `MAX_MANIFEST_SIZE`
  - `MAX_SHARE_PACKAGE_SIZE`
  - `MAX_SUBMISSION_SIZE`
  - `MAX_AI_REQUEST_SIZE`
- Older `EXPERIMENT_*_MAX_BYTES` variables remain supported as fallbacks.
- Oversized payloads return the standard error envelope with HTTP `413`.

### Standard Error Contract

Errors are routed through the shared envelope:

```json
{
  "success": false,
  "error": {
    "code": "",
    "message": ""
  }
}
```

This is applied through global handlers for HTTP exceptions, request validation, and unhandled exceptions.

### Pagination

Pagination support is present for:

- Builder manifests
- Builder revisions
- Classroom sessions
- Classroom assignments
- Classroom submissions
- Experiment registry lists and searches
- Experiment templates

Responses include `page`, `page_size`, and `total` where the endpoint already returns an object envelope.

### Observability

- Request middleware adds `request_id`, request start/end logs, response status, and `duration_ms`.
- Startup database verification is logged.
- Existing module logs continue to track builder validation failures, sharing imports/exports, classroom assignment/submission activity, and AI generation operations.

### Hashing And Deduplication

- Builder manifests now persist:
  - `content_hash` for backward compatibility
  - `manifest_hash` for deterministic manifest identity
- Builder revisions now persist `revision_hash`.
- Existing rows are backfilled at repository initialization.
- Sharing now stores package hash records:
  - `package_hash`
  - `manifest_hash`
  - `revision_hash`
  - direction
  - manifest id
- Share imports use verified `manifest_hash` to detect duplicates and return the existing draft/manifest instead of creating another copy.

### Submission Protection

- Classroom submissions enforce one unique submission per `(assignment_id, student_id, result_id)`.
- Duplicate submissions are rejected through the existing classroom validation path.

## SQLite Schema Changes

### Builder Store

- Added `experiment_manifests.manifest_hash`.
- Added `experiment_revisions.revision_hash`.
- Added indexes:
  - `idx_builder_manifests_manifest_hash`
  - `idx_builder_revisions_hash`

### Sharing Store

- Added `sharing_package_hashes`.
- Added `idx_sharing_package_manifest_hash`.

### Classroom Store

- Added indexes:
  - `idx_classroom_sessions_teacher`
  - `idx_classroom_submissions_student`

## Startup Verification Report

Smoke validation confirmed:

```text
journal_mode=wal
foreign_keys=1
busy_timeout=5000
```

Default payload limits:

```text
manifest=524288
share_package=2097152
submission=2097152
ai=262144
```

Hash validation confirmed deterministic `manifest_hash` and `revision_hash` creation.

Duplicate classroom submission validation confirmed SQLite rejects repeated `(assignment_id, student_id, result_id)` attempts.

## Risks Mitigated

- SQLite write contention is reduced through WAL and `busy_timeout`.
- Foreign key enforcement is enabled consistently.
- Partial writes are reduced by centralized transactions.
- Oversized manifest, share, submission, and AI payloads are rejected before route handling.
- API failures now use a consistent error envelope.
- Large builder and classroom lists have pagination.
- Duplicate share imports can be detected by manifest hash.
- Duplicate classroom submissions are blocked explicitly.

## Remaining Risks

- SQLite remains a single-node embedded database and still has write throughput limits under heavy classroom concurrency.
- Some legacy list-returning endpoints intentionally keep their response shape for backward compatibility and do not expose full pagination envelopes.
- Share signatures are deterministic hashes, not asymmetric cryptographic signatures.
- Cross-store operations, such as classroom assignment creation after share package generation, are not globally atomic across separate SQLite files.
- Analytics are still basic counters and may need retention or rollup policies at larger scale.

## Migration Impact

- Existing SQLite databases are upgraded in-place through compatibility column checks.
- Existing `content_hash` remains available.
- Existing APIs remain available.
- New response metadata is additive.
- No Docker, gateway, tutor, sync, pack, P2P, runtime, marketplace, voice, or Math Studio changes were made.

## Validation

```text
python3 -m py_compile ... -> passed
SQLite smoke test -> passed
Startup pragma verification -> passed
Hash persistence test -> passed
Duplicate submission test -> passed
```
