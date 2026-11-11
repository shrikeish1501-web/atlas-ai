"""Step 16: the whole Day 2 pipeline in one command.

    python atlas_cad.py "a plate 120 by 70 by 10 mm with two 8 mm holes"
    python atlas_cad.py                 (type requests one after another)

Request -> AI writes JSON -> validate -> build in SolidWorks -> measure -> save .SLDPRT + .STEP
"""

import json
import sys
import time
import traceback

from sw_builder import build_part, check_part
from sw_connect import connect, version_info
from sw_export import export_part
from text_to_spec import generate_spec


def process(request: str, app) -> None:
    started = time.time()
    print(f"\nRequest: {request}")

    result = generate_spec(request, verbose=True)
    if result["status"] == "unsupported":
        print(f"Not supported: {result['reason']}")
        return
    if result["status"] != "ok":
        print("The AI could not produce a valid spec:")
        for problem in result["problems"]:
            print(f"  - {problem}")
        return

    spec = result["spec"]
    print("\nSpec:")
    print(json.dumps(spec, indent=2))

    doc, _feature = build_part(app, spec)
    print()
    if not check_part(doc, spec):
        print("\nNOT saved: at least one check did not pass. Look at the part in SolidWorks.")
        return

    files = export_part(doc, spec)
    print("\nAll checks passed. Saved:")
    for key in ("sldprt", "step"):
        path = files[key]
        print(f"  {path.relative_to(path.parent.parent)}  ({path.stat().st_size / 1024:.0f} KB)")
    print(f"STEP check: {files['step_info']}")
    if "unit: metre" in files["step_info"]:
        print("Tip: set your default part template to MMGS so STEP files use millimetres.")
    print(f"(total {time.time() - started:.1f} s)")


def main() -> None:
    request = " ".join(sys.argv[1:]).strip()
    try:
        app = connect()
        revision, year = version_info(app)
        print(f"Connected to SolidWorks {year} (revision {revision})")

        if request:
            process(request, app)
            return
        print("Describe a plate or a cylinder, or q to quit.")
        while True:
            request = input("\nDescribe the part> ").strip()
            if request.lower() in ("q", "quit", "exit"):
                break
            if request:
                try:
                    process(request, app)
                except Exception:
                    traceback.print_exc()
    except Exception:
        print("Something went wrong. Please send me everything below:\n")
        traceback.print_exc()


if __name__ == "__main__":
    main()