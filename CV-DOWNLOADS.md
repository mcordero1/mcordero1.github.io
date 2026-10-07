# Descargas de CV

La sección Perfil ofrece un botón que despliega CV (PDF) y CV - ATS (Word). Ambos archivos están en español y son copias locales de los originales privados de Drive.

## Actualización

Reemplazar los archivos en `downloads/` conservando los nombres y ejecutar `python -m scripts.build_static`. La publicación usa las copias generadas en `docs/downloads/`. No usar enlaces ni credenciales de Drive en la web.

## Prueba local

Desde la carpeta del proyecto, ejecutar `python -m http.server 8003 --bind 127.0.0.1 --directory docs` y abrir `http://127.0.0.1:8003/#perfil`.

Verificar que Descargar CV abre y cierra las opciones, CV descarga el PDF y CV - ATS descarga el Word. Revisar también inglés, modos claro/oscuro y móvil. Los enlaces tienen el atributo nativo `download`; el navegador puede mostrar su aviso habitual de descarga.

## Rollback

La funcionalidad está aislada en un commit de la rama `feature/cv-downloads`. Puede desestimarse sin modificar main. Si ya se integra, revertir ese commit y regenerar la web estática.
