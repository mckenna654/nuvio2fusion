"""Offline client-layout conversion; never reinterpret an addon's catalog recipe.

Contracts and compatibility limits are documented in docs/FUSION.md.
"""
from __future__ import annotations

import copy
import re
import uuid
from collections import Counter
from urllib.parse import urlsplit, urlunsplit


SHAPES = {'POSTER': 'poster', 'LANDSCAPE': 'wide', 'SQUARE': 'square'}
CLASSIC_TYPES = {'row.classic', 'row.classic.numbered'}
TYPE_ALIASES = {'movies': 'movie', 'tv': 'series', 'show': 'series', 'shows': 'series'}


def string(value):
    return value.strip() if isinstance(value, str) else ''


def manifest_url(value, *, base=False):
    """Validate without fetching. Preserve private path/query bytes in the export."""
    value = string(value)
    if value.startswith('stremio://'):
        value = 'https://' + value[10:]
    if not value or re.search(r'\s', value):
        raise ValueError('A full HTTP(S) addon URL is required.')
    parts = urlsplit(value)
    if (parts.scheme not in {'http', 'https'} or not parts.hostname or
            parts.username or parts.password or parts.fragment):
        raise ValueError('Invalid addon URL.')
    parts.port  # Also validate malformed ports without exposing the value.
    path = parts.path.rstrip('/')
    if not path.endswith('/manifest.json'):
        if not base:
            raise ValueError('Use the full install URL ending in /manifest.json.')
        path += '/manifest.json'
    return urlunsplit(parts._replace(path=path))


def is_web_url(value):
    try:
        parts = urlsplit(string(value))
        return parts.scheme in {'http', 'https'} and bool(parts.hostname) and not (parts.username or parts.password)
    except ValueError:
        return False


