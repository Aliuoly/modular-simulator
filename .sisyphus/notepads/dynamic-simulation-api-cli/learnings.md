## Canonical Runtime Mutation Domain Contracts
- Intent: Establish typed contracts for UnitProcess, JunctionProcess, Port, ConnectionLine, ResistanceConfig, ValveConfig, SensorBinding, ControllerBinding, and command envelope fields.
- Observed patterns: see src/modular_simulation/connection/topology.py (TopologyGraph, ProcessNode, BoundaryNode, JunctionNode), src/modular_simulation/connection/process_binding.py (OutletBinding, ProcessBinding), src/modular_simulation/connection/state.py (MaterialState, PortCondition), src/modular_simulation/connection/runtime.py (Runtime contracts), src/modular_simulation/framework/system.py (System binding), etc.
- Insertion plan: add new module src/modular_simulation/connection/typed_runtime_contracts.py with dataclass-based contracts mirroring topology.py style; implement UnitProcessContract, JunctionProcessContract, PortContract, ConnectionLineContract, ResistanceConfigContract, ValveConfigContract, SensorBindingContract, ControllerBindingContract, CommandEnvelopeContract; reuse existing PortReference, TopologyGraph types for interoperability; add light validation in __post_init__ to enforce field types and allowed values; expose via __all__ = [...] to ease import.
- Extension points: keep KISS by reusing existing patterns; hooks to connect to topology (ProcessNode) and binding (ProcessBinding) semantics; stable IDs could come from edge_id-like tokens or separate stable_id fields near each contract.
- Verification: no code changes yet; this note logs planned approach for Task 1.
#YY|## Hybrid CLI Workflows: Diff/Apply Pattern Research
#MK|- Intent: Gather authoritative external references for hybrid CLI workflows combining terse imperative commands with declarative spec diff/apply while maintaining backend API parity.
#SS|- Observed patterns: From production-grade tools (Kubernetes kubectl, Terraform, AWS CDK, Nomad, ArgoCD, Docker Compose, Google Cloud) - all implement dry-run/diff-before-apply workflows with explicit transaction boundaries.
#KJ|- Research synthesis: compiled patterns below from 8 authoritative sources; extracted command grammar, spec diff/apply flows, safety checks; identified must-have patterns vs nice-to-have extras for this project's KISS goals.
#PY|- Key insight: All mature tools separate validation/preview (diff/plan/dry-run) from execution (apply/run/deploy) into distinct commands; provide atomic operations with --auto-approve flags for automation; maintain 1:1 API parity by using same validation logic for CLI and API.
#XJ|- Verification: appended Feb 24, 2026 - comprehensive research complete.

---

## AUTHORITATIVE SOURCES (8 total)

### Declarative Infra Tools

1. **Kubernetes kubectl diff/apply**  
   URL: https://kubernetes.io/docs/reference/kubectl/generated/kubectl_diff/  
   URL: https://kubernetes.io/docs/reference/kubectl/generated/kubectl_apply/  
   Pattern: `kubectl diff -f spec.yaml` previews unified diff, `kubectl apply -f spec.yaml` applies changes. Supports server-side apply with field management.

2. **Terraform plan/apply**  
   URL: https://developer.hashicorp.com/terraform/cli/commands/plan  
   URL: https://developer.hashicorp.com/terraform/cli/commands/apply  
   Pattern: `terraform plan` creates execution plan with human-readable diff, `terraform apply` executes plan. Supports saved plan files (`-out=plan.tfplan`, `terraform apply plan.tfplan`) for CI/CD.

3. **AWS CDK synth/diff/deploy**  
   URL: https://docs.aws.amazon.com/cdk/v2/guide/ref-cli-cmd-diff.html  
   URL: https://docs.aws.amazon.com/cdk/v2/guide/ref-cli-cmd-deploy.html  
   URL: https://docs.aws.amazon.com/cdk/v2/guide/ref-cli-cmd-synth.html  
   Pattern: `cdk synth` generates CloudFormation templates, `cdk diff` compares stacks, `cdk deploy` applies changes. Supports `--change-set` flag for exact preview.

4. **Nomad job plan/run**  
   URL: https://developer.hashicorp.com/nomad/docs/commands/job/plan  
   URL: https://developer.hashicorp.com/nomad/docs/job-declare/create-job  
   Pattern: `nomad job plan <file>` dry-runs scheduler to show allocation changes, `nomad job run <file>` applies. Returns job modify index for concurrency safety.

5. **ArgoCD app diff**  
   URL: https://argo-cd.readthedocs.io/en/stable/user-guide/commands/argocd_app_diff/  
   Pattern: `argocd app diff APPNAME` performs diff against target and live state. Uses `diff` tool with `KUBECTL_EXTERNAL_DIFF` environment variable for customization.

### Container/Config Tools

6. **Docker Compose --dry-run**  
   URL: https://docs.docker.com/reference/cli/docker/compose/  
   URL: https://docs.docker.com/reference/cli/docker/compose/alpha/dry-run/  
   Pattern: Experimental `docker compose alpha dry-run -- <command>` executes in dry-run mode without applying changes. GitHub issue #8292 requested this for visibility.

7. **GitHub CLI gh api**  
   URL: https://cli.github.com/manual/gh_api  
   Pattern: `gh api <endpoint>` makes authenticated HTTP requests to GitHub API. Supports all CRUD operations with field-based requests, maintains API parity.

### Cloud Platform Tools

8. **Google Cloud gcloud infra-manager previews**  
   URL: https://docs.cloud.google.com/sdk/gcloud/reference/infra-manager/previews/create  
   URL: https://docs.cloud.google.com/infrastructure-manager/docs/preview-deployment  
   Pattern: `gcloud infra-manager previews create --preview-mode=PREVIEW_MODE` creates preview before deployment. Executes `terraform plan` internally.

---

## PATTERN EXTRACTION

### Command Grammar

All tools follow consistent structure:
```
<cli> <subcommand> <target-spec> [options]
<cli> <apply-subcommand> <target-spec> [options]
```

**Terse Imperative + Declarative:**
- **Imperative verbs:** plan, diff, apply, run, deploy, create, update
- **Declarative spec:** file path (`-f spec.yaml`), directory (`-k dir/`), or stdin (`-`)
- **Consistency:** same spec format works for preview AND apply

### Spec Diff/Apply Flow

**Mandatory two-step workflow:**

