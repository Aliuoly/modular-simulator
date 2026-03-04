# Research: Authoritative External References for Deterministic Command Transaction Envelopes
# Date: 2026-02-24
# Context: Task - Gather authoritative external references for idempotency, revision/concurrency, and batch transaction patterns

## HIGH-SIGNAL SOURCES (6-10 authoritative references with relevance)

### 1. IETF Draft: The Idempotency-Key HTTP Header Field (draft-ietf-httpapi-idempotency-key-header-07)
**URL**: https://datatracker.ietf.org/doc/draft-ietf-httpapi-idempotency-key-header/
**Relevance**: RFC-track standard defining idempotency-key semantics, error handling (400, 409, 422), and enforcement patterns for POST/PATCH operations.
**Key Points**:
- Idempotency-Key as Item Structured Header (RFC8941)
- Uniqueness requirements: MUST be unique per request/payload
- Error scenarios: missing key (400), reuse with different payload (422), concurrent outstanding (409)
- Idempotency fingerprint: checksum or payload hash for duplicate detection
- Implementation Status: Stripe, Adyen, Dwolla, Interledger, WorldPay, Yandex, Finastra, Datatrans all use custom Idempotency-Key headers
**Alignment**: Direct match with ModularSimulator's idempotency requirements for mutation commands

### 2. MDN: Idempotency-Key header documentation
**URL**: https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Idempotency-Key
**Relevance**: Browser-authoritative reference explaining idempotency semantics for POST/PATCH methods and retry-safe request handling
**Key Points**:
- POST and PATCH are non-idempotent by default
- Idempotency-Key allows clients to resend unacknowledged requests safely
- Prevents duplicate state changes (e.g., duplicate orders, double charges)
**Alignment**: Clarifies when idempotency is needed (all mutation operations in ModularSimulator)

### 3. PostgreSQL: Concurrency Control (Chapter 13)
**URL**: https://www.postgresql.org/docs/16/mvcc.html
**Relevance**: Database-level concurrency control patterns for optimistic locking, transaction isolation, and serialization failure handling
**Key Points**:
- MVCC (Multi-Version Concurrency Control) for read committed/repeatable read/serializable isolation
- Explicit locking (table, row, advisory locks) for pessimistic concurrency
- Serialization failure handling for detected conflicts
- Advisory locks for application-level coordination
**Alignment**: Underlying database patterns for revision-based concurrency checks and atomic transaction rollback

### 4. Stripe Python SDK: Idempotency Key Implementation
**URL**: https://github.com/stripe/stripe-python
**File**: stripe/_request_options.py (lines 30, 46)
**Relevance**: Production-proven Python implementation of idempotency key handling in payment API
**Key Points**:
```python
# Request options include idempotency_key field
"idempotency_key": None  # Default to None, client can set
```
- Idempotency keys passed per-request
- Auto-generation patterns for safety
**Alignment**: Demonstrates per-request idempotency_key field in command envelope

### 5. Saleor E-Commerce Platform: Transaction Item Idempotency
**URL**: https://github.com/saleor/saleor
**Files**: 
- saleor/payment/migrations/0053_auto_20231211_0850.py (idempotency_key field addition)
- saleor/payment/migrations/0054_add_idempotency_key_indexes.py (unique constraints)
- saleor/graphql/payment/mutations/transaction/transaction_initialize.py (validation logic)
**Relevance**: Real-world Python e-commerce platform with idempotency keys for transaction items and events
**Key Points**:
```python
# Migration adds idempotency_key field
field=models.CharField(blank=True, max_length=512, null=True)

# Unique index on (app_identifier, idempotency_key) for transactionitem
# Unique index on (transaction_id, idempotency_key) for transactionevent
```
- Unique constraints ensure one operation per key per scope
- Validation prevents empty string idempotency keys
- Error handling for duplicate key reuse
**Alignment**: Production pattern for scoped uniqueness (per-transaction, per-app) and validation

### 6. RFC 9457: Problem Details for HTTP APIs (updates RFC 7807)
**URL**: https://swagger.io/blog/problem-details-rfc9457-doing-api-errors-well
**Relevance**: Standard for structured error payloads with type, status, title, detail, instance, and extensions
**Key Points**:
- Standardized error object structure: type, status, title, detail, instance, extensions
- Extensions (e.g., code, errors array) for additional context
- Must-ignore pattern for extension fields
- IANA registry for common problem type URIs
- Anti-patterns: inconsistent formats, hiding errors in 200 OK, leaking stack traces
**Alignment**: Direct pattern for ModularSimulator error payload design (code, message, path, retry hints)

### 7. Django: Database Transactions Documentation
**URL**: https://docs.djangoproject.com/en/4.2/topics/db/transactions/
**Relevance**: Python framework's transaction management patterns, atomic context managers, and savepoints
**Key Points**:
- autocommit mode vs explicit transaction wrapping
- atomic() context manager for all-or-nothing operations
- ATOMIC_REQUESTS setting for request-scoped transactions
- Savepoints for nested subtransactions
- Rollback on exception, commit on success
**Alignment**: Pythonic transaction patterns for command engine atomicity

### 8. FastAPI ETag/Conditional Requests Articles
**URLs**: 
- https://medium.com/@kaushalsinh73/fastapi-etags-conditional-writes-prevent-lost-updates-without-heavy-locking-d517c91c9850
- https://bugfactory.io/articles/using-the-if-match-header-to-avoid-collisions/
**Relevance**: Python-specific ETag/If-Match patterns for optimistic concurrency in FastAPI
**Key Points**:
- ETag as version fingerprint (hash or version ID)
- If-Match header for conditional updates on PATCH/PUT
- 412 Precondition Failed on version mismatch
- Prevents lost updates in concurrent editing scenarios
- Alternatives: pessimistic locking, last-write-wins (both problematic)
**Alignment**: Pattern for expected_revision field in command envelopes with HTTP-standard semantics

### 9. Wikipedia: Optimistic Concurrency Control
**URL**: https://en.wikipedia.org/wiki/Optimistic_concurrency_control
**Relevance**: Foundational concept for OCC phases and conflict detection
**Key Points**:
- Phases: Begin, Read, Validate, Write (commit or rollback)
- No locks during transaction, conflict detection at commit time
- Best for low-contention scenarios
- Higher throughput than locking-based methods when conflicts are rare
**Alignment**: Theoretical foundation for revision-based conflict detection in command engine

