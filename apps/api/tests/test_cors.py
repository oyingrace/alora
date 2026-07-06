from fastapi.testclient import TestClient


def test_cors_preflight_allows_cross_origin_widget_requests(client: TestClient) -> None:
    """The snippet runs on arbitrary third-party storefront origins — a browser
    preflight (OPTIONS) against any endpoint must succeed, or every real embed
    fails with a CORS error before a single request reaches the API.
    """
    response = client.options(
        "/memory",
        headers={
            "Origin": "https://some-storefront.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "*"