1. **Validation/Preview Phase:**
   ```
   kubectl diff -f spec.yaml        # Preview changes
   terraform plan                       # Create execution plan
   cdk diff my-stack                   # Compare stack states
   nomad job plan job.nomad           # Dry-run scheduler
   argocd app diff myapp              # Show live diff
   ```

2. **Apply Phase:**
   ```
   kubectl apply -f spec.yaml        # Apply changes
   terraform apply                      # Execute plan (with prompt)
   cdk deploy my-stack                  # Deploy stack
   nomad job run job.nomad            # Submit job
   ```

**Atomic Transaction Boundaries:**
- **Saved plan files:** Terraform `terraform plan -out=plan.tfplan`, then `terraform apply plan.tfplan`
- **Concurrency safety:** Nomad returns `JobModifyIndex` to check no drift between plan/run
- **Change sets:** AWS CDK `--change-set` creates CloudFormation change set for review
- **Field management:** Kubernetes server-side apply tracks field ownership to prevent conflicts

### Safety Checks

**Exit Codes:**
- `kubectl diff`: 0 = no diff, 1 = diff found, 1+ = error
- `argocd app diff`: 0 = no diff, 1 = diff found, 2 = error
- `terraform plan`: 0 = success, 1 = changes needed, 2 = error

**Default Behavior:**
- **Prompt by default:** Terraform apply prompts for confirmation (use `-auto-approve` to skip)
- **Dry-run validation:** All tools validate spec before preview
- **No hidden side effects:** Diff commands NEVER modify state

**Structured Errors:**
- Precise problem identification (what field, what validation)
- Concrete format specification (expected format)
- Practical example (how to fix)
- Documentation reference (URL for more info)

---

## FILE-LEVEL GITHUB EXAMPLES

### 1. Kubernetes Dry-Run Implementation
**Repository:** kubernetes/kubernetes  
**File:** cmd/kubeadm/app/util/apiclient/dryrun.go  
**Permalink:** https://github.com/kubernetes/kubernetes/blob/master/cmd/kubeadm/app/util/apiclient/dryrun.go#L50-L60

```go
// DryRun is responsible for performing verbose dry-run operations
type DryRun struct {
    fakeClient    *fake.Clientset
    client        clientset.Interface
    dynamicClient dynamic.Interface
    writer      io.Writer
    marshalFunc func(runtime.Object, schema.GroupVersion) ([]byte, error)
}

// Log actions, use fake client store for non-GET/LIST,
// attempt real GET/LIST for validation
```

**Pattern:** Fake client pattern for safe dry-run operations.

### 2. Terraform Diff-to-Apply Pipeline
**Repository:** hashicorp/terraform  
**File:** internal/terraform/node_resource_apply_instance.go  
**Permalink:** https://github.com/hashicorp/terraform/blob/main/internal/terraform/node_resource_apply_instance.go#L216-L225

```go
// Get saved diff for apply
diffApply, err := n.readDiff(ctx, providerSchema)
if diags.HasErrors() {
    return diags
}

// We don't want to do any destroys
if diffApply == nil || diffApply.Action == plans.Delete {
    return diags
}
destroy := (diffApply.Action == plans.Delete || diffApply.Action.IsReplace())
```

**Pattern:** Read diff from plan file, validate action type before execution.

### 3. Kubernetes Diff Flag Propagation
**Repository:** kubernetes/kubernetes  
**File:** cmd/kubeadm/app/cmd/init.go  
**Permalink:** https://github.com/kubernetes/kubernetes/blob/master/cmd/kubeadm/app/cmd/init.go#L56-L65

```go
type initOptions struct {
    cfgPath                 string
    skipTokenPrint          bool
    dryRun                  bool  // ← Standard flag across commands
    kubeconfigDir           string
    kubeconfigPath          string
    featureGatesString      string
    ignorePreflightErrors   []string
}
```

**Pattern:** Consistent `dryRun` flag across all subcommands.

---

## MUST-HAVE PATTERNS (Task 13/14)

### 1. Separate Preview/Apply Commands
```bash
# Preview changes
cli diff spec.yaml          # Show what would change
cli plan spec.yaml          # Show execution plan

# Apply changes
cli apply spec.yaml          # Execute changes (with prompt)
cli apply spec.yaml -y        # Execute without prompt (for automation)
```

**Why:** Explicit two-step prevents accidents, enables CI/CD automation with `-y` flag.

### 2. Dry-Run Validation
```bash
# Validate spec without modifying state
cli validate spec.yaml       # Check syntax/semantics
cli diff spec.yaml           # Preview diff (no changes)
```

**Why:** Early error detection, supports development workflow.

### 3. Structured Diff Output
```
diff -u -N /tmp/LIVE-123/apps.v1.Deployment.default.myapp \
             /tmp/MERGED-456/apps.v1.Deployment.default.myapp
--- /tmp/LIVE-123/...
+++ /tmp/MERGED-456/...
@@ -6,7 +6,7 @@
   spec:
     containers:
     - name: myapp
-      image: myapp:1.0.0
+      image: myapp:1.1.0
```

**Why:** Standard diff format is universally understood, toolable.

### 4. Exit Code Semantics
```python
# Exit codes
0: No changes / validation passed
1: Changes found (or diff non-zero)
2: Error occurred
```

**Why:** Enables shell scripting and CI/CD automation.

### 5. API 1:1 Parity
```python
# Use same validation logic for CLI and API
def validate_spec(spec: dict) -> ValidationResult:
    """Shared validation function"""
    # Same logic for API and CLI
    # CLI calls this before apply
    # API calls this on POST /spec
    pass

# CLI
def cmd_apply(spec_path: str):
    spec = load_spec(spec_path)
    result = validate_spec(spec)  # ← Reuse
    if not result.valid:
        print_error(result)
        sys.exit(2)
    apply_spec(spec)

# API
@app.post("/spec")
def api_apply(spec: dict):
    result = validate_spec(spec)  # ← Reuse
    if not result.valid:
        return error_response(result)
    apply_spec(spec)
    return success_response()
```

**Why:** Single source of truth, no CLI/API drift.

---

## NICE-TO-HAVE EXTRAS

### 1. Saved Plan Files
```bash
# Save plan, apply later
cli plan spec.yaml -out plan.json
cli apply plan.json          # Replays saved plan
```

**Benefit:** Supports review workflows, stores intent.