### 10. python-statemachine Library
**URL**: https://github.com/pytransitions/transitions (6425 stars)
**Relevance**: Mature Python state machine library with transitions, guards, callbacks
**Key Points**:
- Declarative state/transition definition
- Guard conditions for conditional transitions
- Callbacks before/after transitions
- Hierarchical and nested states support
- Async transition support
**Alignment**: State machine patterns for simulation lifecycle (running, paused, checkpointing, error states)

## PATTERN COMPARISON TABLE: Command Envelope Fields and Atomicity Handling

| Field/Concept | IETF Idempotency Key | Stripe Pattern | Saleor Pattern | FastAPI ETag | ModularSimulator (Proposed) |
|---------------|------------------------|----------------|----------------|---------------|-------------------------------|
| Idempotency Key | Idempotency-Key header (RFC8941) | idempotency_key in request options | N/A | idempotency_key (str, UUID) |
| Key Scope | Per operation | Per API call | (app_identifier, key) or (transaction_id, key) | Per operation or batch |
| Version/Revision | N/A | N/A | ETag header | expected_revision (int) |
| Conflict Detection | Concurrent outstanding (409) | Key reuse detection | If-Match mismatch (412) | Revision mismatch or key reuse |
| Error Codes | 400, 409, 422 | Payment-specific | 412, 404 | Custom catalog (RFC9457) |
| Error Payload | RFC 7807 Problem Details | API-specific | RFC 7807 Problem Details | RFC 9457 Problem Details |
| Batch Support | N/A | N/A | N/A | commands list in envelope |
| Atomicity | Single request only | Single request | Single conditional update | Multi-command with rollback |
| Rollback | N/A (client retry) | N/A | N/A | Explicit compensation/undo |
| Fingerprint | Checksum of payload | N/A | Hash of resource | N/A (optional) |

### ATOMICITY HANDLING PATTERNS COMPARISON

| Aspect | Database Transactions | Django atomic() | Django ATOMIC_REQUESTS | Command Engine Pattern (ModularSimulator) |
|---------|---------------------|----------------|---------------------|------------------------------------|
| Scope | Transaction block | Context manager | HTTP request scope | Command envelope or batch |
| Commit | Explicit COMMIT or auto | Exit context without exception | Response returns successfully | All validation/compile steps pass |
| Rollback | Explicit ROLLBACK or exception | Exception in context | Exception in view | Any validation/compile failure |
| Nesting | Savepoints | Nested atomic() | Subtransactions via savepoints | Batched commands as sub-transactions |
| Retry | Application-level | Application-level | Application-level | Idempotency key + expected_revision |
| Locking | Pessimistic (SELECT FOR UPDATE) | Pessimistic available | Pessimistic available | Optimistic (revision checks) |

## ALIGNMENT WITH EXISTING MODULARSIMULATOR ARCHITECTURE

### Existing Patterns (from codebase analysis)
1. **Queued Mutations** (src/modular_simulation/connection/network.py)
   - Already implements FIFO mutation queue
   - Aligns with tick-boundary apply requirement
   - Command envelope can extend this pattern

2. **Runtime Apply/Barrier** (src/modular_simulation/connection/runtime.py)
   - Existing barrier sequencing for deterministic tick boundaries
   - Command engine can integrate with existing apply timing
   - Revision tracking already implicit in state transitions

3. **Topology Validation** (src/modular_simulation/connection/topology.py)
   - Graph integrity checks already present
   - Invariant validator can extend existing patterns
   - Destructive edit policy can leverage existing dependency tracking

4. **Process Binding Contracts** (src/modular_simulation/connection/process_binding.py)
   - Port binding contracts already defined
   - Command envelope fields can reuse existing PortReference types
   - Junction-as-unit pattern matches existing abstractions

### Recommended Alignment Strategy

**ADOPT NOW** (KISS scope - immediate implementation):
1. **Idempotency-Key Header Pattern** (IETF draft)
   - Add `idempotency_key: str` to CommandEnvelopeContract
   - UUID generation for client-side key creation
   - 409 Conflict for concurrent outstanding, 422 for payload mismatch
   - Persistence of idempotency keys across checkpoints

2. **RFC 9457 Error Payloads**
   - Define ProblemDetails dataclass with type, status, title, detail, instance
   - Extensions: code, path, hint, revision (current/expected)
   - Use in all API error responses
   - CLI error mapping to same codes

3. **Django atomic() Pattern for Transaction Engine**
   - Wrap command execution in atomic() context manager
   - Explicit savepoints for batched sub-commands
   - Rollback on any validation/compile failure
   - Reuse existing DatabaseTransactionError handling

4. **expected_revision Field** (FastAPI ETag pattern)
   - Add `expected_revision: int` to CommandEnvelopeContract
   - Check against current graph revision before commit
   - Return 409 Conflict with current/expected revision details
   - Support for optimistic concurrency in multi-client scenarios

5. **Saleor-Style Unique Constraints**
   - Database unique index on (operation_type, idempotency_key) for pending commands
   - Or in-memory map for pending keys within runtime (no DB overhead for single-process)
   - Validation prevents empty strings and key reuse

**DEFER** (out of KISS scope - future consideration):
1. **Saga Pattern for Distributed Compensation**
   - Not needed: single-process deterministic runtime
   - Compensation transactions add complexity without benefit
   - Existing atomic rollback handles failures adequately

2. **Complex Idempotency Fingerprints**
   - Payload checksum adds computational overhead
   - Simple key uniqueness suffices for deterministic game backend
   - Fingerprint useful if clients vary payloads (not our use case)

3. **Advisory Locks for Coordination**
   - Database-level locks unnecessary for single-process runtime
   - Revision checks provide sufficient concurrency control
   - Advisory locks useful for multi-service coordination (out of scope)

4. **Hierarchical State Machines**
   - pytransitions library powerful but overkill for simple simulation states
   - Enum-based state tracking sufficient for running/paused/checkpointing/error
   - Can upgrade if state complexity grows

5. **ETag HTTP Headers for Read Operations**
   - Conditional GET/304 Not Modified optimization not needed
   - Simulation state typically read for control, not cached by clients
   - Performance gains minimal for low-latency game loop

## PRACTICAL ERROR PAYLOAD DESIGN PATTERNS

