"""Macht tiny-qwen/run.py unter nativem Windows lauffaehig.

Benutzung (im tiny-qwen Ordner):
    python patch_windows.py
oder mit Pfad:
    python patch_windows.py C:\\pfad\\zu\\run.py

Es wird eine Sicherung run.py.bak angelegt.
"""
import re
import shutil
import sys
from pathlib import Path

path = Path(sys.argv[1] if len(sys.argv) > 1 else "run.py")
if not path.exists():
    sys.exit(f"Datei nicht gefunden: {path}")

src = path.read_text(encoding="utf-8")

if "msvcrt" in src:
    sys.exit("run.py ist schon gepatcht.")

shutil.copy(path, path.with_name(path.name + ".bak"))

# 1) Unix-only Imports entfernen und plattformabhaengig neu einfuegen
for line in (r"import readline.*", r"import select", r"import termios", r"import tty"):
    src, n = re.subn(rf"^{line}\n", "", src, count=1, flags=re.M)
    if n == 0:
        print(f"Hinweis: Zeile '{line}' nicht gefunden (evtl. schon geaendert)")

IMPORT_BLOCK = '''from pathlib import Path

if os.name == "nt":
    import msvcrt

    os.system("")  # ANSI-Farben in der Windows-Konsole aktivieren
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
else:
    import readline  # noqa: F401 - Pfeiltasten und History im Prompt
    import select
    import termios
    import tty
'''
if "from pathlib import Path\n" not in src:
    sys.exit("Konnte 'from pathlib import Path' nicht finden - andere run.py-Version?")
src = src.replace("from pathlib import Path\n", IMPORT_BLOCK, 1)

# 2) EscWatch plattformuebergreifend ersetzen
ESC_WATCH = '''class EscWatch:
    """Fragt waehrend eines Turns ab, ob Esc gedrueckt wurde (Windows + Unix)."""

    def __enter__(self):
        self.enabled = sys.stdin.isatty()
        if self.enabled and os.name != "nt":
            self.fd = sys.stdin.fileno()
            self.old = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
        return self

    def pressed(self):
        if not self.enabled:
            return False
        hit = False
        if os.name == "nt":
            while msvcrt.kbhit():
                if msvcrt.getwch() == "\\x1b":
                    hit = True
        else:
            while select.select([sys.stdin], [], [], 0)[0]:
                if sys.stdin.read(1) == "\\x1b":
                    hit = True
        return hit

    def __exit__(self, *exc):
        if self.enabled and os.name != "nt":
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old)

'''
src, n = re.subn(
    r"class EscWatch:.*?(?=\n# -+ backends)",
    lambda m: ESC_WATCH.rstrip("\n") + "\n",
    src,
    count=1,
    flags=re.S,
)
if n == 0:
    sys.exit("Konnte die Klasse EscWatch nicht finden - andere run.py-Version?")

# 3) Dem Modell sagen, dass es unter Windows laeuft
src = src.replace(
    "working from a terminal.",
    "working from a Windows terminal (cmd.exe), so use Windows commands such as "
    "dir and type instead of ls and cat.",
    1,
)

path.write_text(src, encoding="utf-8")
print(f"Fertig. Gepatcht: {path}  (Sicherung: {path.name}.bak)")
