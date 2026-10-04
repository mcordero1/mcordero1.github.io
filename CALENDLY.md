# Entrevistas en desarrollo

Rama: `feature/calendly-interviews`, creada desde `main` en `4c57f34`.
La sección Contacto contiene el widget oficial de Calendly y un enlace alternativo.
Los textos del sitio están en español e inglés. El widget conserva el idioma,
los colores y las reglas configurados en Calendly; su paleta permanece clara
para mantener la legibilidad en ambos modos del sitio con el plan Free.

## Vista previa de la versión para GitHub Pages

Desde la carpeta del proyecto, con el entorno Python activado:

```powershell
python -m scripts.build_static
python -m http.server 8003 --bind 127.0.0.1 --directory docs
```

Abrir http://127.0.0.1:8003/#agendar-entrevista.
La alternativa FastAPI es `python -m uvicorn app.main:app --port 8002`.
La vista estática reproduce el contenido publicado; FastAPI puede leer datos
anteriores de la base local de la primera versión.

## Configuración necesaria en Calendly

El sitio usa https://calendly.com/corderotenreyromarcos/30min.
El 3 de octubre de 2026 se verificó públicamente duración de una hora,
zona horaria Buenos Aires, fines de semana deshabilitados y último inicio
a las 17:00. La ubicación figura como Phone call y el formulario pide teléfono;
no contiene una pregunta obligatoria de empresa. No se creó ninguna reserva.

En Scheduling, editar ese evento:

1. Mantener duración de 60 minutos y configurar Location como Google Meet.
2. Availability: lunes a viernes de 09:00 a 18:00, zona America/Argentina/Buenos_Aires.
3. Booking page options: incrementos de 60 minutos para ofrecer comienzos a horas enteras.
4. Permitir reservas del mismo día con aviso mínimo de 0 horas. Los comienzos
   pasados no deben poder reservarse. A partir de las 18:00 no quedan horarios
   de ese día; con duración de una hora el último inicio posible es 17:00.
5. Invitee form: nombre y email obligatorios, agregar pregunta de texto
   obligatoria Nombre Empresa. Quitar preguntas adicionales que no se necesiten.
6. Calendar connections: verificar el calendario Google que se consulta para
   conflictos y el calendario destino. Mantener bloqueados los eventos Ocupado.
7. Notifications: Calendar invitation para que Google Calendar envíe la
   invitación y sus actualizaciones. Mantener el asunto estándar.
8. Bloquear todos los feriados nacionales argentinos dentro del rango de
   fechas que se permita reservar, mediante Date-specific hours sin horarios.
   Renovar estos bloqueos al ampliar el rango/año. Como alternativa, agregar
   eventos de día completo marcados Ocupado al calendario que Calendly consulta.
   Suscribirse a un calendario de feriados que figure Libre no garantiza bloqueo.

Argentina no aparece en la lista de países con bloqueo automático de feriados
de Calendly. Consultar fechas oficiales, incluyendo traslados, en
https://www.argentina.gob.ar/feriados. No asumir fechas fijas para los trasladables.

Documentación oficial:
- https://calendly.com/help/how-to-edit-holidays-within-calendly
- https://calendly.com/help/how-to-customize-your-event-types
- https://calendly.com/help/calendly-scheduling-notifications
- https://developer.calendly.com/api-docs/overview/embedding/getting-started

## Validación y rollback

Comprobar móvil y escritorio, español/inglés, claro/oscuro, un feriado bloqueado,
conflictos con reuniones existentes, formulario obligatorio y Google Meet.
Enviar una reserva de prueba sólo con autorización explícita: genera un evento
real y notificaciones. La integración visual no comprueba por sí sola el envío.

`main` conserva la versión publicada. Para descartar esta propuesta basta con
volver a `main`; no borrar carpetas ni sobrescribir cambios de Kiro. Si se decide
integrarla en producción más adelante, revertir su commit con `git revert`
permite deshacer los cambios del sitio. Los ajustes en la cuenta de Calendly
deben revertirse por separado.
