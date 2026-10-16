import json
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "railway_deploy.sh"
IMAGE = "ghcr.io/abti247/iron_verdict:sha-1a2b3c4"


class FakeRailway:
    """Railway GraphQL API (POST /graphql) and the deployed app (/health, /)."""

    def __init__(self):
        self.requests = []
        self.graphql_errors = None
        self.served_version = "sha-old0000"
        # Status answers to successive deployment queries; the last one repeats.
        self.statuses = ["DEPLOYING", "SUCCESS"]
        self.status_queries = 0
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _send(self, status, body, content_type):
                data = body.encode()
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                fake.requests.append({"token": self.headers.get("Project-Access-Token"), **body})
                if fake.graphql_errors:
                    payload = {"errors": fake.graphql_errors, "data": None}
                elif "deployment(" in body["query"]:
                    status = fake.statuses[min(fake.status_queries, len(fake.statuses) - 1)]
                    fake.status_queries += 1
                    if status == "SUCCESS":
                        fake.served_version = fake.pending_version
                    payload = {"data": {"deployment": {"status": status}}}
                elif "serviceInstanceUpdate" in body["query"]:
                    payload = {"data": {"serviceInstanceUpdate": True}}
                    fake.pending_version = body["variables"]["i"].rsplit(":", 1)[1]
                else:
                    payload = {"data": {"serviceInstanceDeployV2": "deploy-1"}}
                self._send(200, json.dumps(payload), "application/json")

            def do_GET(self):
                if self.path == "/health":
                    self._send(200, '{"status":"ok"}', "application/json")
                else:
                    html = f'<div class="app-version">\n    {fake.served_version}\n</div>'
                    self._send(200, html, "text/html")

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


@pytest.fixture
def railway():
    fake = FakeRailway()
    yield fake
    fake.server.shutdown()


def run_deploy(railway, expected_version="sha-1a2b3c4", timeout_s="20"):
    env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "RAILWAY_TOKEN": "token-123",
        "RAILWAY_SERVICE_ID": "service-1",
        "RAILWAY_ENVIRONMENT_ID": "env-1",
        "RAILWAY_API": f"{railway.url}/graphql",
        "DEPLOY_TIMEOUT_S": timeout_s,
        "POLL_INTERVAL_S": "0.1",
    }
    return subprocess.run(
        ["bash", str(SCRIPT), IMAGE, railway.url, expected_version],
        env=env, capture_output=True, text=True, timeout=60,
    )


def test_deploy_sets_image_deploys_and_waits_for_footer_version(railway):
    result = run_deploy(railway)

    assert result.returncode == 0, result.stderr
    assert f"{railway.url} serves sha-1a2b3c4" in result.stdout
    update, deploy, *status_queries = railway.requests
    assert update["token"] == deploy["token"] == "token-123"
    assert "serviceInstanceUpdate" in update["query"]
    assert update["variables"] == {"e": "env-1", "s": "service-1", "i": IMAGE}
    assert "serviceInstanceDeployV2" in deploy["query"]
    assert deploy["variables"] == {"e": "env-1", "s": "service-1"}
    assert [q["variables"] for q in status_queries] == [{"d": "deploy-1"}] * 2


def test_redeploy_of_served_version_waits_for_new_deployment(railway):
    # Re-run: staging already serves the image; only Railway's status tells
    # the new deployment from the old one.
    railway.served_version = "sha-1a2b3c4"
    railway.statuses = ["QUEUED", "DEPLOYING", "DEPLOYING", "SUCCESS"]

    result = run_deploy(railway)

    assert result.returncode == 0, result.stderr
    assert railway.status_queries == 4


def test_deploy_fails_when_deployment_fails(railway):
    railway.statuses = ["DEPLOYING", "CRASHED"]

    result = run_deploy(railway)

    assert result.returncode != 0
    assert "ended with status CRASHED" in result.stderr


def test_deploy_fails_on_graphql_error_without_deploying(railway):
    railway.graphql_errors = [{"message": "Not Authorized"}]

    result = run_deploy(railway)

    assert result.returncode != 0
    assert "Not Authorized" in result.stderr
    assert len(railway.requests) == 1


def test_deploy_fails_when_footer_never_shows_expected_version(railway):
    railway.statuses = ["SUCCESS"]

    result = run_deploy(railway, expected_version="sha-9999999", timeout_s="1")

    assert result.returncode != 0
    assert "did not serve sha-9999999" in result.stderr
    assert "last seen: 'sha-1a2b3c4'" in result.stderr
