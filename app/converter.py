"""converter.py - Core Conversion Engine for Xperience / Nuvio to AIOMetadata."""

from __future__ import annotations

import copy
import datetime
import re
from typing import Any

# Service and Studio Mappings
STREAMING_SERVICE_MAP: dict[str, dict[str, str]] = {
    "netflix": {"name": "Netflix", "code": "nfx"},
    "disney": {"name": "Disney+", "code": "dis"},
    "apple": {"name": "Apple TV+", "code": "atv"},
    "prime": {"name": "Prime Video", "code": "amp"},
    "hbo": {"name": "HBO Max", "code": "hbo"},
    "paramount": {"name": "Paramount+", "code": "pmp"},
    "hulu": {"name": "Hulu", "code": "hlu"},
    "peacock": {"name": "Peacock", "code": "pck"},
    "crunchyroll": {"name": "Crunchyroll", "code": "cr"},
    "discovery": {"name": "Discovery+", "code": "dsc"},
    "shudder": {"name": "Shudder", "code": "shd"},
    "mgm": {"name": "MGM+", "code": "mgm"},
    "amc": {"name": "AMC+", "code": "amc"},
}

STUDIO_MAP: dict[str, str] = {
    "a24": "A24",
    "blumhouse": "Blumhouse",
    "dc": "DC",
    "dcu": "DC Universe",
    "dc_animation": "DC Animated",
    "dc_batman": "Batman",
    "dc_superman": "Superman",
    "dc_dceu": "DC Extended Universe",
    "disney_animated": "Disney Animated",
    "ghibli": "Studio Ghibli",
    "lucasfilm": "Lucasfilm",
    "marvel": "Marvel",
    "marvel_animation": "Marvel Animation",
    "marvel_avengers": "Avengers",
    "marvel_legacy": "Marvel Legacy",
    "marvel_spiderman": "Spider-Man",
    "marvel_xmen": "X-Men",
    "pixar": "Pixar",
    "paramount": "Paramount Pictures",
    "sony": "Sony Pictures",
    "universal": "Universal Pictures",
    "warner": "Warner Bros",
}

MANIFEST_CATALOG_ID_MAP: dict[str, dict[str, Any]] = {
    "discover_all_movies": {"id": "tmdb.discover", "source": "tmdb", "type": "movie", "name": "[Discover] Movies"},
    "discover_all_series": {"id": "tmdb.discover", "source": "tmdb", "type": "series", "name": "[Discover] Series"},
    "trending_movies": {"id": "tmdb.trending", "source": "tmdb", "type": "movie", "name": "[Discover] Trending Movies"},
    "trending_series": {"id": "tmdb.trending", "source": "tmdb", "type": "series", "name": "[Discover] Trending Shows"},
    "now_playing_movies": {"id": "tmdb.now_playing", "source": "tmdb", "type": "movie", "name": "[Discover] In Theaters"},
    "on_the_air_series": {"id": "tmdb.airing_today", "source": "tmdb", "type": "series", "name": "[Discover] On The Air"},
    "tmdb_popular_movies": {"id": "tmdb.popular", "source": "tmdb", "type": "movie", "name": "[Catalog] Popular Movies"},
    "tmdb_popular_series": {"id": "tmdb.popular", "source": "tmdb", "type": "series", "name": "[Catalog] Popular Shows"},
    "trakt_popular_movies": {"id": "trakt.popular", "source": "trakt", "type": "movie", "name": "[Catalog] Trakt Popular Movies"},
    "trakt_popular_series": {"id": "trakt.popular", "source": "trakt", "type": "series", "name": "[Catalog] Trakt Popular Shows"},
    "trakt_trending_movies": {"id": "trakt.trending", "source": "trakt", "type": "movie", "name": "[Catalog] Trakt Trending Movies"},
    "trakt_trending_series": {"id": "trakt.trending", "source": "trakt", "type": "series", "name": "[Catalog] Trakt Trending Shows"},
    "trakt_anticipated_movies": {"id": "trakt.anticipated", "source": "trakt", "type": "movie", "name": "[Catalog] Trakt Anticipated Movies"},
    "trakt_anticipated_series": {"id": "trakt.anticipated", "source": "trakt", "type": "series", "name": "[Catalog] Trakt Anticipated Shows"},
    "trakt_watchlist_movies": {"id": "trakt.watchlist", "source": "trakt", "type": "movie", "name": "[Discover] Trakt Watchlist (Movies)"},
    "trakt_watchlist_series": {"id": "trakt.watchlist", "source": "trakt", "type": "series", "name": "[Discover] Trakt Watchlist (Shows)"},
    "anilist_planning_movies": {"id": "anilist.planning", "source": "anilist", "type": "anime", "name": "[AniList] Plan to Watch (Movies)"},
    "anilist_planning_series": {"id": "anilist.planning", "source": "anilist", "type": "anime", "name": "[AniList] Plan to Watch (Shows)"},
    "anilist_watching_movies": {"id": "anilist.watching", "source": "anilist", "type": "anime", "name": "[AniList] Watching (Movies)"},
    "anilist_watching_series": {"id": "anilist.watching", "source": "anilist", "type": "anime", "name": "[AniList] Watching (Shows)"},
    "collection_mcu": {"id": "trakt.list.884", "source": "trakt", "type": "movie", "name": "[Collections] Marvel Cinematic Universe"},
}

