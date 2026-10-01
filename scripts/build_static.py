"""Generar el release público sin abrir ni crear una base de datos."""
from html.parser import HTMLParser
from pathlib import Path
from shutil import copyfile

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from app.schemas import Profile

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "docs"
SITE_URL = "https://mcordero1.github.io/"

# Archivos estáticos que se copian a docs/static/
STATIC_FILES = ("style.css", "favicon.svg", "portfolio.js")


class LinkCheck(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.links = []
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        if "href" in attrs:
            self.links.append(attrs["href"])
        if tag == "script" and "src" in attrs:
            self.scripts.append(attrs["src"])


def build():
    profile = Profile.model_validate_json((ROOT / "content/profile.json").read_text(encoding="utf-8"))
    env = Environment(
        loader=FileSystemLoader(ROOT / "templates"),
        autoescape=select_autoescape(["html"]),
        undefined=StrictUndefined,
    )
    rendered = env.get_template("profile.html").render(profile=profile, asset_prefix="./static", site_url=SITE_URL)
    html = "\n".join(line.rstrip() for line in rendered.splitlines()) + "\n"
    (PUBLIC / "static").mkdir(parents=True, exist_ok=True)
    for name in STATIC_FILES:
        src = ROOT / "static" / name
        if src.exists():
            copyfile(src, PUBLIC / "static" / name)
        else:
            print(f"Aviso: {src} no existe, se omite.")
    (PUBLIC / "index.html").write_text(html, encoding="utf-8", newline="\n")
    (PUBLIC / ".nojekyll").write_text("", encoding="utf-8")
    # Comprobar el HTML generado y los destinos internos antes de publicarlo.
    check = LinkCheck()
    check.feed(html)
    assert "{{" not in html and "{%" not in html, "Quedaron variables sin renderizar."
    for link in check.links:
        if link.startswith("#"):
            assert link[1:] in check.ids, f"Ancla inexistente: {link}"
        elif link.startswith("./"):
            assert (PUBLIC / link).is_file(), f"Recurso inexistente: {link}"
    for src in check.scripts:
        if src.startswith("./"):
            assert (PUBLIC / src).is_file(), f"Script inexistente: {src}"
    assert len(profile.experience) == html.count('<article class="job">')
    print(f"Release estático generado en {PUBLIC}: {len(profile.experience)} experiencias, {len(check.links)} enlaces y {len(check.scripts)} scripts verificados.")


if __name__ == "__main__":
    build()
