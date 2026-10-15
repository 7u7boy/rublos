# Dólares a rublos — ayuda para decidir cuándo enviar dinero

Página web (se abre desde el celular) que muestra el cambio oficial USD→RUB del Banco Central de Rusia,
un semáforo (enviar hoy / mitad y mitad / esperar), probabilidades de subir o bajar (mañana, 1 semana, 1 mes),
gráfico, calculadora y comparador de formas de envío.

Importante: el cambio es casi imposible de predecir. La app lo dice y muestra una prueba con el pasado.

## Probar en tu computadora
    pip install -r requirements.txt
    python -m flask --app app run
Abre http://localhost:5000 (necesita internet para bajar los datos de cbr.ru).

## Publicar en Railway (servicio nuevo, separado del bot)
1. Sube esta carpeta a un repositorio de GitHub (puede ser uno nuevo).
2. En Railway: New Project → Deploy from GitHub repo → elige ese repositorio.
3. Railway usa el `Procfile` solo. En Settings → Networking → Generate Domain.
4. Abre el enlace en el celular de tu mamá → menú del navegador → «Agregar a la pantalla de inicio».

No necesita base de datos ni variables de entorno.
Opcionales: `FX_CACHE_FILE` (ruta del caché), `FX_URL_DINAMICA`, `FX_URL_DIARIO`, `FX_URL_ARCHIVO` (otras fuentes).

## Pruebas
    python -m unittest discover tests

## Qué revisar tras publicar
- Que el dato diga «Cambio oficial del <fecha de hoy o último día hábil>».
- En «Cómo se calcula esto» → «Prueba con el pasado»: con datos reales decide si la regla vale la pena.
- El cambio oficial no es el que dará el servicio de envío: usa «Comparar formas de enviar» con los números reales de cada uno.
