# -*- coding: utf-8 -*-
"""Quick test: PIL + arabic_reshaper + python-bidi Arabic text rendering."""
from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display
import os

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

# Use Windows Arial (supports Arabic glyphs)
font_path = "C:/Windows/Fonts/arial.ttf"
print(f"Using font: {font_path}")

font = ImageFont.truetype(font_path, 80)

# Reshape Arabic text - use a known Quranic verse
text = "\u0628\u0650\u0633\u0652\u0645\u0650 \u0627\u0644\u0644\u0651\u064e\u0647\u0650 \u0627\u0644\u0631\u0651\u064e\u062d\u0652\u0645\u064e\u0640\u0670\u0646\u0650 \u0627\u0644\u0631\u0651\u064e\u062d\u0650\u064a\u0645\u0650"
reshaped = arabic_reshaper.reshape(text)
bidi = get_display(reshaped)

img = Image.new("RGBA", (1080, 500), (30, 30, 30, 255))
draw = ImageDraw.Draw(img)
bbox = draw.textbbox((0, 0), bidi, font=font)
tw = bbox[2] - bbox[0]
x = (1080 - tw) // 2
# Shadow
draw.text((x+3, 203), bidi, font=font, fill=(0, 0, 0, 200))
# Main text
draw.text((x, 200), bidi, font=font, fill=(255, 255, 255, 255))

out = os.path.join(ASSETS, "test_arabic.png")
img.save(out, "PNG")
print(f"SUCCESS! Saved test image to {out}")
