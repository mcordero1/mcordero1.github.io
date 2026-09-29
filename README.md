# Perfil profesional de Marcos Cordero Tenreyro

Primera sección de una web personal modular, construida con Python y FastAPI. Diseño oscuro inspirado en tecnología financiera: jerarquía editorial, tipografía legible, acentos verdes y referencias discretas a interfaces de mercado. El contenido profesional es el centro de la página.

## Ejecutar localmente

Requiere Python 3.12 o superior. Desde esta carpeta, en PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Abrir http://127.0.0.1:8000. La primera ejecución crea `data/profile.db` y carga `content/profile.json`. Las ejecuciones posteriores conservan las ediciones existentes. Para inicializar sin abrir el servidor: `python -m app.manage init`.

## Actualizar el perfil desde la base de datos

La página y `GET /api/v1/profile` consultan la base en cada petición; no hay que recompilar ni reiniciar. Una pestaña ya abierta debe recargarse para recibir los cambios.

Con el Python del entorno virtual:

```powershell
# Copia de seguridad: usar un nombre nuevo cada vez.
.\.venv\Scripts\python.exe -m app.manage export profile-backup-01.json
.\.venv\Scripts\python.exe -m app.manage export profile-edit.json
# Editar profile-edit.json en un editor de texto y guardar como UTF-8.
.\.venv\Scripts\python.exe -m app.manage import profile-edit.json
```

El importador valida el documento antes de modificar la base y guarda el perfil completo en una transacción. Importar reemplaza el perfil completo: conservar todos los campos del archivo exportado. Un JSON inválido no se guarda. Para restaurar, importar la copia de seguridad.

También puede editarse `profiles.content` con un cliente SQL respetando el esquema de `app/schemas.py`; se recomienda el importador para evitar datos inválidos. Cambiar el JSON de `content/` por sí solo no cambia una base ya inicializada.

Esta primera versión permite administrar el contenido desde la terminal con acceso a la base. No incluye un panel web de edición ni endpoints públicos de escritura. Un panel posterior necesitará autenticación y autorización.

## Estructura y crecimiento

```text
app/main.py          Aplicación, ciclo de vida y cabeceras HTTP
app/routes.py        Página, API de perfil y estado
app/schemas.py       Validación del contenido
app/database.py      Persistencia y carga inicial
app/manage.py        Importación y exportación administrativa
content/profile.json Contenido inicial basado en el CV de julio de 2026
templates/           HTML generado en servidor
static/              Estilos e icono
tests/               Pruebas con una base temporal independiente
```

El perfil es un documento JSON validado dentro de una tabla SQL, apropiado para un único perfil en esta primera etapa. Para nuevas secciones, agregar routers, esquemas y tablas propios. Incorporar migraciones versionadas, por ejemplo Alembic, antes de modificar el esquema de una base productiva. `create_all` solo crea tablas ausentes; no migra tablas existentes.

La interfaz funciona sin JavaScript, sin fuentes remotas ni rastreadores. Incluye navegación por anclas, responsabilidades desplegables con teclado, diseño adaptable, enlace para saltar al contenido y preferencia de movimiento reducido. Las fechas y cargos se conservaron; los textos se resumieron para lectura web. No se inventaron métricas ni continuidad laboral posterior a julio de 2026. El teléfono del CV no se incorporó a esta versión pública.

## Comprobar

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Las pruebas cubren la lectura del perfil, cambios SQL visibles al recargar, conservación de ediciones, escape de HTML, validación de enlaces y ausencia de escritura pública o exposición de la base.

## Repositorio y despliegue

Repositorio del proyecto: [mcordero1/mcordero1.github.io](https://github.com/mcordero1/mcordero1.github.io). La publicación del código y el despliegue de la aplicación son pasos independientes. El alojamiento de la aplicación todavía está pendiente de elección y configuración.

GitHub aloja el código. GitHub Pages es estático y no ejecuta este servidor Python. Este proyecto está preparado para un servidor Python convencional; Render es una opción. Cloudflare Workers admite FastAPI, pero esta aplicación requiere adaptar la persistencia y el acceso a archivos a su entorno antes de desplegar allí.

Para un servidor convencional:

1. Crear PostgreSQL persistente y configurar `DATABASE_URL` como variable secreta del alojamiento. Se admiten URLs `postgresql://`, `postgres://` y `postgresql+psycopg://`.
2. Instalar `requirements.txt` y ejecutar `python -m app.manage init` una vez antes de iniciar los procesos web. No lanzar varios procesos inicializadores simultáneamente contra una base vacía.
3. Ejecutar `python -m uvicorn app.main:app --host 0.0.0.0 --port <puerto del proveedor>` detrás del HTTPS gestionado por el proveedor.
4. Configurar comprobación de estado en `/health`, copias de seguridad y revisión de costos/retención del servicio elegido.
5. Revisar el contenido público antes de subirlo. No subir `.env`, contraseñas, bases locales o copias de seguridad. `.gitignore` los excluye.

SQLite local no debe usarse en un disco efímero de alojamiento: se perderían las ediciones al reemplazar la instancia. PostgreSQL está contemplado por el adaptador, pero la ejecución con un servidor PostgreSQL real todavía debe verificarse durante el despliegue.

Fuentes consultadas el 29 de septiembre de 2026:

- [GitHub Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)
- [FastAPI en Cloudflare Workers](https://developers.cloudflare.com/workers/languages/python/packages/fastapi/)
- [FastAPI en Render](https://render.com/docs/deploy-fastapi)

Referencias visuales de contexto: sitios de tecnología financiera como [Stripe](https://stripe.com/industries/fintech). La implementación y la composición de este perfil son propias.
