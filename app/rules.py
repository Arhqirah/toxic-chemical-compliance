"""The storage rules from the brief, as plain Python functions.

They don't touch the database, so they are easy to unit test (phase 4).
The routes in app.py load the site's current state from the database,
call these functions, and only save the job if no errors come back.
"""
from decimal import Decimal

# Legal limit: above this much class A on one site, the fire brigade must be told
FIRE_BRIGADE_LIMIT_K = Decimal("15")


def check_delivery(warehouses, number, chemical_class, units):
    """Can `units` K of `chemical_class` go into warehouse `number`?

    `warehouses` describes one site:
        {1: {"capacity": Decimal("10"), "used": Decimal("4"), "classes": {"A"}},
         2: {...}, ...}
    "used" and "classes" must include open (not yet confirmed) deliveries,
    so two lorries can't both be given the last free space.

    Returns a list of error messages. An empty list means it's allowed.
    """
    errors = []
    w = warehouses[number]

    if w["used"] + units > w["capacity"]:
        free = w["capacity"] - w["used"]
        errors.append(f"Warehouse {number} only has {free}K free, the delivery is {units}K.")

    if chemical_class == "A" and "B" in w["classes"]:
        errors.append(f"Warehouse {number} holds class B. Class A and B may not be stored together.")
    if chemical_class == "B" and "A" in w["classes"]:
        errors.append(f"Warehouse {number} holds class A. Class A and B may not be stored together.")

    if chemical_class == "A":
        # Warehouses are assumed to stand in a row: 1-2-3-4-5
        for neighbour in (number - 1, number + 1):
            if neighbour in warehouses and "A" in warehouses[neighbour]["classes"]:
                errors.append(
                    f"Neighbouring warehouse {neighbour} holds class A. "
                    "Class A may not be stored in adjacent warehouses."
                )

    return errors


def check_dispatch(available, units):
    """Is there enough stock for a dispatch?

    `available` = units of that class in that warehouse, minus open dispatches.
    """
    if units > available:
        return [f"Only {available}K of that class is available in this warehouse, the order is {units}K."]
    return []


def fire_brigade_alert(class_a_total):
    """True if the site holds more class A than the legal limit."""
    return class_a_total > FIRE_BRIGADE_LIMIT_K