### 2. Concurrency Safety (Job Modify Index)
```bash
# Check for drift between plan and apply
plan_output=$(cli plan spec.yaml --output json)
modify_index=$(echo "$plan_output" | jq '.modifyIndex')
cli apply spec.yaml --check-index="$modify_index"
```

**Benefit:** Prevents race conditions in team environments.

### 3. Field-Level Ownership Tracking
```yaml
# Server-side apply tracks field owners
metadata:
  annotations:
    kubectl.kubernetes.io/last-applied-configuration: "..."
```

**Benefit:** Enables collaborative configuration, detects conflicts.

### 4. Local Manifest Comparison
```bash
# Compare local to remote without remote access
argocd app diff myapp --local manifests/
```

**Benefit:** Offline development, air-gapped environments.

### 5. Custom Diff Tools
```bash
# Use custom diff (colordiff, icdiff)
export KUBECTL_EXTERNAL_DIFF="colordiff -N -u"
kubectl diff -f spec.yaml
```

**Benefit:** Enhanced readability, integration with user preferences.

---

## AVOID (Anti-Patterns)

### 1. Wizard-Like Interactive Flows
```
# ❌ DON'T: Multi-step interactive prompts
$ cli configure
? Enter simulation name: my-sim
? Add process? Yes
? Process type: UnitProcess
? Process ID: p1
? Add another process? No
```

**Why:** Not scriptable, hard to automate, breaks KISS.

### 2. Opaque DSLs
```
# ❌ DON'T: Custom domain-specific language
simulation "my-sim" {
  flow [p1 -> j1 -> p2]
  valve v1 = open(0.5)
}
```

**Why:** Reduces debuggability, users need to learn new syntax, harder to validate.

### 3. Hidden Side Effects
```
# ❌ DON'T: Apply command that modifies state before confirmation
$ cli apply spec.yaml
# ... applies changes immediately, no preview, no prompt
```

**Why:** Dangerous, no safety net, violates dry-run-first principle.

### 4. Mixed CLI/API Logic
```
# ❌ DON'T: Separate validation for CLI and API
# CLI validation
def cli_validate(spec):  # ← One implementation
    return check_fields(spec)

# API validation
def api_validate(spec):  # ← Different implementation
    return check_fields(spec) and check_permissions(spec)  # Drift!
```

**Why:** Double maintenance, CLI/API behave differently.

---

## KISS RECOMMENDATIONS FOR THIS PROJECT

### Minimal Pattern Subset (Must-Have Only)

1. **Two-command structure:**
   ```bash
   cli sim diff spec.yaml          # Preview changes
   cli sim apply spec.yaml          # Apply changes
   ```

2. **Consistent flags:**
   ```bash
   --dry-run                  # Show what would change (for apply)
   --yes, -y                  # Skip confirmation (for automation)
   --output=json|yaml          # Structured output
   ```

3. **Exit codes:**
   ```python
   0: Success (no changes for diff)
   1: Changes found (for diff)
   2: Validation error
   3: Apply error
   ```

4. **Shared validation:**
   ```python
   # Single validate() function for CLI and API
   # CLI: validate() → print errors → exit
   # API: validate() → return HTTP 400
   ```

5. **Structured errors:**
   ```json
   {
     "error": "Validation failed",
     "field": "spec.processes[0].ports[0].max_flow",
     "message": "max_flow must be >= 0",
     "current": -5,
     "expected": "0 <= value <= 100",
     "example": {"max_flow": 10.5},
     "documentation": "https://..."
   }
   ```

### Deferred (Nice-to-Have, Out of Scope)

- Saved plan files (`-out plan.json`, `apply plan.json`)
- Concurrency safety with modify indices
- Field-level ownership tracking (server-side apply)
- Custom diff tool support
- Local manifest comparison mode

---

## BACKEND API PARITY GUIDANCE

### 1:1 Mapping Principle

**CLI commands map directly to API endpoints:**
```
CLI Command                    API Endpoint
-----------                 -------------
cli sim diff spec.yaml         GET /sim/{id}/diff?spec={spec}
cli sim apply spec.yaml        POST /sim/{id}?spec={spec}
cli sim validate spec.yaml      POST /sim/validate
cli sim get <id>            GET /sim/{id}
```

**Same payload format:**
```yaml
# CLI: cli sim apply spec.yaml
spec:
  processes:
    - id: p1
      type: UnitProcess
      ports:
        - id: out
          max_flow: 10.0

# API: POST /sim/{id} (same YAML)
spec:
  processes:
    - id: p1
      type: UnitProcess
      ports:
        - id: out
          max_flow: 10.0
```

### Avoid Hidden Side Effects

**CLI should NOT:**
- Auto-create resources if they don't exist (unless explicit `--create` flag)
- Modify state without user confirmation (unless `-y` flag)
- Apply partial specs without validation

**CLI SHOULD:**
- Validate spec before any API call
- Show diff before apply (use `--yes` to skip)
- Return same HTTP error codes from API to CLI

---

## Task 1 implementation notes (2026-02-24)
- Added `src/modular_simulation/connection/domain_contracts.py` with strict pydantic contracts for `UnitProcess`, `JunctionProcess`, `Port`, `ConnectionLine`, `ResistanceConfig`, `ValveConfig`, `SensorBinding`, `ControllerBinding`, and command envelope (`idempotency_key`, `expected_revision`, `metadata`, `mutations`).
- Junctions now map through the same unit-process path via `JunctionProcess.as_unit_process()` and `UnitProcess.process_kind="junction"`, while still supporting existing `JunctionNode` through `UnitProcess.as_junction_node()`.
- Integrated envelope validation into `ConnectionNetwork.queue_reconfiguration` using `validate_command_envelope(...)` without changing queue/barrier ordering semantics.
- Extended queued reconfiguration payload persistence in `runtime_persistence.py` to include `expected_revision` and `metadata` alongside `request_id`, `idempotency_key`, and `mutations`.

---

## AUTHORITATIVE EXAMPLES: Deterministic Rollback & Atomicity Testing in Python Systems
**Research Date:** 2026-02-24  
**Task:** Gather authoritative examples for deterministic rollback and atomicity testing in Python systems, with focus on patterns applicable to command-processing pipelines and stateful runtimes.

### 1. Django Transaction Tests - Proven Rollback Patterns with State Verification
**URL:** https://github.com/django/django/blob/e84dc87/tests/transactions/tests.py  
**Relevance:** Production-proven framework with comprehensive transaction rollback tests using deterministic state verification.