### RFC 9457 Problem Details Structure
```python
@dataclass
class ProblemDetails:
    type: str  # URI to problem type documentation
    status: int  # HTTP status code
    title: str  # Human-readable summary
    detail: str  # Specific explanation of occurrence
    instance: Optional[str] = None  # URI to specific occurrence
    code: Optional[str] = None  # Machine-readable error code (extension)
    path: Optional[str] = None  # Field path or resource path (extension)
    hint: Optional[str] = None  # Retry or remediation hint (extension)
    revision: Optional[dict] = None  # {"current": int, "expected": int} (extension)
```

### Error Code Catalog Examples
| Code | Message | HTTP Status | Retry | Hint |
|------|---------|--------------|-------|------|
| IDEMPOTENCY_KEY_MISSING | Idempotency-Key header required for this operation | 400 | No | Generate UUID and retry |
| IDEMPOTENCY_KEY_REUSE | Idempotency-Key already used with different payload | 422 | No | Use new key for different operation |
| REVISION_MISMATCH | Expected revision X does not match current Y | 409 | Yes | Fetch current state and retry with correct revision |
| CONCURRENT_OUTSTANDING | Request with same key currently processing | 409 | Yes | Wait and retry with same key |
| INVALID_PORT_DIRECTION | Port must be inlet or outlet | 400 | No | Correct port direction in command |
| DESTRUCTIVE_EDIT_DEPENDENTS | Cannot remove unit with 2 dependents | 400 | No | Use safe-detach mode or remove dependents first |
| GEOMETRY_INVALID | Radius and length must be positive | 400 | No | Provide valid geometry values |
| VERSION_MISMATCH | Checkpoint version 1.2.3 incompatible with runtime 1.2.4 | 422 | No | Use same package version for save/load |

## BATCH TRANSACTION ROLLBACK STRATEGIES

### Single-Process Atomic Rollback (Recommended for ModularSimulator)
**Pattern**: Django atomic() context manager with savepoints
```python
with transaction.atomic():
    try:
        # Parse command envelope
        for cmd in envelope.commands:
                with transaction.savepoint():
                        # Semantic validate
                        # Invariant validate
                        # Compile preview
        # All validation passes - commit all changes
        update_revision()
        enqueue_for_tick_boundary()
    except ValidationError as e:
        # Automatic rollback to savepoint or transaction boundary
        # No partial state mutation
        raise ProblemDetails(status=400, code=...)
```

### Compensation Transaction Pattern (Defer - Not Needed)
**Pattern**: Execute forward operations, then reverse on failure
- Overkill for single-process in-memory state
- Existing atomic rollback simpler and more reliable
- Useful for distributed services (out of scope)

### State Snapshot Revert Pattern (Defer - Last Resort)
**Pattern**: Save state snapshot before transaction, restore on failure
- Memory overhead for large simulations
- Slower than atomic rollback
- Only needed if atomic context not available (not our case)

## ARCHITECTURAL RECOMMENDATIONS SUMMARY

### IMMEDIATE ADOPTION (KISS-compliant):
1. ✅ CommandEnvelopeContract with idempotency_key (UUID) and expected_revision (int)
2. ✅ RFC 9457 error payloads with code, message, path, hint, revision
3. ✅ Django atomic() transaction context with savepoints for batches
4. ✅ In-memory idempotency key tracking for pending commands
5. ✅ Revision-based optimistic concurrency (no distributed locks)
6. ✅ Unique constraint pattern for key collision detection

### FUTURE CONSIDERATIONS (defer until justified by use case):
1. ⏸️ Saga compensation pattern (if multi-service or external integrations added)
2. ⏸️ Payload fingerprinting (if clients send variable payloads for same operation)
3. ⏸️ Hierarchical state machines (if simulation state complexity grows)
4. ⏸️ ETag HTTP headers for reads (if caching/conditional GET becomes valuable)
5. ⏸️ Advisory database locks (if coordination beyond revision checks needed)

### KEY PRINCIPLES FROM RESEARCH:
- **Idempotency prevents duplicate mutations**: IETF standard for POST/PATCH safety
- **Optimistic concurrency > Pessimistic locking**: Higher throughput, sufficient for single-process
- **Structured errors > Ad hoc strings**: RFC 9457 enables automated client handling
- **Atomic rollback > Compensation transactions**: Simpler, faster for in-memory state
- **Revision checks > Database locks**: Cleaner for deterministic runtime

## CONCRETE GITHUB CODE EXAMPLES (3 references)

### 1. Saleor - Idempotency Key Validation
**URL**: https://github.com/saleor/saleor/blob/main/saleor/graphql/payment/mutations/transaction/transaction_initialize.py#L139-L212
**Pattern**: Clean idempotency key validation with structured errors
**Relevance**: Production Python validation logic to emulate

### 2. Stripe Python SDK - Request Options
**URL**: https://github.com/stripe/stripe-python/blob/master/stripe/_request_options.py#L30-L46
**Pattern**: Per-request idempotency key in request options
**Relevance**: Python SDK pattern for per-command idempotency field

