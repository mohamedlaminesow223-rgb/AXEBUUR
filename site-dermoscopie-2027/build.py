"""Assemble index.html : remplace les {{...}} de site.src.html par les images en data URI."""
import base64
from pathlib import Path

ICI = Path(__file__).resolve().parent
IMAGES = {
    "PHOTO": ("photo-dermatoscope.jpg", "image/jpeg"),
    "LOGO_COURS": ("logo-cours.png", "image/png"),
    "LOGO_SOSEDEV": ("logo-sosedev.png", "image/png"),
}

html = (ICI / "site.src.html").read_text(encoding="utf-8")
for cle, (nom, mime) in IMAGES.items():
    data = base64.b64encode((ICI / nom).read_bytes()).decode()
    html = html.replace("{{" + cle + "}}", f"data:{mime};base64,{data}")
(ICI / "index.html").write_text(html, encoding="utf-8")
print("index.html", len(html) // 1024, "Ko")
