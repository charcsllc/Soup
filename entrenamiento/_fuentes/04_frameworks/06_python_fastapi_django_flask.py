"""04_frameworks / 06: FastAPI, Django y Flask (reparto 13 / 11 / 6)."""

SISTEMA = (
    "Eres un asistente experto en programación, análisis y razonamiento. Respondes en el "
    "idioma del usuario (español por defecto), con precisión y sin relleno, y verificas tu "
    "trabajo antes de responder."
)

ROWS = [
    # ---------------------------------------------------------------- FastAPI (13)
    # 1) Pydantic v2 en FastAPI: migración de validadores.
    {
        "messages": [
            {
                "role": "user",
                "content": "Estoy migrando una API de FastAPI a Pydantic v2 y me rompe medio proyecto (`@validator`, `class Config`, `.dict()`). ¿Cómo queda un modelo de alta de usuario con validación de contraseña y email en minúsculas?",
            },
            {
                "role": "assistant",
                "content": r"""Así queda el modelo en Pydantic v2 (FastAPI ≥ 0.100):

```python
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class UserCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    password: Annotated[str, Field(min_length=12, max_length=128)]
    password_confirm: str
    display_name: Annotated[str, Field(min_length=1, max_length=60)]

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, value: str) -> str:
        return value.lower()

    @field_validator("password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        if value.isalpha() or value.isdigit():
            raise ValueError("la contraseña debe mezclar letras y números")
        return value

    @model_validator(mode="after")
    def passwords_match(self) -> "UserCreate":
        if self.password != self.password_confirm:
            raise ValueError("las contraseñas no coinciden")
        return self


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    display_name: str
```

Equivalencias que te están rompiendo:

| v1 | v2 |
|---|---|
| `@validator("campo")` | `@field_validator("campo")` + `@classmethod` |
| `@root_validator` | `@model_validator(mode="after")` (recibe `self`, ya tipado) |
| `class Config: orm_mode = True` | `model_config = ConfigDict(from_attributes=True)` |
| `.dict()` / `.json()` | `.model_dump()` / `.model_dump_json()` |
| `Model.parse_obj(d)` | `Model.model_validate(d)` |
| `Field(..., example="x")` | `Field(examples=["x"])` (lista) |

Tres detalles que no son cosméticos:

- **`model_validator(mode="after")` corre sobre la instancia ya validada**, así que `self.password` existe y tiene el tipo correcto. En v1 el `root_validator` recibía un dict donde el campo podía faltar si otro validador había fallado antes; ese `values.get("password")` defensivo ya no hace falta.
- **El orden importa**: `field_validator` por campo se ejecuta antes que el `model_validator`. Si la contraseña es débil, el usuario ve ese error y no «no coinciden».
- **`EmailStr` requiere `pip install "pydantic[email]"`**; si falta, Pydantic lanza `ImportError` al importar el módulo, no al validar.

El endpoint no cambia: FastAPI devuelve 422 con `detail` por campo cuando cualquier validador lanza `ValueError`.

```python
@app.post("/users", response_model=UserOut, status_code=201)
def create_user(payload: UserCreate) -> UserOut:
    user = repo.create(email=payload.email, display_name=payload.display_name, password=payload.password)
    return UserOut.model_validate(user)
```

Comprobación rápida con `pytest`:

```python
def test_email_se_normaliza_y_passwords_coinciden():
    u = UserCreate(email="Ana@Example.COM", password="abc123def456", password_confirm="abc123def456", display_name="Ana")
    assert u.email == "ana@example.com"


def test_passwords_distintas_falla():
    with pytest.raises(ValidationError, match="no coinciden"):
        UserCreate(email="a@b.co", password="abc123def456", password_confirm="otra12345678", display_name="Ana")
```

Si usas `bump-pydantic` (herramienta oficial) te reescribe el 80 % mecánico; los `root_validator` con lógica los revisas a mano.""",
            },
        ]
    },
    # 2) async def que bloquea el event loop (usuario trae código).
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Mi API de FastAPI se queda colgada bajo carga, incluso /health deja de responder. Esta es la ruta que más se llama:

```python
@app.get("/precio/{sku}")
async def precio(sku: str):
    r = requests.get(f"https://proveedor.example/api/{sku}", timeout=5)
    time.sleep(0.2)  # el proveedor pide ritmo entre llamadas
    return {"sku": sku, "precio": r.json()["price"]}
```

Con 1 worker. ¿Es el worker? ¿Pongo más?""",
            },
            {
                "role": "assistant",
                "content": r"""No es el worker: es que **estás bloqueando el event loop**. La ruta es `async def`, así que FastAPI la ejecuta directamente en el loop de asyncio, y dentro llamas a dos cosas síncronas: `requests.get` (hasta 5 s) y `time.sleep(0.2)`. Mientras una petición está dentro, **ninguna otra corrutina avanza**, ni `/health`. Por eso cae todo, no solo esa ruta.

Más workers no lo resuelve: cada worker tiene su propio loop y se bloquea igual. Solo subes el número de clientes que pueden estar esperando.

**Reproduce en 30 segundos** (antes de arreglar, para confirmar):

```bash
# terminal 1: 20 peticiones concurrentes
seq 20 | xargs -P 20 -I{} curl -s -o /dev/null http://localhost:8000/precio/SKU{}
# terminal 2: mientras tanto
time curl -s http://localhost:8000/health
```

Si `/health` tarda segundos, es el loop.

**Arreglo mínimo (una palabra):** quita el `async`. FastAPI ejecuta las rutas `def` en un threadpool (40 hilos por defecto, los de anyio) y el loop queda libre:

```python
@app.get("/precio/{sku}")
def precio(sku: str):
    r = requests.get(f"https://proveedor.example/api/{sku}", timeout=5)
    time.sleep(0.2)
    return {"sku": sku, "precio": r.json()["price"]}
```

**Arreglo correcto:** hazla asíncrona de verdad, con un cliente compartido (pool de conexiones y keep-alive) creado en el `lifespan`:

```python
import asyncio
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http = httpx.AsyncClient(base_url="https://proveedor.example", timeout=5)
    app.state.rate = asyncio.Semaphore(5)  # como mucho 5 llamadas en vuelo al proveedor
    yield
    await app.state.http.aclose()


app = FastAPI(lifespan=lifespan)


@app.get("/precio/{sku}")
async def precio(sku: str):
    async with app.state.rate:
        try:
            r = await app.state.http.get(f"/api/{sku}")
            r.raise_for_status()
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"proveedor: {exc}") from exc
    return {"sku": sku, "precio": r.json()["price"]}
```

Dos observaciones sobre tu código original:

- `time.sleep(0.2)` **no limita el ritmo** hacia el proveedor cuando hay concurrencia: 50 peticiones simultáneas hacen 50 llamadas y luego duermen todas a la vez. Un `Semaphore` (o un token bucket si el límite es por segundo) sí acota las llamadas en vuelo.
- El `timeout=5` que tenías es correcto; mantenlo en el cliente. Lo que faltaba era el `raise_for_status()` y traducir el fallo del proveedor a un 502 en vez de dejar que explote como 500.

Regla para el resto de la API: `async def` solo si **todo** lo que hay dentro es `await`-able (httpx, asyncpg, SQLAlchemy async). Si hay `requests`, `psycopg2`, `boto3` síncrono o `time.sleep`, la ruta va como `def`.""",
            },
        ]
    },
    # 3) Inglés: dependencias con yield y Annotated (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": "What's the idiomatic way to share a DB session across dependencies in FastAPI? Right now I open a session inside every function that needs one.",
            },
            {
                "role": "assistant",
                "content": r"""Make the session a dependency with `yield`, and let every other dependency or route ask for it with `Depends`. FastAPI caches a dependency's result per request, so all of them receive the **same** session object.

```python
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, FastAPI
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

engine = create_engine("postgresql+psycopg://app:app@localhost/app", pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session  # context manager closes it even if the route raises


SessionDep = Annotated[Session, Depends(get_session)]
```

Now use the alias everywhere:

```python
def get_current_user(session: SessionDep, token: TokenDep) -> User:
    user = session.get(User, decode(token).sub)
    if user is None:
        raise HTTPException(401)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


@app.get("/orders")
def list_orders(session: SessionDep, user: CurrentUser) -> list[OrderOut]:
    rows = session.execute(select(Order).where(Order.owner_id == user.id)).scalars()
    return [OrderOut.model_validate(r) for r in rows]
```

What you get:

- **One session per request.** `get_current_user` and `list_orders` both declare `SessionDep`, but `get_session` runs once; the second `Depends` returns the cached value (`use_cache=True` is the default). Same transaction, same identity map, no "object attached to a different session" surprises.
- **Guaranteed cleanup.** The code after `yield` runs when the request finishes, including when the handler raises. Keep that exit code small (close, maybe rollback); business logic does not belong there.
- **`Annotated` aliases** keep signatures short and let you change the implementation in one place.

If you want transactional routes (commit on success, rollback on error), do it in the dependency rather than in every handler:

```python
def get_tx_session() -> Iterator[Session]:
    with SessionLocal() as session:
        with session.begin():
            yield session
```

`session.begin()` commits when the block exits normally and rolls back on exception.

Tests override the dependency without touching the routes:

```python
app.dependency_overrides[get_session] = lambda: sqlite_session
```""",
            },
            {
                "role": "user",
                "content": "And for background jobs or a CLI command that don't go through a request? Depends won't work there.",
            },
            {
                "role": "assistant",
                "content": r"""Correct: `Depends` only exists inside the request lifecycle. Outside it, call the same context manager yourself. That is the reason to write the session factory as a plain context manager first and wrap it as a FastAPI dependency second, instead of putting the logic in the dependency.

```python
from contextlib import contextmanager


@contextmanager
def session_scope() -> Iterator[Session]:
    with SessionLocal() as session:
        with session.begin():
            yield session


def get_tx_session() -> Iterator[Session]:  # FastAPI adapter, one line
    with session_scope() as session:
        yield session
```

Then:

```python
# CLI (typer, argparse, whatever)
def rebuild_stats() -> None:
    with session_scope() as session:
        recompute_stats(session)


# BackgroundTasks: never reuse the request's session
@app.post("/orders")
def create_order(payload: OrderIn, session: SessionDep, tasks: BackgroundTasks) -> OrderOut:
    order = Order(**payload.model_dump())
    session.add(order)
    session.flush()
    tasks.add_task(send_confirmation, order.id)
    return OrderOut.model_validate(order)


def send_confirmation(order_id: int) -> None:
    with session_scope() as session:
        order = session.get(Order, order_id)
        mailer.send(order.email, render(order))
```

Two rules that follow from this:

1. **Pass ids, not ORM objects, into background work.** The request's session is closed by the time the task runs; an `Order` instance from it would be detached and lazy loads would fail. Reload it inside a fresh `session_scope()`.
2. **Business functions take a `Session` parameter** (`recompute_stats(session)`), not a dependency. The same function then serves the route, the CLI and the tests, and the caller decides where the session comes from.""",
            },
        ]
    },
    # 4) BackgroundTasks vs cola durable (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": "Quiero mandar un email de bienvenida después de registrar al usuario sin que la petición tarde más. ¿Me sirve BackgroundTasks de FastAPI?",
            },
            {
                "role": "assistant",
                "content": r"""Sí, para un email de bienvenida es justo el caso de uso. `BackgroundTasks` ejecuta la función **después de enviar la respuesta**, en el mismo proceso.

```python
from fastapi import BackgroundTasks, FastAPI

app = FastAPI()


def send_welcome_email(email: str, name: str) -> None:
    mailer.send(to=email, template="welcome", context={"name": name})


@app.post("/users", status_code=201)
def create_user(payload: UserCreate, tasks: BackgroundTasks, session: SessionDep) -> UserOut:
    user = repo.create(session, payload)
    session.commit()
    tasks.add_task(send_welcome_email, user.email, user.display_name)
    return UserOut.model_validate(user)
```

Detalles:

- Si la función de la tarea es `def`, corre en el threadpool; si es `async def`, en el loop. Un cliente SMTP síncrono va como `def`.
- Haz el `commit()` **antes** de encolar: si la tarea lee el usuario de la base de datos y la transacción aún no está confirmada, no lo encuentra.
- Pasa datos simples (`email`, `name`), no el objeto ORM: la sesión de la petición se cierra antes de que la tarea se ejecute.

Lo que `BackgroundTasks` **no** garantiza: si el proceso se reinicia, se despliega o se cae mientras la tarea está en cola o a medias, la tarea se pierde sin rastro. Para un email de bienvenida es aceptable; para cualquier cosa que no pueda perderse, no.""",
            },
            {
                "role": "user",
                "content": "Vale, pero también mando el PDF del contrato firmado por email. Eso no se puede perder si se reinicia el pod en un despliegue.",
            },
            {
                "role": "assistant",
                "content": r"""Entonces ese envío **no va en `BackgroundTasks`**: necesita una cola durable con reintentos. El de bienvenida puede seguir donde está; mueve solo el contrato.

Con Celery sobre Redis (el broker que probablemente ya tengas):

```python
# tasks.py
from celery import Celery

celery_app = Celery("app", broker="redis://redis:6379/0")
celery_app.conf.task_acks_late = True          # el mensaje se confirma al TERMINAR, no al recibir
celery_app.conf.worker_prefetch_multiplier = 1  # no acapares mensajes que luego se pierden si muere el worker


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_backoff_max=600, max_retries=8)
def send_contract(self, contract_id: int) -> None:
    with session_scope() as session:
        contract = session.get(Contract, contract_id)
        if contract is None or contract.sent_at is not None:
            return  # idempotente: ya enviado o inexistente
        pdf = storage.read(contract.pdf_key)
        mailer.send(to=contract.email, template="contract", attachments=[("contrato.pdf", pdf)])
        contract.sent_at = datetime.now(timezone.utc)
```

Y en la ruta:

```python
@app.post("/contracts/{contract_id}/sign")
def sign_contract(contract_id: int, session: SessionDep) -> ContractOut:
    contract = repo.sign(session, contract_id)
    session.commit()
    send_contract.delay(contract.id)
    return ContractOut.model_validate(contract)
```

Por qué cada pieza:

- **`task_acks_late` + `prefetch_multiplier=1`**: si el pod muere a mitad de envío, el mensaje vuelve a la cola y otro worker lo reintenta. Sin `acks_late`, Redis lo da por entregado en cuanto el worker lo recibe.
- **Reintentos con backoff exponencial** (`retry_backoff=True`, tope 10 min): un SMTP caído 20 minutos no pierde el envío.
- **Idempotencia con `sent_at`**: con reintentos y `acks_late`, la tarea puede ejecutarse dos veces (worker muere después de enviar y antes de confirmar). El flag evita el segundo email. Para un contrato, un duplicado raro es mejor que un envío perdido.
- **`commit()` antes de `delay()`**: el worker puede arrancar en milisegundos; si la transacción no está confirmada, verá `None`.

Queda una ventana diminuta: commit hecho y el proceso muere **antes** del `delay()`. Si tampoco la aceptas, el siguiente escalón es el patrón *outbox*: escribes una fila `outbox(contract_id, pending)` en la misma transacción y un proceso periódico encola lo pendiente. Primero mide si esa ventana te ocurre alguna vez; casi nunca compensa el outbox desde el día uno.

Despliegue: `celery -A tasks worker --concurrency=4 --loglevel=info` como un Deployment aparte, con `terminationGracePeriodSeconds` mayor que el envío más lento para que el `SIGTERM` deje terminar la tarea en curso.""",
            },
        ]
    },
    # 5) lifespan en vez de on_event (usuario trae warning).
    {
        "messages": [
            {
                "role": "user",
                "content": "Al arrancar me sale `DeprecationWarning: on_event is deprecated, use lifespan event handlers instead.` Tengo un `@app.on_event(\"startup\")` que crea un cliente httpx y otro de shutdown que lo cierra. ¿Cómo lo paso a lifespan?",
            },
            {
                "role": "assistant",
                "content": r"""Los dos handlers se fusionan en una sola función `async` decorada con `asynccontextmanager`: lo que va antes del `yield` es el arranque, lo que va después es la parada.

```python
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http = httpx.AsyncClient(base_url="https://api.proveedor.example", timeout=10)
    yield
    await app.state.http.aclose()


app = FastAPI(lifespan=lifespan)
```

Y en las rutas, accede por `request.app.state`:

```python
from fastapi import Request


@app.get("/ping-proveedor")
async def ping(request: Request):
    r = await request.app.state.http.get("/health")
    return {"status": r.status_code}
```

Ventajas respecto a `on_event`, además de quitar el warning:

- **Un solo lugar** para recursos emparejados (abrir/cerrar). Con dos decoradores era fácil crear el cliente en startup y olvidar el `aclose()`.
- **Si el arranque falla** (por ejemplo, la base de datos no responde), la excepción sale antes del `yield` y uvicorn no empieza a aceptar tráfico. Con `on_event` el error también paraba el arranque, pero no podías encadenar varios recursos con `async with` de forma natural.
- **Varios recursos** se anidan sin más:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient(timeout=10) as http, engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        app.state.http = http
        yield
```

Dos avisos:

- `lifespan` y `on_event` **no se pueden mezclar**: si pasas `lifespan=`, los `on_event` restantes se ignoran. Migra todos a la vez.
- En tests, `httpx.AsyncClient(transport=ASGITransport(app=app))` **no ejecuta el lifespan**. Usa `TestClient` como context manager (`with TestClient(app) as client:`) o `asgi-lifespan` (`LifespanManager`) si tus tests son async.""",
            },
        ]
    },
    # 6) OAuth2 + JWT completo (system exacto).
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Necesito autenticación en FastAPI con usuario/contraseña y JWT: endpoint de login, dependencia que me dé el usuario actual y que Swagger pueda probarlo. ¿Cómo lo armarías hoy, sin librerías abandonadas?",
            },
            {
                "role": "assistant",
                "content": r"""Flujo OAuth2 «password» con token Bearer. Dependencias: `pyjwt`, `pwdlib[argon2]` (lo que recomienda la documentación actual de FastAPI; `passlib` está sin mantener y rompe con bcrypt ≥ 4.1) y `python-multipart` (el formulario de login).

```python
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pwdlib import PasswordHash
from pydantic import BaseModel

SECRET_KEY = settings.jwt_secret  # 32+ bytes aleatorios, desde el entorno
ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = 30

password_hash = PasswordHash.recommended()  # argon2id
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
app = FastAPI()


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class User(BaseModel):
    username: str
    disabled: bool = False


class UserInDB(User):
    hashed_password: str


# Sustituye por tu repositorio; la forma importa, no el almacenamiento.
USERS: dict[str, UserInDB] = {
    "ana": UserInDB(username="ana", hashed_password=password_hash.hash("una-contraseña-larga")),
}


def authenticate(username: str, password: str) -> User | None:
    user = USERS.get(username)
    if user is None or not password_hash.verify(password, user.hashed_password):
        return None
    return User(username=user.username, disabled=user.disabled)


def create_access_token(subject: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": subject, "iat": now, "exp": now + timedelta(minutes=ACCESS_TOKEN_MINUTES)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.InvalidTokenError as exc:  # incluye expirado y firma inválida
        raise credentials_error from exc
    username = payload.get("sub")
    user = USERS.get(username) if username else None
    if user is None or user.disabled:
        raise credentials_error
    return User(username=user.username, disabled=user.disabled)


CurrentUser = Annotated[User, Depends(get_current_user)]


@app.post("/token")
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()]) -> Token:
    user = authenticate(form.username, form.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password",
                            headers={"WWW-Authenticate": "Bearer"})
    return Token(access_token=create_access_token(user.username))


