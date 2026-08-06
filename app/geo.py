import math

import httpx

from .config import NOMINATIM_URL, NOMINATIM_USER_AGENT


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance between two lat/long points in kilometres."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(a))


def reverse_geocode(lat: float, long: float) -> str:
    """Get a human-readable address from GPS coords via OSM Nominatim (free).
    Returns empty string on failure — never raises."""
    try:
        resp = httpx.get(
            NOMINATIM_URL,
            params={"lat": lat, "lon": long, "format": "json"},
            headers={"User-Agent": NOMINATIM_USER_AGENT},
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json().get("display_name", "")
    except Exception:
        return ""


def forward_geocode(query: str) -> tuple[float, float] | None:
    """Get GPS coords from a typed address or pincode via OSM Nominatim.
    This is the fallback when a phone's GPS won't fix — indoors, a flaky
    lock, or a desktop browser with no location hardware at all. Returns
    None on failure or no match — never raises."""
    query = query.strip()
    if not query:
        return None
    try:
        resp = httpx.get(
            NOMINATIM_URL.replace("/reverse", "/search"),
            # A bare pincode like "110001" matches postal codes worldwide —
            # without this it drifted to China in testing. Every address in
            # this app is somewhere a Hinglish-speaking user is standing.
            params={"q": query, "format": "json", "limit": 1, "countrycodes": "in"},
            headers={"User-Agent": NOMINATIM_USER_AGENT},
            timeout=10.0,
        )
        resp.raise_for_status()
        results = resp.json()
        if not results:
            return None
        return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception:
        return None
