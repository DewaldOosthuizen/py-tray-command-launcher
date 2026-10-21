# SPDX-License-Identifier: GPL-3.0-or-later

"""
CommandSearch — shared fuzzy command-palette search compatibility API.

Uses ``rapidfuzz.fuzz.WRatio`` for scoring.  Falls back to exact
substring search with a log warning when rapidfuzz is unavailable.

The palette owns command filtering, keyboard navigation, and execution. This
module keeps the search-scoring helpers and a legacy route to that palette.
"""

import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

try:
    from rapidfuzz import fuzz as _fuzz

    _FUZZY_AVAILABLE = True
except ImportError:
    _FUZZY_AVAILABLE = False
    logger.warning("rapidfuzz not available; falling back to substring search in CommandSearch")


def _score(query: str, text: str) -> float:
    """Return a match score 0–100 for *query* against *text*."""
    if _FUZZY_AVAILABLE:
        return _fuzz.WRatio(query, text)
    return 100.0 if query.lower() in text.lower() else 0.0


COMMAND_SEARCH_CACHE_SIZE = 128


def _search_positions(query: str, searchable_commands: tuple) -> tuple:
    """Score a searchable command snapshot and return immutable position/score pairs.

    Args:
        query: Normalized query. Whitespace is preserved unless it is all whitespace.
        searchable_commands: Ordered ``(group, label)`` pairs for the current command snapshot.

    Returns:
        An immutable tuple of ``(command_index, score)`` pairs in stable descending score order.
    """
    if not query:
        return tuple((position, 100) for position in range(len(searchable_commands)))

    scored = []
    for position, (group, label) in enumerate(searchable_commands):
        text = f"{group} {label}"
        score = _score(query, text)
        if score > 30 or query.lower() in text.lower():
            scored.append((position, score))
    scored.sort(key=lambda result: result[1], reverse=True)
    return tuple(scored)


@lru_cache(maxsize=COMMAND_SEARCH_CACHE_SIZE)
def _cached_search_positions(query: str, searchable_commands: tuple) -> tuple:
    """Return cached immutable search positions and scores for a query/snapshot pair."""
    return _search_positions(query, searchable_commands)


def _normalized_query(query: str) -> str:
    """Collapse blank queries while preserving raw non-blank search semantics."""
    return query if query.strip() else ""


def _searchable_signature(commands: list) -> tuple:
    """Build the ordered, immutable set of fields that determines matching and ranking."""
    return tuple((str(command["group"]), str(command["label"])) for command in commands)


def _render_results(positions: tuple, commands: list) -> list:
    """Pair cached positions and scores with command objects from the current snapshot."""
    return [(score, commands[position]) for position, score in positions]


def search_commands(query: str, commands: list) -> list:
    """Return matching commands ranked by score, reusing bounded cached scoring.

    The cache stores only immutable result positions and scores. Command payloads are
    resolved from *commands* on every call, so callers never receive stale dictionaries.

    Args:
        query: User-entered search text.
        commands: Ordered command dictionaries containing ``group`` and ``label``.

    Returns:
        A list of ``(score, command)`` pairs. An empty or whitespace-only query returns
        every command in input order with score 100.

    Raises:
        KeyError: If a command is missing its ``group`` or ``label`` searchable field.
        AttributeError: If *query* does not provide the string operations used for normalization.
    """
    signature = _searchable_signature(commands)
    positions = _cached_search_positions(_normalized_query(query), signature)
    return _render_results(positions, commands)


def search_commands_uncached(query: str, commands: list) -> list:
    """Return the same ranked search results without reading or populating the LRU cache.

    This shares the scoring implementation with :func:`search_commands` and is intended
    for benchmarks and parity verification.

    Args:
        query: User-entered search text.
        commands: Ordered command dictionaries containing ``group`` and ``label``.

    Returns:
        A list of ``(score, command)`` pairs with command payloads from *commands*.

    Raises:
        KeyError: If a command is missing its ``group`` or ``label`` searchable field.
        AttributeError: If *query* does not provide the string operations used for normalization.
    """
    signature = _searchable_signature(commands)
    positions = _search_positions(_normalized_query(query), signature)
    return _render_results(positions, commands)


def clear_command_search_cache() -> None:
    """Discard cached positions and reset hit/miss statistics.

    Returns:
        None.
    """
    _cached_search_positions.cache_clear()


def command_search_cache_info():
    """Return standard LRU hit, miss, capacity, and current-size statistics.

    Returns:
        The immutable cache-info tuple provided by :func:`functools.lru_cache`.
    """
    return _cached_search_positions.cache_info()


class CommandSearch:
    """Compatibility facade for the shared command-palette search flow."""

    def __init__(self, services, show_palette=None):
        """Initialize with services and an optional palette-opening callback."""
        self.services = services
        self._show_palette = show_palette

    def show_dialog(self):
        """Open the shared palette for callers of the former search dialog API."""
        callback = self._show_palette or getattr(self.services, "show_command_palette", None)
        if callback is None:
            logger.warning("Command search compatibility route has no palette callback")
            return
        callback()
