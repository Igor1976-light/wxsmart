import re
from pathlib import Path

from pypdf import PdfReader

pdf_path = Path("Weller WXsmart im Test - element14 Community.pdf")
reader = PdfReader(str(pdf_path))
print("PAGES", len(reader.pages))

patterns = re.compile(
    r"mqtt|mosquitto|websocket|topic|subscribe|publish|status|command|wxsmart|serial|1883|9001|3084",
    re.I,
)
found: list[tuple[int, str]] = []
for idx, page in enumerate(reader.pages, start=1):
    text = page.extract_text() or ""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line and patterns.search(line):
            found.append((idx, line))

print("MATCHES", len(found))
for page, line in found[:300]:
    print(f"[{page:02d}] {line}")