### 3. pytransitions - State Machine Library
**URL**: https://github.com/pytransitions/transitions
**Pattern**: Declarative state/transition definitions with guards
**Relevance**: Mature Python state machine implementation to study (if future complexity justifies adoption)
#NK|# --- ADDITIONAL RESEARCH FINDINGS (2026-02-24) ---
#RW|
#HB|## ADDITIONAL HIGH-AUTHORITY REFERENCES (Beyond Initial 10 Sources)
#MQ|
#JN|### 11. AWS Lambda Powertools Python - Idempotency Utility
#YT|**URL**: https://docs.aws.amazon.com/powertools/python/latest/utilities/idempotency/
#VR|**Relevance**: Production-grade Python idempotency utility for Lambda functions with DynamoDB/Redis/Valkey backends
#ZT|**Key Points**:
#BP|- Supports DynamoDB, Valkey, Redis OSS, or any Redis-compatible cache
#KV|- Safeguards concurrent requests, timeouts, missing keys, payload tampering
#SX|- Configurable idempotency key selection (one/multiple fields, entire payload)
#PY|- Returns cached previous successful result on duplicate calls
#WV|- Time-windowed idempotency for expiration handling
#TJ|**Alignment**: Production-proven Python implementation with persistence layer abstraction
#HZ|
#JN|### 12. If-Match HTTP Header - MDN Documentation
#YT|**URL**: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/If-Match
#VR|**Relevance**: Browser-authoritative reference for conditional requests and 412 Precondition Failed semantics
#ZT|**Key Points**:
#BP|- If-Match makes request conditional on ETag match
#KV|- Server returns resource only if matches one of provided ETag values
#SX|- 412 Precondition Failed response if match fails (no modification)
#PY|- Uses strong comparison algorithm (byte-by-byte)
#WV|- Two common use cases: lost update prevention (PUT) and range requests
#TJ|**Alignment**: HTTP-standard semantics for expected_revision field in command envelopes
#HZ|
#JN|### 13. Cosmos Python Book - Unit of Work Pattern
#YT|**URL**: https://www.cosmicpython.com/book/chapter_06_uow.html
#VR|**Relevance**: Production-quality Python implementation of Unit of Work pattern with transactions
#ZT|**Key Points**:
#BP|- Unit of Work tracks multiple repository operations as single transaction
#KV|- Atomic commit/rollback across repositories and message bus
#SX|- Supports both read and write operations with transaction boundaries
#PY|- Integrates with Django ORM for database operations
#WV|- Clear separation between domain logic and data access
#TJ|**Alignment**: Pattern reference for transaction engine lifecycle (parse -> validate -> commit/rollback)
#HZ|
#JN|### 14. Redis Transaction Patterns (MULTI/EXEC/WATCH)
#YT|**URL**: https://redis.io/docs/latest/develop/clients/redis-py/transpipe
#VR|**Relevance**: Redis documentation for atomic transactions and optimistic locking patterns
#ZT|**Key Points**:
#BP|- MULTI/EXEC for atomic command batching
#KV|- WATCH for optimistic concurrency control (abort if watched key changes)
#SX|- Watch-multiple-watch-exec pattern for conditional writes
#PY|- Redis transactions are all-or-nothing (no partial execution)
#WV|- Useful for distributed coordination when/if needed
#TJ|**Alignment**: Reference for understanding optimistic locking mechanics; deferred for single-process runtime
#HZ|
#JN|### 15. Gist: Unit of Work with Context Manager
#YT|**URL**: https://gist.github.com/tsensei/979109dc542d463758daecd7b3c39234
#VR|**Relevance**: Concrete Python implementation of transactional Unit of Work with rollback
#ZT|**Key Points**:
#BP|- Step-based execution with explicit execute/rollback methods
#KV|- Context manager integration for with-block usage
#SX|- Reverse rollback order on failure (undo last operation first)
#PY|- Separates execution logic from transaction management
#WV|- Retry decorator support for resilience
#TJ|**Alignment**: Pattern reference for command pipeline with compensation rollback (defer option)
#HZ|
#JN|### 16. FastAPI + ETags - Conditional Writes (2026)
#YT|**URL**: https://medium.com/@kaushalsinh73/fastapi-etags-conditional-writes-prevent-lost-updates-without-heavy-locking-d517c91c9850
#VR|**Relevance**: 2026-dated FastAPI-specific ETag implementation with optimistic concurrency
#ZT|**Key Points**:
#BP|- ETag as version fingerprint (hash or integer version)
#KV|- If-Match header for conditional updates (412 on mismatch)
#SX|- Prevents lost updates in concurrent editing scenarios
#PY|- Compares ETag and If-Match using strong comparison
#WV|- Higher throughput than locking for low-contention systems
#TJ|**Alignment**: Direct reference for FastAPI-style expected_revision implementation
#HZ|
#JN|### 17. Event-Driven.io - Optimistic Concurrency with ETags
#YT|**URL**: https://event-driven.io/en/how_to_use_etag_header_for_optimistic_concurrency/
#VR|**Relevance**: Production guidance for OCC implementation with ETag headers
#ZT|**Key Points**:
#BP|- Phases: read with version, modify, validate version match, commit
#KV|- Update entity version on successful commit
#PX|- Reject if version from database ≠ expected version
#SX|- Retry workflow on conflict detection
#WV|- Suitable for low-contention, high-throughput systems
#TJ|**Alignment**: Theoretical foundation for revision-based conflict detection
#HZ|
#JN|## ADDITIONAL GITHUB CODE EXAMPLES
#YT|
#VR|### 1. Stripe Python SDK - Idempotency Key Handling (with Permalinks)
#VK|**Repository**: https://github.com/stripe/stripe-python
#ZM|**Commit**: a643eac6562ca7addbb37c3aa95fa3bafa5809f0
#BK|
#QJ|#### File: stripe/_request_options.py (lines 9-55)
#TS|**Permalink**: https://github.com/stripe/stripe-python/blob/a643eac/stripe/_request_options.py#L9-L55
#RT|
#HS|```python
#HK|class RequestOptions(TypedDict):
#KZ|    api_key: NotRequired["str|None"]
#SM|    stripe_version: NotRequired["str|None"]
#HB|    stripe_account: NotRequired["str|None"]
#VT|    stripe_context: NotRequired["str | StripeContext | None"]
#BR|    max_network_retries: NotRequired["int|None"]
#WJ|    idempotency_key: NotRequired["str|None"]  # ← Key field
#XM|    content_type: NotRequired["str|None"]
#KQ|    headers: NotRequired["Mapping[str, str]|None"]
#YB|
#JF|def merge_options(requestor, request):
#NZ|    # Merge client and request options
#YH|    return {
#WK|        "api_key": requestor.api_key,
#WK|        "idempotency_key": request.get("idempotency_key"),  # ← Per-request override
#YM|        # ... other fields
#SQ|    }
#RY|```
#QK|
#BX|**Pattern**: TypedDict with optional idempotency_key field, merge logic for client/request options
#JF|
#ZM|#### File: stripe/_api_requestor.py (lines 515-521)
#TS|**Permalink**: https://github.com/stripe/stripe-python/blob/a643eac/stripe/_api_requestor.py#L515-L521
#RT|
#HS|```python
#HK|# Build request headers
#KZ|idempotency_key = options.get("idempotency_key")
#SM|if idempotency_key:
#HB|    headers["Idempotency-Key"] = idempotency_key  # ← HTTP header injection
#VT|
#BR|# Auto-generate for POST and V2 delete if not provided
#WJ|if method == "post" or (api_mode == "V2" and method == "delete"):
#XM|    headers.setdefault("Idempotency-Key", str(uuid.uuid4()))  # ← UUID generation
#KQ|```
#YB|
#JF|**Pattern**: Per-request header injection, auto-UUID generation for mutation methods
#JF|
#JN|### 2. Saleor - Transaction Idempotency Validation (with Permalinks)
#YT|**Repository**: https://github.com/saleor/saleor
#VK|**Commit**: 368a33e306817b6f2473c71f14060a1dd3dcaa28
#BK|
#QJ|#### File: saleor/graphql/payment/mutations/transaction/transaction_initialize.py (lines 140-225)
#TS|**Permalink**: https://github.com/saleor/saleor/blob/368a33e/saleor/graphql/payment/mutations/transaction/transaction_initialize.py#L140-L225
#RT|
#HS|```python
#HK|@classmethod
#KZ|def clean_idempotency_key(cls, idempotency_key: str | None):
#SM|    if not idempotency_key and isinstance(idempotency_key, str):
#HB|        raise ValidationError(
#VT|            message="Cannot be provided as an empty string.",
#BR|            code=TransactionInitializeErrorCode.INVALID.value,
#WJ|        )
#XM|    if not idempotency_key:
#KQ|        idempotency_key = str(uuid.uuid4())  # ← Auto-generate if None
#YB|    return idempotency_key
#JF|
#NZ|@classmethod
#YH|def perform_mutation(cls, root, info, *, idempotency_key=None):
#WK|    # ... validation and setup ...
#YM|
#SQ|    idempotency_key = cls.clean_idempotency_key(idempotency_key)  # ← Clean/validate
#RY|
#QK|    try:
#BX|        transaction, event, data = handle_transaction_initialize_session(
#HZ|            # ... parameters ...
#JN|            idempotency_key=idempotency_key,  # ← Pass to handler
#VW|        )
#KS|    except TransactionItemIdempotencyUniqueError as e:  # ← Unique constraint violation
#QP|        if payment_ids:
#XR|            activate_payments(payment_ids)  # ← Rollback side effects
#HZ|        raise ValidationError(
#JN|            message="Different transaction with provided idempotency key already exists.",
#VW|            code=TransactionInitializeErrorCode.UNIQUE.value,
#KS|        ) from e
#QP|
#XR|    return cls(transaction=transaction, transaction_event=event, data=data)
#RY|```
#QK|
#BX|**Pattern**: 
#HZ|- Validation prevents empty strings
#JN|- Auto-generation with UUID4
#VW|- Unique constraint error handling with rollback
#KS|- Explicit error code (UNIQUE) for client handling
#QP|
#JN|### 3. Django - Transaction Atomic Implementation (from Source)
#YT|**Repository**: https://github.com/django/django
#VK|**Relevance**: Production-grade transaction management in Python's most popular web framework
#BK|
#QJ|#### File: django/db/transaction.py (Atomic.__enter__ and __exit__)
#TS|**Source**: Django 4.2 documentation (https://docs.djangoproject.com/en/4.2/_modules/django/db/transaction)
#RT|
#HS|```python
#HK|class Atomic(ContextDecorator):
#KZ|    def __enter__(self):
#SM|        connection = get_connection(self.using)
#HB|        
#VT|        if not connection.in_atomic_block:
#BR|            # Reset state for outermost block
#WJ|            connection.commit_on_exit = True
#XM|            connection.needs_rollback = False
#KQ|        
#YB|        if connection.in_atomic_block:
#JF|            # Create savepoint for nested transaction
#NZ|            if self.savepoint and not connection.needs_rollback:
#YH|                sid = connection.savepoint()  # ← Savepoint creation
#WK|                connection.savepoint_ids.append(sid)
#YM|            else:
#SQ|                connection.savepoint_ids.append(None)
#RY|        else:
#QK|            # Start transaction for outermost block
#BX|            connection.set_autocommit(False)
#HZ|            connection.in_atomic_block = True
#JN|
#VW|        connection.atomic_blocks.append(self)
#KS|
#QP|    def __exit__(self, exc_type, exc_value, traceback):
#XR|        connection = get_connection(self.using)
#HZ|        connection.atomic_blocks.pop()
#JN|
#VW|        if exc_type is None and not connection.needs_rollback:
#KS|            # Success path: release savepoint or commit
#QP|            if sid is not None:
#XR|                connection.savepoint_commit(sid)  # ← Release savepoint
#HZ|            elif connection.commit_on_exit:
#JN|                connection.commit()  # ← Commit transaction
#VW|        else:
#KS|            # Failure path: rollback to savepoint or transaction
#QP|            if sid is None:
#XR|                connection.rollback()  # ← Full transaction rollback
#HZ|            else:
#JN|                connection.savepoint_rollback(sid)  # ← Savepoint rollback
#VW|            connection.needs_rollback = True
#KS|
#QP|        # Outermost block: final commit or rollback
#XR|        if not connection.in_atomic_block:
#HZ|            if connection.commit_on_exit and not connection.needs_rollback:
#JN|                connection.commit()
#VW|            else:
#KS|                connection.rollback()
#QP|```
#XR|
#HZ|**Pattern**: 
#JN|- Nested atomic blocks use savepoints for partial rollback
#VW|- Outermost block manages transaction commit/rollback
#KS|- Exception-based rollback (any exception triggers rollback)
#QP|- Thread-safe connection management
#XR|
#JN|## UPDATED PATTERN COMPARISON: Envelope Fields Across Implementations
#YT|
#VK|**Table 2: Comprehensive Idempotency & Concurrency Field Comparison**
#BK|
#QJ| Implementation     | Idempotency Key    | Key Scope           | Version/Revision    | Conflict Detection    | Auto-Generation       | Persistence Layer
#TS|--------------------|---------------------|---------------------|------------------|--------------------|--------------------|---------------------|
#RT| IETF Draft        | Idempotency-Key (RF...| Per operation       | N/A              | 409/422 error codes | Not specified        | N/A (standard)
#HS| Stripe SDK         | idempotency_key     | Per API call        | N/A              | Unique violation    | UUID4 (if missing)  | Stripe backend
#KZ| Saleor            | idempotency_key     | (app,key) or (tx,key)| N/A              | UNIQUE error code | UUID4 (if None)    | Database unique idx
#SM| AWS Powertools     | Configurable        | Per function        | N/A              | Deduplication      | Configurable       | DynamoDB/Redis/Valkey
#HB| FastAPI ETag      | ETag (response)     | Per resource        | If-Match header  | 412 Precondition   | Hash/int version     | N/A (state-based)
#VT| Django Transactions | N/A                | N/A                | Savepoints       | Exception-based    | N/A                | Database connection
#BR| ModularSimulator   | idempotency_key     | Per operation/batch | expected_revision | 409/409/422       | UUID4              | In-memory (single-proc)|
#WJ|                   |                     |                     |                  |                    |                    |                     |
#XM|
#KQ|**Key Insights:**
#YB|- **UUID generation** is standard across Stripe, Saleor, Powertools
#JF|- **Scoped uniqueness**: Saleor uses composite keys (app,key) or (tx,key) for multi-tenancy
#NZ|- **Error codes**: 409 (conflict), 422 (payload mismatch), 412 (version mismatch) are standard
#YH|- **Persistence**: Most production systems use database (Stripe, Saleor, Powertools)
#WK|- **Single-process optimization**: ModularSimulator can use in-memory tracking for performance
#YM|
#SQ|## UPDATED RECOMMENDATIONS FOR MODULARSIMULATOR
#RY|
#QK|### ADOPT NOW (KISS-aligned - Immediate Implementation Priority):
#BX|
#HZ|**1. Idempotency Key Field with UUID Generation** (sources 1, 4, 11, 16)
#JN|- Add `idempotency_key: str` to CommandEnvelopeContract
#VW|- Use UUID4 generation when not provided (Stripe pattern)
#KS|- Validate: reject empty strings (Saleor pattern)
#QP|- Auto-generate for all mutation commands
#XR|
#HZ|**2. HTTP-Standard Error Semantics** (sources 1, 6, 12)
#JN|- 409 Conflict for concurrent outstanding or key reuse
#VW|- 422 Unprocessable Entity for payload mismatch with same key
#KS|- 412 Precondition Failed for expected_revision mismatch
#QP|- RFC 9457 Problem Details structure for all errors
#XR|
#HZ|**3. expected_revision with If-Match Semantics** (sources 8, 12, 16, 17)
#JN|- Add `expected_revision: int` to CommandEnvelopeContract
#VW|- Check against current graph revision before commit
#KS|- Return 409 with current/expected details on mismatch
#QP|- Support optimistic concurrency for multi-client scenarios (defer if single-process)
#XR|
#HZ|**4. Atomic Transaction Context with Savepoints** (sources 7, 13, 15, 18)
#JN|- Use Python context manager for transaction boundary
#VW|- Nested atomic blocks use savepoints for batched commands
#KS|- Exception-based rollback (any validation/compile failure triggers rollback)
#QP|- Follow Django pattern: commit on success, rollback on exception
#XR|
#HZ|**5. In-Memory Idempotency Tracking** (optimization for single-process runtime)
#JN|- Track pending idempotency keys in memory map
#VW|- Remove from map on completion (commit or rollback)
#KS|- Skip database overhead for production use case
#QP|- Scale to database if multi-process/multi-service in future
#XR|
#HZ|**6. Revision Increment on Commit** (sources 3, 17)
#JN|- Increment graph revision counter on successful transaction commit
#VW|- Persist revision in checkpoint envelope (Task 11)
#KS|- Use revision for deterministic replay verification (Task 12)
#QP|
#JN|### DEFER (Out of KISS scope - future consideration):
#YT|
#VK|**1. AWS Powertools Integration** (source 11)
#BK|- Production-grade but adds DynamoDB/Redis dependency
#QJ|- Useful if moving to distributed/serverless architecture
#TS|- Keep pattern in mind for future migration path
#RT|
#HS|**2. Redis WATCH for Distributed Coordination** (source 14)
#KZ|- Adds complexity for optimistic locking across processes
#SM|- Single-process runtime doesn't need distributed coordination
#HB|- Defer until multi-process or microservices architecture
#VT|
#BR|**3. Compensation Transaction Pattern** (source 15)
#WJ|- Unit of Work with undo operations
#XM|- More complex than atomic rollback
#KQ|- Useful for distributed saga workflows (out of scope)
#YB|
#JF|**4. HTTP ETag Headers for Reads** (sources 8, 12, 16)
#NZ|- Conditional GET with 304 Not Modified optimization
#YH|- Simulation state typically read for control, not cached
#WK|- Performance gains minimal for low-latency game loop
#YM|
#SQ|**5. Database Advisory Locks** (source 3)
#RY|- PostgreSQL advisory locks for cross-service coordination
#QK|- Revision checks provide sufficient concurrency control for single-process
#BX|- Defer until multi-service architecture
#HZ|
#JN|## ALIGNMENT WITH CURRENT ARCHITECTURE
#VW|
#KS|### Existing ModularSimulator Patterns (from codebase):
#QP|
#XR|1. **ConnectionNetwork - Queued Mutations** (`src/modular_simulation/connection/network.py`)
#HZ|   - Already implements FIFO mutation queue
#JN|   - Aligns with tick-boundary apply requirement
#VW|   - Command envelope can extend this pattern with idempotency/revision fields
#KS|
#QP|2. **ConnectionRuntime - Barrier Sequencing** (`src/modular_simulation/connection/runtime.py`)
#XR|   - Existing barrier sequencing for deterministic tick boundaries
#HZ|   - Transaction engine can integrate with existing apply timing
#JN|   - Revision tracking already implicit in state transitions
#VW|
#KS|3. **ConnectionTopology - Graph Integrity** (`src/modular_simulation/connection/topology.py`)
#QP|   - Graph integrity checks already present
#XR|   - Invariant validator can extend existing patterns
#HZ|   - Destructive edit policy can leverage existing dependency tracking
#JN|
#VW|## IMPLEMENTATION CHECKLIST (Task 2 Guidance):
#KS|
#QP|**Command Envelope Contract:**
#XR|```python
#HZ|@dataclass
#JN|class CommandEnvelopeContract:
#VW|    idempotency_key: str  # UUID4 for deduplication
#KS|    expected_revision: Optional[int]  # Optimistic concurrency check
#QP|    metadata: Dict[str, Any]  # Extensible metadata
#XR|    commands: List[MutationCommand]  # Batch support
#HZ|
#JN|    def __post_init__(self):
#VW|        # Validate idempotency_key is not empty string
#KS|        if not self.idempotency_key:
#QP|            raise ValidationError("idempotency_key cannot be empty")
#XR|
#HZ|        # Auto-generate if not provided (Stripe/Saleor pattern)
#HZ|        if not getattr(self, '_idempotency_key_generated', False):
#JN|            self.idempotency_key = str(uuid.uuid4())
#VW|```
#KS|
#QP|**Transaction Lifecycle:**
#XR|```python
#HZ|from contextlib import contextmanager
#JN|
#VW|@contextmanager
#KS|def execute_transaction(envelope: CommandEnvelopeContract):
#QP|    """Parse -> Validate -> Compile -> Commit/Rollback"""
#XR|    # Parse envelope (semantic validation)
#HZ|    parsed_commands = parse_commands(envelope.commands)
#JN|
#VW|    # Check expected_revision (optimistic concurrency)
#KS|    if envelope.expected_revision is not None:
#QP|        if current_revision() != envelope.expected_revision:
#XR|            raise ConflictError(
#HZ|                code="REVISION_MISMATCH",
#JN|                message=f"Expected revision {envelope.expected_revision}, current {current_revision()}",
#VW|                current=current_revision(),
#KS|                expected=envelope.expected_revision,
#QP|            )  # 409 Conflict
#XR|
#HZ|    with atomic_transaction():  # Django-like atomic context
#JN|        try:
#VW|            # Check idempotency key uniqueness
#KS|            if idempotency_key_exists(envelope.idempotency_key):
#QP|                raise ConflictError(
#XR|                    code="IDEMPOTENCY_KEY_REUSE",
#HZ|                    message="Idempotency key already in use",
#JN|                )  # 409 Conflict
#VW|
#KS|            # Mark key as in-use (concurrent outstanding)
#QP|            mark_idempotency_key_pending(envelope.idempotency_key)
#XR|
#HZ|            # Semantic and invariant validation
#JN|            for cmd in parsed_commands:
#VW|                with savepoint():  # Savepoint for each command
#KS|                    validate_semantic(cmd)
#QP|                    validate_invariants(cmd)
#XR|                    compile_preview(cmd)
#HZ|
#JN|            # All validation passed - commit all changes
#VW|            apply_commands(parsed_commands)
#KS|            increment_revision()
#QP|            enqueue_for_tick_boundary()  # Existing pattern
#XR|
#HZ|        except ValidationError as e:
#JN|            # Automatic rollback to transaction or savepoint boundary
#VW|            raise ProblemDetails(
#KS|                type="/errors/validation-error",
#QP|                status=400,
#XR|                title="Validation Failed",
#HZ|                detail=str(e),
#JN|                code=e.code,
#VW|            )  # 400/422 based on error type
#KS|
#QP|        except ConflictError as e:
#XR|            # Revision or idempotency conflict - no state mutation
#HZ|            raise ProblemDetails(
#JN|                type="/errors/conflict-error",
#VW|                status=409,
#KS|                title="Conflict Detected",
#QP|                detail=str(e),
#XR|                code=e.code,
#HZ|                current=getattr(e, 'current'),
#JN|                expected=getattr(e, 'expected'),
#VW|            )  # 409 Conflict
#KS|
#QP|        finally:
#XR|            # Always release idempotency key
#HZ|            mark_idempotency_key_completed(envelope.idempotency_key)
#JN|```
#VW|
#KS|## SUMMARY: 17 AUTHORITATIVE REFERENCES COLLECTED
#QP|
#XR|**Standards & RFCs (2):**
#HZ|1. IETF Draft: Idempotency-Key HTTP Header (draft-ietf-httpapi-idempotency-key-header-07)
#JN|2. RFC 9457: Problem Details for HTTP APIs
#VW|
#KS|**Official Documentation (4):**
#QP|3. MDN: Idempotency-Key and If-Match headers
#XR|4. PostgreSQL: Concurrency Control (Chapter 13)
#HZ|5. Django: Database Transactions documentation
#JN|6. FastAPI: ETag conditional requests patterns
#VW|
#KS|**Production Python Implementations (3):**
#QP|7. Stripe Python SDK: Idempotency key request handling
#XR|8. Saleor E-Commerce: Transaction item idempotency with validation
#HZ|9. AWS Lambda Powertools: Production-grade idempotency utility
#JN|
#VW|**GitHub Code Examples (3 with Permalinks):**
#KS|10. Stripe Python: request_options.py and _api_requestor.py with commit SHA
#QP|11. Saleor: transaction_initialize.py with commit SHA and error handling
#XR|12. Django: transaction.py atomic implementation (from docs)
#HZ|
#VW|**Patterns & Theory (5):**
#KS|13. Wikipedia: Optimistic Concurrency Control (OCC foundations)
#QP|14. Cosmos Python Book: Unit of Work pattern
#XR|15. Redis: MULTI/EXEC/WATCH transaction patterns
#HZ|16. Gist: Unit of Work with context manager
#JN|17. python-statemachine: State machine library (defer)
#VW|
#KS|### Key Takeaways for ModularSimulator:
#QP|
#XR|1. **Idempotency is standard** - IETF draft, Stripe, Saleor, AWS Powertools all use it
#HZ|2. **UUID generation is default** - Stripe, Saleor, Powertools auto-generate UUID4
#JN|3. **409/422/412 are standard error codes** - Used across Stripe, Saleor, MDN
#VW|4. **Atomic rollback > Compensation** - Django pattern is simpler for in-memory state
#KS|5. **Revision checks > Database locks** - Optimistic concurrency sufficient for single-process
#QP|6. **Savepoints for batched commands** - Nested atomic blocks with partial rollback
#XR|7. **In-memory optimization** - Single-process runtime doesn't need database persistence
#HZ|
#JN|### Adopt-Now vs Defer Decision Matrix:
#VW|
#KS|**ADOPT NOW (KISS-aligned):**
#QP|- ✅ Idempotency key with UUID generation
#XR|- ✅ expected_revision with 409/412 error codes
#HZ|- ✅ Atomic context manager with savepoints
#JN|- ✅ In-memory idempotency tracking
#VW|- ✅ RFC 9457 error payloads
#KS|- ✅ Revision increment on commit
#QP|
#XR|**DEFER (future consideration):**
#HZ|- ⏸️ AWS Powertools (distributed infrastructure)
#JN|- ⏸️ Redis WATCH (multi-process coordination)
#VW|- ⏸️ Compensation transactions (complex saga pattern)
#KS|- ⏸️ HTTP ETag for reads (caching optimization)
#QP|- ⏸️ Database advisory locks (single-process doesn't need them)
#XR|⏸️ Hierarchical state machines (overkill for simple simulation states)
#HZ|
#JN|**Research completed 2026-02-24. Sources aligned with KISS principles and single-process deterministic runtime constraints.**


