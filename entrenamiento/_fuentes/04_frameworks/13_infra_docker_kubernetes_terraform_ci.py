"""Infraestructura: Docker, Kubernetes, Helm, Terraform, GitHub Actions / GitLab CI.

30 filas. Reparto aproximado: Docker 8 · Kubernetes 9 · Helm 2 · Terraform 5 · CI 5 ·
estrategias de despliegue 1. Nginx como proxy inverso, TLS, observabilidad y 12-factor
van integrados en las filas de Docker y Kubernetes. Sigue entrenamiento/GUIA_DE_ESTILO.md.
"""

SISTEMA = (
    "Eres un asistente experto en programación, análisis y razonamiento. Respondes en el "
    "idioma del usuario (español por defecto), con precisión y sin relleno, y verificas tu "
    "trabajo antes de responder."
)

ROWS = [
    # 1) Docker: multi-stage, capas y .dockerignore (España, usuario trae Dockerfile)
    {
        "messages": [
            {
                "role": "user",
                "content": """Mi imagen de una API en Node/TypeScript pesa 1,4 GB y tarda un siglo en subir al registro. Dockerfile:

```dockerfile
FROM node:22
WORKDIR /app
COPY . .
RUN npm install
RUN npm run build
CMD ["node", "dist/server.js"]
```

¿Cómo la adelgazo sin liarme mucho?""",
            },
            {
                "role": "assistant",
                "content": r"""Tres problemas, cada uno con su kilo de más: la base `node:22` completa (Debian con compiladores, cerca de 1 GB), las `devDependencies` y el código fuente dentro de la imagen final, y un `COPY . .` antes del `npm install` que invalida la caché con cada cambio de código. Con un *multi-stage build* la imagen final lleva solo el runtime, el `dist/` y las dependencias de producción.

```dockerfile
# syntax=docker/dockerfile:1

# ---- etapa 1: dependencias y compilación ----
FROM node:22-bookworm-slim AS build
WORKDIR /app

# Solo los manifiestos primero: esta capa se cachea mientras no cambien las dependencias
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci

COPY tsconfig.json ./
COPY src ./src
RUN npm run build

# Deja en node_modules solo lo de producción
RUN npm prune --omit=dev

# ---- etapa 2: imagen final ----
FROM node:22-bookworm-slim AS runtime
ENV NODE_ENV=production
WORKDIR /app

COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/dist ./dist
COPY package.json ./

USER node
EXPOSE 3000
CMD ["node", "dist/server.js"]
```

Y un `.dockerignore` al lado, que es la mitad del ahorro y de la velocidad:

```
node_modules
dist
.git
.env*
*.md
coverage
```

Sin él, `COPY . .` mete tu `node_modules` local (con binarios compilados para tu sistema, que luego pisan a los de la imagen) y el `.git` entero en el contexto de build.

Por qué cada decisión:

- **`-slim` en vez de la imagen completa**: unos 200 MB frente a 1 GB. Lleva Node y poco más; si alguna dependencia compila código nativo (`sharp`, `bcrypt`), lo hace en la etapa `build`, y el binario ya compilado viaja a la final.
- **`npm ci` y no `npm install`**: instala exactamente lo que dice `package-lock.json`, falla si no cuadra, y es más rápido. El `--mount=type=cache` conserva la caché de npm entre builds sin dejarla dentro de la capa.
- **Orden de los `COPY`**: manifiestos → instalación → código. Docker reutiliza una capa solo si todo lo anterior es idéntico; con el código al final, un cambio en `src/` reconstruye solo `npm run build`, no la instalación.
- **`npm prune --omit=dev`** después del build quita TypeScript, ESLint y compañía del `node_modules` que se copia.
- **`USER node`**: la imagen oficial ya trae ese usuario. Correr como root dentro del contenedor es un riesgo innecesario y algunos clústeres directamente lo prohíben.

Resultado esperable: de 1,4 GB a 250-300 MB. Compruébalo con `docker image ls` y mira qué capas pesan con `docker history <imagen>`; si una capa sigue siendo grande, ahí está lo siguiente que recortar.

Lo que no hice a propósito: pasar a `alpine`. Ahorra otros 100 MB, pero usa musl en vez de glibc y hay paquetes nativos que no compilan o se comportan distinto. Es un cambio aparte, con su propia prueba, no parte de este arreglo.""",
            },
        ]
    },
    # 2) Docker: Dockerfile de producción para Python con uv, usuario no root y healthcheck (SISTEMA)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Dame un Dockerfile de producción para una API FastAPI gestionada con uv, que no corra como root y con healthcheck. Lo que encuentro por ahí es todo con pip y root.",
            },
            {
                "role": "assistant",
                "content": r"""```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# ---- dependencias ----
FROM base AS deps
COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv   # fija la versión que uses
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# ---- imagen final ----
FROM base AS runtime
RUN groupadd --system app && useradd --system --gid app --home /app app
WORKDIR /app
COPY --from=deps /app/.venv /app/.venv
COPY --chown=app:app src ./src
ENV PATH="/app/.venv/bin:$PATH"
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)" || exit 1
CMD ["uvicorn", "src.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Qué hay detrás de cada línea:

- **`uv sync --frozen --no-dev`** instala exactamente lo del `uv.lock` (falla si el lock no cuadra con `pyproject.toml`) y sin dependencias de desarrollo. `--no-install-project` deja fuera tu propio paquete en esa capa, así que la capa de dependencias solo cambia cuando cambia el lock, no con cada commit. El `--mount=type=cache` reutiliza las descargas entre builds.
- **El `.venv` viaja copiado** a la imagen final; `uv` ya no está en ella. Menos superficie, y `PATH` apunta al entorno virtual para que `uvicorn` se resuelva sin activar nada.
- **`useradd --system`** crea un usuario sin contraseña ni shell de login. `--chown` en el `COPY` evita un `RUN chown -R` que duplicaría la capa. Como `app` no puede escribir en `/app`, si tu aplicación necesita escribir (subidas, caché), dale un directorio explícito con `RUN mkdir /app/data && chown app:app /app/data`, o mejor un volumen.
- **`PYTHONUNBUFFERED=1`** manda los logs al instante a stdout; sin ello se quedan en el búfer, `docker logs` va con retraso y se pierden líneas al matar el contenedor. `UV_COMPILE_BYTECODE=1` precompila los `.pyc` para que el arranque no lo haga en cada réplica.
- **`HEALTHCHECK` sin `curl`**: `python:slim` no lo trae, y añadirlo son 10 MB y un paquete más que parchear. `urllib` ya está. `--start-period` da margen al arranque antes de contar fallos.
- **`CMD` en forma exec** (lista JSON): uvicorn es PID 1 y recibe el `SIGTERM` de `docker stop` directamente. En forma shell (`CMD uvicorn ...`) el proceso 1 sería `sh`, que no reenvía señales, y el contenedor tardaría 10 s en morir a golpe de `SIGKILL`.

Dos cosas que faltan y son decisión tuya:

- El endpoint `/health` debe existir y ser barato: no consultar la base de datos. Eso es *readiness*, otro nivel.
- Los workers: un proceso de `uvicorn` por contenedor y escalar con réplicas es más simple que `gunicorn` con workers de uvicorn dentro del contenedor. Si solo tienes un host y quieres usar todos los núcleos, entonces sí, `--workers N`.

Verificación: `docker build -t api . && docker run -d --rm -p 8000:8000 api`; `docker inspect --format '{{.State.Health.Status}}' <id>` debe pasar de `starting` a `healthy` en menos de un minuto, y `docker exec <id> id` debe mostrar un uid distinto de 0.""",
            },
        ]
    },
    # 3) Docker: caché de capas en CI (inglés, intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": "Our Docker build takes 9 minutes on every GitHub Actions run even though nothing in the dependencies changed. Locally the second build takes 20 seconds. What's different in CI?",
            },
            {
                "role": "assistant",
                "content": """Locally the layer cache lives on your machine and survives between builds. In CI every job starts on a fresh runner with an empty Docker cache, so every layer is rebuilt. You have to export the cache somewhere and import it on the next run.

**1. Use `docker/build-push-action` with the GitHub Actions cache backend.**

```yaml
name: build
on: [push]
jobs:
  image:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: ghcr.io/${{ github.repository }}:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

`type=gha` stores layers in the Actions cache (10 GB per repository, least-recently-used eviction). `mode=max` exports every intermediate layer, including the ones from earlier stages of a multi-stage build; the default `min` keeps only the final image's layers, which means your `npm ci` or `pip install` stage would still be rebuilt every time.

If the cache gets evicted too often or you build from several repositories, point `cache-to` at the registry instead: `type=registry,ref=ghcr.io/org/app:buildcache,mode=max`. It is slower to pull than the gha cache but has no size limit and is shared by anything that can reach the registry.

**2. Make the Dockerfile cache-friendly.** The cache only helps if the expensive layers come *before* the layers that change on every commit:

```dockerfile
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci       # cached until the lockfile changes
COPY . .                                             # changes every commit; everything after is rebuilt
RUN npm run build
```

With `COPY . .` first, the `npm ci` layer is invalidated by any file change and the cache is useless no matter where you store it.

**3. Check what actually invalidates.** Run the build with `--progress=plain` once in CI and look for `CACHED` next to each step. The first non-cached step tells you which layer broke the chain. Common surprises: a `COPY` that includes a file with a timestamp or build number, a missing `.dockerignore` so `.git` is part of the context (its content changes every commit), or an `ARG` placed before the dependency install (changing its value invalidates everything after it).

Expected result: a run with no dependency changes drops to 1-2 minutes, most of it pulling the cache and pushing the final layers. A cold run after a lockfile change stays at 9 minutes, which is correct.

One thing to confirm: `docker/setup-buildx-action` is required. The classic builder does not support `cache-from`/`cache-to` or `--mount=type=cache`; without buildx the options are silently ignored and the build looks fine but never caches.""",
            },
        ]
    },
    # 4) Docker Compose para desarrollo + Nginx como proxy inverso con TLS (multiturno)
    {
        "messages": [
            {
                "role": "user",
                "content": "Para desarrollo quiero levantar mi API (Python), Postgres y Redis con docker compose. Me pasa que la API arranca antes que Postgres y revienta al conectar, y tengo que hacer `docker compose up` dos veces.",
            },
            {
                "role": "assistant",
                "content": """`depends_on` a secas solo ordena el **arranque** de los contenedores; no espera a que Postgres esté listo para aceptar conexiones. Necesitas `condition: service_healthy` con un `healthcheck` en la base de datos, y que tu API reintente de todas formas.

```yaml
# compose.yaml
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://app:app@db:5432/app
      REDIS_URL: redis://cache:6379/0
    depends_on:
      db:
        condition: service_healthy
      cache:
        condition: service_healthy
    develop:
      watch:
        - action: sync
          path: ./src
          target: /app/src
        - action: rebuild
          path: pyproject.toml

  db:
    image: postgres:17
    environment:
      POSTGRES_USER: app
      POSTGRES_PASSWORD: app
      POSTGRES_DB: app
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app -d app"]
      interval: 2s
      timeout: 2s
      retries: 15

  cache:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 2s
      timeout: 2s
      retries: 15

volumes:
  pgdata:
```

Lo que importa:

- **`healthcheck` + `condition: service_healthy`**: `pg_isready` responde solo cuando Postgres acepta conexiones. Compose no arranca `api` hasta que `db` y `cache` han pasado el chequeo. El primer `up` ya funciona.
- **Nombres de servicio como hosts**: `db` y `cache` resuelven por DNS dentro de la red que Compose crea. Nada de `localhost` desde la API: `localhost` dentro del contenedor es el propio contenedor.
- **El volumen con nombre** (`pgdata`) conserva los datos entre `down` y `up`. `docker compose down -v` los borra; úsalo cuando quieras empezar de cero.
- **`develop.watch`** (Compose 2.22+): `docker compose watch` sincroniza `src/` al contenedor al guardar y reconstruye si cambia `pyproject.toml`. Sustituye al *bind mount* de todo el proyecto, que arrastra tu `.venv` local dentro del contenedor.
- **La API debe reintentar igualmente.** `service_healthy` cubre el arranque, no un reinicio de Postgres a mitad de sesión. Un bucle de 10 intentos con espera creciente al abrir el pool, en el arranque de la aplicación, son cinco líneas y te ahorra el mismo problema en producción.

Comprobación: `docker compose down -v && docker compose up` debe dejar los tres servicios en marcha sin que `api` reinicie, y `docker compose ps` muestra `healthy` en `db` y `cache`.""",
            },
            {
                "role": "user",
                "content": "Genial. Para el entorno de staging quiero meter Nginx delante de la API, con HTTPS. ¿Cómo lo añado aquí?",
            },
            {
                "role": "assistant",
                "content": """Añade un servicio `proxy` que publique 80 y 443 y hable con `api` por la red interna, y deja de publicar el 8000 al host. Para HTTPS, lo más simple y realista en staging es un certificado de Let's Encrypt; Caddy o Traefik lo renuevan solos, y con Nginx lo gestiona `certbot` aparte. Te dejo Nginx porque es lo que pediste, con el certificado montado desde un volumen.

```yaml
services:
  api:
    build: .
    expose:
      - "8000"                   # visible solo en la red interna; ya no "ports"
    environment:
      FORWARDED_ALLOW_IPS: "*"   # uvicorn confía en las cabeceras X-Forwarded-* del proxy
    depends_on:
      db:
        condition: service_healthy

  proxy:
    image: nginx:1.27-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - ./certs:/etc/nginx/certs:ro
    depends_on:
      - api
```

```nginx
# nginx.conf
upstream api {
    server api:8000;
    keepalive 32;
}

server {
    listen 80;
    server_name staging.example.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    http2 on;
    server_name staging.example.com;

    ssl_certificate     /etc/nginx/certs/fullchain.pem;
    ssl_certificate_key /etc/nginx/certs/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    client_max_body_size 20m;

    location / {
        proxy_pass http://api;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }
}
```

Decisiones:

- **`expose` en vez de `ports`** para la API: el único punto de entrada es el proxy. Si dejas el 8000 publicado, cualquiera se salta el TLS.
- **Cabeceras `X-Forwarded-*`** y `FORWARDED_ALLOW_IPS` en uvicorn: sin ellas tu aplicación cree que todas las peticiones vienen de la IP del proxy por HTTP, y las redirecciones y las cookies `Secure` se rompen.
- **`proxy_http_version 1.1` + `Connection ""`** reutiliza conexiones con el upstream (`keepalive 32`); sin esto Nginx abre una conexión nueva por petición.
- **Solo TLS 1.2 y 1.3**: lo anterior está roto y ningún cliente actual lo necesita.
- `client_max_body_size` por defecto es 1 MB; si subes archivos, el 413 saldrá de Nginx, no de tu API, y te costará encontrarlo.

El certificado: con dominio público, `certbot certonly --standalone -d staging.example.com` una vez en el host (o el contenedor `certbot/certbot` con un volumen compartido) y un cron de renovación que termine con `docker compose exec proxy nginx -s reload`. Para un entorno sin dominio, `mkcert` genera uno local de confianza para tu máquina.

Comprobación: `curl -I http://staging.example.com` devuelve `301` a HTTPS; `curl -sI https://staging.example.com/health` devuelve `200`; y en los logs de la API el cliente ya no es la IP interna del proxy sino la real.""",
            },
        ]
    },
    # 5) Docker: permisos en bind mounts y usuario no root (rioplatense, intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": "Monto una carpeta con `-v $(pwd)/data:/app/data` y el contenedor (que corre con `USER app`) me tira `PermissionError: [Errno 13] Permission denied: '/app/data/salida.csv'`. Si saco el `USER` anda, pero me dijeron que correr como root está mal. ¿Cómo se resuelve bien?",
            },
            {
                "role": "assistant",
                "content": """Los permisos de un *bind mount* son los del host, no los de la imagen. Tu carpeta `data` pertenece a tu usuario (UID 1000, por ejemplo) y el `app` de la imagen tiene otro UID (999 si lo creó `useradd --system`). Dentro del contenedor, `app` ve una carpeta de otro dueño y no puede escribir. Volver a root lo «arregla» porque root escribe donde sea, que es justo el motivo por el que no querés root.

Tenés tres soluciones correctas, según el caso:

**1. Alinear el UID del contenedor con el tuyo (desarrollo).** Creá el usuario de la imagen con un UID configurable y pasale el tuyo al construir:

```dockerfile
ARG UID=1000
ARG GID=1000
RUN groupadd --gid $GID app && useradd --uid $UID --gid $GID --create-home app
USER app
```

```bash
docker build --build-arg UID=$(id -u) --build-arg GID=$(id -g) -t miapp .
```

Así `app` dentro del contenedor y vos en el host son el mismo UID, y los archivos que escribe te pertenecen, sin el clásico «`salida.csv` es de root y no lo puedo borrar».

**2. `--user` en tiempo de ejecución**, sin tocar la imagen:

```bash
docker run --rm --user "$(id -u):$(id -g)" -v "$(pwd)/data:/app/data" miapp
```

Funciona siempre que la aplicación no necesite escribir en `$HOME` ni en rutas de la imagen que sean de `app`; ese UID arbitrario no tiene entrada en `/etc/passwd`, así que algunas herramientas se quejan de «usuario desconocido». Para un script que lee y escribe en `/app/data`, sobra.

**3. Volumen con nombre en vez de bind mount (producción).** Un volumen gestionado por Docker se inicializa con el dueño que tenga la ruta en la imagen:

```dockerfile
RUN mkdir -p /app/data && chown app:app /app/data
USER app
VOLUME /app/data
```

```bash
docker run -v datos:/app/data miapp     # el volumen "datos" nace con dueño app
```

En producción no querés depender del UID del host; el volumen con nombre desacopla las dos cosas.

Lo que **no** conviene: `chmod -R 777 data` en el host. Funciona, y deja la carpeta escribible por cualquier proceso de la máquina.

Para ver qué pasa antes de elegir: `docker run --rm miapp id` muestra el UID con el que corre, y `docker run --rm -v "$(pwd)/data:/app/data" miapp ls -ln /app/data` muestra el UID numérico del dueño de la carpeta montada. Si no coinciden, es exactamente este problema.""",
            },
        ]
    },
    # 6) Docker: el contenedor sale al instante (principiante, system variante)
    {
        "messages": [
            {"role": "system", "content": "Explica para alguien que está empezando con Docker, sin asumir conocimientos avanzados de Linux."},
            {
                "role": "user",
                "content": "Hice `docker run -d mi-imagen` y el contenedor aparece como `Exited (0)` al segundo. Si entro con `docker run -it mi-imagen bash` sí funciona. No entiendo qué pasa.",
            },
            {
                "role": "assistant",
                "content": """Un contenedor vive exactamente lo que dure su proceso principal (el que indica `CMD` o `ENTRYPOINT`). Si ese proceso termina, el contenedor termina. `Exited (0)` significa «terminó sin error»: tu proceso principal hizo su trabajo, o no tenía nada que hacer, y salió. No es un fallo de Docker; es que no hay nada que mantenga el contenedor vivo.

Con `docker run -it mi-imagen bash` funciona porque sustituyes el `CMD` por `bash` interactivo, que no termina hasta que escribes `exit`.

**Cómo ver qué pasó:**

```bash
docker logs <id>                                                            # lo que imprimió antes de salir
docker inspect --format '{{.Config.Entrypoint}} {{.Config.Cmd}}' mi-imagen  # qué proceso arranca
```

**Las tres causas habituales:**

1. **El `CMD` no es un proceso de larga duración.** Por ejemplo `CMD ["python", "script.py"]` donde `script.py` hace algo y termina. Si quieres un servicio, el proceso tiene que quedarse escuchando (`uvicorn`, `node server.js`, `nginx -g "daemon off;"`).
2. **El proceso se va a segundo plano.** Un `CMD ["nginx"]` sin `daemon off`, o un `service x start`: el programa se convierte en *daemon*, el proceso que Docker vigila termina, y Docker da el contenedor por acabado. En Docker, el servidor siempre en primer plano.
3. **No hay `CMD`**, o lo pisa un `docker run` con un comando que termina. Un `Dockerfile` sin `CMD` hereda el de la imagen base; en `python:3.12` es `python3`, que sin terminal interactiva se cierra al instante con código 0.

**Códigos de salida que te dicen la causa:**

| Código | Significa |
|---|---|
| 0 | El proceso terminó normalmente (tu caso) |
| 1 | El proceso falló: mira `docker logs` |
| 126 / 127 | El comando no es ejecutable / no existe (ruta mal, falta el binario) |
| 137 | Lo mató el sistema con `SIGKILL`, casi siempre por falta de memoria |
| 143 | Recibió `SIGTERM` (`docker stop`) y terminó limpiamente |

**Arreglo típico** para una imagen de un servicio web en Python:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

`--host 0.0.0.0` también importa: si el servidor escucha solo en `127.0.0.1`, el contenedor vive pero nada desde fuera puede conectar, que es el siguiente error que verás.

Comprobación: `docker run -d -p 8000:8000 mi-imagen` y después `docker ps` debe mostrar el contenedor como `Up`; si vuelve a salir, `docker logs <id>` tiene la respuesta.""",
            },
        ]
    },
    # 7) Docker: secretos en imágenes y configuración por entorno, 12-factor (avanzado)
    {
        "messages": [
            {
                "role": "user",
                "content": "Un escaneo nos avisó de que la imagen de producción contiene una clave de API. La pasamos como `ARG API_KEY` en el build porque hace falta para descargar un paquete privado. Ya la rotamos, pero ¿cómo evitamos que vuelva a pasar?",
            },
            {
                "role": "assistant",
                "content": r"""Un `ARG` no es secreto: queda grabado en los metadatos de cada capa que lo usa, y `docker history --no-trunc imagen` lo muestra en texto plano a cualquiera que pueda hacer `docker pull`. Rotarla fue lo correcto; ahora toca separar dos cosas que hoy están mezcladas: **secretos de build** (solo durante `docker build`) y **configuración de runtime** (la aplicación en marcha).

**1. Secretos de build: `--mount=type=secret`.** El archivo se monta solo durante ese `RUN` y no deja rastro en ninguna capa:

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN --mount=type=secret,id=pip_token \
    PIP_INDEX_URL="https://__token__:$(cat /run/secrets/pip_token)@pypi.empresa.internal/simple" \
    pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "-m", "app"]
```

```bash
docker build --secret id=pip_token,env=PIP_TOKEN -t app .        # desde una variable de entorno
docker build --secret id=pip_token,src=./token.txt -t app .      # o desde un archivo
```

En GitHub Actions, `docker/build-push-action` acepta `secrets: pip_token=${{ secrets.PIP_TOKEN }}`. Para repositorios git privados, `--mount=type=ssh` hace lo mismo con el agente SSH.

**2. Configuración de runtime: nunca dentro de la imagen.** La misma imagen debe servir en staging y producción; lo que cambia entra desde fuera, al arrancar (es el principio de «configuración en el entorno» de los 12 factores):

```bash
docker run --env-file .env.production app          # desarrollo o un solo host
```

En Kubernetes, un `Secret` montado como variable o archivo; en ECS o Cloud Run, el gestor de secretos del proveedor inyectado al arrancar. Y la aplicación lee `os.environ["API_KEY"]` y falla al arrancar si falta, en vez de tener un valor por defecto.

**3. Cerrar las otras puertas por las que entran secretos a una imagen:**

- `.dockerignore` con `.env*`, `*.pem`, `*.key`, `.git`, `.aws`, `.npmrc`. Un `COPY . .` sin esto mete tu `.env` local en la imagen aunque nadie lo haya pedido.
- `RUN echo "$TOKEN" > ~/.npmrc && npm ci && rm ~/.npmrc` **no sirve**: el archivo queda en la capa de ese `RUN` aunque lo borres en el mismo comando. Las capas son inmutables; «borrar» solo añade una marca de borrado encima.
- Las variables `ENV` del Dockerfile se ven con `docker inspect`. Son para configuración pública (`NODE_ENV`, `PORT`), no para credenciales.

**4. Que el escáner corra antes de publicar, no después.** Un paso en CI con `gitleaks` sobre el repositorio y `trivy image --scanners secret app:ci` sobre la imagen construida, bloqueando el push al registro si encuentra algo. Lo que detectó el escaneo en producción lo habría detectado en el PR.

Verificación de que la imagen nueva está limpia: `docker history --no-trunc app | grep -i token` no debe devolver nada, y `docker run --rm app env` no debe mostrar la clave.""",
            },
        ]
    },
    # 8) Docker: imagen base para Go y multi-arquitectura (intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": "¿`alpine`, `slim` o `distroless` para la imagen final de un servicio en Go? Y nos piden también que corra en los Mac con chip M de los desarrolladores.",
            },
            {
                "role": "assistant",
                "content": r"""Para Go, **distroless o `scratch`**: el binario es estático y no necesita ni shell ni libc. Y para los Mac, una imagen *multi-arquitectura* construida con `buildx`, no una imagen por plataforma.

| Base | Tamaño | Qué incluye | Cuándo |
|---|---|---|---|
| `scratch` | 0 MB | Nada: ni shell, ni certificados CA, ni zona horaria | Binario estático que no hace HTTPS ni usa `time.LoadLocation` |
| `gcr.io/distroless/static-debian12` | ~2 MB | Certificados CA, `/etc/passwd` con `nonroot`, tzdata | Servicio Go normal. **El valor por defecto** |
| `alpine` | ~8 MB | musl, shell `sh`, `apk` | Cuando necesitas depurar dentro o instalar una herramienta |
| `debian:bookworm-slim` | ~75 MB | glibc, shell, `apt` | Binarios con cgo o dependencias nativas |

Distroless gana porque la superficie de ataque es mínima (no hay shell que ejecutar en un *exploit* ni gestor de paquetes que parchear) y porque trae lo que a `scratch` le falta y descubres en producción: sin certificados CA, la primera llamada HTTPS falla con `x509: certificate signed by unknown authority`.

```dockerfile
# syntax=docker/dockerfile:1
FROM --platform=$BUILDPLATFORM golang:1.23 AS build
ARG TARGETOS TARGETARCH
WORKDIR /src
COPY go.mod go.sum ./
RUN --mount=type=cache,target=/go/pkg/mod go mod download
COPY . .
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 GOOS=$TARGETOS GOARCH=$TARGETARCH go build -trimpath -ldflags="-s -w" -o /out/server ./cmd/server

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /out/server /server
USER nonroot:nonroot
EXPOSE 8080
ENTRYPOINT ["/server"]
```

```bash
docker buildx create --use --name multi                 # una vez
docker buildx build --platform linux/amd64,linux/arm64 -t registry/app:1.4.0 --push .
```

Cómo funciona lo multi-arquitectura: `--platform=$BUILDPLATFORM` hace que la etapa de compilación corra siempre nativa (sin emulación, que es 5-10 veces más lenta), y Go compila cruzado con `GOOS` y `GOARCH`, que `buildx` rellena por plataforma destino. El resultado es un **manifest list**: una sola etiqueta `registry/app:1.4.0` detrás de la cual hay una imagen por arquitectura, y cada máquina descarga la suya. Los desarrolladores con chip M hacen `docker pull` y reciben la `arm64` sin saberlo.

Dos detalles:

- `CGO_ENABLED=0` es lo que garantiza el binario estático. Si alguna dependencia exige cgo (SQLite, por ejemplo), pasa a `distroless/base-debian12` (con glibc) o a `debian-slim`.
- `:nonroot` ya arranca con UID 65532; no hace falta crear usuario. Para depurar un contenedor sin shell, `kubectl debug` o `docker debug` adjuntan un contenedor efímero con herramientas en vez de meterlas en la imagen.

Comprobación: `docker buildx imagetools inspect registry/app:1.4.0` lista `linux/amd64` y `linux/arm64`, y `docker run --rm registry/app:1.4.0` en un Mac arranca sin el aviso `WARNING: The requested image's platform (linux/amd64) does not match the detected host platform`.""",
            },
        ]
    },
    # 9) Kubernetes: CrashLoopBackOff con método (SISTEMA, multiturno, usuario trae salida)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": """Desplegué y el pod no levanta:

