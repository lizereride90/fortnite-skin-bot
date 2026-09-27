"""Shared constants for the Fortnite skin checker bot."""

import base64

# --- fortnite-api.com (free, no key, has images) ---
FN_SEARCH = "https://fortnite-api.com/v2/cosmetics/br/search"
FN_SEARCH_ALL = "https://fortnite-api.com/v2/cosmetics/br/search/all"
FN_BY_ID = "https://fortnite-api.com/v2/cosmetics/br/{id}"
FN_ALL = "https://fortnite-api.com/v2/cosmetics/br"
FN_SHOP = "https://fortnite-api.com/v2/shop"
FN_NEWS_BR = "https://fortnite-api.com/v2/news/br"
FN_MAP = "https://fortnite-api.com/v1/map"
FN_STATS = "https://fortnite-api.com/v2/stats/br/v2"

# --- Epic OAuth + Fortnite profile (locker checker) ---
# Public Fortnite PC client id/secret (used by many open-source locker tools).
EPIC_CLIENT_ID = "ec684b8c687f479fadea3cb2ad83f5c6"
EPIC_CLIENT_SECRET = "e1f31c211f28413186262d37a13fc84d"
EPIC_BASIC = base64.b64encode(f"{EPIC_CLIENT_ID}:{EPIC_CLIENT_SECRET}".encode()).decode()
EPIC_TOKEN_URL = "https://account-public-service-prod.ol.epicgames.com/account/api/oauth/token"
EPIC_ACCOUNT_URL = "https://account-public-service-prod.ol.epicgames.com/account/api/public/account/{account_id}"
FN_PROFILE_URL = (
    "https://fortnite-public-service-prod11.ol.epicgames.com"
    "/fortnite/api/game/v2/profile/{account_id}/client/QueryProfile"
    "?profileId={profile}&rvn=-1"
)
# Open AFTER logging in on epicgames.com -> returns {"authorizationCode": "..."}
AUTHCODE_REDIRECT_URL = (
    "https://www.epicgames.com/id/login"
    "?redirectUrl=https://www.epicgames.com/id/api/redirect"
    f"?clientId={EPIC_CLIENT_ID}"
)

# Rarity sort order (higher = rarer) for locker/showcase sorting.
RARITY_RANK = {
    "mythic": 7, "legendary": 6, "epic": 5, "rare": 4,
    "uncommon": 3, "common": 2, "": 1,
}

# Friendly cosmetic-type filter names -> fortnite-api backend values.
TYPE_FILTERS = {
    "outfit": "outfit", "skin": "outfit",
    "backbling": "backpack", "backpack": "backpack",
    "pickaxe": "pickaxe",
    "glider": "glider",
    "emote": "emote", "dance": "emote",
    "wrap": "wrap",
    "music": "music", "lobby": "music",
    "loading": "loadingscreen", "loadingscreen": "loadingscreen",
    "contrail": "contrail",
    "spray": "spray",
}