## F1 Plan Compliance Audit (2026-02-25)
- Verdict: PASS (Tasks 1-18 comply with plan intent and acceptance criteria based on direct verification and targeted file audit).
- Scope: audited plan checkboxes, Task 15-18 implementation artifacts, and verification commands aligned to plan acceptance criteria.

### Compliance matrix (Tasks 15-18)
| Task | Plan intent + acceptance target | Evidence run | Result | Notes |
| --- | --- | --- | --- | --- |
| 15 | Shared error catalog with stable payload fields and API/CLI parity (`tests/connection/test_error_catalog.py`, `tests/cli/test_cli_error_mapping.py`) | `uv run python -m pytest -q tests/connection/test_error_catalog.py tests/cli/test_cli_error_mapping.py` | PASS | 5 passed; payload schema includes `code/message/path/hint/revision`; parity assertions pass. |
| 16 | Baseline quality tooling + CI lint/type/smoke alignment (`ruff`, `mypy`, CI workflow) | `uv run python -m ruff check src tests && uv run --with mypy python -m mypy src`; `uv run python -m pytest -q tests -k "smoke"` | PASS | Lint/type checks pass; smoke selector passes; `.github/workflows/ci.yml` runs lint/type/targeted tests. |
| 17 | Full dynamic workflow contract/integration wave including failure-path matrix | `uv run python -m pytest -q tests/connection tests/components tests/persistence tests/cli tests/integration/test_dynamic_process_network_workflow.py`; `uv run python -m pytest -q tests/connection tests/cli -k "rollback or mismatch or invalid"` | PASS | 206 passed on full command; 38 failure-path tests passed. |
| 18 | Minimal-boilerplate docs/examples for command/spec paths + save/load continuation | `uv run python -m pytest -q tests/integration/test_examples_smoke.py`; corrected selectors: `-k "quickstart and two and process"` and `-k "save and load and continue"` | PASS (with caveat) | As-written plan selectors with plain spaces are invalid pytest syntax; corrected boolean `-k` form executes intended tests and passes. |

