# Publicación gratuita con Render y Neon

Esta configuración usa Render **Free** para FastAPI y Neon **Free** para PostgreSQL. No crea servicios de pago ni una base en Render. GitHub conserva el código. La URL pública se obtiene de Render al finalizar el despliegue.

## Límites que hay que conocer

Condiciones consultadas el 29 de septiembre de 2026; los proveedores pueden modificarlas:

- Render Free suspende la aplicación después de 15 minutos sin tráfico. La siguiente visita puede esperar aproximadamente un minuto. Incluye 750 horas de instancia por espacio de trabajo al mes, compartidas por sus servicios gratuitos. También aplica límites de transferencia, compilaciones y tráfico saliente.
- Neon Free incluye cuotas de cómputo y almacenamiento. Su documentación actual indica 100 CU-horas de cómputo al mes y 0,5 GB de almacenamiento por proyecto. El uso de este perfil debería ser pequeño, pero revisar el consumo en la consola.
- Elegir siempre los planes **Free**, sin contratar extras ni subir de plan. Si una pantalla requiere pago o tarjeta para continuar, detener la configuración y revisar la alternativa antes de aceptar. No comprar un dominio: usar el subdominio gratuito de Render.
- No crear una base PostgreSQL gratuita en Render: vence a los 30 días. La base de esta configuración se aloja en Neon.
- No instalar servicios que hagan peticiones periódicas para evitar la suspensión. La comprobación de salud de Render usa `/health/live`, que no consulta la base. `/health` comprueba la conexión bajo demanda.

## 1. Crear PostgreSQL en Neon

1. Crear o iniciar sesión en https://console.neon.tech/.
2. Elegir el plan **Free** y crear un proyecto llamado `perfil-profesional`.
3. Elegir una región cercana a Virginia (US East), donde está configurado Render. Usar PostgreSQL 17 o 18.
4. Abrir **Connect** y copiar la cadena de conexión PostgreSQL. Conservar `sslmode=require` y los demás parámetros TLS que Neon incluya. Usar la base y rama de producción elegidas.
5. Esa cadena contiene una contraseña: pegarla solo en la variable secreta `DATABASE_URL` de Render. No publicarla en GitHub, capturas, mensajes ni archivos del repositorio.

## 2. Crear el servicio en Render

1. Iniciar sesión en https://dashboard.render.com/ y conectar GitHub, con acceso a `mcordero1/mcordero1.github.io`.
2. Elegir **New → Blueprint**, seleccionar ese repositorio y la rama `main`.
3. Render leerá `render.yaml`. Verificar que aparezca **un Web Service Free** y ninguna base de datos ni servicio de pago.
4. Completar `DATABASE_URL` con la cadena de Neon en el campo secreto solicitado.
5. Aplicar el Blueprint. Al iniciar, la aplicación crea la tabla `profiles` y carga el perfil inicial si aún no existe. Usar una sola instancia.
6. Esperar el estado **Live** y abrir la URL `.onrender.com` que muestra el servicio. Este es el enlace para compartir el perfil.

Si se configura manualmente como **Web Service**, usar:

| Campo | Valor |
| --- | --- |
| Plan | Free |
| Runtime | Python |
| Branch | main |
| Region | Virginia |
| Build command | `pip install -r requirements.txt` |
| Start command | `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health check path | `/health/live` |
| Environment | `DATABASE_URL` con la conexión privada de Neon |

`.python-version` selecciona la última versión correctiva de Python 3.12. El arranque en Render falla si falta PostgreSQL o TLS, para evitar guardar por error en SQLite efímero. Los secretos no aparecen en el Blueprint.

## 3. Verificar la publicación

- Abrir la portada y revisar nombre, experiencia, navegación y estilos en escritorio y celular.
- Abrir `/health` una vez: debe devolver `{"status":"ok"}` y confirmar conexión a PostgreSQL.
- Abrir `/api/v1/profile` y verificar que coincida con el perfil mostrado.
- Hacer una edición de prueba en PostgreSQL, recargar la portada y verificar el cambio. Restaurar el valor original.
- Reiniciar o volver a desplegar y verificar que el contenido editado se conserva.
- No anunciar la web como publicada hasta completar estos pasos. Las pruebas locales no prueban una conexión PostgreSQL remota.

## Actualizar la información publicada

La tabla es `profiles`, la fila del perfil tiene `id = 1` y `content` almacena el documento JSON completo. Dos caminos:

**Importador validado (recomendado):** usar los comandos de exportación/importación del README, configurando `DATABASE_URL` en la sesión local para que apunte a Neon. Exportar primero una copia de seguridad. Esto permite validar el contenido antes de escribir. No usar la SQLite local esperando que se sincronice: son bases independientes.

**SQL Editor de Neon:** se pueden hacer cambios puntuales sin instalar aplicaciones. Por ejemplo, este comando cambia el cargo del perfil. Reemplazar únicamente el texto entre comillas y respetar el resto:

```sql
UPDATE profiles
SET content = jsonb_set(
    content::jsonb,
    '{role}',
    to_jsonb('Product Owner'::text)
  )::json,
  updated_at = CURRENT_TIMESTAMP
WHERE id = 1;
```

Este cambio aparece en la web al recargar y permanece tras futuros despliegues. SQL directo no aplica la validación del importador; no borrar campos obligatorios ni cambiar tipos. Para editar experiencias o listas completas conviene el importador. Un panel privado con formularios todavía no está implementado.

## Fuentes

- https://render.com/docs/free
- https://render.com/docs/blueprint-spec
- https://render.com/docs/python-version
- https://neon.com/blog/building-patterns-unlocked-by-scale-to-zero
- https://neon.com/pricing
