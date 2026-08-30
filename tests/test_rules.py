from __future__ import annotations

import unittest
from datetime import date

from app.rules import (
    RuleStatus,
    apex_rotation_rule,
    delhi_ncr_rule,
    driver_night_rule,
    hill_route_rule,
    jugaad_rule,
    maintenance_overdue_rule,
    monsoon_eta_rule,
    orion_age_rule,
    replacement_source_rule,
    shakti_sla_rule,
    vertex_cutoff_rule,
)


class RulesTests(unittest.TestCase):
    citation = "SRC-rules:record:1"

    def test_delhi_bs4_is_rejected_in_winter(self) -> None:
        result = delhi_ncr_rule(date(2026, 1, 1), "BS4", True, self.citation)
        self.assertEqual(result.status, RuleStatus.FAIL)
        self.assertEqual(result.rule_id, "DELHI_NCR_WINTER_BS6_V1")

    def test_hill_rules_require_heater_and_no_recent_brake_work(self) -> None:
        heater = hill_route_rule(date(2026, 12, 1), True, "No", [], self.citation)
        brakes = hill_route_rule(date(2026, 12, 1), True, "Yes", [date(2026, 11, 20)], self.citation)
        self.assertEqual(heater.status, RuleStatus.FAIL)
        self.assertEqual(brakes.status, RuleStatus.FAIL)

    def test_shakti_and_vertex_rules_are_operational_not_contractual(self) -> None:
        shakti = shakti_sla_rule("Shakti Cement", [self.citation])
        vertex = vertex_cutoff_rule("Vertex Retail", "Ludhiana", 18, [self.citation])
        self.assertEqual(shakti.details["sla_hours"], 36)
        self.assertEqual(vertex.details["delivery_status"], "SCHEDULED_MORNING")

    def test_apex_and_orion_client_rules(self) -> None:
        self.assertEqual(apex_rotation_rule("Apex Chemicals", True, [self.citation]).status, RuleStatus.FAIL)
        self.assertEqual(orion_age_rule("Orion Pharma", 2019, [self.citation]).status, RuleStatus.FAIL)
        self.assertEqual(orion_age_rule("Orion Pharma", 2020, [self.citation]).status, RuleStatus.PASS)

    def test_monsoon_and_replacement_source_rules(self) -> None:
        monsoon = monsoon_eta_rule(date(2026, 7, 1), True, [self.citation])
        origin = replacement_source_rule(50, False, [self.citation])
        unknown = replacement_source_rule(51, False, [self.citation])
        self.assertEqual(monsoon.details["eta_multiplier"], 1.2)
        self.assertEqual(origin.details["source_strategy"], "ORIGIN_HUB")
        self.assertEqual(unknown.status, RuleStatus.INSUFFICIENT_DATA)

    def test_maintenance_and_jugaad_rules(self) -> None:
        overdue = maintenance_overdue_rule(31, [self.citation])
        jugaad = jugaad_rule(date(2026, 8, 10), date(2026, 8, 1), False, True, [self.citation])
        self.assertEqual(overdue.status, RuleStatus.FAIL)
        self.assertEqual(jugaad.status, RuleStatus.FAIL)

    def test_driver_night_rule_and_unknowns_are_fail_safe(self) -> None:
        new_driver = driver_night_rule(date(2026, 8, 1), True, True, date(2026, 9, 1), [self.citation])
        unknown_route = delhi_ncr_rule(date(2026, 1, 1), "BS6", None, self.citation)
        self.assertEqual(new_driver.status, RuleStatus.FAIL)
        self.assertEqual(unknown_route.status, RuleStatus.INSUFFICIENT_DATA)

