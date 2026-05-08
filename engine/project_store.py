"""
project_store.py
----------------
Persist individual cost plan projects to disk as JSON files.
Each project is saved to:  data/projects/<project_id>.json

Provides: save, load, list, delete.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path

PROJECTS_DIR = Path(__file__).parent.parent / "data" / "projects"


def _ensure_dir():
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)


def save_project(project_data: dict) -> str:
    """
    Save a project dict. If project_data contains a 'project_id', overwrites.
    Returns the project_id.
    """
    _ensure_dir()

    project_id = project_data.get("project_id") or str(uuid.uuid4())[:8].upper()
    project_data["project_id"] = project_id
    project_data["saved_at"] = datetime.now().isoformat(timespec="seconds")

    path = PROJECTS_DIR / f"{project_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(project_data, f, indent=2, ensure_ascii=False)

    return project_id


def load_project(project_id: str) -> dict:
    """Load a project by ID. Raises FileNotFoundError if not found."""
    path = PROJECTS_DIR / f"{project_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Project '{project_id}' not found.")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_projects() -> list[dict]:
    """Return a list of all project summary dicts, sorted newest first."""
    _ensure_dir()
    projects = []
    for path in sorted(PROJECTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            projects.append({
                "project_id":   data.get("project_id", path.stem),
                "project_name": data.get("project_name", "Untitled"),
                "location":     data.get("location", "—"),
                "total_cost":   data.get("total_cost", 0),
                "saved_at":     data.get("saved_at", ""),
                "gia_m2":       data.get("gia_m2", 0),
            })
        except Exception:
            pass  # skip corrupted files
    return projects


def delete_project(project_id: str):
    """Delete a project by ID."""
    path = PROJECTS_DIR / f"{project_id}.json"
    if path.exists():
        path.unlink()