@app.get("/me")
def me(user: CurrentUser) -> User:
    return user
```

Por qué está así:

- **`OAuth2PasswordBearer(tokenUrl="token")`** hace dos cosas: extrae el header `Authorization: Bearer <token>` (401 si falta) y declara el esquema en OpenAPI, así que el botón «Authorize» de Swagger pide usuario y contraseña, llama a `/token` y manda el Bearer en las siguientes llamadas.
- **`OAuth2PasswordRequestForm`** espera `application/x-www-form-urlencoded` con `username` y `password`, como manda la especificación. Si tu frontend manda JSON, crea tu propio modelo; pierdes el flujo automático de Swagger, nada más.
- **`exp` corto (30 min)**. Un JWT no se puede revocar; la única mitigación es que caduque pronto. Si necesitas sesiones largas, añade un *refresh token* opaco guardado en base de datos (ese sí se revoca).
- **`algorithms=[ALGORITHM]` explícito en `decode`**: evita el ataque clásico de `alg: none` o de cambiar a otro algoritmo.
- **El mismo 401 para «usuario no existe» y «contraseña incorrecta»**: no reveles cuál de los dos falló.
- **Hasheo con argon2id** (`PasswordHash.recommended()`), que es lo que recomienda OWASP hoy; `verify` tarda unas decenas de ms a propósito.

Prueba mínima:

```python
from fastapi.testclient import TestClient

client = TestClient(app)


def test_login_y_me():
    r = client.post("/token", data={"username": "ana", "password": "una-contraseña-larga"})
    token = r.json()["access_token"]
    r = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200 and r.json()["username"] == "ana"


def test_sin_token_401():
    assert client.get("/me").status_code == 401
```

Lo que no cubre y debes decidir aparte: límite de intentos en `/token` (p. ej. `slowapi` o en el proxy), rotación de `SECRET_KEY` (usa `kid` y varias claves si la rotas), y `HTTPS` obligatorio: un Bearer por HTTP es una contraseña en claro.""",
            },
        ]
    },
    # 7) Errores: HTTPException vs handlers; cambiar 422 (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Qué diferencia hay entre lanzar `HTTPException` y registrar mi propia excepción con `@app.exception_handler`? ¿Cuándo usar cada una?",
            },
            {
                "role": "assistant",
                "content": r"""`HTTPException` es «quiero devolver este código y este mensaje ahora mismo». Un handler propio es «mi dominio lanza esta excepción y yo decido centralizadamente cómo se traduce a HTTP».

**`HTTPException`**: directo, para casos locales de una ruta.

```python
@app.get("/orders/{order_id}")
def get_order(order_id: int, session: SessionDep) -> OrderOut:
    order = session.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return OrderOut.model_validate(order)
```

**Excepción de dominio + handler**: cuando la lógica no está en la ruta (servicios, repositorios) y no quieres que esas capas sepan de HTTP.

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class DomainError(Exception):
    status_code = 400
    code = "domain_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class OrderNotFound(DomainError):
    status_code = 404
    code = "order_not_found"


class InsufficientStock(DomainError):
    status_code = 409
    code = "insufficient_stock"


app = FastAPI()


@app.exception_handler(DomainError)
async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": exc.code, "message": exc.message})
```

El servicio lanza `InsufficientStock("only 2 left")` sin importar `fastapi`, y la ruta ni siquiera lo captura. Un solo handler para toda la jerarquía porque FastAPI resuelve por `isinstance`.

Criterio:

| Situación | Usa |
|---|---|
| Comprobación puntual dentro de la ruta | `HTTPException` |
| Error que nace en un servicio/repositorio | excepción de dominio + handler |
| Formato de error uniforme para toda la API | handler (también para `HTTPException`, ver abajo) |
| Librería que lanza algo propio (p. ej. `jwt.InvalidTokenError`) | handler para esa clase |

Si quieres que **todos** los errores tengan la misma forma, registra también un handler para `HTTPException` (el de Starlette, que es la base):

```python
from starlette.exceptions import HTTPException as StarletteHTTPException


@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": "http_error", "message": exc.detail},
                        headers=exc.headers)
```

Conserva `headers=exc.headers`: ahí viaja `WWW-Authenticate` en los 401.""",
            },
            {
                "role": "user",
                "content": "Y los errores de validación: el cliente móvil espera 400 con `{error, message, fields}` y FastAPI devuelve 422 con `detail`. ¿Lo cambio?",
            },
            {
                "role": "assistant",
                "content": r"""Sí, cámbialo, y la razón es **el contrato con el cliente**, no el código en sí: 422 es correcto según la especificación (JSON válido, contenido inválido), pero una app ya instalada que espera 400 es más cara de cambiar que un handler.

```python
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def _field_name(loc: tuple) -> str:
    # loc llega como ("body", "address", "zip") o ("query", "page"); el primer tramo es la fuente
    parts = [str(p) for p in loc[1:]] or [str(loc[0])]
    return ".".join(parts)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    fields: dict[str, str] = {}
    for error in exc.errors():
        fields.setdefault(_field_name(tuple(error["loc"])), error["msg"])
    return JSONResponse(
        status_code=400,
        content={"error": "validation_error", "message": "Request validation failed", "fields": fields},
    )
```

Ejemplo de salida para un `POST /users` con email malo y contraseña corta:

```json
{"error": "validation_error", "message": "Request validation failed",
 "fields": {"email": "value is not a valid email address: ...", "password": "String should have at least 12 characters"}}
```

Tres decisiones:

- **Construyo la respuesta a mano** en vez de devolver `exc.errors()`. En Pydantic v2 cada error trae `input` (el valor recibido, que puede ser una contraseña) y a veces `ctx` con objetos no serializables. Devolverlo tal cual filtra datos y puede romper la serialización.
- **`setdefault`**: si un campo tiene dos errores, el cliente ve el primero. Para formularios es lo que se espera; si quieres todos, cambia a `dict[str, list[str]]`.
- **No toco `ResponseValidationError`**: ese significa que *tu* respuesta no cumple el `response_model`, es un bug del servidor y debe seguir siendo 500.

Un efecto secundario: Swagger seguirá mostrando `422` en cada ruta porque el schema se genera antes de conocer tu handler. Si el equipo móvil lee la documentación, decláralo donde importe:

```python
@app.post("/users", responses={400: {"model": ValidationErrorOut}, 422: {"include_in_schema": False}})
```

O bien quítalo globalmente recorriendo `app.openapi()` una vez tras crear la app y borrando la entrada `"422"` de cada operación; es más código y solo compensa si tienes decenas de rutas.""",
            },
        ]
    },
    # 8) Testing async con httpx + override de dependencia.
    {
        "messages": [
            {
                "role": "user",
                "content": "Tenemos tests con TestClient pero ahora las rutas son async y usan SQLAlchemy async contra Postgres. ¿Cómo hacemos los tests con httpx y una SQLite en memoria para que corran rápido en CI?",
            },
            {
                "role": "assistant",
                "content": r"""Tres piezas: `httpx.AsyncClient` con `ASGITransport` (desde httpx 0.27 el parámetro `app=` está obsoleto), `app.dependency_overrides` para inyectar la sesión de pruebas y `pytest-asyncio` en modo `auto`.

