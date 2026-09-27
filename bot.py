"""Fortnite skin checker Discord bot — /skin with images + Epic locker checker.

Commands:
    /skin name:<skin name>      -> public cosmetic lookup with images (fortnite-api.com)
    /shop                      -> current Item Shop with images
    /locker_help               -> how to get your Epic auth code (no password to bot)
    /locker auth_code:<code>   -> exchange auth code, fetch Epic locker, show skins w/ images
    /locker_logout             -> delete saved Epic token

Auth model (safe, no password storage):
    1. User logs in on epicgames.com in their own browser.
    2. User visits the redirect URL which returns a one-time `authorizationCode`.
    3. User pastes that code into /locker (preferably in DMs, ephemeral reply).
    4. Bot exchanges the code for an access_token via Epic OAuth, then calls
       Fortnite QueryProfile (athena + common_core) to count skins and V-Bucks.
    5. Skin IDs are resolved to names/images via free fortnite-api.com.
    6. Only access/refresh tokens are stored locally in tokens.json (chmod 600).
       Use /locker_logout anytime. Never share your auth code publicly.

Requires: DISCORD_TOKEN in .env (see .env.example)
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
import time
from pathlib import Path

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

BASE_DIR = Path(__file__).resolve().parent
TOKENS_FILE = BASE_DIR / "tokens.json"

# --- Fortnite-API.com (free, no key, has images) ---
FN_API_SEARCH = "https://fortnite-api.com/v2/cosmetics/br/search"
FN_API_SEARCH_ALL = "https://fortnite-api.com/v2/cosmetics/br/search/all"
FN_API_BY_ID = "https://fortnite-api.com/v2/cosmetics/br/{id}"
FN_API_SHOP = "https://fortnite-api.com/v2/shop"

# --- Epic OAuth + Fortnite profile (locker) ---
# Public Fortnite PC client (used by many open-source locker tools).
EPIC_CLIENT_ID = "ec684b8c687f479fadea3cb2ad83f5c6"
EPIC_CLIENT_SECRET = "e1f31c211f28413186262d37a13fc84d"
_EPIC_BASIC = base64.b64encode(f"{EPIC_CLIENT_ID}:{EPIC_CLIENT_SECRET}".encode()).decode()
EPIC_TOKEN_URL = "https://account-public-service-prod.ol.epicgames.com/account/api/oauth/token"
EPIC_ACCOUNT_URL = "https://account-public-service-prod.ol.epicgames.com/account/api/public/account/{account_id}"
FN_PROFILE_URL = (
    "https://fortnite-public-service-prod11.ol.epicgames.com"
    "/fortnite/api/game/v2/profile/{account_id}/client/QueryProfile"
    "?profileId={profile}&rvn=-1"
)
# This URL, opened AFTER logging in on epicgames.com, returns {"authorizationCode": "..."}
AUTHCODE_REDIRECT_URL = (
    "https://www.epicgames.com/id/login"
    "?redirectUrl=https://www.epicgames.com/id/api/redirect"
    f"?clientId={EPIC_CLIENT_ID}"
)

HTTP_TIMEOUT = aiohttp.ClientTimeout(total=25)

RARITY_COLORS = {
    "common": discord.Color.light_grey(),
    "uncommon": discord.Color.green(),
    "rare": discord.Color.blue(),
    "epic": discord.Color.purple(),
    "legendary": discord.Color.orange(),
    "mythic": discord.Color.gold(),
    "icon": discord.Color.teal(),
    "gaminglegends": discord.Color.dark_purple(),
    "starwars": discord.Color.dark_blue(),
    "marvel": discord.Color.red(),
    "dc": discord.Color.dark_blue(),
    "dark": discord.Color.darker_grey(),
    "frozen": discord.Color.teal(),
    "lava": discord.Color.orange(),
    "shadow": discord.Color.darker_grey(),
    "slurp": discord.Color.teal(),
}


def rarity_color(rarity_value: str, series_value: str = "") -> discord.Color:
    key = (rarity_value or "").lower()
    if key in RARITY_COLORS:
        return RARITY_COLORS[key]
    key2 = (series_value or "").lower().replace(" ", "")
    return RARITY_COLORS.get(key2, discord.Color.blurple())


def cosmetic_embed(item: dict) -> discord.Embed:
    """Build a rich embed with images for one fortnite-api.com cosmetic."""
    name = item.get("name", "Unknown")
    desc = item.get("description", "")
    ctype = (item.get("type") or {}).get("displayValue", "?")
    rarity = (item.get("rarity") or {}).get("displayValue", "?")
    rarity_backend = (item.get("rarity") or {}).get("value", "")
    series = (item.get("series") or {}).get("value", "") if item.get("series") else ""
    series_name = (item.get("series") or {}).get("name", "") if item.get("series") else ""
    set_name = (item.get("set") or {}).get("value", "") if item.get("set") else ""
    intro = item.get("introduction") or {}
    images = item.get("images") or {}

    main_img = images.get("featured") or images.get("icon") or images.get("smallIcon")
    thumb = images.get("smallIcon")

    embed = discord.Embed(
        title=f"{name}",
        description=desc or "_No description_",
        color=rarity_color(rarity_backend, series),
    )
    embed.add_field(name="Type", value=str(ctype), inline=True)
    embed.add_field(name="Rarity", value=str(rarity), inline=True)
    if series_name:
        embed.add_field(name="Series", value=str(series_name), inline=True)
    if set_name:
        embed.add_field(name="Set", value=str(set_name), inline=True)
    if intro and intro.get("text"):
        embed.add_field(name="Introduced", value=str(intro.get("text")), inline=True)
    shop_hist = item.get("shopHistory") or []
    if shop_hist:
        embed.set_footer(text=f"Last seen in shop: {shop_hist[-1][:10]} · ID: {item.get('id')}")
    else:
        embed.set_footer(text=f"ID: {item.get('id')}")
    if main_img:
        embed.set_image(url=main_img)
    if thumb and thumb != main_img:
        embed.set_thumbnail(url=thumb)
    return embed


# ---------------------------------------------------------------------------
# fortnite-api.com helpers
# ---------------------------------------------------------------------------

async def fn_search_exact(session: aiohttp.ClientSession, name: str) -> dict | None:
    params = {"name": name}
    async with session.get(FN_API_SEARCH, params=params, timeout=HTTP_TIMEOUT) as r:
        if r.status == 200:
            data = await r.json()
            return data.get("data")
        return None


async def fn_search_contains(session: aiohttp.ClientSession, name: str, limit: int = 5) -> list[dict]:
    params = {"name": name, "matchMethod": "contains"}
    async with session.get(FN_API_SEARCH_ALL, params=params, timeout=HTTP_TIMEOUT) as r:
        if r.status != 200:
            return []
        data = await r.json()
        items = data.get("data") or []
        return items[:limit]


async def fn_get_by_id(session: aiohttp.ClientSession, cosmetic_id: str) -> dict | None:
    async with session.get(FN_API_BY_ID.format(id=cosmetic_id), timeout=HTTP_TIMEOUT) as r:
        if r.status == 200:
            data = await r.json()
            return data.get("data")
        return None


# ---------------------------------------------------------------------------
# Epic locker helpers
# ---------------------------------------------------------------------------

def load_tokens() -> dict:
    if TOKENS_FILE.exists():
        try:
            return json.loads(TOKENS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_tokens(data: dict) -> None:
    TOKENS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        os.chmod(TOKENS_FILE, 0o600)
    except Exception:
        pass


async def epic_exchange_auth_code(session: aiohttp.ClientSession, code: str) -> dict:
    """Exchange one-time authorizationCode for access_token + refresh_token."""
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {_EPIC_BASIC}",
    }
    body = {"grant_type": "authorization_code", "code": code.strip()}
    async with session.post(EPIC_TOKEN_URL, headers=headers, data=body, timeout=HTTP_TIMEOUT) as r:
        text = await r.text()
        if r.status != 200:
            raise ValueError(f"Epic rejected the code (HTTP {r.status}). Code is one-time & expires in ~5 min. Get a fresh one. Details: {text[:200]}")
        return json.loads(text)


async def epic_refresh(session: aiohttp.ClientSession, refresh_token: str) -> dict:
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {_EPIC_BASIC}",
    }
    body = {"grant_type": "refresh_token", "refresh_token": refresh_token}
    async with session.post(EPIC_TOKEN_URL, headers=headers, data=body, timeout=HTTP_TIMEOUT) as r:
        if r.status != 200:
            raise ValueError(f"Refresh token expired (HTTP {r.status}). Please /locker with a fresh code.")
        return await r.json()


async def epic_account(session: aiohttp.ClientSession, access_token: str, account_id: str) -> dict:
    headers = {"Authorization": f"Bearer {access_token}"}
    async with session.get(EPIC_ACCOUNT_URL.format(account_id=account_id), headers=headers, timeout=HTTP_TIMEOUT) as r:
        if r.status != 200:
            raise ValueError(f"Could not fetch Epic account (HTTP {r.status}).")
        return await r.json()


async def fn_query_profile(session: aiohttp.ClientSession, access_token: str, account_id: str, profile: str) -> dict:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    url = FN_PROFILE_URL.format(account_id=account_id, profile=profile)
    async with session.post(url, headers=headers, json={}, timeout=HTTP_TIMEOUT) as r:
        text = await r.text()
        if r.status != 200:
            raise ValueError(f"Fortnite profile '{profile}' query failed (HTTP {r.status}): {text[:200]}")
        return json.loads(text)


def parse_athena(profile: dict) -> tuple[dict, list[str]]:
    """Return (counts_by_label, skin_template_ids)."""
    items: dict = {}
    try:
        changes = profile.get("profileChanges", [])
        if changes:
            items = changes[0].get("profile", {}).get("items", {}) or {}
    except Exception:
        items = {}
    counts: dict[str, int] = {}
    skin_ids: list[str] = []
    for _iid, entry in items.items():
        tid = str(entry.get("templateId", ""))
        if ":" not in tid:
            continue
        kind, cid = tid.split(":", 1)
        kind_l = kind.lower()
        if kind_l == "athenacharacter":
            counts["Skins"] = counts.get("Skins", 0) + 1
            if cid and cid not in skin_ids:
                skin_ids.append(cid)
        elif kind_l == "athenabackpack":
            counts["Back Blings"] = counts.get("Back Blings", 0) + 1
        elif kind_l == "athenapickaxe":
            counts["Pickaxes"] = counts.get("Pickaxes", 0) + 1
        elif kind_l == "athenaglider":
            counts["Gliders"] = counts.get("Gliders", 0) + 1
        elif kind_l in ("athenadance", "athenaemote", "eid"):
            counts["Emotes"] = counts.get("Emotes", 0) + 1
        elif kind_l == "athenaitemwrap":
            counts["Wraps"] = counts.get("Wraps", 0) + 1
        elif kind_l in ("athenamusicpack", "athenaloadingscreen", "athenacontrail", "athenaspray"):
            counts[kind] = counts.get(kind, 0) + 1
        else:
            counts["Other"] = counts.get("Other", 0) + 1
    counts["Total items"] = len(items)
    return counts, skin_ids


def parse_vbucks(profile: dict) -> int | None:
    try:
        changes = profile.get("profileChanges", [])
        items = changes[0].get("profile", {}).get("items", {}) if changes else {}
        total = 0
        found = False
        for entry in items.values():
            tid = str(entry.get("templateId", ""))
            if tid.startswith("Currency:Mtx"):
                found = True
                total += int(entry.get("quantity", 0))
        return total if found else None
    except Exception:
        return None


RARITY_RANK = {
    "mythic": 7, "legendary": 6, "epic": 5, "rare": 4,
    "uncommon": 3, "common": 2, "": 1,
}


async def resolve_skins(session: aiohttp.ClientSession, skin_ids: list[str], limit: int = 12) -> list[dict]:
    """Resolve up to `limit` skin IDs concurrently, sorted by rarity."""
    sem = asyncio.Semaphore(5)

    async def one(cid: str):
        async with sem:
            try:
                return await fn_get_by_id(session, cid)
            except Exception:
                return None

    sample = skin_ids[: max(limit * 2, limit)]  # resolve a few extra so we can sort
    results = await asyncio.gather(*[one(c) for c in sample])
    resolved = [r for r in results if r]
    resolved.sort(
        key=lambda d: RARITY_RANK.get(str((d.get("rarity") or {}).get("value", "")).lower(), 0),
        reverse=True,
    )
    return resolved[:limit]


# ---------------------------------------------------------------------------
# Bot
# ---------------------------------------------------------------------------

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.tree.command(name="skin", description="Look up a Fortnite skin with images")
@app_commands.describe(name="Skin name, e.g. Renegade Raider")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def skin_command(interaction: discord.Interaction, name: str):
    name = name.strip()
    if not name:
        await interaction.response.send_message("Give me a skin name — e.g. `/skin name: Renegade Raider`", ephemeral=True)
        return
    await interaction.response.defer(thinking=True)
    try:
        async with aiohttp.ClientSession() as session:
            exact = await fn_search_exact(session, name)
            if exact:
                await interaction.followup.send(embed=cosmetic_embed(exact))
                return
            options = await fn_search_contains(session, name, limit=5)
            if not options:
                await interaction.followup.send(f"No skin found for **{name}**. Check spelling and try again.")
                return
            # Show best match + alternatives
            embeds = [cosmetic_embed(options[0])]
            if len(options) > 1:
                alt = "\n".join(f"• {o.get('name')} (`{o.get('id')}`)" for o in options[1:])
                more = discord.Embed(title="Did you mean…?", description=alt, color=discord.Color.greyple())
                embeds.append(more)
            await interaction.followup.send(embeds=embeds)
    except Exception as exc:
        await interaction.followup.send(f"Lookup failed: `{exc}`")


@bot.tree.command(name="shop", description="Show the current Fortnite Item Shop with images")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def shop_command(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(FN_API_SHOP, timeout=HTTP_TIMEOUT) as r:
                if r.status != 200:
                    await interaction.followup.send("Shop is unavailable right now. Try again later.")
                    return
                payload = await r.json()
        entries = (payload.get("data") or {}).get("entries") or []
        # Filter to real cosmetic offers (skip currency/virtual placeholders)
        offers = [e for e in entries if e.get("brItems")]
        if not offers:
            await interaction.followup.send("Shop is empty right now.")
            return
        date = (payload.get("data") or {}).get("date", "")[:10]
        header = discord.Embed(
            title=f"Fortnite Item Shop — {date}",
            description=f"{len(offers)} cosmetic offers today. Showing first 8:",
            color=discord.Color.gold(),
        )
        embeds: list[discord.Embed] = [header]
        for entry in offers[:8]:
            items = entry.get("brItems") or []
            if not items:
                continue
            first = items[0]
            price = entry.get("finalPrice", entry.get("regularPrice", "?"))
            names = ", ".join(i.get("name", "?") for i in items[:3])
            images = first.get("images") or {}
            img = images.get("featured") or images.get("icon") or images.get("smallIcon")
            e = discord.Embed(title=f"{names} — {price} V-Bucks", color=discord.Color.blue())
            if img:
                e.set_image(url=img)
            embeds.append(e)
        await interaction.followup.send(embeds=embeds[:10])
    except Exception as exc:
        await interaction.followup.send(f"Shop fetch failed: `{exc}`")


@bot.tree.command(name="locker_help", description="How to check your Epic locker (get your auth code)")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def locker_help_command(interaction: discord.Interaction):
    msg = (
        "**Check your Fortnite locker (shows skins with images)**\n\n"
        "**Steps (2 min, no password given to the bot):**\n"
        "1️⃣ Log in on epicgames.com in your browser (complete 2FA there).\n"
        "2️⃣ Open this link (logged-in tab):\n"
        f"<{AUTHCODE_REDIRECT_URL}>\n"
        "3️⃣ It shows JSON like `{\"authorizationCode\":\"abc123…\"}` — copy the code.\n"
        "4️⃣ Back here, run `/locker auth_code:abc123…` — **use it within ~5 min, one-time use.**\n\n"
        "⚠️ Treat the code like a password: use the bot in **DMs**, don't post it publicly. "
        "Run `/locker_logout` when done."
    )
    await interaction.response.send_message(msg, ephemeral=True)


@bot.tree.command(name="locker", description="Check your Epic Fortnite locker (skins + images)")
@app_commands.describe(auth_code="One-time Epic authorizationCode (see /locker_help). Omit to reuse saved login.")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def locker_command(interaction: discord.Interaction, auth_code: str | None = None):
    await interaction.response.defer(thinking=True, ephemeral=True)
    user_key = str(interaction.user.id)
    tokens = load_tokens()
    saved = tokens.get(user_key)

    try:
        async with aiohttp.ClientSession() as session:
            token_data: dict | None = None
            if auth_code and auth_code.strip():
                token_data = await epic_exchange_auth_code(session, auth_code.strip())
            elif saved and saved.get("refresh_token"):
                try:
                    refreshed = await epic_refresh(session, saved["refresh_token"])
                    # Epic refresh may omit account_id/displayName — keep old ones
                    token_data = {**saved, **refreshed}
                except Exception:
                    await interaction.followup.send(
                        "Saved login expired. Get a fresh code (see `/locker_help`) and run `/locker auth_code:...` again.",
                        ephemeral=True,
                    )
                    return
            else:
                await interaction.followup.send(
                    "No saved login. See `/locker_help`, then run `/locker auth_code:YOUR_CODE`.",
                    ephemeral=True,
                )
                return

            access = token_data["access_token"]
            account_id = token_data.get("account_id") or (saved or {}).get("account_id")
            if not account_id:
                raise ValueError("Epic did not return an account_id.")

            # Persist (merge display info later)
            tokens[user_key] = {
                "access_token": access,
                "refresh_token": token_data.get("refresh_token", (saved or {}).get("refresh_token", "")),
                "account_id": account_id,
                "expires_at": time.time() + int(token_data.get("expires_in", 7200)),
            }
            save_tokens(tokens)

            try:
                acc = await epic_account(session, access, account_id)
                display = acc.get("displayName", "Unknown")
            except Exception:
                display = token_data.get("displayName", "Unknown")
            tokens[user_key]["displayName"] = display
            save_tokens(tokens)

            athena = await fn_query_profile(session, access, account_id, "athena")
            try:
                core = await fn_query_profile(session, access, account_id, "common_core")
                vbucks = parse_vbucks(core)
            except Exception:
                vbucks = None

            counts, skin_ids = parse_athena(athena)
            header = discord.Embed(
                title=f"{display}'s Fortnite locker",
                color=discord.Color.green(),
            )
            lines = [f"**{k}:** {v}" for k, v in counts.items()]
            if vbucks is not None:
                lines.append(f"**V-Bucks:** {vbucks:,} 💰")
            header.description = "\n".join(lines) or "Empty locker?"
            header.set_footer(text=f"{len(skin_ids)} skins total · showing rarest first · /locker_logout to forget login")

            if not skin_ids:
                await interaction.followup.send(embed=header, ephemeral=True)
                return

            resolved = await resolve_skins(session, skin_ids, limit=8)
            embeds: list[discord.Embed] = [header]
            for item in resolved:
                embeds.append(cosmetic_embed(item))
            # Discord caps at 10 embeds per message
            await interaction.followup.send(embeds=embeds[:10], ephemeral=True)

    except Exception as exc:
        await interaction.followup.send(f"Locker check failed: `{exc}`", ephemeral=True)


@bot.tree.command(name="locker_logout", description="Delete your saved Epic login from the bot")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def locker_logout_command(interaction: discord.Interaction):
    tokens = load_tokens()
    if str(interaction.user.id) in tokens:
        del tokens[str(interaction.user.id)]
        save_tokens(tokens)
        await interaction.response.send_message("Logged out — saved Epic token deleted. ✅", ephemeral=True)
    else:
        await interaction.response.send_message("No saved login found.", ephemeral=True)


@bot.event
async def on_ready():
    try:
        guild_id = os.getenv("GUILD_ID", "").strip()
        if guild_id:
            guild = discord.Object(id=int(guild_id))
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            print(f"[ready] synced {len(synced)} command(s) to test guild {guild_id}")
        synced = await bot.tree.sync()
        print(f"[ready] synced {len(synced)} global command(s)")
    except Exception as exc:
        print(f"[ready] command sync failed: {exc}")
    print(f"[ready] logged in as {bot.user}")


def get_token() -> str:
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("\"'"))
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token:
        print("ERROR: DISCORD_TOKEN is not set.\n  1. cp .env.example .env\n  2. paste your bot token into .env\n  3. python bot.py", file=sys.stderr)
        sys.exit(1)
    return token


if __name__ == "__main__":
    bot.run(get_token())
