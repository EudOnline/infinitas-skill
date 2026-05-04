#!/usr/bin/env python3
"""Remove decorative CSS comments (emojis, section banners, Chinese descriptions)."""
import re
import sys

CSS_FILE = "server/static/css/input.css"

with open(CSS_FILE) as f:
    lines = f.readlines()

count = 0
output = []
emoji_pattern = re.compile(
    r"^\s*/\*\s*["+
    "".join(chr(c) for c in range(0x1F300, 0x1F9FF)) +
    "".join(chr(c) for c in range(0x2600, 0x26FF)) +
    "".join(chr(c) for c in range(0x2700, 0x27BF)) +
    "".join(chr(c) for c in range(0xFE00, 0xFE0F)) +
    r"\dD]+.*\*/\s*$"
)
banner_pattern = re.compile(r"^\s*/\*\s*(=+|-+)\s*\*/\s*$")
chinese_pattern = re.compile(r"^\s*/\*\s*[\u4e00-\u9fff]+.*\*/\s*$")

for line in lines:
    if emoji_pattern.match(line):
        count += 1
        continue
    if banner_pattern.match(line):
        count += 1
        continue
    if chinese_pattern.match(line):
        count += 1
        continue
    # Also remove single decorative markers like "/* ===== */" anywhere in the line
    output.append(line)

with open(CSS_FILE, "w") as f:
    f.writelines(output)

print(f"Removed {count} decorative comment lines. Remaining lines: {len(output)}")