```python
# tests/conftest.py
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db import Base, get_session
from app.main import app


@pytest.fixture
async def engine():
    # StaticPool: una sola conexión compartida; sin él, cada conexión a ":memory:" es una BD distinta
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool,
                                 connect_args={"check_same_thread": False})
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(engine) -> AsyncIterator[AsyncSession]:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest.fixture
async def client(session) -> AsyncIterator[AsyncClient]:
    async def override_session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
```

```ini
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
```

Y un test:

```python
async def test_crear_y_leer_pedido(client, session):
    r = await client.post("/orders", json={"sku": "A1", "qty": 2})
    assert r.status_code == 201
    order_id = r.json()["id"]

    r = await client.get(f"/orders/{order_id}")
    assert r.json()["qty"] == 2
```

Lo que hay que saber para que esto no les muerda:

- **`StaticPool` es obligatorio con `:memory:`.** Sin él, SQLAlchemy abre una conexión nueva por sesión y cada una ve una base de datos vacía distinta.
- **`ASGITransport` no ejecuta el `lifespan`.** Si crean recursos ahí (cliente HTTP, pools), en tests no existirán. Opciones: `asgi-lifespan` (`async with LifespanManager(app):`) o mover esos recursos a dependencias que se puedan sobreescribir.
- **`dependency_overrides.clear()` en el teardown**, o un test contamina al siguiente.
- **`expire_on_commit=False`** evita que, tras un `commit()`, acceder a un atributo dispare una carga perezosa en contexto async (`MissingGreenlet`).
- **SQLite no es Postgres.** Sirve para lógica de rutas y serialización. Cualquier cosa con `JSONB`, `ARRAY`, `FOR UPDATE`, ventanas o `ON CONFLICT` específico necesita Postgres real; para eso usen `testcontainers` en un job aparte y márquenlo `@pytest.mark.integration`.

