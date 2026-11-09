"""Connect Python to SolidWorks (Step 11).

Other scripts import connect() from this file.
Run this file directly to test the link:  python sw_connect.py
"""

import struct
import sys

import win32com.client


def connect():
    """Attach to a running SolidWorks (or start it) and make sure it is visible."""
    app = win32com.client.Dispatch("SldWorks.Application")
    app.Visible = True
    return app


def version_info(app):
    """Return (revision string, release year) read from SolidWorks."""
    revision = app.RevisionNumber
    if callable(revision):  # a method in some COM modes, a plain value in others
        revision = revision()
    major = int(str(revision).split(".")[0])
    return str(revision), major + 1992  # revision 23 = 2015, so year = major + 1992


def main() -> None:
    bits = struct.calcsize("P") * 8
    print(f"Python: {sys.version.split()[0]} ({bits}-bit)")
    print("Connecting to SolidWorks (can take 30-60 seconds if it is not open yet)...")

    try:
        app = connect()
        revision, year = version_info(app)
    except Exception as error:
        print(f"Could not connect: {type(error).__name__}: {error}")
        print(
            "Tips: open SolidWorks first and wait for it to finish loading, and "
            "run PowerShell WITHOUT 'Run as administrator'."
        )
        return

    print("Connected.")
    print(f"SolidWorks revision number: {revision}  ->  SolidWorks {year}")
    print(f"Visible: {app.Visible}")
    document = app.ActiveDoc
    print("Active document:", "none (nothing is open)" if document is None else "one is open")


if __name__ == "__main__":
    main()