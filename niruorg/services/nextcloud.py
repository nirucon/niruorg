from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

SHARE_PATH = '/ocs/v2.php/apps/files_sharing/api/v1/shares'
CAPABILITIES_PATH = '/ocs/v2.php/cloud/capabilities'


class NextcloudError(RuntimeError):
    pass


class NextcloudClient:
    def __init__(
        self,
        base_url: str,
        user: str,
        secret: Callable[[], str] | str,
        opener: Callable[..., Any] | None = None,
        timeout: int = 8,
    ) -> None:
        self.base_url = (base_url or '').strip().rstrip('/')
        self.user = (user or '').strip()
        self._secret = secret
        self._opener = opener or urllib.request.urlopen
        self.timeout = timeout
        if not self.base_url or not self.user:
            raise NextcloudError('Configure the Nextcloud server and username in Settings → Integrations.')

    @property
    def secret(self) -> str:
        value = self._secret() if callable(self._secret) else self._secret
        return (value or '').strip()

    def request(self, path: str, data: dict[str, Any] | None = None, method: str | None = None) -> dict[str, Any]:
        if not path.startswith('/'):
            raise NextcloudError('Invalid Nextcloud API path.')
        password = self.secret
        if not password:
            raise NextcloudError('No Nextcloud app password is available in the system Secret Service.')
        body = urllib.parse.urlencode(data).encode() if data else None
        request = urllib.request.Request(self.base_url + path, data=body, method=method)
        request.add_header('Authorization', 'Basic ' + base64.b64encode(f'{self.user}:{password}'.encode()).decode())
        request.add_header('OCS-APIRequest', 'true')
        request.add_header('Accept', 'application/json')
        try:
            with self._opener(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode())
        except urllib.error.HTTPError as error:
            raise NextcloudError(f'Nextcloud HTTP {error.code}: {error.reason}') from error
        except urllib.error.URLError as error:
            raise NextcloudError(f'Nextcloud network error: {error.reason}') from error
        except (ValueError, OSError) as error:
            raise NextcloudError(f'Nextcloud response error: {error}') from error
        if not isinstance(payload, dict):
            raise NextcloudError('Nextcloud returned an unexpected response.')
        meta = payload.get('ocs', {}).get('meta', {}) if isinstance(payload.get('ocs'), dict) else {}
        status = meta.get('statuscode')
        if status is not None and str(status) not in ('100', '200'):
            raise NextcloudError(meta.get('message') or f'Nextcloud OCS status {status}')
        return payload

    def _data(self, payload: dict[str, Any]) -> Any:
        ocs = payload.get('ocs', {})
        return ocs.get('data') if isinstance(ocs, dict) else None

    def capabilities(self) -> dict[str, Any]:
        data = self._data(self.request(CAPABILITIES_PATH))
        return data if isinstance(data, dict) else {}

    def create_share(self, path: str, permissions: int = 1, expire: str = '', password: str = '') -> dict[str, Any]:
        if not path.startswith('/') or '..' in path.split('/'):
            raise NextcloudError('The selected path is not a valid Nextcloud path.')
        payload = {'path': path, 'shareType': '3', 'permissions': str(int(permissions)), 'format': 'json'}
        if expire:
            payload['expireDate'] = expire
        if password:
            payload['password'] = password
        data = self._data(self.request(SHARE_PATH + '?' + urllib.parse.urlencode({'format': 'json'}), payload))
        if not isinstance(data, dict) or not data.get('url'):
            raise NextcloudError((data or {}).get('message') if isinstance(data, dict) else 'Nextcloud did not return a public URL.')
        return data

    def list_shares(self, path: str | None = None) -> list[dict[str, Any]]:
        query = {'format': 'json'}
        if path:
            query['path'] = path
        payload = self.request(SHARE_PATH + '?' + urllib.parse.urlencode(query))
        data = self._data(payload)
        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]
        if isinstance(data, dict):
            return [data]
        return []

    def delete_share(self, share_id: str | int) -> None:
        self.request(f'{SHARE_PATH}/{int(share_id)}?format=json', method='DELETE')
