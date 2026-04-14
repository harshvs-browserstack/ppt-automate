"""
Confluence REST API client.
Uses Basic auth (email + API token). Synchronous — research runs before async generation.
"""
import base64
from typing import Any, Dict, List

import httpx
from bs4 import BeautifulSoup


class ConfluenceClient:
    """Thin wrapper around the Confluence Cloud REST API."""

    def __init__(self, base_url: str, email: str, token: str):
        self._base_url = base_url.rstrip("/")
        token_b64 = base64.b64encode(f"{email}:{token}".encode()).decode()
        self._headers = {
            "Authorization": f"Basic {token_b64}",
            "Content-Type": "application/json",
        }
        self._http = httpx.Client(headers=self._headers, timeout=30.0)

    def list_spaces(self) -> List[Dict[str, str]]:
        """Return [{key, name}] for all accessible spaces (up to 250)."""
        url = f"{self._base_url}/wiki/api/v2/spaces"
        response = self._http.get(url, params={"limit": 250})
        response.raise_for_status()
        return [
            {"key": s["key"], "name": s["name"]}
            for s in response.json()["results"]
        ]

    def search(self, cql: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Run a CQL search and return matching pages as dicts.

        Each dict has: id, title, url, space, space_key.
        Uses Confluence REST API v1 (CQL search is not in v2).
        """
        url = f"{self._base_url}/wiki/rest/api/content/search"
        response = self._http.get(url, params={"cql": cql, "limit": limit, "expand": "space"})
        response.raise_for_status()
        results = []
        for item in response.json().get("results", []):
            results.append({
                "id": item["id"],
                "title": item["title"],
                "url": f"{self._base_url}/wiki{item['_links']['webui']}",
                "space": item["space"]["name"],
                "space_key": item["space"]["key"],
            })
        return results

    def get_page_content(self, page_id: str) -> Dict[str, Any]:
        """
        Fetch a page's body and metadata.

        Returns: title, url, last_updated, author, content (plain text).
        Uses v1 API to get body, version, and links in one call.
        """
        url = f"{self._base_url}/wiki/rest/api/content/{page_id}"
        response = self._http.get(
            url,
            params={"expand": "body.storage,version", "status": "current"},
        )
        response.raise_for_status()
        data = response.json()
        storage_xml = data.get("body", {}).get("storage", {}).get("value", "")
        version = data.get("version", {})
        return {
            "title": data["title"],
            "url": f"{self._base_url}/wiki{data['_links']['webui']}",
            "last_updated": version.get("when", ""),
            "author": version.get("by", {}).get("displayName", ""),
            "content": _extract_text(storage_xml),
        }

    def close(self):
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def _extract_text(storage_xml: str) -> str:
    """
    Convert Confluence storage format (XHTML) to plain text.
    Strips all Confluence macro/structured elements (namespaced tags like ac:*, ri:*).
    """
    soup = BeautifulSoup(storage_xml, "html.parser")
    for tag in soup.find_all(True):
        if tag.name and ":" in tag.name:
            tag.decompose()
    return soup.get_text(separator="\n", strip=True)