Nota sobre `TestClient`: sigue funcionando con rutas `async` (levanta su propio loop en un hilo). El problema aparece cuando mezclan `TestClient` con fixtures `async` que comparten el motor: dos loops, un motor, errores de «attached to a different loop». Por eso, si la base de datos es async, el cliente también.""",
            },
        ]
    },
    # 9) MissingGreenlet con SQLAlchemy async (usuario trae traza).
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Esta ruta funciona a veces y a veces da 500 con esto:

```
sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called; can't call await_only() here. Was IO attempted in an unexpected place? (Background on this error at: https://sqlalche.me/e/20/xd2s)
```

```python
@router.get("/pedidos/{pedido_id}", response_model=PedidoOut)
async def get_pedido(pedido_id: int, session: AsyncSession = Depends(get_session)):
    pedido = await session.get(Pedido, pedido_id)
    if not pedido:
        raise HTTPException(404)
    return pedido
```

`PedidoOut` tiene `lineas: list[LineaOut]`. ¿Por qué «a veces»?""",
            },
            {
                "role": "assistant",
                "content": r"""El 500 no viene de tu ruta: viene de **FastAPI serializando `pedido` con `PedidoOut`**. Al leer `pedido.lineas` para rellenar `lineas: list[LineaOut]`, SQLAlchemy intenta una carga perezosa (lazy load), y en modo async eso solo puede ocurrir dentro de un `await`. Fuera de él lanza `MissingGreenlet`.

El «a veces» es el identity map: si en esa misma sesión las líneas ya estaban cargadas (otra consulta anterior, o el objeto ya en memoria), no hay I/O y la serialización pasa. Si la sesión es nueva o un `commit()` expiró los atributos (`expire_on_commit=True` es el default), hay I/O y explota. No es aleatorio; depende del historial de la sesión.

**Arreglo correcto:** carga la relación en la consulta.

```python
from sqlalchemy import select
from sqlalchemy.orm import selectinload


@router.get("/pedidos/{pedido_id}", response_model=PedidoOut)
async def get_pedido(pedido_id: int, session: SessionDep):
    stmt = select(Pedido).where(Pedido.id == pedido_id).options(selectinload(Pedido.lineas))
    pedido = (await session.execute(stmt)).scalar_one_or_none()
    if pedido is None:
        raise HTTPException(404)
    return pedido
```

`selectinload` hace una segunda consulta `WHERE pedido_id IN (...)`; para una colección es mejor que `joinedload`, que multiplica filas del padre por cada línea.

**Para que no vuelva a pasar en otra ruta**, dos cambios en la configuración:

```python
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, relationship


class Base(AsyncAttrs, DeclarativeBase):
    pass


class Pedido(Base):
    __tablename__ = "pedidos"
    lineas: Mapped[list["Linea"]] = relationship(lazy="raise")


SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
```

- `lazy="raise"` convierte cualquier carga perezosa accidental en `InvalidRequestError: 'Pedido.lineas' is not available due to lazy='raise'` **siempre**, con el nombre de la relación en el mensaje. Prefiero un error determinista en desarrollo a un 500 intermitente en producción.
- `expire_on_commit=False` evita que un `commit()` deje el objeto «vacío» y obligue a recargar al serializar.
- `AsyncAttrs` te da `await pedido.awaitable_attrs.lineas` para los casos en que quieres cargar bajo demanda sin reescribir la consulta.

Test de regresión (con la fixture de sesión async que ya tengas):

```python
async def test_get_pedido_incluye_lineas(client, session):
    pedido = Pedido(lineas=[Linea(sku="A1", qty=1), Linea(sku="B2", qty=3)])
    session.add(pedido)
    await session.commit()

    r = await client.get(f"/pedidos/{pedido.id}")
    assert r.status_code == 200
    assert len(r.json()["lineas"]) == 2
```

Con `lazy="raise"`, este test también falla si alguien quita el `selectinload` en el futuro, que es lo que quieres.""",
            },
        ]
    },
    # 10) Workers de uvicorn/gunicorn (system exacto).
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "¿Cuántos workers de uvicorn pongo para una API FastAPI en un contenedor con 2 CPU y 1 GB? ¿Y necesito gunicorn delante o ya no?",
            },
            {
                "role": "assistant",
                "content": r"""**2 workers** (uno por CPU), y gunicorn no te hace falta en un contenedor orquestado.

**Por qué 2 y no «(2 × CPU) + 1».** Esa fórmula es de gunicorn para workers síncronos, que atienden una petición cada uno y conviene sobresuscribir. Un worker de uvicorn es un event loop que atiende cientos de conexiones concurrentes; más workers que núcleos solo añade cambios de contexto y memoria. La excepción: si tienes muchas rutas `def` (síncronas, van al threadpool de 40 hilos) y saturan la CPU, 3 puede rendir algo más. Mídelo, no lo supongas.

**La memoria manda más que la CPU.** Cada worker carga la app completa. Mide el RSS de un proceso en caliente:

```bash
uvicorn app.main:app --workers 1 &
sleep 5 && curl -s localhost:8000/health && ps -o rss= -p $(pgrep -f "uvicorn app.main") | awk '{print $1/1024 " MB"}'
```

Si da 200 MB, 2 workers son 400 MB y cabes en 1 GB con margen para picos. Si da 400 MB, con 2 workers ya estás al límite y el OOM killer mata el contenedor entero, lo que es mucho peor que atender más lento.

**Comando:**

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 --timeout-graceful-shutdown 20 --no-access-log
```

- `--timeout-graceful-shutdown` deja terminar las peticiones en curso cuando Kubernetes manda `SIGTERM`.
- `--no-access-log` si ya tienes logs en el ingress; el access log de uvicorn en stdout cuesta CPU a volumen alto.

**El efecto de segundo orden: el pool de base de datos es por proceso.** Con 2 workers y los defaults de SQLAlchemy (5 + 10 de overflow) la base de datos puede ver 30 conexiones *por réplica*. Multiplica por réplicas y compáralo con `max_connections` de Postgres. Si hay 10 réplicas, ya son 300; ahí pon PgBouncer o baja `pool_size`.

**¿Gunicorn?** Aportaba supervisión de workers, recarga sin corte con `SIGHUP` y `--max-requests` para fugas de memoria. Hoy:

- uvicorn `--workers` tiene su propio supervisor (reescrito en 0.30) que reinicia workers caídos.
- En Kubernetes/ECS, el despliegue sin corte lo hace el orquestador (rolling update), no el servidor de aplicaciones.
- La clase `uvicorn.workers.UvicornWorker` está **deprecada** dentro de uvicorn; si de verdad lo quieres, instala `uvicorn-worker` y usa `-k uvicorn_worker.UvicornWorker`.

Gunicorn sigue teniendo sentido en una VM sin orquestador donde quieras recargar con `kill -HUP` sin perder peticiones. En un pod, prefiere **1-2 workers por pod y escalar pods**: el HPA ve CPU y memoria por pod, y los límites de recursos son honestos.

Un aviso si pasas de 1 a 2 workers: cualquier estado en memoria (caché con `dict`, rate limiting por proceso, un contador) deja de ser compartido. Si tienes algo así, va a Redis antes de subir los workers.""",
            },
        ]
    },
    # 11) Usuario en inglés pide respuesta en español: OpenAPI.
    {
        "messages": [
            {
                "role": "user",
                "content": "How do I document error responses and request examples properly in FastAPI's OpenAPI? Please answer in Spanish, the rest of my team reads it better that way.",
            },
            {
                "role": "assistant",
                "content": r"""Cuatro mecanismos, de más usado a menos:

**1. Errores por ruta con `responses=`.** Declara un modelo para el error y lo referencias por código:

```python
from pydantic import BaseModel


class Problem(BaseModel):
    error: str
    message: str


@app.get(
    "/orders/{order_id}",
    response_model=OrderOut,
    responses={
        404: {"model": Problem, "description": "El pedido no existe"},
        409: {"model": Problem, "description": "El pedido está bloqueado por otro proceso"},
    },
)
def get_order(order_id: int) -> OrderOut:
    return service.get(order_id)
```

Swagger muestra cada código con su schema y descripción. Esto es solo documentación: sigues teniendo que lanzar el error con ese formato (handler de excepciones).

**2. Ejemplos en el modelo con `Field(examples=[])`** (Pydantic v2; en v1 era `example=` en singular):

```python
class OrderIn(BaseModel):
    sku: str = Field(examples=["SKU-1234"])
    qty: int = Field(gt=0, examples=[2])
```

El ejemplo del cuerpo se construye combinando los de cada campo.

**3. Varios ejemplos con nombre en el cuerpo**, con `openapi_examples` en `Body()`:

```python
from typing import Annotated

from fastapi import Body


@app.post("/orders", status_code=201)
def create_order(
    payload: Annotated[
        OrderIn,
        Body(openapi_examples={
            "normal": {"summary": "Pedido habitual", "value": {"sku": "SKU-1234", "qty": 2}},
            "invalido": {"summary": "Cantidad cero (devuelve 400)", "value": {"sku": "SKU-1234", "qty": 0}},
        }),
    ],
) -> OrderOut:
    return service.create(payload)
```

Swagger muestra un desplegable para elegir el ejemplo. Útil para enseñar el caso de error junto al válido.

**4. Metadatos de la app y agrupación**: `tags` por ruta y `openapi_tags` para describirlos, `summary`/`description` por operación (el docstring de la función también se usa como `description` y admite Markdown), e `include_in_schema=False` para rutas internas como `/debug/*`.

```python
app = FastAPI(
    title="Orders API",
    version="2.3.0",
    openapi_tags=[{"name": "orders", "description": "Pedidos y sus líneas"}],
)
```

Para exportar el documento y versionarlo en el repositorio (o generar clientes con `openapi-generator`):

```bash
python -c "import json; from app.main import app; print(json.dumps(app.openapi(), indent=2))" > openapi.json
```

Un detalle: FastAPI añade `422` automáticamente a cada ruta con cuerpo o parámetros. Si tu API devuelve otro código para validación, decláralo con `responses` y oculta el 422 con `422: {"include_in_schema": False}`.""",
            },
        ]
    },
    # 12) Paginación reutilizable + settings (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo 15 endpoints de listado y en cada uno repito `page: int = 1, page_size: int = 20` con sus validaciones. ¿Cómo evito repetirlo en FastAPI?",
            },
            {
                "role": "assistant",
                "content": r"""Convierte la paginación en una dependencia: una clase con los parámetros de query y sus límites, y un alias `Annotated` para pedirla en cada ruta.

```python
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query


@dataclass(frozen=True)
class Pagination:
    page: Annotated[int, Query(ge=1)] = 1
    page_size: Annotated[int, Query(ge=1, le=100)] = 20

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


PageDep = Annotated[Pagination, Depends()]
```

`Depends()` sin argumento le dice a FastAPI que use la propia anotación (`Pagination`) como dependencia: inspecciona `__init__`, convierte cada parámetro en un query param con sus validaciones, y aparece en Swagger igual que si lo hubieras escrito a mano.

Las rutas quedan así:

```python
@app.get("/orders")
def list_orders(page: PageDep, session: SessionDep) -> list[OrderOut]:
    stmt = select(Order).order_by(Order.id).offset(page.offset).limit(page.page_size)
    return [OrderOut.model_validate(o) for o in session.execute(stmt).scalars()]
```

`?page=0` devuelve 422 con `Input should be greater than or equal to 1`; `?page_size=500` lo mismo con `less than or equal to 100`. Un solo sitio para cambiar los límites.

Si además quieres devolver el total y los metadatos, añade un modelo genérico de respuesta:

```python
from pydantic import BaseModel


class Page[T](BaseModel):  # Python 3.12; en 3.10/3.11 usa Generic[T]
    items: list[T]
    page: int
    page_size: int
    total: int


@app.get("/orders")
def list_orders(page: PageDep, session: SessionDep) -> Page[OrderOut]:
    total = session.scalar(select(func.count()).select_from(Order))
    stmt = select(Order).order_by(Order.id).offset(page.offset).limit(page.page_size)
    items = [OrderOut.model_validate(o) for o in session.execute(stmt).scalars()]
    return Page(items=items, page=page.page, page_size=page.page_size, total=total)
```

Si las tablas crecen a millones de filas, `offset` se vuelve lento (la base de datos recorre y descarta las filas saltadas); ahí cambias a paginación por cursor (`WHERE id > :last_id LIMIT n`), pero la dependencia sigue siendo el sitio donde vive ese cambio.""",
            },
            {
                "role": "user",
                "content": "Perfecto. ¿Y si el page_size máximo tiene que venir de configuración por entorno? En staging quiero permitir 1000 para pruebas.",
            },
            {
                "role": "assistant",
                "content": r"""Entonces el límite deja de ser una constante en `Query(le=100)` y pasa a validarse contra la configuración. Dos piezas: `pydantic-settings` para leer el entorno y una dependencia de settings cacheada.

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_")

    max_page_size: int = 100
    database_url: str


@lru_cache
def get_settings() -> Settings:
    return Settings()


SettingsDep = Annotated[Settings, Depends(get_settings)]
```

`APP_MAX_PAGE_SIZE=1000` en el entorno de staging y listo. `lru_cache` hace que `Settings()` se construya una vez por proceso (leer `.env` y validar en cada petición es tirar tiempo).

La dependencia de paginación ahora recibe settings y valida el máximo ella misma:

```python
from fastapi import HTTPException


class Pagination:
    def __init__(
        self,
        settings: SettingsDep,
        page: Annotated[int, Query(ge=1)] = 1,
        page_size: Annotated[int, Query(ge=1)] = 20,
    ) -> None:
        if page_size > settings.max_page_size:
            raise HTTPException(status_code=422, detail=f"page_size must be <= {settings.max_page_size}")
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size
```

Pierdes el `le=` en Swagger (el schema no conoce el valor en tiempo de ejecución), pero ganas un límite real por entorno. Si quieres que la documentación lo muestre, añade `description=f"máximo configurado por entorno"` al `Query`.

En tests, sobreescribe settings sin tocar variables de entorno:

```python
app.dependency_overrides[get_settings] = lambda: Settings(max_page_size=5, database_url="sqlite://")


def test_page_size_respeta_configuracion(client):
    assert client.get("/orders?page_size=6").status_code == 422
    assert client.get("/orders?page_size=5").status_code == 200
```

`lru_cache` y `dependency_overrides` conviven bien: el override reemplaza la función entera, así que la caché de la real no interfiere.""",
            },
        ]
    },
    # 13) Comparación: FastAPI vs Django vs Flask (system exacto).
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Arrancamos un backend nuevo: panel interno de administración, usuarios con roles, facturación mensual y una API REST para la app móvil. Somos 3 personas. ¿FastAPI, Django o Flask? Queremos decidirlo esta semana.",
            },
            {
                "role": "assistant",
                "content": r"""**Django**, y la razón es la lista que has escrito: panel de administración, usuarios con roles y facturación son tres cosas que Django trae resueltas y que en FastAPI o Flask construiríais a mano. Con 3 personas, eso son semanas que no diferencian vuestro producto.

| Necesidad | Django | FastAPI | Flask |
|---|---|---|---|
| Panel de administración | `django.contrib.admin`, listo en una tarde | a mano o SQLAdmin (limitado) | a mano o Flask-Admin (poco mantenido) |
| Usuarios, roles, permisos | `contrib.auth`: grupos, permisos por modelo, sesiones | a mano (JWT, tablas, roles) | Flask-Login + a mano |
| ORM + migraciones | integrados, `makemigrations` | SQLAlchemy + Alembic (dos librerías a configurar) | SQLAlchemy + Alembic |
| API REST | DRF o Django Ninja | nativo, excelente | a mano o Flask-RESTX |
| Tareas periódicas (facturación) | Celery beat, bien integrado | Celery/arq, igual de bien | Celery |
| Async/I/O concurrente | parcial (ORM mayormente síncrono) | nativo | parcial |
| Opiniones y estructura | muchas; menos decisiones | pocas; tú eliges todo | ninguna; tú eliges todo |

**Cuándo habría dicho otra cosa:**

- **FastAPI** si fuera una API pura sin panel, con mucha I/O concurrente (agregar llamadas a terceros, websockets, streaming) y un equipo cómodo con async. Allí Django os haría pelear con el ORM síncrono.
- **Flask** para un servicio pequeño con dos endpoints o un prototipo de una semana. Para un producto con cuatro áreas funcionales, su falta de opiniones significa que las decisiones las tomáis vosotros, una por una.

**Cómo arrancarlo para no arrepentiros:**

1. `django-admin startproject config .` y una app por dominio: `accounts`, `billing`, `catalog`. No una app `core` que lo absorbe todo.
2. API bajo `/api/v1/` con **DRF** si queréis lo más documentado, o **Django Ninja** si venís de FastAPI (mismo estilo con Pydantic y OpenAPI automático, sobre el ORM de Django). Elegid uno; no los mezcléis.
3. Admin para **operaciones internas** (soporte, finanzas): no es un panel de cliente final. La facturación visible para clientes son vistas vuestras, en la API o en plantillas.
4. **Celery + Redis** desde el inicio para la facturación mensual (`celery beat` para la periodicidad) y para cualquier envío de email. Encolad con `transaction.on_commit`.
5. Usuario personalizado desde la primera migración (`AUTH_USER_MODEL = "accounts.User"`): cambiarlo después es el cambio más doloroso que existe en Django.
6. `pytest-django` desde el primer día; Postgres también en desarrollo, no SQLite, para que las migraciones y las consultas sean las mismas que en producción.

El riesgo real de Django para vosotros es el rendimiento en endpoints con muchas llamadas externas concurrentes; si aparece, se resuelve con `gunicorn` y varios workers o moviendo esa pieza a una tarea, no cambiando de framework.""",
            },
        ]
    },
    # ---------------------------------------------------------------- Django (11)
    # 14) Migración: campo único no nulo en tabla grande.
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo que añadir un campo `codigo` único y no nulo al modelo `Pedido`, que ya tiene 2 millones de filas en Postgres. `makemigrations` me pide un default. ¿Cómo lo hago sin romper producción?",
            },
            {
                "role": "assistant",
                "content": r"""En tres migraciones, no en una: añadir el campo como nulo, rellenarlo, y entonces volverlo no nulo y único. Un solo paso con un `default` fijo fallaría en el `UNIQUE` (2 millones de filas con el mismo valor) y, aunque no fallara, Postgres reescribiría la tabla.

**Migración 1: campo nullable.** En Postgres, añadir una columna nullable sin default es un cambio de metadatos: instantáneo, sin reescritura.

```python
# ventas/migrations/0007_pedido_codigo_nullable.py
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("ventas", "0006_anterior")]
    operations = [
        migrations.AddField(model_name="pedido", name="codigo",
                            field=models.CharField(max_length=16, null=True)),
    ]
```

**Migración 2: rellenar por lotes.** Usa el modelo histórico (`apps.get_model`), nunca el import directo, y escribe por lotes para no mantener una transacción enorme ni cargar 2 millones de objetos en memoria.

```python
# ventas/migrations/0008_pedido_codigo_poblar.py
from django.db import migrations

LOTE = 5000


def poblar_codigos(apps, schema_editor):
    Pedido = apps.get_model("ventas", "Pedido")
    pendientes = []
    for pedido in Pedido.objects.filter(codigo__isnull=True).only("id").iterator(chunk_size=LOTE):
        pedido.codigo = f"P{pedido.id:010d}"
        pendientes.append(pedido)
        if len(pendientes) >= LOTE:
            Pedido.objects.bulk_update(pendientes, ["codigo"])
            pendientes.clear()
    if pendientes:
        Pedido.objects.bulk_update(pendientes, ["codigo"])


class Migration(migrations.Migration):
    atomic = False  # cada bulk_update en su propia transacción; una migración atómica de 2M filas bloquea demasiado
    dependencies = [("ventas", "0007_pedido_codigo_nullable")]
    operations = [migrations.RunPython(poblar_codigos, migrations.RunPython.noop)]
```

**Migración 3: restricciones.**

```python
# ventas/migrations/0009_pedido_codigo_unique.py
class Migration(migrations.Migration):
    dependencies = [("ventas", "0008_pedido_codigo_poblar")]
    operations = [
        migrations.AlterField(model_name="pedido", name="codigo",
                              field=models.CharField(max_length=16, unique=True)),
    ]
```

Y en el modelo, `codigo = models.CharField(max_length=16, unique=True)`. El código de aplicación que crea pedidos tiene que asignar `codigo` **antes** de desplegar la migración 3, o los `INSERT` nuevos fallarán por `NOT NULL`. Orden de despliegue: migraciones 1 y 2 → código que rellena `codigo` al crear → migración 3.

Sobre el bloqueo: `SET NOT NULL` en Postgres hace un escaneo de la tabla (segundos para 2 millones de filas) y `CREATE UNIQUE INDEX` bloquea escrituras mientras construye el índice (también segundos a ese tamaño). Para la mayoría de equipos es aceptable en una ventana de poco tráfico. Si no lo es, la migración 3 se hace con `RunSQL` en una migración `atomic = False`: `CREATE UNIQUE INDEX CONCURRENTLY` y después `ALTER TABLE ... ADD CONSTRAINT ... UNIQUE USING INDEX`, con `SeparateDatabaseAndState` para que el estado de Django coincida. Es más trabajo y solo compensa si no puedes permitirte esos segundos.

Un detalle de Django 5: si el valor por defecto pudiera calcularlo la base de datos (por ejemplo, un `uuid`), `db_default=` evita la migración de datos entera. Para un código derivado del `id` no sirve, por eso el `RunPython`.""",
            },
        ]
    },
    # 15) N+1 con select_related/prefetch_related (usuario trae código, vos, system variante).
    {
        "messages": [
            {"role": "system", "content": "Respondé en español rioplatense, con precisión técnica y sin relleno."},
            {
                "role": "user",
                "content": r"""Tengo una vista que tarda un montón. El debug toolbar me dice 213 queries para 50 pedidos. Te paso el código, ¿me decís qué estoy haciendo mal?

```python
def pedidos_recientes(request):
    pedidos = Pedido.objects.filter(estado="pagado").order_by("-creado")[:50]
    filas = []
    for p in pedidos:
        filas.append({
            "cliente": p.cliente.nombre,
            "vendedor": p.cliente.vendedor.nombre,
            "lineas": [(l.producto.nombre, l.cantidad) for l in p.lineas.all()],
        })
    return render(request, "pedidos/recientes.html", {"filas": filas})
```""",
            },
            {
                "role": "assistant",
                "content": r"""Es un N+1 en tres niveles, y los números cierran exactos: 1 consulta para los pedidos + 50 por `p.cliente` + 50 por `p.cliente.vendedor` + 50 por `p.lineas.all()` + 62 por `l.producto` (tenés 62 líneas en total) = 213.

El arreglo es decirle al ORM qué vas a recorrer, en la consulta inicial:

```python
from django.db.models import Prefetch


def pedidos_recientes(request):
    pedidos = (
        Pedido.objects.filter(estado="pagado")
        .select_related("cliente__vendedor")
        .prefetch_related(Prefetch("lineas", queryset=Linea.objects.select_related("producto")))
        .order_by("-creado")[:50]
    )
    filas = [
        {
            "cliente": p.cliente.nombre,
            "vendedor": p.cliente.vendedor.nombre,
            "lineas": [(linea.producto.nombre, linea.cantidad) for linea in p.lineas.all()],
        }
        for p in pedidos
    ]
    return render(request, "pedidos/recientes.html", {"filas": filas})
```

De 213 consultas a **2**:

- **`select_related("cliente__vendedor")`**: las dos claves foráneas hacia adelante se resuelven con `JOIN` en la misma consulta de pedidos. Sirve para `ForeignKey` y `OneToOne`; nunca para relaciones inversas ni `ManyToMany`.
- **`Prefetch("lineas", queryset=...select_related("producto"))`**: las líneas son una relación inversa (muchas por pedido), así que van en una segunda consulta con `WHERE pedido_id IN (...)`. El `select_related("producto")` dentro del `Prefetch` trae el producto en esa misma consulta. Si escribís `prefetch_related("lineas__producto")` también funciona, pero son 3 consultas (líneas, después productos por `IN`).

Dos trampas para que no se te vuelva a disparar:

1. `p.lineas.all()` usa la caché del prefetch. `p.lineas.filter(...)`, `.count()` o `.order_by()` sobre esa relación **ignoran el prefetch** y van a la base de datos otra vez. Si necesitás filtrar, metelo en el `queryset=` del `Prefetch`.
2. Si algún día una plantilla accede a `pedido.cliente.direccion.ciudad`, aparece otro +50. El test de abajo lo detecta antes que el toolbar.

```python
from django.test import TestCase
from django.urls import reverse


class PedidosRecientesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        for _ in range(5):
            PedidoFactory(estado="pagado", lineas=3)

    def test_la_vista_hace_dos_consultas(self):
        with self.assertNumQueries(2):
            response = self.client.get(reverse("pedidos:recientes"))
        self.assertEqual(response.status_code, 200)
```

Si el login está activo en esa vista, sumá las consultas de sesión y usuario (normalmente 2) al número esperado.

Un detalle menor: renombré `l` a `linea`; una ele sola se confunde con el 1 y `ruff` lo marca como E741.""",
            },
        ]
    },
    # 16) Inglés: CBV vs FBV.
    {
        "messages": [
            {
                "role": "user",
                "content": "When should I use class-based views vs function views in Django? My team keeps arguing about it and I'd like a rule we can actually follow.",
            },
            {
                "role": "assistant",
                "content": r"""Rule: **use a generic class-based view when your view is one of the five generic shapes (list, detail, create, update, delete) and you only need to override one or two hooks. Use a function view for everything else.** The argument usually ends there, because most views are clearly one or the other.

What a generic CBV buys you is that the boilerplate is already written and tested: pagination, 404 on missing object, form handling with GET/POST split, success redirect.

```python
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView


class OrderListView(LoginRequiredMixin, ListView):
    model = Order
    paginate_by = 25
    template_name = "orders/list.html"

    def get_queryset(self):
        return (
            super().get_queryset()
            .filter(owner=self.request.user)
            .select_related("customer")
            .order_by("-created_at")
        )
```

Eleven lines for an authenticated, paginated, filtered list. The function version is longer and you would reimplement pagination by hand.

What a CBV costs you: the control flow is hidden in the base classes. When a view needs `get_context_data` **and** `get_queryset` **and** `form_valid` **and** `dispatch` overrides, you are fighting the class instead of using it. That is the signal to switch.

Function view when:

- The view does something that is not CRUD: a webhook receiver, a report that aggregates three querysets, an endpoint that returns JSON by hand, a multi-step workflow.
- The logic is short and reading it top to bottom is clearer than knowing the mixin order.
- You need to branch on method in a way the generic views do not expect.

```python
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_POST


@require_POST
def stripe_webhook(request: HttpRequest) -> HttpResponse:
    event = verify_signature(request.body, request.headers.get("Stripe-Signature", ""))
    handle_event(event)
    return JsonResponse({"ok": True})
```

Two things that are **not** arguments for either side:

- "CBVs are more reusable." Only if you actually reuse them. A view used once gains nothing from being a class.
- "FBVs are simpler." Only until you hand-roll pagination and form handling for the fourth time.

A practical addition that avoids most of the fighting: keep business logic out of both. Views call a service function (`orders.services.place_order(user, data)`), so whether the view is a class or a function becomes a presentation detail nobody needs to argue about.""",
            },
        ]
    },
    # 17) Forms: clean() y add_error (multiturno, principiante).
    {
        "messages": [
            {
                "role": "user",
                "content": "Soy nuevo en Django. Tengo un formulario con fecha_inicio y fecha_fin y quiero validar que la de fin sea posterior. ¿Dónde se hace eso?",
            },
            {
                "role": "assistant",
                "content": r"""En el método `clean()` del formulario. Las validaciones de **un** campo van en `clean_<campo>()`; las que comparan **varios** campos van en `clean()`, porque es el único sitio donde ya tienes todos los valores limpios.

```python
from django import forms


class ReservaForm(forms.Form):
    fecha_inicio = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    fecha_fin = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))

    def clean(self):
        cleaned = super().clean()
        inicio = cleaned.get("fecha_inicio")
        fin = cleaned.get("fecha_fin")
        if inicio and fin and fin <= inicio:
            raise forms.ValidationError("La fecha de fin debe ser posterior a la de inicio.")
        return cleaned
```

Por qué cada línea:

- `super().clean()` ejecuta la validación de campos individuales y devuelve `cleaned_data`.
- `cleaned.get(...)` en vez de `cleaned["fecha_inicio"]`: si el usuario dejó un campo vacío o con formato inválido, ese campo **no está** en `cleaned_data` (su error ya se registró). Con `[]` tendrías un `KeyError` en vez de un mensaje bonito.
- `if inicio and fin`: solo compara cuando ambos son válidos.

En la vista no cambia nada:

```python
def crear_reserva(request):
    form = ReservaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        Reserva.objects.create(**form.cleaned_data)
        return redirect("reservas:lista")
    return render(request, "reservas/crear.html", {"form": form})
```

Y en la plantilla, `{{ form.non_field_errors }}` muestra el error de `clean()` (no pertenece a un campo concreto) y `{{ form.fecha_fin.errors }}` los del campo.

Si usas `ModelForm`, es idéntico; `clean()` corre antes de guardar y puedes acceder a `self.instance` si necesitas comparar con el valor anterior.""",
            },
            {
                "role": "user",
                "content": "Funciona, pero el mensaje sale arriba del todo y me gustaría que apareciera al lado del campo fecha_fin, como los otros errores.",
            },
            {
                "role": "assistant",
                "content": r"""Usa `self.add_error("fecha_fin", mensaje)` en lugar de lanzar la excepción. Asocia el error a ese campo y, de paso, lo elimina de `cleaned_data` para que no se use por error.

```python
    def clean(self):
        cleaned = super().clean()
        inicio = cleaned.get("fecha_inicio")
        fin = cleaned.get("fecha_fin")
        if inicio and fin and fin <= inicio:
            self.add_error("fecha_fin", "Debe ser posterior a la fecha de inicio.")
        return cleaned
```

Ahora `{{ form.fecha_fin.errors }}` lo muestra junto al campo y `non_field_errors` queda vacío.

Cuándo elegir cada uno:

- `add_error("campo", ...)`: el error tiene un responsable claro y el usuario sabe qué corregir. Es tu caso.
- `raise ValidationError(...)` en `clean()`: el error es de la combinación y no tiene sentido señalar un campo («no puedes reservar la sala A y la B a la vez»).

Un matiz: `add_error` no interrumpe `clean()`, así que puedes acumular varios errores en una pasada (por ejemplo, fecha de fin inválida y además duración superior a 30 días) y el usuario los ve todos de una vez en lugar de uno por envío.""",
            },
        ]
    },
    # 18) Admin de Django en tabla grande (system variante: solo código).
    {
        "messages": [
            {"role": "system", "content": "Responde solo con código y un comentario breve por cada decisión."},
            {
                "role": "user",
                "content": "Admin de Django para `Pedido` (FK a `Cliente`, FK a `Vendedor`, 500 000 filas). La lista tarda 8 segundos y el formulario de edición tarda otros 10 porque el select de cliente carga 80 000 opciones.",
            },
            {
                "role": "assistant",
                "content": r"""```python
from django.contrib import admin

from .models import Cliente, Pedido


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    search_fields = ["nombre", "email"]  # obligatorio para que Pedido pueda usar autocomplete sobre Cliente


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ["id", "cliente", "vendedor", "estado", "total", "creado"]
    list_select_related = ["cliente", "vendedor"]  # un JOIN en vez de 2 consultas por fila (N+1 en la lista)
    list_filter = ["estado", "creado"]
    search_fields = ["id", "cliente__nombre"]  # búsqueda acotada; `cliente__email` con icontains sin índice sería lenta
    date_hierarchy = "creado"
    list_per_page = 50  # el default es 100; menos filas por página es menos renderizado
    show_full_result_count = False  # evita el COUNT(*) completo en cada página (segundos en 500k filas)
    ordering = ["-id"]  # ordenar por PK usa el índice; ordenar por `creado` necesita índice propio
    autocomplete_fields = ["cliente"]  # select2 con búsqueda vía AJAX; el formulario ya no carga 80k opciones
    raw_id_fields = ["vendedor"]  # pocos vendedores, pero evita cargar la lista completa igualmente
    readonly_fields = ["creado", "total"]  # campos calculados o inmutables no se editan a mano
    actions = ["marcar_enviado"]

    @admin.action(description="Marcar como enviado")
    def marcar_enviado(self, request, queryset):
        actualizados = queryset.filter(estado="pagado").update(estado="enviado")  # UPDATE en bloque, sin señales
        self.message_user(request, f"{actualizados} pedidos marcados como enviados.")
```

```python
# models.py: índice para los filtros y la jerarquía por fecha; sin él, list_filter por `creado` escanea la tabla
class Pedido(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=["estado", "-creado"]),  # cubre el filtro por estado ordenado por fecha
        ]
```""",
            },
        ]
    },
    # 19) DRF: serializer anidado lectura/escritura (system exacto).
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Con DRF necesito un CRUD de `Pedido` con sus `Linea`s. Al leer quiero las líneas anidadas con el nombre del producto; al crear quiero mandar solo `producto_id` y `cantidad`. ¿Cómo lo haces sin tener dos serializers por cada cosa?",
            },
            {
                "role": "assistant",
                "content": r"""Un serializer por modelo, con campos de solo lectura para lo que se muestra y de solo escritura para lo que se recibe, y un `create()` que sabe guardar el anidado dentro de una transacción.

```python
# pedidos/serializers.py
from django.db import transaction
from rest_framework import serializers

from .models import Linea, Pedido, Producto


class LineaSerializer(serializers.ModelSerializer):
    producto_id = serializers.PrimaryKeyRelatedField(
        queryset=Producto.objects.filter(activo=True), source="producto", write_only=True
    )
    producto = serializers.CharField(source="producto.nombre", read_only=True)

    class Meta:
        model = Linea
        fields = ["id", "producto_id", "producto", "cantidad", "precio_unitario"]
        read_only_fields = ["id", "precio_unitario"]


class PedidoSerializer(serializers.ModelSerializer):
    lineas = LineaSerializer(many=True)
    cliente = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Pedido
        fields = ["id", "cliente", "estado", "total", "lineas", "creado"]
        read_only_fields = ["id", "estado", "total", "creado"]

    def validate_lineas(self, lineas):
        if not lineas:
            raise serializers.ValidationError("Un pedido necesita al menos una línea.")
        return lineas

    @transaction.atomic
    def create(self, validated_data):
        lineas = validated_data.pop("lineas")
        pedido = Pedido.objects.create(cliente=self.context["request"].user.cliente, **validated_data)
        Linea.objects.bulk_create(
            Linea(pedido=pedido, producto=l["producto"], cantidad=l["cantidad"], precio_unitario=l["producto"].precio)
            for l in lineas
        )
        pedido.recalcular_total()
        return pedido
```

```python
# pedidos/views.py
from rest_framework import permissions, viewsets

from .models import Pedido
from .serializers import PedidoSerializer


class PedidoViewSet(viewsets.ModelViewSet):
    serializer_class = PedidoSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "delete", "head", "options"]  # sin PUT/PATCH: un pedido no se edita, se cancela

    def get_queryset(self):
        return (
            Pedido.objects.filter(cliente__user=self.request.user)
            .select_related("cliente")
            .prefetch_related("lineas__producto")
            .order_by("-creado")
        )
```

```python
# pedidos/urls.py
from rest_framework.routers import DefaultRouter

from .views import PedidoViewSet

router = DefaultRouter()
router.register("pedidos", PedidoViewSet, basename="pedido")
urlpatterns = router.urls
```

Petición y respuesta:

```http
POST /api/pedidos/
{"lineas": [{"producto_id": 12, "cantidad": 2}, {"producto_id": 7, "cantidad": 1}]}

201
{"id": 501, "cliente": "Ana Ruiz", "estado": "pendiente", "total": "59.90",
 "lineas": [{"id": 1, "producto": "Teclado", "cantidad": 2, "precio_unitario": "19.95"}, ...]}
```

Decisiones:

- **El mismo nombre lógico con dos campos**: `producto_id` (`write_only`, `source="producto"`) recibe el id y lo convierte en instancia; `producto` (`read_only`, `source="producto.nombre"`) muestra el nombre. DRF no se queja porque los nombres de campo son distintos aunque el `source` apunte al mismo atributo.
- **`queryset=Producto.objects.filter(activo=True)`** en el `PrimaryKeyRelatedField`: un id de producto inactivo devuelve 400 con «Invalid pk», sin código extra.
- **`precio_unitario` se copia del producto en el servidor**, nunca se acepta del cliente. Por eso es `read_only`.
- **`@transaction.atomic` en `create`**: si falla el `bulk_create` o el `recalcular_total`, no queda un pedido sin líneas.
- **Sin `update`**: DRF lanza `NotImplementedError` si alguien intenta un PATCH con anidados y no has escrito `update()`. Quitar los métodos es más honesto que un 500. Si de verdad hace falta editar líneas, escribe `update()` con lógica de diff explícita; no hay versión automática buena.
- **`prefetch_related("lineas__producto")` en el ViewSet**: sin esto, listar 50 pedidos son 100+ consultas.

Test mínimo con `APIClient`:

```python
def test_crear_pedido_con_lineas(api_client, producto):
    r = api_client.post("/api/pedidos/", {"lineas": [{"producto_id": producto.id, "cantidad": 2}]}, format="json")
    assert r.status_code == 201
    assert r.data["lineas"][0]["producto"] == producto.nombre
    assert Linea.objects.count() == 1
```""",
            },
        ]
    },
    # 20) Señales post_save y transacciones.
    {
        "messages": [
            {
                "role": "user",
                "content": "Uso una señal `post_save` en `Pedido` para encolar una tarea de Celery que manda el email de confirmación. A veces el worker falla con `Pedido.DoesNotExist` aunque el pedido existe (lo veo en el admin). ¿Cómo puede ser?",
            },
            {
                "role": "assistant",
                "content": r"""Es una carrera entre tu transacción y el worker. `post_save` se dispara **dentro** de la transacción, justo después del `INSERT` pero **antes del `COMMIT`**. La tarea llega a Redis, el worker (otro proceso, otra conexión a Postgres) la recoge en milisegundos y hace `Pedido.objects.get(id=...)`, y desde su conexión el pedido aún no existe. Unos milisegundos después tu vista hace commit y el pedido aparece en el admin. Por eso «existe» y por eso es intermitente: depende de quién llegue antes.

**Arreglo mínimo:** encola cuando la transacción haya confirmado.

```python
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Pedido
from .tasks import enviar_confirmacion


@receiver(post_save, sender=Pedido)
def encolar_confirmacion(sender, instance: Pedido, created: bool, **kwargs):
    if not created:
        return
    transaction.on_commit(lambda: enviar_confirmacion.delay(instance.id))
```

`on_commit` hace lo correcto en los tres casos: si no hay transacción abierta ejecuta ya; si la hay, espera al commit; si hay rollback, **no ejecuta**, que es lo que quieres (sin pedido no hay email). El `if not created` es el segundo bug latente: sin él, cada `pedido.save()` posterior (cambio de estado, por ejemplo) reenviaba el email.

**Arreglo que recomiendo:** saca el encolado de la señal y ponlo donde se crea el pedido.

```python
# pedidos/services.py
from django.db import transaction


def crear_pedido(cliente: Cliente, lineas: list[LineaInput]) -> Pedido:
    with transaction.atomic():
        pedido = Pedido.objects.create(cliente=cliente)
        Linea.objects.bulk_create(Linea(pedido=pedido, **l.__dict__) for l in lineas)
        transaction.on_commit(lambda: enviar_confirmacion.delay(pedido.id))
    return pedido
```

Razones:

- Las señales no se disparan con `bulk_create()` ni con `queryset.update()`. Si mañana un importador crea pedidos por lotes, no habrá emails y nadie sabrá por qué.
- Quien lea `crear_pedido` ve que se envía un email. Con la señal, el efecto está en otro archivo y aparece «por magia».
- Las señales tienen sentido para que una app reaccione a otra que no controla (p. ej. crear un perfil cuando `auth.User` se crea). Para lógica de tu propio dominio, esconden el flujo.

**Red de seguridad en la tarea**, por si en el futuro alguien vuelve a encolar antes del commit:

```python
@shared_task(bind=True, autoretry_for=(Pedido.DoesNotExist,), retry_backoff=2, max_retries=3)
def enviar_confirmacion(self, pedido_id: int) -> None:
    pedido = Pedido.objects.select_related("cliente").get(id=pedido_id)
    mailer.enviar_confirmacion(pedido)
```

Un reintento con 2 segundos de espera tapa la carrera, pero no la arregla; úsalo como cinturón, no como solución.

**Test que reproduce el bug** (sin Celery real):

```python
from unittest.mock import patch

from django.test import TestCase


class CrearPedidoTests(TestCase):
    def test_encola_solo_tras_commit(self):
        with patch("pedidos.services.enviar_confirmacion.delay") as delay:
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                pedido = crear_pedido(self.cliente, [LineaInput(producto_id=1, cantidad=1)])
        self.assertEqual(len(callbacks), 1)
        delay.assert_called_once_with(pedido.id)
```

`captureOnCommitCallbacks` existe desde Django 3.2 precisamente para esto: en `TestCase` todo corre dentro de una transacción que nunca confirma, así que sin él los `on_commit` jamás se ejecutarían en los tests.""",
            },
        ]
    },
    # 21) Middleware con request id (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Cómo añado un `X-Request-ID` a cada petición en Django y hago que salga en todas las líneas de log de esa petición?",
            },
            {
                "role": "assistant",
                "content": r"""Un middleware que genera o reutiliza el id y lo guarda en un `ContextVar`, más un filtro de logging que lo inyecta en cada registro.

```python
# core/request_id.py
import logging
import uuid
from contextvars import ContextVar

from django.http import HttpRequest, HttpResponse

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
HEADER = "X-Request-ID"


class RequestIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request_id = request.headers.get(HEADER) or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        try:
            response = self.get_response(request)
        finally:
            request_id_var.reset(token)
        response[HEADER] = request_id
        return response


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True
```

```python
# settings.py
MIDDLEWARE = [
    "core.request_id.RequestIdMiddleware",
    "django.middleware.security.SecurityMiddleware",
    # el resto
]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"request_id": {"()": "core.request_id.RequestIdFilter"}},
    "formatters": {
        "plain": {"format": "%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "filters": ["request_id"], "formatter": "plain"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}
```

Por qué así:

- **Reutilizar el header entrante** permite seguir una petición desde el proxy o desde otro servicio. Si no viene, generas uno. Si no te fías de clientes externos, valida el formato (`len <= 64`, alfanumérico) antes de aceptarlo.
- **`ContextVar` en vez de `threading.local`**: funciona con hilos (gunicorn sync) y con vistas `async` (cada tarea tiene su contexto). `reset(token)` en el `finally` evita que el id se filtre a la siguiente petición del mismo hilo.
- **El filtro vive en el handler, no en un logger**: así cualquier `logging.getLogger(__name__)` de cualquier app lo lleva, sin configurar logger por logger.

Ya puedes escribir `logger.info("pedido creado", extra={"pedido_id": p.id})` en cualquier sitio y la línea sale con `[a3f9...]`. Para correlacionar con Celery, pasa `request_id_var.get()` como argumento a la tarea y vuelve a hacer `set()` dentro del worker.""",
            },
            {
                "role": "user",
                "content": "Lo he puesto al final de MIDDLEWARE y funciona, pero cuando el middleware de autenticación lanza una excepción esa línea de log sale con `[-]`. ¿Por qué?",
            },
            {
                "role": "assistant",
                "content": r"""Porque el orden de `MIDDLEWARE` es el orden de ejecución en la entrada: el primero de la lista envuelve a todos los demás. Si el tuyo está al final, cuando `AuthenticationMiddleware` falla (o `SecurityMiddleware` redirige, o `CsrfViewMiddleware` rechaza), tu `__call__` **todavía no se ha ejecutado**, así que el `ContextVar` sigue con el valor por defecto `-`.

Muévelo al **principio** de la lista, como en el ejemplo:

```python
MIDDLEWARE = [
    "core.request_id.RequestIdMiddleware",   # primero: envuelve a todos
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]
```

Visualiza la pila: la petición entra por arriba y baja hasta la vista; la respuesta (o la excepción) sube de vuelta. Un middleware solo ve lo que ocurre **por debajo** de él. Para que el id esté disponible en todo lo que pueda fallar, el tuyo tiene que estar por encima de todo.

Hay una excepción práctica: si usas un middleware de salud (`/health` que responde sin pasar por nada) y no quieres que genere ids ni logs, ese sí puede ir por encima del tuyo. Todo lo demás, debajo.""",
            },
        ]
    },
    # 22) Settings por entorno (México).
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Cómo manejan la configuración de Django por ambiente? Ahorita tengo un settings.py con un `if DEBUG:` gigante y la semana pasada ya se me fue el SECRET_KEY de producción al repo. Necesito arreglarlo bien.",
            },
            {
                "role": "assistant",
                "content": r"""Dos reglas y una estructura: **los secretos y lo que cambia por ambiente vienen del entorno**, **lo que no cambia va en código**, y el `if DEBUG:` desaparece porque cada ambiente es un módulo.

Estructura:

```
config/
  settings/
    __init__.py
    base.py        # todo lo común
    dev.py         # from .base import *  + DEBUG, toolbar, SQLite si quieres
    prod.py        # from .base import *  + seguridad
    test.py        # from .base import *  + hasher rápido, email a memoria
```

`base.py` lee el entorno con `django-environ` (o `os.environ` a pelo; la librería solo te ahorra las conversiones):

```python
# config/settings/base.py
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent
env = environ.Env(DEBUG=(bool, False), ALLOWED_HOSTS=(list, []))

SECRET_KEY = env("SECRET_KEY")               # sin default: si falta, Django no arranca
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")
DATABASES = {"default": env.db("DATABASE_URL")}  # postgres://user:pass@host:5432/db
CACHES = {"default": env.cache("CACHE_URL", default="locmemcache://")}
EMAIL_CONFIG = env.email("EMAIL_URL", default="consolemail://")
vars().update(EMAIL_CONFIG)
```

```python
# config/settings/prod.py
from .base import *  # noqa: F403

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS")
```

```python
# config/settings/dev.py
from .base import *  # noqa: F403

DEBUG = True
INSTALLED_APPS += ["debug_toolbar"]
MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")
INTERNAL_IPS = ["127.0.0.1"]
```

Selección del módulo con la variable que Django ya mira:

```bash
# desarrollo (.env, NO versionado; con .env.example sí versionado y sin valores reales)
DJANGO_SETTINGS_MODULE=config.settings.dev
# producción: la pone el Dockerfile o el orquestador
ENV DJANGO_SETTINGS_MODULE=config.settings.prod
```

Para el `SECRET_KEY` que ya se fue al repo:

1. **Rótalo ya.** Un secreto en el historial de git está comprometido aunque borres el commit. Genera otro: `python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"`. Rotarlo invalida sesiones y tokens de reseteo de contraseña; avisa.
2. Añade `.env` a `.gitignore` y versiona solo `.env.example`.
3. Mete `gitleaks` o `detect-secrets` como *pre-commit hook* para que no vuelva a pasar.

Antes de cada despliegue, `python manage.py check --deploy` te lista lo que falta en seguridad (HSTS, cookies, `DEBUG=True` en producción). Ponlo en el pipeline de CI con `DJANGO_SETTINGS_MODULE=config.settings.prod` y variables dummy; falla si alguien relaja algo.

Una recomendación en contra de la tentación: no uses `if os.environ.get("ENV") == "prod":` dentro de `base.py`. Es volver al `if DEBUG:` gigante con otro nombre.""",
            },
        ]
    },
    # 23) Tests: pytest-django vs TestCase, assertNumQueries (system variante).
    {
        "messages": [
            {"role": "system", "content": "Responde de forma breve y directa, con ejemplos de código ejecutables."},
            {
                "role": "user",
                "content": "¿pytest-django o el TestCase de Django? Y quiero que un test falle si una vista que hoy hace 2 consultas mañana hace 50.",
            },
            {
                "role": "assistant",
                "content": r"""`pytest-django`. Usa el mismo motor (transacción por test, base de datos de pruebas) pero con fixtures, parametrización y `assert` normales. Puedes seguir escribiendo clases `TestCase` si quieres; `pytest-django` las ejecuta igual.

```ini
# pyproject.toml
[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "config.settings.test"
python_files = ["test_*.py"]
```

```python
# config/settings/test.py
from .base import *  # noqa: F403

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # crear usuarios tarda ms, no cientos de ms
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
```

Para el número de consultas, la fixture `django_assert_num_queries`:

```python
import pytest
from django.urls import reverse


@pytest.fixture
def pedidos(db):
    cliente = Cliente.objects.create(nombre="Ana")
    for i in range(20):
        p = Pedido.objects.create(cliente=cliente, estado="pagado")
        Linea.objects.create(pedido=p, producto=Producto.objects.create(nombre=f"P{i}"), cantidad=1)
    return cliente


def test_lista_pedidos_hace_dos_consultas(client, pedidos, django_assert_num_queries):
    with django_assert_num_queries(2):
        response = client.get(reverse("pedidos:recientes"))
    assert response.status_code == 200
```

Si la vista pasa a hacer 42 consultas, el fallo imprime **las 42 SQL** con su traza, así que ves de inmediato cuál es la relación sin cargar.

Dos ajustes para que el test no sea frágil:

- Si la vista exige login, `client.force_login(user)` añade 2 consultas (sesión y usuario). Cuéntalas o usa `django_assert_max_num_queries(4)` si prefieres un tope.
- Crea datos con `factory_boy` cuando pases de dos modelos; el `setUp` a mano crece sin control.

```python
import factory


class PedidoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Pedido

    cliente = factory.SubFactory(ClienteFactory)
    estado = "pagado"
```

`pytest -x --reuse-db` para el ciclo rápido: no destruye la base de datos de pruebas entre ejecuciones; `--create-db` cuando cambies migraciones.""",
            },
        ]
    },
    # 24) Race condition en stock (usuario trae código).
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Dos compras al mismo tiempo dejan el stock en -1 aunque compruebo antes. Código:

