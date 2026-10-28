#!/usr/bin/env python3
import json
import urllib.error
import urllib.parse
from niruorg.services.nextcloud import NextcloudClient, NextcloudError

class Response:
    def __init__(self, payload): self.payload = payload
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self): return json.dumps(self.payload).encode()

class Opener:
    def __init__(self): self.calls = []; self.payload = {'ocs': {'meta': {'statuscode': 200}, 'data': {'id': 7, 'url': 'https://cloud.example/s/abc'}}}
    def __call__(self, request, timeout=None):
        self.calls.append((request, timeout))
        return Response(self.payload)

opener = Opener()
client = NextcloudClient('https://cloud.example/', 'niru', 'app-secret', opener=opener)
share = client.create_share('/Documents/report.txt', permissions=1, expire='2026-11-01', password='link-secret')
assert share['id'] == 7 and share['url'].endswith('/s/abc')
request = opener.calls[0][0]
body = urllib.parse.parse_qs(request.data.decode())
assert body['path'] == ['/Documents/report.txt']
assert body['shareType'] == ['3'] and body['permissions'] == ['1']
assert body['expireDate'] == ['2026-11-01'] and body['password'] == ['link-secret']
assert request.get_header('Authorization') == 'Basic bmlydTphcHAtc2VjcmV0'
assert opener.calls[0][1] == 8
opener.payload = {'ocs': {'meta': {'statuscode': 200}, 'data': [{'id': 4, 'share_type': 3}, {'id': 5, 'share_type': 0}]}}
assert [row['id'] for row in client.list_shares('/Documents/report.txt')] == [4, 5]
client.delete_share(4)
assert opener.calls[-1][0].get_method() == 'DELETE' and opener.calls[-1][0].full_url.endswith('/shares/4?format=json')

def failing(request, timeout=None):
    raise urllib.error.HTTPError(request.full_url, 401, 'Unauthorized', {}, None)
try:
    NextcloudClient('https://cloud.example', 'niru', 'top-secret', opener=failing).capabilities()
except NextcloudError as error:
    message = str(error)
    assert '401' in message and 'top-secret' not in message
else:
    raise AssertionError('401 must fail')
try:
    NextcloudClient('https://cloud.example', 'niru', 'top-secret', opener=lambda *a, **k: Response({'ocs': {'meta': {'statuscode': 403, 'message': 'Forbidden'}, 'data': []}})).capabilities()
except NextcloudError as error:
    assert 'Forbidden' in str(error)
else:
    raise AssertionError('OCS error must fail')
print('Nextcloud client contract OK')
