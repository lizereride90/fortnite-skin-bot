"""Player stats: /stats (needs free fortnite-api.com key)."""

from __future__ import annotations

import os

import discord
from discord import app_commands
from discord.ext import commands

from utils.fn_api import FnAPI

fn = FnAPI()
ALLOW = dict(guilds=True, users=True)
CTX = dict(guilds=True, dms=True, private_channels=True)


def _mode_block(stats: dict, mode: str) -> str:
    m = (stats.get(mode) or {}) if stats else {}
    if not m or not m.get("matches"):
        return "—"
    return (
        f"W **{m.get('wins', 0)}** · K **{m.get('kills', 0)}**\n"
        f"KD **{m.get('kd', 0)}** · WR **{m.get('winRate', 0)}%**\n"
        f"Matches **{m.get('matches', 0)}**"
    )


class Stats(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="stats", description="Fortnite BR stats for a player")
    @app_commands.describe(username="Epic username", account_type="Account platform")
    @app_commands.choices(account_type=[
        app_commands.Choice(name="Epic", value="epic"),
        app_commands.Choice(name="PlayStation", value="psn"),
        app_commands.Choice(name="Xbox", value="xbl"),
    ])
    @app_commands.allowed_installs(**ALLOW)
    @app_commands.allowed_contexts(**CTX)
    async def stats(self, interaction: discord.Interaction, username: str, account_type: str = "epic"):
        api_key = os.getenv("FORTNITE_API_KEY", "").strip()
        if not api_key:
            return await interaction.response.send_message(
                "**/stats needs a free API key.**\n"
                "1. Get one at https://dash.fortnite-api.com (free).\n"
                "2. Bot host: add `FORTNITE_API_KEY=...` to `.env` and restart.\n"
                "Meanwhile try `/skin`, `/shop`, `/news`, `/locker`.",
                ephemeral=True,
            )
        await interaction.response.defer(thinking=True)
        try:
            data = await fn.get_stats(username, api_key)
            account = data.get("account") or {}
            bp = data.get("battlePass") or {}
            stats = data.get("stats") or {}
            overall = stats.get("all", {}).get("overall") or {}
            embed = discord.Embed(
                title=f"📊 {account.get('name', username)}",
                description=(
                    f"Level **{account.get('level', '?')}**"
                    f" · BP level **{bp.get('level', '?')}**"
                    f"\nWins **{overall.get('wins', 0)}** · Kills **{overall.get('kills', 0)}**"
                    f" · KD **{overall.get('kd', 0)}** · WR **{overall.get('winRate', 0)}%**"
                    f" · Matches **{overall.get('matches', 0)}**"
                ),
                color=discord.Color.blue(),
            )
            all_modes = stats.get("all") or {}
            for mode, label in (("solo", "Solo"), ("duo", "Duos"), ("trio", "Trios"), ("squad", "Squads")):
                embed.add_field(name=label, value=_mode_block(all_modes, mode), inline=True)
            embed.set_footer(text=f"via fortnite-api.com · {account_type}")
            await interaction.followup.send(embed=embed)
        except Exception as exc:
            await interaction.followup.send(
                f"Stats lookup failed: `{exc}` (private accounts or unknown names fail)."
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Stats(bot))
