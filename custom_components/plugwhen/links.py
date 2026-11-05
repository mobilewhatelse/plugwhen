"""Finding the entities of another integration by its config entry (pure Python, no Home Assistant imports).

The user chooses *the other integration* (a config entry) in the settings; the entities that matter are found here by their
unique id, so nothing has to be picked entity by entity and a vehicle added later is found at once.
"""

from __future__ import annotations

from collections.abc import Iterable


def pick(entries: Iterable[tuple[str, str, str | None]], domain: str, suffix: str) -> str | None:
    """The entity id of the first entity (sorted by id) in `domain` whose unique id ends with `suffix`.
    `entries` are `(entity_id, domain, unique_id)` of one config entry."""
    found = sorted(eid for eid, dom, uid in entries if dom == domain and str(uid or "").endswith(suffix))
    return found[0] if found else None