### Evidence commands executed
- `grep -nE "\- \[(x| )\] (1[0-8]|[1-9]|F1)\." .sisyphus/plans/dynamic-simulation-api-cli.md`
- `grep -nE "Command-based path|Spec-based path|Dynamic API and CLI Quickstarts|save/load/continue" readme.md`
- `uv run python -m pytest -q tests/connection/test_error_catalog.py tests/cli/test_cli_error_mapping.py`
- `uv run python -m ruff check src tests && uv run --with mypy python -m mypy src`
- `uv run python -m pytest -q tests -k "smoke"`
- `uv run python -m pytest -q tests/connection tests/components tests/persistence tests/cli tests/integration/test_dynamic_process_network_workflow.py`
- `uv run python -m pytest -q tests/connection tests/cli -k "rollback or mismatch or invalid"`
- `uv run python -m pytest -q tests/integration/test_examples_smoke.py`
- `uv run python -m pytest -q tests/integration/test_examples_smoke.py -k "quickstart two process"` (expected syntax error)
- `uv run python -m pytest -q tests/integration/test_examples_smoke.py -k "save load continue"` (expected syntax error)
- `uv run python -m pytest -q tests/integration/test_examples_smoke.py -k "quickstart and two and process"`
- `uv run python -m pytest -q tests/integration/test_examples_smoke.py -k "save and load and continue"`

