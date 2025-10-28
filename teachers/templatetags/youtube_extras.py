# templatetags/youtube_extras.py
from django import template
import urllib.parse

register = template.Library()

@register.filter
def youtube_id(url):
    parsed_url = urllib.parse.urlparse(url)
    if parsed_url.hostname == "youtu.be":
        return parsed_url.path.lstrip("/")
    if parsed_url.hostname in ["www.youtube.com", "youtube.com"]:
        query = urllib.parse.parse_qs(parsed_url.query)
        return query.get("v", [None])[0]
    return url
