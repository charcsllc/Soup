"""04_frameworks / 07: Axum 0.8, Actix-web 4 y tokio (reparto 14 / 6 / 10)."""

SISTEMA = (
    "Eres un asistente experto en programación, análisis y razonamiento. Respondes en el "
    "idioma del usuario (español por defecto), con precisión y sin relleno, y verificas tu "
    "trabajo antes de responder."
)

ROWS = [
    # ---------------------------------------------------------------- Axum (14)
    # 1) Estructura de proyecto, Router<AppState> y estado compartido (system exacto).
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Estoy empezando una API en Rust con Axum 0.8 y Postgres con sqlx. ¿Cómo organizo el proyecto (módulos, estado compartido, rutas) para que no acabe todo en main.rs?",
            },
            {
                "role": "assistant",
                "content": r"""Separa tres cosas desde el primer día: **arranque** (`main.rs`), **construcción del `Router`** (`lib.rs`, para que los tests lo reutilicen sin levantar un servidor) y **acceso a datos** (que no sabe nada de HTTP).

```
src/
  main.rs          # config, pool, tracing, serve
  lib.rs           # build_app(state) -> Router
  state.rs         # AppState
  error.rs         # AppError + IntoResponse
  routes/
    mod.rs         # compone los routers de cada recurso
    items.rs       # handlers de /items
  db/
    mod.rs
    items.rs       # consultas sqlx
migrations/        # sqlx migrate add -r <nombre>
```

**Estado.** Un `struct` `Clone`. `PgPool` ya es un `Arc` por dentro, así que clonarlo es barato; solo necesitas `Arc<AppState>` si añades campos que no sean `Clone`.

```rust
// state.rs
use sqlx::PgPool;

#[derive(Clone)]
pub struct AppState {
    pub pool: PgPool,
}
```

**Rutas por recurso.** Cada módulo devuelve un `Router<AppState>`; el estado se inyecta una sola vez arriba con `with_state`, que convierte el router en `Router<()>` listo para servir.

```rust
// routes/items.rs
use axum::{extract::{Path, State}, http::StatusCode, routing::get, Json, Router};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::{db, error::AppError, state::AppState};

#[derive(Serialize)]
pub struct Item {
    pub id: Uuid,
    pub name: String,
}

#[derive(Deserialize)]
pub struct NewItem {
    pub name: String,
}

pub fn router() -> Router<AppState> {
    Router::new()
        .route("/items", get(list).post(create))
        .route("/items/{id}", get(get_one)) // sintaxis de 0.8: {id}, no :id
}

async fn list(State(state): State<AppState>) -> Result<Json<Vec<Item>>, AppError> {
    Ok(Json(db::items::list(&state.pool).await?))
}

async fn get_one(State(state): State<AppState>, Path(id): Path<Uuid>) -> Result<Json<Item>, AppError> {
    db::items::find(&state.pool, id).await?.map(Json).ok_or(AppError::NotFound)
}

async fn create(
    State(state): State<AppState>,
    Json(body): Json<NewItem>,
) -> Result<(StatusCode, Json<Item>), AppError> {
    let item = db::items::insert(&state.pool, &body.name).await?;
    Ok((StatusCode::CREATED, Json(item)))
}
```

```rust
// routes/mod.rs
pub mod items;

use axum::Router;

use crate::state::AppState;

pub fn api() -> Router<AppState> {
    Router::new().merge(items::router())
}
```

```rust
// db/items.rs: no importa nada de axum
use sqlx::PgPool;
use uuid::Uuid;

use crate::routes::items::Item;

pub async fn list(pool: &PgPool) -> sqlx::Result<Vec<Item>> {
    sqlx::query_as!(Item, "SELECT id, name FROM items ORDER BY name").fetch_all(pool).await
}

pub async fn find(pool: &PgPool, id: Uuid) -> sqlx::Result<Option<Item>> {
    sqlx::query_as!(Item, "SELECT id, name FROM items WHERE id = $1", id).fetch_optional(pool).await
}

pub async fn insert(pool: &PgPool, name: &str) -> sqlx::Result<Item> {
    sqlx::query_as!(Item, "INSERT INTO items (id, name) VALUES (gen_random_uuid(), $1) RETURNING id, name", name)
        .fetch_one(pool)
        .await
}
```

**Errores.** Un enum propio que implementa `IntoResponse`; los handlers devuelven `Result<_, AppError>` y el `?` sobre `sqlx::Error` funciona gracias al `#[from]`.

```rust
// error.rs
use axum::{http::StatusCode, response::{IntoResponse, Response}, Json};
use serde_json::json;

#[derive(Debug, thiserror::Error)]
pub enum AppError {
    #[error("not found")]
    NotFound,
    #[error(transparent)]
    Db(#[from] sqlx::Error),
}

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let (status, message) = match &self {
            AppError::NotFound => (StatusCode::NOT_FOUND, self.to_string()),
            AppError::Db(err) => {
                tracing::error!(error = ?err, "fallo de base de datos");
                (StatusCode::INTERNAL_SERVER_ERROR, "internal error".to_string())
            }
        };
        (status, Json(json!({ "error": message }))).into_response()
    }
}
```

**Construcción y arranque.**

```rust
// lib.rs
pub mod db;
pub mod error;
pub mod routes;
pub mod state;

use axum::Router;
use tower_http::trace::TraceLayer;

use state::AppState;

pub fn build_app(state: AppState) -> Router {
    Router::new()
        .nest("/api", routes::api())
        .layer(TraceLayer::new_for_http())
        .with_state(state)
}
```

```rust
// main.rs
use std::net::SocketAddr;

use sqlx::postgres::PgPoolOptions;
use tokio::net::TcpListener;
use tracing_subscriber::EnvFilter;

use api::{build_app, state::AppState};

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt().with_env_filter(EnvFilter::from_default_env()).init();

    let database_url = std::env::var("DATABASE_URL")?;
    let pool = PgPoolOptions::new().max_connections(10).connect(&database_url).await?;
    sqlx::migrate!("./migrations").run(&pool).await?;

    let addr = SocketAddr::from(([0, 0, 0, 0], 8080));
    let listener = TcpListener::bind(addr).await?;
    tracing::info!(%addr, "escuchando");
    axum::serve(listener, build_app(AppState { pool })).await?;
    Ok(())
}
```

Dependencias (`Cargo.toml`), con las versiones que corresponden a esta sintaxis:

```toml
[dependencies]
axum = "0.8"
tokio = { version = "1", features = ["full"] }
tower-http = { version = "0.6", features = ["trace"] }
sqlx = { version = "0.8", features = ["runtime-tokio", "postgres", "migrate", "uuid"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
uuid = { version = "1", features = ["serde", "v4"] }
thiserror = "2"
anyhow = "1"
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter"] }
```

Por qué así:

- `build_app` en `lib.rs` es lo que permite tests con `tower::ServiceExt::oneshot` sin puerto ni proceso.
- `Router<AppState>` en los submódulos y un único `with_state` evita el error clásico «expected `Router<()>`, found `Router<AppState>`» al anidar.
- `db/` devuelve `sqlx::Result`; la traducción a códigos HTTP vive solo en `error.rs`.

Comprobación: `DATABASE_URL=postgres://... cargo run`, y `curl -s localhost:8080/api/items` debe responder `[]` con 200; un `GET /api/items/<uuid inexistente>` devuelve `{"error":"not found"}` con 404.""",
            },
        ]
    },
    # 2) Handler que no compila: orden de extractores (usuario trae error).
    {
        "messages": [
            {
                "role": "user",
                "content": """No compila un handler de Axum y el error es kilométrico. Lo relevante creo que es esto:

```
error[E0277]: the trait bound `fn(Json<CreateOrder>, Path<Uuid>, State<AppState>) -> impl Future<Output = Result<Json<Order>, AppError>> {create_order}: Handler<_, _>` is not satisfied
   --> src/routes/orders.rs:31:40
    |
31  |         .route("/customers/{id}/orders", post(create_order))
    |                                          ---- ^^^^^^^^^^^^ the trait `Handler<_, _>` is not implemented
```

El handler:

```rust
async fn create_order(
    Json(body): Json<CreateOrder>,
    Path(customer_id): Path<Uuid>,
    State(state): State<AppState>,
) -> Result<Json<Order>, AppError> {
    let order = db::orders::create(&state.pool, customer_id, body).await?;
    Ok(Json(order))
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""`Json` consume el cuerpo de la petición y por eso **tiene que ser el último argumento**. Axum distingue dos familias de extractores:

- `FromRequestParts` (`Path`, `Query`, `State`, `HeaderMap`, `Extension`, tus extractores de auth): leen cabeceras, URI o estado. Pueden ir en cualquier orden y repetirse.
- `FromRequest` (`Json`, `Form`, `String`, `Bytes`, `Multipart`, `Request`): consumen el cuerpo. Solo puede haber **uno** y va al final.

Con `Json` en primera posición, el `impl Handler` no encaja y el compilador te da ese error genérico.

Arreglo:

```rust
async fn create_order(
    State(state): State<AppState>,
    Path(customer_id): Path<Uuid>,
    Json(body): Json<CreateOrder>,
) -> Result<Json<Order>, AppError> {
    let order = db::orders::create(&state.pool, customer_id, body).await?;
    Ok(Json(order))
}
```

**Para no volver a adivinar**, activa la feature `macros` y anota el handler:

```toml
axum = { version = "0.8", features = ["macros"] }
```

```rust
#[axum::debug_handler]
async fn create_order(/* igual */) -> Result<Json<Order>, AppError> { /* igual */ }
```

Con tu versión original, el mensaje pasa a ser directo: «`Json<_>` consumes the request body and thus must be the last argument to the handler function». Cuesta cero en tiempo de compilación en release (el macro solo genera comprobaciones) y te señala también las otras tres causas que producen exactamente el mismo `Handler<_, _> is not satisfied`:

1. **El futuro no es `Send`.** Un `std::sync::MutexGuard` o un `Rc` vivo a través de un `.await` dentro del handler. `debug_handler` lo dice con el tipo culpable.
2. **El estado no coincide.** `State<AppState>` en el handler pero `.with_state(Arc::new(state))` en el router (o al revés). Los tipos tienen que ser idénticos, o `AppState` tiene que implementar `FromRef` del estado real.
3. **El tipo de retorno no es `IntoResponse`.** Por ejemplo `Result<Json<Order>, sqlx::Error>`: `sqlx::Error` no implementa `IntoResponse`, de ahí que convenga un `AppError` propio.

Verificación rápida: tras reordenar, `cargo check` debe pasar; y una petición sin cuerpo JSON válido devolverá 422 (`JsonRejection`) sin llegar a tu código, lo que confirma que el extractor está en su sitio.""",
            },
        ]
    },
    # 3) Inglés, multiturno: tipo de error propio y formato uniforme de rechazos.
    {
        "messages": [
            {
                "role": "user",
                "content": "How do you structure error handling in Axum 0.8? I keep writing `(StatusCode::INTERNAL_SERVER_ERROR, e.to_string()).into_response()` in every handler and it's getting ugly.",
            },
            {
                "role": "assistant",
                "content": r"""One error enum for the whole crate, one `IntoResponse` impl, and handlers that return `Result<T, AppError>` so `?` does the mapping. The tuple you keep writing moves into that single impl and never shows up in a handler again.

```rust
// error.rs
use axum::{http::StatusCode, response::{IntoResponse, Response}, Json};
use serde_json::json;

#[derive(Debug, thiserror::Error)]
pub enum AppError {
    #[error("{0} not found")]
    NotFound(&'static str),
    #[error("{0}")]
    Validation(String),
    #[error("unauthorized")]
    Unauthorized,
    #[error(transparent)]
    Db(#[from] sqlx::Error),
    #[error(transparent)]
    Unexpected(#[from] anyhow::Error),
}

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        let (status, message) = match &self {
            AppError::NotFound(_) => (StatusCode::NOT_FOUND, self.to_string()),
            AppError::Validation(msg) => (StatusCode::UNPROCESSABLE_ENTITY, msg.clone()),
            AppError::Unauthorized => (StatusCode::UNAUTHORIZED, self.to_string()),
            AppError::Db(sqlx::Error::RowNotFound) => (StatusCode::NOT_FOUND, "not found".into()),
            AppError::Db(err) => {
                tracing::error!(error = ?err, "database error");
                (StatusCode::INTERNAL_SERVER_ERROR, "internal error".into())
            }
            AppError::Unexpected(err) => {
                tracing::error!(error = ?err, "unexpected error");
                (StatusCode::INTERNAL_SERVER_ERROR, "internal error".into())
            }
        };
        (status, Json(json!({ "error": message }))).into_response()
    }
}
```

A handler then reads like business logic:

```rust
async fn get_order(State(state): State<AppState>, Path(id): Path<Uuid>) -> Result<Json<Order>, AppError> {
    let order = sqlx::query_as!(Order, "SELECT id, total_cents FROM orders WHERE id = $1", id)
        .fetch_optional(&state.pool)
        .await?                       // sqlx::Error -> AppError::Db
        .ok_or(AppError::NotFound("order"))?;
    Ok(Json(order))
}
```

Three design decisions worth being explicit about:

- **Client-facing text vs. logged detail.** 4xx variants echo their message; 5xx variants log the full error with `tracing` and return a fixed `"internal error"`. Leaking `e.to_string()` for a 500 is how connection strings and table names end up in API responses.
- **`anyhow` as the catch-all.** Anything that is not a domain error (`reqwest`, parsing, a third-party crate) converts via `.context("calling payments")?` into `Unexpected`, so you keep one `From` impl instead of one variant per library.
- **`thiserror` 2** for the enum, not a hand-written `Display`. `#[error(transparent)]` forwards `Display` and `source()` from the wrapped error, which is what the log line needs.

Check: `curl -i localhost:8080/orders/00000000-0000-0000-0000-000000000000` must return `404` with `{"error":"order not found"}`, and a deliberately broken `DATABASE_URL` must return `500` with `{"error":"internal error"}` while the real cause shows up in the logs.""",
            },
            {
                "role": "user",
                "content": "Nice. But when the request body is bad, Axum's own `Json` rejection still comes back as a plain-text 422. Can those use the same `{\"error\": ...}` shape?",
            },
            {
                "role": "assistant",
                "content": r"""Yes: wrap `Json` in your own extractor whose rejection is `AppError`. The shortest way in 0.8 is the `FromRequest` derive (feature `macros`) with `via` and `rejection`:

```rust
use axum::extract::rejection::JsonRejection;

#[derive(axum::extract::FromRequest)]
#[from_request(via(axum::Json), rejection(AppError))]
pub struct AppJson<T>(pub T);

impl From<JsonRejection> for AppError {
    fn from(rejection: JsonRejection) -> Self {
        // body_text() is the human-readable reason; status() tells 400 (syntax) from 422 (shape) from 415 (content-type)
        AppError::Validation(format!("{}: {}", rejection.status(), rejection.body_text()))
    }
}
```

Then replace `Json<T>` with `AppJson<T>` in the handlers that take a body:

```rust
async fn create_order(
    State(state): State<AppState>,
    AppJson(body): AppJson<CreateOrder>,
) -> Result<(StatusCode, Json<Order>), AppError> {
    let order = db::orders::create(&state.pool, body).await?;
    Ok((StatusCode::CREATED, Json(order)))
}
```

If you would rather not depend on the derive, the manual impl is ten lines and shows what the macro generates. Note that Axum 0.8 uses native `async fn` in traits, so there is no `#[async_trait]` anymore:

```rust
use axum::extract::{FromRequest, Request};

impl<S, T> FromRequest<S> for AppJson<T>
where
    axum::Json<T>: FromRequest<S, Rejection = JsonRejection>,
    S: Send + Sync,
{
    type Rejection = AppError;

    async fn from_request(req: Request, state: &S) -> Result<Self, Self::Rejection> {
        let axum::Json(value) = axum::Json::<T>::from_request(req, state).await?;
        Ok(AppJson(value))
    }
}
```

One caveat: this only covers `Json`. `Path` and `Query` rejections (a non-UUID in the URL, a missing query parameter) are still plain text unless you wrap those too, same pattern via `FromRequestParts`. Do `Path` next, because a malformed id is the most common client mistake after a bad body.

Check: `curl -i -X POST localhost:8080/orders -H 'content-type: application/json' -d '{"total_cents": "ten"}'` returns `422` with `{"error":"422 Unprocessable Entity: Failed to deserialize the JSON body into the target type: total_cents: invalid type: string \"ten\", expected i64 at line 1 column 21"}`. Keep the detail for 4xx: it is the client's own input, not internal state.""",
            },
        ]
    },
    # 4) Middleware tower-http: orden de capas, timeout, CORS (system variante).
    {
        "messages": [
            {"role": "system", "content": "Responde en español y cita la versión de cada crate que uses."},
            {
                "role": "user",
                "content": "¿Qué middlewares de tower-http pongo en una API Axum de producción y en qué orden? Me lío con `.layer()` repetido y con `ServiceBuilder`, y no sé si el timeout necesita `HandleErrorLayer` como en versiones viejas.",
            },
            {
                "role": "assistant",
                "content": r"""Cuatro capas cubren el 90 % de una API pública: trazas, timeout, límite de tamaño del cuerpo y CORS. Con `tower-http` 0.6 ninguna necesita `HandleErrorLayer`: `TimeoutLayer` responde 408 por sí sola y `RequestBodyLimitLayer` responde 413. Eso cambió en tower-http 0.5; el patrón con `HandleErrorLayer` que verás en tutoriales es de Axum 0.6.

```toml
axum = "0.8"
tower = "0.5"
tower-http = { version = "0.6", features = ["trace", "timeout", "cors", "limit"] }
```

```rust
use std::time::Duration;

use axum::{
    http::{header, HeaderValue, Method},
    Router,
};
use tower::ServiceBuilder;
use tower_http::{
    cors::CorsLayer,
    limit::RequestBodyLimitLayer,
    timeout::TimeoutLayer,
    trace::TraceLayer,
};

pub fn build_app(state: AppState, allowed_origin: &str) -> Router {
    let cors = CorsLayer::new()
        .allow_origin(allowed_origin.parse::<HeaderValue>().expect("origen válido"))
        .allow_methods([Method::GET, Method::POST, Method::PUT, Method::DELETE])
        .allow_headers([header::CONTENT_TYPE, header::AUTHORIZATION])
        .max_age(Duration::from_secs(3600));

    Router::new()
        .nest("/api", routes::api())
        .layer(
            ServiceBuilder::new()
                .layer(TraceLayer::new_for_http())          // 1.º: ve toda petición, incluidas las que el timeout corta
                .layer(TimeoutLayer::new(Duration::from_secs(10)))
                .layer(RequestBodyLimitLayer::new(1024 * 1024)) // 1 MiB
                .layer(cors),                                // último: más cerca del handler
        )
        .with_state(state)
}
```

**El orden.** Con `ServiceBuilder`, las capas se aplican **de arriba abajo**: la primera envuelve a todas las demás y es la primera que ve la petición. Con `.layer()` llamado varias veces sobre el `Router` ocurre lo contrario: la última que añades es la más externa. Por eso `ServiceBuilder`: el código se lee en el mismo orden en que viaja la petición.

Qué va fuera y por qué:

- **`TraceLayer` lo más externo**, para que un 408 del timeout o un 413 del límite queden registrados con su latencia. Si lo pones dentro del timeout, las peticiones cortadas no dejan traza.
- **`TimeoutLayer` antes del límite de cuerpo**: leer un cuerpo lento también cuenta contra el timeout.
- **`CorsLayer` con `.layer()` del router, no con `.route_layer()`**: el *preflight* `OPTIONS` no coincide con ninguna ruta tuya, y `route_layer` solo corre en rutas que existen. Con `.layer()` el middleware intercepta el `OPTIONS` antes del enrutado.

Dos avisos:

- `CorsLayer::permissive()` y `CorsLayer::very_permissive()` son para desarrollo. En producción, lista de orígenes explícita; si necesitas cookies, además `.allow_credentials(true)`, que es incompatible con `Any` como origen (tower-http entra en pánico al construir la capa, a propósito).
- El timeout corta la **respuesta**, no el trabajo: si el handler sigue haciendo una consulta de 30 s, la base de datos la termina igual. Pon también timeouts en el pool de sqlx (`acquire_timeout`) y en `reqwest`.

Comprobación: un handler de prueba con `tokio::time::sleep(Duration::from_secs(11))` debe devolver `408 Request Timeout` a los 10 s y aparecer en el log de `TraceLayer` con `latency=10000 ms`; un `curl -X OPTIONS -H 'Origin: https://otro.example' -H 'Access-Control-Request-Method: POST'` debe venir sin `Access-Control-Allow-Origin`.""",
            },
        ]
    },
    # 5) middleware::from_fn_with_state, route_layer vs layer, extensiones.
    {
        "messages": [
            {
                "role": "user",
                "content": "Quiero proteger solo las rutas `/admin/*` de mi API Axum con una API key en cabecera, sin tocar cada handler. ¿Middleware? ¿Y cómo accedo al estado (la lista de claves) desde ahí?",
            },
            {
                "role": "assistant",
                "content": r"""Un middleware con `axum::middleware::from_fn_with_state`, aplicado solo al sub-router de `/admin`. El estado llega como extractor, igual que en un handler.

```rust
use std::sync::Arc;

use axum::{
    extract::{Request, State},
    http::StatusCode,
    middleware::{self, Next},
    response::Response,
    routing::get,
    Router,
};

#[derive(Clone)]
pub struct AppState {
    pub api_keys: Arc<std::collections::HashSet<String>>,
}

#[derive(Clone)]
pub struct AdminKey(pub String); // queda disponible para los handlers vía Extension

async fn require_api_key(
    State(state): State<AppState>,
    mut req: Request,
    next: Next,
) -> Result<Response, StatusCode> {
    let key = req
        .headers()
        .get("x-api-key")
        .and_then(|value| value.to_str().ok())
        .ok_or(StatusCode::UNAUTHORIZED)?;

    if !state.api_keys.contains(key) {
        return Err(StatusCode::FORBIDDEN);
    }
    req.extensions_mut().insert(AdminKey(key.to_owned()));
    Ok(next.run(req).await)
}

fn admin_routes(state: AppState) -> Router<AppState> {
    Router::new()
        .route("/stats", get(stats))
        .route("/users", get(list_users))
        .route_layer(middleware::from_fn_with_state(state, require_api_key))
}

pub fn build_app(state: AppState) -> Router {
    Router::new()
        .route("/health", get(|| async { "ok" }))
        .nest("/admin", admin_routes(state.clone()))
        .with_state(state)
}

async fn stats(axum::Extension(AdminKey(key)): axum::Extension<AdminKey>) -> String {
    format!("stats para la clave que termina en {}", &key[key.len().saturating_sub(4)..])
}

async fn list_users() -> &'static str {
    "[]"
}
```

Detalles que importan:

- **Firma del middleware.** Primero los extractores (`State`, `HeaderMap`, los que necesites), luego `Request`, y `Next` al final. En 0.8 `Next` ya no es genérico. Devolver `Result<Response, StatusCode>` sirve porque ambos implementan `IntoResponse`; si quieres cuerpo JSON en el error, devuelve tu `AppError`.
- **`route_layer` en vez de `layer`.** `route_layer` solo se ejecuta cuando una ruta coincide: `GET /admin/no-existe` da **404**, no 401, y no filtras qué rutas existen a quien no tiene clave. `layer` envolvería también el *fallback*.
- **El estado del middleware y el del router no tienen por qué ser el mismo tipo**; aquí lo son porque es lo más simple. `from_fn_with_state` recibe su copia explícita, por eso `state.clone()` antes del `with_state` final.
- **`extensions_mut().insert`** es la forma de pasar algo del middleware al handler sin estado global; `Extension<AdminKey>` lo recupera. Si el handler lo pide y no está (por ejemplo, porque montaste el handler fuera de `/admin`), Axum responde 500 con un mensaje que lo dice.

Comparación de claves: `HashSet::contains` sobre strings no es de tiempo constante, pero para una API key de 32+ bytes aleatorios el canal lateral es irrelevante; si guardas hashes de las claves, compara con `subtle::ConstantTimeEq`.

Comprobación:

```bash
curl -i localhost:8080/admin/stats                      # 401
curl -i -H 'x-api-key: mala' localhost:8080/admin/stats # 403
curl -i -H 'x-api-key: <válida>' localhost:8080/admin/stats # 200
curl -i localhost:8080/admin/otra                        # 404, no 401
curl -i localhost:8080/health                            # 200 sin clave
```""",
            },
        ]
    },
    # 6) WebSockets con broadcast (vos, system variante).
    {
        "messages": [
            {"role": "system", "content": "Respondé en español rioplatense, con voseo."},
            {
                "role": "user",
                "content": "Necesito un chat mínimo con WebSockets en Axum 0.8: todo lo que manda uno lo reciben todos los conectados. ¿Me armás un ejemplo? Leí que en 0.8 cambió el tipo de `Message` y los ejemplos viejos no compilan.",
            },
            {
                "role": "assistant",
                "content": r"""Sí, cambió: en 0.8 `Message::Text` lleva un `Utf8Bytes` (no un `String`) y `Message::Binary` un `Bytes`. Los ejemplos viejos fallan con «expected `Utf8Bytes`, found `String`». Se arregla con `.into()` al enviar y con `.to_string()` o `as_str()` al leer.

El diseño: un `broadcast::channel` en el estado; cada conexión abre dos tareas, una que reenvía lo que llega por el canal al socket y otra que lee del socket y lo publica en el canal.

```toml
axum = { version = "0.8", features = ["ws"] }
tokio = { version = "1", features = ["full"] }
futures-util = "0.3"
```

```rust
use std::sync::Arc;

use axum::{
    extract::{
        ws::{Message, WebSocket, WebSocketUpgrade},
        State,
    },
    response::IntoResponse,
    routing::get,
    Router,
};
use futures_util::{SinkExt, StreamExt};
use tokio::sync::broadcast;

pub struct ChatState {
    tx: broadcast::Sender<String>,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let (tx, _rx) = broadcast::channel::<String>(256);
    let state = Arc::new(ChatState { tx });

    let app = Router::new()
        .route("/ws", get(ws_handler))
        .with_state(state);

    let listener = tokio::net::TcpListener::bind("0.0.0.0:8080").await?;
    axum::serve(listener, app).await?;
    Ok(())
}

async fn ws_handler(ws: WebSocketUpgrade, State(state): State<Arc<ChatState>>) -> impl IntoResponse {
    ws.on_upgrade(move |socket| handle_socket(socket, state))
}

async fn handle_socket(socket: WebSocket, state: Arc<ChatState>) {
    let (mut sink, mut stream) = socket.split();
    let mut rx = state.tx.subscribe();
    let tx = state.tx.clone();

    // canal -> socket
    let mut send_task = tokio::spawn(async move {
        loop {
            match rx.recv().await {
                Ok(text) => {
                    if sink.send(Message::Text(text.into())).await.is_err() {
                        break; // el cliente cerró
                    }
                }
                Err(broadcast::error::RecvError::Lagged(skipped)) => {
                    tracing::warn!(skipped, "cliente lento, se perdieron mensajes");
                }
                Err(broadcast::error::RecvError::Closed) => break,
            }
        }
    });

    // socket -> canal
    let mut recv_task = tokio::spawn(async move {
        while let Some(Ok(msg)) = stream.next().await {
            match msg {
                Message::Text(text) => {
                    // send falla solo si no hay receptores; no es un error
                    let _ = tx.send(text.to_string());
                }
                Message::Close(_) => break,
                _ => {} // Binary, Ping, Pong: Axum responde los ping solo
            }
        }
    });

    // si una tarea termina, cancelá la otra
    tokio::select! {
        _ = &mut send_task => recv_task.abort(),
        _ = &mut recv_task => send_task.abort(),
    }
}
```

Por qué está armado así:

- **`broadcast` y no `mpsc`**: cada suscriptor recibe una copia de cada mensaje. La capacidad (256) es por suscriptor; si un cliente no lee a tiempo, recibe `Lagged(n)` y sigue, no bloquea a los demás. Eso es exactamente lo que querés en un chat: un lento no frena al resto.
- **`socket.split()`** (de `futures_util::StreamExt`) te da sink y stream independientes para poder leer y escribir en dos tareas a la vez. Sin eso, una sola tarea que lee bloquearía los envíos.
- **`select!` con `abort`**: cuando el cliente cierra, la tarea de lectura termina; si no abortás la de escritura, queda viva para siempre esperando el canal. Es la fuga clásica de este patrón.
- `_rx` en `main` se descarta a propósito: `broadcast::channel` exige crear un receptor, pero no lo necesitás.

Probalo con `websocat`:

```bash
websocat ws://localhost:8080/ws   # en dos terminales; lo que escribís en una aparece en la otra
```

Si vas a pasarlo a producción, agregá un `TimeoutLayer` que **no** cubra `/ws` (una conexión larga no es una petición lenta) y un límite de tamaño de mensaje con `ws.max_message_size(64 * 1024)` antes de `on_upgrade`.""",
            },
        ]
    },
    # 7) Inglés: testing con tower::ServiceExt::oneshot e integración con puerto real.
    {
        "messages": [
            {
                "role": "user",
                "content": "What's the right way to test Axum handlers? Do I need to spin up a real server, or is there an in-process way?",
            },
            {
                "role": "assistant",
                "content": r"""In-process, for almost everything: a `Router` is a tower `Service`, so you call it with `oneshot` and never bind a port. Keep one real-socket test for the things only a socket exercises (graceful shutdown, keep-alive, your HTTP client's behavior).

Dev-dependencies:

```toml
[dev-dependencies]
tower = { version = "0.5", features = ["util"] }   # ServiceExt::oneshot
http-body-util = "0.1"                            # BodyExt::collect
serde_json = "1"
```

**Unit-style test, no network:**

```rust
use axum::{
    body::Body,
    http::{header, Request, StatusCode},
};
use http_body_util::BodyExt;
use tower::ServiceExt;

use api::{build_app, state::AppState};

#[tokio::test]
async fn creating_an_item_returns_201_and_the_item() {
    let app = build_app(AppState::for_tests().await);

    let response = app
        .oneshot(
            Request::builder()
                .method("POST")
                .uri("/api/items")
                .header(header::CONTENT_TYPE, "application/json")
                .body(Body::from(r#"{"name":"lamp"}"#))
                .unwrap(),
        )
        .await
        .unwrap();

    assert_eq!(response.status(), StatusCode::CREATED);
    let bytes = response.into_body().collect().await.unwrap().to_bytes();
    let json: serde_json::Value = serde_json::from_slice(&bytes).unwrap();
    assert_eq!(json["name"], "lamp");
    assert!(json["id"].is_string());
}

#[tokio::test]
async fn unknown_item_returns_404_json() {
    let app = build_app(AppState::for_tests().await);
    let response = app
        .oneshot(Request::get("/api/items/00000000-0000-0000-0000-000000000000").body(Body::empty()).unwrap())
        .await
        .unwrap();
    assert_eq!(response.status(), StatusCode::NOT_FOUND);
}
```

`oneshot` consumes the router; for several requests in one test, clone it first (`Router` is cheap to clone) and call `oneshot` on each clone. Middleware runs exactly as in production because you are calling the same `build_app`.

**Integration test over a real socket**, binding port 0 so tests can run in parallel:

```rust
#[tokio::test]
async fn server_answers_over_tcp() {
    let app = build_app(AppState::for_tests().await);
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    tokio::spawn(async move { axum::serve(listener, app).await.unwrap() });

    let body: serde_json::Value = reqwest::get(format!("http://{addr}/api/items"))
        .await
        .unwrap()
        .json()
        .await
        .unwrap();
    assert!(body.is_array());
}
```

**The database.** `AppState::for_tests()` is where the real decision lives. Two options that both work:

- A real Postgres per test run (Testcontainers, or `docker compose` in CI) plus `sqlx::migrate!` on a fresh schema. Slowest, most honest; catches SQL mistakes that `query!` cannot (wrong `WHERE`, missing index behavior).
- `#[sqlx::test]` (sqlx 0.8): creates an isolated database per test, runs migrations, hands you a `PgPool`, drops it afterward. Needs `DATABASE_URL` pointing at a server with `CREATE DATABASE` rights.

```rust
#[sqlx::test(migrations = "./migrations")]
async fn lists_items_in_name_order(pool: sqlx::PgPool) {
    let app = build_app(AppState { pool });
    // same oneshot pattern as above
}
```

Avoid mocking the pool behind a trait just for tests: you end up testing the mock, and `sqlx::test` is fast enough (tens of milliseconds per test after the first).

Run with `cargo test -- --test-threads=4`; if a test hangs, it is almost always a `TcpListener` that never got spawned, or a `reqwest` call with no timeout, so give the client `.timeout(Duration::from_secs(5))` in tests too.""",
            },
        ]
    },
    # 8) Migración Axum 0.7 -> 0.8: pánico por `:id`, Option<T> extractor (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": """Subí axum de 0.7 a 0.8 y ahora el servidor explota al arrancar:

