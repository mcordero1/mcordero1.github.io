# Aparición gradual al navegar

Rama de prueba: `feature/scroll-reveal`, creada desde la versión publicada.

Los textos, títulos y bloques aparecen con una transición de 620 ms y un
desplazamiento de 18 px al entrar en pantalla. El efecto se repite al regresar
desde arriba o abajo. No se anima el navbar ni el calendario de Calendly.
El contenido inicialmente visible se muestra directamente para conservar
la posición al abrir un enlace o cambiar de idioma.

La implementación respeta `prefers-reduced-motion`. No oculta contenido mediante
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
