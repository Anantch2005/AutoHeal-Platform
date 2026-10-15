
import pytest

from app.collectors.jenkins import JenkinsCollector


class FakeResponse:
    def __init__(self, payload=None, text=""):
        self._payload = payload or {}
        self.text = text

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeAsyncClient:
    requested_urls = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, **kwargs):
        self.requested_urls.append(url)
        if url.endswith("api/json"):
            return FakeResponse({"result": "FAILURE", "url": url.rsplit("/api/json", 1)[0] + "/"})
        return FakeResponse(text="secret=not-logged")


@pytest.mark.asyncio
async def test_collector_quotes_folder_and_multibranch_job_segments(monkeypatch):
    FakeAsyncClient.requested_urls = []
    monkeypatch.setattr("app.collectors.jenkins.httpx.AsyncClient", FakeAsyncClient)
    collector = JenkinsCollector()
    build = await collector.get_build_info("Folder Name/Job #1/feature", 7)

    assert build.result == "FAILURE"
    assert any("/job/Folder%20Name/job/Job%20%231/job/feature/7/api/json" in url
               for url in FakeAsyncClient.requested_urls)
    assert any(url.endswith("/consoleText") for url in FakeAsyncClient.requested_urls)

