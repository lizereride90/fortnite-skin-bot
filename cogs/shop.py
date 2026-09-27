"""Item Shop commands: /shop (paginated with images) + /shop_search."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import Pages
from utils.fn_api import FnAPI

fn = FnAPI()
ALLOW = dict(guilds=True, users=True)
CTX = dict(guilds=True, dms=True, private_channels=True)


def offer_embed(entry: dict, date: str, page: int, total: int) -> discord.Embed:
    items = entry.get("brItems") or []
    first = items[0]
    price = entry.get("finalPrice", entry.get("regularPrice", "?"))
    names = ", ".join(i.get("name", "?") for i in items[:4])
    images = first.get("images") or {}
    img = images.get("featured") or images.get("icon") or images.get("smallIcon")
    rarity = (first.get("rarity") or {}).get("displayValue", "?")
    embed = discord.Embed(
        title=f"{names}",
        description=f"💰 **{price}** V-Bucks · {rarity}",
        color=discord.Color.gold(),
    )
    lines = [
        f"• {i.get('name')} (`{(i.get('type') or {}).get('displayValue', '?')}`)"
        for i in items[:6]
    ]
    embed.add_field(name=f"Bundle contents ({len(items)})", value="\n".join(lines)[:1024], inline=False)
    embed.set_footer(text=f"Shop {date} · {page}/{total}")
    if img:
        embed.set_image(url=img)
    return embed


class Shop(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="shop", description="Current Fortnite Item Shop with images (paginated)")
    @app_commands.allowed_installs(**ALLOW)
    @app_commands.allowed_contexts(**CTX)
    async def shop(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        try:
            date, offers = await fn.get_shop()
            if not offers:
                return await interaction.followup.send("Shop is empty right now.")
            header = discord.Embed(
                title=f"🛒 Item Shop — {date}",
                description=f"**{len(offers)}** cosmetic offers. Flip pages with ◀ ▶.",
                color=discord.Color.gold(),
            )
            per_page = 2
            pages: list[list[discord.Embed]] = [[header]]
            for i in range(0, min(len(offers), 60), per_page):
                chunk = offers[i:i + per_page]
                page_no = i // per_page + 1
                total = (min(len(offers), 60) + per_page - 1) // per_page
                pages.append([offer_embed(e, date, page_no, total) for e in chunk])
            await interaction.followup.send(embeds=pages[0], view=Pages(pages))
        except Exception as exc:
            await interaction.followup.send(f"Shop fetch failed: `{exc}`")

    @app_commands.command(name="shop_search", description="Is a specific skin in today's shop?")
    @app_commands.describe(query="Skin or item name")
    @app_commands.allowed_installs(**ALLOW)
    @app_commands.allowed_contexts(**CTX)
    async def shop_search(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer(thinking=True)
        try:
            date, offers = await fn.get_shop()
            q = query.strip().lower()
            hits = [e for e in offers
                    if any(q in str(i.get("name", "")).lower() for i in (e.get("brItems") or []))]
            if not hits:
                return await interaction.followup.send(
                    f"**{query}** is NOT in today's shop ({date}). Try `/lastseen name:{query}`."
                )
            pages = [[offer_embed(e, date, n + 1, len(hits))] for n, e in enumerate(hits[:10])]
            await interaction.followup.send(
                content=f"✅ **{query}** IS in today's shop ({len(hits)} offer(s)):",
                embeds=pages[0],
                view=Pages(pages) if len(pages) > 1 else None,
            )
        except Exception as exc:
            await interaction.followup.send(f"Shop search failed: `{exc}`")


async def setup(bot: commands.Bot):
    await bot.add_cog(Shop(bot))
