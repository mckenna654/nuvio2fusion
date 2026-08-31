# Direct Nuvio → Fusion conversion

Reviewed 2026-08-31. Nuvio2Fusion transfers a client layout and retains catalog references. It does not rebuild provider queries or serve catalogs.

## Evidence

- User-supplied `fusion.json`: `fusionWidgets` export version 1, 13 widgets (5 collection rows, 8 classic rows), 65 folder items, 308 source references (307 addon catalogs and 1 Fusion `localWatchlist`). The original was inspected locally, not fetched or placed in the repository. `app/presets/fusion_example.json` replaces its private addon URL with `https://addon.example.invalid/profile/manifest.json`; artwork URLs also use neutral placeholders.
- [Nuvio Collection model](https://github.com/NuvioMedia/NuvioTV/blob/9c5d82b1bc30995b27c6deaa3ce147ba6caf8e88/app/src/main/java/com/nuvio/tv/domain/model/Collection.kt) and [CollectionsDataStore serializer](https://github.com/NuvioMedia/NuvioTV/blob/9c5d82b1bc30995b27c6deaa3ce147ba6caf8e88/app/src/main/java/com/nuvio/tv/data/local/CollectionsDataStore.kt): exported collections are an array. `sources` is authoritative when present; `catalogSources` is its legacy addon-only mirror. Native TMDB/Trakt sources are distinct providers. A native Android export can omit addon base URLs, making explicit URL mapping necessary.
- [AIOMetadata's Fusion exporter](https://github.com/cedya77/aiometadata/blob/b4dd42e199db66c5d1fe3aa39c6e2b2c3f8a6190/addon/lib/collectionBuilder/fusionExport.ts) and [format types](https://github.com/cedya77/aiometadata/blob/b4dd42e199db66c5d1fe3aa39c6e2b2c3f8a6190/addon/lib/collectionBuilder/types.ts): corroborating producer contract for folder shapes, composite catalog IDs, widget envelope and classic-row restrictions. These are not Fusion's own importer implementation.
- [Fusion's official addon protocol](https://fusionapp.dev/docs): manifest URLs identify addon services. Its public protocol docs do not establish every widget setting or native-source payload.

No upstream implementation is vendored. Native source conversion is intentionally conservative because the supplied Fusion example does not prove equivalent TMDB/Trakt payloads.

## Field mapping

| Nuvio | Fusion widget v1 |
| --- | --- |
| Collection | `type: collection.row`, `dataSource.kind: collection` |
| Collection `id` | Widget ID, prefixed with `collection.` once |
| Collection `title` / optional `hideTitle` | Same fields |
| `folders` | `dataSource.payload.items` in original order |
| Folder `id`, `title`, `hideTitle` | Same fields |
| `coverImageUrl` | `imageURL` (HTTP/S only) |
| `tileShape` POSTER / LANDSCAPE / SQUARE | `imageAspect` poster / wide / square |
| `sources` or legacy `catalogSources` | Ordered `dataSources`; no duplicate mirror import |
| Addon source | `kind: addonCatalog` |
| `addonBaseUrl` or addon URL mapping | `payload.addonId`, full manifest URL |
| `type` + `catalogId` | `payload.type` + `payload.catalogId: type::id` |
| `genre` | `payload.genre`; existing encoded genre suffixes are retained |

All addon URLs required by exported sources are collected once in `requiredAddons`, in first-use order. URLs are not contacted during conversion. Query strings and private configuration path segments stay intact. URL mappings are explicit per addon ID; a single supplied URL never implicitly binds all addons. A mapping can override an embedded obsolete URL.

Missing URLs produce repair fields in the UI, not invalid placeholders in a supposedly complete output. Missing/duplicate layout IDs receive deterministic IDs and a report entry. Unknown settings are reported; malformed container structures are rejected.

## Limitations

- This converts collections, not an entire Nuvio installation. Accounts, player settings, installed stream addons, watch history, local library contents and home catalog preferences outside the collection export are not transferred. Envelope fields outside collections are reported as unconverted.
- A Nuvio collections export does not contain ordinary home rows outside its collections. Existing Fusion classic rows can be preserved when a Fusion export is the input; the converter does not invent absent rows.
- Nuvio-native TMDB and Trakt sources are omitted with source-level reasons. Recreate these in Fusion or first serve their recipes from a compatible addon. The converter never silently substitutes another provider or query.
- Focus GIFs, emoji tiles, hero backdrops/video, title logos, pinning, collection backgrounds and Nuvio view settings have no verified mapping in this v1 adapter. Explicit fields are listed as issues. Folder covers remain remote URLs, not embedded assets.
- Already-Fusion native sources such as `localWatchlist` retain their payloads. Their actual content comes from the target Fusion account/device; copying the widget does not copy a watchlist. Unknown native Fusion kinds are retained from Fusion input without asserting semantic validation.
- Classic addon rows accept movie/series types. Other types must be placed in a collection folder; incompatible classic rows are omitted and reported. Unknown widget types are also reported, not treated as supported.
- `report.complete` means no omitted source/widget, empty folder, repair or unmapped setting was detected. `sourceCoverageComplete` refers only to source references. Neither proves live addon access or native client import.
- The supplied Fusion example round-trips exactly, but a user-specific Nuvio export and an actual import into the user's Fusion version have not yet been tested. Container builds and publication are performed by GitHub Actions; consult the run for the commit you deploy.

## API

`POST /api/fusion/convert`:

```json
{
  "export_data": [
    {
      "id": "home",
      "title": "Movies",
      "folders": [
        {
          "id": "popular",
          "title": "Popular",
          "tileShape": "POSTER",
          "catalogSources": [
            {"addonId": "my.addon", "type": "movie", "catalogId": "popular"}
          ]
        }
      ]
    }
  ],
  "addon_urls": {"my.addon": "https://addon.example/config/manifest.json"}
}
```

Response: `success`, `fusionConfig` (the importable file), and `report` (counts, per-source results, missing addons, layout issues and warnings). Send `fusionConfig` to Fusion, not the whole API response. `export_data` also accepts a single Nuvio collection, `{collections: [...]}`, Fusion `{widgets: [...]}`/v1 envelope, or a Fusion widget array. Manifests and arbitrary full-backup schemas are rejected.

Privacy: inputs are held only in application memory. The report does not include addon URL fields, but still includes user-provided titles, IDs and setting field names. The Fusion file contains the actual URLs and must be kept private. The app is unauthenticated and intended for local use.
