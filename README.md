# Fortnite Skin Checker Discord Bot

17 slash commands, skin images everywhere, paginated shop/locker, Epic locker checker, player stats, news + map.

Powered by free [fortnite-api.com](https://fortnite-api.com) (images) + Epic OAuth (locker).
No password is ever given to the bot — locker login uses a one-time Epic auth code.

## Commands

| Command | What it does |
|---|---|
| `/skin name:...` | Skin lookup with image, rarity, set, styles, tags, shop history — **with autocomplete** |
| `/search query:...` | Up to 8 partial-name results, paged with ◀ ▶ |
| `/random kind:...` | Random outfit / back bling / pickaxe / glider / emote / wrap / music / loading / contrail / spray |
| `/compare first:... second:...` | Two skins side-by-side with images + verdict (rarity, shop appearances) |
| `/set name:...` | Skins in an item set (e.g. Skull Squad) |
| `/rarity rarity:...` | Random picks of a rarity (Common → Mythic, Icon) |
| `/lastseen name:...` | Every shop appearance date for a skin |
| `/shop` | Today's shop, **paginated** with images + prices |
| `/shop_search query:...` | Is a skin in today's shop right now? |
| `/locker_help` | How to get your Epic auth code |
| `/locker auth_code:...` | Your full locker: counts, V-Bucks + top 24 rarest skins with images, **paginated** (private) |
| `/locker_logout` | Delete saved Epic token |
| `/stats username:...` | BR stats: level, wins/KD/WR overall + Solo/Duos/Trios/Squads (needs free API key) |
| `/news` | Latest BR news, paginated with images |
| `/map` | Current map image + all POI names |

## Setup

1. Create a bot at https://discord.com/developers/applications → Bot → copy token.
   OAuth2 → enable **Guild Install + User Install**, scope `applications.commands` (works in DMs).
2. Install:
```bash
cd fortnite-skin-bot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env: DISCORD_TOKEN=... (+ optional GUILD_ID, FORTNITE_API_KEY)
python bot.py
```

## Project layout

```
bot.py          entry point, loads cogs, syncs commands
config.py       API URLs, Epic client, rarity ranks, type filters
cogs/
  skins.py      /skin /search /random /compare /set /rarity /lastseen
  shop.py       /shop /shop_search
  locker.py     /locker_help /locker /locker_logout
  stats.py      /stats
  news.py       /news /map
utils/
  fn_api.py     fortnite-api.com client with TTL caches
  epic.py       Epic OAuth + QueryProfile + locker parsing
  embeds.py     rarity colors, rich cosmetic embeds, button paginator
  store.py      per-user token storage (chmod 600 json)
```

## Epic auth code (for /locker)

1. Log in on epicgames.com (finish 2FA there).
2. In the same tab open the link `/locker_help` gives you.
3. Copy the `authorizationCode`, run `/locker auth_code:...` in **DMs** (one-time, ~5 min expiry).
4. `/locker_logout` when done. Tokens live only in local `tokens.json`.

## Notes

- Locker replies are **ephemeral** (only you see them) — still prefer DMs.
- `/stats` needs a free key from https://dash.fortnite-api.com (stats endpoint is key-only).
- If Epic rotates its client secret/endpoints, update `config.py`.
