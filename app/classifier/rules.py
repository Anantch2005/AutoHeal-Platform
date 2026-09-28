from dataclasses import dataclass


@dataclass
class FailureRule:
    category: str
    action: str
    reason: str
    patterns: list[str]


FAILURE_RULES = [

    # Most specific signatures FIRST.
    FailureRule(
        category="FLAKY_TEST",
        action="RETRY",
        reason=(
            "The failure matches a known AutoHeal "
            "flaky-test scenario."
        ),
        patterns=[
            r"AUTOHEAL_FLAKY_TEST",
            r"FLAKY_TEST",
        ],
    ),

    FailureRule(
        category="WORKSPACE_FAILURE",
        action="CLEAN_WORKSPACE_AND_RETRY",
        reason=(
            "A Jenkins workspace or filesystem "
            "failure was detected."
        ),
        patterns=[
            r"Permission denied",
            r"unable to create file",
            r"Could not checkout",
            r"Maximum checkout retry attempts reached",
            r"workspace.*permission",
        ],
    ),

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
        ],
    ),

    # Registry MUST come before generic Docker rules.
    FailureRule(
        category="REGISTRY_FAILURE",
        action="RETRY",
        reason=(
            "A container registry operation "
            "appears to have failed."
        ),
        patterns=[
            r"unauthorized.*registry",
            r"unauthorized:.*",
            r"requested access to the resource is denied",
            r"denied:.*(?:push|pull)",
            r"push.*failed",
            r"failed to push",
            r"pull.*failed",
            r"manifest unknown",
            r"registry.*timeout",
            r"name unknown",
        ],
    ),

    FailureRule(
        category="DOCKER_FAILURE",
        action="INVALIDATE_DOCKER_CACHE_AND_RETRY",
        reason=(
            "A Docker build or container operation "
            "failure was detected."
        ),
        patterns=[
            r"Cannot connect to the Docker daemon",
            r"failed to solve",
            r"failed to build",
            r"docker build.*error",
            r"docker build.*failed",
            r"failed to create.*container",
        ],
    ),

    # Generic code signatures LAST.
    FailureRule(
        category="CODE_FAILURE",
        action="DO_NOT_HEAL",
        reason=(
            "A test assertion or application "
            "code failure was detected."
        ),
        patterns=[
            r"AssertionError",
            r"assert .*==",
            r"FAILED .*test_",
            r"test_.*failed",
            r"Traceback \(most recent call last\)",
        ],
    ),
]