```
NAME                     READY   STATUS             RESTARTS      AGE
api-7d9f8c6b4-x2k9p      0/1     CrashLoopBackOff   6 (45s ago)   8m
```

`kubectl logs` no me muestra nada útil, solo una línea de arranque. ¿Por dónde empiezo?""",
            },
            {
                "role": "assistant",
                "content": """`CrashLoopBackOff` no es un error en sí: es Kubernetes diciendo «el contenedor termina una y otra vez y estoy esperando cada vez más entre reintentos». La causa está en *por qué* termina, y hay tres comandos que la acotan en un minuto.

**1. Los logs del intento anterior, no del actual.** `kubectl logs` muestra el contenedor que corre ahora, que acaba de arrancar y solo ha impreso la línea de inicio. El que falló es el anterior:

```bash
kubectl logs api-7d9f8c6b4-x2k9p --previous
```

Si ahí hay una traza (`KeyError`, `connection refused`, `Address already in use`), ya tienes la causa.

**2. El motivo y el código de salida que registró Kubernetes:**

```bash
kubectl describe pod api-7d9f8c6b4-x2k9p
```

Mira `Last State: Terminated`, con `Reason` y `Exit Code`, y la sección `Events` del final. Cada combinación apunta a un sitio:

| `Reason` / `Exit Code` | Qué pasó |
|---|---|
| `Error` / 1 | La aplicación lanzó una excepción al arrancar: configuración, dependencia, migración |
| `Error` / 126 o 127 | El comando del contenedor no es ejecutable o no existe (ruta mal en `command`/`args`) |
| `OOMKilled` / 137 | Superó `resources.limits.memory` |
| `Completed` / 0 | El proceso terminó bien: la imagen no es un servicio, o `command` lo sobrescribe |
| `Error` / 143 con `Unhealthy` en eventos | La *liveness probe* falló y kubelet lo mató |

**3. Si los logs están vacíos, los eventos del namespace** ordenados por tiempo muestran lo que los logs no:

```bash
kubectl get events --sort-by=.lastTimestamp -n <namespace> | tail -20
```

Ahí aparecen `Liveness probe failed`, `Error: secret "api-secrets" not found` o `Back-off restarting failed container`.

**Las causas, por frecuencia**, cuando el log solo muestra la línea de arranque:

1. **Liveness probe demasiado impaciente.** La aplicación tarda 20 s en arrancar, la probe empieza a los 5 s con 3 fallos permitidos, y kubelet la mata antes de que termine de arrancar. Se ve en `Events` como `Liveness probe failed` seguido de `Killing`.
2. **Falta una variable, un ConfigMap o un Secret** referenciado en el manifiesto. El evento lo dice con nombre.
3. **No puede conectar con una dependencia** (base de datos, cola) y el código decide salir. Confirma desde el mismo namespace: `kubectl run tmp --rm -it --restart=Never --image=busybox -- nc -zv db 5432`.
4. **Memoria**: `OOMKilled` en `Last State`; con un límite demasiado bajo, el proceso muere antes de escribir nada.