DEFAULT_BASE_CONFIG: dict[str, Any] = {
    "version": 1,
    "exportedAt": "2026-08-15T00:00:00.000Z",
    "config": {
        "language": "en",
        "addonName": "AIOMetadata",
        "includeAdult": False,
        "blurThumbs": False,
        "showPrefix": False,
        "showMetaProviderAttribution": True,
        "castCount": 25,
        "displayAgeRating": True,
        "showDisabledCatalogs": False,
        "sfw": False,
        "hideUnreleasedDigital": False,
        "hideUnreleasedDigitalSearch": False,
        "hideWatchedTrakt": False,
        "hideWatchedAnilist": False,
        "hideWatchedMdblist": False,
        "providers": {
            "movie": "tmdb",
            "series": "tmdb",
            "anime": "mal",
            "anime_id_provider": "mal",
            "forceAnimeForDetectedImdb": True,
        },
        "artProviders": {
            "movie": {"poster": "tmdb", "background": "tmdb", "logo": "fanart"},
            "series": {"poster": "tmdb", "background": "tmdb", "logo": "fanart"},
            "anime": {"poster": "mal", "background": "fanart", "logo": "fanart"},
            "englishArtOnly": False,
        },
        "tvdbSeasonType": "official",
        "mal": {
            "skipFiller": True,
            "skipRecap": True,
            "allowEpisodeMarking": True,
            "useImdbIdForCatalogAndSearch": True,
        },
        "tmdb": {
            "scrapeImdb": True,
            "forceLatinCastNames": True,
        },
        "apiKeys": {
            "gemini": None,
            "tmdb": None,
            "tvdb": None,
            "fanart": None,
            "rpdb": None,
            "topPoster": None,
            "mdblist": None,
            "openrouter": None,
            "traktTokenId": None,
            "simklTokenId": None,
            "anilistTokenId": None,
            "customDescriptionBlurb": None,
        },
        "posterRatingProvider": "rpdb",
        "usePosterProxy": False,
        "mdblistWatchTracking": False,
        "anilistWatchTracking": False,
        "simklWatchTracking": False,
        "traktWatchTracking": False,
        "enableRatingPostersForLibrary": False,
        "showRateMeButton": True,
        "ageRating": "None",
        "searchEnabled": True,
        "sessionId": None,
        "catalogSetupComplete": True,
        "timezone": "auto",
        "catalogs": [],
        "search": {
            "enabled": True,
            "ai_enabled": False,
            "ai_provider": "gemini",
            "ai_model": "gemini-2.0-flash",
            "providers": {
                "movie": "tmdb",
                "series": "tmdb",
                "anime_movie": "mal",
                "anime_series": "mal",
                "people_search_movie": "tmdb",
                "people_search_series": "tmdb",
            },
            "engineEnabled": {
                "tmdb.search": True,
                "tvdb.search": True,
                "tvdb.collections.search": True,
                "tvmaze.search": True,
                "trakt.search": True,
                "mdblist.search": True,
                "people_search_movie": True,
                "people_search_series": True,
                "mal.search.movie": True,
                "mal.search.series": True,
            },
            "searchNames": {
                "movie": "[Search] Movies",
                "series": "[Search] Series",
            },
            "searchOrder": [
                "tmdb.search",
                "tvdb.search",
                "tvmaze.search",
                "trakt.search",
                "mdblist.search",
                "people_search_movie",
                "people_search_series",
                "mal.search.movie",
                "mal.search.series",
                "tvdb.collections.search",
            ],
            "searchDisplayTypes": {
                "movie": "movie",
                "series": "series",
            },
        },
        "streaming": {},
        "customPosterUrlPattern": "",
        "customBackgroundUrlPattern": "",
        "customLogoUrlPattern": "",
        "customThumbnailUrlPattern": "",
        "publicmetadbWatchTracking": False,
        "lastModified": None,
        "configVersion": 1,
        "configHash": None,
    },
    "metadata": {
        "apiKeysExcluded": True,
        "totalCatalogs": 0,
        "enabledCatalogs": 0,
    },
}


