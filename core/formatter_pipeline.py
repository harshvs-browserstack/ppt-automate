"""
Document-to-Deck pipeline.
Refactored from [Script]_Formatter_Release.ipynb — all Colab-specific code removed.
"""
import re
from typing import Any, Dict, List
import pandas as pd


def contains_url(text: str) -> bool:
    """Return True if the string contains an HTTP/HTTPS URL."""
    url_pattern = re.compile(r"https?://(?:www\.)?\S+\.\S+")
    return bool(url_pattern.search(text))


def extract_id_from_url(value: str) -> str:
    """
    Extract a Google resource ID from a URL like .../d/<ID>/...
    Returns the value unchanged if it is not a URL.
    """
    if not contains_url(value):
        return value
    match = re.search(r"/d/([a-zA-Z0-9-_]+)", value)
    return match.group(1) if match else value


def _merge_ai_output_with_template(
    original_df: pd.DataFrame, ai_data_list: List[Dict]
) -> pd.DataFrame:
    """
    Merge AI-generated contentRuns into the original style-map DataFrame.
    Rows are matched on placeholderId. Last occurrence wins on duplicates.
    """
    if not ai_data_list:
        return original_df.copy()
    ai_df = pd.DataFrame(ai_data_list)
    if not {"placeholderId", "contentRuns"}.issubset(ai_df.columns):
        return original_df.copy()
    ai_df_unique = ai_df.drop_duplicates(subset=["placeholderId"], keep="last")
    ai_mapping = ai_df_unique.set_index("placeholderId")["contentRuns"]
    merged = original_df.copy()
    mapped = merged["placeholderId"].map(ai_mapping)
    merged["contentRuns"] = mapped.where(mapped.notna(), merged["contentRuns"])
    return merged