Para inspeccionar sin que el contenedor se reinicie: `kubectl debug -it api-7d9f8c6b4-x2k9p --image=busybox --target=api -- sh` adjunta un contenedor efímero junto al que falla. Si necesitas el entorno exacto de la aplicación, edita el Deployment temporalmente con `command: ["sleep", "infinity"]`, entra con `kubectl exec` y lanza el proceso a mano para ver el error completo.

Pega la salida de `--previous` y la parte de `Last State` y `Events` del `describe` y te digo cuál de los cuatro es.""",
            },
            {
                "role": "user",
                "content": """`--previous` sigue vacío. Del describe:

```
    Last State:     Terminated
      Reason:       Error
      Exit Code:    143
Events:
  Warning  Unhealthy  2m (x12 over 7m)  kubelet  Liveness probe failed: Get "http://10.244.1.17:8000/health": dial tcp 10.244.1.17:8000: connect: connection refused
  Normal   Killing    2m (x4 over 7m)   kubelet  Container api failed liveness probe, will be restarted
```

La liveness es:

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
```""",
            },
            {
                "role": "assistant",
                "content": """Es la causa 1: la aplicación todavía no ha abierto el puerto cuando la *liveness probe* empieza a llamar, falla tres veces seguidas (5 s de espera inicial + 3 × 5 s = 20 s) y kubelet la mata con `SIGTERM`; de ahí el código 143 y el log vacío, porque nunca llegó a arrancar del todo. En cada reinicio se repite, y el *backoff* alarga la espera.

`connection refused` (y no un 500 ni un timeout) confirma que no hay nadie escuchando en el 8000 en ese momento: es arranque lento, no un `/health` roto.

El arreglo es separar «está arrancando» de «está vivo» con una `startupProbe`, que existe para esto:

```yaml
startupProbe:                 # durante el arranque: hasta 30 × 5 s = 150 s de margen
  httpGet:
    path: /health
    port: 8000
  periodSeconds: 5
  failureThreshold: 30
livenessProbe:                # solo empieza a contar cuando la startupProbe ha pasado
  httpGet:
    path: /health
    port: 8000
  periodSeconds: 10
  failureThreshold: 3
readinessProbe:               # decide si recibe tráfico; no reinicia nada
  httpGet:
    path: /ready
    port: 8000
  periodSeconds: 5
```

Mientras la `startupProbe` no pase, las otras dos están desactivadas. Una vez pasa, la liveness vigila con criterio de «proceso colgado», no de «proceso arrancando».

Dos cosas más que conviene corregir ya que estás ahí:

- **Mide cuánto tarda en arrancar de verdad.** `kubectl logs -f` sobre un pod nuevo, desde `Started` hasta la línea de «listening on». Si son 40 s, pregúntate por qué: cargar un modelo, migraciones en el arranque, compilar algo. La probe tapa el síntoma; el arranque lento sigue costando en cada escalado y cada despliegue.
- **`/health` debe ser barato y local**: 200 si el proceso responde. Si consulta la base de datos, una caída de la base de datos hará que la liveness mate todos los pods, y reiniciarlos no va a arreglar la base de datos. Las dependencias se comprueban en `/ready`, que solo quita el pod del Service.

Verificación: tras aplicar, `kubectl rollout status deployment/api` debe terminar con `successfully rolled out`, `kubectl get pod` debe mostrar `1/1 Running` con `RESTARTS 0`, y en `describe` ya no debe aparecer `Unhealthy`.""",
            },
        ]
    },
    # 10) Kubernetes: ImagePullBackOff y registro privado (México, intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": "Ahorita el pod se quedó en `ImagePullBackOff` y `describe` dice `Failed to pull image \"registry.empresa.com/api:1.8.2\": ... unauthorized: authentication required`. Desde mi laptop sí puedo hacer `docker pull` de esa imagen. ¿Qué le falta al clúster?",
            },
            {
                "role": "assistant",
                "content": r"""Al clúster le faltan **tus credenciales**. En tu laptop, `docker pull` usa el `docker login` que hiciste una vez; en Kubernetes, kubelet no tiene ese login y el registro privado responde `unauthorized`. Hay que darle un `Secret` de tipo `docker-registry` y decirle al pod que lo use.

**1. Crear el secreto** en el namespace del pod (los secretos no cruzan namespaces):

```bash
kubectl create secret docker-registry regcred \
  --docker-server=registry.empresa.com \
  --docker-username=ci-pull \
  --docker-password="$REGISTRY_TOKEN" \
  -n produccion
```

Usa un token de solo lectura creado para el clúster, no tu usuario personal: cuando cambies tu contraseña, los pods no deben caerse.

**2. Referenciarlo en el pod**, o mejor en la `ServiceAccount`, para no repetirlo en cada Deployment:

```yaml
# opción A: en el Deployment
spec:
  template:
    spec:
      imagePullSecrets:
        - name: regcred
      containers:
        - name: api
          image: registry.empresa.com/api:1.8.2
```

```bash
# opción B: en la ServiceAccount (todos los pods del namespace que la usen)
kubectl patch serviceaccount default -n produccion -p '{"imagePullSecrets": [{"name": "regcred"}]}'
```

Tras el cambio no hace falta borrar el pod: kubelet reintenta con *backoff* y en un par de minutos lo toma. Si tienes prisa, `kubectl rollout restart deployment/api -n produccion`.

**Las otras causas de `ImagePullBackOff`**, por si el mensaje cambia:

| Mensaje en `describe` | Causa |
|---|---|
| `unauthorized` / `denied` | Credenciales ausentes o sin permiso sobre ese repositorio (tu caso) |
| `manifest unknown` / `not found` | La etiqueta no existe: error de dedo, o el pipeline de CI no llegó a publicar `1.8.2` |
| `no match for platform in manifest` | La imagen es `amd64` y el nodo `arm64`, o al revés: construye multi-arquitectura |
| `dial tcp: i/o timeout` | Los nodos no alcanzan el registro: firewall, DNS o un registro interno sin ruta |
| `too many requests` | Límite de descargas de Docker Hub; usa un *mirror* o autentica también para Hub |

**Un detalle de `imagePullPolicy`**: con una etiqueta fija como `1.8.2`, el valor por defecto es `IfNotPresent`, así que un nodo que ya tenga esa imagen no vuelve al registro. Con `:latest` el valor por defecto es `Always`, lo que explica despliegues que «no cambian nada» (la etiqueta es la misma) o que cambian solos. En producción, etiqueta inmutable por versión o, mejor, el digest `@sha256:...`.

Comprobación de que el secreto es válido, sin esperar al pod:

```bash
kubectl get secret regcred -n produccion -o jsonpath='{.data.\.dockerconfigjson}' | base64 -d
kubectl run pull-test --rm -it --restart=Never -n produccion \
  --image=registry.empresa.com/api:1.8.2 \
  --overrides='{"spec":{"imagePullSecrets":[{"name":"regcred"}]}}' -- true
```

Si el segundo comando termina sin `ErrImagePull`, el clúster ya puede descargar la imagen.""",
            },
        ]
    },
    # 11) Kubernetes: OOMKilled, requests/limits y CPU throttling (multiturno, avanzado)
    {
        "messages": [
            {
                "role": "user",
                "content": "Nuestros pods de Java se reinician cada pocas horas con `OOMKilled` aunque el límite es 2Gi y la JVM tiene `-Xmx1g`. ¿Cómo puede pasarse de 2 GB si el heap es 1?",
            },
            {
                "role": "assistant",
                "content": """Porque `-Xmx` limita solo el **heap**, y la JVM usa bastante memoria fuera de él: metaspace, caché de código JIT, pilas de hilos (1 MB por hilo por defecto), búferes directos de NIO y la memoria nativa del recolector. Con `-Xmx1g` es normal ver 1.5-1.8 GB de RSS, y con 200 hilos y algo de NIO, superar 2 GiB. El límite de Kubernetes es sobre el **cgroup entero** (RSS de todos los procesos del contenedor), no sobre el heap, y cuando se cruza, el kernel mata el proceso: código 137, `OOMKilled`.

**1. Mide en vez de suponer.** Antes de tocar números:

```bash
kubectl top pod -l app=api --containers             # uso actual (necesita metrics-server)
kubectl describe pod <pod> | grep -A3 "Last State"  # confirma OOMKilled y cuándo
```

Y dentro de la JVM, `-XX:NativeMemoryTracking=summary` más `jcmd <pid> VM.native_memory summary` desglosa heap, metaspace, hilos y código. Ahí ves qué parte crece.

**2. Deja que la JVM lea el límite del contenedor** en vez de fijar `-Xmx` a mano:

```yaml
containers:
  - name: api
    image: registry/api:2.3.0
    env:
      - name: JAVA_TOOL_OPTIONS
        value: "-XX:MaxRAMPercentage=65 -XX:+ExitOnOutOfMemoryError -Xss512k"
    resources:
      requests:
        cpu: "500m"
        memory: "2Gi"
      limits:
        memory: "2Gi"
```

- `MaxRAMPercentage=65` fija el heap al 65 % del límite del contenedor (unos 1.3 GiB de 2 GiB) y deja el resto para lo que vive fuera del heap. Si subes el límite, el heap sube solo. Cualquier JVM desde la 11 lee el cgroup, y desde la 17 también cgroups v2.
- `ExitOnOutOfMemoryError`: si de verdad se agota el heap, mejor que el proceso muera y Kubernetes lo reinicie que quedarse zombi contestando `OutOfMemoryError` a cada petición.
- `-Xss512k` reduce la pila por hilo si tienes cientos de hilos (servidores clásicos de Tomcat); con pocos hilos no cambia nada.

**3. `requests` igual a `limits` en memoria.** La memoria no se comprime: si un nodo se queda sin ella, Kubernetes desaloja primero los pods que usan más de lo que pidieron. Con `requests == limits` el pod es *Guaranteed* en memoria y es el último en ser desalojado. Pedir 512Mi y limitar a 2Gi es apostar a que el nodo tendrá memoria libre cuando la necesites.

**4. Si sigue creciendo hasta el límite con el tiempo**, es una fuga o una caché sin tope, no configuración: un *heap dump* al morir (`-XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=/tmp`) con un `emptyDir` montado en `/tmp` te dice qué objetos se acumulan.

Comprobación: tras el cambio, `kubectl top pod` debe estabilizarse por debajo del límite durante un día completo y `kubectl get pod` debe mostrar `RESTARTS 0`. Si la memoria se estabiliza en 1.9 GiB, vas justo: sube el límite a 3Gi y mantén el porcentaje.""",
            },
            {
                "role": "user",
                "content": "Lo del heap tiene sentido. Y de CPU, ¿ponemos también límite? Un compañero dice que los límites de CPU nos están ralentizando las peticiones.",
            },
            {
                "role": "assistant",
                "content": """Tu compañero tiene razón en la mayoría de los casos: los límites de CPU **no** funcionan como los de memoria, y en una API de latencia conviene poner `requests` y no `limits`.

Cómo funciona el límite de CPU: es una cuota por periodo de 100 ms gestionada por CFS. Con `limits.cpu: "1"` el contenedor puede usar 100 ms de CPU por cada 100 ms de reloj, **sumando todos los hilos**. Una JVM con 8 hilos de GC y 50 de peticiones puede consumir esos 100 ms en 20 ms de reloj, y durante los 80 ms restantes queda **congelada** aunque el nodo esté al 30 %. Eso es *throttling*, y aparece como picos de latencia (p99) sin que el uso medio de CPU parezca alto.

Para verlo, la métrica es `container_cpu_cfs_throttled_periods_total` frente a `container_cpu_cfs_periods_total` en Prometheus; si el 10 % o más de los periodos están limitados, es exactamente lo que describe tu compañero.

Recomendación práctica:

```yaml
resources:
  requests:
    cpu: "500m"       # lo que el scheduler reserva y tu peso relativo cuando hay contención
    memory: "2Gi"
  limits:
    memory: "2Gi"     # memoria sí; CPU, no
```

- **`requests.cpu` sigue siendo obligatorio**: es lo que usa el scheduler para colocar el pod y lo que fija la proporción de CPU que recibes cuando el nodo está saturado (CFS reparte por `requests`, así que un pod con 500m no «roba» a uno con 2000m).
- **Sin `limits.cpu`** el pod puede usar CPU ociosa del nodo, que es lo que quieres en una API: absorber ráfagas sin pagar latencia.
- **Sí pon límite de CPU** en cargas batch que no deban afectar a vecinas, en clústeres multi-inquilino con `LimitRange` o `ResourceQuota` que lo exijan, o si necesitas QoS *Guaranteed* completa (eso requiere `limits == requests` en CPU y memoria).

Un matiz con Java: desde JDK 17 la JVM calcula `availableProcessors()` a partir de la cuota, y sin límite ve todos los núcleos del nodo y dimensiona hilos de GC y pools como si tuviera 32 CPU. Fíjalo tú con `-XX:ActiveProcessorCount=2`, acorde a la `request`, para que los pools no se sobredimensionen.

Verificación: quita el límite en un solo Deployment, compara el p99 de latencia y la métrica de throttling antes y después durante un día. Si el p99 baja y el uso total de CPU del nodo no se dispara, aplícalo al resto.""",
            },
        ]
    },
    # 12) Kubernetes: Deployment + Service + Ingress con TLS (system variante, avanzado)
    {
        "messages": [
            {"role": "system", "content": "Eres un SRE senior. Responde en español con manifiestos completos y las razones de cada campo."},
            {
                "role": "user",
                "content": "Necesito desplegar una API HTTP (imagen `registry/api:2.0.1`, puerto 8080) en Kubernetes con 3 réplicas, accesible en `api.example.com` con HTTPS. Tenemos ingress-nginx y cert-manager instalados. ¿Me das los manifiestos completos?",
            },
            {
                "role": "assistant",
                "content": """Tres objetos más un `ClusterIssuer` si todavía no existe. Los pongo en un solo archivo separado por `---`; se aplica con `kubectl apply -f api.yaml -n api`.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api
  labels:
    app.kubernetes.io/name: api
spec:
  replicas: 3
  revisionHistoryLimit: 5
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0          # nunca por debajo de 3 pods listos durante un despliegue
  selector:
    matchLabels:
      app.kubernetes.io/name: api
  template:
    metadata:
      labels:
        app.kubernetes.io/name: api
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 10001
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: api
          image: registry/api:2.0.1
          ports:
            - name: http
              containerPort: 8080
          env:
            - name: PORT
              value: "8080"
          resources:
            requests:
              cpu: 250m
              memory: 256Mi
            limits:
              memory: 256Mi
          startupProbe:
            httpGet: { path: /health, port: http }
            periodSeconds: 5
            failureThreshold: 24
          readinessProbe:
            httpGet: { path: /ready, port: http }
            periodSeconds: 5
          livenessProbe:
            httpGet: { path: /health, port: http }
            periodSeconds: 10
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop: ["ALL"]
      terminationGracePeriodSeconds: 30
      topologySpreadConstraints:
        - maxSkew: 1
          topologyKey: kubernetes.io/hostname
          whenUnsatisfiable: ScheduleAnyway
          labelSelector:
            matchLabels:
              app.kubernetes.io/name: api
---
apiVersion: v1
kind: Service
metadata:
  name: api
spec:
  type: ClusterIP
  selector:
    app.kubernetes.io/name: api
  ports:
    - name: http
      port: 80
      targetPort: http
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/proxy-body-size: 10m
spec:
  ingressClassName: nginx
  tls:
    - hosts: [api.example.com]
      secretName: api-tls          # cert-manager lo crea y lo renueva
  rules:
    - host: api.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: api
                port:
                  name: http
---
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: ops@example.com
    privateKeySecretRef:
      name: letsencrypt-prod-account
    solvers:
      - http01:
          ingress:
            ingressClassName: nginx
```

Las razones, por bloque:

**Deployment.**
- `maxUnavailable: 0` con `maxSurge: 1`: cada pod nuevo tiene que estar `Ready` antes de retirar uno viejo. Es lo que hace que un despliegue roto no reduzca capacidad; con `maxUnavailable: 25%` (el valor por defecto) perderías un pod de tres durante el rollout.
- Tres probes con papeles distintos: `startupProbe` cubre el arranque (hasta 2 minutos), `readinessProbe` decide si el pod recibe tráfico del Service, `livenessProbe` reinicia solo si el proceso se cuelga. `/ready` puede comprobar dependencias; `/health` no debe.
- `requests` sin `limits` de CPU para no pagar *throttling* en una API de latencia; memoria con `requests == limits` para que el pod sea el último en ser desalojado.
- `securityContext` restrictivo: sin root, sin escalada, sistema de archivos de solo lectura. Si tu aplicación escribe en `/tmp`, añade un `emptyDir` montado ahí; es mejor descubrirlo ahora que abrir todo el sistema de archivos.
- `topologySpreadConstraints` reparte las tres réplicas entre nodos. Sin ello, el scheduler puede ponerlas en el mismo nodo y un solo fallo de hardware te tumba las tres.
- Las etiquetas `app.kubernetes.io/name` son la convención recomendada; el `selector` del Deployment es inmutable una vez creado, así que decídelo bien ahora.

**Service.** `ClusterIP` porque nadie fuera del clúster habla con él directamente; el Ingress sí. `targetPort: http` por nombre, no por número: si el contenedor cambia de puerto, cambias un sitio.

**Ingress.** `ingressClassName` en vez de la anotación antigua `kubernetes.io/ingress.class` (deprecada). El bloque `tls` con `secretName` es la señal para cert-manager: con la anotación `cluster-issuer`, crea un `Certificate`, resuelve el reto HTTP-01 publicando temporalmente una ruta `/.well-known/acme-challenge/` por este mismo Ingress, y guarda el certificado en `api-tls`. Lo renueva 30 días antes de caducar.

**ClusterIssuer.** Uno por clúster, reutilizable por todos los namespaces. Para probar sin agotar los límites de emisión de Let's Encrypt, crea un segundo issuer apuntando a `https://acme-staging-v02.api.letsencrypt.org/directory` y úsalo primero.

Requisitos que no están en los manifiestos: el DNS de `api.example.com` apuntando a la IP externa del Service de ingress-nginx (`kubectl get svc -n ingress-nginx`), y que el puerto 80 sea alcanzable desde Internet para el reto HTTP-01.

Verificación en orden: `kubectl rollout status deployment/api -n api` → `kubectl get certificate -n api` debe pasar a `READY True` en uno o dos minutos (si no, `kubectl describe challenge -n api` dice por qué) → `curl -sI https://api.example.com/health` devuelve `200` con un certificado válido.""",
            },
        ]
    },
    # 13) Kubernetes: ConfigMap y Secret, cambios que no llegan al pod (usuario en inglés pide español)
    {
        "messages": [
            {
                "role": "user",
                "content": "I changed a value in my ConfigMap and ran `kubectl apply`, but the pods still use the old value. Do I have to delete them? (Please answer in Spanish, I'm practicing.)",
            },
            {
                "role": "assistant",
                "content": """Depende de **cómo** consume el pod el ConfigMap, y en tu caso casi seguro lo consume como variables de entorno, que se leen una sola vez al arrancar el contenedor y no se actualizan nunca. No hace falta borrar pods a mano, pero sí provocar un reinicio ordenado.

**Dos formas de consumir un ConfigMap, dos comportamientos:**

| Forma | Se actualiza al cambiar el ConfigMap |
|---|---|
| `env` / `envFrom` | Nunca. El proceso ya arrancó con el valor viejo |
| Volumen montado (`volumes` + `volumeMounts`) | Sí, kubelet lo refresca en un minuto aproximadamente, **salvo** si usas `subPath` |

Y aunque el archivo cambie en el volumen, tu aplicación tiene que releerlo; la mayoría solo lee la configuración al arrancar.

**La solución inmediata:** un reinicio progresivo del Deployment, que respeta `maxUnavailable` y las probes:

```bash
kubectl rollout restart deployment/api -n produccion
kubectl rollout status deployment/api -n produccion
```

**La solución permanente: que el cambio de configuración sea un despliegue.** Hay dos maneras limpias:

1. **ConfigMap versionado e inmutable.** En vez de modificar `api-config`, creas `api-config-v2` y cambias la referencia en el Deployment. Como el Deployment cambió, Kubernetes hace un rollout, y además tienes rollback gratis (`kubectl rollout undo` vuelve a `v1`):

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: api-config-v2
immutable: true          # nadie puede editarlo por accidente; para cambiar, se crea otro
data:
  LOG_LEVEL: info
  FEATURE_X: "true"
```

2. **Anotación con el hash del ConfigMap** en la plantilla del pod. Es lo que hace Helm con `checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}`; Kustomize lo hace solo con `configMapGenerator`, que añade un sufijo al nombre. Cualquier cambio en el contenido cambia la anotación, y eso dispara el rollout.

Si no usas ni Helm ni Kustomize y quieres que sea automático, el operador *Reloader* (`stakater/reloader`) vigila ConfigMaps y Secrets y reinicia los Deployments que los referencian con una anotación.

**Lo mismo aplica a los Secrets, con dos avisos más:**

- Un `Secret` es base64, **no cifrado**. Cualquiera con `get secrets` en el namespace lo lee con `kubectl get secret x -o jsonpath='{.data.PASSWORD}' | base64 -d`. Restringe ese permiso con RBAC y activa el cifrado en reposo en etcd (`EncryptionConfiguration`) si gestionas el clúster.
- No los guardes en git en claro. Las opciones habituales son *External Secrets Operator* (sincroniza desde AWS Secrets Manager, Vault, etc.) o *Sealed Secrets* (cifrados con la clave pública del clúster, se pueden commitear).

Comprobación de que el valor nuevo llegó: `kubectl exec deploy/api -- env | grep LOG_LEVEL` tras el rollout, o `kubectl exec deploy/api -- cat /etc/config/LOG_LEVEL` si es un volumen.""",
            },
        ]
    },
    # 14) Kubernetes: Service sin endpoints, 503 por el Ingress (usuario trae manifiestos, intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": """Mi Ingress devuelve `503 Service Temporarily Unavailable`, pero si hago `kubectl port-forward deploy/web 8080:8080` la app responde bien. Manifiestos:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
