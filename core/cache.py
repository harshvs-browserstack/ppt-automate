"""
Generation history caching with TTL.
Caches history DataFrame in Streamlit session state for 1 hour.
"""
import streamlit as st
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd


CACHE_KEY = "history_cache_data"
CACHE_TIMESTAMP_KEY = "history_cache_timestamp"
CACHE_TTL_SECONDS = 3600  # 1 hour


def get_history_cache() -> Optional[pd.DataFrame]:
    """
    Retrieve cached history DataFrame if valid (< 1 hour old).

    Returns:
        DataFrame if cache is valid and fresh, None if cache missing or stale.
    """
    if CACHE_KEY not in st.session_state or CACHE_TIMESTAMP_KEY not in st.session_state:
        return None

    cache_timestamp = st.session_state[CACHE_TIMESTAMP_KEY]
    age = (datetime.now() - cache_timestamp).total_seconds()

    if age > CACHE_TTL_SECONDS:
        # Cache is stale, invalidate it
        invalidate_history_cache()
        return None

    return st.session_state[CACHE_KEY]


def set_history_cache(data: pd.DataFrame) -> None:
    """
    Store history DataFrame in cache with current timestamp.

    Args:
        data: DataFrame of history records to cache.
    """
    st.session_state[CACHE_KEY] = data
    st.session_state[CACHE_TIMESTAMP_KEY] = datetime.now()


def invalidate_history_cache() -> None:
    """
    Clear the history cache.
    Called after new generation is logged or when user requests refresh.
    """
    if CACHE_KEY in st.session_state:
        del st.session_state[CACHE_KEY]
    if CACHE_TIMESTAMP_KEY in st.session_state:
        del st.session_state[CACHE_TIMESTAMP_KEY]
