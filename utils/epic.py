"""Epic OAuth + Fortnite profile (locker) helpers."""

from __future__ import annotations

import json

import aiohttp

import config

TIMEOUT = aiohttp.ClientTimeout(total=25)


async def exchange_auth_code(session: aiohttp.ClientSession, code: str) -> dict:
    """Exchange one-time authorizationCode for access/refresh tokens."""
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {config.EPIC_BASIC}",
    }
    async with session.post(
        config.EPIC_TOKEN_URL,
        headers=headers,
        data={"grant_type": "authorization_code", "code": code.strip()},
        timeout=TIMEOUT,
    ) as r:
        text = await r.text()
        if r.status != 200:
            raise ValueError(
                f"Epic rejected the code (HTTP {r.status}). Codes are one-time & expire in ~5 min — "
                f"grab a fresh one. Details: {text[:200]}"
            )
        return json.loads(text)


async def refresh(session: aiohttp.ClientSession, refresh_token: str) -> dict:
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {config.EPIC_BASIC}",
    }
    async with session.post(
        config.EPIC_TOKEN_URL,
        headers=headers,
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        timeout=TIMEOUT,
    ) as r:
        if r.status != 200:
            raise ValueError("Saved login expired — run /locker with a fresh auth code.")
        return await r.json()


async def account(session: aiohttp.ClientSession, access_token: str, account_id: str) -> dict:
    async with session.get(
        config.EPIC_ACCOUNT_URL.format(account_id=account_id),
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=TIMEOUT,
    ) as r:
        if r.status != 200:
            raise ValueError(f"Could not fetch Epic account (HTTP {r.status}).")
        return await r.json()


async def query_profile(
    session: aiohttp.ClientSession, access_token: str, account_id: str, profile: str
) -> dict:
    url = config.FN_PROFILE_URL.format(account_id=account_id, profile=profile)
    async with session.post(
        url,
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json={},
        timeout=TIMEOUT,
    ) as r:
        text = await r.text()
        if r.status != 200:
            raise ValueError(f"Fortnite profile '{profile}' failed (HTTP {r.status}): {text[:200]}")
        return json.loads(text)


def parse_athena(profile: dict) -> tuple[dict, list[str]]:
    """Return (counts_by_label, outfit cosmetic ids)."""
    items: dict = {}
    try:
        changes = profile.get("profileChanges", [])
        if changes:
            items = changes[0].get("profile", {}).get("items", {}) or {}
    except Exception:
        items = {}
    counts: dict[str, int] = {}
    skin_ids: list[str] = []
    for entry in items.values():
        tid = str(entry.get("templateId", ""))
        if ":" not in tid:
            continue
        kind, cid = tid.split(":", 1)
        k = kind.lower()
        if k == "athenacharacter":
            counts["Skins"] = counts.get("Skins", 0) + 1
            if cid and cid not in skin_ids:
                skin_ids.append(cid)
        elif k == "athenabackpack":
            counts["Back Blings"] = counts.get("Back Blings", 0) + 1
        elif k == "athenapickaxe":
            counts["Pickaxes"] = counts.get("Pickaxes", 0) + 1
        elif k == "athenaglider":
            counts["Gliders"] = counts.get("Gliders", 0) + 1
        elif k in ("athenadance", "athenaemote", "eid"):
            counts["Emotes"] = counts.get("Emotes", 0) + 1
        elif k == "athenaitemwrap":
            counts["Wraps"] = counts.get("Wraps", 0) + 1
        elif k in ("athenamusicpack", "athenaloadingscreen", "athenacontrail", "athenaspray",
                   "athenacharm", "athenavehiclecosmetic"):
            counts[k] = counts.get(k, 0) + 1
        else:
            counts["Other"] = counts.get("Other", 0) + 1
    counts["Total items"] = len(items)
    return counts, skin_ids


def parse_vbucks(profile: dict) -> int | None:
    try:
        changes = profile.get("profileChanges", [])
        items = changes[0].get("profile", {}).get("items", {}) if changes else {}
        total, found = 0, False
        for entry in items.values():
            if str(entry.get("templateId", "")).startswith("Currency:Mtx"):
                found = True
                total += int(entry.get("quantity", 0))
        return total if found else None
    except Exception:
        return None
