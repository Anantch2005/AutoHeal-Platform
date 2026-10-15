
from dataclasses import dataclass


@dataclass(frozen=True)
class FailureRule:
    category: str
    action: str
    reason: str
    patterns: tuple[str, ...]
    confidence: float = 0.90


# Order is intentional: explicit test/application failures take precedence
# over broad transport words that may appear inside an assertion message.
FAILURE_RULES = (
    FailureRule(
        category="FLAKY_TEST",
        action="RETRY",
        reason="An explicit AutoHeal flaky-test marker was detected.",
        patterns=(r"AUTOHEAL_FLAKY_TEST", r"AUTOHEAL_TEST_FAILURE.*FLAKY_TEST"),
        confidence=0.99,
    ),
    FailureRule(
        category="CODE_FAILURE",
        action="DO_NOT_HEAL",
        reason="Application code or test assertions must not be changed automatically.",
        patterns=(
            r"AssertionError",
            r"\bassert(?:ion)?\b.{0,100}(?:failed|expected|actual)",
            r"\bFAILED\s+.*test[_\w]*",
            r"\b(?:SyntaxError|TypeError|NameError|AttributeError)\b",
            r"\bImportError:\s*cannot import name\b",
            r"\bModuleNotFoundError: No module named ['\"]?(?:app|src|tests?)\.[\w.]+",
            r"\bImportError:\s*attempted relative import beyond top-level package\b",
        ),
        confidence=0.93,
    ),
    FailureRule(
        category="REGISTRY_AUTH_FAILURE",
        action="ESCALATE",
        reason="Registry authentication failed; credentials must be reviewed by a human.",
        patterns=(
            r"(?:docker|containerd|podman).{0,100}(?:unauthorized: authentication required|authentication required)",
            r"(?:docker|containerd|podman).{0,100}denied: requested access to the resource is denied",
            r"(?:docker|containerd|podman).{0,100}incorrect username or password",
            r"insufficient_scope: authorization failed.{0,100}(?:registry|image|manifest|layer)",
            r"(?:pull|push) access denied for [\w./:-]+",
        ),
        confidence=0.96,
    ),
    FailureRule(
        category="DOCKER_DAEMON_FAILURE",
        action="ESCALATE",
        reason="Docker daemon is unavailable; cache cleanup cannot repair it.",
        patterns=(
            r"Cannot connect to the Docker daemon",
            r"permission denied while trying to connect to the Docker daemon",
            r"docker daemon.*not running",
            r"Is the docker daemon running",
        ),
        confidence=0.98,
    ),
    FailureRule(
        category="DISK_FULL",
        action="ESCALATE",
        reason="Disk exhaustion detected; privileged agent cleanup is not enabled.",
        patterns=(r"No space left on device", r"\bENOSPC\b", r"disk quota exceeded", r"write failed.*no space"),
        confidence=0.98,
    ),
    FailureRule(
        category="OOM",
        action="ESCALATE",
        reason="Out-of-memory failure detected; resource resizing is not enabled.",
        patterns=(r"\bOOMKilled\b", r"out of memory", r"\bexit code 137\b", r"\bexit status 137\b", r"signal 9.*killed", r"oom-kill"),
        confidence=0.95,
    ),
    FailureRule(
        category="AGENT_FAILURE",
        action="ESCALATE",
        reason="Jenkins agent failure detected; agent replacement is not enabled.",
        patterns=(r"agent .* went offline", r"agent .* is offline", r"computer .* is offline", r"channel .* is closed", r"lost connection to agent", r"remoting\.ChannelClosedException", r"agent was removed"),
        confidence=0.95,
    ),
    FailureRule(
        category="NETWORK_FAILURE",
        action="CONNECTIVITY_CHECK_BACKOFF_AND_RETRY",
        reason="A connection-level transient network failure was detected.",
        patterns=(
            r"Connection timed out",
            r"ConnectTimeout",
            r"connection timeout",
            r"Temporary failure in name resolution",
            r"network is unreachable",
            r"Connection refused",
            r"Failed to connect to .* port",
            r"Could not resolve host",
            r"Name or service not known",
            r"\bETIMEDOUT\b",
            r"\bECONNRESET\b",
            r"Max retries exceeded.*(?:Connection|NameResolution|ConnectTimeout)",
        ),
        confidence=0.88,
    ),
    FailureRule(
        category="DEPENDENCY_FAILURE",
        action="CLEAN_DEPENDENCY_ENV_AND_RETRY",
        reason="A known runtime dependency is missing or dependency installation failed.",
        patterns=(
            r"Could not find a version that satisfies",
            r"No matching distribution found",
            r"ResolutionImpossible",
            r"failed to resolve dependencies",
            r"dependency.*resolution.*failed",
            r"pip(?:3)? install.*(?:failed|error)",
            r"npm (?:ERR!|error).*(?:ENOENT|EINTEGRITY|ERESOLVE)",
            r"checksum mismatch",
            r"corrupt(?:ed)? archive",
            r"No module named ['\"]?(?:pytest|pytest_cov|requests|httpx|flask|fastapi|pydantic|sqlalchemy|yaml|coverage|numpy|pandas|boto3|botocore)(?:['\"]|\b)",
            r"ModuleNotFoundError: No module named ['\"]?(?:pytest|pytest_cov|requests|httpx|flask|fastapi|pydantic|sqlalchemy|yaml|coverage|numpy|pandas|boto3|botocore)(?:['\"]|\b)",
        ),
        confidence=0.92,
    ),
    FailureRule(
        category="DOCKER_FAILURE",
        action="DOCKER_CACHE_BYPASS_AND_RETRY",
        reason="A Docker build/cache failure was detected.",
        patterns=(r"failed to solve:", r"failed to build", r"docker build.*(?:error|failed)", r"BuildKit.*failed", r"failed to compute cache key", r"cache key.*failed"),
        confidence=0.90,
    ),
    FailureRule(
        category="REGISTRY_FAILURE",
        action="RETRY",
        reason="A potentially transient image registry failure was detected.",
        patterns=(r"failed to push (?:image|manifest|layer|artifact)", r"failed to pull (?:image|manifest|layer|artifact)", r"manifest unknown", r"toomanyrequests", r"registry.*(?:timeout|timed out)"),
        confidence=0.88,
    ),
    FailureRule(
        category="WORKSPACE_FAILURE",
        action="CLEAN_WORKSPACE_AND_RETRY",
        reason="A Jenkins workspace or checkout failure was detected.",
        patterns=(r"unable to create file", r"workspace.*permission denied", r"permission denied.*workspace", r"cannot create .*workspace", r"Could not checkout", r"Maximum checkout retry attempts reached", r"fatal: cannot create directory.*permission denied", r"workspace.*corrupt"),
        confidence=0.90,
    ),
)