### Risks / gaps
- The plan's Task 18 `-k` examples are syntactically invalid in pytest without boolean operators; corrected selectors satisfy intent and should be considered equivalent acceptance evidence.
- No `.sisyphus/evidence/task-*.txt` artifacts were found in this workspace; this audit relies on live re-execution evidence instead.

### Final readiness confidence
- High (0.92): acceptance commands and targeted artifact checks are passing, with only the Task 18 selector syntax caveat requiring explicit interpretation.


## F4 Scope Fidelity Check (2026-02-25)

Verdict: PASS

Evidence reviewed:
- Plan scope and gate: `.sisyphus/plans/dynamic-simulation-api-cli.md` Final Verification Wave includes `F4. Scope Fidelity Check - deep`.
- Changed-file inventory: `git diff --stat` shows tracked implementation concentrated in connection/runtime/system plus quality/docs files; targeted `git status --short --untracked-files=all -- ...` confirms Task 15-18 artifacts are present (CLI, error catalog, quality CI, integration/docs examples).
- Task 15-18 placeholder scan: grep over `src/modular_simulation/cli`, `tests/cli`, `tests/components`, `tests/integration`, `examples/dynamic_api_cli`, `.github`, and `src/modular_simulation/connection/error_catalog.py` found no TODO/FIXME/TBD/placeholder markers.
- Prior concern check (fake-green + broad suppressions): grep for `pyright: ignore`, `type: ignore`, and `# noqa` in Task 15-18 artifacts returned no matches.

