"""Step 15: turn a plain-English request into a validated JSON part spec.

Usage:
    python text_to_spec.py                      type requests one after another
    python text_to_spec.py "plate 100x60x8 with two 8.5 mm holes"
    python text_to_spec.py --demo               run 7 sample requests and score them
"""

import json
import sys
import time

import ollama

from config import CHAT_MODEL
from part_spec import extract_json, validate_spec
from rag import clean_answer, model_settings

MAX_ATTEMPTS = 3
NUM_CTX = 4096
SPEC_FILE = "last_spec.json"

PLATE_KEYS = ("part_type", "name", "units", "length", "width", "thickness", "holes")
CYLINDER_KEYS = ("part_type", "name", "units", "diameter", "length", "bore_diameter")

SYSTEM_PROMPT = """You convert a user's request for a mechanical part into ONE JSON object. Output JSON only.

Supported part types: "plate" and "cylinder".

plate:    {"part_type": "plate", "name": "...", "units": "mm", "length": L, "width": W, "thickness": T, "holes": [{"diameter": D, "x": X, "y": Y}]}
cylinder: {"part_type": "cylinder", "name": "...", "units": "mm", "diameter": D, "length": L, "bore_diameter": B}

Rules:
- Every plate must include length, width and thickness. Every cylinder must include diameter and length. All of them are plain numbers.
- All sizes are in millimetres. Convert other units first (1 cm = 10 mm, 1 inch = 25.4 mm, 1 m = 1000 mm). "units" is always "mm".
- "name" is a short CamelCase name without spaces, for example "MountingPlate".
- A plate lies flat. Hole positions x and y are measured from the CENTRE of the plate in mm: x along the length (positive to the right), y along the width (positive upwards).
- If the user gives no hole positions: 1 hole goes at x=0, y=0. 2 holes go on the centreline (y=0) at x = -(length/2 - 15) and x = +(length/2 - 15). 4 holes go in the four corners at x = +/-(length/2 - 15) and y = +/-(width/2 - 15).
- Leave "holes" out when the plate has no holes. Leave "bore_diameter" out when the cylinder has no bore.
- If the request is not a plate or a cylinder, or a needed size is missing, output {"part_type": "unsupported", "units": "mm", "reason": "<one short sentence>"}.
- Never invent a main size or a hole diameter that the user did not give."""


def _example(request: str, spec: dict) -> list:
    return [
        {"role": "user", "content": request},
        {"role": "assistant", "content": json.dumps(spec)},
    ]


EXAMPLES = (
    _example(
        "a plate 100 by 60 by 8 mm with two 8.5 mm holes",
        {"part_type": "plate", "name": "MountingPlate", "units": "mm",
         "length": 100, "width": 60, "thickness": 8,
         "holes": [{"diameter": 8.5, "x": -35, "y": 0}, {"diameter": 8.5, "x": 35, "y": 0}]},
    )
    + _example(
        "10 cm x 6 cm plate, 5 mm thick, 4 corner holes 6 mm",
        {"part_type": "plate", "name": "CornerHolePlate", "units": "mm",
         "length": 100, "width": 60, "thickness": 5,
         "holes": [{"diameter": 6, "x": -35, "y": -15}, {"diameter": 6, "x": 35, "y": -15},
                   {"diameter": 6, "x": -35, "y": 15}, {"diameter": 6, "x": 35, "y": 15}]},
    )
    + _example(
        "round bar 30 mm diameter, 80 mm long, with a 10 mm bore",
        {"part_type": "cylinder", "name": "RoundBar", "units": "mm",
         "diameter": 30, "length": 80, "bore_diameter": 10},
    )
    + _example(
        "a gear with 20 teeth",
        {"part_type": "unsupported", "units": "mm", "reason": "Only plates and cylinders are supported."},
    )
    + _example(
        "a steel plate with a hole",
        {"part_type": "unsupported", "units": "mm",
         "reason": "Missing length, width, thickness and hole diameter."},
    )
)


def clean_spec(spec: dict) -> dict:
    """Keep only the keys that belong to the part type and drop empty or zero extras."""
    part_type = spec.get("part_type")
    if part_type == "plate":
        keys = PLATE_KEYS
    elif part_type == "cylinder":
        keys = CYLINDER_KEYS
    else:
        return spec
    cleaned = {key: value for key, value in spec.items() if key in keys}
    if not cleaned.get("bore_diameter"):
        cleaned.pop("bore_diameter", None)
    if not cleaned.get("holes"):
        cleaned.pop("holes", None)
    return cleaned


def ask_model(messages: list) -> str:
    """Send the conversation to the local model and return its reply text."""
    think, _ = model_settings(CHAT_MODEL)
    extra = {} if think is None else {"think": think}
    response = ollama.chat(
        model=CHAT_MODEL,
        messages=messages,
        options={"temperature": 0.1, "num_ctx": NUM_CTX},
        **extra,
    )
    return clean_answer(response["message"]["content"])