**Pattern:** Before/after state verification with exception-based rollback
```python
# File: tests/transactions/tests.py:80-85
def test_rollback(self):
    with self.assertRaisesMessage(Exception, "Oops"):
        with transaction.atomic():
            Reporter.objects.create(first_name="Haddock")
            raise Exception("Oops, that's his last name")
    # ← Critical: Verify state is unchanged after rollback
    self.assertSequenceEqual(Reporter.objects.all(), [])
```

**Key Pattern:**
1. Wrap operation in `transaction.atomic()` context
2. Raise exception to trigger rollback
3. Assert state matches initial condition (empty list)
4. No external infrastructure - uses in-memory assertions

**Why it works for ModularSimulator:**
- Direct assertion on internal state (`network._compiled`, `network._process_specs`)
- Exception-based rollback matches existing `pytest.raises(RuntimeError)` pattern
- Deterministic fixture setup with helper functions (`_network()`, `_valid_system()`)

---

### 2. Django Nested Transaction Tests - Multi-Level Rollback Patterns
**URL:** https://github.com/django/django/blob/e84dc87/tests/transactions/tests.py#L114-L123  
**Relevance:** Demonstrates nested transaction semantics with savepoint rollback isolation.

**Pattern:** Nested rollback preserves outer transaction state
```python
# File: tests/transactions/tests.py:114-123
def test_nested_rollback_rollback(self):
    with self.assertRaisesMessage(Exception, "Oops"):
        with transaction.atomic():  # Outer transaction
            Reporter.objects.create(last_name="Tintin")
            with self.assertRaisesMessage(Exception, "Oops"):
                with transaction.atomic():  # Inner savepoint
                    Reporter.objects.create(first_name="Haddock")
                raise Exception("Oops, that's his last name")
            raise Exception("Oops, that's his first name")
    # ← Both writes rolled back, state unchanged
    self.assertSequenceEqual(Reporter.objects.all(), [])
```

**Key Pattern:**
- Nested `transaction.atomic()` creates savepoints
- Exception at any level rolls back all changes
- Final state assertion proves isolation

**Alignment with ModularSimulator:**
- Matches barrier apply semantics (Queued → Staged → Applied/Skipped/RolledBack)
- Supports batch mutation testing with partial failure rollback
- Demonstrates deterministic queueing with poison-at-head blocking

---

### 3. ModularSimulator Existing Pattern - Snapshot Equality Assertions
**URL:** tests/connection/test_runtime_mutation_contract.py:146-L174  
**Relevance:** Current best practices already demonstrate deterministic rollback testing with state snapshot comparison.

**Pattern:** Before/after snapshot equality proves atomicity
```python
# File: tests/connection/test_runtime_mutation_contract.py
def test_invalid_mutation_batch_rolls_back_graph_runtime_and_time() -> None:
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)

    _ = network.queue_reconfiguration(
        {
            "operation": "batch_update",
            "mutations": [
                {
                    "operation": "add_connection",
                    "source": "unknown_source",  # ← Invalid reference
                    "target": "reactor.feed",
                }
            ],
        }
    )
    before_failed_commit = network.save_runtime_snapshot()  # ← Capture BEFORE

    with pytest.raises(
        RuntimeError,
        match=(
            "reconfiguration transaction rollback: request 'rq_0001' mutation 1 failed: "
            "unknown endpoint node 'unknown_source'"
        ),
    ):
        _ = network.step(macro_step_time_s=1.0)

    after_failed_commit = network.save_runtime_snapshot()  # ← Capture AFTER
    assert after_failed_commit == before_failed_commit  # ← Critical: State unchanged
    assert network._compiled is not None
    assert network._compiled.graph_revision == "graph_rev_0001"
    assert network._next_revision_index == 2
```

**Key Pattern:**
1. `save_runtime_snapshot()` captures full state before operation
2. Execute operation with expected exception
3. Capture state after failure
4. Equality assertion proves no side effects
5. Additional invariants (graph_revision, next_revision_index) verify internal consistency

**Why this is the gold standard:**
- Direct access to internal state (`network._compiled`, `network._next_revision_index`)
- Deterministic snapshot format (dict with graph_revision, next_edge_index, next_reconfiguration_index, etc.)
- Matches Task 2 requirement: "proving atomic commit and rollback behavior"

---

### 4. psycopg Transaction Tests - Database-Level Rollback Patterns
**URL:** https://github.com/psycopg/psycopg/blob/master/tests/test_pipeline.py#L519-L523  
**Relevance:** PostgreSQL Python driver demonstrates transaction rollback with division-by-zero failure injection.

**Pattern:** Exception in transaction triggers automatic rollback
```python
# File: tests/test_pipeline.py:519-523
def test_rollback_transaction(conn):
    conn.set_autocommit(True)
    with pytest.raises(e.DivisionByZero):
        with conn.pipeline():
            with conn.transaction():
                cur = conn.execute("select 1 / %s", [0])
    # ← Transaction automatically rolled back on exception
```

**Key Pattern:**
- Failure injection via invalid operation (division by zero)
- Context manager guarantees rollback on exception
- No explicit rollback needed - automatic

**Alignment with ModularSimulator:**
- Failure injection patterns (invalid endpoint, unknown subsystem reference)
- Automatic rollback via barrier semantics
- Exception-based verification (`pytest.raises`)

---

### 5. Flask-SQLAlchemy Auto-Rollback - Fixture-Based Isolation
**URL:** https://jackevans.bearblog.dev/auto-rollback-database-transactions-with-flask-sqlalchemy-and-pytest  
**Relevance:** Production pattern for per-test transaction isolation with automatic rollback.

**Pattern:** Fixture wrapper guarantees clean state per test
```python
# File: conftest.py (from blog)
@pytest.fixture(scope="function")
def database(app_ctx):
    engines = db.engines
    engine = engines[None]

    connection = engine.connect()
    transaction = connection.begin()

    session_factory = sessionmaker(bind=connection)
    session = session_factory()

    db.session = session
    yield session

    # ← Automatic rollback after test
    transaction.rollback()
    connection.close()
```

**Key Pattern:**
- Yield fixture provides isolated session
- Automatic rollback in teardown (even on test failure)
- No manual cleanup needed

**Alignment with ModularSimulator:**
- Each test gets fresh network state via `_network()` fixture
- Barrier semantics ensure mutations only apply at tick boundaries
- No persistent state between tests (single-process deterministic runtime)

---

