#!/usr/bin/env python3
"""Erzeugt icon.png (1024) fuer voice2claude.app — Mikrofon auf Verlauf."""
from PIL import Image, ImageDraw

S = 1024
TOP = (110, 123, 255)   # indigo
BOT = (46, 160, 67)     # gruen
W = (255, 255, 255, 255)

# Diagonaler Verlauf
grad = Image.new("RGB", (S, S))
px = grad.load()
for y in range(S):
    for x in range(S):
        t = (x + y) / (2 * S)
        px[x, y] = tuple(int(TOP[i] + (BOT[i] - TOP[i]) * t) for i in range(3))

# Abgerundete Maske (macOS-Squircle-naeherung)
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=232, fill=255)

img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
img.paste(grad, (0, 0), mask)
d = ImageDraw.Draw(img)

# Mikrofon
d.rounded_rectangle([417, 250, 607, 575], radius=95, fill=W)     # Kapsel
d.arc([372, 360, 652, 660], start=18, end=162, fill=W, width=44) # Buegel (U)
d.line([512, 660, 512, 752], fill=W, width=44)                   # Stiel
d.rounded_rectangle([432, 740, 592, 778], radius=19, fill=W)     # Fuss

img.save("icon.png")
print("icon.png geschrieben")
