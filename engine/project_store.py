"""
project_store.py
----------------
Persist individual cost plan projects to Supabase (table: saved_projects).
Replaces the previous local-disk JSON storage so projects survive on
Streamlit Cloud, where local files are wiped on every restart.

Provides: save, load, list, delete — same interface as before.
"""

import os
import uuid
from datetime import datetime, timezone

import httpx
import streamlit as st

TABLE = "saved_projects"


# ── Credentials & request helpers ─────────────────────────────────────────────

def _get_credentials() -> tuple[str, str]:
    url = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY", "")
    if not url or not key:
        raise EnvironmentError(
            "SUPABASE_URL and SUPABASE_KEY must be set in .env or "
            ".streamlit/secrets.toml"
        )
    return url, key


def _headers(key: str, extra: dict | None = None) -> dict:
    h = {
        "apikey":        key,
        "Authorization": f"Bearer {key}",
        "Content-Type":  "application/json",
    }
    if extra:
        h.update(extra)
    return h


# ── Public API (same interface as the old disk version) ──────────────────────

def save_project(project_data: dict) -> str:
    """
    Save a project dict to Supabase. If project_data contains a 'project_id',
    the existing row is overwritten (upsert). Returns the project_id.
    """
    url, key = _get_credentials()

    project_id = project_data.get("project_id") or str(uuid.uuid4())[:8].upper()

    row = {
        "project_id":       project_id,
        "project_name":     project_data.get("project_name", "Untitled"),
        "postcode":         project_data.get("postcode", ""),
        "location":         project_data.get("location", ""),
        "quartile":         project_data.get("quartile", "Standard"),
        "gia_m2":           project_data.get("gia_m2", 0) or 0,
        "nia_m2":           project_data.get("nia_m2", 0) or 0,
        "element_areas_m2": project_data.get("element_areas_m2", {}) or {},
        "total_cost":       project_data.get("total_cost", 0) or 0,
        "owner_email":      st.session_state.get("current_user_email", "") or None,
        "saved_at":         datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    # on_conflict + merge-duplicates = "update the row if this ID already exists"
    response = httpx.post(
        f"{url}/rest/v1/{TABLE}?on_conflict=project_id",
        headers=_headers(key, {"Prefer": "resolution=merge-duplicates"}),
        json=row,
        timeout=15,
    )
    if response.status_code not in (200, 201, 204):
        raise RuntimeError(
            f"Failed to save project [{response.status_code}]: {response.text}"
        )

    return project_id


def load_project(project_id: str) -> dict:
    """Load a project by ID. Raises FileNotFoundError if not found."""
    url, key = _get_credentials()

    response = httpx.get(
        f"{url}/rest/v1/{TABLE}?project_id=eq.{project_id}&select=*",
        headers=_headers(key),
        timeout=15,
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"Failed to load project [{response.status_code}]: {response.text}"
        )

    rows = response.json()
    if not rows:
        # Dashboard catches FileNotFoundError, so keep raising the same type
        raise FileNotFoundError(f"Project '{project_id}' not found.")

    return rows[0]


def list_projects() -> list[dict]:
    """Return a list of all project summary dicts, sorted newest first."""
    url, key = _get_credentials()

    response = httpx.get(
        f"{url}/rest/v1/{TABLE}"
        "?select=project_id,project_name,location,total_cost,saved_at,gia_m2"
        "&order=saved_at.desc",
        headers=_headers(key),
        timeout=15,
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"Failed to list projects [{response.status_code}]: {response.text}"
        )

    projects = []
    for row in response.json():
        saved_at = (row.get("saved_at") or "")[:19]  # trim to YYYY-MM-DDTHH:MM:SS
        projects.append({
            "project_id":   row.get("project_id", ""),
            "project_name": row.get("project_name", "Untitled"),
            "location":     row.get("location", "—"),
            "total_cost":   row.get("total_cost", 0) or 0,
            "saved_at":     saved_at,
            "gia_m2":       row.get("gia_m2", 0) or 0,
        })
    return projects


def delete_project(project_id: str):
    """Delete a project by ID."""
    url, key = _get_credentials()

    response = httpx.delete(
        f"{url}/rest/v1/{TABLE}?project_id=eq.{project_id}",
        headers=_headers(key),
        timeout=15,
    )
    if response.status_code not in (200, 204):
        raise RuntimeError(
            f"Failed to delete project [{response.status_code}]: {response.text}"
        )