### 6. Pytest Fixture Factories - Flexible, Maintainable Test Data
**URL:** https://python.plainenglish.io/pytest-fixture-factories-the-secret-to-writing-flexible-maintainable-tests  
**Relevance:** Modern pytest pattern for creating flexible test data without duplication.

**Pattern:** Factory fixture returns callable for test data creation
```python
# From blog example
@pytest.fixture
def make_customer():
    def make(
        first_name: str = "Cosmo",
        last_name: str = "Kramer",
        email: str = "test@example.com",
        **rest
    ):
        customer = Customer(
            first_name=first_name, last_name=last_name, email=email, **rest
        )
        return customer
    return make

def test_customer(make_customer):
    customer_1 = make_customer(first_name="Elaine", last_name="Benes")
    assert customer_1.first_name == "Elaine"
    customer_2 = make_customer()
    assert customer_2.first_name == "Cosmo"  # ← Default value
```

**Key Pattern:**
- Fixture returns factory function, not data
- Default values for common cases
- Override specific parameters per test
- Eliminates duplication across tests

**Alignment with ModularSimulator:**
- Existing `_network()` and `_valid_system()` helper functions follow this pattern
- Can be formalized as fixtures in `tests/connection/conftest.py`
- Supports parameterized test scenarios (e.g., different topologies)

---

### 7. Pydantic inline-snapshot - State Snapshot Testing
**URL:** https://pydantic.dev/articles/inline-snapshot  
**Relevance:** Modern Python library for snapshot testing with automatic updates and diff output.

**Pattern:** Inline snapshot assertion with auto-update workflow
```python
from inline_snapshot import snapshot

def test_user_creation():
    user = create_user(id=123, name="test_user")
    # ← First run: pytest --inline-snapshot=fix updates this
    assert user.dict() == snapshot({
        "id": 123,
        "name": "test_user",
        "status": "active"
    })
```

**Key Pattern:**
- Write test with empty snapshot: `assert actual == snapshot({})`
- Run `pytest --inline-snapshot=fix` to auto-fill expected value
- Review and commit snapshot
- Future runs verify no drift

**Alignment with ModularSimulator:**
- Alternative to manual `save_runtime_snapshot()` assertions
- Useful for complex state comparisons (e.g., full topology dict)
- Maintains test readability with inline expected values

**Note:** For Task 2, stick to existing `save_runtime_snapshot()` pattern (KISS). Inline-snapshot adds dependency for minimal benefit given deterministic runtime state.

---

### 8. Failure Injection Patterns - Negative Testing Strategies
**URL:** https://medium.com/delivus/negative-testing-in-python-web-applications-with-pytest-db0304234638  
**Relevance:** Systematic approach to testing error paths and edge cases.

**Pattern:** Parametrized tests cover multiple failure scenarios
```python
# From blog example
@pytest.mark.parametrize("invalid_data,expected_error", [
    ({"email": "not-an-email"}, "Invalid email format"),
    ({"email": "test@example.com", "password": "short"}, "Password too short"),
    ({"name": "a"*300}, "Name too long"),
])
def test_create_user_validation(client, invalid_data, expected_error):
    response = client.post("/api/user", json=invalid_data)
    assert response.status_code == 400
    assert expected_error in response.json()["error"]
```

**Key Pattern:**
- `pytest.mark.parametrize` for multiple test cases
- Cover validation errors, edge cases, invalid inputs
- Clear error message verification

**Alignment with ModularSimulator:**
- Existing tests already demonstrate multiple failure types:
  - `test_invalid_mutation_batch_rolls_back` - unknown endpoint
  - `test_invalid_scope_operation_is_rejected` - unsupported operation
  - `test_unresolved_cross_subsystem_reference_rolls_back` - subsystem reference
- Can extend with parametrization for systematic coverage

---

## RECOMMENDED ASSERTION PATTERN FOR TASK 2 TESTS

### Core Pattern: Snapshot Equality with Exception Verification

```python
def test_atomic_commit_and_rollback_on_failure():
    """Prove that failed mutations roll back completely without state drift."""
    # 1. Deterministic setup
    runtime = ConnectionRuntimeOrchestrator()
    network = _network(runtime)
    
    # 2. Capture baseline state
    before_state = network.save_runtime_snapshot()
    assert before_state["graph_revision"] == "graph_rev_0001"
    assert before_state["next_revision_index"] == 2
    
    # 3. Queue mutation with failure point
    request_id = network.queue_reconfiguration({
        "operation": "batch_update",
        "mutations": [
            {"operation": "add_process", "process_id": "p1"},
            {"operation": "add_connection", "source": "invalid"},  # ← Failure injection
        ]
    })
    
    # 4. Verify exception and rollback
    with pytest.raises(
        RuntimeError,
        match="reconfiguration transaction rollback: request '.*' mutation 2 failed: .*"
    ):
        network.step(macro_step_time_s=1.0)
    
    # 5. Prove state unchanged (atomicity)
    after_state = network.save_runtime_snapshot()
    assert after_state == before_state
    assert after_state["graph_revision"] == "graph_rev_0001"
    assert after_state["next_revision_index"] == 2
    
    # 6. Verify invariants
    assert network._compiled is not None
    assert "p1" not in network._process_specs  # No partial apply
    assert tuple(item.request_id for item in network.queued_reconfigurations) == (request_id,)
```

### Pattern Breakdown:

| Step | Purpose | Assertion |
|------|-----------|------------|
| 1. Deterministic setup | Isolate test from external state | Fresh network via `_network()` |
| 2. Capture baseline | Prove initial state | Snapshot + invariants |
| 3. Failure injection | Trigger rollback path | Invalid reference/operation |
| 4. Exception verification | Confirm rollback triggered | `pytest.raises()` with message match |
| 5. State equality | Prove atomicity (no partial apply) | `after == before` |
| 6. Invariant verification | Confirm internal consistency | Revision indices, queues |

### Key Principles:

1. **No timing-based assertions:** All checks are deterministic state comparisons
2. **No external infrastructure:** Uses in-memory runtime state only
3. **Explicit failure injection:** Known failure point triggers rollback
4. **Snapshot equality:** Single assertion proves complete rollback
5. **Invariant checks:** Additional assertions verify internal consistency

---

## PRACTICAL ANTI-PATTERNS TO AVOID

### 1. ❌ Timing-Based Assertions
```python
# DON'T: Relies on timing, flaky under load
time.sleep(0.1)
assert network._compiled is not None
```