spec:
  replicas: 2
  selector:
    matchLabels:
      app: web
  template:
    metadata:
      labels:
        app: web
        tier: frontend
    spec:
      containers:
        - name: web
          image: registry/web:3.1.0
          ports:
            - containerPort: 8080
---
apiVersion: v1
kind: Service
metadata:
  name: web
spec:
  selector:
    app: web-frontend
  ports:
    - port: 80
      targetPort: 3000
```""",
            },
            {
                "role": "assistant",
                "content": """El 503 de ingress-nginx significa «el Service no tiene endpoints»: el Ingress encontró el Service, pero detrás no hay ningún pod. Y en tu Service hay dos errores que lo explican; el `port-forward` funciona porque se salta el Service y habla con el Deployment directamente.

**Cómo se confirma en 10 segundos**, antes de mirar el YAML:

```bash
kubectl get endpoints web
# NAME   ENDPOINTS   AGE
# web    <none>      12m      ← ningún pod seleccionado
```

(`kubectl get endpointslices -l kubernetes.io/service-name=web` es el equivalente moderno.) Si `ENDPOINTS` está vacío con pods `Running`, el `selector` del Service no coincide con las etiquetas de los pods. Es la causa más frecuente de 503 con todo «en verde».

**Error 1: el selector no casa.** El Service busca `app: web-frontend`; los pods llevan `app: web` y `tier: frontend`. Un selector es una conjunción de pares exactos, no una búsqueda parcial.

**Error 2: `targetPort: 3000`**, pero el contenedor escucha en 8080. Este no lo ves todavía porque el primero lo tapa: cuando arregles el selector, los endpoints aparecerán con `:3000` y el Ingress pasará de 503 a `502 Bad Gateway` (hay pod, pero rechaza la conexión).

Service corregido:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: web
spec:
  selector:
    app: web                 # exactamente las etiquetas de la plantilla del pod
  ports:
    - name: http
      port: 80
      targetPort: http       # por nombre: el contenedor declara su puerto como "http"
```

y en el Deployment, el puerto con nombre:

```yaml
          ports:
            - name: http
              containerPort: 8080
```

Usar el nombre en `targetPort` hace imposible el segundo error: si el contenedor cambia de puerto, solo se toca el Deployment.

**Mapa de códigos cuando entras por ingress-nginx**, para la próxima vez:

| Código | Qué falla |
|---|---|
| 404 de nginx | Ninguna regla de Ingress coincide: `host` mal, `ingressClassName` ausente, o `pathType` que no casa |
| 503 | El Service no tiene endpoints: selector, pods no `Ready` (readiness probe fallando) o `replicas: 0` |
| 502 | Hay endpoints pero la conexión falla: `targetPort` mal o la app escucha solo en `127.0.0.1` |
| 504 | La app acepta pero tarda más que `proxy-read-timeout` (60 s por defecto) |

Prueba desde dentro del clúster, que separa «Service» de «Ingress»:

```bash
kubectl run tmp --rm -it --restart=Never --image=curlimages/curl -- curl -s -o /dev/null -w "%{http_code}" http://web.default.svc/
```

Si eso devuelve 200 y el Ingress sigue fallando, el problema está en el Ingress; si falla, está en el Service o en los pods. Con los dos cambios de arriba, `kubectl get endpoints web` debe listar dos IPs con `:8080` y el 503 desaparece.""",
            },
        ]
    },
    # 15) Kubernetes: HPA sin métricas (inglés, system variante)
    {
        "messages": [
            {"role": "system", "content": "You are a Kubernetes expert. Be precise and show the exact commands."},
            {
                "role": "user",
                "content": "I created an HPA for my deployment but `kubectl get hpa` shows `TARGETS <unknown>/70%` and it never scales. What's missing?",
            },
            {
                "role": "assistant",
                "content": """`<unknown>` means the HPA controller cannot compute the current CPU utilization. Utilization is `usage / requests`, so there are exactly two things that can be missing: the usage (no metrics API) or the requests (no `resources.requests.cpu` on the pods). The HPA tells you which one:

```bash
kubectl describe hpa api
```

Look at `Conditions` and `Events`:

- `FailedGetResourceMetric ... the server could not find the requested resource (get pods.metrics.k8s.io)` → **metrics-server is not installed**. Check with `kubectl top pods`; if that fails too, install it (`kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml`; on kind or minikube you may need `--kubelet-insecure-tls`). Managed clusters (EKS, GKE, AKS) usually ship it, but EKS does not by default.
- `missing request for cpu in container api` → **no CPU request** on the pod template. Utilization as a percentage is meaningless without a denominator. Add it:

```yaml
resources:
  requests:
    cpu: 250m
    memory: 256Mi
```

- `ScalingActive False / FailedGetScale` → the `scaleTargetRef` points to the wrong name or kind.

Once both are present, `TARGETS` shows a number within about a minute.

A complete HPA with sane defaults:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 0        # react immediately to load
      policies:
        - type: Percent
          value: 100
          periodSeconds: 60                # at most double every minute
    scaleDown:
      stabilizationWindowSeconds: 300      # wait 5 min of low usage before removing pods
      policies:
        - type: Pods
          value: 1
          periodSeconds: 60
```

Things that bite after it starts working:

- **Remove `replicas` from the Deployment manifest.** If it stays at `replicas: 2` and you `kubectl apply` the Deployment again, you reset the replica count the HPA had raised, and the HPA then scales back up: a visible dip every deploy. With Helm, use `{{- if not .Values.autoscaling.enabled }} replicas: ... {{- end }}`.
- **Target 70 %, not 90 %.** Scaling takes time (metrics interval 15 s, controller loop 15 s, pod startup). The headroom is what absorbs the spike while new pods come up.
- **Memory is a poor scaling signal** for most services: it does not drop when load drops (JVM heaps, caches), so the HPA never scales down. Use CPU, or a real work metric (requests per second, queue length) through the custom metrics API; KEDA is the practical way to get those.
- `minReplicas: 2` keeps you available during a node failure or a rollout; `1` means the HPA is also your single point of failure.

Verification: generate load (`kubectl run load --rm -it --restart=Never --image=busybox -- sh -c "while true; do wget -q -O- http://api/; done"`), watch `kubectl get hpa api -w`; `TARGETS` should rise above 70 % and `REPLICAS` increase within a couple of minutes, then fall back after the 5-minute stabilization window once you stop the load.""",
            },
        ]
    },
    # 16) Kubernetes: rollback y despliegues que se frenan solos (rioplatense, intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": "Desplegamos la 2.4.0 y empezaron a saltar errores 500. ¿Cómo vuelvo atrás rápido con kubectl y cómo hago para que la próxima vez el despliegue se frene solo antes de romper todo?",
            },
            {
                "role": "assistant",
                "content": """**Volver atrás ahora:**

```bash
kubectl rollout history deployment/api -n prod          # qué revisiones hay
kubectl rollout undo deployment/api -n prod             # vuelve a la anterior
kubectl rollout status deployment/api -n prod           # espera a que termine
```

Si la anterior tampoco era buena, `--to-revision=<n>` con el número que muestra `history`. El `undo` es un rollout normal en sentido inverso: respeta `maxUnavailable` y las probes, así que no es instantáneo pero tampoco deja el servicio sin pods.

Para que `history` diga algo más que números, anotá cada despliegue: `kubectl annotate deployment/api kubernetes.io/change-cause="2.4.0: nuevo endpoint de pagos"` (o la anotación en el manifiesto). El flag `--record` está deprecado.

**Que se frene solo la próxima vez.** Kubernetes solo puede frenar un despliegue por lo que *él* ve: pods que no llegan a `Ready`. Tus 500 los veían los usuarios, no las probes. Así que hay dos capas:

*Capa 1: que el rollout no avance sin pods sanos y falle en vez de quedarse a medias.*

```yaml
spec:
  strategy:
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  minReadySeconds: 30            # un pod cuenta como listo solo tras 30 s Ready sin fallar
  progressDeadlineSeconds: 300   # si en 5 min no progresa, el rollout se marca como fallido
  template:
    spec:
      containers:
        - name: api
          readinessProbe:
            httpGet: { path: /ready, port: http }
            periodSeconds: 5
            failureThreshold: 2
