import pytest
import requests

from de4py.api.client import ApiError, De4pyApiClient
from de4py.api.constants import ERROR_CODES
from de4py.config.config import settings


class FakeResponse:
    def __init__(self, status=200, payload=None, text=""):
        self.status_code = status
        self._payload = payload
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(response=self)

    def json(self):
        if self._payload is None:
            raise ValueError("not json")
        return self._payload


class StubSession:
    def __init__(self, response=None, exc=None):
        self.response = response
        self.exc = exc
        self.calls = []

    def _record(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.exc is not None:
            raise self.exc
        return self.response

    def get(self, url, **kwargs):
        return self._record(url, **kwargs)

    def post(self, url, **kwargs):
        return self._record(url, **kwargs)


def make_client(session_stub):
    client = De4pyApiClient()
    client._session = session_stub
    return client


def test_timeout_comes_from_settings():
    client = De4pyApiClient()
    assert client.timeout == settings.api_timeout


def test_get_passes_url_params_and_timeout():
    stub = StubSession(response=FakeResponse(payload={"ok": True}))
    client = make_client(stub)
    result = client.get("/api/x", params={"a": 1})
    assert result == {"ok": True}
    url, kwargs = stub.calls[0]
    assert url.endswith("/api/x")
    assert kwargs["params"] == {"a": 1}
    assert kwargs["timeout"] == client.timeout


def test_known_status_maps_to_catalog_entry():
    status = next(iter(ERROR_CODES))
    info = ERROR_CODES[status]
    client = make_client(StubSession(FakeResponse(status=status, text="boom")))
    with pytest.raises(ApiError) as err:
        client.get("/api/x")
    assert err.value.status_code == status
    assert err.value.message == info["meaning"]
    assert err.value.action == info["action"]


def test_unknown_error_prefers_detail_field():
    client = make_client(StubSession(
        FakeResponse(status=599, payload={"detail": "went bad"})))
    with pytest.raises(ApiError) as err:
        client.get("/api/x")
    assert err.value.status_code == 599
    assert err.value.message == "went bad"


def test_non_json_error_falls_back_to_text():
    client = make_client(StubSession(
        FakeResponse(status=503, text="server melted")))
    with pytest.raises(ApiError) as err:
        client.get("/api/x")
    assert "server melted" in err.value.message


def test_connection_error_is_wrapped():
    client = make_client(StubSession(exc=requests.exceptions.ConnectionError()))
    with pytest.raises(ApiError) as err:
        client.get("/api/x")
    assert err.value.status_code == 0


def test_timeout_is_wrapped_as_408():
    client = make_client(StubSession(exc=requests.exceptions.Timeout()))
    with pytest.raises(ApiError) as err:
        client.post("/api/x", json={})
    assert err.value.status_code == 408
