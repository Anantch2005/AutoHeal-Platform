
from pathlib import Path
import os

# Isolate the test database so repeated local test runs are deterministic.
TEST_DB = Path("/tmp/buildsentry-test.db")
TEST_DB.unlink(missing_ok=True)


# =========================================================
# DETERMINISTIC TEST ENVIRONMENT
# =========================================================

os.environ["JENKINS_URL"] = "http://127.0.0.1:8080"

os.environ["JENKINS_USERNAME"] = "test-user"

os.environ["JENKINS_API_TOKEN"] = "test-token"

os.environ["WEBHOOK_SECRET"] = "change-me"

os.environ["ALERTMANAGER_SECRET"] = "change-me-alertmanager"

os.environ["DATABASE_URL"] = "sqlite:////tmp/buildsentry-test.db"

os.environ["AI_ENABLED"] = "false"

os.environ["OLLAMA_URL"] = "http://127.0.0.1:11434"

os.environ["OLLAMA_MODEL"] = "llama3.2:3b"

os.environ["AI_MAX_LOG_CHARS"] = "12000"

os.environ["OTEL_ENDPOINT"] = "http://127.0.0.1:4318"
os.environ["OTEL_ENABLED"] = "false"