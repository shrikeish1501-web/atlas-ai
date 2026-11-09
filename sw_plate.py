"""Step 12: build a rectangular plate in SolidWorks from Python.

The SolidWorks API works in metres, so every size is converted from millimetres.
Run this file directly:  python sw_plate.py
"""

import traceback

import pythoncom
import win32com.client

from sw_connect import connect, version_info

PART_TEMPLATE = 8  # swDefaultTemplatePart: the default part template path
DEFAULT_PLANES = {"Front Plane": 0, "Top Plane": 1, "Right Plane": 2}


def mm(value: float) -> float:
    """Convert millimetres to metres (the SolidWorks API unit)."""
    return value / 1000.0


def call(obj, name, *args):
    """Call a COM method; if it turns out to be a plain value, just return it."""
    attribute = getattr(obj, name)
    return attribute(*args) if callable(attribute) else attribute


def new_part(app):
    """Create a new empty part using the default part template."""
    template = app.GetUserPreferenceStringValue(PART_TEMPLATE)
    doc = app.NewDocument(template, 0, 0, 0) if template else None
    if doc is None:
        doc = app.NewPart()  # fallback when no default template is configured
    return doc


def select_plane(doc, plane_name: str = "Top Plane") -> bool:
    """Select one of the three default planes."""
    doc.ClearSelection2(True)

    # SelectByID2 needs an empty 'callout' object, so we build one explicitly.
    callout = win32com.client.VARIANT(pythoncom.VT_DISPATCH, None)
    if doc.Extension.SelectByID2(plane_name, "PLANE", 0, 0, 0, False, 0, callout, 0):
        return True

    # Fallback: default planes always come in the order Front, Top, Right.
    wanted = DEFAULT_PLANES[plane_name]
    found = 0
    feature = call(doc, "FirstFeature")
    while feature is not None:
        if call(feature, "GetTypeName2") == "RefPlane":
            if found == wanted:
                return bool(call(feature, "Select2", False, 0))
            found += 1
        feature = call(feature, "GetNextFeature")
    return False


def build_plate(app, length_mm: float, width_mm: float, thickness_mm: float):
    """Build a plate lying on the Top Plane, centred on the origin."""
    doc = new_part(app)
    if doc is None:
        raise RuntimeError("SolidWorks did not create a new part.")

    if not select_plane(doc, "Top Plane"):
        raise RuntimeError("Could not select the Top Plane.")

    sketch = doc.SketchManager
    sketch.InsertSketch(True)  # start a sketch on the selected plane
    sketch.CreateCenterRectangle(0, 0, 0, mm(length_mm) / 2, mm(width_mm) / 2, 0)

    depth = mm(thickness_mm)
    feature = doc.FeatureManager.FeatureExtrusion2(
        True, False, False,      # single direction, no flip, no flip-to-cut
        0, 0,                    # end condition 1 and 2 = blind
        depth, depth,            # depth in direction 1 and 2
        False, False, False, False,  # no draft in either direction
        0.0, 0.0,                # draft angles (unused)
        False, False, False, False,  # offset / translate-surface options
        True, True, True,        # merge result, use feature scope, auto-select
        0, 0.0, False,           # start condition = sketch plane, no offset
    )
    if feature is None:
        raise RuntimeError("The extrude failed (SolidWorks returned nothing).")

    try:  # cosmetic only
        doc.ShowNamedView2("*Isometric", 7)
        doc.ViewZoomtofit2()
    except Exception:
        pass
    return doc, feature


def part_size_mm(doc):
    """Return the part's bounding-box size [X, Y, Z] in millimetres."""
    box = doc.GetPartBox(True)  # [xmin, ymin, zmin, xmax, ymax, zmax] in metres
    return [round((box[i + 3] - box[i]) * 1000, 3) for i in range(3)]


def main() -> None:
    try:
        app = connect()
        revision, year = version_info(app)
        print(f"Connected to SolidWorks {year} (revision {revision})")

        doc, feature = build_plate(app, length_mm=100, width_mm=60, thickness_mm=8)
        print(f"New part: {call(doc, 'GetTitle')}")
        print(f"Created feature: {feature.Name}")

        try:
            x, y, z = part_size_mm(doc)
            print(f"Size X, Y, Z in mm: [{x}, {y}, {z}]")
        except Exception as error:
            print(f"(could not read the size automatically: {error})")

        print("Done. Look at SolidWorks: a flat plate should be showing.")
    except Exception:
        print("Something went wrong. Please send me everything below:\n")
        traceback.print_exc()


if __name__ == "__main__":
    main()