```

Con esto, un pod nuevo que arranca pero se cae a los 10 s nunca llega a contar, el rollout se detiene con un pod viejo menos como máximo, y `kubectl rollout status` sale con error pasado el *deadline* (que es lo que querés en CI: que el pipeline falle). Un 500 en `/ready` también lo frena, así que hacé que `/ready` compruebe lo mínimo que la app necesita para servir (conexión a la base de datos, migraciones aplicadas).

*Capa 2: que los 500 de los usuarios también frenen el despliegue.* Eso requiere mirar métricas durante el rollout, y Kubernetes solo no lo hace. Las opciones, de menos a más automatizadas:

- **Canary manual con ingress-nginx**: un segundo Deployment `api-canary` con la 2.4.0 y un Ingress con `nginx.ingress.kubernetes.io/canary: "true"` y `canary-weight: "10"`. Mirás el ratio de 5xx en Grafana 10 minutos, y si está bien subís el peso o promovés.
- **Argo Rollouts**: sustituye el Deployment por un `Rollout` con pasos (`setWeight: 10`, `pause: 5m`, `setWeight: 50`...) y un `AnalysisTemplate` que consulta Prometheus; si el ratio de errores supera el umbral, hace rollback solo. Es la versión automatizada del punto anterior y vale la pena cuando desplegás varias veces al día.

Verificación de la capa 1 sin esperar al próximo incidente: desplegá a propósito una imagen con `/ready` devolviendo 500 en staging. Esperás ver un pod nuevo que nunca pasa a `1/1`, los dos viejos intactos, y `rollout status` fallando a los 5 minutos con `deployment "api" exceeded its progress deadline`.""",
            },
        ]
    },
    # 17) Observabilidad: Prometheus, Grafana, OpenTelemetry (intermedio/avanzado)
    {
        "messages": [
            {
                "role": "user",
                "content": "Tenemos 15 microservicios en Kubernetes y cuando algo falla nos enteramos por los usuarios. ¿Por dónde empiezo con observabilidad sin montar una plataforma gigante?",
            },
            {
                "role": "assistant",
                "content": """Empieza por métricas y alertas sobre síntomas; logs estructurados después; trazas al final. En ese orden cada paso da valor en una semana y no depende del siguiente.

**Semana 1: métricas RED por servicio y alertas sobre lo que ve el usuario.**

Instala `kube-prometheus-stack` (Helm): Prometheus, Alertmanager, Grafana y el operador, con los *dashboards* de nodos y pods ya hechos. Luego cada servicio expone `/metrics` con la librería cliente de su lenguaje y tres métricas, las RED (*Rate, Errors, Duration*):

```python
# ejemplo FastAPI con prometheus_client
from prometheus_client import Counter, Histogram

REQUESTS = Counter("http_requests_total", "Peticiones", ["service", "route", "method", "status"])
LATENCY = Histogram("http_request_duration_seconds", "Latencia", ["service", "route"],
                    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5))
```

Y le dices a Prometheus que las recoja con un `ServiceMonitor` por servicio (o uno genérico por etiqueta):

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: apps
  labels:
    release: kube-prometheus-stack     # la etiqueta que el operador busca
spec:
  namespaceSelector:
    any: true
  selector:
    matchLabels:
      metrics: "true"                   # pon esta etiqueta en el Service de cada microservicio
  endpoints:
    - port: http
      path: /metrics
      interval: 30s
```

Las alertas van sobre **síntomas**, no causas, y en términos de tasa de error y latencia, que es lo que el usuario nota:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: apps-slo
  labels:
    release: kube-prometheus-stack
spec:
  groups:
    - name: apps
      rules:
        - alert: HighErrorRate
          expr: |
            sum by (service) (rate(http_requests_total{status=~"5.."}[5m]))
              / sum by (service) (rate(http_requests_total[5m])) > 0.02
          for: 5m
          labels: { severity: page }
          annotations:
            summary: "{{ $labels.service }}: más del 2 % de errores durante 5 min"
        - alert: HighLatencyP99
          expr: |
            histogram_quantile(0.99, sum by (service, le) (rate(http_request_duration_seconds_bucket[5m]))) > 1
          for: 10m
          labels: { severity: warn }
```

Dos alertas por servicio, bien calibradas, valen más que cuarenta sobre CPU y memoria: «CPU al 80 %» no es un problema si la latencia está bien, y despierta a alguien por nada.

**Semana 2: logs estructurados.** Cada servicio escribe JSON a stdout con `timestamp`, `level`, `service`, `trace_id`, `message`; nada de archivos ni formatos propios. Un recolector (Loki con Promtail/Alloy, o el que ya tenga tu nube) los indexa por etiqueta de pod. Lo importante no es la herramienta sino que el campo `trace_id` exista, porque es lo que une un log con una traza.

**Semana 3-4: trazas con OpenTelemetry.** El SDK de OTel en cada servicio (en Python, Java y Node la instrumentación automática cubre HTTP, clientes de base de datos y colas sin tocar código), exportando al *OpenTelemetry Collector* desplegado como DaemonSet, que reenvía a Tempo o Jaeger. La ganancia real es la propagación del contexto: el `traceparent` viaja en las cabeceras entre tus 15 servicios y una petición lenta se ve como un árbol con el tiempo de cada salto.

**Lo que no haría:** instalar las tres cosas a la vez y un *service mesh* «para tener observabilidad». Métricas y alertas solas ya te quitan el «nos enteramos por los usuarios»; el resto se añade cuando las alertas te dicen *qué* falla pero no *por qué*.

Verificación del primer paso: `kubectl port-forward svc/kube-prometheus-stack-prometheus 9090` y en `/targets` todos tus servicios en `UP`; luego provoca errores en uno en staging y comprueba que `HighErrorRate` pasa a `FIRING` en Alertmanager en menos de 6 minutos.""",
            },
        ]
    },
    # 18) Helm: cuándo merece la pena y valores por entorno (España, multiturno, principiante)
    {
        "messages": [
            {
                "role": "user",
                "content": "Tenemos 8 microservicios con manifiestos YAML casi iguales copiados y pegados. ¿Helm merece la pena para esto o es matar moscas a cañonazos? Nunca lo he usado.",
            },
            {
                "role": "assistant",
                "content": """Para «8 servicios casi iguales» es justo el caso en que Helm compensa: un *chart* y ocho archivos de valores cortos sustituyen a ocho copias de 200 líneas que ya se han empezado a desincronizar. Lo que no haría es un chart por servicio.

**Cómo se ve.** Un chart es una carpeta con plantillas Go y un `values.yaml` con los valores por defecto:

```
charts/servicio/
  Chart.yaml
  values.yaml
  templates/
    deployment.yaml
    service.yaml
    ingress.yaml
    _helpers.tpl
```

```yaml
# charts/servicio/values.yaml  (valores por defecto para cualquier servicio)
image:
  repository: registry/placeholder
  tag: ""
replicaCount: 2
port: 8080
resources:
  requests: { cpu: 250m, memory: 256Mi }
  limits: { memory: 256Mi }
ingress:
  enabled: false
  host: ""
```

```yaml
# charts/servicio/templates/deployment.yaml  (fragmento)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Release.Name }}
spec:
  replicas: {{ .Values.replicaCount }}
  selector:
    matchLabels:
      app.kubernetes.io/name: {{ .Release.Name }}
  template:
    metadata:
      labels:
        app.kubernetes.io/name: {{ .Release.Name }}
    spec:
      containers:
        - name: app
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}"
          ports:
            - name: http
              containerPort: {{ .Values.port }}
          resources:
            {{- toYaml .Values.resources | nindent 12 }}
```

Y cada servicio es un archivo de 10 líneas:

```yaml
# values/pagos.yaml
image:
  repository: registry/pagos
replicaCount: 3
ingress:
  enabled: true
  host: pagos.example.com
```

```bash
helm upgrade --install pagos ./charts/servicio -f values/pagos.yaml --set image.tag=2.4.0 -n prod --atomic --wait
```

**Los comandos que vas a usar de verdad:**

- `helm template pagos ./charts/servicio -f values/pagos.yaml` renderiza los manifiestos sin tocar el clúster. Es cómo depuras una plantilla y cómo revisas en un PR qué va a cambiar.
- `helm upgrade --install` crea o actualiza, así que CI no necesita distinguir. `--atomic` deshace el despliegue si falla, `--wait` espera a que los pods estén `Ready`.
- `helm diff upgrade ...` (plugin `helm-diff`) muestra el diff contra lo desplegado antes de aplicarlo.
- `helm history pagos` y `helm rollback pagos 3` para volver a una revisión.

**La alternativa que conviene conocer: Kustomize.** Viene en `kubectl` (`kubectl apply -k`), no tiene plantillas: una base con los YAML completos y *overlays* que aplican parches. Es mejor cuando las diferencias entre servicios o entornos son pocas y puntuales, y peor cuando hay lógica (condicionales, bucles, valores calculados). Con 8 servicios y un chart común, Helm te deja la configuración de cada uno en 10 líneas; con Kustomize tendrías 8 bases casi iguales otra vez.

Lo que sería matar moscas a cañonazos: un *umbrella chart* con dependencias, hooks y subcharts para esto. Un chart plano y ocho archivos de valores es todo lo que necesitas.""",
            },
            {
                "role": "user",
                "content": "Vale. ¿Y cómo organizo los valores por entorno (dev, staging, prod) sin duplicar?",
            },
            {
                "role": "assistant",
                "content": """Con **capas de archivos de valores**: Helm acepta varios `-f` y los fusiona en orden, el último gana. Así cada capa contiene solo lo que cambia respecto a la anterior.

```
values/
  pagos.yaml           # lo que define al servicio, igual en todos los entornos
  pagos-staging.yaml   # solo las diferencias de staging
  pagos-prod.yaml      # solo las diferencias de prod
```

```yaml
# values/pagos-prod.yaml
replicaCount: 4
resources:
  requests: { cpu: 500m, memory: 512Mi }
  limits: { memory: 512Mi }
ingress:
  host: pagos.example.com
```

```bash
helm upgrade --install pagos ./charts/servicio \
  -f values/pagos.yaml \
  -f values/pagos-prod.yaml \
  --set image.tag=$IMAGE_TAG \
  -n prod --atomic --wait
