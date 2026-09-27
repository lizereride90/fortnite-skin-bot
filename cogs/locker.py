"""Epic locker checker: /locker_help /locker (paginated skins w/ images) /locker_logout."""

from __future__ import annotations

import asyncio
import time

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

import config
from utils import epic
from utils.embeds import Pages, cosmetic_embed
from utils.fn_api import FnAPI
from utils import store

fn = FnAPI()
ALLOW = dict(guilds=True, users=True)
CTX = dict(guilds=True, dms=True, private_channels=True)
MAX_RESOLVE = 40  # max skins resolved to names/images per check
PER_PAGE = 4


class Locker(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="locker_help", description="How to check your Epic locker (get your auth code)")
    @app_commands.allowed_installs(**ALLOW)
    @app_commands.allowed_contexts(**CTX)
    async def locker_help(self, interaction: discord.Interaction):
        msg = (
            "**Check your Fortnite locker (skins with images)**\n\n"
            "1️⃣ Log in on **epicgames.com** in your browser (finish 2FA there).\n"
            "2️⃣ Open this link in the same logged-in tab:\n"
            f"<{config.AUTHCODE_REDIRECT_URL}>\n"
            "3️⃣ It shows JSON like `{\"authorizationCode\":\"abc123…\"}` — copy the code.\n"
            "4️⃣ Back here: `/locker auth_code:abc123…` — **within ~5 min, one-time use.**\n\n"
            "⚠️ Treat the code like a password — use the bot in **DMs**. "
            "Run `/locker_logout` when done."
        )
        await interaction.response.send_message(msg, ephemeral=True)

    @app_commands.command(name="locker", description="Check your Epic Fortnite locker (skins + images)")
    @app_commands.describe(auth_code="One-time Epic code (see /locker_help). Omit to reuse saved login.")
    @app_commands.allowed_installs(**ALLOW)
    @app_commands.allowed_contexts(**CTX)
    async def locker(self, interaction: discord.Interaction, auth_code: str | None = None):
        await interaction.response.defer(thinking=True, ephemeral=True)
        saved = store.get(interaction.user.id)
        try:
            async with aiohttp.ClientSession() as session:
                if auth_code and auth_code.strip():
                    token_data = await epic.exchange_auth_code(session, auth_code.strip())
                elif saved and saved.get("refresh_token"):
                    try:
                        token_data = {**saved, **await epic.refresh(session, saved["refresh_token"])}
                    except Exception:
                        return await interaction.followup.send(
                            "Saved login expired — get a fresh code (`/locker_help`) and run "
                            "`/locker auth_code:...` again.",
                            ephemeral=True,
                        )
                else:
                    return await interaction.followup.send(
                        "No saved login. See `/locker_help`, then `/locker auth_code:YOUR_CODE`.",
                        ephemeral=True,
                    )

                access = token_data["access_token"]
                account_id = token_data.get("account_id") or (saved or {}).get("account_id")
                if not account_id:
                    raise ValueError("Epic did not return an account_id.")
                store.put(interaction.user.id, {
                    "access_token": access,
                    "refresh_token": token_data.get("refresh_token", (saved or {}).get("refresh_token", "")),
                    "account_id": account_id,
                    "expires_at": time.time() + int(token_data.get("expires_in", 7200)),
                })

                try:
                    display = (await epic.account(session, access, account_id)).get("displayName", "?")
                except Exception:
                    display = token_data.get("displayName", "?")
                entry = store.get(interaction.user.id) or {}
                entry["displayName"] = display
                store.put(interaction.user.id, entry)

                athena = await epic.query_profile(session, access, account_id, "athena")
                try:
                    vbucks = epic.parse_vbucks(
                        await epic.query_profile(session, access, account_id, "common_core")
                    )
                except Exception:
                    vbucks = None

                counts, skin_ids = epic.parse_athena(athena)
                header = discord.Embed(title=f"🔐 {display}'s locker", color=discord.Color.green())
                header.description = "\n".join(f"**{k}:** {v}" for k, v in counts.items())
                if vbucks is not None:
                    header.description += f"\n**V-Bucks:** {vbucks:,} 💰"
                header.set_footer(text=f"{len(skin_ids)} skins · rarest first · /locker_logout to forget login")

                if not skin_ids:
                    return await interaction.followup.send(embed=header, ephemeral=True)

                # Resolve top skins concurrently, sort rarest-first
                sem = asyncio.Semaphore(5)

                async def one(cid: str):
                    async with sem:
                        try:
                            return await fn.get_by_id(cid)
                        except Exception:
                            return None

                resolved = [r for r in await asyncio.gather(
                    *[one(c) for c in skin_ids[:MAX_RESOLVE]]
                ) if r]
                resolved.sort(
                    key=lambda d: config.RARITY_RANK.get(
                        str((d.get("rarity") or {}).get("value", "")).lower(), 0),
                    reverse=True,
                )
                shown = resolved[:24]
                pages: list[list[discord.Embed]] = [[header]]
                for i in range(0, len(shown), PER_PAGE):
                    pages.append([cosmetic_embed(s) for s in shown[i:i + PER_PAGE]])
                if len(skin_ids) > len(shown):
                    header.description += f"\n_Showing top {len(shown)} rarest._"
                await interaction.followup.send(embeds=pages[0], view=Pages(pages), ephemeral=True)
        except Exception as exc:
            await interaction.followup.send(f"Locker check failed: `{exc}`", ephemeral=True)

    @app_commands.command(name="locker_logout", description="Delete your saved Epic login from the bot")
    @app_commands.allowed_installs(**ALLOW)
    @app_commands.allowed_contexts(**CTX)
    async def locker_logout(self, interaction: discord.Interaction):
        if store.delete(interaction.user.id):
            await interaction.response.send_message("Logged out — saved Epic token deleted. ✅", ephemeral=True)
        else:
            await interaction.response.send_message("No saved login found.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Locker(bot))
