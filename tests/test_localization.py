from app.localization import locale_context, localized_profile
from scripts import build_static


def test_bilingual_build_has_complete_navigation_and_no_agent(tmp_path, monkeypatch):
    monkeypatch.setattr(build_static, 'PUBLIC', tmp_path)
    build_static.build()
    spanish = (tmp_path / 'index.html').read_text(encoding='utf-8')
    english = (tmp_path / 'en/index.html').read_text(encoding='utf-8')
    assert 'lang="es"' in spanish and 'lang="en"' in english
    assert 'href="./en/?v=2"' in spanish and 'href="../?v=2"' in english
    assert 'Cambiar a inglés' in spanish and 'Switch to Spanish' in english
    assert 'Cambiar a modo claro' in spanish and 'Switch to light mode' in english
    assert 'View responsibilities' in english and 'Ver responsabilidades' not in english
    for html in (spanish, english):
        assert 'portfolio-health' not in html and 'portfolio.js' not in html
        assert html.count('<article class="job">') == 6
        assert html.index('Product Manager') < html.index('Blockchain')
        assert 'preferences.js' in html and 'preferences.css' in html
    assert (tmp_path / 'static/preferences.js').is_file()


def test_translation_preserves_identity_and_record_structure():
    es, en = localized_profile('es'), localized_profile('en')
    assert es.name == en.name and es.email == en.email and es.linkedin == en.linkedin
    assert len(es.education) == len(en.education) == 5
    assert len(es.courses) == len(en.courses) == 2
    assert [j.company for j in es.experience] == [j.company for j in en.experience]
    assert [len(j.highlights) for j in es.experience] == [len(j.highlights) for j in en.experience]
    assert locale_context('es', '/en/')['ui'].keys() == locale_context('en', '/')['ui'].keys()
