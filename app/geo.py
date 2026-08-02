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
