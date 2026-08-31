import copy
import json
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
    return result['fusionConfig']['widgets'][0]['dataSource']['payload']['items'][0]


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

    def test_missing_url_is_reported_with_a_repair_key(self):
        result = convert_to_fusion(collection(source(), source('other')))
        self.assertEqual(result['report']['missingAddons'], [{'addonId': 'my.addon', 'references': 1}, {'addonId': 'other', 'references': 1}])
        self.assertEqual(item(result)['dataSources'], [])
        self.assertEqual(result['report']['emptyFolders'], 1)
        self.assertFalse(result['report']['complete'])

    def test_one_url_never_binds_other_addons_implicitly(self):
        result = convert_to_fusion(collection(source(), source('other')), {'my.addon': MANIFEST})
        self.assertEqual(len(item(result)['dataSources']), 1)
        self.assertEqual(result['report']['counts']['unsupported'], 1)

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
        self.assertEqual(result['fusionConfig']['requiredAddons'], [])

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
        self.assertEqual(result['fusionConfig']['widgets'], [])
        self.assertEqual(result['fusionConfig']['requiredAddons'], [])
        self.assertEqual(result['report']['skippedWidgets'], 1)

    def test_custom_media_type_supported_in_collection(self):
        result = convert_to_fusion(collection(source(typ='anime')), {'my.addon': MANIFEST})
        self.assertEqual(item(result)['dataSources'][0]['payload']['type'], 'anime')

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
