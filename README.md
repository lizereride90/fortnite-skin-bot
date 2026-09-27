# Fortnite Skin Checker Discord Bot

`/skin` lookup with images + `/shop` + Epic `/locker` checker.

Powered by free [fortnite-api.com](https://fortnite-api.com) (images) + Epic OAuth (locker).
No password is ever given to the bot — locker login uses a one-time Epic auth code.

## Commands

| Command | What it does |
|---|---|
| `/skin name:Renegade Raider` | Skin info embed with image, rarity, set |
| `/shop` | Current Item Shop with images |
| `/locker_help` | How to get your Epic auth code |
| `/locker auth_code:XXX` | Check your Epic locker (private reply with skin images) |
| `/locker` | Re-check using saved login |
| `/locker_logout` | Delete saved Epic token |

## Setup

1. Create a bot at https://discord.com/developers/applications → Bot → copy token.
   Enable **User Install** if you want it usable in DMs (like the rewrite bot):
   OAuth2 → `integration_types`: Guild Install + User Install, scope `applications.commands`.
2. Install:
```bash
cd fortnite-skin-bot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env, paste DISCORD_TOKEN
python bot.py
```
3. Invite the bot, then in Discord run `/skin name: Renegade Raider`.

## Getting your Epic auth code (for /locker)

1. Log in on epicgames.com in your browser (finish 2FA there).
2. In the same logged-in tab open:
   `https://www.epicgames.com/id/login?redirectUrl=https://www.epicgames.com/id/api/redirect?clientId=ec684b8c687f479fadea3cb2ad83f5c6`
3. Copy the `authorizationCode` from the JSON.
4. In Discord **DMs** with the bot: `/locker auth_code:YOUR_CODE` (one-time, ~5 min expiry).
5. `/locker_logout` when done. Tokens live only in local `tokens.json` (chmod 600).

## Notes

- Locker replies are **ephemeral** (only you see them) — still, prefer DMs.
- Auth codes are one-time; an already-used code gives "Epic rejected the code" — just grab a fresh one.
- If Epic changes its client secret/endpoints, update `EPIC_CLIENT_ID/SECRET` at the top of `bot.py`.