```python
def comprar(producto_id, cantidad):
    producto = Producto.objects.get(id=producto_id)
    if producto.stock < cantidad:
        raise SinStock()
    producto.stock -= cantidad
    producto.save()
    return Pedido.objects.create(producto=producto, cantidad=cantidad)
```

Lo tengo dentro de `transaction.atomic()` en la vista y sigue pasando. ¿No debería la transacción evitarlo?""",
            },
            {
                "role": "assistant",
                "content": r"""La transacción no te protege porque **no estás pidiendo exclusión**: solo atomicidad. Con el aislamiento por defecto de Postgres (`READ COMMITTED`), dos transacciones leen `stock = 1` a la vez, las dos pasan el `if`, y cada una escribe el valor que calculó en Python con una lectura ya obsoleta. Es el patrón *check-then-act*; una transacción no lo convierte en atómico.

Hay dos arreglos correctos. Elige por lo que necesites después del decremento.

**1. Decremento condicional en una sola sentencia (mi recomendación).** La base de datos serializa las escrituras sobre la misma fila; si el stock no alcanza, `update()` devuelve 0.

```python
from django.db import transaction
from django.db.models import F


def comprar(producto_id: int, cantidad: int) -> Pedido:
    with transaction.atomic():
        actualizados = Producto.objects.filter(id=producto_id, stock__gte=cantidad).update(
            stock=F("stock") - cantidad
        )
        if actualizados == 0:
            raise SinStock(producto_id)
        return Pedido.objects.create(producto_id=producto_id, cantidad=cantidad)
```

