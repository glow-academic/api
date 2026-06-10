"""Page-size cap on the canonical ``POST /attempt/search`` route.

Regression guard for the unbounded-query DoS (box-hang-under-load class):
``SearchAttemptApiRequest.page_size``/``page`` had no ``ge``/``le`` bounds,
so a huge ``page_size`` flowed straight into
``search_attempts(limit=page_size, ...)`` which over-fetches
``LIMIT limit + offset + 1000`` — loading the whole visible result set into
memory. The bounds match the sibling ``page``/``page_size`` convention
(``page: ge=0``, ``page_size: ge=1, le=200`` — see ``test``/``activity``
search request models): an out-of-range value is rejected with 422 by
pydantic validation, before the query ever runs.
"""

from __future__ import annotations

import pytest


@pytest.mark.asyncio
class TestAttemptSearchPageCap:
    async def test_page_size_over_cap_rejected_422(
        self,
        attempt_route_client,
        attempt_route_actor,
    ):
        """``page_size`` above the cap (200) is rejected at validation."""
        attempt_route_client.authenticate(
            profile_id=attempt_route_actor.profile_id,
            session_id=attempt_route_actor.session_id,
        )

        response = await attempt_route_client.client.post(
            "/attempt/search",
            json={"page_size": 100000},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 422, response.text

    async def test_page_size_zero_rejected_422(
        self,
        attempt_route_client,
        attempt_route_actor,
    ):
        """``page_size`` below the floor (ge=1) is rejected at validation."""
        attempt_route_client.authenticate(
            profile_id=attempt_route_actor.profile_id,
            session_id=attempt_route_actor.session_id,
        )

        response = await attempt_route_client.client.post(
            "/attempt/search",
            json={"page_size": 0},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 422, response.text

    async def test_negative_page_rejected_422(
        self,
        attempt_route_client,
        attempt_route_actor,
    ):
        """A negative ``page`` index (ge=0) is rejected at validation."""
        attempt_route_client.authenticate(
            profile_id=attempt_route_actor.profile_id,
            session_id=attempt_route_actor.session_id,
        )

        response = await attempt_route_client.client.post(
            "/attempt/search",
            json={"page": -1},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 422, response.text

    @pytest.mark.parametrize("page_size", [20, 100, 200])
    async def test_valid_page_size_within_cap_ok(
        self,
        attempt_route_client,
        attempt_route_actor,
        page_size,
    ):
        """In-range ``page_size`` values still succeed (behavior unchanged)."""
        attempt_route_client.authenticate(
            profile_id=attempt_route_actor.profile_id,
            session_id=attempt_route_actor.session_id,
        )

        response = await attempt_route_client.client.post(
            "/attempt/search",
            json={"page": 0, "page_size": page_size},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