**Why:** Flaky under varying system load, violates determinism
**Fix:** Use explicit state checks (`assert network._compiled is not None`)

---

### 2. ❌ External Infrastructure Dependencies
```python
# DON'T: Requires database, file system, network
@pytest.fixture
def db_connection():
    conn = psycopg2.connect("...")
    yield conn
    conn.close()
```

**Why:** Breaks isolation, introduces flakiness, violates KISS
**Fix:** Use in-memory state via `_network()` helper

---

### 3. ❌ Broad Refactors for Test Changes
```python
# DON'T: Change production code to make tests pass
def step(macro_step_time_s: float):
    if "test" in sys.argv:  # ← Test-specific code path
        return self._internal_step_for_test(macro_step_time_s)
    return self._real_step(macro_step_time_s)
```

**Why:** Technical debt, production code has test dependencies
**Fix:** Test public API, use existing snapshot patterns

---

### 4. ❌ Flaky Randomness Without Seeding
```python
# DON'T: Random IDs cause non-deterministic behavior
def test_idempotency():
    request_id = str(uuid.uuid4())  # ← Different each run
    # Test fails randomly on UUID collision
```

**Why:** Tests fail intermittently, hard to reproduce
**Fix:** Use deterministic ID generation (`network.queue_reconfiguration()` returns `rq_0001`)

---

### 5. ❌ Implicit State Changes Without Verification
```python
# DON'T: Assumes mutation succeeded without checking
def test_mutation():
    network.queue_reconfiguration({"operation": "add_process", ...})
    network.step(macro_step_time_s=1.0)
    # ← Missing assertion! What if mutation failed silently?
```

**Why:** False positives, doesn't verify atomicity
**Fix:** Capture before/after snapshots, assert equality

---

### 6. ❌ Over-Mocking with Stubs
```python
# DON'T: Mock internal implementation details
def test_rollback(monkeypatch):
    monkeypatch.setattr(network, "_apply_mutation", lambda: None)  # ← Suppresses real logic
    network.step(macro_step_time_s=1.0)
    assert ...  # Doesn't test real rollback behavior
```

**Why:** Tests mock, not production behavior
**Fix:** Test real code with failure injection (invalid references, unsupported operations)

---

## CONCISE PATTERN LIST MAPPABLE TO `tests/connection/`

### 1. Deterministic Fixture Pattern
```python
# tests/connection/conftest.py
@pytest.fixture
def network(runtime_orchestrator: ConnectionRuntimeOrchestrator | None = None) -> ConnectionNetwork:
    """Deterministic network fixture with valid hydraulic system."""
    network = ConnectionNetwork(
        compile_lifecycle=HydraulicCompileLifecycle(),
        hydraulic_system_builder=lambda topology: _valid_system(),
        runtime_orchestrator=runtime_orchestrator,
    )
    network.add_process("reactor", inlet_ports=("feed",), outlet_ports=("product",))
    network.add_boundary_source("feed_boundary")
    network.add_boundary_sink("product_boundary")
    network.connect("feed_boundary", "reactor.feed")
    network.connect("reactor.product", "product_boundary")
    _ = network.compile()
    return network
```

### 2. Snapshot Equality Assertion Pattern
```python
def test_rollback_proves_atomicity(network):
    before_snapshot = network.save_runtime_snapshot()
    
    # Execute mutation with failure
    request_id = network.queue_reconfiguration({...})
    
    with pytest.raises(RuntimeError, match="transaction rollback"):
        network.step(macro_step_time_s=1.0)
    
    after_snapshot = network.save_runtime_snapshot()
    assert after_snapshot == before_snapshot  # ← Atomicity proven
```

### 3. Failure Injection Pattern
```python
@pytest.mark.parametrize("mutation,expected_error", [
    ({"operation": "add_connection", "source": "invalid"}, "unknown endpoint"),
    ({"operation": "install_subsystem_sensor", "scope": "subsystem"}, "unsupported operation"),
    ({"operation": "add_connection", "source": "subsystem_a/reactor"}, "unknown subsystem"),
])
def test_failure_injection_rolls_back(network, mutation, expected_error):
    before_snapshot = network.save_runtime_snapshot()
    
    network.queue_reconfiguration({"operation": "batch_update", "mutations": [mutation]})
    
    with pytest.raises(RuntimeError, match=expected_error):
        network.step(macro_step_time_s=1.0)
    
    assert network.save_runtime_snapshot() == before_snapshot
```

### 4. Idempotency Verification Pattern
```python
def test_idempotency_key_prevents_duplicate_state(network):
    # First mutation succeeds
    rq1 = network.queue_reconfiguration({
        "operation": "add_boundary_sink",
        "boundary_id": "sink_a",
        "idempotency_key": "sink-key",
    })
    result = network.step(macro_step_time_s=1.0)
    assert result.barrier_reconfiguration.applied_request_ids == ("rq_0001",)
    
    # Replay with same key is skipped
    rq2 = network.queue_reconfiguration({
        "operation": "add_boundary_sink",
        "boundary_id": "sink_a",
        "idempotency_key": "sink-key",  # ← Same key
    })
    result = network.step(macro_step_time_s=1.0)
    assert result.barrier_reconfiguration.skipped_request_ids == ("rq_0002",)
    assert "sink_a" in network._boundary_specs  # Single sink, not duplicate
```

### 5. Batch Transaction Pattern
```python
def test_batch_transaction_all_or_none(network):
    before_snapshot = network.save_runtime_snapshot()
    
    network.queue_reconfiguration({
        "operation": "batch_update",
        "mutations": [
            {"operation": "add_process", "process_id": "p1"},
            {"operation": "add_process_port", "process_id": "p1", "port_name": "inlet"},
            {"operation": "add_connection", "source": "invalid"},  # ← Failure point
        ]
    })
    
    with pytest.raises(RuntimeError):
        network.step(macro_step_time_s=1.0)
    
    after_snapshot = network.save_runtime_snapshot()
    assert after_snapshot == before_snapshot  # All mutations rolled back
    assert "p1" not in network._process_specs  # No partial state
```

---

## KISS-COMPATIBLE RECOMMENDATIONS

### Adopt Immediately (Task 2):

1. **Snapshot Equality Pattern**: `assert after == before` proves atomicity
2. **Exception-Based Verification**: `pytest.raises(RuntimeError, match=...)` confirms rollback triggered
3. **Deterministic Fixtures**: `_network()` helper provides fresh, isolated state
4. **Failure Injection**: Invalid references trigger rollback paths
5. **Invariant Assertions**: Check graph_revision, next_revision_index, queues

