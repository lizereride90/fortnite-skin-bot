"""News + map: /news (paginated MOTDs with images) + /map (POI map)."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import Pages
from utils.fn_api import FnAPI

fn = FnAPI()
ALLOW = dict(guilds=True, users=True)
CTX = dict(guilds=True, dms=True, private_channels=True)


class News(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="news", description="Latest Fortnite Battle Royale news with images")
    @app_commands.allowed_installs(**ALLOW)
    @app_commands.allowed_contexts(**CTX)
    async def news(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        try:
            motds = [m for m in await fn.get_news() if not m.get("hidden")]
            if not motds:
                return await interaction.followup.send("No news right now.")
            pages: list[list[discord.Embed]] = []
            for m in motds[:10]:
                body = str(m.get("body", ""))[:500]
                embed = discord.Embed(
                    title=f"📰 {m.get('title', 'News')}",
                    description=body,
                    color=discord.Color.blurple(),
                )
                img = m.get("image") or m.get("tileImage")
                if img:
                    embed.set_image(url=img)
                pages.append([embed])
            await interaction.followup.send(embeds=pages[0], view=Pages(pages) if len(pages) > 1 else None)
        except Exception as exc:
            await interaction.followup.send(f"News fetch failed: `{exc}`")

    @app_commands.command(name="map", description="Current Fortnite map with POI locations")
    @app_commands.allowed_installs(**ALLOW)
    @app_commands.allowed_contexts(**CTX)
    async def map_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        try:
            data = await fn.get_map()
            images = data.get("images") or {}
            pois = data.get("pois") or []
            embed = discord.Embed(
                title="🗺️ Current Fortnite Map",
                description=f"**{len(pois)}** named POIs:\n"
                + ", ".join(f"`{p.get('name')}`" for p in pois[:40])[:1900],
                color=discord.Color.green(),
            )
            if images.get("pois"):
                embed.set_image(url=images["pois"])
            await interaction.followup.send(embed=embed)
        except Exception as exc:
            await interaction.followup.send(f"Map fetch failed: `{exc}`")


async def setup(bot: commands.Bot):
    await bot.add_cog(News(bot))
