import os
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

UTM_SOURCE = os.getenv("UTM_SOURCE", "vk")
UTM_MEDIUM = os.getenv("UTM_MEDIUM", "repost")
UTM_CAMPAIGN = os.getenv("UTM_CAMPAIGN", "auction")

def add_utm(url: str | None) -> str | None:
    if not url:
        return None
    try:
        u = urlparse(url)
        q = dict(parse_qsl(u.query))
        q.update({
            "utm_source": UTM_SOURCE,
            "utm_medium": UTM_MEDIUM,
            "utm_campaign": UTM_CAMPAIGN,
        })
        return urlunparse(u._replace(query=urlencode(q)))
    except Exception:
        return url
