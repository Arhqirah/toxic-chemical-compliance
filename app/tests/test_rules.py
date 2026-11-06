"""Unit tests for the storage rules.

No database needed: rules.py only works on plain Python data,
so these run in a fraction of a second.
"""
from decimal import Decimal as D

import rules


def site(**warehouses):
    """Build a site from e.g. w1=("A", 4), w3=("C", 2). Capacities are from the brief."""
    capacities = {1: D(10), 2: D(12), 3: D(5), 4: D(3), 5: D(9)}
    result = {n: {"capacity": cap, "used": D(0), "classes": set()} for n, cap in capacities.items()}
    for key, (chemical_class, used) in warehouses.items():
        n = int(key[1:])
        result[n]["used"] = D(used)
        result[n]["classes"] = {chemical_class}
    return result


# ---------------------------------------------------------------- capacity

def test_delivery_into_empty_warehouse_is_allowed():
    assert rules.check_delivery(site(), 1, "C", D(5)) == []


def test_delivery_filling_warehouse_exactly_is_allowed():
    assert rules.check_delivery(site(w3=("C", 3)), 3, "C", D(2)) == []


def test_delivery_over_capacity_is_blocked():
    errors = rules.check_delivery(site(w4=("C", 2)), 4, "C", D(2))
    assert len(errors) == 1
    assert "only has 1K free" in errors[0]


# ---------------------------------------------------------------- A and B separation

def test_class_a_into_warehouse_with_b_is_blocked():
    errors = rules.check_delivery(site(w2=("B", 1)), 2, "A", D(1))
    assert any("may not be stored together" in e for e in errors)


def test_class_b_into_warehouse_with_a_is_blocked():
    errors = rules.check_delivery(site(w2=("A", 1)), 2, "B", D(1))
    assert any("may not be stored together" in e for e in errors)


def test_class_c_can_go_with_anything():
    assert rules.check_delivery(site(w2=("A", 1)), 2, "C", D(1)) == []
    assert rules.check_delivery(site(w2=("B", 1)), 2, "C", D(1)) == []


def test_class_b_next_to_class_a_is_allowed():
    # The adjacency rule is only for A next to A
    assert rules.check_delivery(site(w1=("A", 1)), 2, "B", D(1)) == []


# ---------------------------------------------------------------- A not in neighbouring warehouses

def test_class_a_next_to_class_a_is_blocked():
    errors = rules.check_delivery(site(w2=("A", 1)), 3, "A", D(1))
    assert any("Neighbouring warehouse 2" in e for e in errors)


def test_class_a_between_two_class_a_reports_both_neighbours():
    errors = rules.check_delivery(site(w1=("A", 1), w3=("A", 1)), 2, "A", D(1))
    assert any("warehouse 1" in e for e in errors)
    assert any("warehouse 3" in e for e in errors)


def test_class_a_two_warehouses_apart_is_allowed():
    assert rules.check_delivery(site(w1=("A", 1)), 3, "A", D(1)) == []


def test_edge_warehouses_only_have_one_neighbour():
    # Warehouse 5 has no warehouse 6, warehouse 1 has no warehouse 0
    assert rules.check_delivery(site(w3=("A", 1)), 5, "A", D(1)) == []
    assert rules.check_delivery(site(w3=("A", 1)), 1, "A", D(1)) == []


def test_several_broken_rules_give_several_errors():
    errors = rules.check_delivery(site(w4=("B", 3), w5=("A", 1)), 4, "A", D(1))
    assert len(errors) == 3  # full, holds B, neighbour has A


# ---------------------------------------------------------------- dispatch

def test_dispatch_within_stock_is_allowed():
    assert rules.check_dispatch(D(5), D(5)) == []


def test_dispatch_more_than_stock_is_blocked():
    errors = rules.check_dispatch(D(2), D(3))
    assert "Only 2K" in errors[0]


# ---------------------------------------------------------------- fire brigade

def test_exactly_15k_class_a_needs_no_alert():
    # The brief says "more than 15K"
    assert rules.fire_brigade_alert(D(15)) is False


def test_over_15k_class_a_needs_alert():
    assert rules.fire_brigade_alert(D("15.01")) is True
