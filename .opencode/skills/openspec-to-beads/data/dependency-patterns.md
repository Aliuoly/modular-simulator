# Smart Dependency Patterns

## Automatic Dependency Detection

### Pattern 1: Sequential Within A Planning Wave Group

**Rule:** When two tasks are clearly ordered within the same wave, the later task blocks on the earlier one.

```text
Task 1.1: Setup database schema
Task 1.2: Create repository layer
Task 1.3: Add service layer

Dependencies:
1.2 blocks on 1.1
1.3 blocks on 1.2
```

### Pattern 2: Database Or Migration Before API Or Business Logic

**Rule:** API or business logic work blocks on prerequisite database or migration work.

```text
Task 1.1: Create users table migration
Task 2.1: Add user registration endpoint

Dependencies:
2.1 blocks on 1.1
```

### Pattern 3: Config Before Implementation

**Rule:** Configuration and setup block implementation.

```text
Task 1.1: Configure JWT secret in env
Task 2.1: Implement JWT generation

Dependencies:
2.1 blocks on 1.1
```

### Pattern 4: Implementation Related To Verification

**Rule:** Verification tasks are usually `related`, not `blocks`, unless the plan says otherwise.

```text
Task 2.1: Implement user registration
Task 3.1: Write registration tests

Dependencies:
3.1 related-to 2.1
```

### Pattern 5: Core Before Polish

**Rule:** Non-essential polish blocks on core functionality.

```text
Task 2.1: Basic transaction import
Task 4.1: Add import progress indicator

Dependencies:
4.1 blocks on 2.1
```

## Dependency Types

### `blocks`

Use when a task cannot start until another one completes.

### `related`

Use when two tasks share context but can progress independently.

### `parent-child`

Use to link child execution tasks to the change epic.

### `discovered-from`

Use for work discovered during execution that should stay attached to its origin.

## Gap Detection Patterns

### Missing Rollback

If a planning wave contains migration work but no rollback or recovery task exists, create a discovered task for rollback planning.

### Missing Rate Limiting

If a planning wave introduces an API endpoint and the plan omits throttling or abuse controls where they are expected, create a discovered task.

### Missing Error Handling

If a planning wave touches an external service and the plan omits retries, error surfacing, or failure handling, create a discovered task.

### Missing Monitoring

If a feature wave lacks operational visibility where the repo would normally expect it, create a discovered task.

### Missing Tests

If an implementation wave lacks verification or test coverage work, create a related task or stop sync if the gap is too large.
