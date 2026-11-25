"""Settings for the Notion mirror.

A class of its own rather than fields on app/config.py, so the mirror can be
added or removed without touching the settings every other module reads. It
reads the same two env files in the same order (repo-root .env, then
backend/.env winning), and follows app.config when the test suite blanks
those files, so pytest never picks up a real NOTION_TOKEN.
"""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_REPO_ROOT = _BACKEND_DIR.parent
ENV_FILES = (_REPO_ROOT / ".env", _BACKEND_DIR / ".env")

# Pinned, never "latest": a Notion-Version is a contract on request and
# response shapes. 2026-03-11 is the newest released version. The code uses
# the data-source model that 2025-09-03 introduced and none of the fields
# 2026-03-11 renamed (archived, after, transcription), so NOTION_VERSION can be
# set back to 2025-09-03 without code changes. 2022-06-28 will NOT work: rows
# are addressed through data sources here, which that version predates.
DEFAULT_NOTION_VERSION = "2026-03-11"

# Database key -> env var holding that database's data source id. The data
# source id, not the database id, because every row-level call (query, create
# page, relation target) takes the data source id since 2025-09-03.
DATA_SOURCE_ENV = {
    "brands": "NOTION_DS_BRANDS",
    "families": "NOTION_DS_FAMILIES",
    "notes": "NOTION_DS_NOTES",
    "playbook": "NOTION_DS_PLAYBOOK",
    "products": "NOTION_DS_PRODUCTS",
    "leads": "NOTION_DS_LEADS",
    "calls": "NOTION_DS_CALLS",
    "objections": "NOTION_DS_OBJECTIONS",
    "meetings": "NOTION_DS_MEETINGS",
}


class NotionSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    notion_token: str = ""
    notion_parent_page_id: str = ""
    notion_start_page_id: str = ""
    notion_version: str = DEFAULT_NOTION_VERSION
    # Notion allows about 3 requests a second per connection, and since June
    # 2026 also 180 a minute per workspace on non-Business plans, shared with
    # every other integration reading it. Graphify syncing the same workspace
    # is one of those, so stay a little under the ceiling.
    notion_max_rps: float = 2.5

    notion_ds_brands: str = ""
    notion_ds_families: str = ""
    notion_ds_notes: str = ""
    notion_ds_playbook: str = ""
    notion_ds_products: str = ""
    notion_ds_leads: str = ""
    notion_ds_calls: str = ""
    notion_ds_objections: str = ""
    notion_ds_meetings: str = ""

    def data_source_ids(self) -> dict[str, str]:
        return {key: getattr(self, env.lower()).strip() for key, env in DATA_SOURCE_ENV.items()}

    def missing(self) -> list[str]:
        """Env var names still blank. Empty means the mirror can run."""
        names = [] if self.notion_token.strip() else ["NOTION_TOKEN"]
        names += [
            DATA_SOURCE_ENV[key] for key, value in self.data_source_ids().items() if not value
        ]
        return names

    @property
    def configured(self) -> bool:
        return not self.missing()


def load_notion_settings(**overrides: object) -> NotionSettings:
    """Build settings from the env files app.config currently points at.

    tests/conftest.py sets Settings.model_config["env_file"] to None so the
    suite never reads a developer's real secrets; reading it here at call
    time means this class is blanked by the same line, with no conftest edit.
    """
    try:
        from app.config import Settings

        env_file = Settings.model_config.get("env_file", ENV_FILES)
    except Exception:
        env_file = ENV_FILES
    return NotionSettings(_env_file=env_file, **overrides)