```
thread 'main' panicked at /home/dev/.cargo/registry/src/index.crates.io-6f17d22bba15001f/axum-0.8.4/src/routing/path_router.rs:65:17:
Path segments must not start with `:`. For capture groups, use `{capture}`. If you meant to literally match a segment starting with a colon, call `without_v07_checks` on the router.
```

Tengo como 40 rutas. ¿Hay forma de no reescribirlas a mano?""",
            },
            {
                "role": "assistant",
                "content": r"""Es el cambio más visible de 0.8: la sintaxis de captura pasó de `:id` a `{id}` y de `*rest` a `{*rest}`, siguiendo el estilo de `matchit` 0.8 y de la especificación de URI templates. Se reescriben con un `sed`, no a mano:

```bash
# capturas :nombre -> {nombre}; comodín *nombre -> {*nombre}
grep -rl --include='*.rs' '\.route(' src | xargs sed -E -i \
  -e 's#/:([A-Za-z_][A-Za-z0-9_]*)#/{\1}#g' \
  -e 's#/\*([A-Za-z_][A-Za-z0-9_]*)#/{*\1}#g'
git diff --stat   # revisa: solo deben cambiar literales de rutas
```

Antes y después, para que lo contrastes con el diff:

```rust
// 0.7
.route("/users/:id/posts/:post_id", get(post))
.route("/static/*path", get(serve_file))

// 0.8
.route("/users/{id}/posts/{post_id}", get(post))
.route("/static/{*path}", get(serve_file))
```

Si alguna ruta tiene que coincidir con un literal `{` o `}`, se escapa doblándolo: `/api/{{literal}}`. El `without_v07_checks()` del mensaje solo desactiva la comprobación; no vuelve a la sintaxis vieja, así que no sirve como atajo.

Los otros cambios de 0.8 que te van a saltar en `cargo check` una vez pasen las rutas, en el orden en que suelen aparecer:

1. **`#[async_trait]` sobra.** `FromRequest` y `FromRequestParts` usan `async fn` nativo. Quita el atributo y la dependencia de `async-trait` si solo la usabas para esto.
2. **`Option<T>` como extractor cambió de semántica.** Antes `Option<Query<Filtros>>` devolvía `None` ante *cualquier* fallo, incluido un query string mal formado. Ahora `T` tiene que implementar `OptionalFromRequestParts` (o `OptionalFromRequest`), y los extractores de Axum devuelven `None` solo cuando el dato **no está**; si está y es inválido, rechazan con 400. Para tus extractores propios hay que implementar el trait nuevo (siguiente punto, si te pasa).
3. **`Host` se fue a `axum-extra`** (`axum_extra::extract::Host`).
4. **`Next` en middlewares ya no lleva genérico**: `next: Next`, no `next: Next<B>`.
5. **MSRV 1.75.**

Verificación: `cargo check` limpio, y un test de humo sobre una ruta con captura y otra con comodín:

```rust
#[tokio::test]
async fn captures_still_route() {
    let app = build_app(AppState::for_tests().await);
    let r = app.clone().oneshot(Request::get("/users/42/posts/7").body(Body::empty()).unwrap()).await.unwrap();
    assert_ne!(r.status(), StatusCode::NOT_FOUND);
    let r = app.oneshot(Request::get("/static/css/app.css").body(Body::empty()).unwrap()).await.unwrap();
    assert_ne!(r.status(), StatusCode::NOT_FOUND);
}
```""",
            },
            {
                "role": "user",
                "content": """Ya arranca. Ahora me pasa el punto 2: tengo un extractor `CurrentUser` propio (lee la cookie de sesión) y en varios handlers lo uso como `Option<CurrentUser>` para páginas públicas. Error:

```
error[E0277]: the trait bound `CurrentUser: OptionalFromRequestParts<AppState>` is not satisfied
```""",
            },
            {
                "role": "assistant",
                "content": r"""Implementa `OptionalFromRequestParts` para `CurrentUser` y decide explícitamente qué significa `None`: **sin cookie** → `None`; **con cookie inválida** → rechazo. Eso es lo que 0.8 quiere que escribas, porque antes el `Option` se tragaba también el segundo caso y una sesión caducada parecía un visitante anónimo.

```rust
use axum::{
    extract::{FromRequestParts, OptionalFromRequestParts},
    http::{header, request::Parts},
};

#[derive(Clone)]
pub struct CurrentUser {
    pub id: uuid::Uuid,
}

fn session_cookie(parts: &Parts) -> Option<&str> {
    parts
        .headers
        .get(header::COOKIE)?
        .to_str()
        .ok()?
        .split(';')
        .map(str::trim)
        .find_map(|pair| pair.strip_prefix("session="))
}

impl FromRequestParts<AppState> for CurrentUser {
    type Rejection = AppError;

    async fn from_request_parts(parts: &mut Parts, state: &AppState) -> Result<Self, Self::Rejection> {
        let token = session_cookie(parts).ok_or(AppError::Unauthorized)?;
        let id = state.sessions.lookup(token).await?.ok_or(AppError::Unauthorized)?;
        Ok(CurrentUser { id })
    }
}

impl OptionalFromRequestParts<AppState> for CurrentUser {
    type Rejection = AppError;

    async fn from_request_parts(
        parts: &mut Parts,
        state: &AppState,
    ) -> Result<Option<Self>, Self::Rejection> {
        if session_cookie(parts).is_none() {
            return Ok(None); // visitante anónimo
        }
        // hay cookie: una sesión caducada o manipulada es un error, no un anónimo
        <CurrentUser as FromRequestParts<AppState>>::from_request_parts(parts, state)
            .await
            .map(Some)
    }
}
```

Con esto los handlers quedan como los tenías:

```rust
async fn home(user: Option<CurrentUser>) -> Html<String> {
    match user {
        Some(u) => render_home_for(u.id),
        None => render_public_home(),
    }
}
```

Dos observaciones:

- Si prefieres el comportamiento antiguo (cualquier fallo → `None`), la implementación es `Ok(FromRequestParts::from_request_parts(parts, state).await.ok())`. No lo recomiendo: una cookie corrupta merece un 401 o un `Set-Cookie` que la borre, no una página pública silenciosa.
- La función auxiliar `session_cookie` evita duplicar el *parsing* en los dos `impl`; es lo que mantiene las dos semánticas alineadas cuando cambies el nombre de la cookie.

Test que fija la decisión:

```rust
#[tokio::test]
async fn expired_session_is_rejected_not_anonymous() {
    let app = build_app(AppState::for_tests().await);
    let r = app
        .oneshot(Request::get("/").header(header::COOKIE, "session=caducada").body(Body::empty()).unwrap())
        .await
        .unwrap();
    assert_eq!(r.status(), StatusCode::UNAUTHORIZED);
}
```""",
            },
        ]
    },
    # 9) Apagado ordenado con señales y Docker (México).
    {
        "messages": [
            {
                "role": "user",
                "content": "Cuando hacemos `docker stop` a la API de Axum se muere de golpe y cortamos peticiones a la mitad; luego en los logs del balanceador salen 502. ¿Cómo hago un apagado ordenado? Ahorita el `main` es un `axum::serve(listener, app).await` pelón.",
            },
            {
                "role": "assistant",
                "content": r"""Dos piezas: `with_graceful_shutdown` en Axum, y asegurarte de que la señal de Docker **llega** al proceso. Lo segundo falla más veces que lo primero.

**1. Axum: esperar a las peticiones en curso.**

```rust
use std::time::Duration;

use tokio::signal;
use tower_http::timeout::TimeoutLayer;

async fn shutdown_signal() {
    let ctrl_c = async {
        signal::ctrl_c().await.expect("no se pudo instalar el handler de Ctrl+C");
    };

    #[cfg(unix)]
    let terminate = async {
        signal::unix::signal(signal::unix::SignalKind::terminate())
            .expect("no se pudo instalar el handler de SIGTERM")
            .recv()
            .await;
    };

    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();

    tokio::select! {
        _ = ctrl_c => {},
        _ = terminate => {},
    }
    tracing::info!("señal recibida; dejo de aceptar conexiones y espero a las peticiones en curso");
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let app = build_app(state).layer(TimeoutLayer::new(Duration::from_secs(10)));
    let listener = tokio::net::TcpListener::bind("0.0.0.0:8080").await?;

    axum::serve(listener, app)
        .with_graceful_shutdown(shutdown_signal())
        .await?;

    tracing::info!("servidor cerrado");
    Ok(())
}
```

Qué hace `with_graceful_shutdown` cuando el futuro resuelve: cierra el *listener* (ya no acepta conexiones nuevas), manda `Connection: close` en las respuestas pendientes de keep-alive y espera a que terminen los handlers activos. No tiene límite de tiempo propio: por eso el `TimeoutLayer`, que acota cuánto puede durar un handler y, por tanto, el apagado.

**2. Docker: que SIGTERM llegue al binario.** `docker stop` envía SIGTERM al PID 1 y, tras 10 s por defecto, SIGKILL. Tres errores típicos:

- `CMD sh -c "./api"` en forma *shell*: el PID 1 es `sh`, que **no reenvía** SIGTERM. Usa la forma *exec*: `ENTRYPOINT ["/app/api"]`.
- Un `entrypoint.sh` que lanza la API sin `exec`: mismo problema. Termina el script con `exec /app/api`.
- Con `docker compose`, `stop_grace_period: 30s` si tus peticiones pueden durar más de 10 s. En Kubernetes es `terminationGracePeriodSeconds`.

**3. El balanceador.** Los 502 que ves salen porque el balanceador sigue mandando tráfico a un pod que ya cerró el listener. En Kubernetes la solución estándar es un `preStop` con `sleep 5` para dar tiempo a que el Endpoint se retire antes de que llegue el SIGTERM; en Docker con nginx delante, quita el upstream antes del `stop`.

Comprobación:

```bash
# terminal 1: una petición lenta (ponle un handler con sleep de 5 s para probar)
curl -s localhost:8080/api/lento &
# terminal 2, inmediatamente
docker stop <contenedor>
```

Debe pasar esto: el `curl` termina con 200, el log muestra «señal recibida» y luego «servidor cerrado», y `docker stop` tarda ~5 s, no 10. Si tarda exactamente 10 s, la señal no llegó al proceso: revisa el `ENTRYPOINT`.""",
            },
        ]
    },
    # 10) Extractor propio FromRequestParts con JWT y FromRef (system exacto).
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Quiero un extractor `AuthUser` para Axum 0.8 que lea el `Authorization: Bearer <jwt>`, lo valide con `jsonwebtoken` y falle con 401, para pedirlo como argumento en los handlers. La clave de firma está en el estado de la app.",
            },
            {
                "role": "assistant",
                "content": r"""Implementa `FromRequestParts` para `AuthUser` y pide la clave al estado con `FromRef`, de modo que el extractor funcione con cualquier estado que contenga las claves, no solo con tu `AppState` concreto.

```toml
axum = { version = "0.8", features = ["macros"] }
jsonwebtoken = "9"
```

```rust
use axum::{
    extract::{FromRef, FromRequestParts},
    http::{header, request::Parts},
};
use jsonwebtoken::{decode, Algorithm, DecodingKey, EncodingKey, Validation};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::error::AppError;

#[derive(Clone)]
pub struct JwtKeys {
    pub encoding: EncodingKey,
    pub decoding: DecodingKey,
}

impl JwtKeys {
    pub fn from_secret(secret: &[u8]) -> Self {
        Self {
            encoding: EncodingKey::from_secret(secret),
            decoding: DecodingKey::from_secret(secret),
        }
    }
}

#[derive(Clone, FromRef)]
pub struct AppState {
    pub pool: sqlx::PgPool,
    pub jwt: JwtKeys,
}

#[derive(Serialize, Deserialize)]
pub struct Claims {
    pub sub: Uuid,
    pub role: String,
    pub exp: usize, // segundos desde epoch; Validation lo comprueba por defecto
}

#[derive(Clone, Debug)]
pub struct AuthUser {
    pub id: Uuid,
    pub role: String,
}

impl<S> FromRequestParts<S> for AuthUser
where
    S: Send + Sync,
    JwtKeys: FromRef<S>,
{
    type Rejection = AppError;

    async fn from_request_parts(parts: &mut Parts, state: &S) -> Result<Self, Self::Rejection> {
        let token = parts
            .headers
            .get(header::AUTHORIZATION)
            .and_then(|value| value.to_str().ok())
            .and_then(|value| value.strip_prefix("Bearer "))
            .ok_or(AppError::Unauthorized)?;

        let keys = JwtKeys::from_ref(state);
        let mut validation = Validation::new(Algorithm::HS256);
        validation.leeway = 30; // tolera 30 s de desfase de reloj entre emisor y API

        let data = decode::<Claims>(token, &keys.decoding, &validation).map_err(|err| {
            tracing::debug!(error = %err, "jwt rechazado");
            AppError::Unauthorized
        })?;

        Ok(AuthUser { id: data.claims.sub, role: data.claims.role })
    }
}
```

Uso en handlers, sin tocar el router:

```rust
async fn me(user: AuthUser) -> Json<AuthUser> {
    Json(user)
}

async fn delete_item(user: AuthUser, Path(id): Path<Uuid>) -> Result<StatusCode, AppError> {
    if user.role != "admin" {
        return Err(AppError::Forbidden);
    }
    // borrar
    Ok(StatusCode::NO_CONTENT)
}
```

Y el emisor del token, para que el `exp` y el algoritmo coincidan con la validación:

```rust
use jsonwebtoken::{encode, Header};

pub fn issue_token(keys: &JwtKeys, user_id: Uuid, role: &str, ttl_secs: u64) -> Result<String, jsonwebtoken::errors::Error> {
    let exp = jsonwebtoken::get_current_timestamp() + ttl_secs;
    let claims = Claims { sub: user_id, role: role.to_owned(), exp: exp as usize };
    encode(&Header::new(Algorithm::HS256), &claims, &keys.encoding)
}
```

Decisiones:

- **`FromRef<S>` en vez de `S = AppState`.** El extractor solo exige «un estado del que se pueda sacar `JwtKeys`». Los tests pueden usar un estado mínimo y los sub-routers con `Router<OtroEstado>` también lo pueden usar. El `#[derive(FromRef)]` genera `impl FromRef<AppState> for JwtKeys` por cada campo.
- **El algoritmo se fija en el servidor**, nunca se lee del token: `Validation::new(Algorithm::HS256)` rechaza un token firmado con `none` o con RS256 aunque la cabecera lo pida. Ese es el ataque clásico de confusión de algoritmo.
- **El mensaje al cliente es siempre 401 sin detalle**; el motivo real (caducado, firma inválida, `sub` malformado) va al log a nivel `debug`. Distinguirlos en la respuesta ayuda a un atacante más que a un cliente legítimo.
- `Validation` por defecto exige `exp` y lo valida; si tus tokens no lo llevan, `decode` falla con `MissingRequiredClaim("exp")`, que es lo correcto.

Prueba:

```rust
#[tokio::test]
async fn expired_token_is_401_and_valid_token_passes() {
    let keys = JwtKeys::from_secret(b"test-secret");
    let app = build_app(AppState::for_tests_with(keys.clone()).await);

    let expired = issue_token(&keys, Uuid::new_v4(), "user", 0).unwrap(); // exp = ahora; con leeway 30 aún pasa
    let caducado_de_verdad = {
        let claims = Claims { sub: Uuid::new_v4(), role: "user".into(), exp: 1_000 };
        encode(&Header::new(Algorithm::HS256), &claims, &keys.encoding).unwrap()
    };

    for (token, expected) in [(expired, StatusCode::OK), (caducado_de_verdad, StatusCode::UNAUTHORIZED)] {
        let r = app
            .clone()
            .oneshot(Request::get("/me").header(header::AUTHORIZATION, format!("Bearer {token}")).body(Body::empty()).unwrap())
            .await
            .unwrap();
        assert_eq!(r.status(), expected);
    }
}
```""",
            },
        ]
    },
    # 11) Revisión estricta: MutexGuard a través de un await (usuario trae código, system variante).
    {
        "messages": [
            {"role": "system", "content": "Eres un revisor de código estricto. Señala problemas concretos antes de proponer código."},
            {
                "role": "user",
                "content": """Revisa este handler de Axum, no compila y no entiendo el error:

```rust
use std::{collections::HashMap, sync::{Arc, Mutex}};

#[derive(Clone)]
struct AppState {
    cache: Arc<Mutex<HashMap<String, Quote>>>,
    http: reqwest::Client,
}

async fn quote(State(state): State<AppState>, Path(symbol): Path<String>) -> Result<Json<Quote>, AppError> {
    let mut cache = state.cache.lock().unwrap();
    if let Some(q) = cache.get(&symbol) {
        return Ok(Json(q.clone()));
    }
    let q: Quote = state.http.get(format!("https://api.example/quotes/{symbol}")).send().await?.json().await?;
    cache.insert(symbol, q.clone());
    Ok(Json(q))
}
```

```
error: future cannot be sent between threads safely
   = help: within `impl Future<Output = Result<Json<Quote>, AppError>>`, the trait `Send` is not implemented for `std::sync::MutexGuard<'_, HashMap<String, Quote>>`
note: future is not `Send` as this value is used across an await
   |
10 |     let mut cache = state.cache.lock().unwrap();
   |         --------- has type `std::sync::MutexGuard<'_, HashMap<String, Quote>>` which is not `Send`
...
14 |     let q: Quote = state.http.get(...).send().await?.json().await?;
   |                                               ^^^^^ await occurs here, with `cache` maybe used later
```""",
            },
            {
                "role": "assistant",
                "content": r"""Cuatro problemas; el primero es el que no compila y el segundo es peor que el primero.

**1. El `MutexGuard` vive a través de dos `.await`.** `tokio::spawn` exige futuros `Send`, y `std::sync::MutexGuard` no lo es: no puede cambiar de hilo entre un `.await` y el siguiente. El compilador te lo dice literalmente: «this value is used across an await». Es un error de diseño, no de sintaxis.

**2. Aunque compilara, bloquearías el servidor.** Mantener el candado mientras haces una llamada HTTP de cientos de milisegundos serializa **todas** las peticiones de `quote`, para cualquier símbolo, detrás de la más lenta. Un `Mutex` se sostiene durante microsegundos, nunca durante I/O.

**3. `lock().unwrap()` convierte un pánico ajeno en una cascada.** Si un hilo entra en pánico con el candado tomado, el mutex queda envenenado y cada `unwrap` posterior tira el handler. Para una caché, el estado interno sigue siendo válido: recupera el guard con `unwrap_or_else(|e| e.into_inner())`.

**4. Sin TTL.** Una cotización cacheada para siempre es un bug de negocio, no de Rust. Lo resuelvo abajo de la forma mínima.

Arreglo: tomar el candado **dos veces, brevemente**, y hacer la I/O sin él. El `Mutex` sigue siendo el de `std`, que es el correcto cuando la sección crítica no contiene `await`.

```rust
use std::{
    collections::HashMap,
    sync::{Arc, Mutex, MutexGuard},
    time::{Duration, Instant},
};

const QUOTE_TTL: Duration = Duration::from_secs(30);

#[derive(Clone)]
struct AppState {
    cache: Arc<Mutex<HashMap<String, (Instant, Quote)>>>,
    http: reqwest::Client,
}

fn lock_cache(state: &AppState) -> MutexGuard<'_, HashMap<String, (Instant, Quote)>> {
    state.cache.lock().unwrap_or_else(|poisoned| poisoned.into_inner())
}

async fn quote(State(state): State<AppState>, Path(symbol): Path<String>) -> Result<Json<Quote>, AppError> {
    // sección crítica 1: lectura; el guard muere al final del bloque, antes de cualquier await
    let cached = {
        let cache = lock_cache(&state);
        cache
            .get(&symbol)
            .filter(|(stored_at, _)| stored_at.elapsed() < QUOTE_TTL)
            .map(|(_, q)| q.clone())
    };
    if let Some(q) = cached {
        return Ok(Json(q));
    }

    // I/O sin candado
    let fresh: Quote = state
        .http
        .get(format!("https://api.example/quotes/{symbol}"))
        .send()
        .await?
        .error_for_status()?
        .json()
        .await?;

    // sección crítica 2: escritura
    lock_cache(&state).insert(symbol, (Instant::now(), fresh.clone()));
    Ok(Json(fresh))
}
```

Qué **no** he hecho y por qué:

- No he cambiado a `tokio::sync::Mutex`. Compilaría con el guard a través del `await`, pero el problema 2 seguiría ahí: el `Mutex` async existe para el caso raro en que *necesitas* sostener un recurso durante I/O (una conexión exclusiva), no para una caché.
- Queda una carrera benigna: dos peticiones del mismo símbolo con la caché vacía hacen dos llamadas HTTP y la segunda escritura gana. Para una cotización es aceptable. Si el proveedor cobra por llamada, usa `moka` 0.12 (feature `future`) con `cache.get_with(symbol, async { fetch().await }).await`, que coalesce las peticiones concurrentes de la misma clave y lleva TTL incorporado; sustituye todo el bloque anterior.

Verificación: `cargo check` pasa; y un test con `tokio::join!` de dos `quote` sobre símbolos distintos debe completar en el tiempo de **una** llamada HTTP, no de dos, lo que demuestra que ya no se serializan.""",
            },
        ]
    },
    # 12) serde: enum etiquetado para webhooks, compatibilidad hacia adelante.
    {
        "messages": [
            {
                "role": "user",
                "content": "Recibo webhooks de pagos con un campo `type` que decide qué otros campos vienen (`payment.succeeded`, `payment.failed`, `refund.created`), y el proveedor añade tipos nuevos sin avisar. ¿Cómo lo modelo con serde sin acabar con un `serde_json::Value` gigante lleno de `.get()`?",
            },
            {
                "role": "assistant",
                "content": r"""Un enum **etiquetado internamente** (`#[serde(tag = "type")]`) con una variante comodín `#[serde(other)]` para los tipos que aún no conoces. Así cada evento conocido llega tipado y uno desconocido no rompe el endpoint.