def infer_source_from_id(catalog_id: str) -> str:
    """Infers provider source from catalog ID."""
    cid = catalog_id.lower()
    if cid.startswith(("mdblist.", "mdblist:")):
        return "mdblist"
    if cid.startswith(("trakt.", "trakt:")):
        return "trakt"
    if cid.startswith(("anilist.", "anilist:")):
        return "anilist"
    if cid.startswith(("tmdb.", "tmdb:")):
        return "tmdb"
    if cid.startswith(("tvdb.", "tvdb:")):
        return "tvdb"
    if cid.startswith(("mal.", "mal:")):
        return "mal"
    if cid.startswith(("streaming.", "streaming:")):
        return "streaming"
    if cid.startswith(("tvmaze.", "tvmaze:")):
        return "tvmaze"
    if cid.isdigit():
        return "mdblist"
    return "mdblist"


def clean_catalog_id(raw_id: str) -> tuple[str, str | None]:
    """Strips leading type:: prefix from catalog id."""
    extracted_type: str | None = None
    if "::" in raw_id:
        parts = raw_id.split("::", 1)
        extracted_type = parts[0]
        clean_id = parts[1]
    else:
        clean_id = raw_id

    if clean_id.isdigit():
        clean_id = f"mdblist.{clean_id}"

    return clean_id, extracted_type


def format_catalog_name(
    base_name: str,
    widget_category: str | None = None,
    media_type: str | None = None,
    prefix_mode: str = "category",
) -> str:
    """Formats catalog names for AIOMetadata."""
    base_name = base_name.strip()
    if prefix_mode == "preserve" and base_name.startswith("["):
        return base_name

    match = re.match(r"^\[([^\]]+)\]\s*(.*)$", base_name)
    if match:
        existing_cat, actual_name = match.groups()
        cat = widget_category or existing_cat
        name_body = actual_name
    else:
        cat = widget_category
        name_body = base_name

    if prefix_mode == "clean":
        return name_body

    if media_type:
        type_suffix_map = {"movie": "Movies", "series": "Shows", "anime": "Anime"}
        type_label = type_suffix_map.get(media_type.lower())
        if type_label and type_label.lower() not in name_body.lower() and not re.search(r"\((Movies|Shows|Anime)\)$", name_body, re.IGNORECASE):
            name_body = f"{name_body} ({type_label})"

    if cat:
        return f"[{cat}] {name_body}"
    return f"[Catalog] {name_body}"


