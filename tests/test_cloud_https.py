from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient
from app.cloud_https import HerokuHTTPS


def test_http_redirect_is_canonical_and_preserves_path_query_method():
    app = HerokuHTTPS(Starlette(), "https://student-os.dev/api/auth/telegram/callback")
    with TestClient(app, base_url="http://untrusted.invalid", follow_redirects=False) as client:
        response = client.post("/example?q=one", headers={"X-Forwarded-Proto":"http"})
    assert response.status_code == 307
    assert response.headers["location"] == "https://student-os.dev/example?q=one"
    assert response.headers["cache-control"] == "no-store"


def test_router_https_is_not_redirected_and_missing_proto_fails_closed():
    async def healthy(request):
        return PlainTextResponse("ok")
    app = HerokuHTTPS(Starlette(routes=[Route("/", healthy)]), "https://student-os.dev/callback")
    with TestClient(app, follow_redirects=False) as client:
        assert client.get("/", headers={"X-Forwarded-Proto":"https"}).status_code == 200
        assert client.get("/").status_code == 307
        assert client.get("/", headers={"X-Forwarded-Proto":"https,http"}).status_code == 307