In-scope delivered (matches plan intent):
- Task 15: structured diagnostics catalog and parity tests (`src/modular_simulation/connection/error_catalog.py`, `tests/connection/test_error_catalog.py`, `tests/cli/test_cli_error_mapping.py`).
- Task 16: quality baseline wiring (`.github/workflows/ci.yml`, `pyproject.toml`, `opencode.json`) with uv/ruff/mypy/pytest smoke flow.
- Task 17: integration/contract expansion (`tests/components/*.py`, `tests/integration/test_dynamic_process_network_workflow.py`, CLI contract/spec tests).
- Task 18: operator examples/docs (`examples/dynamic_api_cli/*`, `readme.md`, `tests/integration/test_examples_smoke.py`).

Out-of-scope or non-deliverable churn observed:
- Non-functional generated artifacts under tracked new directories (for example `__pycache__/*.pyc`) and `opencode.json:Zone.Identifier`; these are environmental and should be excluded from final commit.
- Minor cosmetic cleanup in `tests/connection/test_plant_scoped_calculation_registrations.py` (removed unused import/comment/blank lines) is not required by dynamic-simulation-api-cli scope; acceptable but non-essential.

Risk classification: LOW
- Core scope alignment is strong across Tasks 15-18 deliverables.
- Main risk is accidental inclusion of environment/generated files in final commit, not runtime behavior drift.

Lockfile judgment (explicit):
- `uv.lock` churn is functionally relevant here because Task 16 introduces/records quality-tool dependencies (`basedpyright`, `nodejs-wheel-binaries`) mirrored from `pyproject.toml` dev dependency updates.
- Per instruction, no separate lockfile concern is raised beyond functional dependency alignment.