def generate_spec(request: str, verbose: bool = False) -> dict:
    """Ask for a spec, validate it, and retry with the error messages if needed.

    Returns a dict with "status" = "ok" | "unsupported" | "failed" and "attempts".
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + EXAMPLES
    messages.append({"role": "user", "content": request})

    problems = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        text = ask_model(messages)
        try:
            spec = extract_json(text)
        except ValueError as error:
            problems = [f"The reply was not valid JSON ({error})."]
        else:
            if spec.get("part_type") == "unsupported":
                return {"status": "unsupported", "reason": spec.get("reason", ""), "attempts": attempt}
            spec = clean_spec(spec)
            problems = validate_spec(spec)
            if not problems:
                return {"status": "ok", "spec": spec, "attempts": attempt}

        if verbose:
            print(f"  attempt {attempt} reply: {text[:300]}")
            for problem in problems:
                print(f"  attempt {attempt} rejected: {problem}")
        messages.append({"role": "assistant", "content": text})
        messages.append(
            {
                "role": "user",
                "content": "That JSON has problems:\n- " + "\n- ".join(problems)
                + "\nReturn the corrected JSON only, with every required key as a plain number.",
            }
        )
    return {"status": "failed", "problems": problems, "attempts": MAX_ATTEMPTS}


def run_request(request: str) -> None:
    """Handle one request and print the result."""
    started = time.time()
    result = generate_spec(request, verbose=True)
    seconds = time.time() - started

    print(f"\nRequest: {request}")
    if result["status"] == "ok":
        print(json.dumps(result["spec"], indent=2))
        with open(SPEC_FILE, "w", encoding="utf-8") as file:
            json.dump(result["spec"], file, indent=2)
        print(f"\n(valid on attempt {result['attempts']}, {seconds:.1f} s) saved to {SPEC_FILE}")
        print(f"Build it in SolidWorks with:  python sw_builder.py {SPEC_FILE}")
    elif result["status"] == "unsupported":
        print(f"Not supported: {result['reason']}  ({seconds:.1f} s)")
    else:
        print("Could not produce a valid spec. Last problems:")
        for problem in result["problems"]:
            print(f"  - {problem}")


# ----- Demo: 7 requests with the answers we expect -----
DEMO = [
    ("I need a mounting plate, 150 mm long, 90 mm wide and 10 mm thick, with two 9 mm holes",
     {"part_type": "plate", "length": 150, "width": 90, "thickness": 10, "n_holes": 2, "hole_diameter": 9}),
    ("plate 120 x 80 x 6 with 4 corner holes of 6 mm",
     {"part_type": "plate", "length": 120, "width": 80, "thickness": 6, "n_holes": 4, "hole_diameter": 6}),
    ("a 4 inch by 2 inch plate, 0.25 inch thick",
     {"part_type": "plate", "length": 101.6, "width": 50.8, "thickness": 6.35, "n_holes": 0}),
    ("a round bar 25 mm in diameter and 120 mm long",
     {"part_type": "cylinder", "diameter": 25, "length": 120, "bore_diameter": None}),
    ("a hollow tube with 40 mm outer diameter, a 30 mm bore and 200 mm length",
     {"part_type": "cylinder", "diameter": 40, "length": 200, "bore_diameter": 30}),
    ("a gear with 20 teeth", "unsupported"),
    ("a plate with a hole", "unsupported"),
]


def mismatches(result: dict, expected) -> list:
    """List the ways a result differs from what we expected (empty list = all good)."""
    if expected == "unsupported":
        return [] if result["status"] == "unsupported" else [f"expected 'unsupported', got '{result['status']}'"]
    if result["status"] != "ok":
        return [f"no valid spec (status: {result['status']})"]

    spec = result["spec"]
    problems = []
    for key, wanted in expected.items():
        if key == "n_holes":
            got = len(spec.get("holes", []))
        elif key == "hole_diameter":
            diameters = {hole.get("diameter") for hole in spec.get("holes", [])}
            got = diameters.pop() if len(diameters) == 1 else sorted(map(str, diameters))
        else:
            got = spec.get(key)

        if isinstance(wanted, (int, float)) and isinstance(got, (int, float)):
            if abs(got - wanted) > 0.1:
                problems.append(f"{key}: wanted {wanted}, got {got}")
        elif got != wanted:
            problems.append(f"{key}: wanted {wanted}, got {got}")
    return problems


def run_demo() -> None:
    passed = first_try = 0
    total_seconds = 0.0
    for request, expected in DEMO:
        started = time.time()
        result = generate_spec(request)
        total_seconds += time.time() - started

        problems = mismatches(result, expected)
        if not problems:
            passed += 1
            if result["attempts"] == 1:
                first_try += 1
        status = "PASS" if not problems else "FAIL"
        print(f"{status}  attempts={result['attempts']}  {request}")
        for problem in problems:
            print(f"      - {problem}")

    total = len(DEMO)
    print(
        f"\nPassed {passed}/{total} | right on the first attempt {first_try}/{total} "
        f"| average {total_seconds / total:.1f} s per request"
    )


def main() -> None:
    args = sys.argv[1:]
    try:
        if args and args[0] == "--demo":
            run_demo()
        elif args:
            run_request(" ".join(args))
        else:
            print(f"Model: {CHAT_MODEL}. Describe a part (a plate or a cylinder), or q to quit.")
            while True:
                request = input("\nDescribe the part> ").strip()
                if request.lower() in ("q", "quit", "exit"):
                    break
                if request:
                    run_request(request)
    except Exception as error:
        print(f"Error: {type(error).__name__}: {error}")


if __name__ == "__main__":
    main()