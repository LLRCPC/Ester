"""
data_loader.py
--------------
Loads cost database from Supabase via direct HTTP.
No supabase SDK required — uses httpx only.
Returns same dict shape as the original JSON loader.
"""

import os
import httpx
import streamlit as st


def _get_credentials() -> tuple[str, str]:
    url = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY", "")
    if not url or not key:
        raise EnvironmentError(
            "SUPABASE_URL and SUPABASE_KEY must be set in .env or "
            ".streamlit/secrets.toml"
        )
    return url, key


def _headers(key: str) -> dict:
    return {
        "apikey":        key,
        "Authorization": f"Bearer {key}",
        "Content-Type":  "application/json",
    }


def _get(url: str, key: str, table: str, params: str = "") -> list:
    response = httpx.get(
        f"{url}/rest/v1/{table}?{params}",
        headers=_headers(key),
        timeout=15,
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"Failed to fetch '{table}' [{response.status_code}]: {response.text}"
        )
    return response.json()


@st.cache_data(ttl=300)
def load_cost_database() -> dict:
    """
    Load elements, quantity rules, and current rates from Supabase.
    Returns the same shape as the original JSON loader.
    """
    url, key = _get_credentials()

    # Active elements in display order
    elements = _get(url, key, "elements",
                    "is_active=eq.true&order=sort_order.asc&select=*")

    # Quantity rules
    quantity_rules = _get(url, key, "quantity_rules", "select=*")

    # Get current published rate set ID
    rate_sets = _get(url, key, "rate_sets",
                     "is_draft=eq.false&superseded_at=is.null"
                     "&order=published_at.desc&limit=1&select=rate_set_id")

    if not rate_sets:
        raise ValueError(
            "No published rate set found in Supabase. "
            "Check rate_sets table — is_draft must be false."
        )

    rate_set_id = rate_sets[0]["rate_set_id"]

    # Rates from current rate set only
    rates = _get(url, key, "rates",
                 f"rate_set_id=eq.{rate_set_id}&select=*")

    return {
        "elements":       elements,
        "quantity_rules": quantity_rules,
        "rates":          rates,
        "_rate_set_id":   rate_set_id,
    }


def get_json_mtime() -> float:
    """Legacy shim — app.py calls this. Return 0 now we use Supabase."""
    return 0.0