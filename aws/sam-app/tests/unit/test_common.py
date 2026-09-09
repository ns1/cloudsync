"""Tests for shared_layer/common.py — token handling and UnauthorizedException."""
import sys
import os
import pytest
from unittest.mock import MagicMock, patch
from requests import Response

# shared_layer is a Lambda layer — add it to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src/shared_layer'))

from common import UnauthorizedException, get_tokens_using_api_key, insert_token


def make_response(status_code, text='{"data": {"access_token": "at", "refresh_token": "rt"}}'):
    res = Response()
    res.status_code = status_code
    res._content = text.encode()
    return res


class MockSecretHandler:
    def __init__(self, ns1_key=None, cs_key=None):
        self._secrets = {}
        if ns1_key:
            self._secrets['CloudSync/NS1APIKey'] = ns1_key
        if cs_key:
            self._secrets['CloudSync/CloudSyncAPIKey'] = cs_key

    def get_if_present(self, name):
        return self._secrets.get(name)

    def upsert(self, name, value):
        self._secrets[name] = value


class TestGetTokensUsingApiKey:
    def test_success_returns_response(self):
        secret_handler = MockSecretHandler(ns1_key='valid-key')
        with patch('common.requests.post', return_value=make_response(200)) as mock_post:
            res = get_tokens_using_api_key('https://endpoint/token', secret_handler)
            assert res.status_code == 200
            mock_post.assert_called_once()

    def test_401_raises_unauthorized_exception(self):
        secret_handler = MockSecretHandler(ns1_key='expired-key')
        with patch('common.requests.post', return_value=make_response(401, '{"error":"user unauthorized"}')):
            with pytest.raises(UnauthorizedException) as exc:
                get_tokens_using_api_key('https://endpoint/token', secret_handler)
            assert '401' in str(exc.value)

    def test_403_raises_unauthorized_exception(self):
        secret_handler = MockSecretHandler(ns1_key='bad-key')
        with patch('common.requests.post', return_value=make_response(403, '{"error":"forbidden"}')):
            with pytest.raises(UnauthorizedException):
                get_tokens_using_api_key('https://endpoint/token', secret_handler)

    def test_500_raises_generic_exception(self):
        secret_handler = MockSecretHandler(ns1_key='valid-key')
        with patch('common.requests.post', return_value=make_response(500, 'internal error')):
            with pytest.raises(Exception) as exc:
                get_tokens_using_api_key('https://endpoint/token', secret_handler)
            # Must NOT be an UnauthorizedException — SQS should retry
            assert not isinstance(exc.value, UnauthorizedException)

    def test_no_api_key_raises_exception(self):
        secret_handler = MockSecretHandler()
        with pytest.raises(Exception, match='API keys are not set'):
            get_tokens_using_api_key('https://endpoint/token', secret_handler)


class TestInsertToken:
    """Tests for the insert_token decorator — specifically the 4xx fast-path on refresh."""

    def _make_handler(self):
        """Returns a dns_post-like function wrapped with insert_token."""
        import constants

        @insert_token
        def fake_post(endpoint, msg, headers):
            r = Response()
            r.status_code = 202
            r._content = b''
            return r

        return fake_post

    def test_refresh_token_401_raises_unauthorized_exception(self):
        """4xx on the refresh token path raises UnauthorizedException immediately
        without falling through to the API key path."""
        import constants
        secret_handler = MockSecretHandler(ns1_key='valid-key')
        secret_handler.upsert(constants.ACCESS_TOKEN_NAME, None)
        secret_handler.upsert(constants.REFRESH_TOKEN_NAME, 'old-refresh-token')

        fake_post = self._make_handler()

        with patch('common.requests.post', return_value=make_response(401, '{"error":"user unauthorized"}')):
            with pytest.raises(UnauthorizedException):
                fake_post('https://endpoint', {}, secret_handler)

    def test_refresh_token_500_falls_through_to_api_key(self):
        """5xx on the refresh token path falls through to the API key path (tokens=None path)."""
        import constants
        secret_handler = MockSecretHandler(ns1_key='valid-key')
        secret_handler.upsert(constants.ACCESS_TOKEN_NAME, None)
        secret_handler.upsert(constants.REFRESH_TOKEN_NAME, 'old-refresh-token')

        fake_post = self._make_handler()

        responses = [
            make_response(500, 'error'),            # refresh token → 500
            make_response(200),                     # api key → 200
        ]
        with patch('common.requests.post', side_effect=responses):
            # Should succeed — fell through to API key path
            result = fake_post('https://endpoint', {}, secret_handler)
            assert result.status_code == 202
