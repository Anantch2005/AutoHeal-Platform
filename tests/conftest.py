
from pathlib import Path
import os

# Isolate the test database so repeated local test runs are deterministic.
TEST_DB = Path("/tmp/autoheal-test.db")
TEST_DB.unlink(missing_ok=True)


# =========================================================
# DETERMINISTIC TEST ENVIRONMENT
# =========================================================

os.environ.setdefault(
    "JENKINS_URL",
    "http://127.0.0.1:8080",
)

os.environ.setdefault(
    "JENKINS_USERNAME",
    "test-user",
)

os.environ.setdefault(
    "JENKINS_API_TOKEN",
    "test-token",
)

os.environ.setdefault(
    "WEBHOOK_SECRET",
    "change-me",
)

os.environ.setdefault(
    "ALERTMANAGER_SECRET",
    "change-me-alertmanager",
)

os.environ.setdefault(
    "DATABASE_URL",
    "sqlite:////tmp/autoheal-test.db",
)

os.environ.setdefault(
    "AI_ENABLED",
    "false",
)

os.environ.setdefault(
    "OLLAMA_URL",
    "http://127.0.0.1:11434",
)

os.environ.setdefault(
    "OLLAMA_MODEL",
    "llama3.2:3b",
)

os.environ.setdefault(
    "AI_MAX_LOG_CHARS",
    "12000",
)

os.environ.setdefault(
    "OTEL_ENDPOINT",
    "http://127.0.0.1:4318",
)
os.environ.setdefault("OTEL_ENABLED", "false")

