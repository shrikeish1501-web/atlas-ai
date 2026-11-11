"""Step 14: build a part in SolidWorks from a JSON spec.

Usage (SolidWorks must be open):
    python sw_builder.py                    builds the plate_two_holes example
    python sw_builder.py plate_asymmetric   builds one named example
    python sw_builder.py all                builds every example
    python sw_builder.py my_part.json       builds the spec stored in a JSON file
"""

import json
import math
import sys
import traceback

from part_spec import TESTS, validate_spec
from sw_connect import connect, version_info
from sw_plate import mm, new_part, part_size_mm, select_plane

# The valid specs from the part_spec self-test, plus one asymmetric plate that
# lets us check which way x and y point in SolidWorks.
EXAMPLES = {label: spec for label, spec, is_valid in TESTS if is_valid}
EXAMPLES["plate_asymmetric"] = {
    "part_type": "plate", "name": "AsymmetricPlate", "units": "mm",
    "length": 100, "width": 60, "thickness": 8,
    "holes": [{"diameter": 10, "x": 30, "y": 10}],
}


def start_sketch_on_top_plane(doc):
    """Select the Top Plane and open a new sketch on it."""
    if not select_plane(doc, "Top Plane"):
        raise RuntimeError("Could not select the Top Plane.")
    sketch = doc.SketchManager
    sketch.InsertSketch(True)
    return sketch


def extrude_sketch(doc, depth_mm: float):
    """Extrude the open sketch by depth_mm (single direction, blind)."""
    depth = mm(depth_mm)
    feature = doc.FeatureManager.FeatureExtrusion2(
        True, False, False,          # single direction, no flip
        0, 0,                        # end condition = blind
        depth, depth,                # depth for direction 1 and 2
        False, False, False, False,  # no draft
        0.0, 0.0,
        False, False, False, False,
        True, True, True,            # merge result, feature scope, auto-select
        0, 0.0, False,
    )
    if feature is None:
        raise RuntimeError("The extrude failed (SolidWorks returned nothing).")
    return feature


def make_plate(doc, spec: dict):
    """Rectangle centred on the origin, plus one circle per hole, then extrude."""
    sketch = start_sketch_on_top_plane(doc)
    sketch.CreateCenterRectangle(0, 0, 0, mm(spec["length"]) / 2, mm(spec["width"]) / 2, 0)
    for hole in spec.get("holes", []):
        # A circle inside the outline becomes a hole when the sketch is extruded.
        sketch.CreateCircleByRadius(mm(hole["x"]), mm(hole["y"]), 0, mm(hole["diameter"]) / 2)
    return extrude_sketch(doc, spec["thickness"]), "BasePlate"


def make_cylinder(doc, spec: dict):
    """Circle (plus a smaller circle for a bore) extruded along the vertical axis."""
    sketch = start_sketch_on_top_plane(doc)
    sketch.CreateCircleByRadius(0, 0, 0, mm(spec["diameter"]) / 2)
    if "bore_diameter" in spec:
        sketch.CreateCircleByRadius(0, 0, 0, mm(spec["bore_diameter"]) / 2)
    return extrude_sketch(doc, spec["length"]), "BaseCylinder"


def build_part(app, spec: dict):
    """Validate the spec, then build it. Returns (document, first feature)."""
    errors = validate_spec(spec)
    if errors:
        raise ValueError("Invalid part spec:\n- " + "\n- ".join(errors))

    doc = new_part(app)
    if doc is None:
        raise RuntimeError("SolidWorks did not create a new part.")

    if spec["part_type"] == "plate":
        feature, feature_name = make_plate(doc, spec)
    else:
        feature, feature_name = make_cylinder(doc, spec)

    try:  # give the feature a meaningful name
        feature.Name = feature_name
    except Exception:
        pass
    try:  # cosmetic only
        doc.ShowNamedView2("*Isometric", 7)
        doc.ViewZoomtofit2()
    except Exception:
        pass
    return doc, feature


# ----- Checking the result against what the spec predicts -----

def expected_size_mm(spec: dict) -> list:
    """Predicted bounding box [X, Y, Z]. Parts lie on / stand up from the Top Plane."""
    if spec["part_type"] == "plate":
        return [float(spec["length"]), float(spec["thickness"]), float(spec["width"])]
    return [float(spec["diameter"]), float(spec["length"]), float(spec["diameter"])]


def expected_volume_mm3(spec: dict) -> float:
    """Predicted volume from simple geometry."""
    if spec["part_type"] == "plate":
        area = spec["length"] * spec["width"]
        area -= sum(math.pi * (hole["diameter"] / 2) ** 2 for hole in spec.get("holes", []))
        return area * spec["thickness"]
    area = math.pi * (spec["diameter"] / 2) ** 2
    if "bore_diameter" in spec:
        area -= math.pi * (spec["bore_diameter"] / 2) ** 2
    return area * spec["length"]


