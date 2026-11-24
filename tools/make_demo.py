"""Generate a demo form PDF + a transparent signature PNG for trying the app.

    python tools/make_demo.py
"""
import os
import sys

import pymupdf
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(HERE)


def make_signature(path):
    img = Image.new("RGBA", (800, 260), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.line([(40, 190), (150, 50), (240, 180), (360, 60), (470, 185), (700, 90)],
           fill=(12, 32, 110, 255), width=12, joint="curve")
    d.line([(170, 205), (690, 210)], fill=(12, 32, 110, 255), width=6)
    img.save(path)
    return path


def make_form(path):
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)

    page.insert_text((56, 70), "SERVICE AGREEMENT", fontsize=18, fontname="hebo")
    page.insert_text((56, 100), "Form 2026-A  ·  please complete in ink or electronically",
                     fontsize=9, color=(0.35, 0.35, 0.35))

    y = 150
    for label, value in (("Full name", ""), ("NRIC / IC No.", ""), ("Date", ""),
                         ("Address", "")):
        page.insert_text((56, y + 12), label, fontsize=10)
        page.draw_line((56 + 140, y + 15), (520, y + 15), color=(0.6, 0.6, 0.6),
                       width=0.6)
        y += 44

    page.insert_text((56, y + 26), "Terms accepted", fontsize=11, fontname="hebo")
    page.draw_rect(pymupdf.Rect(56, y + 40, 72, y + 56), width=0.9)
    page.insert_text((82, y + 53), "Yes", fontsize=10)
    page.draw_rect(pymupdf.Rect(56, y + 68, 72, y + 84), width=0.9)
    page.insert_text((82, y + 81), "No", fontsize=10)

    page.insert_text((56, 700), "Signature", fontsize=10)
    page.draw_line((56, 740), (300, 740), color=(0.6, 0.6, 0.6), width=0.6)

    doc.save(path)
    doc.close()
    return path


def make_rotated_page(path):
    """A page with /Rotate 90 - the case that breaks naive editors."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((80, 120), "ROTATED PAGE", fontsize=22, fontname="hebo")
    page.insert_text((80, 160), "This page carries a /Rotate 90 entry.",
                     fontsize=10)
    page.set_rotation(90)
    doc.save(path)
    doc.close()
    return path


def make_signed(src_pdf, sig_png, out_pdf):
    """Fill + sign the demo form, exactly like the app would."""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from pdfedit.engine import PdfDocument

    with PdfDocument(src_pdf) as doc:
        doc.add_text(0, 200, 165, text="SAMPLE SIGNATORY", size=11)
        doc.add_text(0, 200, 209, text="000000-00-0000", size=11)
        doc.add_text(0, 200, 253, text="24 November 2026", size=11)
        doc.add_check(0, 64, 396, size=14)
        doc.add_cross(0, 64, 424, size=14)
        doc.add_image(0, sig_png, 120, 660, 180, 58)
        doc.export(out_pdf)
    return out_pdf


if __name__ == "__main__":
    sig = make_signature(os.path.join(OUT, "demo_signature.png"))
    form = make_form(os.path.join(OUT, "demo_form.pdf"))
    rot = make_rotated_page(os.path.join(OUT, "demo_rotated.pdf"))
    signed = make_signed(form, sig, os.path.join(OUT, "demo_signed.pdf"))
    print("wrote:")
    for f in (form, rot, sig, signed):
        print("  ", f)
