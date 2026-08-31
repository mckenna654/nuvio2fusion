# Nuvio2Fusion release notes

## 2.0.2 · 31 August 2026

Removes the need to write JSON when connecting an addon. Pasting a normal AIOMetadata installation URL into the previous advanced mapping box produced a JSON error before conversion could run.

- Add an **Addon to connect** selector populated from the input's actual addon IDs and catalog-reference counts.
- Add a normal **Addon manifest URL** field and **Connect addon** button; saved URLs remain editable per addon.
- Accept the selected addon's pending URL when converting, even if Connect addon was not clicked separately.
- Clearly label bulk JSON mappings as advanced. Recover a plain URL pasted there into the normal URL field and ask which addon it belongs to, keeping the entered URL intact.
- Keep independent addon mappings and missing-URL export blocking. Connecting AIOMetadata does not silently assign its URL to another addon.

Refresh the updated app to load the new form. API conversion behavior is unchanged from 2.0.1.

## 2.0.1 · 31 August 2026

Fixes an export workflow that allowed collection tiles to be downloaded without their catalog sources. Native Nuvio collection exports can contain logical addon IDs such as `aio-metadata` without the configured installation URLs Fusion needs. Version 2.0.0 reported those omissions but still allowed an empty widget file to be downloaded.

- Block widget exports until every missing addon URL is supplied, and block files with no usable sources.
- Highlight each missing instance URL, show the number of affected catalog references, focus the first repair field and provide a **Connect addons & convert** action.
- Keep each addon mapped separately; write its configured manifest URL into both `requiredAddons` and every matching catalog source.
- Offer repair fields for malformed embedded URLs when an addon ID is available.
- Require deliberate acknowledgement before downloading other partial layouts with omitted sources/widgets or empty folders.
- Keep the compatibility report and diagnostic preview available while export is blocked.
- Add regression coverage for missing instances, independent addon mappings, empty-file recovery, API readiness and partial-export decisions. A locally supplied 12-collection, 154-folder Nuvio export retained all 347 sources with two test URL mappings; live addon availability and native Fusion import were not verified.

**Upgrade and repair:** refresh the updated app, load the **original Nuvio export**, enter every configured addon manifest URL, then convert again. Do not reconvert the empty Fusion file: it no longer contains the source references. Installing an addon manually in Fusion cannot restore those links. Back up your Fusion widgets before replacing any empty imports.

**API behavior change:** `fusionConfig` is now `null` while an export is blocked. Check `report.canExport` and `report.exportBlockReason`; diagnostic widgets are in `previewWidgets`. `success` means the input was analyzed. Respect `report.requiresPartialApproval` before saving a partial file.

## 2.0.0 · 31 August 2026

Nuvio2Fusion is now a focused Nuvio collections → Fusion widgets converter. This major release replaces the earlier provider-migration direction with a direct layout transfer, a new identity and explicit compatibility reporting. Existing repository history is preserved.

### New identity and scope

- Introduced the Nuvio2Fusion name and the tagline **“Take your collections with you.”**
- Added an original collection-transfer logo, SVG favicon, PNG app icon and documentation wordmark.
- Updated the UI, API metadata, startup message, container service/user, image references and Unraid template.
- Removed the unrelated catalog-rebuilding workflow, its page/API, remote manifest fetcher and provider-specific examples.
- Kept one user-facing task: convert a Nuvio collection export or check/re-export existing Fusion widgets.

### Conversion behavior

- Export Fusion widget format v1 using `exportType`, `exportVersion`, `requiredAddons` and `widgets`.
- Preserve collections, folder order, titles, hidden folder titles, HTTP(S) cover URLs and poster/landscape/square shapes.
- Preserve multiple addon catalog sources per folder, source order, original catalog IDs and genre selections.
- Use `sources` as authoritative, with `catalogSources` as a legacy fallback. Mirrored sources are not duplicated.
- Resolve addon URLs from explicit mappings or embedded install/base URLs. Keep configuration paths and query strings intact.
- Provide editable missing-addon URL fields rather than guessing provider URLs.
- Retain supported Fusion classic-row presentation, numbering, cache TTL and limits, including explicit zero values.
- Retain native payloads already present in Fusion exports, such as a local-watchlist source, without claiming to copy the underlying library.
- Generate stable replacement IDs for missing/duplicate layout IDs and report each repair.