Sin bloqueo explícito, sin leer antes, y no pisa otros campos del producto (tu `save()` sin `update_fields` escribía **todas** las columnas con los valores leídos, otra fuente de sobrescrituras).

**2. `select_for_update()` si necesitas el objeto bloqueado** (por ejemplo, para validar reglas que dependen de varios campos antes de decidir).

```python
def comprar(producto_id: int, cantidad: int) -> Pedido:
    with transaction.atomic():
        producto = Producto.objects.select_for_update().get(id=producto_id)
        if producto.stock < cantidad:
            raise SinStock(producto_id)
        producto.stock -= cantidad
        producto.save(update_fields=["stock"])
        return Pedido.objects.create(producto=producto, cantidad=cantidad)
```

`SELECT ... FOR UPDATE` bloquea la fila hasta el commit: la segunda compra **espera** en el `get()` y, cuando lee, ya ve el stock decrementado. Coste: el bloqueo dura toda la transacción, así que no hagas I/O externa (pasarela de pago) dentro. Y el `get()` tiene que estar **dentro** del `atomic()`; fuera, Django lanza `TransactionManagementError`.

**Última defensa en el modelo**, para que ningún otro camino (admin, scripts, un `update()` mal hecho) pueda dejarlo negativo:

```python
class Producto(models.Model):
    stock = models.PositiveIntegerField()

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(stock__gte=0), name="stock_no_negativo")]
```