```

Orden de precedencia, de menor a mayor: `values.yaml` del chart → `-f` en el orden dado → `--set`. Reglas para que no se te vaya de las manos:

- **`--set` solo para lo que inyecta CI** (la etiqueta de la imagen). Todo lo demás vive en archivos, versionado y revisable en un PR. Un `--set` olvidado en un script es configuración invisible.
- **Lo que es igual en todos los entornos no se repite**: si `port: 8080` está en `pagos.yaml`, no aparece en `pagos-prod.yaml`. Cuando necesites ver el resultado fusionado, `helm get values pagos -n prod --all`.
- **Los secretos no van en archivos de valores.** El chart referencia un `Secret` por nombre (`envFrom: secretRef: name: pagos-secrets`) y ese Secret lo crea External Secrets o Sealed Secrets, fuera de Helm.
- **Una release por servicio y entorno**, con el mismo nombre en cada namespace (`pagos` en `staging` y `pagos` en `prod`). Así `helm list -A` te enseña de un vistazo qué versión del chart y de la app hay en cada sitio.

Cuando el número de comandos `helm upgrade` crezca (8 servicios × 3 entornos), **Helmfile** declara todas las releases con sus archivos de valores en un solo `helmfile.yaml` y las aplica con `helmfile -e prod apply`, con diff incluido. Es el paso natural después de este, no antes.

Comprobación de que las capas hacen lo que crees: `helm template pagos ./charts/servicio -f values/pagos.yaml -f values/pagos-prod.yaml | grep -A2 replicas` debe mostrar 4, y con solo el primer archivo, 3.""",
            },
        ]
    },
    # 19) Helm: release atascada en pending-upgrade (usuario trae error, intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": "El pipeline falló a mitad y ahora cualquier `helm upgrade` me da `Error: UPGRADE FAILED: another operation (install/upgrade/rollback) is in progress`. ¿Cómo lo desatasco sin cargarme el release?",
            },
            {
                "role": "assistant",
                "content": """Helm guarda cada revisión de la release como un Secret en el namespace, con un estado. Cuando el proceso de `helm upgrade` muere a mitad (el runner de CI lo mató, se agotó el tiempo), la última revisión se queda en `pending-upgrade` para siempre, y Helm se niega a operar sobre una release «en curso». No hay nada corriendo; solo una marca que nadie limpió.

**1. Mira el estado:**

```bash
helm history api -n prod
# REVISION  STATUS            CHART        DESCRIPTION
# 11        superseded        api-1.3.0    Upgrade complete
# 12        deployed          api-1.3.1    Upgrade complete
# 13        pending-upgrade   api-1.4.0    Preparing upgrade
```

**2. Vuelve a la última revisión buena.** `helm rollback` sí está permitido sobre una release pendiente, y crea una revisión nueva (`14`) con el contenido de la `12`:

```bash
helm rollback api 12 -n prod --wait
helm history api -n prod      # la 13 pasa a "superseded"; la 14 es "deployed"
```

A partir de ahí `helm upgrade` vuelve a funcionar. Los recursos del clúster no se tocan más de lo que diga el diff entre la 13 y la 12; si la 13 llegó a aplicar parte de los manifiestos, el rollback los devuelve a la 12 con un rollout normal.

**Si no hay ninguna revisión `deployed`** (la release nueva se quedó en `pending-install` y nunca llegó a desplegarse), el rollback no tiene a dónde volver. Entonces, o `helm uninstall api -n prod` (borra los recursos, aceptable si es una instalación nueva) o, para no tocar recursos, borra solo el Secret de la revisión atascada:

```bash
kubectl get secret -n prod -l owner=helm,name=api            # sh.helm.release.v1.api.v13
kubectl delete secret sh.helm.release.v1.api.v13 -n prod
```

Helm deja de ver la revisión pendiente y la siguiente operación parte de la última revisión que exista. Es cirugía: hazlo solo cuando `rollback` no sea posible.

**3. Que no vuelva a pasar:**

- `helm upgrade --install --atomic --timeout 10m`: `--atomic` hace rollback automático si el despliegue falla dentro del plazo, y deja la release en `deployed` (la anterior) en vez de `failed` o `pending`.
- Que CI no mate el proceso antes que Helm: el `timeout-minutes` del job tiene que ser mayor que el `--timeout` de Helm.
- Una sola ejecución a la vez por release: en GitHub Actions, `concurrency: { group: deploy-api-prod, cancel-in-progress: false }`. Dos `helm upgrade` simultáneos sobre la misma release son la otra forma de llegar a este error.

Verificación: `helm status api -n prod` muestra `STATUS: deployed`, y un `helm upgrade --install api ./chart -n prod --dry-run` termina sin el error.""",
            },
        ]
    },
    # 20) Terraform: estado remoto en S3 (SISTEMA, principiante/intermedio)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Estamos empezando con Terraform en AWS y guardamos el `terraform.tfstate` en el repo. Un compañero dice que es una barbaridad. ¿Cómo se hace bien y por qué?",
            },
            {
                "role": "assistant",
                "content": """Tu compañero tiene razón, por tres motivos concretos:

1. **El estado contiene secretos en texto plano**: contraseñas de RDS, claves de acceso que un recurso devuelva como atributo, tokens. Todo el que lea el repositorio los tiene, y el historial de git los conserva aunque borres el archivo.
2. **Dos personas aplicando a la vez corrompen el estado.** Cada una parte de un `tfstate` distinto, y el segundo `push` pisa al primero o genera un conflicto de merge en un JSON que no se puede resolver a mano con seguridad.
3. **No hay bloqueo**: nada impide que dos `terraform apply` corran en paralelo sobre la misma infraestructura.

La solución es un *backend* remoto con bloqueo. En AWS, un bucket S3 con versionado:

```hcl
# backend.tf
terraform {
  required_version = ">= 1.10"

  backend "s3" {
    bucket       = "empresa-terraform-state"
    key          = "prod/network/terraform.tfstate"   # una clave por entorno y componente
    region       = "eu-west-1"
    encrypt      = true
    use_lockfile = true                               # bloqueo nativo en S3 (Terraform ≥ 1.10)
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}
```

Antes de la 1.10 el bloqueo necesitaba una tabla de DynamoDB (`dynamodb_table = "terraform-locks"`); si tienes que usar una versión anterior, es esa línea en vez de `use_lockfile`.

**El bucket se crea una vez y fuera de este estado** (el huevo y la gallina: Terraform no puede guardar su estado en un bucket que todavía no existe). O a mano, o con una configuración mínima aparte con estado local que solo gestiona el bucket:

```hcl
resource "aws_s3_bucket" "state" {
  bucket = "empresa-terraform-state"
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "aws:kms" }
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
```

El **versionado** es lo que te salva cuando alguien aplica algo mal: cada `apply` guarda una versión nueva y puedes restaurar la anterior desde la consola de S3.

**Migrar el estado que ya tienes:**

```bash
terraform init -migrate-state      # copia el tfstate local al bucket y pregunta confirmación
git rm --cached terraform.tfstate terraform.tfstate.backup
```

y en `.gitignore`:

```
*.tfstate
*.tfstate.*
.terraform/
*.tfvars          # si contienen secretos; los de ejemplo, como .tfvars.example
```

El estado que ya está en el historial de git sigue ahí: rota los secretos que contenga. Reescribir el historial es posible, pero rotar es seguro y rápido.

**Un estado por entorno**, con claves distintas (`prod/...`, `staging/...`) o directorios separados, no *workspaces*: un error con el workspace activo es la forma más fácil de aplicar a producción creyendo que es staging. Y el acceso al bucket de `prod` restringido por IAM a la cuenta de CI y a quien deba aplicar.

Verificación: tras `init -migrate-state`, `terraform plan` debe decir `No changes`; `aws s3 ls s3://empresa-terraform-state/prod/network/` muestra el archivo, y si lanzas dos `terraform plan` a la vez, el segundo espera con `Acquiring state lock`.""",
            },
        ]
    },
    # 21) Terraform: dividir en módulos sin destruir nada (intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo un `main.tf` de 1.200 líneas con la VPC, 3 servicios ECS, RDS y buckets. Quiero dividirlo en módulos pero no sé con qué criterio, ni cómo evitar que `count` me destruya cosas al reordenar.",
            },
            {
                "role": "assistant",
                "content": """El criterio: un módulo es algo que **se crea varias veces** (los tres servicios ECS son el candidato obvio) o que **tiene un ciclo de vida propio** (la red cambia una vez al año; los servicios, cada semana). No es «un módulo por tipo de recurso»: un módulo `s3` que envuelve un `aws_s3_bucket` solo añade indirección.

Para tu caso, tres módulos y una raíz:

```
infra/
  main.tf              # llama a los módulos y los conecta
  modules/
    network/           # VPC, subredes, NAT, security groups base
    ecs-service/       # task definition, service, target group, listener rule, IAM del servicio
    database/          # RDS, subnet group, parameter group, secreto de la contraseña
```

Cada módulo tiene `main.tf`, `variables.tf` y `outputs.tf`. Las variables son la interfaz: pocas, con `type` y `description`; los *outputs*, lo que otros módulos necesitan (`vpc_id`, `private_subnet_ids`, `db_endpoint`).

```hcl
# modules/ecs-service/variables.tf
variable "name"        { type = string }
variable "image"       { type = string }
variable "cpu"         { type = number, default = 256 }
variable "memory"      { type = number, default = 512 }
variable "cluster_arn" { type = string }
variable "subnet_ids"  { type = list(string) }
variable "env"         { type = map(string), default = {} }
```

```hcl
# main.tf (raíz)
module "network" {
  source     = "./modules/network"
  cidr_block = "10.20.0.0/16"
}

locals {
  services = {
    api     = { image = "registry/api:2.1.0",     cpu = 512, memory = 1024 }
    worker  = { image = "registry/worker:2.1.0",  cpu = 256, memory = 512 }
    gateway = { image = "registry/gateway:1.8.0", cpu = 256, memory = 512 }
  }
}

module "service" {
  for_each    = local.services
  source      = "./modules/ecs-service"
  name        = each.key
  image       = each.value.image
  cpu         = each.value.cpu
  memory      = each.value.memory
  cluster_arn = aws_ecs_cluster.main.arn
  subnet_ids  = module.network.private_subnet_ids
}
```

**`for_each` con un mapa, nunca `count` con una lista, para cosas con identidad.** Con `count`, los recursos se llaman `module.service[0]`, `[1]`, `[2]`; si borras el primero de la lista, el `[1]` pasa a ser `[0]` y Terraform **destruye y recrea** dos servicios para «renombrarlos». Con `for_each`, se llaman `module.service["api"]`, y quitar `worker` solo destruye `worker`. `count` queda para «cero o uno» (`count = var.enabled ? 1 : 0`).

**Mover lo existente sin destruir nada.** Los recursos ya viven en el estado con sus direcciones actuales (`aws_ecs_service.api`). Si los defines dentro del módulo, Terraform ve «desapareció `aws_ecs_service.api`, apareció `module.service["api"].aws_ecs_service.this`» y planifica destruir y crear. Los bloques `moved` le dicen que es el mismo recurso:

```hcl
moved {
  from = aws_ecs_service.api
  to   = module.service["api"].aws_ecs_service.this
}

moved {
  from = aws_vpc.main
  to   = module.network.aws_vpc.this
}
```

Uno por recurso movido (`terraform state list` te da la lista completa). Tras el `apply`, puedes borrar los bloques `moved`. Es la versión declarativa y revisable de `terraform state mv`.

**Versionado de los módulos.** Mientras vivan en el mismo repositorio, `source = "./modules/..."` y se versionan con el resto. Cuando otro equipo los use, pásalos a un repositorio propio con etiquetas git (`source = "git::https://.../modules.git//ecs-service?ref=v1.2.0"`) o al registro privado, y fija la versión en cada llamada: un módulo compartido sin versión es un cambio en producción cada vez que alguien hace push.

Haz la migración en PRs pequeños: un módulo por PR, con `moved` incluidos. El criterio de aceptación de cada uno es el mismo: `terraform plan` debe terminar en `0 to add, 0 to change, 0 to destroy` (o solo los cambios que esperas), y cada línea del plan que diga `# ... has moved to ...` confirma que el recurso se reubicó sin tocarse.""",
            },
        ]
    },
    # 22) Terraform en GitHub Actions: plan en PR, apply en main, OIDC (intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Cómo monto en GitHub Actions que cada PR muestre el `terraform plan` y que el `apply` solo pase al mergear a main, sin guardar claves de AWS en el repo?",
            },
            {
                "role": "assistant",
                "content": r"""Dos jobs en un mismo workflow: `plan` en `pull_request` y `apply` en `push` a `main`, los dos autenticados contra AWS por OIDC (un rol de IAM que confía en GitHub; sin claves). El `apply` reutiliza el plan guardado como artefacto, así que aplica exactamente lo que se revisó.

```yaml
name: terraform
on:
  pull_request:
    paths: ["infra/**"]
  push:
    branches: [main]
    paths: ["infra/**"]

permissions:
  contents: read
  id-token: write            # necesario para pedir el token OIDC
  pull-requests: write       # para comentar el plan en el PR

concurrency:
  group: terraform-prod      # nunca dos operaciones a la vez sobre el mismo estado
  cancel-in-progress: false

env:
  TF_IN_AUTOMATION: "true"
  TF_INPUT: "false"

jobs:
  plan:
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: infra } }
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/github-terraform-plan   # solo lectura + estado
          aws-region: eu-west-1
      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: "1.10.5"
      - run: terraform fmt -check -recursive
      - run: terraform init
      - run: terraform validate
      - id: plan
        run: terraform plan -no-color -out=tfplan -detailed-exitcode
        continue-on-error: true           # código 2 = hay cambios; no es un fallo
      - if: steps.plan.outcome == 'failure' && steps.plan.outputs.exitcode != '2'
        run: exit 1
      - run: terraform show -no-color tfplan > plan.txt
      - uses: actions/github-script@v7
        with:
          script: |
            const fs = require("fs");
            const plan = fs.readFileSync("infra/plan.txt", "utf8").slice(0, 60000);
            await github.rest.issues.createComment({
              owner: context.repo.owner, repo: context.repo.repo,
              issue_number: context.issue.number,
              body: "### terraform plan\n```\n" + plan + "\n```",
            });

  apply:
    if: github.event_name == 'push'
    runs-on: ubuntu-latest
    environment: production               # reviewers obligatorios y secretos del entorno
    defaults: { run: { working-directory: infra } }
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/github-terraform-apply
          aws-region: eu-west-1
      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: "1.10.5"
      - run: terraform init
      - run: terraform plan -no-color -out=tfplan
      - run: terraform apply -auto-approve tfplan
```

Decisiones:

- **OIDC en vez de claves.** `permissions: id-token: write` deja que el job pida a GitHub un token firmado; `configure-aws-credentials` lo cambia por credenciales temporales de un rol cuya política de confianza acepta solo `repo:empresa/infra:ref:refs/heads/main` (para apply) o `repo:empresa/infra:pull_request` (para plan). No hay secreto que rotar ni que filtrar.
- **Dos roles.** El de `plan` solo necesita lectura de recursos y acceso al bucket de estado; el de `apply`, escritura. Un PR de un desconocido no puede modificar infraestructura aunque el workflow corra.
- **`-detailed-exitcode`** devuelve 0 sin cambios, 1 error, 2 con cambios. `setup-terraform` expone el código en `steps.plan.outputs.exitcode`; el paso siguiente convierte solo el 1 en fallo del job.
- **El `apply` vuelve a hacer `plan`** en vez de reutilizar el artefacto del PR: el plan de un PR puede tener días y el estado haber cambiado por otro merge. Si quieres aplicar literalmente lo revisado, sube `tfplan` como artefacto y descárgalo aquí, pero añade un `terraform plan -detailed-exitcode` previo que falle si el estado se movió.
- **`environment: production`** con revisores obligatorios: el merge dispara el job, pero alguien aprueba antes de que el `apply` arranque. Es el equivalente al «¿seguro?» de la terminal.
- **`concurrency` sin cancelar**: un `apply` interrumpido deja el estado bloqueado y a medias; mejor que el segundo espere.
- Fija `terraform_version` y usa el mismo valor en `required_version`; un runner con una versión más nueva actualiza el formato del estado y rompe el `plan` local de todo el equipo.

Verificación: abre un PR con un cambio trivial (una etiqueta) y comprueba que el comentario con el plan aparece y dice `1 to change`; mergea y comprueba que el job `apply` espera la aprobación del entorno antes de correr.""",
            },
        ]
    },
    # 23) Terraform: importar un recurso existente (usuario trae error, intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": "Creé un bucket S3 a mano hace meses y ahora quiero que Terraform lo gestione. Al hacer apply: `Error: creating S3 Bucket (logs-empresa): BucketAlreadyOwnedByYou`. ¿Lo borro y dejo que lo cree?",
            },
            {
                "role": "assistant",
                "content": """No lo borres: perderías los logs, y además no hace falta. El error dice que el bucket existe y es tuyo; lo que Terraform necesita es que **el estado** lo conozca. Para eso está `import`: adopta el recurso real sin tocarlo.

Desde Terraform 1.5 se hace con un bloque declarativo, que queda en el código y se revisa en un PR como cualquier cambio:

```hcl
# import.tf
import {
  to = aws_s3_bucket.logs
  id = "logs-empresa"          # el identificador que pide el proveedor; para S3, el nombre
}
```

**1. Deja que Terraform te escriba la configuración** a partir del recurso real, en vez de adivinar atributos:

```bash
terraform plan -generate-config-out=generated.tf
```

Genera `generated.tf` con un bloque `resource "aws_s3_bucket" "logs"` y todos los atributos leídos de AWS. Revísalo, quita lo que es solo lectura o ruido (el proveedor marca con comentarios lo que no se puede fijar), y mueve el bloque limpio a tu `main.tf`. Si prefieres escribirlo a mano, basta con:

```hcl
resource "aws_s3_bucket" "logs" {
  bucket = "logs-empresa"
}
```

**2. Aplica.** El `apply` hace la importación (solo escribe en el estado) y, en la misma pasada, los cambios que haya entre tu configuración y la realidad:

```bash
terraform plan        # debe decir "1 to import, 0 to add, X to change"
terraform apply
```

Si `X to change` no es 0, mira qué quiere cambiar antes de aplicar: suele ser una etiqueta o una opción que tienes distinta en el código. Ajusta el código hasta que el plan diga `0 to change`; ese es el criterio de que la configuración describe lo que hay.

**3. Los recursos hijos van aparte.** En el proveedor de AWS, el versionado, el cifrado, la política y el ciclo de vida del bucket son recursos independientes desde la versión 4. Si el bucket tiene versionado activado y no lo importas, Terraform no lo gestionará (no lo quitará, pero tampoco lo verá):

```hcl
import {
  to = aws_s3_bucket_versioning.logs
  id = "logs-empresa"
}

import {
  to = aws_s3_bucket_lifecycle_configuration.logs
  id = "logs-empresa"
}
```

`terraform plan -generate-config-out` también los genera si añades sus bloques `import`.

**4. Limpia.** Tras el `apply`, borra `import.tf`: los bloques ya han cumplido y, si se quedan, Terraform avisa en cada plan de que el recurso ya está en el estado.

La versión antigua, `terraform import aws_s3_bucket.logs logs-empresa`, hace lo mismo desde la línea de comandos pero sin generar configuración y sin pasar por el PR; sirve para un recurso suelto, no para adoptar una cuenta entera.

Verificación final: `terraform state show aws_s3_bucket.logs` muestra el bucket con sus atributos, y `terraform plan` dice `No changes. Your infrastructure matches the configuration.`""",
            },
        ]
    },
    # 24) Terraform: moved y drift (system rioplatense, multiturno, intermedio)
    {
        "messages": [
            {"role": "system", "content": "Respondé en español rioplatense, con precisión técnica y sin relleno."},
            {
                "role": "user",
                "content": "Renombré un recurso de `aws_instance.web` a `aws_instance.api` para que el nombre tenga sentido y `terraform plan` quiere destruir la instancia y crear otra. Es producción, no puede pasar. ¿Cómo lo hago?",
            },
            {
                "role": "assistant",
                "content": """Terraform identifica cada recurso por su dirección en el estado, no por lo que hay en AWS. Para él, `aws_instance.web` desapareció del código (hay que destruirlo) y apareció `aws_instance.api` (hay que crearlo). Tenés que decirle que es el mismo: un bloque `moved`.

```hcl
moved {
  from = aws_instance.web
  to   = aws_instance.api
}

resource "aws_instance" "api" {
  # ... la misma configuración que tenía web
}
```

```bash
terraform plan
# aws_instance.web has moved to aws_instance.api
# No changes. Your infrastructure matches the configuration.
```

El plan ya no destruye nada: solo renombra la entrada en el estado durante el `apply`. Después podés borrar el bloque `moved` (dejalo al menos un ciclo si otros compañeros tienen estado o ramas viejas; Terraform ignora un `moved` cuyo origen ya no existe).

Lo mismo sirve para mover un recurso dentro de un módulo (`to = module.api.aws_instance.this`) o para pasar de `count` a `for_each` (`from = aws_instance.web[0]`, `to = aws_instance.api["main"]`).

La alternativa imperativa es `terraform state mv aws_instance.web aws_instance.api`, que edita el estado directamente. Funciona, pero no queda en el PR ni se revisa, y si alguien aplica desde una rama sin ese cambio, vuelve a ver el destroy. El bloque `moved` es la forma que corresponde desde la 1.1.

Para que no vuelva a pasar en producción, dos redes de seguridad:

```hcl
resource "aws_instance" "api" {
  lifecycle {
    prevent_destroy = true     # el plan falla con error si algo intenta destruirlo
  }
}
```

y en CI, un paso que lea el plan en JSON (`terraform show -json tfplan`) y falle si alguna acción es `delete` sobre recursos marcados como críticos. Con eso, el error que acabás de ver lo frena el pipeline antes que vos.

Verificación: `terraform plan` tiene que terminar con `0 to add, 0 to change, 0 to destroy` y la línea `has moved to`. Si en vez de eso dice `1 to add, 1 to destroy`, el `from` no coincide con la dirección real: `terraform state list` te da el nombre exacto.""",
            },
            {
                "role": "user",
                "content": "Buenísimo. Otra: alguien cambió el tipo de instancia a mano en la consola y ahora el plan quiere volverla a `t3.medium`. ¿Cómo manejo ese drift?",
            },
            {
                "role": "assistant",
                "content": """Eso es *drift*: la realidad y el código discrepan, y Terraform siempre va a querer imponer el código. La decisión no es técnica sino de equipo: ¿el cambio manual fue correcto y hay que adoptarlo, o fue un parche y hay que revertirlo?

**Primero, ver el drift sin tocar nada:**

```bash
terraform plan -refresh-only
```

Muestra solo las diferencias entre el estado y la realidad (`instance_type: "t3.medium" -> "t3.large"`), sin proponer cambios de infraestructura. Es el comando para auditar qué se tocó a mano.

**Opción A: adoptar el cambio.** Actualizás el código a `t3.large` y aplicás:

```hcl
resource "aws_instance" "api" {
  instance_type = "t3.large"
}
```

`terraform plan` debe decir `No changes` tras `apply -refresh-only` o directamente en el plan normal, porque código y realidad ya coinciden. El cambio queda documentado en el PR, que es lo que faltaba.

**Opción B: revertir.** Dejás el código como está y `terraform apply` vuelve la instancia a `t3.medium`. Ojo: cambiar `instance_type` reinicia la instancia; coordinalo.

**Lo que no conviene** como respuesta general: `ignore_changes`.

```hcl
lifecycle {
  ignore_changes = [instance_type]
}
```

Tiene un uso legítimo, cuando un atributo lo gestiona otro sistema a propósito (el `desired_count` de un servicio con autoescalado, etiquetas que añade un agente), pero usarlo para «que deje de molestar» convierte el código en mentira: dice `t3.medium` y nadie sabe qué hay en realidad.

**Para que el drift no se acumule:**

1. **Sin permisos de escritura en la consola** para los recursos que gestiona Terraform, salvo un rol de emergencia con alerta. El drift desaparece cuando no se puede crear.
2. **Detección programada**: un workflow diario que corra `terraform plan -detailed-exitcode` y avise en Slack si el código de salida es 2. Así el cambio manual se descubre el mismo día, con quien lo hizo todavía acordándose de por qué.
3. **Si la emergencia obliga a tocar a mano**, la regla es «después del incidente, PR con el cambio o PR que lo revierte»; el `plan -refresh-only` de la mañana siguiente es la lista de tareas.

Verificación: después de la opción que elijas, `terraform plan -refresh-only` y `terraform plan` tienen que decir ambos `No changes`.""",
            },
        ]
    },
    # 25) GitHub Actions: workflow lento, caché, concurrency (usuario trae workflow, principiante/intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": """Nuestro workflow de tests de Node tarda 11 minutos y la mayoría es `npm install`. Además se encola cuando hacemos varios push seguidos.