### Reports and downloads

- Show widget/folder counts and kept/omitted source references.
- Provide searchable source results, a widget layout preview and per-entry compatibility issues.
- Retain empty folder tiles for repair and report their missing sources.
- Mark downloads as partial when sources/widgets are omitted or layout settings need attention.
- Export a separate compatibility report without addon URL fields.
- Clear stale results when inputs change or become invalid.

### Privacy and deployment

- Conversion performs no outbound catalog, artwork or account requests.
- Uploads and results remain in application memory; no account/session database or persistent volume is required.
- Keep scripts, styles and logo assets local. No remote font, analytics or artwork previews are loaded by the UI.
- Limit browser files to 5 MiB, API bodies to 10 MiB, input collections/widgets to 1,000 and source references to 10,000.
- Reject cross-origin posts and avoid reflecting submitted values in request errors.
- Bind Python runs and the supplied Compose host port to localhost by default; run the container as an unprivileged user.
- Test Python 3.11 and 3.14 in CI before publishing `amd64` and `arm64` images to GitHub Container Registry.

### Breaking changes and upgrade steps

This is a major-version change. The previous generic conversion and remote-fetch APIs are removed. Client integrations should use `POST /api/fusion/convert` with `export_data` and optional `addon_urls`, and extract `fusionConfig` from its response.

1. Back up your original Nuvio export and current Fusion widgets.
2. Update the repository remote/image references to `mckenna654/nuvio2fusion`.
3. Rebuild with `docker compose up --build -d`, or recreate your container with the new image after its publish job succeeds. Stop any previous container already using port 7088.
4. Python users should reinstall `requirements.txt`; contributors should install `requirements-dev.txt`.
5. Export Nuvio collections, convert them, supply any missing addon URLs and review the compatibility report before importing into Fusion.

The container image path is `ghcr.io/mckenna654/nuvio2fusion`. `latest` follows successful main-branch builds. Versioned image tags appear only when the corresponding Git tag has been built; this document alone does not create a registry tag. No stored application data needs migrating.

### Known limitations

- Only collection layout and catalog references transfer. Accounts, player settings, watched history, local library data and absent home rows do not.
- Nuvio-native TMDB/Trakt sources have no verified direct mapping and are reported as unsupported. Recreate them in Fusion or supply an addon-backed equivalent.
- Nuvio focus GIFs, emoji, hero artwork/video, title logos, collection backgrounds, pinning and view settings have no verified widget-v1 mapping in this adapter.
- Referenced catalog services and remote artwork must remain accessible. Exporting a layout does not make them self-hosted.
- Classic addon rows require movie/series types. Other types belong in collection folders.
- Native Fusion payloads are retained from Fusion input without comprehensive semantic validation.
- A complete report indicates structural coverage, not identical rendering, live availability or guaranteed import into every Fusion version.
- Downloads can contain private addon tokens. Keep them private. Reports can still contain personal titles and catalog IDs.

### Validation

The remaining regression suite focuses on direct layout conversion and API boundaries. The neutral Fusion fixture round-trips exactly with 13 widgets, 65 folders and 308 source references. Browser checks cover successful conversion, missing-addon repair, invalid-input handling and the downloaded file's contents. Live import behavior remains dependent on the user's Fusion version and installed addons.

## Earlier versions

Earlier releases belong to the project's retired catalog-migration scope. Their source and tags remain in Git history; their endpoints, container references and documentation do not describe Nuvio2Fusion 2.0.0.
