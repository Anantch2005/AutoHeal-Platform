def test_webhook_structure():
    payload = {
        "job_name": "Calculator",
        "build_number": 42,
        "build_url": "http://jenkins/job/Calculator/42/",
        "status": "FAILURE",
    }

    assert payload["job_name"] == "Calculator"
    assert payload["build_number"] == 42
    assert payload["status"] == "FAILURE"