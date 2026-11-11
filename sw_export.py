"""Step 16: save a built part as .SLDPRT and export it as .STEP."""

import re
from pathlib import Path

import pythoncom
import win32com.client

OUTPUT_DIR = Path(__file__).parent / "outputs"
CURRENT_VERSION = 0  # swSaveAsCurrentVersion
SILENT = 1           # swSaveAsOptions_Silent: no pop-up dialogs


def safe_stem(name) -> str:
    """Turn a part name into a safe file name: letters, digits and underscores only."""
    text = re.sub(r"[^A-Za-z0-9_]+", "_", str(name or "")).strip("_")
    return text or "Part"


def unique_stem(stem: str) -> str:
    """Add _2, _3, ... so that existing files are never overwritten."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    candidate, number = stem, 1
    while any((OUTPUT_DIR / f"{candidate}{ext}").exists() for ext in (".SLDPRT", ".STEP")):
        number += 1
        candidate = f"{stem}_{number}"
    return candidate


def save_as(doc, path: Path) -> None:
    """Save or export the document. The file type is decided by the extension."""
    doc.ClearSelection2(True)  # nothing selected, so the whole model is exported
    errors = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, -1)
    warnings = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, -1)
    nothing = win32com.client.VARIANT(pythoncom.VT_DISPATCH, None)

    extension = doc.Extension
    try:
        ok = extension.SaveAs3(str(path), CURRENT_VERSION, SILENT, nothing, nothing, errors, warnings)
    except Exception:  # older name of the same method
        ok = extension.SaveAs(str(path), CURRENT_VERSION, SILENT, nothing, errors, warnings)

    if not ok or not path.exists():
        raise RuntimeError(
            f"SolidWorks could not save {path.name} (errors={errors.value}, warnings={warnings.value})"
        )


def describe_step(path: Path) -> str:
    """Read the STEP file and report whether it is valid and which length unit it uses."""
    text = path.read_text(errors="ignore")
    if not text.startswith("ISO-10303-21"):
        return "this does not look like a STEP file"
    compact = "".join(text.split())
    if ".MILLI.,.METRE." in compact:
        unit = "millimetre"
    elif "SI_UNIT($,.METRE.)" in compact:
        unit = "metre"
    else:
        unit = "unknown"
    solids = text.count("MANIFOLD_SOLID_BREP")
    return f"valid STEP file, {solids} solid(s), length unit: {unit}"


def export_part(doc, spec: dict) -> dict:
    """Save outputs/<name>.SLDPRT and export outputs/<name>.STEP."""
    stem = unique_stem(safe_stem(spec.get("name") or spec["part_type"]))
    sldprt = OUTPUT_DIR / f"{stem}.SLDPRT"
    step = OUTPUT_DIR / f"{stem}.STEP"

    save_as(doc, sldprt)
    save_as(doc, step)
    return {"sldprt": sldprt, "step": step, "step_info": describe_step(step)}