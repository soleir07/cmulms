# utils.py
import re
import requests

def extract_video_id(url: str):
    # robust-ish extractor for common YouTube URL formats
    m = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", url)
    if m:
        return m.group(1)
    m = re.search(r"youtu\.be\/([0-9A-Za-z_-]{11})", url)
    if m:
        return m.group(1)
    return None

def fetch_youtube_metadata(url: str, timeout=5):
    """
    Returns dict like {title, author_name, thumbnail_url, html} or None
    """
    try:
        resp = requests.get("https://www.youtube.com/oembed", params={"url": url, "format": "json"}, timeout=timeout)
        if resp.ok:
            return resp.json()
    except Exception:
        return None

from allauth.socialaccount.models import SocialToken
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

def create_drive_folder(user, class_name, section=None):
    token = SocialToken.objects.get(account__user=user, account__provider='google')
    creds = Credentials(token.token)
    service = build('drive', 'v3', credentials=creds)

    # Check if "CMU LMS" main folder exists
    query = "name='CMU LMS' and mimeType='application/vnd.google-apps.folder'"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    items = results.get('files', [])

    if items:
        parent_id = items[0]['id']
    else:
        parent_metadata = {
            'name': 'CMU LMS',
            'mimeType': 'application/vnd.google-apps.folder'
        }
        parent_folder = service.files().create(body=parent_metadata, fields='id').execute()
        parent_id = parent_folder['id']

    # Create class folder inside "CMU LMS"
    teacher_name = user.get_full_name() or user.username
    folder_name = f"{class_name} - Section {section or 'N/A'} (Teacher: {teacher_name})"
    file_metadata = {
        'name': folder_name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_id]
    }
    folder = service.files().create(body=file_metadata, fields='id, webViewLink').execute()

    # Make folder link shareable
    permission = {'type': 'anyone', 'role': 'reader'}
    service.permissions().create(fileId=folder['id'], body=permission).execute()

    return folder['webViewLink']
