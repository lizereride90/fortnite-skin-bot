"""Skin lookup commands with images: /skin /search /random /compare /set /rarity /lastseen."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import Pages, cosmetic_embed
from utils.fn_api import FnAPI

fn = FnAPI()
ALLOW = dict(guilds=True, users=True)
CTX = dict(guilds=True, dms=True, private_channels=True)


async def name_autocomplete(interaction: discord.Interaction, current: str):
    try:
        pairs = await fn.autocomplete_names(current)
        return [app_commands.Choice(name=label, value=cid) for label, cid in pairs][:25]
    except Exception:
        return []


async def resolve_name_or_id(value: str) -> dict | None:
    """Autocomplete passes an id; typed text passes a name. Handle both."""
    value = value.strip()
    if value and " " not in value and "_" in value:
        item = await fn.get_by_id(value)
        if item:
            return item
    return await fn.search_exact(value)


class Skins(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="skin", description="Look up a Fortnite skin with images")
    @app_commands.describe(name="Start typing — suggestions appear, or type full name")
    @app_commands.autocomplete(name=name_autocomplete)
    @app_commands.allowed_installs(**ALLOW)
    @app_commands.allowed_contexts(**CTX)
    async def skin(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(thinking=True)
        try:
            item = await resolve_name_or_id(name)
            if item:
                return await interaction.followup.send(embed=cosmetic_embed(item))
            options = await fn.search_contains(name, limit=5)
            if not options:
                return await interaction.followup.send(
                    f"No skin found for **{name}**. Try the suggestions while typing."
                )
            pages = [[cosmetic_embed(o)] for o in options[:5]]
            await interaction.followup.send(
                content=f"No exact match — closest {len(pages)} result(s) for **{name}**:",
                embeds=pages[0],
                view=Pages(pages) if len(pages) > 1 else None,
            )
        except Exception as exc:
            await interaction.followup.send(f"Lookup failed: `{exc}`")

    @app_commands.command(name="search", description="Search skins by partial name (up to 8 results)")
    @app_commands.autocomplete(query=name_autocomplete)
    @app_commands.allowed_installs(**ALLOW)
    @app_commands.allowed_contexts(**CTX)
    async def search(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer(thinking=True)
        try:
            # autocomplete may hand us an id
            if query and " " not in query and "_" in query:
                item = await fn.get_by_id(query)
                items = [item] if item else []
            else:
                items = await fn.search_contains(query, limit=8)
            if not items:
                return await interaction.followup.send(f"Nothing found for **{query}**.")
            pages = [[cosmetic_embed(i)] for i in items]
            await interaction.followup.send(
                content=f"🔎 {len(items)} result(s) for **{query}**:",
                embeds=pages[0],
                view=Pages(pages) if len(pages) > 1 else None,
            )
        except Exception as exc:
            await interaction.followup.send(f"Search failed: `{exc}`")

    @app_commands.command(name="random", description="Random Fortnite cosmetic with image")
    @app_commands.describe(kind="Type of cosmetic")
    @app_commands.choices(kind=[
        app_commands.Choice(name="Outfit", value="outfit"),
        app_commands.Choice(name="Back Bling", value="backpack"),
        app_commands.Choice(name="Pickaxe", value="pickaxe"),
        app_commands.Choice(name="Glider", value="glider"),
        app_commands.Choice(name="Emote", value="emote"),
        app_commands.Choice(name="Wrap", value="wrap"),
        app_commands.Choice(name="Music / Lobby", value="music"),
        app_commands.Choice(name="Loading Screen", value="loadingscreen"),
        app_commands.Choice(name="Contrail", value="contrail"),
        app_commands.Choice(name="Spray", value="spray"),
    ])
    @app_commands.allowed_installs(**ALLOW)
    @app_commands.allowed_contexts(**CTX)
    async def random_cmd(self, interaction: discord.Interaction, kind: str = "outfit"):
        await interaction.response.defer(thinking=True)
        try:
            item = await fn.random_pick(kind)
            if not item:
                return await interaction.followup.send(f"No cosmetics of type `{kind}` found.")
            await interaction.followup.send(
                content=f"🎲 Random {kind}:", embed=cosmetic_embed(item)
            )
        except Exception as exc:
            await interaction.followup.send(f"Random failed: `{exc}`")

    @app_commands.command(name="compare", description="Compare two skins side by side with images")
    @app_commands.autocomplete(first=name_autocomplete, second=name_autocomplete)
    @app_commands.allowed_installs(**ALLOW)
    @app_commands.allowed_contexts(**CTX)
    async def compare(self, interaction: discord.Interaction, first: str, second: str):
        await interaction.response.defer(thinking=True)
        try:
            a = await resolve_name_or_id(first)
            b = await resolve_name_or_id(second)
            missing = [n for n, v in ((first, a), (second, b)) if not v]
            if missing:
                return await interaction.followup.send(f"Not found: **{', '.join(missing)}**")
            assert a and b
            verdict = discord.Embed(title="⚖️ Verdict", color=discord.Color.gold())
            for label, key in (("Rarity", "rarity"), ("Type", "type")):
                va = (a.get(key) or {}).get("displayValue", "?")
                vb = (b.get(key) or {}).get("displayValue", "?")
                verdict.add_field(name=label, value=f"{a.get('name')}: {va}\n{b.get('name')}: {vb}", inline=True)
            ha, hb = len(a.get("shopHistory") or []), len(b.get("shopHistory") or [])
            verdict.add_field(
                name="Shop appearances",
                value=f"{a.get('name')}: {ha}\n{b.get('name')}: {hb}",
                inline=True,
            )
            await interaction.followup.send(embeds=[cosmetic_embed(a), cosmetic_embed(b), verdict])
        except Exception as exc:
            await interaction.followup.send(f"Compare failed: `{exc}`")

    @app_commands.command(name="set", description="Show skins in an item set (e.g. Skull Squad)")
    @app_commands.allowed_installs(**ALLOW)
    @app_commands.allowed_contexts(**CTX)
    async def set_cmd(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(thinking=True)
        try:
            items = await fn.by_set(name, limit=6)
            if not items:
                return await interaction.followup.send(
                    f"No set matching **{name}**. Try `/search` to find the exact set name."
                )
            pages = [[cosmetic_embed(i)] for i in items]
            await interaction.followup.send(
                content=f"📦 Set matches for **{name}** ({len(items)} shown):",
                embeds=pages[0],
                view=Pages(pages) if len(pages) > 1 else None,
            )
        except Exception as exc:
            await interaction.followup.send(f"Set lookup failed: `{exc}`")

    @app_commands.command(name="rarity", description="Browse random skins of a rarity with images")
    @app_commands.choices(rarity=[
        app_commands.Choice(name="Common", value="common"),
        app_commands.Choice(name="Uncommon", value="uncommon"),
        app_commands.Choice(name="Rare", value="rare"),
        app_commands.Choice(name="Epic", value="epic"),
        app_commands.Choice(name="Legendary", value="legendary"),
        app_commands.Choice(name="Mythic", value="mythic"),
        app_commands.Choice(name="Icon Series", value="icon"),
    ])
    @app_commands.allowed_installs(**ALLOW)
    @app_commands.allowed_contexts(**CTX)
    async def rarity(self, interaction: discord.Interaction, rarity: str):
        await interaction.response.defer(thinking=True)
        try:
            items = await fn.by_rarity(rarity, limit=6)
            if not items:
                return await interaction.followup.send(f"No {rarity} cosmetics found.")
            pages = [[cosmetic_embed(i)] for i in items]
            await interaction.followup.send(
                content=f"✨ Random **{rarity}** picks:",
                embeds=pages[0],
                view=Pages(pages) if len(pages) > 1 else None,
            )
        except Exception as exc:
            await interaction.followup.send(f"Rarity browse failed: `{exc}`")

    @app_commands.command(name="lastseen", description="When was a skin last in the Item Shop?")
    @app_commands.autocomplete(name=name_autocomplete)
    @app_commands.allowed_installs(**ALLOW)
    @app_commands.allowed_contexts(**CTX)
    async def lastseen(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(thinking=True)
        try:
            item = await resolve_name_or_id(name)
            if not item:
                return await interaction.followup.send(f"No skin found for **{name}**.")
            hist = item.get("shopHistory") or []
            embed = cosmetic_embed(item)
            if hist:
                dates = "\n".join(f"• {d[:10]}" for d in hist[-10:][::-1])
                embed.add_field(
                    name=f"Shop history ({len(hist)}x, latest first)",
                    value=dates[:1024],
                    inline=False,
                )
            else:
                embed.add_field(name="Shop history", value="Never in shop / unreleased.", inline=False)
            await interaction.followup.send(embed=embed)
        except Exception as exc:
            await interaction.followup.send(f"Lookup failed: `{exc}`")


async def setup(bot: commands.Bot):
    await bot.add_cog(Skins(bot))