class FusionConversion:
    def __init__(self, addon_urls=None):
        self.addon_urls = {}
        for key, value in (addon_urls or {}).items():
            if not string(key):
                raise ValueError('Addon mapping keys must not be empty.')
            self.addon_urls[key] = manifest_url(value)
        self.records = []
        self.issues = []
        self.missing = Counter()
        self.ids = set()
        self.required = {}
        self.empty_folders = 0
        self.skipped_widgets = 0

    def issue(self, path, code, message, fields=None):
        self.issues.append({'path': path, 'code': code, 'message': message,
                            **({'fields': fields} if fields else {})})

    def identifier(self, value, path, prefix=''):
        ident = string(value)
        if prefix and not ident.startswith(prefix):
            ident = prefix + ident if ident else ''
        if not ident or ident in self.ids:
            ident = prefix + str(uuid.uuid5(uuid.NAMESPACE_URL, 'nuvio2fusion/fusion/' + path))
            self.issue(path, 'generated_id', 'A missing or duplicate ID was replaced with a stable unique ID.')
        self.ids.add(ident)
        return ident

    def title(self, value, path):
        if string(value):
            return value  # Preserve intentional spelling/spacing.
        self.issue(path, 'missing_title', 'A missing title was replaced with Untitled.')
        return 'Untitled'

    def unavailable_fields(self, raw, allowed, path):
        fields = sorted(k for k, v in raw.items() if k not in allowed and v not in (None, '', [], {}))
        if fields:
            self.issue(path, 'unmapped_settings', 'These Nuvio settings have no verified mapping in Fusion widget v1.', fields)

    def record(self, raw, path, title, status, reason, source=None):
        if len(self.records) >= 10000:
            raise ValueError('Too many source references.')
        # Do not put private addon URLs or native query contents in the report.
        cid = string(raw.get('catalogId'))
        if '://' in cid:
            cid = '[URL omitted]'
        record = {'path': path, 'name': string(raw.get('title')) or string(raw.get('catalogName')) or title,
                  'sourceId': cid, 'sourceType': string(raw.get('type') or raw.get('provider') or raw.get('kind')),
                  'status': status, 'reason': reason}
        self.records.append(record)
        return source

    def resolve_addon(self, raw):
        aid = string(raw.get('addonId'))
        # An explicit mapping can correct an obsolete install, but never falls
        # back to another addon's URL merely because there is only one mapping.
        if aid in self.addon_urls:
            return self.addon_urls[aid]
        for field, base in (('manifestUrl', False), ('addonBaseUrl', True)):
            if string(raw.get(field)):
                return manifest_url(raw[field], base=base)
        if aid.startswith(('https://', 'http://', 'stremio://')):
            return manifest_url(aid, base=True)
        if aid:
            self.missing[aid] += 1
        return None

    def addon_source(self, raw, path, title, *, fusion=False):
        cid, typ = string(raw.get('catalogId')), string(raw.get('type'))
        if not cid or not typ:
            return self.record(raw, path, title, 'unsupported', 'Missing catalog ID or media type.')
        try:
            url = self.resolve_addon(raw)
        except ValueError:
            aid = string(raw.get('addonId'))
            if aid and '://' not in aid:
                self.missing[aid] += 1
            return self.record(raw, path, title, 'unsupported', 'Invalid addon URL. Supply a full manifest URL for this addon.')
        if not url:
            return self.record(raw, path, title, 'unsupported', 'Addon not connected; this source is omitted. Supply its manifest URL only if you want to include it.')
        if not fusion:
            allowed = {'provider', 'addonId', 'addonBaseUrl', 'manifestUrl', 'addonName',
                       'type', 'catalogId', 'genre', 'catalogName', 'title', 'name', 'aiometadata'}
            if any(k not in allowed and v not in (None, '', {}, []) for k, v in raw.items()):
                return self.record(raw, path, title, 'unsupported', 'Additional source options have no verified Fusion mapping; source omitted to avoid changing its query.')
        typ = TYPE_ALIASES.get(typ.lower(), typ.lower())
        if '::' in cid:
            prefix, cid = cid.split('::', 1)
            prefix = TYPE_ALIASES.get(prefix.lower(), prefix.lower())
            if prefix != typ:
                return self.record(raw, path, title, 'unsupported', 'Catalog prefix and media type disagree; resolve the type before exporting.')
        if not cid or not re.fullmatch(r'[a-z0-9_-]+', typ):
            return self.record(raw, path, title, 'unsupported', 'Invalid catalog ID or media type.')
        if raw.get('genre') is not None and not isinstance(raw['genre'], str):
            return self.record(raw, path, title, 'unsupported', 'Genre must be text.')
        payload = copy.deepcopy(raw) if fusion else {}
        payload.update(addonId=url, catalogId=f'{typ}::{cid}', type=typ)
        if not fusion and string(raw.get('genre')):
            payload['genre'] = raw['genre']
        self.required[url] = None
        return self.record(raw, path, title, 'preserved', 'Original addon and catalog retained; no catalog recipe was changed.',
                           {'kind': 'addonCatalog', 'payload': payload})

    def nuvio_source(self, raw, path, title):
        if not isinstance(raw, dict):
            return self.record({}, path, title, 'unsupported', 'Source must be an object.')
        provider = string(raw.get('provider') or 'addon').lower()
        if provider != 'addon':
            return self.record(raw, path, title, 'unsupported',
                'Nuvio-native source has no verified direct Fusion mapping. Recreate it in Fusion or expose it through an addon first.')
        return self.addon_source(raw, path, title)

    def fusion_source(self, raw, path, title):
        if not isinstance(raw, dict) or not string(raw.get('kind')) or not isinstance(raw.get('payload'), dict):
            return self.record({}, path, title, 'unsupported', 'Malformed Fusion data source.')
        if raw['kind'] == 'addonCatalog':
            return self.addon_source(raw['payload'], path, title, fusion=True)
        if raw['kind'] == 'collection':
            return self.record(raw, path, title, 'unsupported', 'Nested collections are not supported in a folder source.')
        # This source already came from Fusion, so retain its native payload.
        # We deliberately do not manufacture one from a Nuvio TMDB/Trakt recipe.
        return self.record(raw, path, title, 'preserved', 'Existing Fusion-native source retained; its account data is not transferred.', copy.deepcopy(raw))

    def nuvio_collection(self, raw, path):
        if not isinstance(raw, dict) or not isinstance(raw.get('folders'), list):
            raise ValueError('Expected a Nuvio collection with folders.')
        title = self.title(raw.get('title'), path)
        widget = {'id': self.identifier(raw.get('id'), path, 'collection.'), 'title': title,
                  'type': 'collection.row', 'dataSource': {'kind': 'collection', 'payload': {'items': []}}}
        if isinstance(raw.get('hideTitle'), bool):
            widget['hideTitle'] = raw['hideTitle']
        self.unavailable_fields(raw, {'id', 'title', 'hideTitle', 'folders'}, path)
        for j, folder in enumerate(raw['folders']):
            fp = f'{path}.folders[{j}]'
            if not isinstance(folder, dict):
                raise ValueError('Expected a folder object.')
            ft = self.title(folder.get('title'), fp)
            shape = string(folder.get('tileShape') or 'SQUARE').upper()
            if shape not in SHAPES:
                self.issue(fp, 'unknown_shape', 'Unknown tile shape replaced with square.')
                shape = 'SQUARE'
            item = {'id': self.identifier(folder.get('id'), fp), 'title': ft,
                    'hideTitle': folder.get('hideTitle') is True,
                    'imageAspect': SHAPES[shape], 'dataSources': []}
            if string(folder.get('coverImageUrl')):
                if is_web_url(folder['coverImageUrl']):
                    item['imageURL'] = folder['coverImageUrl']
                else:
                    self.issue(fp, 'invalid_artwork', 'Non-HTTP(S) artwork URL omitted.')
            self.unavailable_fields(folder, {'id', 'title', 'hideTitle', 'tileShape', 'coverImageUrl',
                                             'sources', 'catalogSources'}, fp)
            # Nuvio writes catalogSources as a legacy mirror. A present sources
            # array is authoritative, even when it is deliberately empty.
            sources = folder.get('sources')
            if sources is None:
                sources = folder.get('catalogSources', [])
            if not isinstance(sources, list):
                raise ValueError('Expected a sources array.')
            for k, raw_source in enumerate(sources):
                source = self.nuvio_source(raw_source, f'{fp}.sources[{k}]', ft)
                if source:
                    item['dataSources'].append(source)
            if not item['dataSources']:
                self.empty_folders += 1
                self.issue(fp, 'empty_folder', 'Folder artwork and position retained, but it has no usable sources.')
            widget['dataSource']['payload']['items'].append(item)
        return widget

    def fusion_widget(self, raw, path):
        if not isinstance(raw, dict):
            raise ValueError('Expected a widget object.')
        typ = raw.get('type')
        if typ not in CLASSIC_TYPES | {'collection.row'}:
            self.issue(path, 'unsupported_widget', 'Widget type is not covered by the verified Fusion widget v1 contract; omitted.')
            self.skipped_widgets += 1
            return None
        widget = copy.deepcopy(raw)
        widget['id'] = self.identifier(raw.get('id'), path)
        widget['title'] = self.title(raw.get('title'), path)
        ds = raw.get('dataSource')
        if typ == 'collection.row':
            if not isinstance(ds, dict) or ds.get('kind') != 'collection' or not isinstance(ds.get('payload', {}).get('items'), list):
                raise ValueError('Invalid collection widget.')
            for j, item in enumerate(widget['dataSource']['payload']['items']):
                fp = f'{path}.items[{j}]'
                if not isinstance(item, dict) or not isinstance(item.get('dataSources'), list):
                    raise ValueError('Invalid collection item.')
                item['id'] = self.identifier(item.get('id'), fp)
                item['title'] = self.title(item.get('title'), fp)
                if item.get('imageAspect') not in {'poster', 'wide', 'square'}:
                    item['imageAspect'] = 'square'
                    self.issue(fp, 'unknown_shape', 'Missing or invalid image aspect replaced with square.')
                sources = [self.fusion_source(s, f'{fp}.sources[{k}]', item['title']) for k, s in enumerate(item['dataSources'])]
                item['dataSources'] = [s for s in sources if s]
                if not item['dataSources']:
                    self.empty_folders += 1
                    self.issue(fp, 'empty_folder', 'Folder retained without usable sources.')
        else:
            # Fusion classic addon rows require movie/series. Reject before
            # recording success or adding an unused required addon.
            if (isinstance(ds, dict) and ds.get('kind') == 'addonCatalog' and
                    isinstance(ds.get('payload'), dict) and
                    TYPE_ALIASES.get(string(ds['payload'].get('type')).lower(), string(ds['payload'].get('type')).lower()) not in {'movie', 'series'}):
                self.record(ds['payload'], path + '.source', widget['title'], 'unsupported', 'Fusion classic rows require movie or series. Place this catalog in a collection folder.')
                self.skipped_widgets += 1
                return None
            source = self.fusion_source(ds, path + '.source', widget['title'])
            if not source:
                self.skipped_widgets += 1
                return None
            widget['dataSource'] = source
            for key, default in (('limit', 20), ('cacheTTL', 1800)):
                if key not in widget:
                    widget[key] = default
                elif type(widget[key]) is not int or widget[key] < 0:
                    raise ValueError('Invalid classic row limit/cacheTTL.')
            if 'presentation' not in widget:
                widget['presentation'] = {'aspectRatio': 'poster', 'cardStyle': 'medium',
                                          'badges': {'providers': False, 'ratings': True}}
            presentation = widget['presentation']
            if (not isinstance(presentation, dict) or presentation.get('aspectRatio') not in {'poster', 'wide', 'square'} or
                    presentation.get('cardStyle') not in {'small', 'medium', 'large'} or
                    not isinstance(presentation.get('badges'), dict)):
                raise ValueError('Invalid row presentation.')
        return widget

    def convert(self, data):
        fusion = False
        envelope_fields = []
        if isinstance(data, dict) and 'widgets' in data:
            if data.get('exportType', 'fusionWidgets') != 'fusionWidgets' or type(data.get('exportVersion', 1)) is not int or data.get('exportVersion', 1) != 1:
                raise ValueError('Unsupported Fusion export version.')
            rows, fusion = data['widgets'], True
        elif isinstance(data, dict) and 'collections' in data:
            rows = data['collections']
            envelope_fields = sorted(set(data) - {'collections', 'version', 'exportVersion', 'exportedAt', 'exportType'})
        elif isinstance(data, dict) and 'folders' in data:
            rows = [data]
        elif isinstance(data, list):
            rows = data
            fusion = bool(rows) and all(isinstance(r, dict) and 'dataSource' in r for r in rows)
        else:
            raise ValueError('Use a Nuvio collections export or Fusion widgets export.')
        if not isinstance(rows, list) or len(rows) > 1000:
            raise ValueError('Expected at most 1000 collections/widgets.')
        if envelope_fields:
            self.issue('root', 'setup_settings', 'Only collections are converted. Other setup/account/player settings are not a Fusion widget layout.', envelope_fields)
        widgets = []
        for i, row in enumerate(rows):
            path = f'{"widgets" if fusion else "collections"}[{i}]'
            widget = self.fusion_widget(row, path) if fusion else self.nuvio_collection(row, path)
            if widget:
                widgets.append(widget)
        counts = Counter(r['status'] for r in self.records)
        folders = sum(len(w['dataSource']['payload']['items']) for w in widgets if w['type'] == 'collection.row')
        warnings = [
            'This converts layout only. Referenced addons must remain installed and accessible in Fusion; their catalogs are not copied or hosted by this tool.',
            'Addon URLs can contain private tokens. Keep the exported file private; the report omits addon URLs.',
            'Artwork stays at its original URL. No artwork, catalogs, accounts, watch history or library contents are copied.',
            'Output targets Fusion widget export v1. Structural validation is not a live import or catalog-availability check.',
        ]
        if not fusion:
            warnings.append('Nuvio focus GIFs, hero artwork/video, title logos and collection view settings have no verified v1 mapping; see the per-entry issues.')
        if self.missing:
            warnings.append(f'{len(self.missing)} addons are not connected; {sum(self.missing.values())} catalog references are omitted. Connecting these addons is optional. Sources from connected addons remain exportable.')
        if self.empty_folders:
            warnings.append(f'{self.empty_folders} folders have no usable sources. Installing an addon later cannot restore omitted catalog references; repair the original Nuvio export and convert again.')
        block_reason = ''
        if not counts['preserved']:
            block_reason = 'No usable catalog sources remain. Use the original Nuvio collections export and resolve the source issues; a layout-only Fusion file cannot recover missing catalogs.'
        elif not widgets:
            block_reason = 'No supported widgets remain to export.'
        can_export = not block_reason
        complete = can_export and counts['unsupported'] == 0 and not self.issues and self.skipped_widgets == 0
        return {'success': True, 'fusionConfig': {'exportType': 'fusionWidgets', 'exportVersion': 1,
                    'requiredAddons': list(self.required), 'widgets': widgets} if can_export else None,
                # Keep a diagnostic preview when no usable content remains.
                'previewWidgets': widgets if not can_export else [],
                'report': {'inputFormat': 'Fusion widgets' if fusion else 'Nuvio collections',
                    'complete': complete, 'sourceCoverageComplete': counts['unsupported'] == 0,
                    'canExport': can_export, 'exportBlockReason': block_reason,
                    'requiresPartialApproval': False,  # Compatibility field; omissions are warnings only.
                    'widgets': len(widgets), 'folders': folders, 'emptyFolders': self.empty_folders,
                    'skippedWidgets': self.skipped_widgets, 'sourceReferences': len(self.records),
                    'counts': {k: counts[k] for k in ('preserved', 'unsupported')},
                    'requiredAddonCount': len(self.required),
                    'requiredAddonHosts': list(dict.fromkeys(urlsplit(u).hostname for u in self.required)),
                    'missingAddons': [{'addonId': aid, 'references': n} for aid, n in self.missing.items()],
                    'items': self.records, 'issues': self.issues, 'warnings': warnings}}


def convert_to_fusion(export_data, addon_urls=None):
    return FusionConversion(addon_urls).convert(export_data)
