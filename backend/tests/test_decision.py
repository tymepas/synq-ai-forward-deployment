from __future__ import annotations

import unittest
from datetime import date

from app.decision import Candidate, select_origin_hub_replacement


class DecisionTests(unittest.TestCase):
    def _context(self, **overrides: object) -> dict[str, object]:
        context: dict[str, object] = {
            "ticket_date": date(2026, 4, 1), "client": "Apex Chemicals", "origin_hub": "Kanpur",
            "route_touches_delhi_ncr": False, "is_hill_route": False, "citations": ("SRC:1",),
        }
        context.update(overrides)
        return context

    def test_selects_deterministic_eligible_candidate(self) -> None:
        candidates = [
            Candidate("B", "Kanpur", "Active", True, False, 2022, "BS6", "Yes", 0,
                      apex_previous_incident=False, permanent_repair_confirmed=True),
            Candidate("A", "Kanpur", "Active", True, False, 2021, "BS6", "Yes", 0,
                      apex_previous_incident=False, permanent_repair_confirmed=True),
        ]
        decision = select_origin_hub_replacement(candidates, **self._context())
        self.assertEqual(decision.status, "REPLACEMENT_SELECTED")
        self.assertEqual(decision.selected_vehicle_reg, "A")

    def test_unknown_live_availability_causes_manual_hold(self) -> None:
        candidate = Candidate("A", "Kanpur", "Active", None, False, 2022, "BS6", "Yes", 0,
                              apex_previous_incident=False, permanent_repair_confirmed=True)
        decision = select_origin_hub_replacement([candidate], **self._context())
        self.assertEqual(decision.status, "MANUAL_HOLD")
        self.assertIn("live_availability_unknown", decision.reason_codes)

    def test_orion_prefers_newest_available_vehicle(self) -> None:
        candidates = [
            Candidate("OLD", "Kanpur", "Active", True, False, 2020, "BS6", "Yes", 0,
                      permanent_repair_confirmed=True, overnight_wait=False),
            Candidate("NEW", "Kanpur", "Active", True, False, 2023, "BS6", "Yes", 0,
                      permanent_repair_confirmed=True, overnight_wait=False),
        ]
        decision = select_origin_hub_replacement(candidates, **self._context(client="Orion Pharma"))
        self.assertEqual(decision.selected_vehicle_reg, "NEW")

