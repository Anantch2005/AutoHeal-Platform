from dataclasses import dataclass


@dataclass(frozen=True)
class FailureRule:
    category: str
    action: str
    reason: str
    patterns: list[str]


FAILURE_RULES = [
    FailureRule(
        category="FLAKY_TEST",
        action="RETRY",
        reason="A known flaky-test signature was detected.",
        patterns=[
            r"AUTOHEAL_FLAKY_TEST",
            r"AUTOHEAL_TEST_FAILURE.*FLAKY_TEST",
        ],
    ),
    FailureRule(
        category="REGISTRY_AUTH_FAILURE",
        action="ESCALATE",
        reason="Registry authentication or authorization failed.",
        patterns=[
            r"denied: requested access to the resource is denied",
            r"unauthorized: authentication required",
            r"authentication required",
            r"incorrect username or password",
            r"insufficient_scope: authorization failed",
        ],
    ),
    FailureRule(
        category="DOCKER_DAEMON_FAILURE",
        action="ESCALATE",
        reason="Docker daemon is unavailable; cache cleanup cannot fix it.",
        patterns=[
            r"Cannot connect to the Docker daemon",
            r"permission denied while trying to connect to the Docker daemon",
            r"docker daemon.*not running",
        ],
    ),
    FailureRule(
        category="DISK_FULL",
        action="ESCALATE",
        reason="Disk exhaustion detected; privileged cleanup is not enabled.",
        patterns=[
            r"No space left on device",
            r"\bENOSPC\b",
            r"disk quota exceeded",
            r"write failed.*no space",
        ],
    ),
    FailureRule(
        category="OOM",
        action="ESCALATE",
        reason="Out-of-memory failure detected; resource resizing is not enabled.",
        patterns=[
            r"OOMKilled",
            r"out of memory",
            r"exit code 137",
            r"signal 9.*killed",
        ],
    ),
    FailureRule(
        category="AGENT_FAILURE",
        action="ESCALATE",
        reason="Jenkins agent failure detected; replacement is not enabled.",
        patterns=[
            r"agent .* went offline",
            r"agent .* is offline",
            r"computer .* is offline",
            r"channel .* is closed",
            r"lost connection to agent",
        ],
    ),
    FailureRule(
        category="CODE_FAILURE",
        action="DO_NOT_HEAL",
        reason="Application code or test assertion failed.",
        patterns=[
            r"AssertionError",
            r"E\s+AssertionError",
            r"FAILED\s+.*test[_\w]*",
            r"SyntaxError",
            r"TypeError",
            r"NameError",
        ],
    ),
    FailureRule(
        category="DEPENDENCY_FAILURE",
        action="CLEAN_DEPENDENCY_ENV_AND_RETRY",
        reason="A missing dependency or package installation failure was detected.",
        patterns=[
            r"Could not find a version that satisfies",
            r"No matching distribution found",
            r"No module named ['\"]?[\w.-]+",
            r"ModuleNotFoundError: No module named ['\"]?[\w.-]+",
            r"ResolutionImpossible",
            r"failed to resolve dependencies",
            r"dependency.*resolution.*failed",
            r"npm ERR!.*(?:ENOENT|ECONNRESET|EINTEGRITY)",
            r"checksum mismatch",
            r"corrupt(?:ed)? archive",
        ],
    ),
    FailureRule(
        category="DOCKER_FAILURE",
        action="INVALIDATE_DOCKER_CACHE_AND_RETRY",
        reason="A Docker build failure was detected.",
        patterns=[
            r"failed to solve:",
            r"failed to build",
            r"docker build.*(?:error|failed)",
            r"failed to create.*(?:task|container|endpoint)",
            r"BuildKit.*failed",
        ],
    ),
    FailureRule(
        category="REGISTRY_FAILURE",
        action="RETRY",
        reason="A potentially transient registry failure was detected.",
        patterns=[
            r"failed to push (?:image|manifest|layer|artifact)",
            r"failed to pull (?:image|manifest|layer|artifact)",
            r"manifest unknown",
            r"toomanyrequests",
            r"registry.*(?:timeout|timed out)",
        ],
    ),
    FailureRule(
        category="NETWORK_FAILURE",
        action="CONNECTIVITY_CHECK_BACKOFF_AND_RETRY",
        reason="A transient network failure was detected.",
        patterns=[
            r"Connection timed out",
            r"ConnectTimeout",
            r"connection timeout",
            r"Temporary failure in name resolution",
            r"network is unreachable",
            r"Connection refused",
            r"Failed to connect to .* port",
            r"Could not resolve host",
            r"Name or service not known",
            r"HTTP/(?:1\.1|2) 5\d\d",
            r"\b429 Too Many Requests\b",
            r"\bETIMEDOUT\b",
            r"\bECONNRESET\b",
        ],
    ),
    FailureRule(
        category="WORKSPACE_FAILURE",
        action="CLEAN_WORKSPACE_AND_RETRY",
        reason="A workspace or filesystem failure was detected.",
        patterns=[
            r"unable to create file",
            r"workspace.*permission denied",
            r"permission denied.*workspace",
            r"cannot create .*workspace",
            r"Could not checkout",
            r"Maximum checkout retry attempts reached",
            r"fatal: cannot create directory.*permission denied",
            r"workspace.*corrupt",
        ],
    ),
]