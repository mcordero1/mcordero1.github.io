# Publicación del primer release en GitHub Pages

- **URL pública:** https://mcordero1.github.io/
- **Repositorio:** `mcordero1/mcordero1.github.io`
- **Rama:** `main`
- **Carpeta pública:** `/docs`
- **HTTPS:** activado
- **Base de datos y backend:** no se usan en este release.

## Publicación

En GitHub: **Settings → Pages → Build and deployment**. Seleccionar **Deploy from a branch**, rama `main`, carpeta `/docs` y guardar.

`docs/index.html` es la portada; `docs/static/` contiene sus recursos. `.nojekyll` evita procesar el sitio con Jekyll. GitHub Pages ejecuta la publicación tras los cambios en la rama configurada. Revisar el resultado de `pages build and deployment` en **Actions** antes de dar por publicado un cambio.

Para modificar contenido o diseño, seguir los comandos del README y regenerar `docs/` antes del push. El generador no se ejecuta automáticamente en GitHub: se sube el HTML ya generado.

## Verificación

1. Confirmar que el despliegue corresponde al último commit de `main`.
2. Abrir la URL pública mediante HTTPS y comprobar el perfil.
3. Verificar que `static/style.css` y `static/favicon.svg` respondan correctamente.
4. Revisar navegación, responsabilidades desplegables y enlaces de contacto en escritorio y celular.

GitHub Pages está disponible sin costo en repositorios públicos con GitHub Free y está sujeto a sus límites de uso. No hace falta contratar dominio ni mantener una computadora encendida. Esta versión no tiene el arranque en frío de un servidor Render Free.

La configuración anterior de Render fue retirada. No se crearon servicios ni bases de datos en Render o Neon durante la preparación de este proyecto.

Documentación: https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site


## Entrega bilingüe en revisión

La rama `feature/profile-preferences` genera español en `/` e inglés en `/en/`, con cambio de apariencia local. Probar ambos idiomas y temas antes de integrarla en main. Portfolio Health permanece en su rama independiente; no se incluye en esta entrega.
