# Perfil profesional de Marcos Cordero Tenreyro

Primer release del perfil profesional: **web estática en GitHub Pages**, sin base de datos, sin servidor Python en producción y sin servicios adicionales.

**Sitio público:** https://mcordero1.github.io/

**Repositorio:** https://github.com/mcordero1/mcordero1.github.io

## Qué incluye

Presentación, perfil, experiencia, competencias, formación, idiomas y contacto. Diseño oscuro inspirado en tecnología financiera, adaptable a escritorio y celular. Navegación por anclas y responsabilidades desplegables. JavaScript local mínimo para apariencia y conservación de la sección al cambiar de idioma, sin rastreadores ni fuentes remotas.

El contenido se basa en el CV proporcionado. No se inventaron métricas ni continuidad laboral posterior a julio de 2026. El teléfono del CV no se incorporó al sitio.

## Actualizar el primer release

El contenido público se mantiene en `content/profile.json`; no se consulta ninguna base de datos. Editar ese archivo, generar la página y subir los cambios:

```powershell
python -m pip install -r requirements-static.txt
python -m scripts.build_static
git add content/profile.json templates static docs
git commit -m "Actualizar perfil profesional"
git push origin feature/profile-preferences
```

GitHub Pages publica automáticamente `main` → `/docs` después de cada push. Siempre regenerar `docs/` si se cambia el contenido, la plantilla o los estilos. Un cambio en SQLite no se refleja en este release.

Para revisar el sitio antes de subirlo:

```powershell
python -m http.server 8001 --directory docs
```

Abrir http://127.0.0.1:8001/. Esto solo sirve archivos; no inicia FastAPI ni crea una base.

## Archivos principales

| Archivo o carpeta | Función |
| --- | --- |
| `content/profile.json` | Datos públicos del perfil |
| `templates/profile.html` | Plantilla del diseño |
| `static/` | CSS e icono fuente |
| `scripts/build_static.py` | Genera y comprueba el sitio estático |
| `requirements-static.txt` | Dependencias para regenerar el HTML |
| `docs/` | Únicos archivos publicados por GitHub Pages |
| `DEPLOY.md` | Configuración de publicación |

El generador valida el contenido y verifica anclas, archivos de estilos e icono. Solo copia HTML, CSS, JavaScript de preferencias, icono y `.nojekyll` a `docs/`. No copia bases de datos ni credenciales.

## Desarrollo futuro

El código previo de FastAPI (`app/`), sus dependencias y pruebas se conserva como base para un release posterior. No participa de la web publicada. La base de datos, la API, un panel privado y el despliegue en Render/Neon quedaron pospuestos. No es necesario crear cuentas en esos servicios para este release.

Para ejecutar opcionalmente el prototipo de FastAPI en desarrollo, instalar `requirements.txt` y ejecutar `python -m uvicorn app.main:app --reload`. Esa versión local puede crear SQLite y es independiente del sitio estático público.


## Idiomas y apariencia

La rama `feature/profile-preferences` contiene la entrega del perfil para revisión. Se creó desde main y solo incorpora los ajustes del perfil. `feature/portfolio-health` conserva el trabajo del agente en Kiro. El perfil no incluye el agente ni su JavaScript: el futuro enlace del navbar se incorporará cuando exista la URL de su página independiente.

- Español principal: `content/profile.json`, `content/ui.es.json` → `docs/index.html`.
- Inglés: `content/profile.en.json`, `content/ui.en.json` → `docs/en/index.html`.
- Ambos idiomas usan `templates/profile.html`; actualizar ambas traducciones cuando cambie el contenido.
- El globo alterna idiomas y conserva la sección mediante el fragmento de la URL. Cada idioma funciona también sin JavaScript y conserva su URL al recargar.
- Sol/luna alternan oscuro y claro con tooltips y etiquetas accesibles en el idioma activo. El modo inicial es oscuro; la elección se guarda en localStorage (`profile-theme`). Si el almacenamiento está bloqueado, el cambio funciona durante la visita.
- `static/preferences.css` define los controles y la paleta clara. `static/preferences.js` aplica el modo antes de mostrar la página. No se usan servicios de traducción ni dependencias de frontend.

Para probar: cambiar a `feature/profile-preferences`, ejecutar `python -m scripts.build_static` y luego `python -m http.server 8001 --bind 127.0.0.1 --directory docs`. Abrir http://127.0.0.1:8001/ o http://127.0.0.1:8001/en/. Si se usan los archivos generados ya subidos, no hace falta volver a generar.

Esta rama no modifica GitHub Pages hasta integrarse en main. No fusionar la rama del agente para publicar únicamente el perfil.