### Defer (Out of Scope):

1. **inline-snapshot library**: Adds dependency, existing `save_runtime_snapshot()` sufficient
2. **Hypothesis stateful testing**: Overkill for deterministic runtime with known mutation paths
3. **External database**: Violates KISS, in-memory state sufficient
4. **Complex fixture factories**: Existing `_network()` pattern sufficient
5. **Parametrized failure injection**: Add only if coverage gaps identified

---

## VERIFICATION CRITERIA FOR TASK 2 TESTS

Each rollback test must verify:

1. ✅ **Atomicity**: `after_snapshot == before_snapshot` proves complete rollback
2. ✅ **Exception**: `pytest.raises(RuntimeError, match="transaction rollback")` confirms failure path
3. ✅ **Invariants**: graph_revision unchanged, next_revision_index unchanged
4. ✅ **No Partial State**: Failed mutation not partially applied (e.g., no orphaned ports)
5. ✅ **Queue State**: Failed request remains in queue for poison-at-head blocking
6. ✅ **Determinism**: Same input produces same output (no random IDs, no timing)

---


## Task 2 implementation notes (2026-02-24)
- Refactored ConnectionRuntimeOrchestrator._apply_reconfiguration_batch into explicit lifecycle stages: parse (_parse_lifecycle_stage), semantic validate (_semantic_validate_lifecycle_stage), invariant validate (_validate_expected_revision_invariant + _validate_idempotency_invariant), compile preview (_compile_preview_lifecycle_stage), and atomic rollback wrapper.
- Enforced expected_revision deterministically against the active compiled graph revision before any mutation staging; mismatches now fail with rollback and zero state mutation.
- Added dedicated tests tests/connection/test_transaction_atomicity.py and tests/connection/test_idempotency_semantics.py covering single-op and explicit batch envelopes, idempotency replay/poison behavior, expected-revision mismatch handling, and mixed topology+unsupported control mutation rollback.

## Task 5 implementation notes (2026-02-24)
- Added compile-time resistance resolver in `src/modular_simulation/connection/hydraulic_compile.py` with `ResolvedLineResistance` provenance (`derived` vs `manual_override`), deterministic manual precedence, and optional `fluid_factor` scaling.
- Added structured deterministic diagnostics for invalid line geometry/manual override/fluid factor via `GraphCompileError` + `GraphCompileDiagnostic` (`invalid_line_geometry`, `invalid_manual_override`, `invalid_fluid_factor`).
- Tightened `ResistanceConfig` geometry contract so `radius_m` and `length_m` are always required in `src/modular_simulation/connection/domain_contracts.py`.
- Added deterministic tests in `tests/connection/test_line_resistance_models.py` and extended `tests/connection/test_graph_compile_validation.py` for invalid-geometry compile diagnostics.

## Task 4 implementation notes (2026-02-24)
- Fixed connected-plant deferred queue merge at runtime barrier by deterministically merging `post_step_queue` and `deferred_until_next_barrier` using `request_id` FIFO ordering; this preserves acceptance order even when barrier apply rolls back.
- Added focused tick-boundary tests in `tests/connection/test_tick_boundary_reconfiguration.py` covering (1) reconfiguration accepted during a running tick becoming visible only on the next barrier and (2) FIFO queue stability across mixed command envelopes after rollback.
- Verified deterministic behavior and type safety with UV-only pytest targets and mypy checks required by Task 4.

## Task 6 implementation notes (2026-02-24)
- Added compile/runtime valve modulation primitives in `src/modular_simulation/connection/hydraulic_compile.py`: `CompiledValveHydraulicState`, `compile_valve_hydraulic_state`, deterministic valve-to-effective-resistance mapping, and `apply_valve_commands_to_compiled_graph` for safe command application without solver contract changes.
- Integrated runtime command path in `src/modular_simulation/connection/runtime.py` with mutation `set_valve_open_fraction`; valve-only commands stage at barrier and do not force full graph recompilation, preserving FIFO rollback semantics and deterministic macro-step behavior.
- Extended `src/modular_simulation/connection/network.py` with staged valve command buffering (`stage_valve_open_fraction_command`, `consume_pending_valve_open_fraction_commands`) plus rollback-safe snapshot/restore of pending valve commands.
- Added deterministic integration coverage in `tests/connection/test_valve_hydraulic_integration.py` for flow/resistance response to valve actuation and out-of-range command rejection with rollback/no runtime corruption.
## Task 7 implementation notes (2026-02-24)
- Added `src/modular_simulation/connection/reconfiguration_api.py` with `DynamicUnitPortReconfigurationApi`, a transaction-only API that queues unit/junction add-remove and inlet/outlet add-remove mutations via `ConnectionNetwork.queue_reconfiguration(...)` (no direct mutable bypass path).
- Kept junction configuration on the same unit-process contract family by accepting both `UnitProcess` and `JunctionProcess`; junction input is normalized through `JunctionProcess.as_unit_process()` and applied through `add_process`/`remove_unit` mutation paths.
- Added pre-queue active-connection guard for destructive port removal (`remove_inlet`/`remove_outlet`) using `list_incident_edge_ids(...)` so connected ports fail early with deterministic no-queue/no-state mutation behavior.
- Extended runtime mutation dispatch aliases in `src/modular_simulation/connection/runtime.py` for `add_unit`, `add_junction`, `add_inlet`, `add_outlet`, `remove_inlet`, and `remove_outlet`, all routed through existing barrier transaction lifecycle and invariant validation flow.
- Extended destructive-edit classification in `src/modular_simulation/connection/invariant_validator.py` so new remove aliases map into existing `remove_unit` / `remove_port` policy classes.
- Added deterministic coverage in `tests/connection/test_dynamic_unit_port_api.py` for (1) add unit + ports + junction success through barrier commit and (2) connected-port removal rejection with zero queue/state mutation.

