import re
import requests
from datetime import datetime, date
from urllib.parse import urlparse


HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CreatorDashboard/1.0)"}


# ── URL / handle extraction ────────────────────────────────────────────────────

def extract_handle_and_subdomain(raw: str):
    """
    Returns (handle, subdomain, base_url) from any Substack URL format.
    Handles:
      https://substack.com/@myaicommunity
      https://myaicommunity.substack.com
      myaicommunity.substack.com
      myaicommunity
    """
    raw = raw.strip().rstrip("/")
    if not raw.startswith("http"):
        raw = "https://" + raw

    parsed = urlparse(raw)
    netloc = parsed.netloc.lower()

    # https://substack.com/@handle  or  https://substack.com/handle
    if netloc in ("substack.com", "www.substack.com"):
        m = re.match(r"/@?([\w-]+)", parsed.path)
        if m:
            handle = m.group(1)
            return handle, handle, f"https://{handle}.substack.com"
        raise ValueError(
            "Enter your newsletter URL, not the main Substack site.\n"
            "Valid formats:\n"
            "  • https://yournewsletter.substack.com\n"
            "  • https://substack.com/@yourhandle"
        )

    # https://subdomain.substack.com
    if netloc.endswith(".substack.com"):
        subdomain = netloc.replace(".substack.com", "")
        return subdomain, subdomain, f"https://{subdomain}.substack.com"

    raise ValueError(f"Unrecognised Substack URL: {raw}")


# ── API calls ──────────────────────────────────────────────────────────────────

def _get(url, **kwargs):
    r = requests.get(url, headers=HEADERS, timeout=20, **kwargs)
    r.raise_for_status()
    return r.json()


def fetch_profile(handle: str, base_url: str) -> dict:
    """
    Fetch publication profile via the user public_profile endpoint on substack.com.
    Falls back to the subdomain profile endpoint.
    """
    try:
        data = _get(f"https://substack.com/api/v1/user/{handle}/public_profile")
        pub_users = data.get("publicationUsers") or []
        pub = pub_users[0].get("publication", {}) if pub_users else {}
        return {
            "name":        pub.get("name") or data.get("name") or handle,
            "description": pub.get("hero_text") or data.get("bio") or "",
            "author":      data.get("name") or "",
            "author_photo": data.get("photo_url") or "",
            "logo":        pub.get("logo_url") or pub.get("logo_url_wide") or "",
            "cover":       pub.get("cover_photo_url") or "",
            "subdomain":   pub.get("subdomain") or handle,
            "url":         base_url,
            "payments":    pub.get("payments_state") == "enabled",
            "subscribers": None,
        }
    except Exception:
        raise ValueError(
            f"Could not fetch profile for '{handle}'. "
            "Check the URL and make sure the newsletter exists."
        )


def fetch_all_posts(subdomain: str, max_posts: int = 300) -> list:
    base = f"https://{subdomain}.substack.com"
    posts, offset, limit = [], 0, 50
    while len(posts) < max_posts:
        batch = _get(f"{base}/api/v1/posts", params={"limit": limit, "offset": offset, "sort": "new"})
        if not batch:
            break
        posts.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return posts[:max_posts]


# ── Post parser ────────────────────────────────────────────────────────────────

def parse_post(p: dict, base_url: str) -> dict:
    reactions = p.get("reactions") or {}
    likes = (
        reactions.get("❤")
        or reactions.get("❤")
        or p.get("reaction_count")
        or 0
    )
    try:
        likes = int(likes)
    except (TypeError, ValueError):
        likes = 0

    comments  = int(p.get("comment_count") or 0)
    restacks  = int(p.get("restacks") or 0)
    wordcount = int(p.get("wordcount") or 0)

    raw_date = p.get("post_date") or p.get("publishedAt") or ""
    try:
        dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
        post_date  = dt.date()
        post_month = dt.strftime("%Y-%m")
    except Exception:
        post_date = post_month = None

    audience  = p.get("audience") or "everyone"
    is_paid   = audience in ("only_paid", "paid")

    canonical = p.get("canonical_url") or ""
    if not canonical and p.get("slug"):
        canonical = f"{base_url}/p/{p['slug']}"

    tags = [t["name"] for t in (p.get("postTags") or []) if t.get("name")]

    bylines = p.get("publishedBylines") or []
    author  = bylines[0].get("name", "") if bylines else ""

    return {
        "id":        p.get("id"),
        "title":     p.get("title") or "Untitled",
        "subtitle":  p.get("subtitle") or "",
        "date":      post_date,
        "month":     post_month,
        "audience":  "Paid" if is_paid else "Free",
        "is_paid":   is_paid,
        "type":      p.get("type") or "newsletter",
        "likes":     likes,
        "comments":  comments,
        "restacks":  restacks,
        "wordcount": wordcount,
        "engagement": likes + comments + restacks,
        "cover":     p.get("cover_image") or "",
        "url":       canonical,
        "tags":      tags[:5],
        "author":    author,
    }


# ── Main entry point ───────────────────────────────────────────────────────────

def fetch_newsletter_data(raw_url: str) -> dict:
    handle, _, base_url = extract_handle_and_subdomain(raw_url)
    profile = fetch_profile(handle, base_url)
    # Use the subdomain from the API response — it may differ from the handle
    actual_subdomain = profile.get("subdomain") or handle
    actual_base_url  = f"https://{actual_subdomain}.substack.com"
    profile["url"]   = actual_base_url
    posts_raw = fetch_all_posts(actual_subdomain)
    posts     = [parse_post(p, actual_base_url) for p in posts_raw]
    posts.sort(key=lambda p: p["date"] or date.min)
    return {"profile": profile, "posts": posts}
