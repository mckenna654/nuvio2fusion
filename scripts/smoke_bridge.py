"""Check profile creation and persistence across actual container replacement."""
import json
from pathlib import Path
import sys
import urllib.request


def request(base, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base + path, data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.load(response)


mode, base, state_file = sys.argv[1:]
if mode == 'create':
    raw = [{'id': 'demo', 'title': 'Demo', 'folders': [{'id': 'mixed', 'title': 'Mixed',
           'sources': [{'addonId': 'demo', 'type': 'all', 'catalogId': 'mixed'}]}]}]
    converted = request(base, '/api/fusion/convert', {'export_data': raw,
        'addon_urls': {'demo': 'https://addon.example.invalid/manifest.json'}, 'bridge_url': base})
    assert converted['report']['bridgedSourceReferences'] == 1
    assert converted['report']['emptyFolders'] == 0
    Path(state_file).write_text(json.dumps({'path': converted['bridge']['manifestUrl'].removeprefix(base)}))
saved = json.loads(Path(state_file).read_text())
manifest = request(base, saved['path'])
assert len(manifest['catalogs']) == 2
assert {c['type'] for c in manifest['catalogs']} == {'movie', 'series'}
assert 'example.invalid' not in json.dumps(manifest)
print('Compatibility profile creation/persistence check passed.')
