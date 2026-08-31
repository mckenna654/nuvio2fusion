import copy
import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.fusion import convert_to_fusion, manifest_url
from app.main import app


MANIFEST = 'https://metadata.example.invalid/profile/TOKEN/manifest.json?key=PRIVATE'


def source(aid='my.addon', cid='original_id', typ='movie', **extra):
    return {'provider': 'addon', 'addonId': aid, 'catalogId': cid, 'type': typ, **extra}


def collection(*sources, **folder):
    return [{'id': 'home', 'title': 'Home', 'folders': [
        {'id': 'weekend', 'title': 'Weekend', 'tileShape': 'LANDSCAPE',
         'hideTitle': True, 'sources': list(sources), **folder}]}]


def item(result):
    widgets = result['fusionConfig']['widgets'] if result['fusionConfig'] else result['previewWidgets']
    return widgets[0]['dataSource']['payload']['items'][0]


class FusionTests(unittest.TestCase):
    def test_source_query_and_multiple_providers_are_not_rebuilt(self):
        raw = collection(source(cid='private_AI_recipe', genre='Science Fiction'),
                         source('another.addon', 'tmdb.top', 'series'),
                         coverImageUrl='https://art.example/cover.jpg')
        result = convert_to_fusion(raw, {'my.addon': MANIFEST, 'another.addon': 'https://another.example/manifest.json'})
        output = result['fusionConfig']
        self.assertEqual((output['exportType'], output['exportVersion']), ('fusionWidgets', 1))
        self.assertEqual(output['requiredAddons'], [MANIFEST, 'https://another.example/manifest.json'])
        folder = item(result)
        self.assertEqual((folder['title'], folder['imageAspect'], folder['hideTitle']), ('Weekend', 'wide', True))
        self.assertEqual(folder['imageURL'], 'https://art.example/cover.jpg')
        self.assertEqual([s['payload']['catalogId'] for s in folder['dataSources']], ['movie::private_AI_recipe', 'series::tmdb.top'])
        self.assertEqual(folder['dataSources'][0]['payload']['genre'], 'Science Fiction')
        self.assertTrue(result['report']['complete'])

    def test_genre_query_uses_fixed_type_bridge_when_available(self):
        with tempfile.TemporaryDirectory() as directory:
            from app.bridge import BridgePlan, ProfileStore
            plan = BridgePlan(ProfileStore(directory), 'http://192.168.1.10:7088')
            result = convert_to_fusion(collection(source(typ='series', cid='anime', genre='Action')),
                                       {'my.addon': MANIFEST}, plan)
            data_sources = item(result)['dataSources']
            self.assertEqual(len(data_sources), 1)
            self.assertEqual(data_sources[0]['payload']['type'], 'series')
            self.assertNotIn('genre', data_sources[0]['payload'])
            self.assertEqual(result['report']['bridgedSourceReferences'], 1)
            self.assertEqual(result['bridge']['catalogs'], 1)
            self.assertIn('genre-filtered', result['report']['items'][0]['reason'])

    def test_none_genre_sentinel_remains_a_direct_unfiltered_source(self):
        with tempfile.TemporaryDirectory() as directory:
            from app.bridge import BridgePlan, ProfileStore
            plan = BridgePlan(ProfileStore(directory), 'http://192.168.1.10:7088')
            result = convert_to_fusion(collection(source(genre='None')), {'my.addon': MANIFEST}, plan)
            self.assertEqual(result['report']['bridgedSourceReferences'], 0)
            self.assertNotIn('genre', item(result)['dataSources'][0]['payload'])

    def test_missing_url_is_reported_with_a_repair_key(self):
        result = convert_to_fusion(collection(source(), source('other')))
        self.assertEqual(result['report']['missingAddons'], [{'addonId': 'my.addon', 'references': 1}, {'addonId': 'other', 'references': 1}])
        self.assertEqual(item(result)['dataSources'], [])
        self.assertEqual(result['report']['emptyFolders'], 1)
        self.assertFalse(result['report']['complete'])
        self.assertIsNone(result['fusionConfig'])
        self.assertFalse(result['report']['canExport'])

    def test_one_url_never_binds_other_addons_implicitly(self):
        result = convert_to_fusion(collection(source(), source('other')), {'my.addon': MANIFEST})
        self.assertEqual(len(item(result)['dataSources']), 1)
        self.assertEqual(result['report']['counts']['unsupported'], 1)
        self.assertTrue(result['report']['canExport'])
        self.assertEqual(result['fusionConfig']['requiredAddons'], [MANIFEST])
        self.assertFalse(result['report']['requiresPartialApproval'])

    def test_base_url_and_query_preserved(self):
        base = 'https://addon.example/TOKEN?key=PRIVATE'
        result = convert_to_fusion(collection(source(addonBaseUrl=base)))
        self.assertEqual(result['fusionConfig']['requiredAddons'], ['https://addon.example/TOKEN/manifest.json?key=PRIVATE'])
        self.assertNotIn('TOKEN', json.dumps(result['report']))
        self.assertNotIn('PRIVATE', json.dumps(result['report']))

    def test_url_addon_id_and_stremio_scheme(self):
        result = convert_to_fusion(collection(source('stremio://addon.example/config')))
        self.assertEqual(result['fusionConfig']['requiredAddons'], ['https://addon.example/config/manifest.json'])

    def test_mapping_overrides_old_base_url(self):
        result = convert_to_fusion(collection(source(addonBaseUrl='https://old.example')), {'my.addon': MANIFEST})
        self.assertEqual(result['fusionConfig']['requiredAddons'], [MANIFEST])

    def test_legacy_catalog_sources_and_authoritative_empty_sources(self):
        raw = collection()
        folder = raw[0]['folders'][0]
        folder['catalogSources'] = [source()]
        result = convert_to_fusion(raw, {'my.addon': MANIFEST})
        self.assertEqual(item(result)['dataSources'], [])
        del folder['sources']
        self.assertEqual(len(item(convert_to_fusion(raw, {'my.addon': MANIFEST}))['dataSources']), 1)

    def test_mirrored_sources_are_not_duplicated(self):
        raw = collection(source(), catalogSources=[source()])
        result = convert_to_fusion(raw, {'my.addon': MANIFEST})
        self.assertEqual(result['report']['sourceReferences'], 1)

    def test_native_tmdb_trakt_never_get_guessed_fusion_payloads(self):
        result = convert_to_fusion(collection(
            {'provider': 'tmdb', 'tmdbSourceType': 'DISCOVER', 'filters': {'withGenres': '28'}},
            {'provider': 'trakt', 'traktListId': 23}, source()), {'my.addon': MANIFEST})
        self.assertEqual(result['report']['counts'], {'preserved': 1, 'unsupported': 2})
        self.assertEqual(len(item(result)['dataSources']), 1)

    def test_unknown_source_options_not_silently_discarded(self):
        result = convert_to_fusion(collection(source(filters={'rating': 9})), {'my.addon': MANIFEST})
        self.assertEqual(item(result)['dataSources'], [])
        self.assertIsNone(result['fusionConfig'])

    def test_visual_settings_reported_instead_of_promising_fidelity(self):
        raw = collection(source(), focusGifUrl='https://art.example/focus.gif',
                         heroVideoUrl='https://art.example/video.mp4', titleLogoUrl='https://art.example/logo.png')
        raw[0]['viewMode'] = 'ROWS'
        result = convert_to_fusion(raw, {'my.addon': MANIFEST})
        fields = {f for issue in result['report']['issues'] for f in issue.get('fields', [])}
        self.assertEqual(fields, {'focusGifUrl', 'heroVideoUrl', 'titleLogoUrl', 'viewMode'})
        self.assertTrue(result['report']['sourceCoverageComplete'])
        self.assertFalse(result['report']['complete'])

    def test_order_and_duplicate_catalog_references_preserved(self):
        raw = collection(source(cid='2'), source(cid='1'), source(cid='2'))
        raw.append({'id': 'second', 'title': 'Second', 'folders': []})
        result = convert_to_fusion(raw, {'my.addon': MANIFEST})
        self.assertEqual([w['title'] for w in result['fusionConfig']['widgets']], ['Home', 'Second'])
        self.assertEqual([s['payload']['catalogId'] for s in item(result)['dataSources']], ['movie::2', 'movie::1', 'movie::2'])
        self.assertEqual(result['fusionConfig']['requiredAddons'], [MANIFEST])

    def test_media_alias_and_composite_id_are_normalized_once(self):
        result = convert_to_fusion(collection(source(cid='shows::custom/genre=Sci%20Fi', typ='TV')), {'my.addon': MANIFEST})
        self.assertEqual(item(result)['dataSources'][0]['payload']['catalogId'], 'series::custom/genre=Sci%20Fi')

    def test_conflicting_prefix_is_reported(self):
        result = convert_to_fusion(collection(source(cid='movie::custom', typ='series')), {'my.addon': MANIFEST})
        self.assertEqual(result['report']['counts']['unsupported'], 1)

    def test_raw_input_is_not_modified_and_ids_are_stable(self):
        raw = collection(source())
        del raw[0]['id']
        raw[0]['folders'].append(copy.deepcopy(raw[0]['folders'][0]))
        original = copy.deepcopy(raw)
        a = convert_to_fusion(raw, {'my.addon': MANIFEST})
        b = convert_to_fusion(raw, {'my.addon': MANIFEST})
        self.assertEqual(a, b)
        self.assertEqual(raw, original)
        folders = a['fusionConfig']['widgets'][0]['dataSource']['payload']['items']
        self.assertNotEqual(folders[0]['id'], folders[1]['id'])

    def test_user_example_sanitized_fixture_is_exact_roundtrip(self):
        raw = json.loads(Path('app/presets/fusion_example.json').read_text())
        result = convert_to_fusion(raw)
        self.assertEqual(raw, result['fusionConfig'])
        self.assertEqual((result['report']['widgets'], result['report']['folders'], result['report']['sourceReferences']), (13, 65, 308))
        self.assertTrue(result['report']['complete'])
        self.assertEqual(item(result)['dataSources'][-1]['kind'], 'localWatchlist')

    def test_existing_classic_presentation_and_zero_values_kept(self):
        raw = {'widgets': [{'id': 'catalog.row', 'title': 'Row', 'type': 'row.classic.numbered',
            'cacheTTL': 0, 'limit': 0, 'hideTitle': True,
            'presentation': {'aspectRatio': 'wide', 'cardStyle': 'large',
                             'badges': {'providers': False, 'ratings': True}, 'backgroundImageURL': 'https://art.example/bg.jpg'},
            'dataSource': {'kind': 'addonCatalog', 'payload': {'addonId': MANIFEST, 'type': 'movie', 'catalogId': 'movie::original'}}}]}
        result = convert_to_fusion(raw)
        self.assertEqual(raw['widgets'], result['fusionConfig']['widgets'])

    def test_classic_custom_type_is_excluded_without_unused_required_addon(self):
        raw = {'widgets': [{'id': 'row', 'title': 'Anime', 'type': 'row.classic',
            'dataSource': {'kind': 'addonCatalog', 'payload': {'addonId': MANIFEST, 'type': 'anime', 'catalogId': 'anime::original'}}}]}
        result = convert_to_fusion(raw)
        self.assertIsNone(result['fusionConfig'])
        self.assertEqual(result['previewWidgets'], [])
        self.assertEqual(result['report']['skippedWidgets'], 1)

    def test_incompatible_type_does_not_poison_other_folder_sources(self):
        for typ in ('all', 'ALL', 'anime'):
            with self.subTest(typ=typ):
                raw = collection(source(cid='movies'), source(cid='mixed', typ=typ),
                                 source(cid='shows', typ='series'))
                original = copy.deepcopy(raw)
                result = convert_to_fusion(raw, {'my.addon': MANIFEST})
                self.assertEqual([s['payload']['catalogId'] for s in item(result)['dataSources']],
                                 ['movie::movies', 'series::shows'])
                self.assertEqual(result['report']['counts'], {'preserved': 2, 'unsupported': 1})
                self.assertEqual(result['report']['incompatibleCatalogs'], 1)
                self.assertEqual(result['report']['emptyFolders'], 0)
                self.assertTrue(result['report']['canExport'])
                self.assertFalse(result['report']['sourceCoverageComplete'])
                self.assertFalse(result['report']['requiresPartialApproval'])
                self.assertIn('query was not rewritten', result['report']['items'][1]['reason'])
                self.assertTrue(any('incompatible source' in w for w in result['report']['warnings']))
                self.assertEqual(raw, original)

    def test_incompatible_only_folder_stays_visible_without_an_unused_addon(self):
        raw = collection(source(typ='all', genre='None'))
        result = convert_to_fusion(raw, {'my.addon': MANIFEST})
        self.assertIsNone(result['fusionConfig'])
        self.assertEqual(item(result)['dataSources'], [])
        self.assertEqual(item(result)['title'], 'Weekend')
        self.assertEqual(result['report']['requiredAddonCount'], 0)
        self.assertEqual(result['report']['emptyFolders'], 1)
        self.assertEqual(result['report']['incompatibleCatalogs'], 1)
        self.assertNotIn('TOKEN', json.dumps(result['report']))

    def test_older_fusion_export_can_be_repaired_before_native_import(self):
        raw = {'exportType': 'fusionWidgets', 'exportVersion': 1, 'requiredAddons': [MANIFEST],
               'widgets': [{'id': 'home', 'title': 'Home', 'type': 'collection.row',
                   'dataSource': {'kind': 'collection', 'payload': {'items': [
                       {'id': 'mixed', 'title': 'Mixed folder', 'imageAspect': 'wide',
                        'dataSources': [
                            {'kind': 'addonCatalog', 'payload': {'addonId': MANIFEST, 'type': 'movie', 'catalogId': 'movie::movies', 'genre': 'None'}},
                            {'kind': 'addonCatalog', 'payload': {'addonId': MANIFEST, 'type': 'all', 'catalogId': 'all::mixed'}},
                            {'kind': 'addonCatalog', 'payload': {'addonId': MANIFEST, 'type': 'series', 'catalogId': 'series::shows'}},
                            {'kind': 'localWatchlist', 'payload': {}}]}]}}}]}
        expected = copy.deepcopy(raw)
        del expected['widgets'][0]['dataSource']['payload']['items'][0]['dataSources'][1]
        result = convert_to_fusion(raw)
        self.assertEqual(result['fusionConfig'], expected)
        self.assertEqual(result['report']['incompatibleCatalogs'], 1)
        self.assertTrue(result['report']['canExport'])

    def test_incompatible_only_addon_not_required_when_other_sources_survive(self):
        raw = collection(source(), source('mixed.addon', typ='all'))
        result = convert_to_fusion(raw, {'my.addon': MANIFEST,
                                       'mixed.addon': 'https://mixed.example/manifest.json'})
        self.assertEqual(result['fusionConfig']['requiredAddons'], [MANIFEST])
        self.assertEqual(len(item(result)['dataSources']), 1)

    def test_unknown_widget_is_not_marked_complete(self):
        result = convert_to_fusion({'widgets': [{'id': 'future', 'type': 'future.widget'}]})
        self.assertFalse(result['report']['complete'])
        self.assertEqual(result['report']['skippedWidgets'], 1)

    def test_full_setup_extras_are_reported_not_leaked(self):
        result = convert_to_fusion({'collections': collection(source()), 'accounts': {'key': 'PRIVATE'}, 'addons': []}, {'my.addon': MANIFEST})
        self.assertEqual(result['report']['issues'][0]['fields'], ['accounts', 'addons'])
        self.assertNotIn('PRIVATE', json.dumps(result['report']))
        self.assertNotIn('accounts', result['fusionConfig'])

    def test_url_validation_and_error_redaction(self):
        for value in ('file:///tmp/manifest.json', 'javascript:alert(1)', 'https://user:PRIVATE@example.com/manifest.json',
                      'https://example.com/a', 'https://example.com/manifest.json#PRIVATE', 'https://example.com:bad/manifest.json'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                manifest_url(value)
        result = convert_to_fusion(collection(source(addonBaseUrl='file:///PRIVATE')))
        self.assertNotIn('PRIVATE', json.dumps(result))

    def test_invalid_formats_do_not_report_success(self):
        for raw in ({'catalogs': []}, {'config': {}}, {'widgets': [], 'exportVersion': 2},
                    {'collections': 'bad'}, collection(sources='bad'), ['bad']):
            with self.subTest(raw=raw), self.assertRaises((ValueError, TypeError)):
                convert_to_fusion(raw)

    def test_optional_addon_can_be_skipped_without_blocking_connected_sources(self):
        # The native Nuvio export records logical IDs but drops install URLs.
        # Keep two instances separate even when one supplies almost every source.
        raw = collection(*[source('aio-metadata', f'list.{i}', genre='None') for i in range(341)],
                         *[source('com.example.second.nuvio', f'custom.{i}', typ='series') for i in range(6)])
        original = copy.deepcopy(raw)
        missing = convert_to_fusion(raw)
        self.assertEqual(missing['report']['missingAddons'], [
            {'addonId': 'aio-metadata', 'references': 341},
            {'addonId': 'com.example.second.nuvio', 'references': 6}])
        self.assertIsNone(missing['fusionConfig'])
        mapped = {'aio-metadata': MANIFEST}
        still_missing = convert_to_fusion(raw, mapped)
        self.assertEqual(still_missing['report']['counts'], {'preserved': 341, 'unsupported': 6})
        self.assertTrue(still_missing['report']['canExport'])
        self.assertFalse(still_missing['report']['requiresPartialApproval'])
        self.assertFalse(still_missing['report']['complete'])
        self.assertEqual(still_missing['fusionConfig']['requiredAddons'], [MANIFEST])
        self.assertEqual(len(item(still_missing)['dataSources']), 341)
        self.assertTrue(all(s['payload']['addonId'] == MANIFEST for s in item(still_missing)['dataSources']))
        self.assertEqual(still_missing['report']['missingAddons'], [{'addonId': 'com.example.second.nuvio', 'references': 6}])
        self.assertTrue(any('optional' in warning for warning in still_missing['report']['warnings']))
        second = 'https://second.example/config/manifest.json'
        mapped['com.example.second.nuvio'] = second
        repaired = convert_to_fusion(raw, mapped)
        self.assertEqual(repaired['fusionConfig']['requiredAddons'], [MANIFEST, second])
        self.assertEqual(repaired['report']['counts'], {'preserved': 347, 'unsupported': 0})
        self.assertEqual(repaired['report']['emptyFolders'], 0)
        self.assertTrue(repaired['report']['canExport'])
        self.assertFalse(repaired['report']['requiresPartialApproval'])
        for before, after in zip(raw[0]['folders'][0]['sources'], item(repaired)['dataSources']):
            self.assertEqual(after['payload']['addonId'], mapped[before['addonId']])
            self.assertEqual(after['payload']['catalogId'], f"{before['type']}::{before['catalogId']}")
        self.assertEqual(raw, original)
        self.assertNotIn('TOKEN', json.dumps(repaired['report']))

    def test_already_empty_fusion_file_cannot_be_exported_as_repaired(self):
        raw = {'widgets': [{'id': 'empty', 'title': 'Empty', 'type': 'collection.row',
            'dataSource': {'kind': 'collection', 'payload': {'items': [
                {'id': 'folder', 'title': 'Folder', 'dataSources': []}]}}}]}
        result = convert_to_fusion(raw, {'aio-metadata': MANIFEST})
        self.assertIsNone(result['fusionConfig'])
        self.assertFalse(result['report']['canExport'])
        self.assertIn('original Nuvio', result['report']['exportBlockReason'])

    def test_invalid_embedded_instance_url_gets_a_repair_field(self):
        raw = collection(source('aio-metadata', addonBaseUrl='file:///PRIVATE'))
        result = convert_to_fusion(raw)
        self.assertIsNone(result['fusionConfig'])
        self.assertEqual(result['report']['missingAddons'], [{'addonId': 'aio-metadata', 'references': 1}])
        self.assertNotIn('PRIVATE', json.dumps(result))
        repaired = convert_to_fusion(raw, {'aio-metadata': MANIFEST})
        self.assertTrue(repaired['report']['canExport'])

    def test_partial_source_loss_and_visual_loss_are_warnings_without_approval_gates(self):
        native = {'provider': 'tmdb', 'tmdbSourceType': 'DISCOVER'}
        partial = convert_to_fusion(collection(source(addonBaseUrl=MANIFEST), native))
        self.assertTrue(partial['report']['canExport'])
        self.assertFalse(partial['report']['requiresPartialApproval'])
        visual = convert_to_fusion(collection(source(addonBaseUrl=MANIFEST), heroVideoUrl='https://art.example/video'))
        self.assertFalse(visual['report']['complete'])
        self.assertTrue(visual['report']['canExport'])
        self.assertFalse(visual['report']['requiresPartialApproval'])

    def test_optional_addon_only_folder_is_reported_without_blocking_other_folders(self):
        raw = collection(source('aio-metadata'))
        raw[0]['folders'].append({'id': 'optional', 'title': 'Optional', 'sources': [source('optional.addon')]})
        result = convert_to_fusion(raw, {'aio-metadata': MANIFEST})
        self.assertTrue(result['report']['canExport'])
        self.assertEqual(result['report']['emptyFolders'], 1)
        self.assertFalse(result['report']['requiresPartialApproval'])
        self.assertEqual(result['fusionConfig']['requiredAddons'], [MANIFEST])


class FusionApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_conversion_endpoint_and_page(self):
        response = self.client.post('/api/fusion/convert', json={'export_data': collection(source()), 'addon_urls': {'my.addon': MANIFEST}})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['fusionConfig']['exportType'], 'fusionWidgets')
        self.assertIn('fusion.js', self.client.get('/').text)

    def test_bad_request_never_echoes_mapping_secrets(self):
        for mapping in ({'my.addon': 99}, {'my.addon': 'file:///PRIVATE'}):
            response = self.client.post('/api/fusion/convert', json={'export_data': collection(source()), 'addon_urls': mapping})
            self.assertIn(response.status_code, (400, 422))
            self.assertNotIn('PRIVATE', response.text)

    def test_example_route_uses_sanitized_url_only(self):
        response = self.client.get('/api/presets/fusion')
        raw = response.json()['rawData']
        self.assertEqual(raw['requiredAddons'], ['https://addon.example.invalid/profile/manifest.json'])
        self.assertNotIn('eyJhbG', response.text)

    def test_malformed_source_shape_is_a_safe_400(self):
        response = self.client.post('/api/fusion/convert', json={'export_data': {'widgets': [
            {'type': 'collection.row', 'dataSource': {'kind': 'collection', 'payload': 'PRIVATE'}}]}})
        self.assertEqual(response.status_code, 400)
        self.assertNotIn('PRIVATE', response.text)

    def test_api_allows_connected_sources_with_optional_addon_missing(self):
        request = {'export_data': collection(source('aio-metadata'), source('optional.addon'))}
        response = self.client.post('/api/fusion/convert', json=request)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()['fusionConfig'])
        self.assertFalse(response.json()['report']['canExport'])
        request['addon_urls'] = {'aio-metadata': MANIFEST}
        fixed = self.client.post('/api/fusion/convert', json=request).json()
        self.assertTrue(fixed['report']['canExport'])
        self.assertEqual(fixed['fusionConfig']['requiredAddons'], [MANIFEST])
        self.assertEqual(fixed['report']['counts'], {'preserved': 1, 'unsupported': 1})
        self.assertEqual(fixed['report']['missingAddons'], [{'addonId': 'optional.addon', 'references': 1}])
        self.assertFalse(fixed['report']['requiresPartialApproval'])