```yaml
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
      - run: npm install
      - run: npm test
```""",
            },
            {
                "role": "assistant",
                "content": """Cuatro cambios, y el primero es el que recorta los minutos: cachear las descargas de npm. El runner arranca vacío en cada ejecución, así que sin caché cada `npm install` baja todo de Internet.

```yaml
name: ci
on:
  push:
    branches: [main]
  pull_request:

permissions:
  contents: read

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true          # un push nuevo a la misma rama cancela la ejecución anterior

jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    strategy:
      fail-fast: false
      matrix:
        node: [20, 22]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: ${{ matrix.node }}
          cache: npm                  # guarda y restaura ~/.npm con clave = hash de package-lock.json
      - run: npm ci
      - run: npm test
```

Por qué cada cosa:

- **`cache: npm` en `setup-node`** guarda la caché de npm al final del job y la restaura al principio, con una clave derivada de `package-lock.json`. Mientras el lock no cambie, `npm ci` instala desde la caché en 20-40 s en vez de descargar. Es lo que convierte 11 minutos en 2 o 3.
- **`npm ci` en vez de `npm install`**: instala exactamente el lock, borra `node_modules` antes y es más rápido. `npm install` puede modificar el lock en CI, que es justo lo que no quieres.
- **`concurrency` con `cancel-in-progress`**: tres pushes seguidos a una rama ya no encolan tres ejecuciones; las dos primeras se cancelan y solo corre la última. En `main` quizá prefieras `cancel-in-progress: false` para que cada commit se pruebe; se puede condicionar con `${{ github.ref != 'refs/heads/main' }}`.
- **`on` acotado**: `push` a todas las ramas más `pull_request` ejecutaba el workflow dos veces por cada push a una rama con PR abierto. `push` solo en `main` y `pull_request` para el resto lo deja en una.
- **`timeout-minutes`**: por defecto un job puede colgarse 6 horas consumiendo minutos; 15 es más que suficiente para tests.
- **`permissions: contents: read`**: el token del job no necesita escribir nada; reducirlo es gratis y limita lo que un test o una dependencia maliciosa pueden hacer.
- **La matriz** prueba las dos versiones de Node que soportas en paralelo; `fail-fast: false` deja que la otra termine aunque una falle, para ver si el fallo es de versión o de código. Si solo soportas una, quita la matriz.

Un paso más cuando quieras bajar otro minuto: separar `lint` y `test` en jobs distintos que corran en paralelo, cada uno con la misma caché.

Comprobación: en la segunda ejecución tras el cambio, el paso `setup-node` debe mostrar `Cache restored from key: node-cache-Linux-x64-npm-<hash>` y `npm ci` debe tardar menos de un minuto. Si sigue diciendo `Cache not found`, el `package-lock.json` no está en el repositorio o está en un subdirectorio (entonces añade `cache-dependency-path: app/package-lock.json`).""",
            },
        ]
    },
    # 26) GitHub Actions: OIDC hacia AWS y gestión de secretos (multiturno, intermedio/avanzado)
    {
        "messages": [
            {
                "role": "user",
                "content": "Para desplegar a AWS desde GitHub Actions tenemos `AWS_ACCESS_KEY_ID` y `AWS_SECRET_ACCESS_KEY` como secretos del repo. Seguridad nos pide quitarlos. ¿Cuál es la alternativa?",
            },
            {
                "role": "assistant",
                "content": """La alternativa es **OIDC**: en cada ejecución, GitHub emite un token firmado que identifica al workflow (repositorio, rama, entorno), y AWS lo cambia por credenciales temporales de un rol de IAM. No hay clave que guardar, rotar ni filtrar, y el rol solo lo puede asumir el workflow que tú digas.

**1. Registrar a GitHub como proveedor de identidad en AWS** (una vez por cuenta):

```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com
```

