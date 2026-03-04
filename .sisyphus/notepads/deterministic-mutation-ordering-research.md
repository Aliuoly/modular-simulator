# Deterministic Mutation Ordering - External Research

## Date
2026-02-21

## Research Scope
External guidance/examples for deterministic mutation ordering under live runtime updates:
- FIFO ordering
- Strict-block poison request
- Payload mismatch reject for idempotency key

## Authoritative Sources Consulted

1. **Stripe API** - Idempotent requests with payload validation
   - URL: https://docs.stripe.com/api/idempotent_requests
   - Key insight: Compares incoming parameters to original on key reuse, errors if mismatch

2. **AWS Well-Architected Framework** - REL04-BP04
   - URL: https://docs.aws.amazon.com/wellarchitected/latest/reliability-pillar/rel_prevent_interaction_failure_idempotent.html
   - Key insights: Anti-patterns to avoid, storage options, implementation steps

3. **AWS SNS FIFO** - Message ordering details
   - URL: https://docs.aws.amazon.com/sns/latest/dg/fifo-topic-message-ordering.html
   - Key insight: Message groups for ordering within groups, parallelism across groups

4. **AWS SQS** - Dead letter queue for poison messages
   - URL: https://docs.aws.amazon.com/AWSSimpleQueueService/latest/SQSDeveloperGuide/capturing-problematic-messages.html
   - Key insight: Redrive policy, poison pill prevention

5. **Apache Kafka** - Consumer ordering and processing patterns
   - Library ID: /apache/kafka
   - Key insights: Manual partition assignment, consumer groups, exactly-once semantics

6. **OneUptime** - Kafka poison message handling guide
   - URL: https://oneuptime.com/blog/post/2026-01-21-kafka-poison-messages/view
   - Key insights: DLQ implementation, circuit breaker, retry strategies

7. **Milan Jovanović** - Solving message ordering from first principles
   - URL: https://www.milanjovanovic.tech/blog/solving-message-ordering-from-first-principles
   - Key insight: Per-aggregate ordering, not global ordering

8. **Microsoft Azure** - Sequential Convoy pattern
   - URL: https://learn.microsoft.com/en-us/azure/architecture/patterns/sequential-convoy
   - Key insight: Batch ordering without blocking unrelated groups

## Key Learnings

### FIFO Ordering
- Global ordering is rarely needed; order per aggregate/entity boundary
- Use partitioning keys based on entity IDs
- Message groups allow strict ordering within groups while enabling parallelism
- Sequential Convoy pattern for batch processing of related messages

### Poison Message Handling
- DLQ with redrive policy prevents queue starvation
- Circuit breaker prevents cascading failures
- Distinguish retriable vs non-retriable exceptions
- Bounded retries with exponential backoff
- Include rich metadata in DLQ for debugging

### Idempotency Key Validation
- **Critical**: Validate payload fingerprint on key reuse; reject if mismatch
- Use SHA-256 or similar for payload fingerprinting
- Atomic check-then-act pattern prevents race conditions
- TTL for key cleanup (minimum 24 hours recommended by Stripe)
- Propagate tokens through entire processing chain
- Never use timestamps as keys (clock skew)

### Anti-Patterns (from AWS Well-Architected)
- Do not store entire payloads for idempotency (use fingerprints)
- Do not apply idempotency indiscriminately
- Do not use timestamps as idempotency keys
- Do not use inconsistent key generation across services
- Do not create overly complex idempotency logic

### Storage Options
- DynamoDB: Key-value model, automatic TTL
- ElastiCache (Redis): High throughput, low latency, TTL support
- RDS: If already using relational DB
- S3: Versioning capabilities

## Actionable Rules for Architecture Contract

See main response for detailed, numbered rules with implementation guidance and rationale.

## Next Steps
1. Encode these rules as architecture contract constraints
2. Implement automated tests for each rule
3. Document service-specific idempotency key generation strategy
4. Configure DLQ for all message consumers
5. Implement circuit breaker pattern for all downstream service calls
