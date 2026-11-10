"""Part specification: the JSON format that describes a part (Step 13).

The AI writes JSON like the examples below. This file checks it BEFORE anything
is sent to SolidWorks. All sizes are in millimetres.
Run this file directly to see the self-test:  python part_spec.py
"""

import json
import math

PART_TYPES = ("plate", "cylinder")
MAX_SIZE_MM = 2000.0
MAX_HOLES = 50
MIN_WALL_MM = 1.0  # least material allowed between a hole and an edge or another hole


def extract_json(text: str) -> dict:
    """Pull the JSON object out of a text (models often add words or ``` fences)."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("No JSON object found in the text.")
    return json.loads(text[start : end + 1])


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _size(data: dict, key: str, errors: list, prefix: str = ""):
    """Read a size that must be > 0 and <= MAX_SIZE_MM. Record an error if it is not."""
    value = data.get(key)
    if not _is_number(value):
        errors.append(f"{prefix}'{key}' must be a number in mm.")
        return None
    if not (0 < value <= MAX_SIZE_MM):
        errors.append(
            f"{prefix}'{key}' must be greater than 0 and at most {MAX_SIZE_MM:g} mm (got {value})."
        )
        return None
    return float(value)


def _coordinate(data: dict, key: str, errors: list, prefix: str = ""):
    """Read a position from the centre. It may be negative, zero or positive."""
    value = data.get(key)
    if not _is_number(value) or abs(value) > MAX_SIZE_MM:
        errors.append(f"{prefix}'{key}' must be a number in mm (between -{MAX_SIZE_MM:g} and {MAX_SIZE_MM:g}).")
        return None
    return float(value)


def _check_plate(spec: dict, errors: list) -> None:
    length = _size(spec, "length", errors)
    width = _size(spec, "width", errors)
    _size(spec, "thickness", errors)

    holes = spec.get("holes", [])
    if not isinstance(holes, list):
        errors.append("'holes' must be a list.")
        return
    if len(holes) > MAX_HOLES:
        errors.append(f"At most {MAX_HOLES} holes are allowed (got {len(holes)}).")
        return

    placed = []  # (x, y, radius) of the holes that are valid so far
    for number, hole in enumerate(holes, start=1):
        label = f"Hole {number}: "
        if not isinstance(hole, dict):
            errors.append(f"{label}must be an object with diameter, x and y.")
            continue
        diameter = _size(hole, "diameter", errors, label)
        x = _coordinate(hole, "x", errors, label)
        y = _coordinate(hole, "y", errors, label)
        if diameter is None or x is None or y is None:
            continue

        radius = diameter / 2
        if length is not None and width is not None:
            fits_x = abs(x) + radius + MIN_WALL_MM <= length / 2
            fits_y = abs(y) + radius + MIN_WALL_MM <= width / 2
            if not (fits_x and fits_y):
                errors.append(
                    f"{label}diameter {diameter:g} at x={x:g}, y={y:g} does not fit inside the "
                    f"{length:g} x {width:g} mm plate with {MIN_WALL_MM:g} mm of material around it."
                )
                continue

        for other_number, (ox, oy, other_radius) in enumerate(placed, start=1):
            gap = math.hypot(x - ox, y - oy) - radius - other_radius
            if gap < MIN_WALL_MM:
                errors.append(f"{label}is too close to or overlaps another hole (gap {gap:.2f} mm, need {MIN_WALL_MM:g} mm).")
                break
        placed.append((x, y, radius))


def _check_cylinder(spec: dict, errors: list) -> None:
    diameter = _size(spec, "diameter", errors)
    _size(spec, "length", errors)
    if "bore_diameter" in spec:
        bore = _size(spec, "bore_diameter", errors)
        if bore is not None and diameter is not None and bore > diameter - 2 * MIN_WALL_MM:
            errors.append(
                f"'bore_diameter' ({bore:g}) must be at most {diameter - 2 * MIN_WALL_MM:g} mm "
                f"to leave {MIN_WALL_MM:g} mm of wall."
            )


def validate_spec(spec) -> list:
    """Return a list of problems in plain sentences. An empty list means the spec is valid."""
    if not isinstance(spec, dict):
        return ["The spec must be a JSON object."]

    part_type = spec.get("part_type")
    if part_type not in PART_TYPES:
        return [f"'part_type' must be one of {list(PART_TYPES)} (got {part_type!r})."]

    errors = []
    if spec.get("units") != "mm":
        errors.append("'units' must be \"mm\" (only millimetres are supported).")

    if part_type == "plate":
        _check_plate(spec, errors)
    else:
        _check_cylinder(spec, errors)
    return errors


# ----- Self-test: (label, spec, should it be valid?) -----
TESTS = [
    ("plate_basic", {"part_type": "plate", "units": "mm", "length": 100, "width": 60, "thickness": 8}, True),
    (
        "plate_two_holes",
        {
            "part_type": "plate", "name": "MountingPlate", "units": "mm",
            "length": 100, "width": 60, "thickness": 8,
            "holes": [{"diameter": 8.5, "x": -30, "y": 0}, {"diameter": 8.5, "x": 30, "y": 0}],
        },
        True,
    ),
    (
        "cylinder_with_bore",
        {"part_type": "cylinder", "units": "mm", "diameter": 30, "length": 80, "bore_diameter": 10},
        True,
    ),
    ("bad_units", {"part_type": "plate", "units": "inch", "length": 4, "width": 2, "thickness": 0.3}, False),
    (
        "bad_hole_outside",
        {
            "part_type": "plate", "units": "mm", "length": 100, "width": 60, "thickness": 8,
            "holes": [{"diameter": 10, "x": 48, "y": 0}],
        },
        False,
    ),
    (
        "bad_holes_overlap",
        {
            "part_type": "plate", "units": "mm", "length": 100, "width": 60, "thickness": 8,
            "holes": [{"diameter": 8, "x": -2, "y": 0}, {"diameter": 8, "x": 2, "y": 0}],
        },
        False,
    ),
    ("bad_negative_thickness", {"part_type": "plate", "units": "mm", "length": 100, "width": 60, "thickness": -5}, False),
    ("bad_part_type", {"part_type": "gear", "units": "mm"}, False),
]

MESSY_TEXT = """Sure! Here is the part you asked for:
```json
{"part_type": "cylinder", "units": "mm", "diameter": 20, "length": 50}
```
Let me know if you want changes."""


def main() -> None:
    mismatches = 0
    for label, spec, should_be_valid in TESTS:
        errors = validate_spec(spec)
        is_valid = not errors
        status = "OK       " if is_valid else "REJECTED "
        print(f"{status}{label}")
        for error in errors:
            print(f"            - {error}")
        if is_valid != should_be_valid:
            mismatches += 1
            print("            !! this was NOT the expected result")

    print("\nExtracting JSON from a messy AI-style reply:")
    parsed = extract_json(MESSY_TEXT)
    print("  parsed ->", parsed)
    print("  problems ->", validate_spec(parsed) or "none")

    if mismatches == 0:
        print(f"\nAll {len(TESTS)} tests behaved as expected.")
    else:
        print(f"\n{mismatches} test(s) did not behave as expected.")


if __name__ == "__main__":
    main()