def build_aio_catalog(
    catalog_id: str,
    name: str,
    media_type: str = "movie",
    source: str | None = None,
    enabled: bool = True,
    show_in_home: bool = True,
    sort: str | None = None,
    order: str | None = None,
    sort_direction: str | None = None,
    cache_ttl: int | None = None,
    genre_selection: str | None = None,
    enable_rating_posters: bool | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Constructs a normalized AIOMetadata catalog object."""
    clean_id, extracted_type = clean_catalog_id(catalog_id)
    final_type = media_type or extracted_type or "movie"
    final_source = source or infer_source_from_id(clean_id)

    cat: dict[str, Any] = {
        "id": clean_id,
        "name": name,
        "type": final_type,
        "enabled": enabled,
        "showInHome": show_in_home,
        "source": final_source,
        "displayType": final_type,
    }

    if final_source == "mdblist":
        cat["sort"] = sort or "default"
        cat["order"] = order or "asc"
        cat["cacheTTL"] = cache_ttl if cache_ttl is not None else 43200
        cat["genreSelection"] = genre_selection or "standard"
        cat["enableRatingPosters"] = enable_rating_posters if enable_rating_posters is not None else True
    elif final_source == "trakt":
        cat["sort"] = sort or ("added" if "watchlist" in clean_id else "released")
        cat["sortDirection"] = sort_direction or order or "asc"
        cat["cacheTTL"] = cache_ttl if cache_ttl is not None else (1800 if "watchlist" in clean_id else 43200)
    elif final_source == "tmdb":
        cat["sort"] = sort or "default"
        cat["order"] = order or "asc"
        cat["cacheTTL"] = cache_ttl if cache_ttl is not None else 43200
        cat["genreSelection"] = genre_selection or "standard"
        cat["enableRatingPosters"] = enable_rating_posters if enable_rating_posters is not None else True
    elif final_source == "anilist":
        if any(k in clean_id.lower() for k in ("watching", "planning", "watchlist")):
            cat["sort"] = sort or "ADDED_TIME"
            cat["sortDirection"] = sort_direction or "desc"
    elif final_source in ("tvdb", "mal", "streaming", "tvmaze"):
        if sort:
            cat["sort"] = sort
        if order:
            cat["order"] = order
        if cache_ttl is not None:
            cat["cacheTTL"] = cache_ttl

    if metadata:
        cat["metadata"] = copy.deepcopy(metadata)

    return cat


class XperienceParser:
    """Parses Xperience / Nuvio JSON structures into AIOMetadata catalog dictionaries."""

    prefix_mode: str
    force_enabled: bool | None
    force_rating_posters: bool | None

    def __init__(
        self,
        prefix_mode: str = "category",
        force_enabled: bool | None = None,
        force_rating_posters: bool | None = None,
    ) -> None:
        self.prefix_mode = prefix_mode
        self.force_enabled = force_enabled
        self.force_rating_posters = force_rating_posters

    def parse(self, raw_data: Any) -> list[dict[str, Any]]:
        if not raw_data:
            return []

        if isinstance(raw_data, dict):
            if "widgets" in raw_data and isinstance(raw_data["widgets"], list):
                return self._parse_widgets(raw_data["widgets"])
            if "catalogs" in raw_data and isinstance(raw_data["catalogs"], list) and ("id" in raw_data or "resources" in raw_data):
                return self._parse_manifest_catalogs(raw_data["catalogs"])
            if "rows" in raw_data and isinstance(raw_data["rows"], list):
                return self._parse_widgets(raw_data["rows"])
            if "layout" in raw_data:
                layout_items = raw_data["layout"]
                if isinstance(layout_items, list):
                    return self._parse_widgets(layout_items)
                if isinstance(layout_items, dict) and "widgets" in layout_items and isinstance(layout_items["widgets"], list):
                    return self._parse_widgets(layout_items["widgets"])
            if "config" in raw_data and isinstance(raw_data["config"], dict) and "catalogs" in raw_data["config"]:
                cats = raw_data["config"]["catalogs"]
                return cats if isinstance(cats, list) else []

        elif isinstance(raw_data, list):
            if raw_data and isinstance(raw_data[0], dict):
                if "dataSource" in raw_data[0] or "type" in raw_data[0]:
                    return self._parse_widgets(raw_data)
                if "id" in raw_data[0] and ("type" in raw_data[0] or "name" in raw_data[0]):
                    return self._parse_manifest_catalogs(raw_data)

        return self._deep_discover_catalogs(raw_data)

    def _parse_widgets(self, widgets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        catalogs: list[dict[str, Any]] = []
        for w_idx, widget in enumerate(widgets):
            try:
                if not isinstance(widget, dict):
                    continue

                widget_title = str(widget.get("title", f"Row {w_idx + 1}"))
                cache_ttl = widget.get("cacheTTL")
                ds = widget.get("dataSource", {})

                if not isinstance(ds, dict):
                    continue

                ds_kind = ds.get("kind")
                ds_payload = ds.get("payload", {})

                if ds_kind == "collection" or (isinstance(ds_payload, dict) and "items" in ds_payload):
                    items = ds_payload.get("items", []) if isinstance(ds_payload, dict) else []
                    for it in items:
                        if not isinstance(it, dict):
                            continue
                        item_title = str(it.get("title", "Untitled"))
                        for sub_ds in it.get("dataSources", []):
                            if not isinstance(sub_ds, dict):
                                continue
                            if sub_ds.get("kind") == "addonCatalog":
                                payload = sub_ds.get("payload", {})
                                if isinstance(payload, dict):
                                    cat_obj = self._create_catalog_from_payload(
                                        payload=payload,
                                        category=widget_title,
                                        item_name=item_title,
                                        cache_ttl=cache_ttl,
                                    )
                                    if cat_obj:
                                        catalogs.append(cat_obj)

                elif ds_kind == "addonCatalog" or (isinstance(ds_payload, dict) and "catalogId" in ds_payload):
                    if isinstance(ds_payload, dict):
                        cat_obj = self._create_catalog_from_payload(
                            payload=ds_payload,
                            category="Catalog",
                            item_name=widget_title,
                            cache_ttl=cache_ttl,
                        )
                        if cat_obj:
                            catalogs.append(cat_obj)

                elif "dataSources" in widget and isinstance(widget["dataSources"], list):
                    for sub_ds in widget["dataSources"]:
                        if isinstance(sub_ds, dict) and sub_ds.get("kind") == "addonCatalog":
                            payload = sub_ds.get("payload", {})
                            if isinstance(payload, dict):
                                cat_obj = self._create_catalog_from_payload(
                                    payload=payload,
                                    category="Catalog",
                                    item_name=widget_title,
                                    cache_ttl=cache_ttl,
                                )
                                if cat_obj:
                                    catalogs.append(cat_obj)

            except (KeyError, TypeError, ValueError):
                continue

        return catalogs

    def _create_catalog_from_payload(
        self,
        payload: dict[str, Any],
        category: str,
        item_name: str,
        cache_ttl: int | None = None,
    ) -> dict[str, Any] | None:
        raw_catalog_id = payload.get("catalogId") or payload.get("id")
        if not raw_catalog_id:
            return None

        clean_id, extracted_type = clean_catalog_id(str(raw_catalog_id))
        media_type = str(payload.get("type") or extracted_type or "movie")

        formatted_name = format_catalog_name(
            base_name=item_name,
            widget_category=category,
            media_type=media_type,
            prefix_mode=self.prefix_mode,
        )

        enabled = True if self.force_enabled is None else self.force_enabled
        enable_rating_posters = True if self.force_rating_posters is None else self.force_rating_posters

        return build_aio_catalog(
            catalog_id=clean_id,
            name=formatted_name,
            media_type=media_type,
            enabled=enabled,
            show_in_home=True,
            cache_ttl=cache_ttl or payload.get("cacheTTL"),
            sort=payload.get("sort"),
            order=payload.get("order"),
            enable_rating_posters=enable_rating_posters,
            metadata=payload.get("metadata"),
        )

    def _parse_manifest_catalogs(self, manifest_catalogs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        catalogs: list[dict[str, Any]] = []
        for m_cat in manifest_catalogs:
            try:
                if not isinstance(m_cat, dict):
                    continue

                m_id = str(m_cat.get("id", ""))
                m_name = str(m_cat.get("name", "Untitled"))
                m_type = str(m_cat.get("type", "movie"))
                show_in_home = bool(m_cat.get("showInHome", True))

                if m_id in MANIFEST_CATALOG_ID_MAP:
                    mapped = MANIFEST_CATALOG_ID_MAP[m_id]
                    target_id = str(mapped["id"])
                    target_source = str(mapped["source"])
                    target_type = str(mapped.get("type", m_type))
                    target_name = str(mapped.get("name", m_name))
                else:
                    target_id, target_source, target_name = self._resolve_manifest_id(m_id, m_name, m_type)
                    target_type = m_type

                enabled = True if self.force_enabled is None else self.force_enabled
                enable_rating_posters = True if self.force_rating_posters is None else self.force_rating_posters

                cat_obj = build_aio_catalog(
                    catalog_id=target_id,
                    name=target_name,
                    media_type=target_type,
                    source=target_source,
                    enabled=enabled,
                    show_in_home=show_in_home,
                    enable_rating_posters=enable_rating_posters,
                )
                catalogs.append(cat_obj)

            except (KeyError, TypeError, ValueError):
                continue

        return catalogs

    def _resolve_manifest_id(self, m_id: str, m_name: str, m_type: str) -> tuple[str, str, str]:
        streaming_match = re.match(r"^streaming_([a-z0-9]+)(?:_(movies|series|toprated|latest|originals))?", m_id)
        if streaming_match:
            service_key = streaming_match.group(1)
            service_info = STREAMING_SERVICE_MAP.get(service_key, {"name": service_key.title(), "code": service_key})
            service_name = service_info["name"]
            service_code = service_info["code"]
            cat_name = f"[Streaming Services] {service_name} ({'Movies' if m_type == 'movie' else 'Shows'})"
            return f"streaming.{service_code}", "streaming", cat_name

        studio_match = re.match(r"^studio_([a-z0-9_]+?)(?:_(movies|series|toprated|latest))?$", m_id)
        if studio_match:
            studio_key = studio_match.group(1)
            studio_name = STUDIO_MAP.get(studio_key, studio_key.replace("_", " ").title())
            cat_name = f"[Studios] {studio_name} ({'Movies' if m_type == 'movie' else 'Shows'})"
            return f"tmdb.studio.{studio_key}", "tmdb", cat_name

        genre_match = re.match(r"^genre_([a-z0-9_]+?)(?:_(movies|series|toprated|latest))?$", m_id)
        if genre_match:
            genre_key = genre_match.group(1).replace("_", " ").title()
            cat_name = f"[Genres] {genre_key} ({'Movies' if m_type == 'movie' else 'Shows'})"
            return f"tmdb.genre.{genre_match.group(1)}", "tmdb", cat_name

        decade_match = re.match(r"^decade_([a-z0-9_]+?)(?:_(movies|series|toprated))?$", m_id)
        if decade_match:
            decade_key = decade_match.group(1).replace("_", " ").title()
            cat_name = f"[Decades] {decade_key} ({'Movies' if m_type == 'movie' else 'Shows'})"
            return f"tmdb.decade.{decade_match.group(1)}", "tmdb", cat_name

        if m_id.startswith("trakt_"):
            clean_part = m_id.replace("trakt_", "")
            return f"trakt.{clean_part}", "trakt", f"[Trakt] {m_name}"
        if m_id.startswith("tmdb_"):
            clean_part = m_id.replace("tmdb_", "")
            return f"tmdb.{clean_part}", "tmdb", f"[TMDB] {m_name}"

        return m_id, infer_source_from_id(m_id), m_name

    def _deep_discover_catalogs(self, obj: Any) -> list[dict[str, Any]]:
        found_catalogs: list[dict[str, Any]] = []

        def search_node(node: Any, category: str = "Discovered") -> None:
            if isinstance(node, dict):
                if node.get("kind") == "addonCatalog" and "payload" in node and isinstance(node["payload"], dict):
                    pl = node["payload"]
                    item_name = str(pl.get("name") or category)
                    cat_obj = self._create_catalog_from_payload(
                        payload=pl,
                        category=category,
                        item_name=item_name,
                    )
                    if cat_obj:
                        found_catalogs.append(cat_obj)
                elif "catalogId" in node:
                    item_name = str(node.get("title") or node.get("name") or category)
                    cat_obj = self._create_catalog_from_payload(
                        payload=node,
                        category=category,
                        item_name=item_name,
                    )
                    if cat_obj:
                        found_catalogs.append(cat_obj)
                else:
                    new_cat = str(node.get("title") or node.get("name") or category)
                    for val in node.values():
                        search_node(val, new_cat)
            elif isinstance(node, list):
                for item in node:
                    search_node(item, category)

        search_node(obj)
        return found_catalogs


def deduplicate_catalogs(catalogs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicates catalogs by (id, type)."""
    seen: set[tuple[str | None, str | None]] = set()
    unique_catalogs: list[dict[str, Any]] = []
    for c in catalogs:
        key = (c.get("id"), c.get("type"))
        if key not in seen:
            seen.add(key)
            unique_catalogs.append(c)
    return unique_catalogs


def build_final_aio_config(
    catalogs: list[dict[str, Any]],
    base_config: dict[str, Any] | None = None,
    addon_name: str | None = None,
) -> dict[str, Any]:
    """Injects catalogs and updates metadata timestamps into AIOMetadata root structure."""
    if isinstance(base_config, dict):
        out_config: dict[str, Any] = copy.deepcopy(base_config)
    else:
        out_config = copy.deepcopy(DEFAULT_BASE_CONFIG)

    if "config" not in out_config or not isinstance(out_config.get("config"), dict):
        out_config = {
            "version": 1,
            "exportedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "config": out_config,
            "metadata": {},
        }

    config_inner_val = out_config.get("config")
    if isinstance(config_inner_val, dict):
        config_inner: dict[str, Any] = config_inner_val
    else:
        config_inner = {}
        out_config["config"] = config_inner

    config_inner["catalogs"] = catalogs

    if addon_name:
        config_inner["addonName"] = addon_name

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    out_config["exportedAt"] = now_iso
    if "lastModified" in config_inner:
        config_inner["lastModified"] = now_iso

    enabled_count = sum(1 for c in catalogs if c.get("enabled", True))
    current_meta = out_config.get("metadata")
    meta_dict = current_meta if isinstance(current_meta, dict) else {}
    out_config["metadata"] = {
        "apiKeysExcluded": meta_dict.get("apiKeysExcluded", True),
        "totalCatalogs": len(catalogs),
        "enabledCatalogs": enabled_count,
    }

    return out_config
