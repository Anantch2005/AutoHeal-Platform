from dataclasses import dataclass


@dataclass(frozen=True)
class FailureRule:
    category: str
    action: str
    reason: str
    patterns: list[str]


# Rule order is deliberate.
#
# Specific / unsafe failures are checked before generic
# transient infrastructure signals.
#
# This prevents cases such as:
#
# Traceback + Connection refused
#     -> CODE_FAILURE
# rather than
#     -> NETWORK_FAILURE
#
# It also prevents generic "Permission denied" from
# automatically becoming WORKSPACE_FAILURE.
FAILURE_RULES = [

    # =========================================================
    # FLAKY TEST
    # =========================================================

    FailureRule(
        category="FLAKY_TEST",
        action="RETRY",
        reason=(
            "The failure matches a known AutoHeal "
            "flaky-test scenario."
        ),
        patterns=[
            r"AUTOHEAL_FLAKY_TEST",
            r"AUTOHEAL_TEST_FAILURE.*FLAKY_TEST",
        ],
    ),

    # =========================================================
    # CODE FAILURE
    # =========================================================

    FailureRule(
        category="CODE_FAILURE",
        action="DO_NOT_HEAL",
        reason=(
            "A test assertion or application "
            "code failure was detected."
        ),
        patterns=[
            r"AssertionError",
            r"E\s+AssertionError",
            r"FAILED\s+.*test[_\w]*",
            r"test[_\w]+.*(?:failed|error)",
            r"Traceback \(most recent call last\)",
            r"SyntaxError",
            r"TypeError",
            r"NameError",
        ],
    ),

    # =========================================================
    # DOCKER FAILURE
    # =========================================================

    FailureRule(
        category="DOCKER_FAILURE",
        action="INVALIDATE_DOCKER_CACHE_AND_RETRY",
        reason=(
            "A Docker build or container operation "
            "failure was detected."
        ),
        patterns=[
            r"Cannot connect to the Docker daemon",
            r"permission denied.*Docker daemon",
            r"Docker daemon.*permission denied",
            r"failed to solve:",
            r"failed to build",
            r"docker build.*(?:error|failed)",
            r"failed to create.*(?:task|container|endpoint)",
            r"BuildKit.*failed",
        ],
    ),

    # =========================================================
    # REGISTRY FAILURE
    # =========================================================

    FailureRule(
        category="REGISTRY_FAILURE",
        action="RETRY",
        reason=(
            "A container registry operation "
            "appears to have failed."
        ),
        patterns=[
            r"requested access to the resource is denied",
            r"denied:.*(?:push|pull)\b",
            r"failed to push (?:image|manifest|layer|artifact)",
            r"failed to pull (?:image|manifest|layer|artifact)",
            r"manifest unknown",
            r"toomanyrequests",
            r"(?:docker\.io|ghcr\.io|quay\.io|ecr).*unauthorized",
            r"unauthorized.*(?:registry|repository|docker\.io|ghcr\.io|ecr)",
            r"registry.*(?:timeout|timed out)",
        ],
    ),

    # =========================================================
    # DEPENDENCY FAILURE
    # =========================================================

    FailureRule(
        category="DEPENDENCY_FAILURE",
        action="CLEAN_DEPENDENCY_ENV_AND_RETRY",
        reason=(
            "A dependency installation or package "
            "resolution failure was detected."
        ),
        patterns=[
            r"Could not find a version that satisfies",
            r"No matching distribution found",
            r"ResolutionImpossible",
            r"dependency conflict",
            r"package.*conflict",
            r"version.*conflict",
            r"failed to resolve dependencies",
            r"dependency.*resolution.*failed",
        ],
    ),

    # =========================================================
    # NETWORK FAILURE
    # =========================================================

    FailureRule(
        category="NETWORK_FAILURE",
        action="CONNECTIVITY_CHECK_BACKOFF_AND_RETRY",
        reason=(
            "A network or connection failure "
            "was detected."
        ),
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
        ],
    ),

    # =========================================================
    # WORKSPACE FAILURE
    # =========================================================

    FailureRule(
        category="WORKSPACE_FAILURE",
        action="CLEAN_WORKSPACE_AND_RETRY",
        reason=(
            "A Jenkins workspace or filesystem "
            "failure was detected."
        ),
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