(`condition=` es el nombre en Django 5.1+; en 5.0 y anteriores es `check=`.) Con esto, el peor caso pasa de «stock -1» a `IntegrityError`, que es ruidoso y correcto.

**Test determinista** del arreglo 1 (no necesitas hilos para probar el `UPDATE` condicional):

```python
def test_no_vende_mas_de_lo_que_hay(db):
    producto = Producto.objects.create(nombre="X", stock=1)
    comprar(producto.id, 1)
    with pytest.raises(SinStock):
        comprar(producto.id, 1)
    producto.refresh_from_db()
    assert producto.stock == 0
```

Si quieres reproducir la carrera real con dos hilos, hazlo en `TransactionTestCase` (o `@pytest.mark.django_db(transaction=True)`): en el `TestCase` normal todo el test vive en una transacción que los otros hilos no ven, y la carrera no se manifiesta.""",
            },
        ]
    },
    # ---------------------------------------------------------------- Flask (6)
    # 25) App factory y blueprints (multiturno, España).
    {
        "messages": [
            {
                "role": "user",
                "content": "Mi app de Flask está toda en un `app.py` de 800 líneas. Cuando intento separarla en varios ficheros me salen imports circulares con `db` y con `app`. ¿Cómo se organiza bien?",
            },
            {
                "role": "assistant",
                "content": r"""Con el patrón *application factory*: `app` no existe a nivel de módulo, se crea en una función, y las extensiones se crean **sin app** y se enlazan dentro de la factoría con `init_app`. Eso rompe los dos ciclos que tienes (`db` necesita `app`, las rutas necesitan `db`, `app` importa las rutas).

```
miapp/
  __init__.py      # create_app()
  extensions.py    # db, migrate, login_manager (sin app)
  models.py        # importa db desde extensions
  config.py
  pedidos/
    __init__.py    # bp = Blueprint(...)
    routes.py
  auth/
    __init__.py
    routes.py
```

```python
# miapp/extensions.py
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)
migrate = Migrate()
```

```python
# miapp/__init__.py
from flask import Flask

from .extensions import db, migrate


def create_app(config_object: str = "miapp.config.DevConfig") -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)
    migrate.init_app(app, db)

    from .auth import bp as auth_bp
    from .pedidos import bp as pedidos_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(pedidos_bp, url_prefix="/pedidos")
    return app
```

```python
# miapp/pedidos/__init__.py
from flask import Blueprint

bp = Blueprint("pedidos", __name__)

from . import routes  # noqa: E402,F401  (al final: routes necesita bp)
```

```python
# miapp/pedidos/routes.py
from flask import jsonify, render_template

from ..extensions import db
from ..models import Pedido
from . import bp


@bp.get("/")
def listar():
    pedidos = db.session.execute(db.select(Pedido).order_by(Pedido.creado.desc())).scalars()
    return render_template("pedidos/lista.html", pedidos=pedidos)


@bp.get("/<int:pedido_id>")
def detalle(pedido_id: int):
    pedido = db.get_or_404(Pedido, pedido_id)
    return jsonify(id=pedido.id, estado=pedido.estado)
```

Por qué desaparecen los ciclos:

- `extensions.py` no importa nada de la app. `models.py` importa `db` de ahí, no de `app`.
- Los blueprints se importan **dentro** de `create_app`, cuando `db` ya existe. El import al final de `pedidos/__init__.py` es el único «truco» y es el idiomático: `routes` necesita `bp`, y `bp` tiene que estar definido antes.
- Nada hace `from miapp import app`. Si una ruta necesita la configuración, usa `current_app.config`.

En las plantillas, `url_for("pedidos.detalle", pedido_id=3)`: el nombre del blueprint va de prefijo.

Una regla para mantenerlo limpio: un blueprint por área funcional, no por tipo de fichero. `pedidos/` contiene sus rutas, sus formularios y sus servicios; no hagas `routes/`, `forms/`, `services/` globales.""",
            },
            {
                "role": "user",
                "content": "Vale, ¿y cómo lanzo eso con `flask run` si ya no hay `app` global? ¿Y en producción con gunicorn?",
            },
            {
                "role": "assistant",
                "content": r"""Flask detecta `create_app` por convención. Solo tienes que señalar el paquete:

```bash
flask --app miapp run --debug
```

Busca `create_app` (o `make_app`) en `miapp/__init__.py` y lo llama sin argumentos. Si necesitas pasarle la config:

```bash
flask --app "miapp:create_app('miapp.config.TestConfig')" run
```

Para no escribir `--app` cada vez, un `.flaskenv` en la raíz (lo lee `python-dotenv`, que Flask instala con el extra `flask[dotenv]`):

```
FLASK_APP=miapp
FLASK_DEBUG=1
```

Lo mismo sirve para `flask --app miapp db migrate` (Flask-Migrate) y para `flask shell`, que ya entra con el contexto de aplicación activo.

En producción, gunicorn acepta una expresión que devuelva la app:

```bash
gunicorn "miapp:create_app()" --workers 4 --bind 0.0.0.0:8000 --access-logfile - --timeout 30
```

Las comillas son por los paréntesis. Si la config de producción es otra clase: `"miapp:create_app('miapp.config.ProdConfig')"`, o mejor, que `create_app` lea `os.environ.get("APP_CONFIG", "miapp.config.DevConfig")` como valor por defecto y lo controles con una variable de entorno en el contenedor.

