"""Generate both public languages without opening or creating a database."""
from html.parser import HTMLParser
from pathlib import Path
from shutil import copyfile
from urllib.parse import urlsplit
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from app.localization import locale_context, localized_profile

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / 'docs'
SITE_URL = 'https://mcordero1.github.io/'


class LinkCheck(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.links = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'id' in attrs:
            assert attrs['id'] not in self.ids, f"Duplicate ID: {attrs['id']}"
            self.ids.add(attrs['id'])
        for attr in ('href', 'src'):
            if attr in attrs:
                self.links.append(attrs[attr])


def build():
    env = Environment(loader=FileSystemLoader(ROOT / 'templates'), autoescape=select_autoescape(['html']), undefined=StrictUndefined)
    (PUBLIC / 'static').mkdir(parents=True, exist_ok=True)
    (PUBLIC / 'en').mkdir(parents=True, exist_ok=True)
    for name in ('style.css', 'favicon.svg', 'preferences.js', 'preferences.css'):
        copyfile(ROOT / 'static' / name, PUBLIC / 'static' / name)
    pages = []
    for language in ('es', 'en'):
        english = language == 'en'
        directory = PUBLIC / 'en' if english else PUBLIC
        profile = localized_profile(language)
        rendered = env.get_template('profile.html').render(
            profile=profile, **locale_context(language, '../' if english else './en/'),
            asset_prefix='../static' if english else './static',
            site_url=SITE_URL + ('en/' if english else ''),
            alternate_urls={'es': SITE_URL, 'en': SITE_URL + 'en/', 'x-default': SITE_URL},
        )
        html = '\n'.join(line.rstrip() for line in rendered.splitlines()) + '\n'
        (directory / 'index.html').write_text(html, encoding='utf-8', newline='\n')
        assert len(profile.experience) == html.count('<article class="job">')
        pages.append((directory, html))
    for directory, html in pages:
        assert '{{' not in html and '{%' not in html
        check = LinkCheck()
        check.feed(html)
        for link in check.links:
            if link.startswith('#'):
                assert link[1:] in check.ids, f'Unknown anchor: {link}'
            elif not urlsplit(link).scheme:
                target = (directory / urlsplit(link).path).resolve()
                assert target.is_relative_to(PUBLIC.resolve()), f'Link outside public directory: {link}'
                if target.is_dir():
                    target /= 'index.html'
                assert target.is_file(), f'Missing resource: {link}'
    (PUBLIC / '.nojekyll').write_text('', encoding='utf-8')
    print('Generated Spanish and English profiles; links, scripts, assets and anchors verified.')


if __name__ == '__main__':
    build()
