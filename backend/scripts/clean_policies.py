"""Clean Unicode characters from all policy .txt files so they are pure ASCII-safe."""
from pathlib import Path

replacements = {
    "\u2192": "->",    # →
    "\u2190": "<-",    # ←
    "\u2022": "-",     # •
    "\u2013": "-",     # –
    "\u2014": "--",    # —
    "\u2018": "'",     # '
    "\u2019": "'",     # '
    "\u201c": '"',     # "
    "\u201d": '"',     # "
    "\u00a0": " ",     # non-breaking space
    "\u20b9": "INR ",  # ₹
    "\u2264": "<=",    # ≤
    "\u2265": ">=",    # ≥
    "\u00b1": "+/-",   # ±
    "\u00d7": "x",     # ×
    "\u2713": "YES",   # ✓
    "\u2717": "NO",    # ✗
    "\u25cf": "*",     # ●
    "\u2610": "[ ]",   # ☐
    "\u2611": "[x]",   # ☑
    "\u00ae": "(R)",   # ®
    "\u00a9": "(C)",   # ©
}

policies_dir = Path("data/policies")
files = sorted(policies_dir.glob("*.txt"))
print(f"Processing {len(files)} policy files...")

for f in files:
    text = f.read_text(encoding="utf-8", errors="replace")
    new_text = text
    for ch, rep in replacements.items():
        new_text = new_text.replace(ch, rep)
    # Final safety net: encode to ASCII replacing anything else
    new_text = new_text.encode("ascii", errors="replace").decode("ascii")
    new_text = new_text.replace("?", "-")  # replace any leftover replacement chars
    if new_text != text:
        f.write_text(new_text, encoding="utf-8")
        print(f"  [cleaned] {f.name}")
    else:
        print(f"  [ok]      {f.name}")

print("Done.")
