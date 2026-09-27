"""Fortnite skin checker Discord bot — entry point. Loads all cogs.

Commands (17):
    Skins:  /skin (autocomplete + images) /search /random /compare /set /rarity /lastseen
    Shop:   /shop (paginated) /shop_search
    Locker: /locker_help /locker (paginated skins) /locker_logout
    Extra:  /stats (needs free API key) /news /map

Run:  cp .env.example .env  ->  paste DISCORD_TOKEN  ->  python bot.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import discord
from discord.ext import commands

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

COGS = ("cogs.skins", "cogs.shop", "cogs.locker", "cogs.stats", "cogs.news")

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def setup_hook():
    for ext in COGS:
        try:
            await bot.load_extension(ext)
            print(f"[cogs] loaded {ext}")
        except Exception as exc:
            print(f"[cogs] FAILED {ext}: {exc}")


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
        print(
            "ERROR: DISCORD_TOKEN is not set.\n"
            "  1. cp .env.example .env\n"
            "  2. paste your bot token into .env\n"
            "  3. python bot.py",
            file=sys.stderr,
        )
        sys.exit(1)
    return token


if __name__ == "__main__":
    bot.run(get_token())
