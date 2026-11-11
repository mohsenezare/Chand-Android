from pathlib import Path
import re

path = Path("source/app/src/test/java/ir/personal/chand/data/MarketParsersTest.kt")
if not path.exists():
    raise SystemExit(f"Missing expected Kotlin test file: {path}")

text = path.read_text()
# A previous migration edit accidentally serialized line breaks as literal backslash-n.
text = text.replace(chr(92) + "n", chr(10))
lines = text.splitlines()
fixed = []
for line in lines:
    if re.match(r"^\s*fun\s+", line):
        previous = fixed[-1].strip() if fixed else ""
        if previous != "@Test":
            fixed.append("    @Test")
    fixed.append(line)
text = "\n".join(fixed).rstrip() + "\n"
path.write_text(text)
