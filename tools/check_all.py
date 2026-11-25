#!/usr/bin/env python3
"""Быстрые проверки готовности: check_all.py [<chapter>]. Без LLM-вызовов, секунды.
Окружение (python3, make, poppler, claude, ffmpeg, jsonschema), синтаксис tools/*.py, схемы организаторов на месте;
для глав (одной или всех с build/<ch>/org/layer.json): tools/check_cov.py и tools/check_org.py. Код возврата 1 при любой ошибке."""
import ast, importlib.util, shutil, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
bad = []

def ok(cond, msg, fatal=True):
    print(("ok   " if cond else ("FAIL " if fatal else "warn ")) + msg)
    if not cond and fatal: bad.append(msg)

for b, fatal in (("python3", 1), ("make", 1), ("pdftotext", 1), ("pdftoppm", 1), ("claude", 1), ("ffmpeg", 0)):
    ok(shutil.which(b), f"программа {b}", bool(fatal))
ok(importlib.util.find_spec("jsonschema"), "python: jsonschema")
for p in sorted((ROOT / "tools").glob("*.py")):
    try: ast.parse(p.read_text())
    except SyntaxError as e: ok(False, f"синтаксис {p.name}: {e}")
ok(all((ROOT / "reference/organizers/01_схемы" / f).exists() for f in ("node.schema.json", "coverage.schema.json", "routing.schema.json")), "схемы организаторов")
chs = sys.argv[1:] or sorted(d.parent.parent.name for d in (ROOT / "build").glob("*/org/layer.json"))
for ch in chs:
    for tool, extra in (("check_cov.py", []), ("check_org.py", [])):
        r = subprocess.run(["python3", "-I", f"tools/{tool}", ch, *extra], cwd=ROOT, capture_output=True, text=True)
        last = (r.stdout.strip().splitlines() or [""])[-1][:150]
        ok(r.returncode == 0, f"{tool} {ch}: {last}")
print("ГОТОВО" if not bad else f"ОШИБОК: {len(bad)}")
sys.exit(1 if bad else 0)