## Task 8 implementation notes (2026-02-24)
- Added `DynamicConnectionLineReconfigurationApi` in `src/modular_simulation/connection/reconfiguration_api.py` with transaction-only operations for `connect_line` / `disconnect_line` plus line geometry, derived/manual resistance mode, and valve attachment commands.
- Extended runtime mutation dispatch in `src/modular_simulation/connection/runtime.py` with `connect_line`, `disconnect_line` aliases and new line config operations (`configure_line_geometry`, `configure_line_resistance`, `attach_line_valve`) routed through the existing barrier transaction lifecycle.
- Added per-line hydraulic config state in `src/modular_simulation/connection/network.py` and wired compile integration to reuse Task 5/6 primitives (`resolve_line_resistance`, `compile_valve_hydraulic_state`) so compiled hydraulic equations and valve runtime state reflect line config updates deterministically.
- Added endpoint direction compatibility validation in `ConnectionNetwork.connect(...)` (`source` must be outlet, `target` inlet) with deterministic rollback/no-side-effect behavior when queued through transactions.
- Added `tests/connection/test_connection_line_config_api.py` covering (1) successful connect + resistance/valve config flow reflected in compiled runtime state and (2) invalid endpoint direction rejection with unchanged revision/snapshot.

## Task 10 implementation notes (2026-02-24)
- Added `ControllerRuntimeWiringApi` in `src/modular_simulation/components/control_system/runtime_wiring_api.py` for transaction-only controller lifecycle commands: `create_controller`, `bind_controller_input`, `bind_controller_output`, `configure_controller_mode`, and `activate_controller`.
- Extended runtime dispatch in `src/modular_simulation/connection/runtime.py` with controller-only mutation routing plus zero-hydraulic-impact guardrails and deterministic pre-barrier validation (controller mutations do not trigger recompilation).
- Implemented controller mutation engine in `src/modular_simulation/framework/system.py` with rollback snapshots, staged controller definitions, activation-time validation of measured/calculated signal tags, actuator existence checks, compatibility checks, and controlled runtime attachment to existing control elements.
- Added deterministic controller wiring tests in `tests/components/test_controller_wiring_api.py` covering successful PID activation/wiring and activation rollback on unresolved signal tags.

## Task 11 implementation notes (2026-02-24)
- Extended `save_runtime_snapshot_contract` to emit a unified checkpoint envelope with explicit schema marker/version, top-level graph revision, package metadata, embedded snapshot state, pending command journal mirror, and integrity checksum.
- Added deterministic integrity validation plus strict same-version restore guard (`CHECKPOINT_VERSION_MISMATCH`) before any mutable restore work, preserving rollback safety.
- Updated `System.save`/`System.load` to use the same envelope principles (package metadata + checksum + strict schema/version checks) and deterministic compatibility/integrity errors.
- Added `tests/persistence/test_checkpoint_same_version_guard.py` for same-version resume success and explicit version-mismatch rejection while asserting restore leaves runtime state unchanged.

## Task 12 implementation notes (2026-02-24)
- Added deterministic replay hash utilities in `src/modular_simulation/connection/runtime_persistence.py`: `runtime_replay_state_hash(...)` and `verify_runtime_replay_hashes(...)`.
- Replay hash payload includes canonicalized process runtime state, FIFO queued reconfiguration payloads, runtime counters, and compiled topology shape; hashing is delegated to `checkpoint_payload_checksum(...)` for stable key ordering and serialization.
- Added `tests/persistence/test_checkpoint_journal_replay_determinism.py` with (1) baseline vs checkpoint-resume selected-tick hash equality and (2) intentional tick-3 queue-order perturbation that deterministically raises a clear mismatch (`tick 3` included in error text).
- Verified with UV-only checks: replay determinism test, existing persistence guard/contract suites, and mypy on runtime persistence/runtime modules.
- 2026-02-25T04:41:39.168364 - initialized CLI bindings
- 2026-02-25T04:41:39.172358 - initialized CLI bindings
- 2026-02-25T04:41:39.175458 - initialized CLI bindings
- 2026-02-25T04:41:39.213820 - initialized CLI bindings

## Task 15 validation notes (2026-02-25)
- Strengthened revision-mismatch contract checks by asserting retry-oriented hint text and explicit expected/actual revision details in `tests/connection/test_error_catalog.py`.
- Added API vs CLI parity coverage for revision-mismatch diagnostics in `tests/cli/test_cli_error_mapping.py` so both interfaces emit the same `code`, `path`, and `revision` payload shape.
- Normalized persistence-side revision mismatch hint wording in `src/modular_simulation/connection/runtime_persistence.py` to include retry semantics.

## Task 16 implementation notes (2026-02-25)
- Aligned quality CI with local UV-only commands by switching `.github/workflows/ci.yml` to `uv run` for Ruff, Mypy (`--with mypy`), and targeted Pytest smoke/minimal checks.
- Tightened mypy suppressions from non-functional `exclude` pattern to narrow per-module overrides, and matched mypy's discovered module names (`measurables.process_model`, `plotting.time_series`) so `uv run --with mypy python -m mypy src` stays green without broad global muting.

## Task 17 implementation notes (2026-02-25)
- Filled the last missing acceptance gap by adding `tests/integration/test_dynamic_process_network_workflow.py` for deterministic end-to-end coverage: dynamic topology edits, line/valve config, sensor/controller runtime wiring, checkpoint save/restore, and replay-continuation hash parity.
- Hardened CLI mapping parity contracts in `tests/cli/test_cli_api_contract_mapping.py` with exact payload assertions for immediate commands and tx envelope commit semantics, plus explicit structured diagnostic assertions for invalid CLI arguments.
- Updated `tests/connection/test_destructive_edit_policies.py` to assert stable structured hard-fail policy fields (`"policy_mode":"hard_fail"`) instead of brittle hint-string text, keeping rollback semantics strict while matching current diagnostics output.
- Verified Task-17 required UV gates pass exactly: full suite target `206 passed` and failure-path matrix `38 passed, 157 deselected`.

## Task 18 implementation notes (2026-02-25)
- Added concise operator-first examples under `examples/dynamic_api_cli/` for command-path quickstart, spec-path quickstart, and valve+sensor+controller with API/CLI save-load-continue flow.
- Added `tests/integration/test_examples_smoke.py` with three scenario-focused smoke tests: quickstart two process, junction as unit plus control loop, and save-load-continue for API+CLI.
- Kept docs minimal and runnable by adding a dedicated `readme.md` section with UV commands that map directly to the new example scripts.

## Task docs alignment notes (2026-02-25)
- Updated documentation command examples to UV-first style (`uv run python ...`) for quickstart and connected-plant reference paths.
- Replaced stale `new_examples/...` references in example diagram notes with live `examples/...` paths.
- Added explicit `pytest -k` boolean-expression guidance in docs to prevent invalid space-only filter usage.