```rust
use chrono::{DateTime, Utc};
use serde::Deserialize;

#[derive(Debug, Deserialize)]
#[serde(tag = "type")]
pub enum WebhookEvent {
    #[serde(rename = "payment.succeeded")]
    PaymentSucceeded(PaymentSucceeded),
    #[serde(rename = "payment.failed")]
    PaymentFailed(PaymentFailed),
    #[serde(rename = "refund.created")]
    RefundCreated(RefundCreated),
    #[serde(other)]
    Unknown, // cualquier `type` no listado; tiene que ser una variante unitaria
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PaymentSucceeded {
    pub payment_id: String,
    pub amount_cents: u64,          // nunca f64 para dinero
    pub currency: String,
    #[serde(with = "chrono::serde::ts_seconds")]
    pub paid_at: DateTime<Utc>,     // el proveedor manda epoch en segundos
    #[serde(default)]
    pub metadata: std::collections::HashMap<String, String>, // ausente -> vacío
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PaymentFailed {
    pub payment_id: String,
    pub reason: String,
    pub retryable: Option<bool>,    // ausente o null -> None
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct RefundCreated {
    pub refund_id: String,
    pub payment_id: String,
    pub amount_cents: u64,
}
```

El handler queda como un `match` exhaustivo, que es la gracia: añadir una variante nueva te obliga a decidir qué hacer con ella en todos los sitios.

```rust
async fn webhook(Json(event): Json<WebhookEvent>) -> StatusCode {
    match event {
        WebhookEvent::PaymentSucceeded(p) => mark_paid(&p).await,
        WebhookEvent::PaymentFailed(p) => mark_failed(&p).await,
        WebhookEvent::RefundCreated(r) => record_refund(&r).await,
        WebhookEvent::Unknown => tracing::info!("evento desconocido ignorado"),
    }
    StatusCode::OK // el proveedor reintenta ante cualquier cosa que no sea 2xx
}
```

Decisiones y sus límites:

- **`tag = "type"` (interno)** encaja con JSON donde el discriminador va al mismo nivel que los datos, que es lo habitual en webhooks. Si el proveedor envía `{"type": "x", "data": {...}}`, es `#[serde(tag = "type", content = "data")]` (adyacente).
- **`#[serde(other)]`** solo admite variantes unitarias: pierdes el contenido del evento desconocido. Si quieres conservarlo para registrarlo, haz un primer parseo a `serde_json::Value`, saca `type`, y deserializa el enum solo cuando sea conocido; el `Value` lo guardas tal cual.
- **No uses `deny_unknown_fields`** en webhooks: el proveedor añadirá campos y romperías tu integración por un dato que ni usas.
- **`Option<T>` no distingue «ausente» de `null`**; para webhooks da igual. Donde sí importa (un `PATCH` donde `null` significa «borrar»), el patrón es `Option<Option<T>>` con `#[serde(default, with = "serde_with::rust::double_option")]`.

Test que fija el contrato, incluido el tipo nuevo:

```rust
#[test]
fn parses_known_and_unknown_events() {
    let paid: WebhookEvent = serde_json::from_str(
        r#"{"type":"payment.succeeded","paymentId":"p_1","amountCents":1999,"currency":"EUR","paidAt":1700000000}"#,
    )
    .unwrap();
    assert!(matches!(paid, WebhookEvent::PaymentSucceeded(ref p) if p.amount_cents == 1999 && p.metadata.is_empty()));

    let future: WebhookEvent = serde_json::from_str(r#"{"type":"dispute.opened","disputeId":"d_9"}"#).unwrap();
    assert!(matches!(future, WebhookEvent::Unknown));

    let bad = serde_json::from_str::<WebhookEvent>(r#"{"type":"payment.succeeded","paymentId":"p_1"}"#);
    assert!(bad.is_err()); // falta amountCents: un evento conocido incompleto sí es error
}
```""",
            },
        ]
    },
    # 13) sqlx: macros query! y modo offline en CI (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": "¿`sqlx::query!` o `sqlx::query_as` con un string normal? Me dicen que las macros comprueban el SQL en tiempo de compilación pero no entiendo contra qué lo comprueban ni cuándo compensan.",
            },
            {
                "role": "assistant",
                "content": r"""Las macros se conectan a la base de datos de `DATABASE_URL` **mientras compilas**, le piden a Postgres que prepare la sentencia y comparan: que el SQL es válido, que los parámetros son del tipo correcto y que las columnas devueltas encajan con el struct. Un `WHERE` con una columna mal escrita es un error de compilación, no un 500 en producción. Compensan siempre que el SQL sea estático; las funciones sin `!` quedan para SQL construido dinámicamente.

```rust
use sqlx::PgPool;
use uuid::Uuid;

pub struct Order {
    pub id: Uuid,
    pub customer_id: Uuid,
    pub total_cents: i64,
    pub note: Option<String>, // la columna es NULLABLE: sqlx exige Option o no compila
}

pub async fn find_order(pool: &PgPool, id: Uuid) -> sqlx::Result<Option<Order>> {
    sqlx::query_as!(
        Order,
        "SELECT id, customer_id, total_cents, note FROM orders WHERE id = $1",
        id
    )
    .fetch_optional(pool)
    .await
}

pub async fn create_order(pool: &PgPool, customer_id: Uuid, lines: &[(Uuid, i64)]) -> sqlx::Result<Uuid> {
    let mut tx = pool.begin().await?;

    let order_id = sqlx::query_scalar!(
        "INSERT INTO orders (customer_id, total_cents) VALUES ($1, $2) RETURNING id",
        customer_id,
        lines.iter().map(|(_, cents)| cents).sum::<i64>()
    )
    .fetch_one(&mut *tx)
    .await?;

    for (product_id, cents) in lines {
        sqlx::query!(
            "INSERT INTO order_lines (order_id, product_id, cents) VALUES ($1, $2, $3)",
            order_id,
            product_id,
            cents
        )
        .execute(&mut *tx)
        .await?;
    }

    tx.commit().await?; // si no se llama, el Drop de tx hace rollback
    Ok(order_id)
}
```

Lo que hay que saber de las macros:

- **`query_as!` mapea por nombre de columna, no necesita `FromRow`.** `query_as` (sin `!`) sí necesita `#[derive(sqlx::FromRow)]` y comprueba en ejecución.
- **Nulabilidad.** sqlx deduce si una columna puede ser `NULL` y te obliga a `Option`. Cuando se equivoca (expresiones, `LEFT JOIN`, funciones), lo fuerzas en el `SELECT`: `"count(*) as \"total!\""` (no nulo), `"p.name as \"product_name?\""` (nulable), `"status as \"status: OrderStatus\""` (tipo propio con `#[derive(sqlx::Type)]`).
- **Transacciones**: el ejecutor de una `Transaction` es `&mut *tx`. Es lo primero que falla al migrar desde sqlx 0.6.
- **Cuándo no usar la macro**: filtros opcionales que cambian el SQL (`QueryBuilder`), tablas elegidas en ejecución, o un `IN (...)` con lista variable (en Postgres se resuelve con `= ANY($1)` y un `&[Uuid]`, que sí admite la macro).

Requisitos: `cargo install sqlx-cli --no-default-features --features postgres`, un `.env` con `DATABASE_URL`, y la base de datos **con las migraciones aplicadas** (`sqlx migrate run`) antes de compilar, porque la comprobación es contra el esquema real.

Verificación: cambia `total_cents` por `total_cent` en el `SELECT` y ejecuta `cargo check`; debe fallar con «error returned from database: column "total_cent" does not exist», con la línea exacta del `query_as!`.""",
            },
            {
                "role": "user",
                "content": """Funciona en local, pero en CI (GitHub Actions) el build falla:

```
error: set `DATABASE_URL` to use query macros online, or run `cargo sqlx prepare` to update the query cache
  --> src/db/orders.rs:14:5
```

No quiero levantar un Postgres solo para compilar.""",
            },
            {
                "role": "assistant",
                "content": r"""No hace falta: las macros tienen **modo offline**. Generas una caché de las consultas en local y la subes al repo; en CI, sqlx compila contra la caché.

**1. Genera la caché** (con `DATABASE_URL` apuntando a tu Postgres local y migrado):

```bash
cargo sqlx prepare                # en un workspace: cargo sqlx prepare --workspace
git add .sqlx
git commit -m "chore(sqlx): actualizar caché de consultas"
```

Crea un directorio `.sqlx/` con un JSON por consulta (hash del SQL, tipos de parámetros y columnas, nulabilidad). Es lo que la macro necesita para hacer la misma comprobación sin conectarse.

**2. En CI**, compila con la variable que fuerza el modo offline:

```yaml
# .github/workflows/ci.yml
env:
  SQLX_OFFLINE: "true"

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
      - run: cargo build --locked
      - run: cargo test --locked
```

Sin `SQLX_OFFLINE`, sqlx usa la caché solo si **no** hay `DATABASE_URL`; con la variable a `true`, la usa aunque la haya, que es lo que quieres en CI para que el resultado no dependa del entorno.

**3. Protege la caché contra el olvido.** El fallo típico es cambiar un `SELECT` y no regenerar `.sqlx/`: en local compila (hay base de datos) y en CI falla con «no cached data for this query». Añade un paso que lo detecte con un mensaje claro, o mejor, que lo compruebe en un job con Postgres de servicio:

```yaml
  sqlx-cache:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env: { POSTGRES_PASSWORD: postgres }
        ports: ["5432:5432"]
        options: --health-cmd pg_isready --health-interval 5s --health-timeout 5s --health-retries 10
    env:
      DATABASE_URL: postgres://postgres:postgres@localhost:5432/postgres
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
      - run: cargo install sqlx-cli --no-default-features --features postgres --locked
      - run: sqlx migrate run
      - run: cargo sqlx prepare --check   # falla si .sqlx/ no coincide con el código
```

Esto levanta un Postgres **solo en ese job**; el `build` principal sigue sin base de datos. Es lo mejor de los dos mundos: compilación rápida y garantía de que la caché está al día.

Y el `Dockerfile`, que tiene el mismo problema: `ENV SQLX_OFFLINE=true` antes del `cargo build --release`, y `.sqlx/` fuera del `.dockerignore`.

Comprobación: en local, `SQLX_OFFLINE=true cargo check` debe compilar sin tocar la base de datos (apágala o cambia `DATABASE_URL` a un puerto cerrado para asegurarte). Si falla, la caché no cubre alguna consulta: vuelve al paso 1.""",
            },
        ]
    },
    # 14) Validación de entrada con `validator` y un extractor ValidatedJson.
    {
        "messages": [
            {
                "role": "user",
                "content": "En Axum, ¿dónde valido reglas tipo «email válido», «contraseña de 8 a 128» o «edad entre 18 y 120»? ¿En el handler, en el modelo, en un extractor? Quiero que la respuesta diga qué campo falló.",
            },
            {
                "role": "assistant",
                "content": r"""En un extractor: `ValidatedJson<T>` deserializa, valida y, si falla, responde 422 con los campos. El handler recibe un `T` que ya cumple las reglas y no tiene ni un `if` de validación. Las reglas viven en el tipo de entrada, con el crate `validator`.

```toml
axum = "0.8"
validator = { version = "0.20", features = ["derive"] }
serde = { version = "1", features = ["derive"] }
serde_json = "1"
```

```rust
use axum::{
    extract::{rejection::JsonRejection, FromRequest, Request},
    http::StatusCode,
    response::{IntoResponse, Response},
    Json,
};
use serde::{de::DeserializeOwned, Deserialize};
use validator::{Validate, ValidationErrors};

#[derive(Debug, Deserialize, Validate)]
pub struct CreateUser {
    #[validate(email)]
    pub email: String,
    #[validate(length(min = 8, max = 128, message = "entre 8 y 128 caracteres"))]
    pub password: String,
    #[validate(range(min = 18, max = 120))]
    pub age: u8,
    #[validate(length(min = 1), custom(function = "no_whitespace_only"))]
    pub display_name: String,
}

fn no_whitespace_only(value: &str) -> Result<(), validator::ValidationError> {
    if value.trim().is_empty() {
        return Err(validator::ValidationError::new("blank"));
    }
    Ok(())
}

pub struct ValidatedJson<T>(pub T);

pub enum ValidationRejection {
    Body(JsonRejection),
    Rules(ValidationErrors),
}

impl IntoResponse for ValidationRejection {
    fn into_response(self) -> Response {
        match self {
            ValidationRejection::Body(rejection) => (
                rejection.status(), // 400 sintaxis, 415 content-type, 422 forma
                Json(serde_json::json!({ "error": rejection.body_text() })),
            )
                .into_response(),
            ValidationRejection::Rules(errors) => {
                // field_errors(): campo -> lista de {code, message, params}
                let fields: serde_json::Map<String, serde_json::Value> = errors
                    .field_errors()
                    .into_iter()
                    .map(|(field, errs)| {
                        let messages: Vec<String> = errs
                            .iter()
                            .map(|e| e.message.as_ref().map(|m| m.to_string()).unwrap_or_else(|| e.code.to_string()))
                            .collect();
                        (field.to_string(), serde_json::Value::from(messages))
                    })
                    .collect();
                (StatusCode::UNPROCESSABLE_ENTITY, Json(serde_json::json!({ "error": "validation", "fields": fields })))
                    .into_response()
            }
        }
    }
}

impl<S, T> FromRequest<S> for ValidatedJson<T>
where
    S: Send + Sync,
    T: DeserializeOwned + Validate,
{
    type Rejection = ValidationRejection;

    async fn from_request(req: Request, state: &S) -> Result<Self, Self::Rejection> {
        let Json(value) = Json::<T>::from_request(req, state).await.map_err(ValidationRejection::Body)?;
        value.validate().map_err(ValidationRejection::Rules)?;
        Ok(ValidatedJson(value))
    }
}
```

Handler:

```rust
async fn create_user(
    State(state): State<AppState>,
    ValidatedJson(body): ValidatedJson<CreateUser>,
) -> Result<(StatusCode, Json<User>), AppError> {
    let user = db::users::insert(&state.pool, &body).await?;
    Ok((StatusCode::CREATED, Json(user)))
}
```

Respuesta ante `{"email":"x","password":"123","age":15,"display_name":"   "}`:

```json
{
  "error": "validation",
  "fields": {
    "email": ["email"],
    "password": ["entre 8 y 128 caracteres"],
    "age": ["range"],
    "display_name": ["blank"]
  }
}
```

Por qué así y no de otra forma:

- **Forma (serde) y reglas (validator) son capas distintas y dan códigos distintos.** Un JSON roto es 400; un campo con el tipo equivocado es 422 con el mensaje de serde; una regla incumplida es 422 con `fields`. El cliente puede distinguirlos.
- **Las reglas que dependen de la base de datos no van aquí.** «Email ya registrado» necesita una consulta: va en el handler o en el servicio, y devuelve 409. El extractor solo comprueba lo que se puede saber mirando el cuerpo.
- **El `u8` de `age` ya rechaza negativos y 300** antes de llegar a `range`; aprovecha los tipos y deja a `validator` solo lo que el tipo no expresa.
- Alternativa equivalente: `garde` 0.20, misma idea con `#[garde(...)]` y reglas con contexto; si ya tienes `validator` en el proyecto no hay motivo para cambiar.

Comprobación: un test con el JSON de arriba espera `422` y `fields.password[0] == "entre 8 y 128 caracteres"`; otro con `{"email": 5}` espera `422` y un `error` que empieza por «Failed to deserialize the JSON body»; otro con `{` a secas espera `400`.""",
            },
        ]
    },
    # ---------------------------------------------------------------- Actix-web (6)
    # 15) web::Data creado dentro del closure: un estado por worker (usuario trae código).
    {
        "messages": [
            {
                "role": "user",
                "content": """Tengo un contador de visitas en Actix-web con `web::Data` y hace cosas raras: al refrescar devuelve 1, 2, 1, 3, 2... como si hubiera varios contadores. ¿`Data` está roto o soy yo?

