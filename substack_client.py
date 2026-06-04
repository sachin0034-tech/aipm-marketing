from apify_client import ApifyClient

# All 31 Substack leaderboard category slugs
CATEGORIES = {
    "Bestseller":        "bestseller",
    "Technology":        "technology",
    "Business":          "business",
    "Finance":           "finance",
    "Politics":          "politics",
    "Culture":           "culture",
    "Health":            "health",
    "Science":           "science",
    "Food":              "food",
    "Sports":            "sports",
    "Arts":              "arts",
    "Music":             "music",
    "Fiction":           "fiction",
    "History":           "history",
    "International":     "international",
    "Environment":       "environment",
    "Education":         "education",
    "Crypto":            "crypto",
    "Philosophy":        "philosophy",
    "Humor":             "humor",
    "Religion":          "religion",
    "Self-Improvement":  "self-improvement",
    "Parenting":         "parenting",
    "Travel":            "travel",
    "Fashion":           "fashion",
    "Gaming":            "gaming",
    "Architecture":      "architecture",
    "Local News":        "local-news",
    "Productivity":      "productivity",
    "Law":               "law",
    "Writing":           "writing",
}

BOARD_TYPES = ["paid", "rising"]


def fetch_leaderboard(token: str, categories: list, board_types: list, max_results: int) -> list:
    client = ApifyClient(token)
    run = client.actor("parsebird/substack-leaderboard-scraper").call(
        run_input={
            "categories": categories,
            "boardTypes": board_types,
            "maxResults": max_results,
        }
    )
    raw = client.dataset(run["defaultDatasetId"]).list_items().items
    return [_parse(item) for item in raw]


def _get(item: dict, *keys, default=""):
    """Try multiple possible field names, return first match."""
    for k in keys:
        if item.get(k) not in (None, "", 0):
            return item[k]
    return default


def _parse(item: dict) -> dict:
    name = _get(item, "title", "name", "newsletterName")
    author = _get(item, "authorName", "author", "ownerName")
    description = _get(item, "description", "tagline", "about")
    logo = _get(item, "logoUrl", "logo", "imageUrl", "image", "avatarUrl")
    url = _get(item, "url", "link", "substackUrl", "newsletterUrl")
    category = _get(item, "category", "categoryName", "categorySlug")
    board_type = _get(item, "type", "boardType", "listType")
    rank = item.get("rank") or item.get("position") or item.get("rankInCategory") or 0

    # subscriber count — try many possible field names
    subs = (
        item.get("subscribersCount")
        or item.get("totalSubscribers")
        or item.get("subscribers")
        or item.get("freeSubscribers")
        or item.get("subscriberCount")
        or 0
    )

    if not url and item.get("subdomain"):
        url = f"https://{item['subdomain']}.substack.com"

    return {
        "rank": int(rank) if str(rank).isdigit() else 0,
        "name": str(name) if name else "Unknown",
        "author": str(author) if author else "",
        "description": str(description) if description else "",
        "logo": str(logo) if logo else "",
        "url": str(url) if url else "#",
        "category": str(category) if category else "",
        "board_type": str(board_type) if board_type else "",
        "subscribers": int(subs) if str(subs).isdigit() else 0,
        "_raw": item,
    }