def expected_faces(spec: dict) -> int:
    """Predicted face count: plate = 6 + one per hole; cylinder = 3 (+1 for a bore)."""
    if spec["part_type"] == "plate":
        return 6 + len(spec.get("holes", []))
    return 3 + (1 if "bore_diameter" in spec else 0)


def volume_via_mass_property(doc) -> float:
    """Route A: the MassProperty object (metres / kilograms)."""
    properties = doc.Extension.CreateMassProperty()
    properties.UseSystemUnits = True
    return properties.Volume


def volume_via_body(body) -> float:
    """Route B: the body's own mass properties. With density 1.0 the volume is in m3."""
    values = body.GetMassProperties(1.0)  # [com x, y, z, volume, area, mass, moments...]
    return values[3]


def first_solid_body(doc):
    """Return the first solid body of the part."""
    bodies = doc.GetBodies2(0, True)  # 0 = solid bodies, visible only
    if not bodies:
        raise RuntimeError("no solid body found")
    return bodies[0]


def read_volume_mm3(doc, body):
    """Try two routes. Returns (volume in mm3 or None, route used, list of problems)."""
    problems = []
    routes = (
        ("body mass properties", lambda: volume_via_body(body)),
        ("mass property object", lambda: volume_via_mass_property(doc)),
    )
    for name, read in routes:
        try:
            return read() * 1e9, name, problems  # cubic metres -> cubic millimetres
        except Exception as error:
            problems.append(f"{name}: {error}")
    return None, "", problems


def check_part(doc, spec: dict) -> bool:
    """Print SolidWorks' own measurements next to the predicted ones.

    Returns True only if the size, the volume and the face count all match.
    """
    results = []

    try:
        measured = part_size_mm(doc)
        expected = expected_size_mm(spec)
        ok = all(abs(m - e) <= 0.01 for m, e in zip(measured, expected))
        results.append(ok)
        print(f"Size X, Y, Z (mm): measured {measured} | expected {expected} | {'PASS' if ok else 'CHECK'}")
    except Exception as error:
        results.append(False)
        print(f"(could not read the size: {error})")

    try:
        body = first_solid_body(doc)
    except Exception as error:
        body = None
        print(f"(could not get the solid body: {error})")

    volume, route, problems = read_volume_mm3(doc, body)
    if volume is None:
        results.append(False)
        print("(could not read the volume)")
    else:
        expected_volume = expected_volume_mm3(spec)
        ok = abs(volume - expected_volume) <= 0.001 * expected_volume
        results.append(ok)
        print(
            f"Volume (mm3): measured {volume:.2f} | expected {expected_volume:.2f} | "
            f"{'PASS' if ok else 'CHECK'}  [via {route}]"
        )
    for problem in problems:
        print(f"   note - failed method: {problem}")

    if body is None:
        results.append(False)
    else:
        try:
            faces = body.GetFaceCount()
            expected_count = expected_faces(spec)
            ok = faces == expected_count
            results.append(ok)
            print(f"Faces: measured {faces} | expected {expected_count} | {'PASS' if ok else 'CHECK'}")
        except Exception as error:
            results.append(False)
            print(f"(could not count the faces: {error})")

    return all(results)
#------------Command Line--------------------

def load_specs(args: list) -> dict:
    if not args:
        return {"plate_two_holes": EXAMPLES["plate_two_holes"]}
    if args[0] == "all":
        return EXAMPLES
    if args[0].lower().endswith(".json"):
        with open(args[0], encoding="utf-8-sig") as file:
            return {args[0]: json.load(file)}
    if args[0] in EXAMPLES:
        return {args[0]: EXAMPLES[args[0]]}
    raise SystemExit(
        f"Unknown example '{args[0]}'. Choose from: {', '.join(EXAMPLES)}, all, or a .json file."
    )


def main() -> None:
    specs = load_specs(sys.argv[1:])
    app = connect()
    revision, year = version_info(app)
    print(f"Connected to SolidWorks {year} (revision {revision})")

    for label, spec in specs.items():
        print(f"\n=== {label} ===")
        try:
            doc, feature = build_part(app, spec)
            print(f"Created feature: {feature.Name}")
            check_part(doc, spec)
        except ValueError as error:
            print(f"Rejected before touching SolidWorks:\n{error}")
        except Exception:
            print("Failed. Please send me everything below:\n")
            traceback.print_exc()


if __name__ == "__main__":
    main()