`flask run` es un servidor de desarrollo: un hilo por petición, sin reinicio de workers, con el *debugger* que permite ejecutar código desde el navegador. Nunca en producción, ni siquiera «temporalmente».""",
            },
        ]
    },
    # 26) Working outside of application context (usuario trae traza).
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Tengo un script que importa modelos de mi app Flask para hacer una carga de datos y falla:

```
Traceback (most recent call last):
  File "scripts/cargar.py", line 12, in <module>
    db.session.add(Producto(nombre="A"))
  File ".../flask_sqlalchemy/session.py", line 86, in get_bind
    raise RuntimeError("Working outside of application context.")
RuntimeError: Working outside of application context.

This typically means that you attempted to use functionality that needed
the current application. To solve this, set up an application context
with app.app_context(). See the documentation for more information.
```

El script hace `from miapp import create_app, db` y `from miapp.models import Producto`. ¿Por qué si estoy importando la app?""",
            },
            {
                "role": "assistant",
                "content": r"""Importar `create_app` **no crea la app**, y aunque la crearas, Flask-SQLAlchemy no sabe a qué aplicación (y por tanto a qué `SQLALCHEMY_DATABASE_URI`) pertenece `db.session` hasta que hay un **contexto de aplicación** activo. Ese contexto lo crea Flask automáticamente durante una petición; en un script no existe nadie que lo cree por ti.

**Arreglo mínimo** en el script:

```python
# scripts/cargar.py
from miapp import create_app, db
from miapp.models import Producto

app = create_app()
with app.app_context():
    db.session.add(Producto(nombre="A"))
    db.session.commit()
```

**Arreglo que recomiendo**: conviértelo en un comando de la propia app. Entra con el contexto activo, lee la misma configuración y no necesitas tocar `sys.path` para que el script encuentre el paquete.

```python
# miapp/commands.py
import click
from flask import Blueprint

from .extensions import db
from .models import Producto

bp = Blueprint("commands", __name__, cli_group=None)


@bp.cli.command("cargar")
@click.argument("fichero", type=click.Path(exists=True))
def cargar(fichero: str) -> None:
    '''Carga productos desde un CSV.'''
    with open(fichero, encoding="utf-8") as f:
        productos = [Producto(nombre=linea.strip()) for linea in f if linea.strip()]
    db.session.add_all(productos)
    db.session.commit()
    click.echo(f"{len(productos)} productos cargados")
```

Regístralo en `create_app` con `app.register_blueprint(commands_bp)` y ejecútalo con:

```bash
flask --app miapp cargar datos/productos.csv
```

Mismo mecanismo que `flask db migrate` o `flask shell`.

Dos aclaraciones que te van a ahorrar la siguiente pregunta:

- **Contexto de aplicación** (`app.app_context()`) da acceso a `current_app`, `g` y a las extensiones (`db`). **Contexto de petición** (`app.test_request_context()`) añade `request`, `session` y `url_for` con URLs completas. Un script o una tarea solo necesita el primero.
- **Los hilos y las tareas de Celery no heredan el contexto.** Dentro de una tarea, haz `with app.app_context():` igual que en el script; el patrón habitual es una subclase de `Task` cuyo `__call__` lo abre, para no repetirlo en cada tarea.""",
            },
        ]
    },
    # 27) Inglés: Jinja y | safe.
    {
        "messages": [
            {
                "role": "user",
                "content": "In Flask/Jinja, when is `| safe` actually safe? I render user comments that are written in Markdown and I'm not sure if I'm opening an XSS hole.",
            },
            {
                "role": "assistant",
                "content": r"""`| safe` is safe exactly when the string was produced by code **you** control and that code already made it safe. User Markdown does not qualify until you sanitize the rendered HTML: Markdown allows raw HTML inline, so `<img src=x onerror=alert(1)>` in a comment survives the Markdown step untouched.

Flask enables Jinja autoescaping for `.html`, `.htm`, `.xml` and `.xhtml` templates. Every `{{ value }}` is escaped, which is why `{{ comment.html }}` shows the tags as text and why people reach for `| safe`. The right pipeline is: Markdown → HTML → sanitizer with an allowlist → `Markup`.

```python
import markdown
import nh3
from markupsafe import Markup

ALLOWED_TAGS = {"p", "br", "strong", "em", "code", "pre", "blockquote", "ul", "ol", "li", "a"}
ALLOWED_ATTRS = {"a": {"href", "title"}}


def render_comment(text: str) -> Markup:
    html = markdown.markdown(text, extensions=["fenced_code"])
    clean = nh3.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, link_rel="nofollow noopener")
    return Markup(clean)
```

In the template:

```html
<div class="comment">{{ render_comment(comment.body) }}</div>
```

No `| safe` needed: `Markup` is the type Jinja treats as already-escaped. That is the point of returning it from the sanitizer rather than sprinkling `| safe` in templates: the only place that can produce trusted HTML is the function that sanitizes.

Details that matter:

- **`nh3`** (bindings to Rust's `ammonia`) is the maintained choice; `bleach` was deprecated in 2023. It strips disallowed tags, attributes and `javascript:` URLs by default.
- **Allowlist, never denylist.** You cannot enumerate every dangerous attribute; you can enumerate the six tags a comment needs.
- **Sanitize at render or at save time, but pick one.** Sanitizing at save time means a future policy change requires re-processing stored comments; sanitizing at render time costs a few hundred microseconds per comment. Cache the rendered HTML if volume is high.
- **`Markup` also escapes when concatenated**: `Markup("<b>") + "<i>"` yields `<b>&lt;i&gt;`. Use `Markup.format()` or f-strings on already-sanitized input only.

Quick check that you did not open a hole:

```python
def test_comment_rendering_strips_scripts():
    out = render_comment('hello <img src=x onerror="alert(1)"> [x](javascript:alert(1))')
    assert "onerror" not in out and "javascript:" not in out
```

Legitimate `| safe` uses: HTML you built from literal strings in Python, output of a template partial you already rendered, or a trusted CMS field edited only by staff. User input is never one of them.""",
            },
        ]
    },
    # 28) Flask-Login + Flask-WTF (system exacto).
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Login clásico con sesión en Flask 3 (sin JWT, es una app con plantillas). ¿Qué extensiones uso y cómo protejo el formulario? Quiero el mínimo correcto.",
            },
            {
                "role": "assistant",
                "content": r"""Flask-Login para la sesión y Flask-WTF para el formulario con CSRF. Hasheo de contraseñas con `werkzeug.security`, que ya viene con Flask.

```python
# miapp/extensions.py
from flask_login import LoginManager
from flask_wtf import CSRFProtect

login_manager = LoginManager()
login_manager.login_view = "auth.login"       # a dónde redirigir cuando @login_required falla
login_manager.session_protection = "strong"  # invalida la sesión si cambia IP/user-agent
csrf = CSRFProtect()
```

```python
# miapp/models.py
from flask_login import UserMixin
from sqlalchemy.orm import Mapped, mapped_column
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager


class User(UserMixin, db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True, index=True)
    password_hash: Mapped[str]

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)  # scrypt por defecto en Werkzeug 3

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    return db.session.get(User, int(user_id))
```

```python
# miapp/auth/forms.py
from flask_wtf import FlaskForm
from wtforms import BooleanField, PasswordField, StringField
from wtforms.validators import DataRequired, Email, Length


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Contraseña", validators=[DataRequired(), Length(min=8)])
    remember = BooleanField("Recordarme")
```

```python
# miapp/auth/routes.py
from urllib.parse import urlsplit

from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required, login_user, logout_user

from ..extensions import db
from ..models import User
from . import bp
from .forms import LoginForm


@bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.execute(db.select(User).filter_by(email=form.email.data.lower())).scalar_one_or_none()
        if user is None or not user.check_password(form.password.data):
            flash("Email o contraseña incorrectos.")
            return render_template("auth/login.html", form=form), 401
        login_user(user, remember=form.remember.data)
        next_url = request.args.get("next")
        if not next_url or urlsplit(next_url).netloc:  # solo rutas relativas: evita open redirect
            next_url = url_for("pedidos.listar")
        return redirect(next_url)
    return render_template("auth/login.html", form=form)


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
```

```html
<!-- templates/auth/login.html -->
<form method="post">
  {{ form.hidden_tag() }}   {# incluye el token CSRF #}
  {{ form.email.label }} {{ form.email(autocomplete="email") }}
  {{ form.password.label }} {{ form.password(autocomplete="current-password") }}
  {{ form.remember() }} {{ form.remember.label }}
  <button type="submit">Entrar</button>
</form>
```

En `create_app`: `login_manager.init_app(app)` y `csrf.init_app(app)`. Con `CSRFProtect` global, **todo** POST/PUT/PATCH/DELETE exige token, incluido el `logout` (por eso es `@bp.post` con un pequeño formulario, no un enlace `GET`: un logout por GET se puede provocar con una imagen en otra web).

Configuración de la cookie de sesión, en `ProdConfig`:

```python
SECRET_KEY = os.environ["SECRET_KEY"]
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
REMEMBER_COOKIE_SECURE = True
REMEMBER_COOKIE_HTTPONLY = True
PERMANENT_SESSION_LIFETIME = timedelta(hours=12)
```

Decisiones que no son obvias:

- **El mismo mensaje para «no existe» y «contraseña incorrecta»**, y un `401` para que el test lo distinga del éxito sin leer el HTML.
- **Validación del `next`**: Flask-Login añade `?next=/ruta` al redirigir; sin comprobar que es relativa, `?next=https://malo.example` convierte tu login en un *open redirect*.
- **`session_protection = "strong"`**: si cambia la huella del cliente, la sesión se descarta. Cuesta algún relogin en redes móviles; vale la pena para una app con datos de clientes.
- **`generate_password_hash`** usa scrypt por defecto en Werkzeug 3 y guarda el método en el hash, así que puedes cambiarlo en el futuro sin romper los existentes.

Queda fuera, y debes decidirlo: límite de intentos por IP/usuario (en el proxy o con Flask-Limiter) y recuperación de contraseña por email con token caducable (`itsdangerous.URLSafeTimedSerializer`, que también viene con Flask).""",
            },
        ]
    },
    # 29) Testing de Flask con usuario logueado.
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Cómo pruebo rutas de Flask que exigen usuario logueado (Flask-Login) sin tener que hacer POST al formulario de login en cada test? Y el CSRF me rompe los POST en los tests.",
            },
            {
                "role": "assistant",
                "content": r"""Tres fixtures: una app con configuración de pruebas (CSRF desactivado), un cliente, y un `logged_in_client` que escribe directamente en la sesión lo que Flask-Login espera.

```python
# tests/conftest.py
import pytest

from miapp import create_app
from miapp.extensions import db
from miapp.models import User


class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False   # los tests prueban la lógica, no el token
    SECRET_KEY = "test"


@pytest.fixture
def app():
    app = create_app("tests.conftest.TestConfig")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def user(app):
    u = User(email="ana@example.com")
    u.set_password("una-contraseña-larga")
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture
def logged_in_client(client, user):
    with client.session_transaction() as session:
        session["_user_id"] = str(user.id)   # la clave que lee Flask-Login
        session["_fresh"] = True
    return client
```

Tests:

```python
def test_lista_pedidos_exige_login(client):
    r = client.get("/pedidos/")
    assert r.status_code == 302
    assert r.headers["Location"].startswith("/auth/login")


def test_lista_pedidos_con_usuario(logged_in_client):
    r = logged_in_client.get("/pedidos/")
    assert r.status_code == 200


def test_crear_pedido_post(logged_in_client):
    r = logged_in_client.post("/pedidos/", data={"producto_id": 1, "cantidad": 2}, follow_redirects=True)
    assert r.status_code == 200
    assert b"Pedido creado" in r.data


def test_login_real_una_vez(client, user):
    r = client.post("/auth/login", data={"email": user.email, "password": "una-contraseña-larga"})
    assert r.status_code == 302
```

Por qué así:

- **`session_transaction()`** abre la sesión del cliente de pruebas, te deja modificarla y la vuelve a firmar al salir del `with`. Flask-Login guarda el id en `_user_id`; con `_fresh = True` pasas también las vistas con `@fresh_login_required`.
- **Un solo test hace el login de verdad** (`test_login_real_una_vez`): cubre el formulario, el hash y la redirección. Los demás no repiten ese camino; si el login se rompe, falla uno, no cuarenta.
- **`WTF_CSRF_ENABLED = False`** solo en tests. El token lo cubres con un test aparte que active CSRF y compruebe que un POST sin token devuelve 400:

```python
def test_csrf_activo_rechaza_post_sin_token(app, logged_in_client):
    app.config["WTF_CSRF_ENABLED"] = True
    r = logged_in_client.post("/pedidos/", data={"producto_id": 1, "cantidad": 2})
    assert r.status_code == 400
```

- **`db.session.remove()` en el teardown** evita que una sesión abierta de un test contamine el siguiente (y los `DetachedInstanceError` esporádicos que vienen de ahí).

Alternativa si no quieres tocar la sesión a mano: `app.config["LOGIN_DISABLED"] = True` hace que `@login_required` deje pasar a todo el mundo, pero `current_user` será anónimo, así que cualquier vista que use `current_user.id` falla. Sirve para pruebas de plantillas, no para lógica por usuario.""",
            },
        ]
    },
    # 30) Revisión estricta: manejo de errores en API JSON (system variante).
    {
        "messages": [
            {"role": "system", "content": "Eres un revisor de código estricto. Señala problemas concretos y propone el arreglo mínimo."},
            {
                "role": "user",
                "content": r"""Revisa el manejo de errores de esta API en Flask, me parece que está bien pero el frontend se queja de respuestas inconsistentes:

```python
@app.route("/api/pedidos/<int:pedido_id>", methods=["GET"])
def get_pedido(pedido_id):
    try:
        pedido = Pedido.query.get(pedido_id)
        if not pedido:
            return jsonify({"error": "no encontrado"}), 404
        return jsonify(pedido.to_dict())
    except Exception as e:
        return str(e), 500


@app.route("/api/pedidos", methods=["POST"])
def crear_pedido():
    data = request.json
    if not data["producto_id"]:
        return "falta producto_id", 400
    pedido = Pedido(producto_id=data["producto_id"], cantidad=data.get("cantidad", 1))
    db.session.add(pedido)
    db.session.commit()
    return jsonify(pedido.to_dict())
```""",
            },
            {
                "role": "assistant",
                "content": r"""Siete problemas, ordenados por impacto. El que explica la queja del frontend es el primero.

**1. Tres formatos de error distintos.** 404 devuelve JSON; 400 y 500 devuelven texto plano con `Content-Type: text/html`. El cliente no puede hacer `response.json()` de forma fiable. Y cualquier error que Flask genere por su cuenta (405, 415, 404 de ruta inexistente) devuelve HTML.

**2. `except Exception as e: return str(e), 500`** expone mensajes internos (SQL, rutas de ficheros) al cliente y **no registra la traza**: el error desaparece. Además está en una ruta y no en la otra; `crear_pedido` ya devuelve 500 con HTML si algo falla.

**3. `data["producto_id"]`** lanza `KeyError` si el campo falta → 500 en vez de 400. Y `if not data["producto_id"]` rechaza `0`, que puede o no ser válido; compara con `None`.

**4. POST responde 200**; un recurso creado es `201`.

**5. `Pedido.query.get`** es la API heredada de Flask-SQLAlchemy; en 3.x es `db.session.get(Pedido, id)` o directamente `db.get_or_404`.

**6. Sin manejo de `IntegrityError`** (por ejemplo `producto_id` inexistente): cae en el 500 genérico. Es un error del cliente, debería ser 400 o 409.

**7. Los `try/except` por ruta se repiten.** Con 30 rutas serán 30 copias; el manejo de errores va en un único sitio.

**Arreglo mínimo:** handlers globales que garanticen JSON siempre, y rutas sin `try/except`.

```python
import logging

from flask import abort, jsonify, request
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException

log = logging.getLogger(__name__)


@app.errorhandler(HTTPException)
def handle_http_error(exc: HTTPException):
    return jsonify(error=exc.name.lower().replace(" ", "_"), message=exc.description), exc.code


@app.errorhandler(IntegrityError)
def handle_integrity_error(exc: IntegrityError):
    db.session.rollback()
    return jsonify(error="integrity_error", message="referencia inválida o duplicada"), 409


@app.errorhandler(Exception)
def handle_unexpected(exc: Exception):
    log.exception("error no controlado")   # traza completa al log, nada al cliente
    db.session.rollback()
    return jsonify(error="internal_error", message="error interno"), 500


@app.get("/api/pedidos/<int:pedido_id>")
def get_pedido(pedido_id: int):
    pedido = db.get_or_404(Pedido, pedido_id, description="pedido no encontrado")
    return jsonify(pedido.to_dict())


@app.post("/api/pedidos")
def crear_pedido():
    data = request.get_json()
    if not isinstance(data, dict) or data.get("producto_id") is None:
        abort(400, description="falta producto_id")
    cantidad = data.get("cantidad", 1)
    if not isinstance(cantidad, int) or cantidad < 1:
        abort(400, description="cantidad debe ser un entero >= 1")
    pedido = Pedido(producto_id=data["producto_id"], cantidad=cantidad)
    db.session.add(pedido)
    db.session.commit()
    return jsonify(pedido.to_dict()), 201
```

Resultado: **toda** respuesta de error es `{"error": "...", "message": "..."}` con el código correcto, incluidos los que genera Flask (`405 method_not_allowed`, `415 unsupported_media_type` cuando el cliente olvida `Content-Type: application/json`).

Un detalle del handler de `Exception`: con `app.debug = True` Flask lo ignora y muestra el debugger, que es lo que quieres en desarrollo; en producción captura todo.

Siguiente paso cuando el número de campos crezca: un esquema de validación (Pydantic o marshmallow) en lugar de `isinstance` a mano. No lo incluyo porque cambia la dependencia del proyecto; decídelo aparte.""",
            },
        ]
    },
]