```rust
use std::sync::atomic::{AtomicU64, Ordering};
use actix_web::{web, App, HttpServer, Responder};

#[derive(Default)]
struct Counter {
    hits: AtomicU64,
}

async fn hits(counter: web::Data<Counter>) -> impl Responder {
    let n = counter.hits.fetch_add(1, Ordering::Relaxed) + 1;
    format!("visitas: {n}")
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    HttpServer::new(|| {
        App::new()
            .app_data(web::Data::new(Counter::default()))
            .route("/hits", web::get().to(hits))
    })
    .bind(("0.0.0.0", 8080))?
    .run()
    .await
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""Eres tú, pero es la trampa número uno de Actix: **el closure de `HttpServer::new` se ejecuta una vez por worker**, y por defecto hay tantos workers como núcleos. Cada worker construye su propia `App` y, con ella, su propio `Counter::default()`. Tienes N contadores independientes y cada petición cae en uno distinto; de ahí el 1, 2, 1, 3.

Arreglo: construye el `Data` **fuera** del closure, una vez, y clónalo dentro. `web::Data<T>` es un `Arc<T>`, así que el clon comparte la misma instancia.

```rust
#[actix_web::main]
async fn main() -> std::io::Result<()> {
    let counter = web::Data::new(Counter::default()); // una sola instancia

    HttpServer::new(move || {
        App::new()
            .app_data(counter.clone()) // Arc::clone: todos los workers ven el mismo Counter
            .route("/hits", web::get().to(hits))
    })
    .bind(("0.0.0.0", 8080))?
    .run()
    .await
}
```

Lo demás de tu código está bien: `AtomicU64` es la elección correcta para un contador compartido entre hilos (sin `Mutex`), y `fetch_add` devuelve el valor anterior, por eso el `+ 1`.

Tres consecuencias de la misma regla que te ahorrarán otros «cosas raras»:

- **Pools de base de datos.** `PgPool` creado dentro del closure da un pool por worker: con 8 núcleos y `max_connections(10)` son 80 conexiones. Crea el pool en `main`, antes de `HttpServer::new`, y pásalo igual que el contador.
- **`app_data(T)` sin `Data::new`** compila, pero el extractor `web::Data<T>` no lo encuentra y responde 500 con «Requested application data is not configured correctly» en el log. El tipo registrado tiene que ser exactamente `Data<T>`.
- **Estado por worker a propósito** sí existe: un cliente que no es `Send` o una caché local se crean dentro del closure, conscientemente. Lo raro es hacerlo sin querer.

Comprobación: `for i in $(seq 1 20); do curl -s localhost:8080/hits; echo; done` debe imprimir del 1 al 20 sin repetir ni retroceder. Y `HttpServer::new(...).workers(1)` también lo «arreglaría», pero solo porque esconde el problema; no lo uses como solución.""",
            },
        ]
    },
    # 16) Errores con ResponseError y JsonConfig (system variante: solo código).
    {
        "messages": [
            {"role": "system", "content": "Responde solo con código y comentarios breves."},
            {
                "role": "user",
                "content": "Actix-web 4: tipo de error propio que responda JSON `{\"error\": ...}` con el código HTTP correcto, incluidos los errores de deserialización de `web::Json` (ahora salen como texto plano 400). Con thiserror.",
            },
            {
                "role": "assistant",
                "content": r"""```rust
// error.rs
use actix_web::{error::ResponseError, http::StatusCode, HttpResponse};
use serde_json::json;

#[derive(Debug, thiserror::Error)]
pub enum ApiError {
    #[error("{0} not found")]
    NotFound(&'static str),
    #[error("{0}")]
    BadRequest(String),
    #[error("unauthorized")]
    Unauthorized,
    #[error(transparent)]
    Db(#[from] sqlx::Error),
    #[error(transparent)]
    Unexpected(#[from] anyhow::Error),
}

impl ResponseError for ApiError {
    fn status_code(&self) -> StatusCode {
        match self {
            ApiError::NotFound(_) => StatusCode::NOT_FOUND,
            ApiError::BadRequest(_) => StatusCode::BAD_REQUEST,
            ApiError::Unauthorized => StatusCode::UNAUTHORIZED,
            ApiError::Db(sqlx::Error::RowNotFound) => StatusCode::NOT_FOUND,
            ApiError::Db(_) | ApiError::Unexpected(_) => StatusCode::INTERNAL_SERVER_ERROR,
        }
    }

    fn error_response(&self) -> HttpResponse {
        let status = self.status_code();
        // 5xx: detalle al log, mensaje fijo al cliente; 4xx: el mensaje del enum
        let message = if status.is_server_error() {
            log::error!("{self:?}");
            "internal error".to_string()
        } else {
            self.to_string()
        };
        HttpResponse::build(status).json(json!({ "error": message }))
    }
}
```

```rust
// main.rs
use actix_web::{error::InternalError, web, App, HttpResponse, HttpServer};
use serde_json::json;

mod error;
mod handlers;

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    env_logger::init();
    let pool = web::Data::new(build_pool().await); // una vez, fuera del closure

    HttpServer::new(move || {
        // los rechazos de web::Json pasan por aquí: mismo formato que ApiError
        let json_cfg = web::JsonConfig::default()
            .limit(256 * 1024)
            .error_handler(|err, _req| {
                let message = err.to_string(); // "Json deserialize error: missing field `name` at line 1 column 12"
                let status = match &err {
                    actix_web::error::JsonPayloadError::Deserialize(_) => actix_web::http::StatusCode::UNPROCESSABLE_ENTITY,
                    _ => actix_web::http::StatusCode::BAD_REQUEST, // tamaño, content-type, cuerpo ilegible
                };
                InternalError::from_response(err, HttpResponse::build(status).json(json!({ "error": message }))).into()
            });

        App::new()
            .app_data(pool.clone())
            .app_data(json_cfg)
            .wrap(actix_web::middleware::Logger::default())
            .service(web::scope("/api").service(handlers::get_order).service(handlers::create_order))
    })
    .bind(("0.0.0.0", 8080))?
    .run()
    .await
}
```

```rust
// handlers.rs
use actix_web::{get, post, web, HttpResponse};
use serde::{Deserialize, Serialize};
use sqlx::PgPool;
use uuid::Uuid;

use crate::error::ApiError;

#[derive(Serialize)]
pub struct Order {
    pub id: Uuid,
    pub total_cents: i64,
}

#[derive(Deserialize)]
pub struct NewOrder {
    pub total_cents: i64,
}

#[get("/orders/{id}")]
pub async fn get_order(pool: web::Data<PgPool>, id: web::Path<Uuid>) -> Result<web::Json<Order>, ApiError> {
    let order = sqlx::query_as!(Order, "SELECT id, total_cents FROM orders WHERE id = $1", *id)
        .fetch_optional(pool.get_ref())
        .await? // sqlx::Error -> ApiError::Db
        .ok_or(ApiError::NotFound("order"))?;
    Ok(web::Json(order))
}

#[post("/orders")]
pub async fn create_order(pool: web::Data<PgPool>, body: web::Json<NewOrder>) -> Result<HttpResponse, ApiError> {
    if body.total_cents <= 0 {
        return Err(ApiError::BadRequest("total_cents must be positive".into()));
    }
    let order = sqlx::query_as!(
        Order,
        "INSERT INTO orders (total_cents) VALUES ($1) RETURNING id, total_cents",
        body.total_cents
    )
    .fetch_one(pool.get_ref())
    .await?;
    Ok(HttpResponse::Created().json(order))
}
```

```rust
// Comprobación (tests/errors.rs)
use actix_web::{http::StatusCode, test, web, App};

#[actix_web::test]
async fn bad_json_is_422_with_json_body() {
    let app = test::init_service(App::new().app_data(json_cfg()).service(crate_handlers())).await;
    let req = test::TestRequest::post()
        .uri("/api/orders")
        .insert_header(("content-type", "application/json"))
        .set_payload(r#"{"total_cents": "mucho"}"#)
        .to_request();
    let resp = test::call_service(&app, req).await;
    assert_eq!(resp.status(), StatusCode::UNPROCESSABLE_ENTITY);
    let body: serde_json::Value = test::read_body_json(resp).await;
    assert!(body["error"].as_str().unwrap().starts_with("Json deserialize error"));
}
```""",
            },
        ]
    },
    # 17) Inglés: testing en Actix-web con test::init_service.
    {
        "messages": [
            {
                "role": "user",
                "content": "How do I write tests for Actix-web handlers without starting the server? I'd like to test a POST that creates a record and a GET that reads it back, sharing state between the two calls.",
            },
            {
                "role": "assistant",
                "content": r"""Use `actix_web::test`: `init_service` builds the `App` in-process, `TestRequest` builds requests, and `call_service` runs them through the full middleware chain without a socket. Sharing state across calls is just reusing the same `web::Data` you pass to the app.

```rust
use actix_web::{http::StatusCode, test, web, App};
use serde_json::json;

use api::{routes, state::AppState, Item};

#[actix_web::test]
async fn create_then_read_back() {
    let state = web::Data::new(AppState::in_memory()); // one instance for both calls
    let app = test::init_service(App::new().app_data(state.clone()).configure(routes)).await;

    // POST
    let req = test::TestRequest::post()
        .uri("/items")
        .set_json(json!({ "name": "lamp" })) // sets content-type and body
        .to_request();
    let resp = test::call_service(&app, req).await;
    assert_eq!(resp.status(), StatusCode::CREATED);
    let created: Item = test::read_body_json(resp).await;

    // GET
    let req = test::TestRequest::get().uri(&format!("/items/{}", created.id)).to_request();
    let fetched: Item = test::call_and_read_body_json(&app, req).await;
    assert_eq!(fetched.name, "lamp");

    // and the state saw exactly one insert
    assert_eq!(state.items.lock().unwrap().len(), 1);
}

#[actix_web::test]
async fn missing_item_is_404_json() {
    let app = test::init_service(App::new().app_data(web::Data::new(AppState::in_memory())).configure(routes)).await;
    let req = test::TestRequest::get().uri("/items/00000000-0000-0000-0000-000000000000").to_request();
    let resp = test::call_service(&app, req).await;
    assert_eq!(resp.status(), StatusCode::NOT_FOUND);
    let body: serde_json::Value = test::read_body_json(resp).await;
    assert_eq!(body["error"], "item not found");
}
```

The piece that makes this clean is `configure(routes)`: a function that registers services on a `ServiceConfig`, used by both `main` and the tests, so the test exercises the real routing table.

```rust
pub fn routes(cfg: &mut web::ServiceConfig) {
    cfg.service(
        web::scope("/items")
            .route("", web::post().to(create_item))
            .route("/{id}", web::get().to(get_item)),
    );
}
```

Notes that save debugging time:

- `#[actix_web::test]` sets up the single-threaded Actix runtime a handler expects. `#[tokio::test]` fails at runtime with «`spawn_local` called from outside of a `task::LocalSet`» the moment a handler uses anything Actix-specific.
- `call_and_read_body_json` panics on a non-2xx status with a readable message; use `call_service` plus `read_body_json` when the status is what you are asserting.
- `app_data` is matched by exact type, so a test that registers `web::Data<AppState>` while the handler asks for `web::Data<Arc<AppState>>` gets a 500 and a log line, not a compile error. Keep one `AppState` type and construct it with `AppState::in_memory()` for tests and `AppState::from_env()` for production.
- For Postgres-backed tests, `#[sqlx::test]` gives you a fresh database per test; wrap the pool in `web::Data::new(pool)` and the rest is identical.

Run with `cargo test`; each test builds its own `App`, so they are independent and can run in parallel.""",
            },
        ]
    },
    # 18) Actix-web vs Axum: criterio (system exacto).
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Para un servicio nuevo en Rust, ¿Actix-web o Axum? En el equipo hay gente que viene de Node y nadie ha hecho Rust en producción.",
            },
            {
                "role": "assistant",
                "content": r"""**Axum**, por tres razones que pesan más en un equipo que empieza: menos conceptos propios, errores de compilación más legibles con `debug_handler`, y todo el ecosistema de `tower`/`tower-http` (middlewares, timeouts, rate limiting, tracing) sin adaptadores.

| | Axum 0.8 | Actix-web 4 |
|---|---|---|
| Modelo | `Router` + handlers como funciones; extractores por tipo | `App` + macros `#[get("/")]` o `route()`; extractores por tipo |
| Runtime | tokio multihilo; handlers deben ser `Send` | actix-rt sobre tokio, un hilo por worker; handlers pueden ser `!Send` |
| Middleware | `tower::Layer`; reutilizas `tower-http` tal cual | `wrap` + `from_fn` (4.9+) o el trait `Transform`; ecosistema propio |
| Estado | `State<T>` tipado, `FromRef` para sub-estados | `web::Data<T>` (un `Arc`), trampa del closure por worker |
| Errores | `IntoResponse` | `ResponseError` |
| Rendimiento | muy alto | muy alto, algo mayor en benchmarks sintéticos |
| Madurez | mantenido por el equipo de tokio; 0.x pero estable | años en producción; 4.x estable |

Lo que de verdad distingue al proyecto:

- **`Send` o no.** Axum exige futuros `Send` porque reparte tareas entre hilos. Si vas a usar `Rc`, `RefCell` o librerías `!Send` dentro de handlers, Actix te lo pone más fácil. Para una API con sqlx y reqwest, no lo notarás.
- **La diferencia de rendimiento no importa** salvo que estés sirviendo cientos de miles de peticiones por segundo por núcleo; antes de eso, el cuello es la base de datos.
- **Documentación y ejemplos.** Los de Axum están en el repo (`examples/`) y se mantienen con cada versión; con Actix encontrarás más tutoriales viejos que mezclan 2.x, 3.x y 4.x.

Para gente que viene de Node: Axum se parece a Express en lo que importa (router, middlewares encadenados, handlers que reciben lo que piden), y el compilador hace el papel de los tipos de TypeScript, pero estricto.

Lo que no cambia con la elección y conviene decidir el primer día: `sqlx` con macros y migraciones, `tracing` desde el arranque, un `AppError` propio, y `cargo clippy -- -D warnings` en CI. Si dentro de un año quieres cambiar de framework, los handlers son lo único que reescribes; el resto (`db/`, dominio, config) no sabe qué framework hay encima.""",
            },
        ]
    },
    # 19) web::block para código síncrono y número de workers (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": "Uso Diesel (síncrono) dentro de handlers de Actix-web y bajo carga todo se frena: hasta las rutas que no tocan la base de datos tardan segundos. ¿Me paso a async o hay arreglo?",
            },
            {
                "role": "assistant",
                "content": r"""Hay arreglo sin cambiar de ORM: envuelve cada llamada a Diesel en `web::block`. El problema es que una consulta síncrona dentro de un handler `async` **bloquea el hilo del worker** mientras Postgres responde, y ese hilo atiende cientos de conexiones a la vez; todas esperan, incluidas las rutas sin base de datos.

```rust
use actix_web::{error::BlockingError, get, web, HttpResponse};
use diesel::prelude::*;
use diesel::r2d2::{self, ConnectionManager};

type DbPool = r2d2::Pool<ConnectionManager<PgConnection>>;

#[get("/orders/{id}")]
async fn get_order(pool: web::Data<DbPool>, id: web::Path<i64>) -> Result<HttpResponse, ApiError> {
    let id = id.into_inner();
    let order = web::block(move || -> Result<Option<Order>, diesel::result::Error> {
        let mut conn = pool.get().map_err(|_| diesel::result::Error::NotFound)?; // r2d2 timeout -> trátalo como error propio si prefieres
        orders::table.find(id).first::<Order>(&mut conn).optional()
    })
    .await
    .map_err(|e: BlockingError| ApiError::Unexpected(e.into()))? // el closure entró en pánico o se canceló
    .map_err(ApiError::from)?;                                   // el error de Diesel

    match order {
        Some(o) => Ok(HttpResponse::Ok().json(o)),
        None => Err(ApiError::NotFound("order")),
    }
}
```

Qué hace `web::block`: manda el closure al *pool de hilos bloqueantes* del runtime y devuelve un futuro; el worker queda libre para otras peticiones mientras la consulta corre en otro hilo. Por eso el resultado lleva dos `Result`: el externo (`BlockingError`) por si el hilo murió, el interno es el tuyo.

Reglas para no deshacer el beneficio:

- **Todo lo de Diesel dentro del closure**, incluido `pool.get()`: esperar una conexión también bloquea.
- **`move` y tipos `'static`**: el closure se ejecuta en otro hilo, así que clona lo que necesite (`web::Data` es un `Arc`, clonarlo es gratis; `into_inner()` para los `Path`).
- **El pool de r2d2 también tiene límite**: con `max_size(10)` y 50 peticiones concurrentes, 40 esperan dentro del closure. Mide `pool.state().idle_connections` bajo carga.

Sobre pasarte a async: `diesel-async` (0.5) existe y evita el pool de hilos, pero migrar un proyecto entero por rendimiento sin haber medido es prematuro. `web::block` te quita el síntoma hoy; después mides.

Comprobación: con un handler `/ping` que solo devuelve `"pong"`, lanza `oha -z 20s -c 200 http://localhost:8080/orders/1` en una terminal y mide `/ping` en otra. Antes del cambio, `/ping` tardará cientos de milisegundos; después, menos de 1 ms.""",
            },
            {
                "role": "user",
                "content": "Mejoró mucho. ¿Y cuántos workers pongo? Tengo 4 núcleos y la máquina está al 30 % de CPU.",
            },
            {
                "role": "assistant",
                "content": r"""Deja los 4 que trae por defecto (`HttpServer::workers` usa `std::thread::available_parallelism`). Más workers que núcleos no ayuda: cada uno es un hilo con su propio event loop, y si la CPU está al 30 %, el cuello no es la CPU.

Lo que sí ajusta tu caso, que es I/O de base de datos sobre hilos bloqueantes:

```rust
HttpServer::new(move || App::new().app_data(pool.clone()).service(get_order))
    .workers(4)
    .worker_max_blocking_threads(64) // por worker; por defecto 512 / workers = 128
    .bind(("0.0.0.0", 8080))?
    .run()
    .await
```

Y la cuenta que tiene que cuadrar:

```
hilos bloqueantes totales  = workers × worker_max_blocking_threads = 4 × 64 = 256
conexiones del pool r2d2   = max_size                                     = p. ej. 32
```

Solo 32 consultas pueden correr a la vez; las otras 224 esperarían una conexión dentro de `web::block`. Dos formas de decidir `max_size`:

- `max_size` cercano al número de consultas que Postgres puede atender bien en paralelo (para una instancia pequeña, 20-50), y `worker_max_blocking_threads` un poco por encima de `max_size / workers`, para no tener hilos ociosos esperando conexión.
- Si el 30 % de CPU viene con latencias altas, la espera está en el pool o en Postgres: mira `pg_stat_activity` y el `wait_event`, no los workers.

Lo que no hagas: subir `workers` a 16 «por si acaso». Multiplicas el estado por worker (si algo quedó dentro del closure) y el tamaño total de los pools de hilos, y la base de datos verá más conexiones de las que puede servir.

Comprobación: repite el `oha` de antes con `-c 200` y mira dos números: p99 de `/orders/1` y `pool.state().idle_connections` (expónlo en `/debug/pool`). Si `idle` está a 0 durante toda la prueba, el límite es el pool; si no, es Postgres.""",
            },
        ]
    },
    # 20) Middleware con from_fn (4.9+), Logger y ReqData.
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Cómo hago un middleware en Actix-web que genere un `X-Request-ID`, lo ponga en la respuesta, lo escriba en los logs y lo pueda leer en los handlers? Lo del trait `Transform` me parece muchísimo código para esto.",
            },
            {
                "role": "assistant",
                "content": r"""Desde actix-web **4.9** hay `middleware::from_fn`, que convierte una función `async` en middleware; `Transform` solo hace falta si necesitas estado de construcción complejo. Para un request id son veinte líneas.

```toml
actix-web = "4.9"
uuid = { version = "1", features = ["v4"] }
env_logger = "0.11"
log = "0.4"
```

```rust
use actix_web::{
    body::MessageBody,
    dev::{ServiceRequest, ServiceResponse},
    http::header::{HeaderName, HeaderValue},
    middleware::{from_fn, Logger, Next},
    web, App, Error, HttpMessage, HttpResponse, HttpServer,
};

#[derive(Clone, Copy, Debug)]
pub struct RequestId(pub uuid::Uuid);

async fn request_id(
    req: ServiceRequest,
    next: Next<impl MessageBody>,
) -> Result<ServiceResponse<impl MessageBody>, Error> {
    // respeta el id del balanceador si viene; si no, genera uno
    let id = req
        .headers()
        .get("x-request-id")
        .and_then(|v| v.to_str().ok())
        .and_then(|v| uuid::Uuid::parse_str(v).ok())
        .unwrap_or_else(uuid::Uuid::new_v4);

    req.extensions_mut().insert(RequestId(id)); // disponible para handlers vía ReqData

    let mut res = next.call(req).await?;
    res.headers_mut().insert(
        HeaderName::from_static("x-request-id"),
        HeaderValue::from_str(&id.to_string()).expect("uuid es ASCII"),
    );
    Ok(res)
}

async fn create_order(request_id: web::ReqData<RequestId>) -> HttpResponse {
    log::info!(request_id = request_id.0.to_string(); "creando pedido"); // log 0.4.21+ admite pares clave-valor
    HttpResponse::Created().finish()
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    env_logger::init_from_env(env_logger::Env::default().default_filter_or("info"));

    HttpServer::new(|| {
        App::new()
            // el último wrap es el más externo: Logger ve la respuesta ya con la cabecera
            .wrap(from_fn(request_id))
            .wrap(Logger::new("%a %r %s %Dms rid=%{x-request-id}o"))
            .route("/orders", web::post().to(create_order))
    })
    .bind(("0.0.0.0", 8080))?
    .run()
    .await
}
```

Detalles que importan:

- **Orden de `wrap`.** Igual que en tower: el último `wrap` envuelve a los anteriores y ve la petición primero. Con `Logger` como último, su `%{x-request-id}o` (la cabecera de la **respuesta**, por la `o`) ya está puesta cuando escribe la línea.
- **`ReqData<T>`** lee lo que el middleware guardó en `extensions`. Si un handler lo pide y ningún middleware lo insertó, responde 500 y lo registra; es el mismo mecanismo que `Extension` en Axum.
- **`Next<impl MessageBody>`** es lo que permite que el middleware sea genérico sobre el cuerpo sin escribir los tipos de `Transform`. Si el middleware necesita cambiar el cuerpo (comprimir, reescribir), ahí sí toca `Transform` o `map_body`.
- Aceptar el `x-request-id` entrante solo si es un UUID evita que un cliente te inyecte texto arbitrario en los logs.

Si prefieres no mantenerlo, `tracing-actix-web` (0.7) hace esto mismo con `TracingLogger` y un `RequestId` extractor, integrado con `tracing` en vez de `log`. Vale la pena cuando ya usas `tracing` en el resto del servicio.

Comprobación: `curl -i -X POST localhost:8080/orders` devuelve `x-request-id: <uuid>` y el log muestra `rid=<el mismo uuid>`; repetir con `-H 'x-request-id: 11111111-1111-1111-1111-111111111111'` devuelve ese mismo id, y con `-H 'x-request-id: basura'` genera uno nuevo.""",
            },
        ]
    },
    # ---------------------------------------------------------------- tokio y ecosistema (10)
    # 21) Principiante: Rc en tokio::spawn, qué hace #[tokio::main] (usuario trae error).
    {
        "messages": [
            {
                "role": "user",
                "content": """Soy nuevo en Rust async. Esto no compila y no entiendo por qué, si solo uso `shared` dentro de una tarea:

```rust
use std::{cell::RefCell, rc::Rc};

#[tokio::main]
async fn main() {
    let shared = Rc::new(RefCell::new(Vec::new()));
    let handle = tokio::spawn(async move {
        shared.borrow_mut().push(1);
    });
    handle.await.unwrap();
}
```

```
error: future cannot be sent between threads safely
  = help: within `{async block}`, the trait `Send` is not implemented for `Rc<RefCell<Vec<i32>>>`
note: required by a bound in `tokio::spawn`
```""",
            },
            {
                "role": "assistant",
                "content": r"""`tokio::spawn` puede ejecutar tu tarea **en cualquier hilo** del runtime, y `Rc` está diseñado para no cruzar hilos (su contador de referencias no es atómico). Por eso exige que el futuro sea `Send`, y un `Rc` dentro lo impide aunque solo lo uses en una tarea: el compilador no sabe que no vas a clonarlo.

`#[tokio::main]` expande a esto, y ahí está la clave:

```rust
fn main() {
    tokio::runtime::Builder::new_multi_thread() // varios hilos de trabajo
        .enable_all()
        .build()
        .unwrap()
        .block_on(async { /* tu main */ });
}
```

Dos arreglos válidos; elige según lo que quieras de verdad.

**1. Compartir entre hilos (lo normal):** `Arc` en vez de `Rc`, `Mutex` en vez de `RefCell`.

```rust
use std::sync::{Arc, Mutex};

#[tokio::main]
async fn main() {
    let shared = Arc::new(Mutex::new(Vec::new()));
    let worker = Arc::clone(&shared);
    let handle = tokio::spawn(async move {
        worker.lock().unwrap().push(1); // el guard muere en esta línea; no cruza ningún await
    });
    handle.await.unwrap();
    println!("{:?}", shared.lock().unwrap()); // [1]
}
```

`Arc` = `Rc` con contador atómico; `std::sync::Mutex` = `RefCell` con exclusión real entre hilos. El `Mutex` de `std` es el correcto aquí porque el candado no se mantiene a través de un `.await`.

**2. Quedarte en un solo hilo a propósito:** runtime `current_thread` y `spawn_local`, que no exige `Send`.

```rust
use std::{cell::RefCell, rc::Rc};
use tokio::task::LocalSet;

#[tokio::main(flavor = "current_thread")]
async fn main() {
    let local = LocalSet::new();
    local
        .run_until(async {
            let shared = Rc::new(RefCell::new(Vec::new()));
            let worker = Rc::clone(&shared);
            tokio::task::spawn_local(async move {
                worker.borrow_mut().push(1);
            })
            .await
            .unwrap();
            println!("{:?}", shared.borrow()); // [1]
        })
        .await;
}
```

Tiene sentido para herramientas de línea de comandos o cuando usas librerías que no son `Send`; para un servidor, no, porque renuncias a los demás núcleos.

Regla para recordarlo: dentro de `tokio::spawn`, todo lo que capture el `async move` tiene que ser `Send + 'static`. `Rc`, `RefCell` y las referencias `&` a variables locales rompen una de las dos condiciones; `Arc`, `Mutex`, `String` y los valores que mueves las cumplen.

Comprobación: la versión 1 imprime `[1]`; y si cambias `.push(1)` por un bucle de 1000 `spawn` que hacen `push`, `shared.lock().unwrap().len()` da 1000 exactos, que es lo que `Rc`/`RefCell` nunca podría garantizar entre hilos.""",
            },
        ]
    },
    # 22) Concurrencia acotada: JoinSet + Semaphore vs buffer_unordered (system exacto).
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Tengo que descargar unas 5000 URLs con reqwest. Si hago `tokio::spawn` por cada una, el proveedor me devuelve 429 y me quedo sin descriptores. ¿Cómo limito a, digamos, 20 descargas a la vez y recojo los resultados con sus errores?",
            },
            {
                "role": "assistant",
                "content": r"""Un `Semaphore` con 20 permisos y un `JoinSet` para recoger los resultados a medida que terminan. El semáforo acota cuántas descargas están **en vuelo**; el `JoinSet` te da cada resultado sin esperar al más lento y te deja abortar todo si hace falta.

```rust
use std::{sync::Arc, time::Duration};

use reqwest::Client;
use tokio::{sync::Semaphore, task::JoinSet};

const MAX_IN_FLIGHT: usize = 20;

#[derive(Debug)]
pub struct Download {
    pub url: String,
    pub result: Result<bytes::Bytes, reqwest::Error>,
}

pub async fn download_all(urls: Vec<String>) -> Vec<Download> {
    let client = Client::builder()
        .timeout(Duration::from_secs(30))
        .connect_timeout(Duration::from_secs(5))
        .build()
        .expect("cliente válido");
    let limiter = Arc::new(Semaphore::new(MAX_IN_FLIGHT));
    let mut tasks = JoinSet::new();

    for url in urls {
        let client = client.clone(); // Client es un Arc por dentro: comparte el pool de conexiones
        let limiter = Arc::clone(&limiter);
        tasks.spawn(async move {
            // el permiso se adquiere DENTRO de la tarea: la cola de espera vive en el semáforo, no en el bucle
            let _permit = limiter.acquire_owned().await.expect("el semáforo no se cierra");
            let result = async {
                client.get(&url).send().await?.error_for_status()?.bytes().await
            }
            .await;
            Download { url, result }
        });
    }

    let mut downloads = Vec::with_capacity(tasks.len());
    while let Some(joined) = tasks.join_next().await {
        match joined {
            Ok(download) => downloads.push(download),
            Err(join_err) if join_err.is_panic() => tracing::error!(?join_err, "una descarga entró en pánico"),
            Err(_) => {} // cancelada: solo ocurre si abortas el JoinSet
        }
    }
    downloads
}
```

Por qué cada pieza:

- **`acquire_owned` dentro de la tarea.** Adquirirlo antes del `spawn` también funciona, pero entonces el bucle `for` se bloquea y no puedes, por ejemplo, abortar o reportar progreso mientras encola. Con 5000 tareas ligeras esperando un permiso, el coste de memoria es de unos pocos KB por tarea.
- **`JoinSet` en vez de `Vec<JoinHandle>`.** `join_next` devuelve en orden de finalización; si el `JoinSet` se descarta, aborta lo que quede. Con un `Vec` de handles, un `?` a mitad deja tareas huérfanas corriendo.
- **Un solo `Client`.** Crear uno por URL abre un pool de conexiones nuevo cada vez y es la causa habitual de «too many open files».
- **El error va en el resultado, no en el `?`.** Una URL caída no debe tirar las otras 4999.

**Alternativa sin tareas**, si no necesitas abortar ni paralelismo entre núcleos (una descarga es I/O, no CPU): un *stream* con `buffer_unordered`, que hace lo mismo en menos líneas.

```rust
use futures::{stream, StreamExt};

let downloads: Vec<Download> = stream::iter(urls)
    .map(|url| {
        let client = client.clone();
        async move {
            let result = async { client.get(&url).send().await?.error_for_status()?.bytes().await }.await;
            Download { url, result }
        }
    })
    .buffer_unordered(MAX_IN_FLIGHT)
    .collect()
    .await;
```

Lo que **no** resuelve ninguna de las dos: el 429. Veinte en vuelo acotan la concurrencia, no la tasa; si el proveedor limita a N peticiones por segundo, añade un `tokio::time::interval` que reparta permisos (o el crate `governor`), y respeta `Retry-After` en los 429 con un reintento.

Comprobación: mete un `AtomicUsize` que haga `fetch_add(1)` al entrar y `fetch_sub(1)` al salir del `async` de descarga, y guarda el máximo visto; con 5000 URLs debe ser exactamente 20. Y `ulimit -n 1024` en la shell de pruebas: antes del cambio reventaba, después no.""",
            },
        ]
    },
    # 23) select! y seguridad ante cancelación (avanzado, usuario trae código).
    {
        "messages": [
            {
                "role": "user",
                "content": """Un servicio que lee líneas de un socket TCP y las procesa. De vez en cuando llegan líneas partidas o se pierden, y no es la red (lo verifiqué con tcpdump). El bucle:

```rust
let mut reader = BufReader::new(stream);
let mut buf = String::new();
let mut flush_tick = tokio::time::interval(Duration::from_secs(1));

loop {
    tokio::select! {
        n = reader.read_line(&mut buf) => {
            if n? == 0 { break; }
            batch.push(parse(&buf)?);
            buf.clear();
        }
        _ = flush_tick.tick() => {
            flush(&mut batch).await?;
        }
        _ = shutdown.recv() => break,
    }
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""`read_line` **no es seguro ante cancelación**, y `select!` cancela cada segundo. Cuando `flush_tick.tick()` gana, el futuro de `read_line` se descarta a medias: los bytes que ya había copiado en `buf` se quedan ahí (o se pierden del búfer interno, según el punto exacto). En la siguiente vuelta, `read_line` sigue escribiendo en ese `buf` con un trozo viejo, y obtienes líneas partidas o pegadas. La documentación de tokio lo dice textualmente para `read_line`: «This method is not cancellation safe».

Cómo confirmarlo antes de tocar nada: baja el `interval` a 10 ms y manda líneas largas (varios KB) con `nc`. La tasa de líneas corruptas se dispara. Vuelve a 1 s y baja. Eso descarta la red y señala la cancelación.

**Arreglo mínimo:** usa `lines()`, cuyo `next_line()` sí es seguro ante cancelación (mantiene el estado parcial dentro del propio `Lines`, no en un búfer tuyo).

```rust
use tokio::io::{AsyncBufReadExt, BufReader};

let mut lines = BufReader::new(stream).lines();
let mut flush_tick = tokio::time::interval(Duration::from_secs(1));

loop {
    tokio::select! {
        biased; // comprueba las ramas en este orden: primero apagado, luego datos

        _ = shutdown.recv() => break,

        line = lines.next_line() => {
            match line? {
                Some(line) => batch.push(parse(&line)?),
                None => break, // EOF
            }
        }

        _ = flush_tick.tick() => {
            flush(&mut batch).await?;
        }
    }
}
flush(&mut batch).await?; // lo que quede al salir, sea por EOF o por apagado
```

Qué cambia, aparte del método de lectura:

- **`biased;`** elimina la aleatoriedad del `select!` (por defecto elige una rama lista al azar) y garantiza que el apagado se atiende aunque el socket siempre tenga datos. Sin él, bajo carga, `shutdown` puede tardar en ganar.
- **El `flush` final** cubre el caso que tu versión perdía: `break` con un `batch` a medio llenar.
- `shutdown.recv()` sobre `mpsc`/`broadcast`/`watch` y `interval.tick()` **sí** son seguros ante cancelación, así que esas ramas estaban bien.

Regla general para `select!` en un bucle: cada futuro que puede ser cancelado debe ser o bien seguro ante cancelación (la documentación de tokio marca cada método), o bien **creado fuera del bucle** y pasado por `&mut`, de modo que la cancelación solo lo deje de sondear sin destruirlo:

```rust
let mut read_fut = Box::pin(reader.read_line(&mut buf)); // fuera del loop
loop {
    tokio::select! {
        n = &mut read_fut => { /* usa n; recrea read_fut */ }
        _ = flush_tick.tick() => { /* read_fut sigue intacto */ }
    }
}
```

Es más incómodo que `lines()`, pero es la técnica cuando el método que necesitas no es seguro (por ejemplo, `read_exact`).

El mismo bug aparece disfrazado en `tokio::time::timeout(d, reader.read_line(&mut buf))`: si vence el plazo, el `read_line` se descarta igual y pierdes bytes. Si necesitas plazo por línea, `timeout` sobre `next_line()`.

Test de regresión, sin red: un `tokio::io::duplex` en el que un lado escribe 10 000 líneas de 4 KB en trozos pequeños con `sleep` de 1 ms entre trozos, mientras el bucle corre con `interval` de 2 ms. El conteo de líneas parseadas tiene que ser 10 000 exactas y cada una válida.""",
            },
        ]
    },
    # 24) CancellationToken + TaskTracker para apagar workers (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo cuatro workers en tokio que consumen de una cola (loop infinito con `rx.recv().await`). Cuando el servicio recibe SIGTERM quiero que terminen lo que tienen entre manos y salgan, pero ahora mismo el proceso simplemente muere. ¿Cuál es el patrón?",
            },
            {
                "role": "assistant",
                "content": r"""`CancellationToken` para avisar y `TaskTracker` para esperar. Los dos están en `tokio-util` y están pensados para usarse juntos: el token dice «parad», el tracker dice «ya han parado todos».

```toml
tokio = { version = "1", features = ["full"] }
tokio-util = { version = "0.7", features = ["rt"] }
```

```rust
use std::time::Duration;

use tokio::sync::mpsc;
use tokio_util::{sync::CancellationToken, task::TaskTracker};

async fn worker(id: usize, mut rx: mpsc::Receiver<Job>, token: CancellationToken) {
    loop {
        tokio::select! {
            biased;
            _ = token.cancelled() => {
                tracing::info!(id, "worker: cancelación recibida, salgo sin coger más trabajo");
                break;
            }
            job = rx.recv() => {
                match job {
                    Some(job) => process(job).await, // NO se cancela a mitad: el select solo decide antes de coger un job
                    None => break,                   // el emisor cerró la cola
                }
            }
        }
    }
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let (tx, rx) = mpsc::channel::<Job>(1024);
    let rx = std::sync::Arc::new(tokio::sync::Mutex::new(rx)); // varios consumidores de un mpsc: ver nota abajo
    let token = CancellationToken::new();
    let tracker = TaskTracker::new();

    for id in 0..4 {
        let token = token.child_token();
        let rx = std::sync::Arc::clone(&rx);
        tracker.spawn(async move {
            loop {
                let job = tokio::select! {
                    biased;
                    _ = token.cancelled() => break,
                    job = async { rx.lock().await.recv().await } => job,
                };
                match job {
                    Some(job) => process(job).await,
                    None => break,
                }
            }
            tracing::info!(id, "worker terminado");
        });
    }
    tracker.close(); // no se van a añadir más tareas; wait() podrá terminar

    tokio::signal::ctrl_c().await?; // o SIGTERM con tokio::signal::unix
    tracing::info!("apagando: cancelo y espero");
    token.cancel();

    match tokio::time::timeout(Duration::from_secs(30), tracker.wait()).await {
        Ok(()) => tracing::info!("todos los workers terminaron"),
        Err(_) => tracing::warn!("30 s agotados; salgo con trabajos a medias"),
    }
    Ok(())
}
```

Las decisiones:

- **La cancelación se comprueba solo entre trabajos.** El `select!` compite entre «me han cancelado» y «hay un trabajo nuevo»; una vez cogido el trabajo, `process(job).await` corre fuera del `select!` y termina. Es la diferencia entre «termina lo que tienes» y «muere a medias».
- **`biased;`** para que, con la cola llena, la cancelación gane siempre al `recv`.
- **`child_token()`** por worker: cancelar el padre cancela a todos; además podrías cancelar uno solo.
- **`tracker.close()` antes de `wait()`**: sin `close`, `wait` espera para siempre porque cree que pueden llegar más tareas.
- **`timeout` sobre `wait()`**: un apagado que puede durar infinito no es un apagado. 30 s es lo que suele dar Kubernetes (`terminationGracePeriodSeconds`); ajusta al tuyo.
- Nota sobre el `Mutex<Receiver>`: `mpsc` es de un solo consumidor; cuatro workers que comparten el `Receiver` necesitan el candado. Si la cola es tuya, `async-channel` o `flume` dan MPMC sin candado y el código queda más limpio.

Comprobación: encola 100 trabajos de 200 ms, manda Ctrl+C a los 2 s. Los logs deben mostrar cuatro «worker terminado» en menos de 300 ms tras la señal, y el contador de trabajos completados debe ser múltiplo de 4 aproximadamente (cada worker terminó el suyo), nunca un trabajo registrado como «empezado» sin «terminado».""",
            },
            {
                "role": "user",
                "content": "Vale, pero `process(job)` tiene varios pasos: descarga un archivo, lo transforma y escribe en Postgres. Si la descarga tarda un minuto, ¿no debería poder cancelarla y solo proteger la escritura?",
            },
            {
                "role": "assistant",
                "content": r"""Sí, y la herramienta es la misma: pasa el token a `process` y decide **por paso** qué es cancelable. La descarga lo es; la escritura, no. Con `run_until_cancelled` (tokio-util 0.7.11+) no hace falta un `select!` en cada sitio.

```rust
async fn process(job: Job, token: &CancellationToken) -> Result<Outcome, ProcessError> {
    // Paso 1: cancelable. Si se cancela, el futuro de descarga se descarta (reqwest cierra la conexión).
    let Some(downloaded) = token.run_until_cancelled(download(&job.url)).await else {
        return Ok(Outcome::Cancelled { job_id: job.id }); // nada que deshacer: no escribimos nada
    };
    let bytes = downloaded?;

    // Paso 2: CPU, segundos como mucho. Si quieres cancelarlo, hay que comprobar el token dentro del bucle.
    let transformed = tokio::task::spawn_blocking(move || transform(&bytes)).await??;

    // Paso 3: NO cancelable. Una vez empezada la transacción, se termina.
    write_result(&job, &transformed).await?;
    Ok(Outcome::Done { job_id: job.id })
}
```

Y en el worker, el `select!` del paso anterior sigue igual: elige entre cancelación y `recv`, pero ahora `process(job, &token).await` también puede terminar antes de tiempo con `Outcome::Cancelled`.

Dos cosas que conviene dejar claras en el diseño:

- **Cancelar antes de escribir es seguro porque el trabajo es reintentable.** Un `Outcome::Cancelled` debe devolver el job a la cola (o dejarlo sin ACK si la cola es Redis/SQS) para que el siguiente arranque lo repita. Si no tienes eso, cancelar la descarga pierde trabajo igual que matar el proceso.
- **El paso 3 no cancelable es lo que acota el apagado.** Su duración máxima es tu presupuesto real: si la transacción puede tardar 20 s, el `timeout` del `tracker.wait()` tiene que ser mayor, y el `terminationGracePeriodSeconds` del pod, mayor todavía.

Lo que no haría: comprobar `token.is_cancelled()` entre cada línea. Un par de puntos de cancelación bien elegidos (antes de coger trabajo, durante la espera larga) bastan; más puntos solo añaden estados intermedios que hay que razonar.

Test: un `download` falso que duerme 60 s, cancelación a los 100 ms; `process` debe devolver `Cancelled` en menos de 200 ms y la tabla de resultados debe seguir vacía. Y el complementario: cancelación lanzada mientras `write_result` está en marcha (un `sleep` de 500 ms dentro de la transacción de prueba); la fila tiene que existir al terminar.""",
            },
        ]
    },
    # 25) spawn_blocking vs rayon para CPU (Colombia, system variante).
    {
        "messages": [
            {"role": "system", "content": "Responde en español, de forma breve y directa."},
            {
                "role": "user",
                "content": "Tengo un endpoint que recibe fotos y las redimensiona con la crate `image`. Con 10 subidas al tiempo la API deja de responder a todo lo demás. ¿Con `spawn_blocking` queda arreglado o hay algo más?",
            },
            {
                "role": "assistant",
                "content": r"""`spawn_blocking` arregla el síntoma (el redimensionado estaba corriendo en los hilos del runtime y los dejaba sin aire), pero para trabajo de **CPU** no es la herramienta final: su pool crece hasta 512 hilos porque está pensado para I/O bloqueante que espera, no para cálculo. Con 50 fotos a la vez tendrías 50 hilos peleando por 4 núcleos.

El patrón correcto son dos piezas:

1. **Un pool de CPU del tamaño de los núcleos** (`rayon`) y un `oneshot` para traer el resultado al mundo async.
2. **Un `Semaphore`** que acote cuántas fotos esperan, para responder 503 en vez de acumular memoria.

```rust
use std::io::Cursor;

use axum::{body::Bytes, extract::State, http::StatusCode};
use tokio::sync::{oneshot, Semaphore};

const MAX_QUEUED: usize = 32;

#[derive(Clone)]
pub struct AppState {
    pub resize_slots: std::sync::Arc<Semaphore>, // Semaphore::new(MAX_QUEUED)
}

fn resize_sync(input: &[u8]) -> Result<Vec<u8>, image::ImageError> {
    let img = image::load_from_memory(input)?;
    let thumb = img.thumbnail(800, 800); // conserva la proporción
    let mut out = Cursor::new(Vec::new());
    thumb.write_to(&mut out, image::ImageFormat::Jpeg)?;
    Ok(out.into_inner())
}

async fn resize_on_cpu_pool(input: Bytes) -> Result<Vec<u8>, AppError> {
    let (tx, rx) = oneshot::channel();
    rayon::spawn(move || {
        let _ = tx.send(resize_sync(&input)); // falla solo si el receptor ya no existe (cliente desconectado)
    });
    rx.await.map_err(|_| AppError::Internal("el worker de imágenes se cayó".into()))?
        .map_err(|e| AppError::BadRequest(format!("imagen inválida: {e}")))
}

async fn upload(State(state): State<AppState>, body: Bytes) -> Result<(StatusCode, Vec<u8>), AppError> {
    let Ok(_slot) = state.resize_slots.try_acquire() else {
        return Err(AppError::Busy); // 503 + Retry-After; mejor que encolar sin límite
    };
    let jpeg = resize_on_cpu_pool(body).await?;
    Ok((StatusCode::OK, jpeg))
}
```

`rayon::spawn` usa el pool global, que por defecto tiene un hilo por núcleo; nunca sobresuscribe. El `oneshot` es el puente: el hilo de rayon envía, la tarea async espera sin bloquear nada.

Cuándo sí basta `spawn_blocking`: cuando lo bloqueante es I/O (leer un archivo con `std::fs`, una librería de cliente síncrona) o cuando el cálculo es ocasional. Para un endpoint que vive de la CPU, rayon.

Dos ajustes más que notarás bajo carga:

- Limita el tamaño del cuerpo (`RequestBodyLimitLayer`, 10 MB) antes de que llegue aquí; decodificar una imagen de 200 MB es un ataque de denegación de servicio con una sola petición.
- `image` 0.25 con solo las features que usas (`features = ["jpeg", "png"]`) compila la mitad de rápido y reduce la superficie de decodificadores.

Comprobación: con `oha -c 50 -n 500` subiendo una foto de 3 MB, un `GET /health` concurrente debe seguir respondiendo en < 5 ms, `top` debe mostrar la CPU al 100 % repartida en N hilos de rayon (no 50), y las peticiones por encima de las 32 en cola deben recibir 503 en vez de esperar.""",
            },
        ]
    },
    # 26) Inglés: broadcast vs watch para recarga de configuración.
    {
        "messages": [
            {
                "role": "user",
                "content": "I need to hot-reload a config file in a tokio service and have ~30 long-running tasks pick up the new values. Should I use `broadcast` or `watch`? I started with `broadcast` and tasks that were busy get `Lagged` errors.",
            },
            {
                "role": "assistant",
                "content": r"""`watch`. A config is **state**, not a stream of events: a task that was busy during three reloads only cares about the latest value, and that is exactly what `watch` gives you. `broadcast` keeps every message in a per-receiver buffer, so a slow receiver either lags (your error) or forces you to size the buffer for the worst case.

```rust
use std::{path::PathBuf, sync::Arc, time::Duration};

use tokio::sync::watch;

#[derive(Debug, Clone, PartialEq, serde::Deserialize)]
pub struct Config {
    pub rate_limit_per_sec: u32,
    pub upstream: String,
}

pub async fn config_reloader(path: PathBuf, tx: watch::Sender<Arc<Config>>) {
    let mut tick = tokio::time::interval(Duration::from_secs(5));
    loop {
        tick.tick().await;
        match tokio::fs::read_to_string(&path).await.map_err(anyhow::Error::from).and_then(|s| Ok(toml::from_str::<Config>(&s)?)) {
            Ok(new) => {
                // send_if_modified: no wake-ups when nothing changed
                tx.send_if_modified(|current| {
                    if **current == new { return false; }
                    *current = Arc::new(new);
                    true
                });
            }
            Err(err) => tracing::warn!(error = %err, "config reload failed; keeping previous"),
        }
    }
}

pub async fn worker(id: usize, mut rx: watch::Receiver<Arc<Config>>) {
    let mut cfg = rx.borrow_and_update().clone(); // mark the current value as seen
    loop {
        tokio::select! {
            changed = rx.changed() => {
                if changed.is_err() { break; } // sender dropped: shutting down
                cfg = rx.borrow_and_update().clone();
                tracing::info!(id, rate = cfg.rate_limit_per_sec, "config updated");
            }
            _ = do_some_work(&cfg) => {}
        }
    }
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let initial: Config = toml::from_str(&std::fs::read_to_string("config.toml")?)?;
    let (tx, rx) = watch::channel(Arc::new(initial));

    tokio::spawn(config_reloader("config.toml".into(), tx));
    for id in 0..30 {
        tokio::spawn(worker(id, rx.clone()));
    }
    tokio::signal::ctrl_c().await?;
    Ok(())
}
```

Why each piece:

- **`Arc<Config>` inside the channel.** `borrow()` returns a guard that holds a read lock; cloning an `Arc` out of it and dropping the guard immediately keeps the critical section tiny. Never hold the `borrow()` guard across an `.await`: `send` would block behind it.
- **`borrow_and_update()`**, not `borrow()`, after `changed()`. It marks the value as seen; with plain `borrow()` the next `changed()` fires again immediately for the same value.
- **`send_if_modified`** avoids waking 30 tasks every 5 seconds when the file has not changed. `PartialEq` on `Config` is what makes it possible.
- **A failed reload keeps the old config.** A syntax error in the file must never take the service down to defaults.

When `broadcast` is the right one: every message matters and must be processed by every receiver (audit events, chat messages, cache invalidation keys). There, `Lagged(n)` is a real signal that a consumer is too slow and you handle it (resync from source), not a nuisance.

If you want the reload triggered by the file system instead of a 5 s poll, use `notify` (6.x) to fire the same `send_if_modified`; keep the periodic tick as a fallback, because inotify events get lost on some Docker volume mounts.

Check: `touch config.toml` without changes must produce zero «config updated» lines; editing `rate_limit_per_sec` must produce exactly 30, one per worker, within 5 s.""",
            },
        ]
    },
    # 27) Bloqueo con tokio::sync::Mutex no reentrante (usuario trae código que se cuelga).
    {
        "messages": [
            {
                "role": "user",
                "content": """Mi servicio se queda colgado la primera vez que se pide un cliente nuevo. No hay error, no hay panic, la petición nunca responde y las siguientes a esa misma ruta tampoco. CPU al 0 %.

```rust
pub struct Registry {
    clients: tokio::sync::Mutex<HashMap<String, Client>>,
    metrics: Metrics,
}

impl Registry {
    pub async fn get_or_connect(&self, name: &str) -> anyhow::Result<Client> {
        let mut clients = self.clients.lock().await;
        if let Some(c) = clients.get(name) {
            return Ok(c.clone());
        }
        let client = self.connect(name).await?;
        clients.insert(name.to_owned(), client.clone());
        Ok(client)
    }

    async fn connect(&self, name: &str) -> anyhow::Result<Client> {
        let client = Client::connect(name).await?;
        self.metrics.record_connect(name, self.clients.lock().await.len()).await;
        Ok(client)
    }
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""Es un **interbloqueo contigo mismo**: `get_or_connect` tiene el candado de `clients` y, sin soltarlo, llama a `connect`, que vuelve a pedir `self.clients.lock().await`. El `Mutex` de tokio no es reentrante: la segunda petición espera a que se libere la primera, y la primera no se libera hasta que termine la segunda. CPU al 0 % y sin pánico es la firma exacta de un interbloqueo en async: nadie hace nada, todos esperan.

Por qué «la primera vez» y «las siguientes también»: el camino de caché (`clients.get(name)` con acierto) devuelve antes de llegar a `connect`, así que solo el primer fallo de caché entra en el bloqueo. Y como esa tarea nunca suelta el candado, cualquier petición posterior a `get_or_connect` se queda en el primer `lock().await`.

**Cómo verlo sin adivinar:** un test con plazo.

```rust
#[tokio::test]
async fn get_or_connect_does_not_hang_on_cache_miss() {
    let registry = Registry::for_tests();
    let result = tokio::time::timeout(Duration::from_secs(2), registry.get_or_connect("nuevo")).await;
    assert!(result.is_ok(), "get_or_connect se bloqueó en un fallo de caché");
}
```

Con tu código, el test falla por `Elapsed`. En producción, `tokio-console` muestra la tarea en estado *idle* con el `lock` como último punto de espera.

**Arreglo mínimo:** `connect` no debe tocar el candado; recibe el dato que necesita.

```rust
impl Registry {
    pub async fn get_or_connect(&self, name: &str) -> anyhow::Result<Client> {
        if let Some(c) = self.clients.lock().await.get(name) {
            return Ok(c.clone()); // el guard temporal muere al final de esta expresión
        }

        // sin candado durante la I/O: otras peticiones siguen leyendo la caché
        let client = Client::connect(name).await?;

        let total = {
            let mut clients = self.clients.lock().await;
            // dos tareas pudieron conectar a la vez; nos quedamos con la que ya está y cerramos la nuestra
            clients.entry(name.to_owned()).or_insert_with(|| client.clone());
            clients.len()
        };
        self.metrics.record_connect(name, total).await;

        Ok(self.clients.lock().await.get(name).cloned().expect("acabamos de insertarlo"))
    }
}
```

Y el método `connect` desaparece: su única razón de existir era registrar la métrica, que ahora se hace fuera de la sección crítica.

Dos consecuencias de hacer la I/O sin candado:

- Dos fallos de caché simultáneos del mismo `name` abren dos conexiones; `entry().or_insert_with` garantiza que solo una queda registrada. Si abrir de más es caro, usa un candado por clave (`DashMap` + `OnceCell` por entrada, o `moka` con `get_with`, que coalesce).
- Como el candado ya no se sostiene a través de ningún `.await`, puedes pasar a `std::sync::Mutex`, que es más barato y hace imposible este bug por construcción (el compilador rechaza el guard a través de un `await` en tareas `Send`).

Regla que evita la familia entera: **nunca llames a un método `&self` que pueda tomar un candado mientras tienes ese mismo candado**. Si un método necesita el candado, que lo diga en su firma recibiendo los datos ya extraídos, no `&self`.

Verificación: el test de arriba pasa en milisegundos; y un segundo test que lanza 50 `get_or_connect("mismo")` con `join_all` debe terminar con `clients.len() == 1`.""",
            },
        ]
    },
    # 28) reqwest: cliente compartido, timeouts, reintentos y TLS en contenedores (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Cómo uso reqwest bien dentro de un servicio? Ahora hago `reqwest::get(url).await` en cada llamada a la API de un proveedor y a veces se queda colgado minutos.",
            },
            {
                "role": "assistant",
                "content": r"""Tres cambios, en este orden: **un cliente compartido**, **timeouts explícitos** y **reintentos solo en lo idempotente**. `reqwest::get` crea un `Client` nuevo por llamada (sin pool de conexiones, sin keep-alive) y, sobre todo, **sin timeout por defecto**: de ahí los minutos colgado.

```toml
reqwest = { version = "0.12", features = ["json"] }
tokio = { version = "1", features = ["full"] }
```

```rust
use std::time::Duration;

use reqwest::{Client, StatusCode};
use serde::de::DeserializeOwned;

#[derive(Clone)]
pub struct ProviderClient {
    http: Client, // Arc por dentro: clonarlo comparte el pool
    base_url: String,
}

impl ProviderClient {
    pub fn new(base_url: String, api_key: &str) -> anyhow::Result<Self> {
        let mut headers = reqwest::header::HeaderMap::new();
        let mut auth = reqwest::header::HeaderValue::from_str(&format!("Bearer {api_key}"))?;
        auth.set_sensitive(true); // no aparece en los Debug de la petición
        headers.insert(reqwest::header::AUTHORIZATION, auth);

        let http = Client::builder()
            .default_headers(headers)
            .connect_timeout(Duration::from_secs(5))  // establecer TCP/TLS
            .timeout(Duration::from_secs(15))         // petición completa, cuerpo incluido
            .pool_idle_timeout(Duration::from_secs(90))
            .user_agent(concat!(env!("CARGO_PKG_NAME"), "/", env!("CARGO_PKG_VERSION")))
            .build()?;
        Ok(Self { http, base_url })
    }

    /// GET con reintentos: solo para operaciones idempotentes.
    pub async fn get_json<T: DeserializeOwned>(&self, path: &str) -> Result<T, ProviderError> {
        const ATTEMPTS: u32 = 3;
        let url = format!("{}{}", self.base_url, path);
        let mut delay = Duration::from_millis(200);

        for attempt in 1..=ATTEMPTS {
            let result = self.http.get(&url).send().await;
            match result {
                Ok(resp) if resp.status().is_success() => return Ok(resp.json::<T>().await?),
                Ok(resp) if is_retryable_status(resp.status()) && attempt < ATTEMPTS => {
                    let wait = retry_after(&resp).unwrap_or(delay);
                    tracing::warn!(status = %resp.status(), attempt, ?wait, "reintento");
                    tokio::time::sleep(wait).await;
                }
                Ok(resp) => {
                    let status = resp.status();
                    let body = resp.text().await.unwrap_or_default();
                    return Err(ProviderError::Status { status, body });
                }
                Err(err) if (err.is_timeout() || err.is_connect()) && attempt < ATTEMPTS => {
                    tracing::warn!(error = %err, attempt, "reintento por red");
                    tokio::time::sleep(delay).await;
                }
                Err(err) => return Err(err.into()),
            }
            delay = (delay * 2).min(Duration::from_secs(5)); // backoff exponencial acotado
        }
        unreachable!("el bucle devuelve en el último intento")
    }
}

fn is_retryable_status(status: StatusCode) -> bool {
    matches!(status.as_u16(), 408 | 429 | 500 | 502 | 503 | 504)
}

fn retry_after(resp: &reqwest::Response) -> Option<Duration> {
    resp.headers().get(reqwest::header::RETRY_AFTER)?.to_str().ok()?.parse::<u64>().ok().map(Duration::from_secs)
}

#[derive(Debug, thiserror::Error)]
pub enum ProviderError {
    #[error("proveedor respondió {status}: {body}")]
    Status { status: StatusCode, body: String },
    #[error(transparent)]
    Transport(#[from] reqwest::Error),
}
```

Por qué así:

- **`timeout` cubre toda la petición**, incluida la lectura del cuerpo; `connect_timeout` solo el establecimiento. Los dos hacen falta: un servidor que acepta la conexión y nunca responde solo lo corta el primero.
- **Reintentos solo en GET** (y en lo que tú sepas idempotente). Reintentar un `POST /cobrar` que hizo timeout puede cobrar dos veces; para eso el proveedor tiene que ofrecer una clave de idempotencia y la mandas en la cabecera.
- **`Retry-After` manda** sobre tu backoff cuando el servidor lo envía (429, 503).
- Si el patrón se repite en varios clientes, `reqwest-middleware` + `reqwest-retry` (con `ExponentialBackoff`) hacen esto mismo como middleware; aquí lo escribo a mano para que se vea qué decisiones toma.

Mete `ProviderClient` en el estado de la app (Axum `State`, Actix `web::Data`) y construye uno al arrancar.

Comprobación: apunta `base_url` a `http://10.255.255.1` (una IP que no responde). Antes: cuelga indefinidamente. Después: falla a los ~5 s con `is_connect()` y, tras dos reintentos, `ProviderError::Transport` en unos 11 s en total. Y con un servidor de pruebas que responde `503` con `Retry-After: 1`, el log muestra dos esperas de 1 s y luego el error.""",
            },
            {
                "role": "user",
                "content": "Al meterlo en la imagen Docker (distroless) explota al arrancar: `error: could not load system certificates` o algo así. En local va bien.",
            },
            {
                "role": "assistant",
                "content": r"""Es TLS: por defecto `reqwest` usa `native-tls` (OpenSSL en Linux) y lee los certificados raíz del sistema, y una imagen distroless mínima puede no tener la libssl que tu binario enlaza dinámicamente. Dos arreglos; el primero es el que recomiendo.

**1. `rustls` con raíces incorporadas** (sin OpenSSL, sin depender del sistema):

```toml
reqwest = { version = "0.12", default-features = false, features = ["json", "rustls-tls-webpki-roots"] }
```

`rustls-tls-webpki-roots` embebe el almacén de Mozilla en el binario (crate `webpki-roots`). El contenedor no necesita `ca-certificates` ni libssl. El binario es estático respecto a TLS y arranca en `distroless/static` o incluso `FROM scratch`.

La variante `rustls-tls-native-roots` usa `rustls` pero lee las raíces del sistema: sirve si tu empresa tiene una CA interna instalada en la imagen base; entonces sí necesitas `ca-certificates` en la imagen.

**2. Mantener `native-tls`** y darle lo que pide:

```dockerfile
FROM gcr.io/distroless/cc-debian12   # incluye libssl y ca-certificates, a diferencia de distroless/static
```

`distroless/cc` trae `libssl3` y los certificados raíz; `distroless/static` no trae ninguna de las dos cosas. Si la imagen es `static`, por eso explota.

Cómo saber cuál tienes: `ldd target/release/api` en la máquina de build. Si aparece `libssl.so.3`, es `native-tls` dinámico y necesitas `distroless/cc` (opción 2); si solo aparecen `libc`, `libm`, `libgcc_s`, vale `cc` o `static` (opción 1).

Comprobación de la opción 1 en una imagen vacía:

```dockerfile
FROM gcr.io/distroless/static-debian12
COPY --from=builder /app/target/release/api /api
ENTRYPOINT ["/api"]
```

`docker run --rm imagen` debe arrancar, y una llamada a `https://` del proveedor debe responder 200. Si falla con «invalid peer certificate: UnknownIssuer», el proveedor usa una CA que no está en Mozilla (típico en entornos internos): añade la CA con `Client::builder().add_root_certificate(reqwest::Certificate::from_pem(&pem)?)` leyendo el PEM de un secreto montado, en vez de volver a `native-tls`.""",
            },
        ]
    },
    # 29) tracing: usuario en inglés pide respuesta en español.
    {
        "messages": [
            {
                "role": "user",
                "content": "Can you explain how to set up `tracing` properly in a tokio + Axum service: JSON logs in production, readable logs in dev, and why my spans vanish inside `tokio::spawn`? Please answer in Spanish, it's going into my team's wiki.",
            },
            {
                "role": "assistant",
                "content": r"""**Configuración única con dos formatos.** Un `Registry` con `EnvFilter` y una capa `fmt` que es JSON en producción y legible en desarrollo. Se decide una vez, al arrancar.

```toml
tracing = "0.1"
tracing-subscriber = { version = "0.3", features = ["env-filter", "json"] }
tower-http = { version = "0.6", features = ["trace"] }
```

```rust
use tracing_subscriber::{fmt, layer::SubscriberExt, util::SubscriberInitExt, EnvFilter};

pub fn init_tracing(json: bool) {
    let filter = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| EnvFilter::new("info,tower_http=debug,sqlx=warn"));

    let registry = tracing_subscriber::registry().with(filter);
    if json {
        registry.with(fmt::layer().json().flatten_event(true).with_current_span(true)).init();
    } else {
        registry.with(fmt::layer().pretty().with_target(false)).init();
    }
}
```

En `main`: `init_tracing(std::env::var("LOG_FORMAT").as_deref() == Ok("json"))`. `RUST_LOG=debug,hyper=info` sigue funcionando porque `EnvFilter` lee esa variable.

**Spans en handlers.** `#[instrument]` crea un span con los argumentos como campos; excluye lo que no quieras serializar (el pool, el cuerpo) con `skip` y añade campos derivados con `fields`.

```rust
#[tracing::instrument(skip(state, body), fields(customer_id = %body.customer_id))]
async fn create_order(State(state): State<AppState>, Json(body): Json<CreateOrder>) -> Result<Json<Order>, AppError> {
    tracing::info!(lines = body.lines.len(), "creando pedido");
    let order = db::orders::create(&state.pool, &body).await?;
    tracing::info!(order_id = %order.id, "pedido creado");
    Ok(Json(order))
}
```

Y un span por petición con `TraceLayer`, que además mide la latencia:

```rust
use tower_http::trace::{DefaultOnResponse, TraceLayer};
use tracing::Level;

let trace = TraceLayer::new_for_http()
    .make_span_with(|req: &axum::extract::Request| {
        let request_id = req
            .headers()
            .get("x-request-id")
            .and_then(|v| v.to_str().ok())
            .unwrap_or("-");
        tracing::info_span!("http", method = %req.method(), uri = %req.uri().path(), request_id)
    })
    .on_response(DefaultOnResponse::new().level(Level::INFO));
```

Cada línea emitida dentro del handler lleva `method`, `uri` y `request_id` sin repetirlos a mano: eso es lo que da el span.

**Por qué desaparecen en `tokio::spawn`.** El span «actual» es por tarea, no por hilo ni por ámbito léxico. `tokio::spawn` crea una tarea nueva que arranca **sin span**, aunque la llames desde dentro de uno. Hay que adjuntárselo explícitamente:

```rust
use tracing::Instrument;

// mal: el log de dentro sale sin request_id
tokio::spawn(async move { tracing::info!("enviando email"); });

// bien: la tarea hereda el span actual
tokio::spawn(
    async move { tracing::info!("enviando email"); }.instrument(tracing::Span::current()),
);

// equivalente más corto
tokio::spawn(async move { tracing::info!("enviando email"); }.in_current_span());
```

Lo mismo aplica a `spawn_blocking`: entra con `let span = tracing::Span::current();` y dentro del closure `let _guard = span.enter();`.

**Tres errores habituales:**

- `.enter()` sobre un span **a través de un `.await`**. El guard es por hilo; tras el `await` la tarea puede despertar en otro hilo con el span equivocado. En código async, siempre `.instrument(span)` o `#[instrument]`, nunca `enter()` alrededor de un `await`.
- Olvidar `skip` en `#[instrument]` y volcar un `PgPool` o un cuerpo de 1 MB en cada línea de log: los argumentos se formatean con `Debug`.
- Niveles: `error` para lo que requiere acción, `warn` para degradación con la que el servicio sigue, `info` para hitos de negocio (uno o dos por petición), `debug` para el detalle. Si en producción hay más de ~5 líneas por petición en `info`, sobra ruido.

Comprobación: con `LOG_FORMAT=json`, una petición `POST /orders -H 'x-request-id: abc'` debe producir líneas JSON que incluyan `"request_id":"abc"` **también** en la emitida desde la tarea del email; con `pretty`, lo mismo en texto. Si la línea del email sale sin `request_id`, falta el `.instrument`.""",
            },
        ]
    },
    # 30) Config con `config` y Docker multi-stage con cargo-chef (multiturno, system variante).
    {
        "messages": [
            {"role": "system", "content": "Eres un ingeniero de plataforma. Prioriza seguridad y reproducibilidad."},
            {
                "role": "user",
                "content": "Necesito la configuración de un servicio Axum (puerto, URL de Postgres, nivel de log, timeouts) y una imagen Docker decente. Ahora mismo son `std::env::var` sueltos por el código y un `Dockerfile` de una etapa que pesa 2 GB y recompila todo con cada cambio.",
            },
            {
                "role": "assistant",
                "content": r"""**Configuración: un `struct` tipado cargado una vez.** Con el crate `config` (0.15): valores por defecto en código, un archivo opcional por entorno y variables de entorno que mandan sobre todo. El resto del programa recibe `&Settings`, nunca lee `env::var`.

```toml
config = { version = "0.15", default-features = false, features = ["toml"] }
serde = { version = "1", features = ["derive"] }
humantime-serde = "1"
```

```rust
// settings.rs
use std::time::Duration;

use serde::Deserialize;

#[derive(Debug, Clone, Deserialize)]
pub struct Settings {
    pub port: u16,
    pub database_url: String,
    pub log_level: String,
    #[serde(with = "humantime_serde")]
    pub request_timeout: Duration, // "10s", "500ms"
    pub db: DbSettings,
}

#[derive(Debug, Clone, Deserialize)]
pub struct DbSettings {
    pub max_connections: u32,
    #[serde(with = "humantime_serde")]
    pub acquire_timeout: Duration,
}

impl Settings {
    pub fn load() -> Result<Self, config::ConfigError> {
        let env = std::env::var("APP_ENV").unwrap_or_else(|_| "development".into());
        config::Config::builder()
            .set_default("port", 8080)?
            .set_default("log_level", "info")?
            .set_default("request_timeout", "10s")?
            .set_default("db.max_connections", 10)?
            .set_default("db.acquire_timeout", "5s")?
            .add_source(config::File::with_name("config/default").required(false))
            .add_source(config::File::with_name(&format!("config/{env}")).required(false))
            // APP__DATABASE_URL, APP__DB__MAX_CONNECTIONS: el doble guion bajo separa niveles
            .add_source(config::Environment::with_prefix("APP").separator("__"))
            .build()?
            .try_deserialize()
    }
}
```

`database_url` no tiene default a propósito: si falta, `load()` falla al arrancar con «missing field `database_url`», que es mejor que un pánico a la primera consulta. Los secretos **solo** por variable de entorno; los archivos `config/*.toml` van al repo y no llevan credenciales.

**Dockerfile multi-etapa con `cargo-chef`**, que cachea la compilación de dependencias por separado del código:

```dockerfile
# syntax=docker/dockerfile:1
FROM rust:1-slim-bookworm AS chef
RUN cargo install cargo-chef --locked
WORKDIR /app

FROM chef AS planner
COPY . .
RUN cargo chef prepare --recipe-path recipe.json

FROM chef AS builder
COPY --from=planner /app/recipe.json recipe.json
# solo dependencias: esta capa se reutiliza mientras Cargo.lock no cambie
RUN cargo chef cook --release --recipe-path recipe.json
COPY . .
ENV SQLX_OFFLINE=true
RUN cargo build --release --locked --bin api

FROM gcr.io/distroless/cc-debian12 AS runtime
WORKDIR /app
COPY --from=builder /app/target/release/api /app/api
COPY config /app/config
USER nonroot:nonroot
EXPOSE 8080
ENTRYPOINT ["/app/api"]
```

`.dockerignore`:

```
target
.git
.env
```

Qué consigue cada decisión:

- **`cargo chef cook` antes de `COPY . .`**: un cambio en `src/` recompila solo tu crate (segundos), no las 300 dependencias (minutos).
- **`--locked`**: falla si `Cargo.lock` no coincide con `Cargo.toml`; la imagen se construye con exactamente las versiones del repo.
- **`distroless/cc`**: ~25 MB, sin shell ni gestor de paquetes, con `libc`, `libgcc_s`, `libssl` y certificados raíz. Un binario Rust con `reqwest` + `native-tls` o `rustls` arranca ahí. Si no usas OpenSSL, `distroless/static` baja a ~2 MB.
- **`USER nonroot`**: el proceso no es root; el puerto 8080 no necesita privilegios.
- **`SQLX_OFFLINE=true`**: las macros de sqlx compilan contra `.sqlx/` (hay que tener el directorio en el repo y fuera del `.dockerignore`).

Comprobación: `docker build -t api .` dos veces seguidas tras tocar un archivo de `src/`; la segunda debe tardar < 1 min y la capa `cargo chef cook` aparecer como `CACHED`. `docker image ls api` por debajo de 50 MB. `docker run --rm -e APP__DATABASE_URL=postgres://... -p 8080:8080 api` arranca; sin la variable, termina en el acto con el error de `database_url`.""",
            },
            {
                "role": "user",
                "content": "¿Y los secretos? Me han dicho que las variables de entorno se ven con `docker inspect` y en `/proc`.",
            },
            {
                "role": "assistant",
                "content": r"""Es cierto, y el orden de preferencia es: **archivos montados por el orquestador > variables de entorno > cualquier cosa dentro de la imagen**. Lo que nunca: `ENV` o `COPY .env` en el `Dockerfile` (queda en las capas para siempre, aunque lo borres después).

Haz que `Settings` acepte las dos fuentes sin cambiar el código que las consume: para cada secreto, una variable `X_FILE` con la ruta tiene prioridad sobre `X`. Es la convención de las imágenes oficiales de Postgres y Docker Secrets.

```rust
fn secret(name: &str) -> Result<Option<String>, config::ConfigError> {
    if let Ok(path) = std::env::var(format!("{name}_FILE")) {
        return std::fs::read_to_string(&path)
            .map(|s| Some(s.trim_end().to_owned()))
            .map_err(|e| config::ConfigError::Message(format!("no se pudo leer {path}: {e}")));
    }
    Ok(std::env::var(name).ok())
}

impl Settings {
    pub fn load() -> Result<Self, config::ConfigError> {
        let mut builder = config::Config::builder()
            .set_default("port", 8080)?
            // resto de defaults y archivos como antes
            .add_source(config::Environment::with_prefix("APP").separator("__"));

        // el secreto leído del archivo se inyecta como override, por encima de todo
        if let Some(url) = secret("APP__DATABASE_URL")? {
            builder = builder.set_override("database_url", url)?;
        }
        builder.build()?.try_deserialize()
    }
}
```

Cómo se monta en cada sitio:

- **Docker Compose / Swarm**: `secrets:` en el servicio y `APP__DATABASE_URL_FILE=/run/secrets/database_url`. El archivo vive en `tmpfs`, solo lo lee el contenedor, no aparece en `docker inspect`.
- **Kubernetes**: un `Secret` montado como volumen (`/run/secrets/db/url`) con `readOnly: true`, no como `env.valueFrom.secretKeyRef`; las variables de entorno acaban en el `describe pod` y en cualquier volcado de `/proc/<pid>/environ` de un contenedor comprometido en el mismo pod.
- **Local**: `.env` con `APP__DATABASE_URL=...` cargado con `dotenvy` solo cuando `APP_ENV=development`, y `.env` en `.gitignore` y `.dockerignore`.

Dos medidas más que completan el cuadro:

- **No registres `Settings` con `{:?}`.** Implementa `Debug` a mano o envuelve los secretos en `secrecy::SecretString` (crate `secrecy` 0.10), cuyo `Debug` imprime `[REDACTED]` y que obliga a llamar `expose_secret()` para usarlo; el `grep` por `expose_secret` te dice exactamente dónde se usa cada credencial.
- **Rotación**: si el secreto se monta como archivo, el orquestador puede actualizarlo sin reiniciar; `sqlx` no relee la URL, así que una rotación de contraseña de Postgres sigue requiriendo reinicio del pod (rolling, sin corte). Con `Secret` por variable de entorno ni siquiera eso: el valor queda congelado al arrancar.

Comprobación: arranca con `APP__DATABASE_URL_FILE=/run/secrets/db` y **sin** `APP__DATABASE_URL`; la conexión debe funcionar y `docker inspect <id> | grep -i database` no debe devolver nada. Luego el negativo: un archivo con una URL inválida debe hacer que el servicio termine al arrancar con un mensaje que diga la ruta del archivo, no la URL.""",
            },
        ]
    },
]
