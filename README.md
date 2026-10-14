
# AutoHeal Platform

**Policy-controlled CI/CD failure recovery for Jenkins pipelines.**

AutoHeal is a DevOps engineering project that detects common CI/CD failures,
collects diagnostic evidence, applies deterministic safety policies, executes
allowlisted recovery actions through Jenkins, and verifies the recovery build.

The project is designed around one rule:

> AI can explain a failure, but AI cannot authorize a remediation.

## Why this project exists

A conventional pipeline reports a failed build and leaves an engineer to
investigate it. AutoHeal attempts to recover from a narrow set of known,
low-risk failure classes while escalating failures that require human judgment.

The goal is not to automatically fix every failure. The goal is to recover
safely when the failure has a known recovery procedure, and to avoid making
an incident worse when it does not.

## Architecture

1. **Jenkins** executes the application pipeline and reports failed builds.
2. **Jenkins Collector** retrieves build metadata and console output.
3. **Deterministic Classifier** maps known failure signatures to categories.
4. **AI Diagnostic Assistant** uses local Ollama to explain relevant evidence.
5. **Policy Engine** decides whether a category and action are allowed.
6. **Remediation Executor** requests an allowlisted recovery build.
7. **Jenkins Shared Library** executes the recovery action at the required stage.
8. **Verification** checks the recovery build's final Jenkins result.
9. **PostgreSQL and Observability** retain incidents, attempts, audit events,
   metrics, logs, and traces.

## Safety model

The system separates diagnosis, authorization, execution, and verification.

- Deterministic rules classify known failure signatures.
- AI analysis is advisory and cannot override the policy engine.
- Remediation actions are allowlisted.
- Recovery commands run through Jenkins, not arbitrary AI-generated shell.
- Recovery is bounded; repeated failures can be blocked by the circuit breaker.
- A successful API response or queued build is not considered a successful heal.
- An incident is healed only when the recovery build finishes successfully.
- Code defects, registry authentication failures, Docker daemon failures,
  disk exhaustion, OOM, and agent failures are escalated unless a dedicated,
  explicitly authorized recovery is implemented.

## Recovery capabilities

| Category | Recovery strategy | Verification |
|---|---|---|
| Dependency failure | Rebuild a supported dependency environment from its manifest | Recovery pipeline result |
| Workspace failure | Repair owner permissions where possible, clean workspace, fresh checkout | Recovery pipeline result |
| Transient network failure | Bounded connectivity probes and controlled retry | Recovery pipeline result |
| Docker build/cache failure | One cache-bypassing rebuild | Recovery pipeline result |
| Code failure | No automatic source modification | Escalation |
| Registry authentication failure | No credential mutation | Escalation |
| Docker daemon failure | No automatic daemon restart | Escalation |
| Disk full, OOM, agent offline | Human investigation | Escalation |

A transient retry is not a repair for a persistent network outage. If connectivity
remains unavailable, the pipeline should remain failed and the incident should
be escalated.

## Technology stack

- Python and FastAPI
- Jenkins Pipeline and Jenkins Shared Libraries
- PostgreSQL and SQLAlchemy
- Ollama for local diagnostic assistance
- OpenTelemetry
- Prometheus and Alertmanager
- Grafana and Tempo
- Docker and Docker Compose
- Pytest

## Local setup

1. Clone the repository.
2. Copy `.env.example` to `.env`.
3. Configure Jenkins URL, Jenkins username, API token, webhook secret,
   PostgreSQL credentials, and Alertmanager secret.
4. Configure Jenkins with the required shared libraries and credentials.
5. Start the services:

   ```bash
   docker compose up -d --build
   ```

6. Check application health:

   ```bash
   curl http://127.0.0.1:8000/health
   ```

7. Run the backend test suite in a Python 3.12 environment:

   ```bash
   python -m pip install -r requirements.txt
   python -m pytest -q
   ```

Do not commit `.env`, Jenkins API tokens, webhook secrets, or registry credentials.

## Controlled recovery validation

Use the Calculator CI/CD pipeline's `AUTOHEAL_TEST_FAILURE` parameter to run
one scenario at a time:

1. `DEPENDENCY_FAILURE`: remove the test runner after installing requirements.
2. `NETWORK_FAILURE`: make an actual HTTP connection attempt to a controlled
   closed local port.
3. `WORKSPACE_FAILURE`: attempt to write inside a directory with no owner
   write permission. Run this scenario as a non-root Jenkins agent.
4. `CODE_FAILURE`: produce an assertion error and verify that AutoHeal does
   not modify application code.
5. `UNKNOWN_FAILURE`: validate the escalation path.

For each recovery test, retain the original build log, the classification and
policy decision, the recovery build log, the final verification result, and
the corresponding incident/audit record.

Do not call a scenario healed merely because a recovery build was queued.

## Operational limitations

This is a learning and portfolio project, not a claim of production readiness.

- The webhook currently schedules processing using FastAPI background tasks;
  a durable queue would be needed to guarantee recovery processing across
  process crashes.
- The circuit breaker currently keeps state in application memory; a
  multi-replica production deployment would need shared persistent state.
- Database table creation is not a substitute for schema migrations.
- Connectivity checks cannot repair arbitrary DNS, routing, firewall, proxy,
  or third-party service outages.
- Cache bypass does not fix all Docker daemon or BuildKit failures.
- Automatic host-level cleanup, credential mutation, daemon restart, and
  resource resizing are intentionally outside the supported recovery scope.

## Engineering priorities

The next production-hardening steps are durable incident processing,
database migrations, persistent circuit-breaker state, explicit incident
lifecycle transitions, structured audit logging, and integration tests that
exercise the complete Jenkins-to-recovery lifecycle.
