# Aparición gradual al navegar

Rama de prueba: `feature/scroll-reveal`, creada desde la versión publicada.

Los textos, títulos y bloques aparecen con una transición de 760 ms y un
desplazamiento de 24 px. El disparador se adelanta un 12% del alto de pantalla,
sin demora programada. Los bloques fuera de pantalla se preparan antes de su
entrada, evitando que primero aparezcan y luego bajen de opacidad.
El efecto se repite al regresar
desde arriba o abajo. No se anima el navbar ni el calendario de Calendly.
El contenido inicialmente visible se muestra directamente para conservar
la posición al abrir un enlace o cambiar de idioma.

La inicialización no espera la carga de Calendly. La implementación respeta
`prefers-reduced-motion`. No oculta contenido mediante
CSS: si JavaScript no está disponible, el perfil sigue siendo completamente
legible. Las animaciones se cancelan al enfocar un control o imprimir.

## Probar

Desde la carpeta del proyecto, con el entorno Python activo:

```powershell
python -m scripts.build_static
python -m http.server 8003 --bind 127.0.0.1 --directory docs
```

Abrir http://127.0.0.1:8003/ y navegar lentamente por Experiencia, Habilidades
y Formación. Bajar y volver a subir para comparar. Revisar también inglés,
claro/oscuro, celular y la opción de reducir animaciones del dispositivo.

## Deshacer

La propuesta está separada de `main`. Volver a `main` y regenerar la vista
estática recupera la web publicada. Si posteriormente se integra, se puede
revertir el commit de esta mejora. No requiere modificar la cuenta de Calendly.