**2. Crear el rol con una política de confianza acotada.** La condición sobre `sub` es la parte importante: dice exactamente qué repositorio y qué contexto pueden asumirlo.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:empresa/api:environment:production"
        }
      }
    }
  ]
}
```

Formas habituales del `sub`: `repo:empresa/api:ref:refs/heads/main` (solo la rama main), `repo:empresa/api:environment:production` (solo jobs con ese `environment`), `repo:empresa/api:pull_request` (PRs). Nunca `repo:empresa/*` sin más: cualquier repositorio de la organización podría desplegar.

Al rol le adjuntas la política de permisos mínima para el despliegue (ECR push, ECS update-service, lo que toque), no `AdministratorAccess`.

**3. El workflow:**

```yaml
jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: production
    permissions:
      id-token: write          # permite pedir el token OIDC
      contents: read
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::123456789012:role/github-deploy-api
          aws-region: eu-west-1
      - run: aws sts get-caller-identity      # comprobación: debe mostrar el rol asumido
      - run: aws ecs update-service --cluster prod --service api --force-new-deployment
```

`permissions: id-token: write` es obligatorio y no viene por defecto; sin él, `configure-aws-credentials` falla con `Error: Credentials could not be loaded`. Las credenciales que obtiene duran una hora y mueren con el job.

**4. Borrar las claves.** Elimina los dos secretos del repositorio **y** desactiva la clave en IAM (`aws iam update-access-key --status Inactive` primero; borrar después de unos días sin alertas). Si dejas la clave activa «por si acaso», no has resuelto nada.

El mismo esquema existe para GCP (*Workload Identity Federation*), Azure (*federated credentials*) y HashiCorp Vault; en todos, el token OIDC de GitHub sustituye al secreto de larga duración.

Verificación: la ejecución debe mostrar en `get-caller-identity` un ARN de tipo `assumed-role/github-deploy-api/...`, y si lanzas el mismo workflow desde una rama que no sea `main` sin el entorno, debe fallar con `Not authorized to perform sts:AssumeRoleWithWebIdentity`. Ese fallo es la prueba de que la condición funciona.""",
            },
            {
                "role": "user",
                "content": "¿Y los secretos que sí necesitamos (tokens de terceros tipo Stripe o Sentry)? ¿Van en el repo, en el environment o en la organización?",
            },
            {
                "role": "assistant",
                "content": """En el **environment** para todo lo que sea de producción, en la **organización** solo lo que de verdad comparten muchos repositorios, y en el **repositorio** lo que es de desarrollo o CI y no da acceso a nada sensible.

| Nivel | Quién lo lee | Cuándo |
|---|---|---|
| Organización | Los repositorios que autorices (lista explícita, no «todos») | Token del registro de imágenes, licencia de una herramienta, Sentry DSN de la org |
| Repositorio | Cualquier workflow del repositorio, en cualquier rama | Claves de servicios de prueba, tokens de CI sin poder sobre producción |
| Environment | Solo jobs con `environment: X`, y solo si pasan sus reglas | Stripe live, credenciales de base de datos, cualquier cosa de producción |

Lo que hace al environment la opción correcta para producción son sus **reglas de protección**: revisores obligatorios antes de que el job arranque, y restricción a ramas concretas (`main`, etiquetas `v*`). Un secreto de repositorio lo lee un workflow en cualquier rama; basta con que alguien con permiso de push modifique el YAML para imprimirlo. Con el environment, el job ni arranca sin aprobación, y un PR desde una rama no autorizada no tiene acceso.

Reglas prácticas:

- **Los PR desde forks no reciben secretos**, por diseño. No lo «arregles» con `pull_request_target` haciendo checkout del código del PR: ese evento sí tiene secretos y ejecuta el código de un desconocido con ellos. Es la vulnerabilidad más explotada en Actions.
- **GitHub enmascara el valor en los logs**, pero solo el valor exacto: un secreto en base64, en una URL o partido en dos líneas sale en claro. No hagas `echo` de nada derivado de un secreto; si generas uno en un paso, regístralo con `echo "::add-mask::$VALOR"` antes de usarlo.
- **Rotación**: anota en el nombre o en la descripción del secreto cuándo caduca, y que el workflow falle de forma clara cuando el token esté vencido (un `curl` de comprobación al inicio del job) en vez de a mitad del despliegue.
- **Cuantos menos secretos viva GitHub, mejor.** Con el rol OIDC ya tienes acceso a AWS: guarda Stripe y Sentry en *Secrets Manager* o *Parameter Store* y léelos en el job con `aws secretsmanager get-secret-value`. GitHub entonces no guarda nada de producción; solo la identidad del workflow, que no es un secreto.

Verificación: en la pestaña *Settings → Environments → production* debe haber al menos un revisor obligatorio y la restricción a `main`; y un workflow lanzado desde una rama de prueba con `environment: production` debe quedarse en *Waiting for review*, no ejecutarse.""",
            },
        ]
    },
    # 27) GitHub Actions: reusable workflows frente a composite actions (SISTEMA, intermedio)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Tenemos el mismo bloque de 40 líneas (checkout, setup, caché, lint, test) copiado en 12 repos. ¿Reusable workflow o composite action? ¿Qué diferencia hay?",
            },
            {
                "role": "assistant",
                "content": """Para un bloque que es **un job completo** (checkout, setup, lint, test) la respuesta es *reusable workflow*. La *composite action* es para un grupo de pasos que se inserta dentro de un job ajeno. La diferencia es de nivel: una se llama donde iría un `job`, la otra donde iría un `step`.

| | Reusable workflow | Composite action |
|---|---|---|
| Se invoca con | `jobs.<id>.uses: org/repo/.github/workflows/ci.yml@v1` | `steps[].uses: org/repo/.github/actions/setup@v1` |
| Qué contiene | Uno o varios jobs completos, con `runs-on`, `strategy`, `services`, `environment` | Solo pasos; corre en el runner del job que la llama |
| Matriz, runners distintos, jobs paralelos | Sí | No: hereda el job del llamador |
| Secretos | `secrets:` explícitos o `secrets: inherit` | Los recibe como `inputs` o lee `env` del llamador |
| `permissions`, `concurrency`, `environment` | Puede definirlos (acotados por el llamador) | No |
| Anidación | Hasta 4 niveles | Puede usar otras actions |
| Aparece en la UI como | Jobs propios | Pasos dentro del job que la llama |

**Reusable workflow para tu caso.** En un repositorio `empresa/workflows`:

```yaml
# .github/workflows/node-ci.yml
name: node-ci
on:
  workflow_call:
    inputs:
      node-version:
        type: string
        default: "22"
      working-directory:
        type: string
        default: "."
    secrets:
      NPM_TOKEN:
        required: false

jobs:
  ci:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: ${{ inputs.working-directory }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: ${{ inputs.node-version }}
          cache: npm
          cache-dependency-path: ${{ inputs.working-directory }}/package-lock.json
      - run: npm ci
        env:
          NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}
      - run: npm run lint
      - run: npm test
```

Y en cada uno de los 12 repositorios, el workflow queda en seis líneas:

```yaml
name: ci
on: [push, pull_request]
jobs:
  ci:
    uses: empresa/workflows/.github/workflows/node-ci.yml@v1
    with:
      node-version: "20"
    secrets: inherit
```

**Composite action cuando** quieras reutilizar *dentro* de un job que ya existe: por ejemplo «instalar nuestra CLI interna y autenticarla» como paso previo a cosas distintas en cada repositorio.

```yaml
# .github/actions/setup-cli/action.yml
name: setup-cli
inputs:
  token:
    required: true
runs:
  using: composite
  steps:
    - run: curl -fsSL https://cli.empresa.internal/install.sh | sh
      shell: bash               # obligatorio en cada run de una composite
    - run: empresa-cli auth --token "${{ inputs.token }}"
      shell: bash
```

Tres detalles que ahorran una tarde:

- **Versiona con etiquetas** (`@v1`) y mueve la etiqueta con cada release compatible; `@main` convierte cualquier push al repositorio de workflows en un cambio simultáneo en los 12. Para máxima seguridad, referencia por SHA del commit.
- **`secrets: inherit`** pasa todos los secretos del llamador, incluidos los del `environment`. Si el workflow reutilizable debe ver solo uno, decláralo explícito como arriba; es más seguro y documenta la dependencia.
- El workflow reutilizable **no puede** usar `github.ref` esperando la rama del llamador en todos los contextos; `github.event` y `github.ref` sí son los del llamador, pero `github.workflow_ref` es el del reutilizable. Los *outputs* de un job del reutilizable se exponen con `on.workflow_call.outputs`.

Verificación: cambia una línea en `node-ci.yml`, etiqueta `v1.1.0`, mueve `v1` y comprueba que la siguiente ejecución en cualquiera de los 12 repositorios muestra el job `ci / ci` con el paso nuevo, sin tocar sus archivos.""",
            },
        ]
    },
    # 28) GitHub Actions: falla en CI y no en local (inglés, intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": "A shell step in my GitHub Actions job fails with `Error: Process completed with exit code 1`, but running the same commands locally works. The step is `./gen.sh | tee out.log` plus a few `cd`s. How do I debug this without pushing 20 commits?",
            },
            {
                "role": "assistant",
                "content": """Three things differ between your terminal and a `run` step, and your step touches all three: the shell flags, the working directory, and the lack of a TTY.

**1. The shell is `bash -e`, and with `shell: bash` it is also `-o pipefail`.** Locally, an interactive shell ignores a non-zero exit from a command in the middle of a script. In Actions, the default is `bash -e {0}`: the step stops at the first command that returns non-zero. If you set `shell: bash` explicitly, you get `bash --noprofile --norc -eo pipefail {0}`, so `./gen.sh | tee out.log` fails as soon as `gen.sh` fails, even though `tee` succeeded. That is correct behavior; locally the failure was hidden.

Find the failing command by turning on tracing for that step only:

```yaml
- run: |
    set -x
    ./gen.sh | tee out.log
  shell: bash
```

The log then shows each command before it runs, and the last `+` line before the error is the culprit. Commands that commonly return non-zero without being "wrong": `grep` with no match, `diff` with differences, `test`/`[` evaluated to false, `git diff --exit-code`.

**2. `cd` does not survive across steps.** Each step is a fresh shell starting in `$GITHUB_WORKSPACE`. A `cd app` in step 3 is gone in step 4. Use `working-directory` instead:

```yaml
- run: ./gen.sh | tee out.log
  working-directory: app
```

The same applies to environment variables: `export FOO=1` dies with the step. To pass a value to later steps, append to `$GITHUB_ENV`:

```yaml
- run: echo "VERSION=$(cat VERSION)" >> "$GITHUB_ENV"
- run: echo "building $VERSION"
```

**3. No TTY, different environment.** Anything that checks `isatty` behaves differently: `docker run -it` fails with `the input device is not a TTY` (drop `-t`), `tput` and color libraries may error, and some CLIs wait for input forever. Also `ubuntu-latest` is not your laptop: check versions in the step itself (`node --version`, `python3 --version`, `which gen-dependency`).

**Debugging without a commit per attempt:**

- `ACTIONS_STEP_DEBUG` set to `true` as a repository **variable** (or secret) makes the runner print `##[debug]` lines for every step: resolved paths, env, action inputs. Re-run the failed job with "Enable debug logging" in the UI does the same for one run.
- Open a shell on the runner at the failing point with `mxschmitt/action-tmate`: add `- uses: mxschmitt/action-tmate@v3` with `if: failure()` right after the step, and the log prints an SSH command. You get the exact filesystem and environment where it broke. Remove it afterwards.
- Run the workflow locally with `act` (`act -j test`). It is close but not identical (different image, no GitHub-hosted tools), so use it for iteration, not as proof.

Most likely diagnosis given your description: `gen.sh` returns non-zero (something it calls, like `grep`, found nothing), `pipefail` surfaces it, and locally you never noticed because the pipeline's last command `tee` exits 0. Fix the script to handle that case, or if the non-zero is expected, make it explicit: `./gen.sh | tee out.log || true` is acceptable only if you then check `out.log` for what you actually need.

Verification: after the fix, run the step with `set -x` once more and confirm no `+` line is followed by an error; then remove `set -x`.""",
            },
        ]
    },
    # 29) GitLab CI: traducir un pipeline desde GitHub Actions (intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": "Nos movemos de GitHub a GitLab. ¿Cómo se traduce un workflow típico (lint, test con matriz de versiones, build de imagen, deploy solo en main) a `.gitlab-ci.yml`?",
            },
            {
                "role": "assistant",
                "content": """Los conceptos se corresponden casi uno a uno; lo que cambia es que GitLab organiza por `stages` y expresa las condiciones con `rules` en cada job.

| GitHub Actions | GitLab CI |
|---|---|
| Un workflow por archivo en `.github/workflows/` | Un `.gitlab-ci.yml` (dividible con `include:`) |
| `jobs.<id>` con `steps` | Un job con `script` (lista de comandos) |
| `needs:` / orden implícito | `stages` (secuenciales) + `needs:` para saltarse el orden |
| `strategy.matrix` | `parallel: matrix` |
| `if:` en job o step | `rules:` con `if:`, `changes:`, `when:` |
| `uses:` (actions) | `include:` de plantillas, *CI/CD components* |
| `actions/cache` / `cache:` en setup-* | `cache:` con `key: files: [...]` |
| `environment:` | `environment:` (con URL, protección y despliegues) |
| OIDC (`id-token: write`) | `id_tokens:` en el job |
| `${{ github.sha }}` | `$CI_COMMIT_SHA`, `$CI_COMMIT_SHORT_SHA` |

```yaml
# .gitlab-ci.yml
stages: [check, build, deploy]

default:
  image: node:22
  cache:
    key:
      files: [package-lock.json]        # misma clave mientras no cambie el lock
    paths: [.npm/]
  before_script:
    - npm ci --cache .npm --prefer-offline

workflow:
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH

lint:
  stage: check
  script:
    - npm run lint

test:
  stage: check
  parallel:
    matrix:
      - NODE_VERSION: ["20", "22"]
  image: node:$NODE_VERSION
  script:
    - npm test
  artifacts:
    when: always
    reports:
      junit: junit.xml                 # los resultados aparecen en el MR

build-image:
  stage: build
  image: docker:27
  services: [docker:27-dind]
  cache: []                            # este job no necesita npm
  before_script:
    - docker login -u "$CI_REGISTRY_USER" -p "$CI_REGISTRY_PASSWORD" "$CI_REGISTRY"
  script:
    - docker build --pull -t "$CI_REGISTRY_IMAGE:$CI_COMMIT_SHORT_SHA" .
    - docker push "$CI_REGISTRY_IMAGE:$CI_COMMIT_SHORT_SHA"
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH

deploy-prod:
  stage: deploy
  image: alpine/k8s:1.31.0
  needs: [build-image]
  environment:
    name: production
    url: https://api.example.com
  script:
    - kubectl set image deployment/api api="$CI_REGISTRY_IMAGE:$CI_COMMIT_SHORT_SHA" -n prod
    - kubectl rollout status deployment/api -n prod
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
      when: manual                     # botón en la UI; quita esta línea para despliegue automático
```

Lo que conviene saber al traducir:

- **`workflow.rules`** decide si el pipeline entero se crea; sin él, GitLab lanza un pipeline por push a cualquier rama *y* otro por MR, duplicando como en Actions con `push` + `pull_request`.
- **`rules` es la primera coincidencia gana.** Un job sin `rules` corre siempre; un job con `rules` que no coincide con nada no se crea. No hay `if: always()` en pasos porque no hay pasos: cada job es atómico, y lo que en Actions eran pasos condicionales aquí son jobs separados.
- **La caché es por runner y «best effort»**; los `artifacts` son la forma fiable de pasar archivos entre jobs (`dist/` del build al deploy).
- **`CI_REGISTRY_*`** vienen predefinidos: el registro de contenedores integrado no necesita secretos. Para AWS u otros, `id_tokens: { AWS_TOKEN: { aud: sts.amazonaws.com } }` en el job y el mismo rol OIDC que tenías en GitHub, cambiando el proveedor de confianza a `gitlab.com`.
- Los runners compartidos de gitlab.com tienen minutos limitados en planes gratuitos; para `docker:dind` suele compensar un runner propio o Kaniko (`gcr.io/kaniko-project/executor`) que construye sin daemon de Docker.

Verificación: abre un MR con un cambio en `package-lock.json` y comprueba que `test` corre dos veces (una por versión de Node), que `build-image` no aparece en el MR, y que al mergear a `main` el pipeline muestra `build-image` seguido de `deploy-prod` con el botón de ejecución manual.""",
            },
        ]
    },
    # 30) Despliegue: blue/green frente a canary, y migraciones de BD compatibles (system variante, multiturno, avanzado)
    {
        "messages": [
            {"role": "system", "content": "Eres un arquitecto de plataforma. Responde en español, directo, con los trade-offs de cada opción."},
            {
                "role": "user",
                "content": "Para nuestra API (Kubernetes, ingress-nginx, unas 300 req/s) ¿blue/green o canary? Cada vez que desplegamos cruzamos los dedos.",
            },
            {
                "role": "assistant",
                "content": """Canary, porque con 300 req/s tienes tráfico de sobra para que un 5 % te dé señal estadística en minutos, y porque el fallo que te hace cruzar los dedos (un 500 que solo aparece con tráfico real) es justo el que blue/green no detecta hasta que ya lo ven todos.

| | Blue/green | Canary |
|---|---|---|
| Qué hace | Dos entornos completos; el tráfico cambia de golpe de uno a otro | Una fracción del tráfico va a la versión nueva; sube por pasos |
| Detecta antes de afectar a todos | Solo lo que prueben los *smoke tests* contra «green» | Sí: errores y latencia con tráfico real sobre el 5 % |
| Rollback | Instantáneo: volver a apuntar a «blue» | Instantáneo: peso a 0 |
| Coste | Doble capacidad durante el despliegue | Un pod o dos extra |
| Compatibilidad entre versiones | No la necesita (nunca conviven) salvo la base de datos | **Obligatoria**: dos versiones sirven a la vez |
| Complejidad | Baja | Media: necesitas métricas por versión y alguien o algo que decida |

**Canary con ingress-nginx, sin instalar nada**: un segundo Deployment (`api-canary`) con la versión nueva y un Ingress idéntico con las anotaciones de canary:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api-canary
  annotations:
    nginx.ingress.kubernetes.io/canary: "true"
    nginx.ingress.kubernetes.io/canary-weight: "5"
spec:
  ingressClassName: nginx
  rules:
    - host: api.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: api-canary
                port: { name: http }
```

Subes `canary-weight` a 25, 50 y 100 mirando dos paneles de Grafana filtrados por la etiqueta `version` de cada Deployment: tasa de 5xx y p99. Si el canary empeora, peso a `0`. Al llegar a 100, actualizas el Deployment principal a la versión nueva y bajas el canary a 0. Es manual, pero ya es infinitamente mejor que cruzar los dedos.

**Cuando quieras que no dependa de una persona mirando Grafana**, Argo Rollouts: sustituyes el `Deployment` por un `Rollout` con los pasos y un análisis que consulta Prometheus; si la tasa de error del canary supera el umbral, revierte solo.

```yaml
strategy:
  canary:
    steps:
      - setWeight: 5
      - pause: { duration: 5m }
      - analysis:
          templates: [{ templateName: error-rate }]
      - setWeight: 25
      - pause: { duration: 10m }
      - setWeight: 50
      - pause: { duration: 10m }
```

Blue/green queda para dos casos: cuando las dos versiones **no pueden** convivir (un cambio de protocolo entre servicios, una migración de datos incompatible), o cuando el tráfico es tan bajo que un 5 % no te dice nada y prefieres probar «green» con tests sintéticos antes de cambiar.

Lo que hace falta para que cualquiera de los dos funcione, y que suele ser el trabajo de verdad: métricas con etiqueta de versión (`version` en los pods y en las métricas RED), y que el Ingress no haga *sticky sessions* por defecto, porque entonces un usuario queda pegado al canary.

Comprobación del montaje antes de usarlo en serio: despliega como canary la **misma** versión que la estable con peso 10 y verifica en Grafana que el canary recibe un 10 % (±2) de las peticiones y que sus métricas son idénticas a las de la estable. Si no ves el 10 %, el enrutado no está funcionando y no quieres descubrirlo con una versión rota.""",
            },
            {
                "role": "user",
                "content": "¿Y las migraciones de base de datos? Con canary tendríamos dos versiones de la app a la vez contra el mismo esquema.",
            },
            {
                "role": "assistant",
                "content": """Esa es la restricción que el canary impone y que conviene aceptar como regla permanente: **cada migración tiene que ser compatible con la versión anterior de la aplicación**. No es un coste del canary; es lo que también necesitas para poder hacer rollback de la app sin deshacer la base de datos, que es algo que ya querías.

El patrón es **expandir y contraer**: un cambio de esquema se reparte en varios despliegues, y en ninguno conviven una app y un esquema que no se entiendan.

Ejemplo: renombrar la columna `nombre` a `nombre_completo` en `clientes`.

| Despliegue | Migración (antes de desplegar la app) | La app |
|---|---|---|
| 1. Expandir | `ALTER TABLE clientes ADD COLUMN nombre_completo text NULL` | Escribe en **las dos** columnas; sigue leyendo `nombre` |
| 2. Migrar datos | `UPDATE clientes SET nombre_completo = nombre WHERE nombre_completo IS NULL` (por lotes) | Lee `nombre_completo`; sigue escribiendo en las dos |
| 3. Contraer | `ALTER TABLE clientes DROP COLUMN nombre` | Solo usa `nombre_completo` |

En cada fila, la versión anterior de la app funciona con el esquema nuevo: durante el canary del despliegue 1, la app vieja ignora la columna nueva; durante el 3, la app del despliegue 2 ya no toca `nombre`. Un `ALTER TABLE RENAME COLUMN` directo rompería la app vieja en el instante de ejecutarse.

Reglas que se derivan:

- **Añadir es seguro, quitar y renombrar no.** Columnas nuevas, `NULL` o con `DEFAULT`; índices con `CREATE INDEX CONCURRENTLY` en Postgres para no bloquear la tabla.
- **Quitar algo va siempre un despliegue después** de que ninguna versión desplegada lo use. Si tienes prisa por el «contraer», no la tengas: la columna sobrante no molesta; la app vieja sin columna sí.
- **La migración corre antes del rollout, una vez, no en cada pod.** Un `Job` de Kubernetes (en Helm, un hook `pre-upgrade`) que ejecuta `alembic upgrade head` o el equivalente y debe terminar bien para que el rollout empiece. Nunca en el arranque del contenedor: tres pods arrancando a la vez son tres migraciones compitiendo, y un pod que reinicia la vuelve a intentar.
- **Las migraciones son idempotentes y con bloqueo** (las herramientas serias, Alembic, Flyway, Prisma Migrate, ya lo hacen con una tabla de versiones), para que un Job reintentado no aplique dos veces.
- **Cambios de comportamiento detrás de *feature flags***, no de versiones: así la lógica nueva se activa cuando el esquema está listo, independientemente de qué pods tengan qué imagen.

Lo que este patrón no cubre y para lo que sí vale blue/green con ventana de mantenimiento: una migración de datos masiva que cambia la semántica (unificar dos tablas, cambiar la clave primaria). Son raras; cuando toque, se planifica como un evento, no como un despliegue.

Comprobación para cada PR con migración, automatizable en CI: levantar la base de datos con el esquema **nuevo** y ejecutar la suite de tests de la versión **anterior** de la app contra él. Si pasa, la migración es compatible hacia atrás y el canary es seguro.""",
            },
        ]
    },
]
