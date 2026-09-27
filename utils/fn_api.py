"""Async client for fortnite-api.com with small TTL caches."""

from __future__ import annotations

import random
import time

import aiohttp

import config

TIMEOUT = aiohttp.ClientTimeout(total=30)


class FnAPI:
    """One shared instance per cog. Caches shop/news/map/all-list in memory."""

    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, object]] = {}

    # -- cache helpers ----------------------------------------------------
    def _get_cache(self, key: str, ttl: float):
        hit = self._cache.get(key)
        if hit and time.time() - hit[0] < ttl:
            return hit[1]
        return None

    def _set_cache(self, key: str, value: object) -> None:
        self._cache[key] = (time.time(), value)

    # -- single lookups ---------------------------------------------------
    async def search_exact(self, name: str) -> dict | None:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
            async with s.get(config.FN_SEARCH, params={"name": name}) as r:
                if r.status == 200:
                    return (await r.json()).get("data")
                return None

    async def search_contains(self, name: str, limit: int = 10) -> list[dict]:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
            async with s.get(
                config.FN_SEARCH_ALL, params={"name": name, "matchMethod": "contains"}
            ) as r:
                if r.status != 200:
                    return []
                return ((await r.json()).get("data") or [])[:limit]

    async def get_by_id(self, cosmetic_id: str) -> dict | None:
        async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
            async with s.get(config.FN_BY_ID.format(id=cosmetic_id)) as r:
                if r.status == 200:
                    return (await r.json()).get("data")
                return None

    async def autocomplete_names(self, query: str, limit: int = 10) -> list[tuple[str, str]]:
        """Return [(name, id), ...] for Discord autocomplete choices."""
        query = query.strip()
        if len(query) < 2:
            return []
        items = await self.search_contains(query, limit=limit)
        out: list[tuple[str, str]] = []
        for it in items:
            label = f"{it.get('name')} ({(it.get('rarity') or {}).get('displayValue', '?')})"[:100]
            out.append((label, str(it.get("id"))))
        return out

    # -- cached bulk endpoints --------------------------------------------
    async def get_shop(self) -> tuple[str, list[dict]]:
        """Return (date, offers_with_brItems). Cached 10 min."""
        cached = self._get_cache("shop", 600)
        if cached:
            return cached  # type: ignore[return-value]
        async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
            async with s.get(config.FN_SHOP) as r:
                r.raise_for_status()
                payload = await r.json()
        data = payload.get("data") or {}
        offers = [e for e in (data.get("entries") or []) if e.get("brItems")]
        result = (str(data.get("date", ""))[:10], offers)
        self._set_cache("shop", result)
        return result

    async def get_news(self) -> list[dict]:
        cached = self._get_cache("news", 1800)
        if cached:
            return cached  # type: ignore[return-value]
        async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
            async with s.get(config.FN_NEWS_BR) as r:
                r.raise_for_status()
                payload = await r.json()
        motds = (payload.get("data") or {}).get("motds") or []
        self._set_cache("news", motds)
        return motds

    async def get_map(self) -> dict:
        cached = self._get_cache("map", 3600)
        if cached:
            return cached  # type: ignore[return-value]
        async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
            async with s.get(config.FN_MAP) as r:
                r.raise_for_status()
                payload = await r.json()
        data = payload.get("data") or {}
        self._set_cache("map", data)
        return data

    async def full_list(self) -> list[dict]:
        """All BR cosmetics. Big (~10-20 MB) — cached 6 h in memory."""
        cached = self._get_cache("all", 6 * 3600)
        if cached:
            return cached  # type: ignore[return-value]
        async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
            async with s.get(config.FN_ALL) as r:
                r.raise_for_status()
                payload = await r.json()
        items = (payload.get("data") or [])
        self._set_cache("all", items)
        return items

    # -- derived helpers --------------------------------------------------
    async def random_pick(self, type_filter: str = "outfit") -> dict | None:
        items = [i for i in await self.full_list()
                 if str((i.get("type") or {}).get("value", "")).lower() == type_filter.lower()]
        return random.choice(items) if items else None

    async def by_set(self, set_name: str, limit: int = 5) -> list[dict]:
        q = set_name.strip().lower()
        return [i for i in await self.full_list()
                if q in str(((i.get("set") or {}) or {}).get("value", "")).lower()][:limit]

    async def by_rarity(self, rarity: str, limit: int = 5) -> list[dict]:
        q = rarity.strip().lower()
        pool = [i for i in await self.full_list()
                if str((i.get("rarity") or {}).get("value", "")).lower() == q]
        random.shuffle(pool)
        return pool[:limit]

    async def get_stats(self, username: str, api_key: str) -> dict:
        """BR stats for a player. Requires free key from fortnite-api.com."""
        async with aiohttp.ClientSession(timeout=TIMEOUT) as s:
            async with s.get(
                config.FN_STATS,
                params={"name": username},
                headers={"Authorization": api_key},
            ) as r:
                body = await r.json()
                if r.status != 200:
                    err = body.get("error", f"HTTP {r.status}")
                    raise ValueError(str(err))
                return body.get("data") or {}
