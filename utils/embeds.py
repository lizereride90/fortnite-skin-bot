"""Embed builders + button pagination."""

from __future__ import annotations

import discord

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
    return RARITY_COLORS.get((series_value or "").lower().replace(" ", ""), discord.Color.blurple())


def cosmetic_embed(item: dict) -> discord.Embed:
    """Rich embed with images + variants, tags, shop history."""
    name = item.get("name", "Unknown")
    desc = item.get("description", "") or "_No description_"
    ctype = (item.get("type") or {}).get("displayValue", "?")
    rarity = (item.get("rarity") or {}).get("displayValue", "?")
    rarity_backend = (item.get("rarity") or {}).get("value", "")
    series = item.get("series") or {}
    set_ = item.get("set") or {}
    intro = item.get("introduction") or {}
    images = item.get("images") or {}
    variants = item.get("variants") or []
    gameplay = item.get("gameplayTags") or []
    shop_hist = item.get("shopHistory") or []
    added = str(item.get("added", ""))[:10]

    main_img = images.get("featured") or images.get("icon") or images.get("smallIcon")
    thumb = images.get("smallIcon")

    embed = discord.Embed(
        title=name, description=desc, color=rarity_color(rarity_backend, series.get("value", ""))
    )
    embed.add_field(name="Type", value=str(ctype), inline=True)
    embed.add_field(name="Rarity", value=str(rarity), inline=True)
    if series.get("name"):
        embed.add_field(name="Series", value=str(series["name"]), inline=True)
    if set_.get("value"):
        embed.add_field(name="Set", value=str(set_["value"]), inline=True)
    if intro.get("text"):
        embed.add_field(name="Introduced", value=str(intro["text"]), inline=True)
    if added:
        embed.add_field(name="Added", value=added, inline=True)
    if variants:
        styles = "; ".join(
            f"{v.get('channel', '?')}: {len(v.get('options', []))}" for v in variants[:4]
        )
        embed.add_field(name=f"Styles ({len(variants)} channels)", value=styles[:1024], inline=False)
    if gameplay:
        embed.add_field(name="Tags", value=", ".join(map(str, gameplay[:8]))[:1024], inline=False)
    footer = f"ID: {item.get('id')}"
    if shop_hist:
        footer += f" · shop appearances: {len(shop_hist)} · last: {shop_hist[-1][:10]}"
    else:
        footer += " · never in shop / unreleased"
    if images.get("lego"):
        footer += " · LEGO ✅"
    embed.set_footer(text=footer)
    if main_img:
        embed.set_image(url=main_img)
    if thumb and thumb != main_img:
        embed.set_thumbnail(url=thumb)
    return embed


class Pages(discord.ui.View):
    """Button paginator. Each page = list of embeds (max 10)."""

    def __init__(self, pages: list[list[discord.Embed]], timeout: float = 300):
        super().__init__(timeout=timeout)
        self.pages = pages
        self.idx = 0
        self._sync_label()

    def _sync_label(self) -> None:
        self.page_label.label = f"{self.idx + 1}/{len(self.pages)}"
        self.prev_btn.disabled = self.idx == 0
        self.next_btn.disabled = self.idx == len(self.pages) - 1

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, _button: discord.ui.Button):
        self.idx = max(0, self.idx - 1)
        self._sync_label()
        await interaction.response.edit_message(embeds=self.pages[self.idx], view=self)

    @discord.ui.button(label="1/1", style=discord.ButtonStyle.secondary, disabled=True)
    async def page_label(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await interaction.response.defer()

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, _button: discord.ui.Button):
        self.idx = min(len(self.pages) - 1, self.idx + 1)
        self._sync_label()
        await interaction.response.edit_message(embeds=self.pages[self.idx], view=self)

    @discord.ui.button(label="✕", style=discord.ButtonStyle.danger)
    async def close_btn(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await interaction.message.delete()
        self.stop()
