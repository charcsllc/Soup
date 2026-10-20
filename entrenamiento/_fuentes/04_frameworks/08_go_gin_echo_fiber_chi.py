"""04_frameworks / 08: net/http 1.22+, chi, Gin, Echo y Fiber (reparto 10 / 6 / 6 / 4 / 4)."""

SISTEMA = (
    "Eres un asistente experto en programación, análisis y razonamiento. Respondes en el "
    "idioma del usuario (español por defecto), con precisión y sin relleno, y verificas tu "
    "trabajo antes de responder."
)

ROWS = [
    # ---------------------------------------------------------------- net/http (10)
    # 1) Estructura cmd/internal, ServeMux 1.22 con métodos y patrones, http.Server con timeouts (system exacto).
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Voy a hacer una API en Go sin framework, solo net/http. ¿Cómo la estructuro (carpetas, router, handlers con dependencias) para que no sea un `main.go` gigante y se pueda testear? Go 1.23.",
            },
            {
                "role": "assistant",
                "content": r"""Con Go 1.22+ el `ServeMux` de la biblioteca estándar ya enruta por método y captura segmentos, así que no necesitas un router externo para empezar. La estructura que escala sin reescribir:

```
cmd/api/main.go            # arranque: config, dependencias, http.Server
internal/
  server/
    server.go              # NewServer(deps) http.Handler
    routes.go              # addRoutes(mux, deps): la tabla de rutas, en un solo sitio
    middleware.go
  users/
    handler.go             # handlers de /users como métodos de un struct con sus dependencias
    service.go
    repo.go
  platform/
    httpx/                 # helpers: encode/decode JSON, errores
```

**`main.go` solo cablea**, y delega en una función `run` que recibe lo que en tests querrás controlar (contexto, salida, variables de entorno):

```go
package main

import (
	"cmp"
	"context"
	"errors"
	"fmt"
	"log/slog"
	"net"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"example.com/api/internal/server"
	"example.com/api/internal/users"
)

func main() {
	if err := run(context.Background(), os.Getenv); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func run(ctx context.Context, getenv func(string) string) error {
	ctx, stop := signal.NotifyContext(ctx, os.Interrupt, syscall.SIGTERM)
	defer stop()

	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	userStore := users.NewMemoryStore() // en producción: users.NewPostgresStore(pool)

	handler := server.New(logger, userStore)

	srv := &http.Server{
		Addr:              net.JoinHostPort("0.0.0.0", cmp.Or(getenv("PORT"), "8080")),
		Handler:           handler,
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       10 * time.Second,
		WriteTimeout:      30 * time.Second,
		IdleTimeout:       120 * time.Second,
		BaseContext:       func(net.Listener) context.Context { return ctx },
	}

	errCh := make(chan error, 1)
	go func() { errCh <- srv.ListenAndServe() }()
	logger.Info("escuchando", "addr", srv.Addr)

	select {
	case err := <-errCh:
		return fmt.Errorf("servidor: %w", err)
	case <-ctx.Done():
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		if err := srv.Shutdown(shutdownCtx); err != nil && !errors.Is(err, context.DeadlineExceeded) {
			return fmt.Errorf("apagado: %w", err)
		}
		return nil
	}
}
```

(`cmp.Or` es de Go 1.22: devuelve el primer valor no vacío.)

**El servidor es un `http.Handler`** construido con sus dependencias; la tabla de rutas se lee de arriba abajo:

```go
package server

import (
	"log/slog"
	"net/http"

	"example.com/api/internal/users"
)

func New(logger *slog.Logger, store users.Store) http.Handler {
	mux := http.NewServeMux()
	addRoutes(mux, logger, store)

	var handler http.Handler = mux
	handler = recoverPanics(logger, handler)
	handler = logRequests(logger, handler)
	return handler
}

func addRoutes(mux *http.ServeMux, logger *slog.Logger, store users.Store) {
	uh := users.NewHandler(logger, store)

	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(http.StatusNoContent) })
	mux.HandleFunc("GET /users/{id}", uh.Get)
	mux.HandleFunc("POST /users", uh.Create)
	mux.HandleFunc("GET /users/{$}", uh.List) // {$}: solo /users exacto, no /users/cualquier-cosa
	mux.Handle("/", http.NotFoundHandler())
}
```

**Los handlers son métodos de un struct** con sus dependencias; nada global:

```go
package users

type Handler struct {
	logger *slog.Logger
	store  Store
}

func NewHandler(logger *slog.Logger, store Store) *Handler {
	return &Handler{logger: logger, store: store}
}

func (h *Handler) Get(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id") // Go 1.22: captura del patrón {id}
	user, err := h.store.Get(r.Context(), id)
	if errors.Is(err, ErrNotFound) {
		httpx.Error(w, http.StatusNotFound, "user not found")
		return
	}
	if err != nil {
		h.logger.ErrorContext(r.Context(), "obteniendo usuario", "err", err, "id", id)
		httpx.Error(w, http.StatusInternalServerError, "internal error")
		return
	}
	httpx.JSON(w, http.StatusOK, user)
}
```

Por qué estas decisiones:

- **`run(ctx, getenv)`** hace que un test de integración arranque el servicio entero con `getenv` falso y lo pare cancelando `ctx`, sin `os.Exit` ni variables globales.
- **`server.New` devuelve `http.Handler`**: los tests usan `httptest.NewServer(server.New(...))` o `handler.ServeHTTP(rec, req)` directamente.
- **`internal/`**: el compilador prohíbe importarlo desde fuera del módulo; es tu límite de API pública gratis.
- **Timeouts en `http.Server` siempre**: sin `ReadHeaderTimeout` una conexión que manda cabeceras gota a gota ocupa un goroutine para siempre.
- Patrones del mux 1.22: `GET` también acepta `HEAD`; dos patrones que se solapan sin que uno sea más específico hacen `panic` al registrarse, lo que es mejor que un enrutado ambiguo en producción; una petición con método no registrado recibe 405 con `Allow` automático.

Comprobación: `go run ./cmd/api` y `curl -i -X DELETE localhost:8080/users/1` debe dar `405` con `Allow: GET`; `curl -i localhost:8080/users/` (barra final) debe dar 404 gracias al `{$}`.""",
            },
        ]
    },
    # 2) Apagado ordenado, y luego Docker distroless (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": "Cada vez que desplegamos, el balanceador registra unos cuantos 502 y algunos clientes ven peticiones cortadas. La API es net/http con `http.ListenAndServe(\":8080\", mux)`. ¿Cómo hago que termine las peticiones en curso antes de morir?",
            },
            {
                "role": "assistant",
                "content": r"""`http.ListenAndServe` no tiene forma de apagarse: el proceso recibe `SIGTERM` y el runtime lo mata con las conexiones abiertas. Necesitas un `*http.Server` propio y llamar a `Shutdown`, que cierra el *listener*, deja terminar las peticiones activas y devuelve cuando no queda ninguna (o cuando vence el contexto).

```go
package main

import (
	"context"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"
)

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	mux := http.NewServeMux()
	mux.HandleFunc("GET /slow", func(w http.ResponseWriter, r *http.Request) {
		time.Sleep(5 * time.Second) // para probar el apagado
		w.Write([]byte("hecho\n"))
	})

	srv := &http.Server{
		Addr:              ":8080",
		Handler:           mux,
		ReadHeaderTimeout: 5 * time.Second,
	}

	// ctx se cancela con SIGINT o SIGTERM; stop() restaura el comportamiento por defecto
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	go func() {
		if err := srv.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			logger.Error("servidor", "err", err)
			os.Exit(1)
		}
	}()
	logger.Info("escuchando", "addr", srv.Addr)

	<-ctx.Done()
	logger.Info("señal recibida; dejo de aceptar conexiones y espero a las peticiones en curso")

	shutdownCtx, cancel := context.WithTimeout(context.Background(), 15*time.Second)
	defer cancel()
	if err := srv.Shutdown(shutdownCtx); err != nil {
		logger.Error("apagado forzoso: quedaban peticiones al vencer el plazo", "err", err)
		srv.Close() // corta lo que quede
	}
	logger.Info("apagado completo")
}
```

Lo que hace cada pieza y por qué está donde está:

- **`signal.NotifyContext`** convierte la señal en un contexto cancelado; es más simple que un canal de señales a mano y se compone con el resto del programa.
- **`http.ErrServerClosed`** es lo que `ListenAndServe` devuelve tras `Shutdown`; no es un error.
- **El plazo de `Shutdown`** debe ser menor que el que da el orquestador antes de `SIGKILL` (Docker: 10 s por defecto; Kubernetes: `terminationGracePeriodSeconds`, 30 s). Si tus peticiones pueden durar más, sube los dos.
- **`Shutdown` no espera conexiones secuestradas** (WebSockets, `Hijack`): regístralas con `srv.RegisterOnShutdown` y ciérralas tú.

Y la parte que explica los 502 del balanceador: cuando el *listener* se cierra, el balanceador aún tiene al pod en su lista durante unos segundos y sigue mandándole tráfico. Dos medidas:

1. **Un pequeño retraso antes de `Shutdown`** si no controlas el balanceador: `time.Sleep(3 * time.Second)` tras recibir la señal, para que el *health check* falle y te saquen de rotación mientras sigues sirviendo. En Kubernetes, lo equivalente es `lifecycle.preStop: exec: sleep 5`.
2. **Que `/healthz` empiece a devolver 503 en cuanto llega la señal**, con un `atomic.Bool`, para acelerar esa retirada.

Comprobación:

```bash
go run . &
curl -s localhost:8080/slow &   # tarda 5 s
sleep 1 && kill -TERM %1
wait
```

Debe imprimir `hecho`, luego «apagado completo», y el proceso terminar a los ~5 s, no de inmediato. Si `curl` muere con «connection reset», el `Shutdown` no se está llamando (señal no capturada o `ListenAndServe` global todavía en uso).""",
            },
            {
                "role": "user",
                "content": "Esto corre en Docker. ¿Hay algo del Dockerfile que afecte? Ahora mismo es `FROM golang:1.23` y `CMD go run ./cmd/api`.",
            },
            {
                "role": "assistant",
                "content": r"""Sí, y es probablemente la causa de que la señal nunca llegara: con `CMD go run ./cmd/api`, el PID 1 es `go run`, que compila y lanza tu binario como proceso hijo. Docker manda `SIGTERM` al PID 1; `go run` lo recibe y tu servidor no. Además la imagen pesa ~800 MB y compila en cada arranque.

Dockerfile multietapa con binario estático y una imagen final sin shell:

```dockerfile
# syntax=docker/dockerfile:1
FROM golang:1.23 AS build
WORKDIR /src

# dependencias primero: esta capa se cachea mientras go.mod/go.sum no cambien
COPY go.mod go.sum ./
RUN --mount=type=cache,target=/go/pkg/mod go mod download

COPY . .
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/api ./cmd/api

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /out/api /api
EXPOSE 8080
ENTRYPOINT ["/api"]
```

Qué resuelve cada línea:

- **`ENTRYPOINT ["/api"]` en forma *exec*** (lista JSON): el binario es el PID 1 y recibe `SIGTERM` directamente. La forma *shell* (`ENTRYPOINT /api`) mete un `sh -c` en medio y vuelves al problema.
- **`CGO_ENABLED=0`**: binario estático, sin libc; es lo que permite `distroless/static` (~2 MB de base). Si usas `sqlite3` con cgo u otra dependencia C, necesitas `distroless/base` o compilar con `-tags` puros.
- **`-trimpath -ldflags="-s -w"`**: quita rutas de tu máquina y la tabla de símbolos; el binario baja un 30-40 %. Las trazas de pánico siguen teniendo nombres de función y líneas.
- **`:nonroot`**: el proceso corre como UID 65532. El puerto 8080 no necesita root.
- **`--mount=type=cache`**: el cache de módulos y de compilación sobrevive entre builds sin quedar en la imagen.

Detalle de PID 1 que sí importa en Go: tu binario como PID 1 no cosecha procesos huérfanos, pero si no lanzas subprocesos no te afecta. Si los lanzas, `docker run --init` o `tini`.

Comprobación: `docker build -t api .` y luego

```bash
docker run -d --name api -p 8080:8080 api
curl -s localhost:8080/slow &
sleep 1; time docker stop api
```

`docker stop` debe tardar ~4 s (lo que le quede a la petición), no 10 (el plazo tras el que Docker manda `SIGKILL`). Si tarda exactamente 10 s, la señal no está llegando: revisa que el `ENTRYPOINT` sea la forma *exec*. Y `docker image ls api` debe estar por debajo de 20 MB.""",
            },
        ]
    },
    # 3) Middlewares: cadena, logging con slog, recover, captura de status (España).
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Cómo se hacen middlewares en net/http sin framework? Quiero logging de cada petición (método, ruta, status, duración), recuperación de panics y un request id, y que podamos reutilizarlos en todos nuestros servicios.",
            },
            {
                "role": "assistant",
                "content": r"""Un middleware en net/http es una función `func(http.Handler) http.Handler`. Se encadenan componiéndolas, y el único truco de verdad es **capturar el status**, porque `http.ResponseWriter` no lo expone: hay que envolverlo.

```go
package middleware

import (
	"crypto/rand"
	"encoding/hex"
	"log/slog"
	"net/http"
	"runtime/debug"
	"time"
)

type Middleware func(http.Handler) http.Handler

// Chain aplica los middlewares en el orden en que se leen: el primero es el más externo.
func Chain(h http.Handler, mws ...Middleware) http.Handler {
	for i := len(mws) - 1; i >= 0; i-- {
		h = mws[i](h)
	}
	return h
}

// statusWriter captura el código y los bytes escritos.
type statusWriter struct {
	http.ResponseWriter
	status int
	bytes  int
}

func (w *statusWriter) WriteHeader(code int) {
	if w.status == 0 {
		w.status = code
	}
	w.ResponseWriter.WriteHeader(code)
}

func (w *statusWriter) Write(b []byte) (int, error) {
	if w.status == 0 {
		w.status = http.StatusOK // Write sin WriteHeader previo implica 200
	}
	n, err := w.ResponseWriter.Write(b)
	w.bytes += n
	return n, err
}

// Unwrap permite que http.ResponseController llegue al writer original (Flush, Hijack, SetWriteDeadline).
func (w *statusWriter) Unwrap() http.ResponseWriter { return w.ResponseWriter }

func RequestID(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		id := r.Header.Get("X-Request-ID")
		if id == "" {
			var b [8]byte
			rand.Read(b[:])
			id = hex.EncodeToString(b[:])
		}
		w.Header().Set("X-Request-ID", id)
		next.ServeHTTP(w, r.WithContext(withRequestID(r.Context(), id)))
	})
}

func Logger(logger *slog.Logger) Middleware {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			start := time.Now()
			sw := &statusWriter{ResponseWriter: w}
			next.ServeHTTP(sw, r)
			logger.LogAttrs(r.Context(), levelFor(sw.status), "request",
				slog.String("method", r.Method),
				slog.String("path", r.URL.Path),
				slog.Int("status", sw.status),
				slog.Int("bytes", sw.bytes),
				slog.Duration("duration", time.Since(start)),
				slog.String("request_id", RequestIDFrom(r.Context())),
			)
		})
	}
}

func levelFor(status int) slog.Level {
	switch {
	case status >= 500:
		return slog.LevelError
	case status >= 400:
		return slog.LevelWarn
	default:
		return slog.LevelInfo
	}
}

func Recover(logger *slog.Logger) Middleware {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			defer func() {
				if rec := recover(); rec != nil {
					if rec == http.ErrAbortHandler { // el handler abortó a propósito; no es un bug
						panic(rec)
					}
					logger.ErrorContext(r.Context(), "panic en handler",
						"err", rec, "stack", string(debug.Stack()), "request_id", RequestIDFrom(r.Context()))
					http.Error(w, "internal error", http.StatusInternalServerError)
				}
			}()
			next.ServeHTTP(w, r)
		})
	}
}
```

El request id en el contexto, con clave de tipo privado para que ningún otro paquete pueda colisionar:

```go
type ctxKey struct{}

func withRequestID(ctx context.Context, id string) context.Context {
	return context.WithValue(ctx, ctxKey{}, id)
}

func RequestIDFrom(ctx context.Context) string {
	id, _ := ctx.Value(ctxKey{}).(string)
	return id
}
```

Y el cableado, que se lee en el orden en que viaja la petición:

```go
handler := middleware.Chain(mux,
	middleware.RequestID,          // 1.º: para que el logger y el recover ya tengan id
	middleware.Logger(logger),     // 2.º: mide también el tiempo del recover
	middleware.Recover(logger),    // 3.º: el más cercano al handler
)
```

Detalles que distinguen esto de una versión ingenua:

- **`Unwrap`** en el wrapper: desde Go 1.20, `http.NewResponseController(w).Flush()` busca `Unwrap` para llegar al writer real. Sin él, el streaming (SSE) y `Hijack` (WebSockets) dejan de funcionar detrás de tu middleware, y es un fallo silencioso.
- **`http.ErrAbortHandler`** se relanza: es la forma oficial de abortar una respuesta sin registrar un pánico.
- **El recover devuelve 500 solo si no se ha escrito nada**; si el handler ya envió cabeceras, `http.Error` fallará con «superfluous WriteHeader» en el log; es inevitable y correcto.
- **`LogAttrs`** evita construir los atributos si el nivel está desactivado; en un middleware que corre en cada petición, compensa.

Para compartirlo entre servicios: un módulo `github.com/tu-org/httpkit` con este paquete, sin dependencias fuera de la biblioteca estándar, para que cualquier servicio (incluidos los que usan chi o Gin, que aceptan `func(http.Handler) http.Handler`) lo importe.

Comprobación: un handler que hace `panic("boom")` debe producir una línea de log con `stack` y una respuesta 500 con `X-Request-ID`; un `GET /healthz` que solo hace `w.Write` debe registrar `status=200` (no 0).""",
            },
        ]
    },
    # 4) context: cancelación por desconexión del cliente (usuario trae log).
    {
        "messages": [
            {
                "role": "user",
                "content": """En los logs de producción veo muchos de estos y no sé si es un bug:

```
level=ERROR msg="listando pedidos" err="context canceled"
level=ERROR msg="listando pedidos" err="timeout: context deadline exceeded"
```

El handler pasa `r.Context()` a pgx. Los clientes son una app móvil. ¿Tengo que dejar de pasar el contexto?""",
            },
            {
                "role": "assistant",
                "content": r"""No es un bug y no dejes de pasarlo: es el contexto haciendo su trabajo. Los dos mensajes tienen causas distintas y se tratan distinto.

**`context canceled`**: el cliente cerró la conexión antes de recibir la respuesta (la app pasó a segundo plano, el usuario salió de la pantalla, se perdió la red). net/http cancela `r.Context()` en cuanto lo detecta, pgx aborta la consulta y Postgres libera la conexión. Sin eso, la consulta de un cliente que ya no está seguiría consumiendo base de datos. Es el comportamiento que quieres; lo que sobra es el nivel `ERROR`.

**`context deadline exceeded`**: venció un plazo que **tú** pusiste (un `context.WithTimeout` en el handler o en el middleware) o el del pool de pgx. Eso sí merece atención: o el plazo es corto para esa consulta o la consulta es lenta.

Arreglo en el handler: distinguir las tres situaciones y no registrar como error lo que no lo es.

```go
func (h *Handler) List(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 5*time.Second) // presupuesto explícito por petición
	defer cancel()

	orders, err := h.store.List(ctx, userIDFrom(ctx))
	switch {
	case err == nil:
		httpx.JSON(w, http.StatusOK, orders)
	case errors.Is(r.Context().Err(), context.Canceled):
		// el cliente se fue: no hay a quién responder y no es un fallo nuestro
		h.logger.DebugContext(ctx, "cliente desconectado durante la consulta")
		// 499 es la convención de nginx para "client closed request"; el cliente nunca lo verá
		w.WriteHeader(499)
	case errors.Is(err, context.DeadlineExceeded):
		h.logger.WarnContext(ctx, "consulta fuera de plazo", "err", err, "timeout", "5s")
		httpx.Error(w, http.StatusGatewayTimeout, "request timed out")
	default:
		h.logger.ErrorContext(ctx, "listando pedidos", "err", err)
		httpx.Error(w, http.StatusInternalServerError, "internal error")
	}
}
```

La clave es comprobar **`r.Context().Err()`**, no solo `err`: pgx envuelve la cancelación en su propio error, pero el contexto de la petición dice sin ambigüedad si fue el cliente quien se fue.

Dos cosas más que valen la pena mirar:

- **Métrica en vez de log** para las cancelaciones: un contador `requests_canceled_total{route}`. Si sube de golpe en una ruta, esa pantalla de la app está tardando tanto que la gente se va; es señal de rendimiento, no de error.
- **Trabajo que no debe cancelarse** cuando el cliente se va (escribir un pedido ya validado, encolar un email): usa `context.WithoutCancel(r.Context())` (Go 1.21+), que conserva los valores (request id, usuario) pero no la cancelación. Lo contrario, pasar `context.Background()`, pierde el request id en los logs.

```go
bgCtx := context.WithoutCancel(r.Context())
go h.mailer.SendConfirmation(bgCtx, order) // sobrevive a la desconexión del cliente
```

Comprobación: con `curl -m 0.1 localhost:8080/orders` (plazo de 100 ms) debe aparecer la línea `DEBUG cliente desconectado` y no la de `ERROR`; y en `pg_stat_activity` no debe quedar la consulta corriendo tras el corte.""",
            },
        ]
    },
    # 5) Inglés: decodificar y escribir JSON correctamente.
    {
        "messages": [
            {
                "role": "user",
                "content": "What's the proper way to read a JSON request body in a net/http handler? I do `json.NewDecoder(r.Body).Decode(&req)` and return 400 on error, but I've been told that's not enough.",
            },
            {
                "role": "assistant",
                "content": r"""It is not enough on four counts: the body has no size limit, unknown fields are silently accepted, a body with two JSON values is accepted, and every failure becomes the same opaque 400. One helper fixes all of them and every handler calls it.

```go
package httpx

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strings"
)

const maxBodyBytes = 1 << 20 // 1 MiB

// DecodeJSON reads exactly one JSON value into dst and reports client errors with actionable messages.
func DecodeJSON(w http.ResponseWriter, r *http.Request, dst any) error {
	if ct := r.Header.Get("Content-Type"); ct != "" && !strings.HasPrefix(ct, "application/json") {
		return &ClientError{Status: http.StatusUnsupportedMediaType, Msg: "Content-Type must be application/json"}
	}

	r.Body = http.MaxBytesReader(w, r.Body, maxBodyBytes) // also closes the connection if exceeded
	dec := json.NewDecoder(r.Body)
	dec.DisallowUnknownFields()

	if err := dec.Decode(dst); err != nil {
		var syntaxErr *json.SyntaxError
		var typeErr *json.UnmarshalTypeError
		var maxErr *http.MaxBytesError
		switch {
		case errors.As(err, &syntaxErr):
			return &ClientError{Status: http.StatusBadRequest, Msg: fmt.Sprintf("malformed JSON at offset %d", syntaxErr.Offset)}
		case errors.Is(err, io.ErrUnexpectedEOF):
			return &ClientError{Status: http.StatusBadRequest, Msg: "malformed JSON"}
		case errors.As(err, &typeErr):
			return &ClientError{Status: http.StatusBadRequest, Msg: fmt.Sprintf("field %q must be %s", typeErr.Field, typeErr.Type)}
		case strings.HasPrefix(err.Error(), "json: unknown field "):
			field := strings.TrimPrefix(err.Error(), "json: unknown field ")
			return &ClientError{Status: http.StatusBadRequest, Msg: "unknown field " + field}
		case errors.Is(err, io.EOF):
			return &ClientError{Status: http.StatusBadRequest, Msg: "body must not be empty"}
		case errors.As(err, &maxErr):
			return &ClientError{Status: http.StatusRequestEntityTooLarge, Msg: fmt.Sprintf("body must be at most %d bytes", maxErr.Limit)}
		default:
			return err // genuinely unexpected: let the caller log it and return 500
		}
	}

	// A second value after the first means "two JSON documents in one body"; reject it.
	if err := dec.Decode(&struct{}{}); !errors.Is(err, io.EOF) {
		return &ClientError{Status: http.StatusBadRequest, Msg: "body must contain a single JSON value"}
	}
	return nil
}

type ClientError struct {
	Status int
	Msg    string
}

func (e *ClientError) Error() string { return e.Msg }

func JSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(v); err != nil {
		// headers are already sent; nothing useful can be done except log
		return
	}
}

func Error(w http.ResponseWriter, status int, msg string) {
	JSON(w, status, map[string]string{"error": msg})
}
```

Handler usage:

```go
func (h *Handler) Create(w http.ResponseWriter, r *http.Request) {
	var req CreateUserRequest
	if err := httpx.DecodeJSON(w, r, &req); err != nil {
		var ce *httpx.ClientError
		if errors.As(err, &ce) {
			httpx.Error(w, ce.Status, ce.Msg)
			return
		}
		h.logger.ErrorContext(r.Context(), "decoding body", "err", err)
		httpx.Error(w, http.StatusInternalServerError, "internal error")
		return
	}
	// validate req, call the service
}
```

Why each piece matters:

- **`http.MaxBytesReader`** is the only thing standing between you and a client posting 2 GB. It returns `*http.MaxBytesError` (Go 1.19+), which is why the switch can turn it into a 413.
- **`DisallowUnknownFields`** catches typos in field names (`"emial"`) that would otherwise be silently dropped. The unknown-field error has no typed form in `encoding/json`, hence the string prefix match; it is stable across Go versions.
- **The trailing `Decode`** guards against `{"a":1}{"b":2}`; `Decoder` reads a stream, and without this check the second object is simply ignored.
- **`UnmarshalTypeError.Field`** gives you the JSON path (`"address.zip"`), so the message points at the exact field.

On the output side, use struct tags deliberately: `json:"name"`, `json:"note,omitempty"`, and from Go 1.24 `json:"created_at,omitzero"`, which omits zero-valued structs such as an unset `time.Time` (`omitempty` never omits structs).

Check with a table test: `{"name": 5}` returns 400 and `field "name" must be string`; `{"name":"a","x":1}` returns 400 with `unknown field "x"`; a 2 MB body returns 413; `{"name":"a"}{"name":"b"}` returns 400 with the single-value message.""",
            },
        ]
    },
    # 6) Testing de handlers con httptest, tabla y t.Parallel.
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Cómo pruebo handlers de net/http? Ahora levanto el servidor con `go run` y lanzo curls a mano antes de cada PR, y obviamente se nos escapan cosas.",
            },
            {
                "role": "assistant",
                "content": r"""Con `net/http/httptest` y tests de tabla: construyes el handler con dependencias falsas, le pasas un `*httptest.ResponseRecorder` y compruebas el resultado. Sin puertos, sin procesos, milisegundos por test.

```go
package users_test

import (
	"context"
	"encoding/json"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"example.com/api/internal/server"
	"example.com/api/internal/users"
)

// fakeStore implementa users.Store en memoria; lo que necesita el test, nada más.
type fakeStore struct {
	users map[string]users.User
}

func (f *fakeStore) Get(_ context.Context, id string) (users.User, error) {
	u, ok := f.users[id]
	if !ok {
		return users.User{}, users.ErrNotFound
	}
	return u, nil
}

func (f *fakeStore) Create(_ context.Context, u users.User) (users.User, error) {
	u.ID = "u-" + u.Email
	f.users[u.ID] = u
	return u, nil
}

func newTestHandler(t *testing.T) http.Handler {
	t.Helper()
	store := &fakeStore{users: map[string]users.User{"u-1": {ID: "u-1", Email: "ana@example.com"}}}
	return server.New(slog.New(slog.DiscardHandler), store) // slog.DiscardHandler: Go 1.24; antes, un handler sobre io.Discard
}

func TestUsers(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name       string
		method     string
		path       string
		body       string
		wantStatus int
		wantBody   string // subcadena que debe aparecer
	}{
		{name: "existente", method: http.MethodGet, path: "/users/u-1", wantStatus: http.StatusOK, wantBody: `"email":"ana@example.com"`},
		{name: "inexistente", method: http.MethodGet, path: "/users/nope", wantStatus: http.StatusNotFound, wantBody: "user not found"},
		{name: "método no permitido", method: http.MethodDelete, path: "/users/u-1", wantStatus: http.StatusMethodNotAllowed},
		{name: "crear", method: http.MethodPost, path: "/users", body: `{"email":"luis@example.com"}`, wantStatus: http.StatusCreated, wantBody: `"id":"u-luis@example.com"`},
		{name: "crear con campo desconocido", method: http.MethodPost, path: "/users", body: `{"email":"x@example.com","rol":"admin"}`, wantStatus: http.StatusBadRequest, wantBody: "unknown field"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			handler := newTestHandler(t) // un handler y un store por subtest: sin estado compartido

			req := httptest.NewRequest(tt.method, tt.path, strings.NewReader(tt.body))
			if tt.body != "" {
				req.Header.Set("Content-Type", "application/json")
			}
			rec := httptest.NewRecorder()

			handler.ServeHTTP(rec, req)

			if rec.Code != tt.wantStatus {
				t.Fatalf("status = %d, quería %d; cuerpo: %s", rec.Code, tt.wantStatus, rec.Body.String())
			}
			if tt.wantBody != "" && !strings.Contains(rec.Body.String(), tt.wantBody) {
				t.Errorf("cuerpo = %q, quería que contuviera %q", rec.Body.String(), tt.wantBody)
			}
		})
	}
}
```

Decisiones:

- **Se prueba a través de `server.New`**, no llamando al método del handler directamente. Así el test cubre el enrutado (`{id}`, 405), los middlewares y la serialización, que es donde están la mitad de los bugs de una API.
- **Un `fakeStore` a mano**, no una librería de mocks: tres métodos, cero dependencias, y el test se lee entero. Cuando la interfaz crece, lo que crece es el fake, no la magia.
- **`t.Parallel()` en el padre y en cada subtest**, con dependencias construidas dentro del subtest. Con Go 1.22+ no hay que copiar `tt := tt`: la variable del bucle ya es por iteración.
- **`t.Fatalf` para el status, `t.Errorf` para el cuerpo**: si el status es otro, el cuerpo no tiene sentido; si el status va bien, quieres ver todos los fallos de cuerpo a la vez.

Cuando necesites un cliente HTTP real (probar `http.Client` con reintentos, redirecciones, timeouts), `httptest.NewServer(handler)` levanta un servidor en un puerto libre y te da `srv.URL`; `t.Cleanup(srv.Close)`.

Comprobación: `go test ./... -race -count=1`; el `-race` es importante con `t.Parallel` porque es lo que te avisará si el `fakeStore` (o el handler) comparte un mapa sin candado. Y para ver que los tests de verdad pasan por el router, cambia el patrón a `GET /users/{uid}` dejando `r.PathValue("id")`: el test «existente» debe fallar con 404.""",
            },
        ]
    },
    # 7) Timeouts del servidor y del cliente; "too many open files" (México, system variante).
    {
        "messages": [
            {"role": "system", "content": "Responde en español de México, directo y sin rodeos."},
            {
                "role": "user",
                "content": "Nuestro servicio en Go se cae cada pocos días con `accept tcp [::]:8080: accept4: too many open files` y hay que reiniciarlo. Subimos el ulimit y solo tardó más en pasar. ¿Qué está fugando?",
            },
            {
                "role": "assistant",
                "content": r"""Conexiones que nunca se cierran. Subir el `ulimit` solo agranda el balde; hay que cerrar la llave. Con Go, el 90 % de las veces es una de estas tres, en este orden de probabilidad:

**1. El `http.Server` no tiene timeouts.** `http.ListenAndServe(":8080", h)` crea un servidor con **cero** timeouts: un cliente que abre la conexión y no manda nada (o manda las cabeceras byte a byte) ocupa un goroutine y un descriptor para siempre. Con un *scanner* de internet o un balanceador con *health checks* mal configurados, se acumulan.

```go
srv := &http.Server{
	Addr:              ":8080",
	Handler:           h,
	ReadHeaderTimeout: 5 * time.Second,   // tiempo para recibir las cabeceras completas
	ReadTimeout:       15 * time.Second,  // cabeceras + cuerpo
	WriteTimeout:      30 * time.Second,  // desde el fin de la lectura hasta terminar de escribir
	IdleTimeout:       60 * time.Second,  // keep-alive sin peticiones
}
```

`ReadHeaderTimeout` es el que mata el *slowloris*; `IdleTimeout` el que limpia conexiones keep-alive abandonadas. Si un handler necesita más de 30 s (descargas grandes), usa `http.NewResponseController(w).SetWriteDeadline(...)` dentro de ese handler en vez de subir el global.

**2. Respuestas de `http.Client` sin cerrar.** Cada `resp.Body` que no se cierra deja la conexión fuera del pool y el descriptor abierto. Busca en tu código llamadas salientes y comprueba que todas hacen esto:

```go
resp, err := client.Do(req)
if err != nil {
	return err
}
defer resp.Body.Close()
// y además LEER el cuerpo (aunque no lo uses) para que la conexión vuelva al pool:
if _, err := io.Copy(io.Discard, resp.Body); err != nil { /* registrar */ }
```

Y el cliente en sí, uno por servicio y con timeout; `http.DefaultClient` tampoco tiene:

```go
client := &http.Client{
	Timeout: 10 * time.Second,
	Transport: &http.Transport{
		MaxIdleConns:        100,
		MaxIdleConnsPerHost: 20, // el default es 2: con más concurrencia abres y cierras conexiones sin parar
		IdleConnTimeout:     90 * time.Second,
	},
}
```

**3. Archivos o conexiones de base de datos sin `Close`.** `os.Open` sin `defer f.Close()`, `rows, _ := db.Query(...)` sin `defer rows.Close()` (cada `Rows` abierto retiene una conexión del pool), y pools sin `SetMaxOpenConns`.

**Cómo saber cuál es, en cinco minutos**, sin reiniciar:

```bash
PID=$(pgrep -f tu-binario)
ls -l /proc/$PID/fd | awk '{print $NF}' | sed 's/:.*//' | sort | uniq -c | sort -rn | head
ss -tanp | grep "pid=$PID" | awk '{print $1}' | sort | uniq -c
```

- Muchos `socket:` y en `ss` la mayoría en `ESTAB` con el puerto 8080 local → causa 1 (conexiones entrantes vivas sin tráfico).
- Muchos `ESTAB` hacia un puerto remoto (443, 5432) → causa 2 o 3.
- Muchos archivos regulares → causa 3.
- Y `curl localhost:6060/debug/pprof/goroutine?debug=1` (con `net/http/pprof` importado) te dice **en qué línea** están parados los goroutines acumulados; esa línea es la fuga.

Comprobación tras el arreglo: en una terminal `for i in $(seq 200); do (exec 3<>/dev/tcp/localhost/8080; sleep 300) & done` (200 conexiones que no mandan nada) y en otra `ss -tan | grep -c 8080`. Con `ReadHeaderTimeout` de 5 s, el número tiene que bajar a ~0 a los 5 s; sin él, se queda en 200 los cinco minutos.""",
            },
        ]
    },
    # 8) pgx + sqlc; después GORM (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": "Para acceso a Postgres en Go, ¿database/sql, pgx directo, sqlc o GORM? Es una API de pedidos normal, nada exótico, y el equipo viene de Java/Hibernate.",
            },
            {
                "role": "assistant",
                "content": r"""**pgx v5 como driver + sqlc para generar el código a partir del SQL.** Escribes las consultas en archivos `.sql`, sqlc genera funciones Go tipadas y comprobadas contra el esquema, y pgx las ejecuta sin la capa de `database/sql`. Para una API de pedidos es lo que mejor envejece: el SQL es visible, los tipos no se adivinan en ejecución y no hay un ORM que aprender.

```yaml
# sqlc.yaml
version: "2"
sql:
  - engine: "postgresql"
    schema: "db/migrations"
    queries: "db/queries"
    gen:
      go:
        package: "db"
        out: "internal/db"
        sql_package: "pgx/v5"
        emit_json_tags: true
```

```sql
-- db/queries/orders.sql
-- name: GetOrder :one
SELECT id, customer_id, total_cents, created_at
FROM orders
WHERE id = $1;

-- name: CreateOrder :one
INSERT INTO orders (customer_id, total_cents)
VALUES ($1, $2)
RETURNING id, customer_id, total_cents, created_at;

-- name: AddOrderLine :exec
INSERT INTO order_lines (order_id, product_id, quantity, unit_cents)
VALUES ($1, $2, $3, $4);
```

`sqlc generate` produce `db.Queries` con `GetOrder(ctx, id)`, `CreateOrder(ctx, CreateOrderParams{...})`, etc. Un servicio con transacción:

```go
package orders

import (
	"context"
	"errors"
	"fmt"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgxpool"

	"example.com/api/internal/db"
)

var ErrNotFound = errors.New("order not found")

type Service struct {
	pool *pgxpool.Pool
	q    *db.Queries
}

func NewService(pool *pgxpool.Pool) *Service {
	return &Service{pool: pool, q: db.New(pool)}
}

func (s *Service) Get(ctx context.Context, id int64) (db.Order, error) {
	order, err := s.q.GetOrder(ctx, id)
	if errors.Is(err, pgx.ErrNoRows) {
		return db.Order{}, ErrNotFound
	}
	return order, err
}

func (s *Service) Create(ctx context.Context, customerID int64, lines []Line) (db.Order, error) {
	tx, err := s.pool.Begin(ctx)
	if err != nil {
		return db.Order{}, fmt.Errorf("iniciando transacción: %w", err)
	}
	defer tx.Rollback(ctx) // tras Commit devuelve ErrTxClosed; es inofensivo y cubre todos los returns de error

	q := s.q.WithTx(tx)
	var total int64
	for _, l := range lines {
		total += int64(l.Quantity) * l.UnitCents
	}
	order, err := q.CreateOrder(ctx, db.CreateOrderParams{CustomerID: customerID, TotalCents: total})
	if err != nil {
		var pgErr *pgconn.PgError
		if errors.As(err, &pgErr) && pgErr.Code == "23503" { // foreign_key_violation
			return db.Order{}, fmt.Errorf("cliente %d no existe: %w", customerID, ErrInvalidCustomer)
		}
		return db.Order{}, fmt.Errorf("creando pedido: %w", err)
	}
	for _, l := range lines {
		if err := q.AddOrderLine(ctx, db.AddOrderLineParams{OrderID: order.ID, ProductID: l.ProductID, Quantity: l.Quantity, UnitCents: l.UnitCents}); err != nil {
			return db.Order{}, fmt.Errorf("añadiendo línea: %w", err)
		}
	}
	if err := tx.Commit(ctx); err != nil {
		return db.Order{}, fmt.Errorf("confirmando: %w", err)
	}
	return order, nil
}
```

El pool, una vez en `main`:

```go
cfg, err := pgxpool.ParseConfig(os.Getenv("DATABASE_URL"))
cfg.MaxConns = 20
cfg.MaxConnLifetime = time.Hour
pool, err := pgxpool.NewWithConfig(ctx, cfg)
defer pool.Close()
if err := pool.Ping(ctx); err != nil { /* fallar al arrancar, no en la primera petición */ }
```

Por qué esta combinación frente a las otras:

| | Ventaja | Coste |
|---|---|---|
| `database/sql` + `lib/pq` | estándar, portable | `lib/pq` está en mantenimiento; `Scan` a mano; sin tipos de Postgres nativos |
| pgx directo | el más rápido; tipos de Postgres (arrays, jsonb, timestamptz) sin conversiones | `Scan` a mano para cada consulta |
| pgx + sqlc | SQL explícito, tipos generados, errores de esquema en `sqlc generate` | regenerar al cambiar consultas; SQL dinámico (filtros opcionales) es incómodo |
| GORM | productivo para CRUD, migraciones automáticas | el SQL generado es opaco; N+1 fácil; `Preload` y hooks esconden coste |

Para el equipo que viene de Hibernate: sqlc es el cambio de mentalidad que les va a sentar mejor, porque en Go el ORM «mágico» no tiene el soporte del lenguaje (sin anotaciones ni proxies) y acaba siendo más código raro que el SQL que esconde.

Comprobación: `sqlc generate && go vet ./...`; luego renombra `total_cents` en la migración y vuelve a generar: sqlc debe fallar con «column "total_cents" does not exist» antes de que compile nada.""",
            },
            {
                "role": "user",
                "content": "Parte del equipo insiste en GORM porque «es lo más parecido a Hibernate». Si al final lo usamos, ¿qué tenemos que vigilar?",
            },
            {
                "role": "assistant",
                "content": r"""Si la decisión es GORM, se puede hacer bien; lo que hay que vigilar es lo que Hibernate también tenía y en Go duele más porque hay menos herramientas que lo detecten.

**1. N+1 con relaciones.** Recorrer pedidos y tocar `order.Customer` dispara una consulta por pedido. `Preload` carga la relación en una segunda consulta con `IN`; `Joins` la mete en un `JOIN`.

```go
var orders []Order
err := db.WithContext(ctx).
	Preload("Lines.Product").   // 2 consultas extra, no 2 × N
	Joins("Customer").          // 1 JOIN para belongs-to
	Where("created_at > ?", since).
	Find(&orders).Error
```

Activa `Logger: logger.Default.LogMode(logger.Info)` en desarrollo y cuenta consultas en un test: si una lista de 50 pedidos hace más de 3, hay un N+1.

**2. `AutoMigrate` en producción.** Es cómodo en local y peligroso en producción: solo añade columnas e índices, nunca los borra, no renombra, y lo hace sin revisión. Usa migraciones versionadas (`golang-migrate`, `goose`, o Atlas) y deja `AutoMigrate` solo para tests.

**3. Errores que no son errores.** `First` devuelve `gorm.ErrRecordNotFound` cuando no hay fila, pero `Find` devuelve `nil` y un slice vacío. Y `Updates(map/struct)` con un struct **ignora los campos con valor cero** (`false`, `0`, `""`): para poner `Active = false` hay que usar `Select("Active").Updates(...)` o un mapa. Este es el bug de GORM más repetido en producción.

```go
// no desactiva a nadie: Active=false es valor cero y se omite
db.Model(&user).Updates(User{Active: false})

// sí
db.Model(&user).Select("active").Updates(map[string]any{"active": false})
```

**4. Siempre `WithContext(ctx)`**: sin él, la consulta no se cancela cuando el cliente se va ni respeta el timeout de la petición.

**5. Transacciones con `db.Transaction(func(tx *gorm.DB) error { ... })`**, usando `tx` dentro, no `db`. Mezclarlos ejecuta parte fuera de la transacción sin ningún aviso.

**6. Rendimiento**: `Find` en una tabla grande sin `Limit` carga todo en memoria; para procesar en lotes, `FindInBatches`. Y `PrepareStmt: true` en la config para que reutilice sentencias preparadas.

Lo que yo haría como término medio: GORM para el CRUD simple y las relaciones, y para las 5 consultas complejas de informes, SQL con `db.Raw(...).Scan(&result)` o directamente sqlc sobre el mismo pool (`db.DB()` devuelve el `*sql.DB` subyacente). No es incoherente: es usar cada herramienta donde rinde.

Comprobación que vale la pena dejar en CI: un test con `gorm.Config{Logger: ...}` que capture las sentencias y falle si el endpoint de listado de pedidos ejecuta más de 3 consultas para 50 pedidos; y otro que actualice `Active` a `false` y lo relea.""",
            },
        ]
    },
    # 9) JWT con golang-jwt/jwt/v5 y usuario en contexto.
    {
        "messages": [
            {
                "role": "user",
                "content": "Necesito autenticación JWT en net/http: un middleware que valide el Bearer y deje el usuario disponible para los handlers, y el endpoint que emite el token. Con `golang-jwt/jwt/v5`.",
            },
            {
                "role": "assistant",
                "content": r"""Tres piezas: *claims* propios que embeben `jwt.RegisteredClaims`, un emisor, y el middleware que valida y guarda el usuario en el contexto con una clave privada.

```go
package auth

import (
	"context"
	"errors"
	"net/http"
	"strings"
	"time"

	"github.com/golang-jwt/jwt/v5"
)

type Claims struct {
	UserID string `json:"uid"`
	Role   string `json:"role"`
	jwt.RegisteredClaims
}

type User struct {
	ID   string
	Role string
}

type Issuer struct {
	secret []byte
	ttl    time.Duration
	issuer string
}

func NewIssuer(secret []byte, ttl time.Duration) *Issuer {
	return &Issuer{secret: secret, ttl: ttl, issuer: "api.example.com"}
}

func (i *Issuer) Issue(userID, role string) (string, error) {
	now := time.Now()
	claims := Claims{
		UserID: userID,
		Role:   role,
		RegisteredClaims: jwt.RegisteredClaims{
			Issuer:    i.issuer,
			Subject:   userID,
			IssuedAt:  jwt.NewNumericDate(now),
			ExpiresAt: jwt.NewNumericDate(now.Add(i.ttl)),
		},
	}
	return jwt.NewWithClaims(jwt.SigningMethodHS256, claims).SignedString(i.secret)
}

func (i *Issuer) Parse(tokenString string) (*Claims, error) {
	token, err := jwt.ParseWithClaims(tokenString, &Claims{},
		func(t *jwt.Token) (any, error) { return i.secret, nil },
		jwt.WithValidMethods([]string{jwt.SigningMethodHS256.Alg()}), // rechaza "none" y RS256 aunque la cabecera lo pida
		jwt.WithIssuer(i.issuer),
		jwt.WithExpirationRequired(),
		jwt.WithLeeway(30*time.Second),
	)
	if err != nil {
		return nil, err
	}
	claims, ok := token.Claims.(*Claims)
	if !ok || !token.Valid {
		return nil, jwt.ErrTokenInvalidClaims
	}
	return claims, nil
}

type ctxKey struct{}

func WithUser(ctx context.Context, u User) context.Context { return context.WithValue(ctx, ctxKey{}, u) }

func UserFrom(ctx context.Context) (User, bool) {
	u, ok := ctx.Value(ctxKey{}).(User)
	return u, ok
}

func Middleware(issuer *Issuer, logger *slog.Logger) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			raw, ok := strings.CutPrefix(r.Header.Get("Authorization"), "Bearer ")
			if !ok || raw == "" {
				w.Header().Set("WWW-Authenticate", `Bearer realm="api"`)
				httpx.Error(w, http.StatusUnauthorized, "missing bearer token")
				return
			}
			claims, err := issuer.Parse(raw)
			if err != nil {
				// el motivo (caducado, firma, emisor) va al log en debug; al cliente, 401 sin detalle
				logger.DebugContext(r.Context(), "jwt rechazado", "err", err)
				if errors.Is(err, jwt.ErrTokenExpired) {
					w.Header().Set("WWW-Authenticate", `Bearer realm="api", error="invalid_token", error_description="expired"`)
				}
				httpx.Error(w, http.StatusUnauthorized, "invalid token")
				return
			}
			next.ServeHTTP(w, r.WithContext(WithUser(r.Context(), User{ID: claims.UserID, Role: claims.Role})))
		})
	}
}
```

El endpoint de login y el uso en rutas, con el mux 1.22:

```go
func (h *Handler) Login(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Email    string `json:"email"`
		Password string `json:"password"`
	}
	if err := httpx.DecodeJSON(w, r, &req); err != nil { /* 400 */ return }

	user, err := h.users.Authenticate(r.Context(), req.Email, req.Password) // bcrypt dentro
	if err != nil {
		httpx.Error(w, http.StatusUnauthorized, "invalid credentials") // mismo mensaje si no existe o si la clave falla
		return
	}
	token, err := h.issuer.Issue(user.ID, user.Role)
	if err != nil { /* 500 */ return }
	httpx.JSON(w, http.StatusOK, map[string]any{"access_token": token, "token_type": "Bearer", "expires_in": int(h.issuer.ttl.Seconds())})
}

// rutas
mux.HandleFunc("POST /login", h.Login)
protected := auth.Middleware(issuer, logger)
mux.Handle("GET /me", protected(http.HandlerFunc(h.Me)))
mux.Handle("GET /orders", protected(http.HandlerFunc(orders.List)))
```

Decisiones:

- **`WithValidMethods`** es obligatorio: sin él, el *keyfunc* devuelve el secreto para cualquier algoritmo que diga la cabecera; es el ataque de confusión de algoritmo. Si en algún momento pasas a claves asimétricas (varios servicios validando), el *keyfunc* devuelve la pública y `WithValidMethods` pasa a `RS256`/`EdDSA`.
- **El secreto con al menos 32 bytes aleatorios** (`openssl rand -base64 32`), por variable de entorno; un secreto corto convierte HS256 en fuerza bruta offline.
- **TTL corto (15 min) + refresh token** guardado en base de datos si necesitas revocar; un JWT no se puede invalidar antes de que caduque salvo con una lista negra.
- **`strings.CutPrefix`** (Go 1.20) distingue «sin cabecera» de «cabecera mal formada» sin un `strings.HasPrefix` + `TrimPrefix` dobles.

Test de regresión, sin red:

```go
func TestMiddlewareRejectsExpired(t *testing.T) {
	issuer := auth.NewIssuer([]byte("test-secret-of-32-bytes-minimum!"), -time.Minute) // ya caducado
	token, _ := issuer.Issue("u1", "user")
	h := auth.Middleware(issuer, slog.New(slog.DiscardHandler))(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(200) }))
	req := httptest.NewRequest("GET", "/me", nil)
	req.Header.Set("Authorization", "Bearer "+token)
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	if rec.Code != http.StatusUnauthorized {
		t.Fatalf("status = %d", rec.Code)
	}
}
```

Con `ttl: -time.Minute` el `leeway` de 30 s no alcanza y el token se rechaza; con `-10 * time.Second` pasaría, que es justo la tolerancia de reloj que quieres.""",
            },
        ]
    },
    # 10) slog en un servicio: handler por entorno, logger por petición, configuración por env.
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Cómo configuran bien `slog` en un servicio? Quiero JSON en producción y algo legible en local, que cada línea lleve el request id sin pasarlo a mano, y leer la configuración (puerto, nivel de log, DSN) de variables de entorno sin un `os.Getenv` en cada sitio.",
            },
            {
                "role": "assistant",
                "content": r"""Tres piezas pequeñas: un `Config` tipado que se carga una vez, un `slog.Handler` elegido por entorno, y un logger por petición guardado en el contexto.

**1. Configuración tipada.** Un struct con tags, validado al arrancar; con `github.com/caarlos0/env/v11` son diez líneas y los errores dicen qué variable falta.

```go
package config

import (
	"fmt"
	"log/slog"
	"time"

	"github.com/caarlos0/env/v11"
)

type Config struct {
	Env         string        `env:"APP_ENV" envDefault:"development"`
	Port        int           `env:"PORT" envDefault:"8080"`
	LogLevel    slog.Level    `env:"LOG_LEVEL" envDefault:"info"` // slog.Level implementa encoding.TextUnmarshaler: "debug", "warn" funcionan
	DatabaseURL string        `env:"DATABASE_URL,required"`
	HTTPTimeout time.Duration `env:"HTTP_TIMEOUT" envDefault:"10s"`
}

func Load() (Config, error) {
	cfg, err := env.ParseAs[Config]()
	if err != nil {
		return Config{}, fmt.Errorf("configuración: %w", err) // p. ej. "required environment variable "DATABASE_URL" is not set"
	}
	if cfg.Env != "development" && cfg.Env != "production" {
		return Config{}, fmt.Errorf("APP_ENV=%q: debe ser development o production", cfg.Env)
	}
	return cfg, nil
}
```

Si prefieres cero dependencias, el mismo struct con `os.LookupEnv` + `strconv` cabe en 30 líneas; lo importante es que **solo `config.Load` lee el entorno**.

**2. El handler según entorno**, y `slog.SetDefault` para que las librerías que usan `log` o `slog` sin logger inyectado escriban en el mismo formato:

```go
func NewLogger(cfg config.Config) *slog.Logger {
	opts := &slog.HandlerOptions{Level: cfg.LogLevel, AddSource: cfg.Env == "development"}
	var h slog.Handler
	if cfg.Env == "production" {
		h = slog.NewJSONHandler(os.Stdout, opts)
	} else {
		h = slog.NewTextHandler(os.Stdout, opts) // legible; para colores, tint o devslog como dependencia solo de dev
	}
	logger := slog.New(h).With("service", "orders-api", "version", buildVersion())
	slog.SetDefault(logger)
	return logger
}
```

**3. Logger por petición en el contexto.** Un middleware crea `logger.With("request_id", id)` y lo guarda; los handlers lo recuperan con una función y nunca pasan el id a mano.

```go
package logging

type ctxKey struct{}

func WithLogger(ctx context.Context, l *slog.Logger) context.Context {
	return context.WithValue(ctx, ctxKey{}, l)
}

// From devuelve el logger de la petición o el global: nunca nil, nunca un if en el handler.
func From(ctx context.Context) *slog.Logger {
	if l, ok := ctx.Value(ctxKey{}).(*slog.Logger); ok {
		return l
	}
	return slog.Default()
}

func Middleware(base *slog.Logger) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			reqLogger := base.With(
				"request_id", middleware.RequestIDFrom(r.Context()),
				"method", r.Method,
				"path", r.URL.Path,
			)
			next.ServeHTTP(w, r.WithContext(WithLogger(r.Context(), reqLogger)))
		})
	}
}
```

En un handler:

```go
func (h *Handler) Create(w http.ResponseWriter, r *http.Request) {
	log := logging.From(r.Context())
	log.Info("creando pedido", "customer_id", req.CustomerID, "lines", len(req.Lines))
	// cualquier función más abajo que reciba ctx puede hacer logging.From(ctx) y hereda request_id
}
```

Detalles que marcan la diferencia:

- **Datos sensibles**: implementa `slog.LogValuer` en los tipos con secretos para que `"user", u` nunca imprima la contraseña o el token:

```go
func (u User) LogValue() slog.Value {
	return slog.GroupValue(slog.String("id", u.ID), slog.String("role", u.Role))
}
```

- **`ReplaceAttr`** en `HandlerOptions` para renombrar `msg`→`message` o `time`→`timestamp` si tu agregador (Datadog, Loki) lo espera así; es mejor que un handler propio.
- **`log.Info("x", "k", v)` con número impar de argumentos** produce `!BADKEY`; `go vet` lo detecta desde Go 1.21 con el analizador `slog`, así que mantén `go vet` en CI.
- **El `Level` es dinámico** si usas `slog.LevelVar`: `var level slog.LevelVar; opts.Level = &level` y un endpoint de administración que llame a `level.Set(slog.LevelDebug)` te deja subir el detalle en producción sin reiniciar.

Comprobación: `APP_ENV=production LOG_LEVEL=warn DATABASE_URL=postgres://x go run ./cmd/api` debe imprimir solo JSON y nada de nivel `info`; sin `DATABASE_URL` debe terminar al instante con el mensaje de la variable que falta; y una petición con `X-Request-ID: abc` debe producir líneas con `"request_id":"abc"` desde el handler y desde el servicio, sin que ninguno lo haya recibido como parámetro.""",
            },
        ]
    },
    # ---------------------------------------------------------------- chi (6)
    # 11) ¿Sigue haciendo falta chi con el mux de Go 1.22? (system exacto).
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Con el ServeMux de Go 1.22 que ya enruta por método, ¿sigue teniendo sentido chi? Tenemos varios servicios con chi v5 y alguien propone quitarlo «para reducir dependencias».",
            },
            {
                "role": "assistant",
                "content": r"""Depende de cuánto uséis de chi más allá de `Get`/`Post`. El mux de 1.22 cubre el enrutado básico (métodos, `{id}`, comodines, 405 automático), pero chi sigue aportando cuatro cosas que con el mux hay que escribir a mano:

1. **Grupos con middlewares distintos** (`Route`, `Group`, `With`): «todo `/api` lleva JSON y rate limit; `/api/admin` además auth».
2. **Montar sub-routers** (`Mount`) definidos en otros paquetes, cada uno con sus middlewares.
3. **El paquete `middleware`** probado en producción: `RequestID`, `RealIP`, `Recoverer`, `Timeout`, `Compress`, `AllowContentType`, `Throttle`.
4. **`chi.Walk`** para listar las rutas (documentación, tests de cobertura de rutas).

Así se ve un servicio que usa esas cuatro cosas; si el vuestro se parece, quitar chi es reescribir esto sin ganar nada:

```go
package server

import (
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
)

func New(deps Deps) http.Handler {
	r := chi.NewRouter()

	// globales, en orden de ejecución
	r.Use(middleware.RequestID)
	r.Use(middleware.RealIP) // X-Forwarded-For / X-Real-IP: solo detrás de un proxy de confianza
	r.Use(middleware.Recoverer)
	r.Use(middleware.Timeout(15 * time.Second))

	r.Get("/healthz", func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(http.StatusNoContent) })

	r.Route("/api/v1", func(r chi.Router) {
		r.Use(middleware.AllowContentType("application/json"))
		r.Use(deps.Logger)

		r.Mount("/users", users.Router(deps.Users))   // un chi.Router definido en el paquete users
		r.Mount("/orders", orders.Router(deps.Orders))

		r.Group(func(r chi.Router) {
			r.Use(deps.RequireAdmin)                   // solo este grupo
			r.Mount("/admin", admin.Router(deps.Admin))
		})
	})

	r.NotFound(func(w http.ResponseWriter, r *http.Request) { httpx.Error(w, http.StatusNotFound, "route not found") })
	r.MethodNotAllowed(func(w http.ResponseWriter, r *http.Request) { httpx.Error(w, http.StatusMethodNotAllowed, "method not allowed") })
	return r
}
```

```go
package users

func Router(h *Handler) chi.Router {
	r := chi.NewRouter()
	r.Get("/", h.List)
	r.Post("/", h.Create)
	r.Route("/{id}", func(r chi.Router) {
		r.Use(h.LoadUser)      // carga el usuario una vez para Get, Update y Delete
		r.Get("/", h.Get)
		r.Put("/", h.Update)
		r.Delete("/", h.Delete)
	})
	return r
}
```

Lo que chi **no** aporta ya frente al mux de 1.22: velocidad (son equivalentes), captura de parámetros (`chi.URLParam(r, "id")` frente a `r.PathValue("id")`), y 405. Y chi es 100 % compatible con `net/http`: sus middlewares son `func(http.Handler) http.Handler`, así que nada de lo que escribáis para chi se pierde si un día migráis.

Criterio para decidir servicio por servicio: haz `chi.Walk` y mira cuántos middlewares distintos hay por grupo.

```go
chi.Walk(r, func(method, route string, h http.Handler, mws ...func(http.Handler) http.Handler) error {
	fmt.Printf("%-6s %-30s %d middlewares\n", method, route, len(mws))
	return nil
})
```

Si todas las rutas llevan los mismos middlewares y no hay `Mount`, el mux de 1.22 con una función `Chain` os basta y la dependencia sobra. Si hay tres o más grupos distintos, chi se está ganando el sitio.

Una dependencia pequeña, sin dependencias transitivas (chi solo importa la biblioteca estándar) y con API estable desde 2019 no es la que hay que recortar; mirad primero `go mod graph | wc -l` y buscad las que arrastran veinte módulos.""",
            },
        ]
    },
    # 12) chi + cors + httprate (system variante: solo código).
    {
        "messages": [
            {"role": "system", "content": "Responde solo con código y comentarios breves."},
            {
                "role": "user",
                "content": "chi v5: CORS para un SPA en otro dominio con cookies, rate limit por IP global de 100/min y de 5/min solo en POST /login, y que las respuestas de límite sean JSON.",
            },
            {
                "role": "assistant",
                "content": r"""```go
package server

import (
	"encoding/json"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
	"github.com/go-chi/cors"
	"github.com/go-chi/httprate"
)

func New(deps Deps) http.Handler {
	r := chi.NewRouter()

	r.Use(middleware.RequestID)
	r.Use(middleware.RealIP) // necesario para que el rate limit por IP vea la IP real detrás del proxy
	r.Use(middleware.Recoverer)

	// CORS antes de cualquier middleware que pueda rechazar la petición:
	// el preflight OPTIONS no lleva cookies ni Authorization y debe responder 204 igualmente.
	r.Use(cors.Handler(cors.Options{
		AllowedOrigins:   []string{"https://app.example.com"}, // con AllowCredentials no se admite "*"
		AllowedMethods:   []string{http.MethodGet, http.MethodPost, http.MethodPut, http.MethodDelete, http.MethodOptions},
		AllowedHeaders:   []string{"Accept", "Authorization", "Content-Type", "X-Request-ID"},
		ExposedHeaders:   []string{"X-Request-ID"},
		AllowCredentials: true, // cookies: el SPA usa fetch(..., { credentials: "include" })
		MaxAge:           300,  // segundos de caché del preflight
	}))

	// límite global: 100 peticiones por minuto por IP
	r.Use(httprate.Limit(
		100, time.Minute,
		httprate.WithKeyFuncs(httprate.KeyByIP),
		httprate.WithLimitHandler(rateLimited),
	))

	r.Post("/login", deps.Auth.Login)

	// límite estricto solo en /login: 5 por minuto por IP, sin afectar al resto
	r.With(httprate.Limit(
		5, time.Minute,
		httprate.WithKeyFuncs(httprate.KeyByIP, httprate.KeyByEndpoint),
		httprate.WithLimitHandler(rateLimited),
	)).Post("/login", deps.Auth.Login)

	r.Route("/api", func(r chi.Router) {
		r.Use(deps.RequireSession)
		r.Get("/me", deps.Users.Me)
	})
	return r
}

// rateLimited: respuesta JSON; httprate ya ha puesto X-RateLimit-* y Retry-After
func rateLimited(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusTooManyRequests)
	json.NewEncoder(w).Encode(map[string]string{
		"error":       "rate limited",
		"retry_after": w.Header().Get("Retry-After"),
	})
}
```

```go
// Comprobación: el límite de /login salta al 6.º intento y el global no
func TestLoginRateLimit(t *testing.T) {
	h := server.New(testDeps())
	for i := 1; i <= 6; i++ {
		req := httptest.NewRequest(http.MethodPost, "/login", strings.NewReader(`{}`))
		req.RemoteAddr = "203.0.113.7:1234"
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, req)
		if i <= 5 && rec.Code == http.StatusTooManyRequests {
			t.Fatalf("intento %d limitado antes de tiempo", i)
		}
		if i == 6 && rec.Code != http.StatusTooManyRequests {
			t.Fatalf("intento 6: status %d, quería 429", rec.Code)
		}
	}
	// preflight: sin cookies, debe pasar
	req := httptest.NewRequest(http.MethodOptions, "/api/me", nil)
	req.Header.Set("Origin", "https://app.example.com")
	req.Header.Set("Access-Control-Request-Method", "GET")
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	if rec.Header().Get("Access-Control-Allow-Origin") != "https://app.example.com" {
		t.Fatalf("preflight sin Allow-Origin: %v", rec.Header())
	}
}
```

```go
// Nota: la segunda r.Post("/login") sustituye a la primera en chi (misma ruta y método);
// deja solo la versión con r.With(...). Está duplicada arriba para mostrar las dos formas.
```""",
            },
        ]
    },
    # 13) chi.URLParam vacío en un test unitario (usuario trae test que falla).
    {
        "messages": [
            {
                "role": "user",
                "content": """Este test falla y no entiendo por qué, el handler funciona en producción:

```go
func TestGetUser(t *testing.T) {
	h := users.NewHandler(fakeStore())
	req := httptest.NewRequest(http.MethodGet, "/users/42", nil)
	rec := httptest.NewRecorder()
	h.Get(rec, req)
	if rec.Code != 200 {
		t.Fatalf("status %d: %s", rec.Code, rec.Body)
	}
}
```

```
--- FAIL: TestGetUser (0.00s)
    users_test.go:18: status 404: {"error":"user not found"}
```

El handler hace `id := chi.URLParam(r, "id")`.""",
            },
            {
                "role": "assistant",
                "content": r"""`chi.URLParam` lee los parámetros del **contexto de ruta** que chi mete en `r.Context()` cuando la petición pasa por el router. Tu test llama a `h.Get` directamente: no hay router, no hay contexto de ruta, `URLParam` devuelve `""`, el store no encuentra `""` y responde 404. En producción funciona porque la petición entra por `r.Get("/users/{id}", h.Get)`.

Dos arreglos, y recomiendo el primero.

**1. Probar a través del router.** Es lo que de verdad ejecuta producción y cubre también el patrón de la ruta:

```go
func TestGetUser(t *testing.T) {
	r := chi.NewRouter()
	r.Mount("/users", users.Router(users.NewHandler(fakeStore()))) // el mismo Router() que usa main

	req := httptest.NewRequest(http.MethodGet, "/users/42", nil)
	rec := httptest.NewRecorder()
	r.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Fatalf("status %d: %s", rec.Code, rec.Body)
	}
}
```

Si `users.Router` no existe aún (las rutas están en `main`), este test es la excusa para extraerlas a una función: es el cambio que hace testable el enrutado.

**2. Inyectar el contexto de ruta a mano**, para un test unitario del handler aislado:

```go
func withURLParams(r *http.Request, params map[string]string) *http.Request {
	rctx := chi.NewRouteContext()
	for k, v := range params {
		rctx.URLParams.Add(k, v)
	}
	return r.WithContext(context.WithValue(r.Context(), chi.RouteCtxKey, rctx))
}

func TestGetUser(t *testing.T) {
	h := users.NewHandler(fakeStore())
	req := withURLParams(httptest.NewRequest(http.MethodGet, "/users/42", nil), map[string]string{"id": "42"})
	rec := httptest.NewRecorder()
	h.Get(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("status %d: %s", rec.Code, rec.Body)
	}
}
```

Vale cuando quieres probar muchas combinaciones de un handler sin construir el router, pero tiene un coste: si alguien renombra el parámetro en la ruta (`{userID}`) y no en el handler, este test sigue en verde y producción rompe. El de la opción 1 lo detecta.

Hay una tercera opción que evita el problema de raíz: que el handler no sepa de chi. Un *wrapper* de ruta lee el parámetro y lo pasa como argumento:

```go
r.Get("/{id}", func(w http.ResponseWriter, r *http.Request) {
	h.Get(w, r, chi.URLParam(r, "id"))
})
```

Con eso `h.Get(rec, req, "42")` se prueba sin contexto y sin router, y el handler es igual de válido con el mux de 1.22 (`r.PathValue("id")`). Es el diseño que usaría en código nuevo; en el existente, la opción 1 es el cambio más pequeño.

Comprobación: con la opción 1, cambia el patrón a `/{uid}` sin tocar el handler; el test debe fallar con 404, que es el fallo que quieres atrapar.""",
            },
        ]
    },
    # 14) Inglés: handlers que devuelven error con chi.
    {
        "messages": [
            {
                "role": "user",
                "content": "My chi handlers all have the same 10 lines of `if err != nil { log; writeJSON(500) ; return }`. Is there a clean pattern in Go to have handlers return an error and map it centrally, like Express's error middleware?",
            },
            {
                "role": "assistant",
                "content": r"""Yes: make your handler type `func(w http.ResponseWriter, r *http.Request) error` and adapt it to `http.Handler` once. The adapter is where errors become status codes, and chi takes the adapter because it is a plain `http.Handler`.

```go
package httpx

import (
	"errors"
	"log/slog"
	"net/http"
)

// HandlerFunc is an http.HandlerFunc that can fail.
type HandlerFunc func(w http.ResponseWriter, r *http.Request) error

// Error carries an HTTP status and a client-safe message; wrap the cause for logs.
type Error struct {
	Status int
	Msg    string
	Err    error
}

func (e *Error) Error() string {
	if e.Err != nil {
		return e.Msg + ": " + e.Err.Error()
	}
	return e.Msg
}
func (e *Error) Unwrap() error { return e.Err }

func NotFound(msg string) error        { return &Error{Status: http.StatusNotFound, Msg: msg} }
func BadRequest(msg string, err error) error { return &Error{Status: http.StatusBadRequest, Msg: msg, Err: err} }

// ServeHTTP makes HandlerFunc an http.Handler; this is the single place that maps errors.
func (h HandlerFunc) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	err := h(w, r)
	if err == nil {
		return
	}
	log := logging.From(r.Context())

	var apiErr *Error
	switch {
	case errors.As(err, &apiErr):
		if apiErr.Status >= 500 {
			log.Error("handler failed", "err", err, "status", apiErr.Status)
		} else {
			log.Debug("client error", "err", err, "status", apiErr.Status)
		}
		JSON(w, apiErr.Status, map[string]string{"error": apiErr.Msg})
	case errors.Is(err, context.Canceled):
		// client went away; nothing to write
	default:
		log.Error("unhandled error", "err", err)
		JSON(w, http.StatusInternalServerError, map[string]string{"error": "internal error"})
	}
}
```

Handlers shrink to the happy path plus `return` of errors:

```go
func (h *Handler) Get(w http.ResponseWriter, r *http.Request) error {
	id := chi.URLParam(r, "id")
	user, err := h.store.Get(r.Context(), id)
	if errors.Is(err, users.ErrNotFound) {
		return httpx.NotFound("user not found")
	}
	if err != nil {
		return fmt.Errorf("getting user %s: %w", id, err) // becomes a logged 500
	}
	httpx.JSON(w, http.StatusOK, user)
	return nil
}

func (h *Handler) Create(w http.ResponseWriter, r *http.Request) error {
	var req CreateRequest
	if err := httpx.DecodeJSON(w, r, &req); err != nil {
		return err // DecodeJSON already returns *httpx.Error with 400/413/415
	}
	user, err := h.store.Create(r.Context(), req.ToUser())
	if err != nil {
		return fmt.Errorf("creating user: %w", err)
	}
	httpx.JSON(w, http.StatusCreated, user)
	return nil
}
```

Registration with chi, no extra plumbing because `HandlerFunc` is an `http.Handler`:

```go
r.Method(http.MethodGet, "/users/{id}", httpx.HandlerFunc(h.Get))
r.Method(http.MethodPost, "/users", httpx.HandlerFunc(h.Create))
```

(`r.Get` wants an `http.HandlerFunc`; `r.Method`/`r.Handle` take any `http.Handler`.)

Why this shape rather than the alternatives:

- **Domain errors stay domain errors.** The store returns `users.ErrNotFound`; only the handler decides it is a 404. The adapter never imports the domain packages, so it can live in a shared module.
- **5xx details never reach the client**, and a wrapped `fmt.Errorf("...: %w", err)` keeps the cause in the log with context about what was being attempted.
- **One known hazard**: if a handler writes a response *and* returns an error, the adapter writes a second response and net/http logs `superfluous response.WriteHeader`. Keep the rule «write or return, never both»; a wrapped `ResponseWriter` with a `written` flag can enforce it if the team is large.
- A `panic` is still a panic: keep `middleware.Recoverer` in the chain; this pattern replaces the `if err != nil` boilerplate, not the panic safety net.

Check: a store that returns `errors.New("boom")` must yield a 500 with body `{"error":"internal error"}` and a log line containing `boom`; a missing user must yield 404 with `{"error":"user not found"}` and no error-level log.""",
            },
        ]
    },
    # 15) middleware.Timeout de chi "no hace nada" y http.TimeoutHandler (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": "Puse `r.Use(middleware.Timeout(2 * time.Second))` en chi y un handler que tarda 10 segundos sigue tardando 10 segundos y responde 200. ¿Está roto el middleware?",
            },
            {
                "role": "assistant",
                "content": r"""No está roto: hace exactamente lo que dice su documentación, que es menos de lo que el nombre sugiere. `middleware.Timeout` **pone un plazo en el contexto** de la petición y, si el handler termina después del plazo, responde 504. No interrumpe al handler: en Go no se puede matar un goroutine desde fuera. Si tu handler no mira `r.Context()`, el plazo se ignora.

Así es su implementación, resumida:

```go
ctx, cancel := context.WithTimeout(r.Context(), timeout)
defer func() {
	cancel()
	if ctx.Err() == context.DeadlineExceeded {
		w.WriteHeader(http.StatusGatewayTimeout) // solo si el handler no escribió nada antes
	}
}()
next.ServeHTTP(w, r.WithContext(ctx))
```

Tu handler de 10 s terminó, escribió 200, y el `WriteHeader(504)` posterior no tuvo efecto (se queda en el log como «superfluous WriteHeader»).

**El arreglo es que el handler respete el contexto.** Casi siempre basta con pasarlo a lo que tarda:

```go
func (h *Handler) Report(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	rows, err := h.db.Query(ctx, slowReportSQL) // pgx aborta la consulta cuando el ctx vence
	if errors.Is(err, context.DeadlineExceeded) {
		httpx.Error(w, http.StatusGatewayTimeout, "report timed out")
		return
	}
	// ...
}
```

Con eso, a los 2 s pgx cancela la consulta en Postgres, `Query` devuelve `context.DeadlineExceeded` y respondes en 2 s, no en 10. Lo mismo con `http.NewRequestWithContext(ctx, ...)` para llamadas salientes y con `select { case <-ctx.Done(): ... }` en bucles de CPU.

Para encontrar los handlers que **no** lo respetan: un test por ruta con un contexto ya cancelado.

```go
func TestHandlersHonorContext(t *testing.T) {
	h := server.New(slowDeps()) // dependencias que tardan 1 s salvo que el ctx se cancele
	for _, route := range []string{"/report", "/orders", "/users/1"} {
		ctx, cancel := context.WithTimeout(context.Background(), 50*time.Millisecond)
		req := httptest.NewRequestWithContext(ctx, http.MethodGet, route, nil) // Go 1.23
		rec := httptest.NewRecorder()
		start := time.Now()
		h.ServeHTTP(rec, req)
		cancel()
		if time.Since(start) > 200*time.Millisecond {
			t.Errorf("%s ignora el contexto: tardó %v", route, time.Since(start))
		}
	}
}
```

Si algún handler hace trabajo que no puede recibir un contexto (una librería síncrona sin `ctx`), entonces sí necesitas la otra herramienta, `http.TimeoutHandler`; te lo explico si lo quieres, porque tiene trampas propias.""",
            },
            {
                "role": "user",
                "content": "Sí, tengo dos handlers que llaman a un SDK antiguo sin contexto. ¿`http.TimeoutHandler` para esos?",
            },
            {
                "role": "assistant",
                "content": r"""Sí, solo para esos dos, y sabiendo lo que compras. `http.TimeoutHandler` ejecuta el handler en otro goroutine, **bufferiza** su respuesta y, si vence el plazo, responde él mismo con 503 y descarta lo que el handler escriba después. El cliente recibe la respuesta a tiempo; el goroutine del SDK sigue corriendo hasta que termine.

```go
legacy := http.TimeoutHandler(http.HandlerFunc(h.LegacyExport), 5*time.Second, `{"error":"export timed out"}`)

r.Route("/legacy", func(r chi.Router) {
	r.Method(http.MethodGet, "/export", legacy)
	r.Method(http.MethodGet, "/sync", http.TimeoutHandler(http.HandlerFunc(h.LegacySync), 5*time.Second, `{"error":"sync timed out"}`))
})
```

Las trampas, para que no te sorprendan:

- **La respuesta se bufferiza entera en memoria** hasta que el handler termina. Un `export` de 200 MB se guarda en RAM antes de enviarse. Para respuestas grandes o streaming, no sirve.
- **`Flush` y `Hijack` no funcionan** a través de él: nada de SSE ni WebSockets en esas rutas.
- **El `Content-Type` del mensaje de timeout** es `text/html` por defecto; si tu API es JSON, pon la cabecera en el handler antes de que empiece el trabajo (`w.Header().Set("Content-Type", "application/json")`), porque `TimeoutHandler` conserva las cabeceras ya fijadas.
- **El trabajo no se cancela**: si el SDK tarda 60 s, el goroutine vive 60 s y consume lo que consuma. Con 100 peticiones en timeout tienes 100 goroutines y 100 llamadas al SDK en vuelo. Protege esas rutas con un límite de concurrencia (`middleware.Throttle(10)` de chi) para que el daño esté acotado.
- Si el handler entra en pánico, `TimeoutHandler` lo propaga al goroutine principal (desde Go 1.17), así que `Recoverer` sigue funcionando.

El criterio queda así: `middleware.Timeout` + handlers que respetan el contexto para todo lo tuyo; `http.TimeoutHandler` + `Throttle` como cuarentena para lo que no puedes arreglar, con un ticket para envolver ese SDK en una goroutine con `select` sobre `ctx.Done()` o sustituirlo.

Comprobación: con el SDK simulado por `time.Sleep(10 * time.Second)`, `curl -i localhost:8080/legacy/export` debe devolver 503 con tu JSON a los 5 s; y `curl localhost:6060/debug/pprof/goroutine?debug=1 | grep -c LegacyExport` debe mostrar el goroutine vivo hasta los 10 s y desaparecer después, nunca acumularse.""",
            },
        ]
    },
    # 16) Server struct con dependencias e inyección (vos).
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo un servicio con chi donde los handlers son funciones sueltas que usan variables globales (`var db *pgxpool.Pool`, `var logger`). Para testear tengo que inicializar todo. ¿Cómo lo reestructurás vos para que sea inyectable sin meter un framework de DI?",
            },
            {
                "role": "assistant",
                "content": r"""Con un `struct` `Server` que tiene las dependencias como campos **de tipo interfaz**, un constructor que registra las rutas, y nada global. Es todo lo que hace falta; un contenedor de DI en Go suele ser más problema que solución.

```go
package server

import (
	"context"
	"log/slog"
	"net/http"

	"github.com/go-chi/chi/v5"
	"github.com/go-chi/chi/v5/middleware"
)

// Las interfaces las define quien las consume, con solo los métodos que usa.
type OrderStore interface {
	Get(ctx context.Context, id string) (Order, error)
	Create(ctx context.Context, o Order) (Order, error)
}

type Clock interface {
	Now() time.Time
}

type Server struct {
	router chi.Router
	logger *slog.Logger
	orders OrderStore
	clock  Clock
}

func New(logger *slog.Logger, orders OrderStore, clock Clock) *Server {
	s := &Server{
		router: chi.NewRouter(),
		logger: logger,
		orders: orders,
		clock:  clock,
	}
	s.routes()
	return s
}

// ServeHTTP hace que *Server sea un http.Handler: lo usa main y lo usan los tests.
func (s *Server) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	s.router.ServeHTTP(w, r)
}

func (s *Server) routes() {
	s.router.Use(middleware.RequestID, middleware.Recoverer)
	s.router.Get("/healthz", s.handleHealth)
	s.router.Route("/orders", func(r chi.Router) {
		r.Get("/{id}", s.handleGetOrder)
		r.Post("/", s.handleCreateOrder)
	})
}

func (s *Server) handleGetOrder(w http.ResponseWriter, r *http.Request) {
	order, err := s.orders.Get(r.Context(), chi.URLParam(r, "id"))
	if errors.Is(err, ErrNotFound) {
		httpx.Error(w, http.StatusNotFound, "order not found")
		return
	}
	if err != nil {
		s.logger.ErrorContext(r.Context(), "obteniendo pedido", "err", err)
		httpx.Error(w, http.StatusInternalServerError, "internal error")
		return
	}
	httpx.JSON(w, http.StatusOK, order)
}
```

`main` conecta las implementaciones reales:

```go
pool, _ := pgxpool.New(ctx, cfg.DatabaseURL)
srv := server.New(logger, postgres.NewOrderStore(pool), clock.System{})
http.ListenAndServe(":8080", srv) // o el http.Server con timeouts y Shutdown
```

Y el test conecta las falsas, sin base de datos y con un reloj fijo:

```go
type fakeOrders struct{ orders map[string]server.Order }

func (f *fakeOrders) Get(_ context.Context, id string) (server.Order, error) {
	o, ok := f.orders[id]
	if !ok {
		return server.Order{}, server.ErrNotFound
	}
	return o, nil
}
func (f *fakeOrders) Create(_ context.Context, o server.Order) (server.Order, error) {
	f.orders[o.ID] = o
	return o, nil
}

type fixedClock struct{ t time.Time }

func (c fixedClock) Now() time.Time { return c.t }

func TestGetOrder(t *testing.T) {
	srv := server.New(
		slog.New(slog.DiscardHandler),
		&fakeOrders{orders: map[string]server.Order{"o-1": {ID: "o-1", TotalCents: 1500}}},
		fixedClock{t: time.Date(2025, 1, 2, 3, 4, 5, 0, time.UTC)},
	)
	req := httptest.NewRequest(http.MethodGet, "/orders/o-1", nil)
	rec := httptest.NewRecorder()
	srv.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("status %d: %s", rec.Code, rec.Body)
	}
}
```

Por qué cada decisión:

- **Interfaces definidas en el consumidor** (`server.OrderStore`), no en el paquete de Postgres. Así `server` no importa `pgx` y la interfaz tiene exactamente los dos métodos que usa; el fake son diez líneas.
- **`Clock` inyectado** parece exagerado hasta el primer test que depende de «hoy»: fechas de vencimiento, cupones, cortes mensuales. Cuesta dos líneas ahora y evita `time.Sleep` y tests que fallan a medianoche.
- **`routes()` separado del constructor** para que la tabla de rutas se lea de corrido y no se mezcle con la construcción.
- **Nada de `init()` ni globales**: el orden de inicialización es explícito en `main` y cada test construye su propio `Server`, así que `t.Parallel()` funciona sin estado compartido.

Para migrar lo que tenés: mové primero las globales a campos del `Server` (los handlers pasan a ser métodos, cambio mecánico), después reemplazá `*pgxpool.Pool` por la interfaz cuando escribas el primer test que lo necesite. No hace falta hacerlo todo en un PR.

Comprobación: `go test ./internal/server/... -race` debe correr en milisegundos y sin `DATABASE_URL`; y `go list -deps ./internal/server | grep pgx` debe devolver vacío.""",
            },
        ]
    },
    # ---------------------------------------------------------------- Gin (6)
    # 17) Gin: binding y validación con mensajes por campo (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": "En Gin uso `c.ShouldBindJSON(&req)` con tags `binding:\"required\"`, pero cuando falla devuelvo `err.Error()` y el frontend recibe cosas como `Key: 'CreateUser.Email' Error:Field validation for 'Email' failed on the 'email' tag`. ¿Cómo lo convierto en algo usable por campo?",
            },
            {
                "role": "assistant",
                "content": r"""Ese texto es el `Error()` de `validator.ValidationErrors`, que es una lista de errores por campo; recórrela y construye un mapa `campo → mensaje`. Dos ajustes más: que los nombres sean los del JSON (no los del struct) y que el 400 de sintaxis se distinga del 422 de validación.

```go
package httpx

import (
	"errors"
	"fmt"
	"net/http"
	"reflect"
	"strings"

	"github.com/gin-gonic/gin"
	"github.com/gin-gonic/gin/binding"
	"github.com/go-playground/validator/v10"
)

// RegisterJSONTagNames hace que fe.Field() devuelva el nombre del tag json ("email"), no "Email".
// Llamar una vez al arrancar.
func RegisterJSONTagNames() {
	v, ok := binding.Validator.Engine().(*validator.Validate)
	if !ok {
		return
	}
	v.RegisterTagNameFunc(func(fld reflect.StructField) string {
		name := strings.SplitN(fld.Tag.Get("json"), ",", 2)[0]
		if name == "-" {
			return ""
		}
		return name
	})
}

func messageFor(fe validator.FieldError) string {
	switch fe.Tag() {
	case "required":
		return "es obligatorio"
	case "email":
		return "debe ser un email válido"
	case "min":
		if fe.Kind() == reflect.String {
			return fmt.Sprintf("debe tener al menos %s caracteres", fe.Param())
		}
		return fmt.Sprintf("debe ser como mínimo %s", fe.Param())
	case "max":
		if fe.Kind() == reflect.String {
			return fmt.Sprintf("debe tener como máximo %s caracteres", fe.Param())
		}
		return fmt.Sprintf("debe ser como máximo %s", fe.Param())
	case "oneof":
		return "debe ser uno de: " + strings.ReplaceAll(fe.Param(), " ", ", ")
	default:
		return "no es válido (" + fe.Tag() + ")"
	}
}

// BindJSON vincula y, si falla, responde por su cuenta y devuelve false.
func BindJSON(c *gin.Context, dst any) bool {
	err := c.ShouldBindJSON(dst)
	if err == nil {
		return true
	}
	var ve validator.ValidationErrors
	if errors.As(err, &ve) {
		fields := make(map[string]string, len(ve))
		for _, fe := range ve {
			fields[fe.Field()] = messageFor(fe)
		}
		c.AbortWithStatusJSON(http.StatusUnprocessableEntity, gin.H{"error": "validation failed", "fields": fields})
		return false
	}
	// JSON malformado, tipo incorrecto, cuerpo vacío
	c.AbortWithStatusJSON(http.StatusBadRequest, gin.H{"error": "invalid JSON body"})
	return false
}
```

El modelo de entrada y el handler:

```go
type CreateUser struct {
	Email    string `json:"email" binding:"required,email"`
	Password string `json:"password" binding:"required,min=8,max=128"`
	Age      int    `json:"age" binding:"omitempty,min=18,max=120"`
	Plan     string `json:"plan" binding:"required,oneof=free pro"`
}

func (h *Handler) Create(c *gin.Context) {
	var req CreateUser
	if !httpx.BindJSON(c, &req) {
		return
	}
	user, err := h.users.Create(c.Request.Context(), req)
	if err != nil {
		_ = c.Error(err) // lo mapea el middleware de errores
		return
	}
	c.JSON(http.StatusCreated, user)
}
```

Respuesta ante `{"email":"x","password":"123","plan":"gold"}`:

```json
{
  "error": "validation failed",
  "fields": {
    "email": "debe ser un email válido",
    "password": "debe tener al menos 8 caracteres",
    "plan": "debe ser uno de: free, pro"
  }
}
```

Dos matices del `binding` de Gin:

- `required` falla con el **valor cero**: un `age: 0` o un `active: false` cuentan como ausentes. Para distinguir «no enviado» de «enviado con cero», usa punteros (`*int`) o `omitempty` como en `Age`.
- Para campos anidados o slices: `binding:"required,dive,required"` valida cada elemento; `fe.Field()` devolverá `lines[2].product_id` si hay fallo, lo que el frontend puede mapear al elemento.

Comprobación: un test de tabla con los tres cuerpos (válido → 201; el de arriba → 422 con esas tres claves y solo esas; `{` → 400).""",
            },
            {
                "role": "user",
                "content": "Necesito una regla propia: `currency` debe ser un código ISO 4217 de nuestra lista. ¿Cómo la registro en el validador de Gin?",
            },
            {
                "role": "assistant",
                "content": r"""Se registra en el mismo `*validator.Validate` que ya obtienes con `binding.Validator.Engine()`, una vez al arrancar, y se usa en el tag como cualquier otra regla.

```go
var supportedCurrencies = map[string]struct{}{"EUR": {}, "USD": {}, "MXN": {}, "COP": {}, "ARS": {}}

func RegisterCustomRules() error {
	v, ok := binding.Validator.Engine().(*validator.Validate)
	if !ok {
		return errors.New("el validador de gin no es *validator.Validate")
	}
	return v.RegisterValidation("currency", func(fl validator.FieldLevel) bool {
		code, ok := fl.Field().Interface().(string)
		if !ok {
			return false
		}
		_, supported := supportedCurrencies[code]
		return supported
	})
}
```

```go
type CreateOrder struct {
	Currency   string `json:"currency" binding:"required,currency"`
	TotalCents int64  `json:"total_cents" binding:"required,min=1"`
}
```

Y el mensaje, añadiendo un caso a `messageFor`:

```go
case "currency":
	return "moneda no soportada"
```

Tres detalles:

- **El orden de los tags importa**: `required,currency` evalúa `required` primero; si el campo falta, el error es «es obligatorio» y no se ejecuta tu función. Si pusieras `currency,required`, un campo vacío daría «moneda no soportada», que confunde.
- **`RegisterValidation` no es seguro para llamarlo concurrentemente** con validaciones en curso: hazlo en `main` antes de `r.Run`, no desde un handler ni en un `init()` de otro paquete que compita con el arranque.
- Si la lista de monedas viene de la base de datos y cambia, la función puede leer de un `atomic.Pointer[map[string]struct{}]` que recargues periódicamente; lo que no debe hacer es una consulta por validación.

Comprobación en un test, que además protege el orden de los tags:

```go
func TestCurrencyRule(t *testing.T) {
	gin.SetMode(gin.TestMode)
	if err := httpx.RegisterCustomRules(); err != nil {
		t.Fatal(err)
	}
	for body, want := range map[string]string{
		`{"currency":"EUR","total_cents":100}`: "",
		`{"currency":"XXX","total_cents":100}`: "moneda no soportada",
		`{"total_cents":100}`:                  "es obligatorio",
	} {
		rec := httptest.NewRecorder()
		c, _ := gin.CreateTestContext(rec)
		c.Request = httptest.NewRequest(http.MethodPost, "/orders", strings.NewReader(body))
		c.Request.Header.Set("Content-Type", "application/json")
		var req CreateOrder
		ok := httpx.BindJSON(c, &req)
		if want == "" && !ok {
			t.Errorf("%s: rechazado: %s", body, rec.Body)
		}
		if want != "" && !strings.Contains(rec.Body.String(), want) {
			t.Errorf("%s: quería %q, cuerpo %s", body, want, rec.Body)
		}
	}
}
```""",
            },
        ]
    },
    # 18) Revisión estricta: middleware de auth que no bloquea (usuario trae código, system variante).
    {
        "messages": [
            {"role": "system", "content": "Eres un revisor de código estricto. Señala problemas concretos antes de proponer código."},
            {
                "role": "user",
                "content": """Este middleware de Gin «funciona» pero vemos en los logs que peticiones sin token llegan igual al handler y devuelven datos. Revísalo:

```go
func Auth(secret []byte) gin.HandlerFunc {
	return func(c *gin.Context) {
		header := c.GetHeader("Authorization")
		if header == "" {
			c.JSON(401, gin.H{"error": "missing token"})
			return
		}
		token := strings.TrimPrefix(header, "Bearer ")
		claims, err := parseToken(token, secret)
		if err != nil {
			c.JSON(401, gin.H{"error": "invalid token"})
		}
		c.Set("user", claims.UserID)
		c.Next()
	}
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""Cuatro problemas, y los dos primeros explican lo que ves en los logs.

**1. `return` no detiene la cadena.** En Gin, cuando un middleware termina (con `return` o llegando al final), el motor llama al siguiente handler igualmente. `return` solo sale de tu función. Para cortar hay que llamar a `c.Abort()` (o `c.AbortWithStatusJSON`, que hace las dos cosas). Resultado actual: sin cabecera, escribes el 401 **y luego el handler se ejecuta**, intenta escribir su 200 con datos (Gin lo registra como «[WARNING] Headers were already written»), y el cuerpo de la respuesta mezcla ambos.

**2. Con token inválido ni siquiera hay `return`.** Tras el `c.JSON(401, ...)` el código sigue: `claims` es `nil`, `claims.UserID` entra en pánico con *nil pointer dereference* y `gin.Recovery` lo convierte en 500. Si `parseToken` devuelve un `claims` vacío en vez de `nil`, es peor: `c.Set("user", "")` y el handler corre con usuario vacío.

**3. `TrimPrefix` acepta cabeceras sin `Bearer `.** `Authorization: Basic abc` llega a `parseToken` como `Basic abc`. No es un agujero, pero el error que devuelves («invalid token») engaña al cliente; es un formato no soportado.

**4. El tipo guardado en el contexto es `string`** y los handlers tendrán que hacer `c.MustGet("user").(string)`; si alguien guarda un `int64` en otra ruta, el *type assertion* entra en pánico en producción. Mejor una clave con tipo y una función de acceso.

Versión corregida:

```go
const userKey = "auth.user"

type User struct {
	ID   string
	Role string
}

func Auth(secret []byte) gin.HandlerFunc {
	return func(c *gin.Context) {
		raw, ok := strings.CutPrefix(c.GetHeader("Authorization"), "Bearer ")
		if !ok || raw == "" {
			c.Header("WWW-Authenticate", `Bearer realm="api"`)
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "missing bearer token"})
			return
		}
		claims, err := parseToken(raw, secret)
		if err != nil {
			c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "invalid token"})
			return
		}
		c.Set(userKey, User{ID: claims.UserID, Role: claims.Role})
		c.Next()
	}
}

// UserFrom es la única forma de leer el usuario; nunca un MustGet suelto en un handler.
func UserFrom(c *gin.Context) (User, bool) {
	v, ok := c.Get(userKey)
	if !ok {
		return User{}, false
	}
	u, ok := v.(User)
	return u, ok
}
```

El `return` tras cada `Abort` sigue siendo necesario: `Abort` impide que se ejecuten los **siguientes** handlers, pero no interrumpe el código que queda en el tuyo.

Test de regresión que fija el comportamiento que fallaba:

```go
func TestAuthBlocksHandler(t *testing.T) {
	gin.SetMode(gin.TestMode)
	r := gin.New()
	handlerRan := false
	r.GET("/me", Auth([]byte("secret")), func(c *gin.Context) {
		handlerRan = true
		c.JSON(http.StatusOK, gin.H{"ok": true})
	})

	for _, header := range []string{"", "Bearer invalido", "Basic abc"} {
		handlerRan = false
		req := httptest.NewRequest(http.MethodGet, "/me", nil)
		if header != "" {
			req.Header.Set("Authorization", header)
		}
		rec := httptest.NewRecorder()
		r.ServeHTTP(rec, req)
		if rec.Code != http.StatusUnauthorized {
			t.Errorf("%q: status %d", header, rec.Code)
		}
		if handlerRan {
			t.Errorf("%q: el handler se ejecutó sin autenticación", header)
		}
	}
}
```

Con tu versión original, los tres casos fallan en `handlerRan`; con la corregida pasan. Deja este test: es el que impide que alguien «simplifique» quitando un `Abort` dentro de seis meses.""",
            },
        ]
    },
    # 19) Gin: errores centralizados con c.Error y middleware; gin.New vs Default (system exacto).
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "En Gin cada handler decide el código HTTP y el JSON de error a mano, y están todos distintos. ¿Cómo centralizo el manejo de errores? Usamos `gin.Default()`.",
            },
            {
                "role": "assistant",
                "content": r"""Los handlers registran el error con `c.Error(err)` y **un** middleware, al final de la cadena, lo traduce a status y JSON. Gin guarda los errores en `c.Errors`; el middleware los lee después de `c.Next()`.

```go
package httpx

import (
	"errors"
	"log/slog"
	"net/http"

	"github.com/gin-gonic/gin"
)

// APIError es el error que los servicios devuelven cuando quieren un status concreto.
type APIError struct {
	Status int
	Msg    string
	Err    error // causa, solo para logs
}

func (e *APIError) Error() string { return e.Msg }
func (e *APIError) Unwrap() error { return e.Err }

func NotFound(msg string) error  { return &APIError{Status: http.StatusNotFound, Msg: msg} }
func Conflict(msg string) error  { return &APIError{Status: http.StatusConflict, Msg: msg} }
func Forbidden(msg string) error { return &APIError{Status: http.StatusForbidden, Msg: msg} }

func ErrorHandler(logger *slog.Logger) gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Next() // ejecuta el resto de la cadena; a la vuelta, miramos qué pasó

		if len(c.Errors) == 0 || c.Writer.Written() {
			return // sin errores, o el handler ya respondió (p. ej. un 422 de validación)
		}
		err := c.Errors.Last().Err

		var apiErr *APIError
		switch {
		case errors.As(err, &apiErr):
			if apiErr.Status >= 500 {
				logger.ErrorContext(c.Request.Context(), "fallo del servidor", "err", err, "path", c.FullPath())
			}
			c.JSON(apiErr.Status, gin.H{"error": apiErr.Msg})
		case errors.Is(err, context.Canceled):
			c.Status(499) // el cliente se fue; no hay a quién responder
		default:
			logger.ErrorContext(c.Request.Context(), "error no manejado", "err", err, "path", c.FullPath())
			c.JSON(http.StatusInternalServerError, gin.H{"error": "internal error"})
		}
	}
}
```

Los handlers quedan sin decisiones de HTTP:

```go
func (h *Handler) Get(c *gin.Context) {
	order, err := h.orders.Get(c.Request.Context(), c.Param("id"))
	if err != nil {
		_ = c.Error(err) // devuelve *gin.Error; no hace falta usarlo
		return
	}
	c.JSON(http.StatusOK, order)
}
```

Y el servicio traduce **sus** errores de dominio una sola vez:

```go
func (s *Service) Get(ctx context.Context, id string) (Order, error) {
	o, err := s.repo.Get(ctx, id)
	if errors.Is(err, repo.ErrNoRows) {
		return Order{}, httpx.NotFound("order not found")
	}
	if err != nil {
		return Order{}, fmt.Errorf("getting order %s: %w", id, err) // 500 con causa en el log
	}
	return o, nil
}
```

Sobre `gin.Default()`: equivale a `gin.New()` + `gin.Logger()` + `gin.Recovery()`. Para un servicio con `slog` conviene montar la cadena a mano, porque `gin.Logger()` escribe en texto a stdout y no sabe de tu request id:

```go
r := gin.New()
r.Use(gin.Recovery()) // sigue siendo necesario: convierte pánicos en 500
r.Use(RequestID(), SlogLogger(logger))
r.Use(httpx.ErrorHandler(logger))
```

El orden importa: `ErrorHandler` después de `Recovery` para que un pánico no se salte el formato JSON (Recovery responde 500 vacío por su cuenta; si quieres JSON ahí también, `gin.CustomRecovery(func(c *gin.Context, rec any) { ... })`).

Dos límites de este patrón:

- **`c.Error` acumula**: si un handler registra dos errores, `Last()` gana. Usa uno por handler.
- **`c.Writer.Written()`** es lo que evita el doble `WriteHeader` cuando un handler ya respondió y además llamó a `c.Error` (por ejemplo, para que el logger lo vea). Es una decisión: el error se registra, la respuesta ya enviada no se toca.

En producción, `gin.SetMode(gin.ReleaseMode)` antes de crear el router (o `GIN_MODE=release`): quita el aviso de arranque y los `[GIN-debug]` de cada ruta.

Comprobación: un test con un `orders` falso que devuelve `repo.ErrNoRows` espera 404 y `{"error":"order not found"}`; con `errors.New("boom")` espera 500, `{"error":"internal error"}` y una línea de log que contiene `boom` y `/orders/:id` (eso es `c.FullPath()`, la plantilla de la ruta, no la URL concreta: útil para agrupar).""",
            },
        ]
    },
    # 20) Inglés: testing en Gin.
    {
        "messages": [
            {
                "role": "user",
                "content": "What's the recommended way to test Gin handlers? Through the router with httptest, or is there something like a test context for unit tests?",
            },
            {
                "role": "assistant",
                "content": r"""Both exist, and they answer different questions. Default to the router: it exercises routing, middleware and binding the way production does. Use `gin.CreateTestContext` only for a handler whose logic you want to drive directly with hand-built params.

**Through the router.** Build the engine with a function that `main` also uses, so the test sees the real route table and middleware chain:

```go
package server

func NewRouter(deps Deps) *gin.Engine {
	r := gin.New()
	r.Use(gin.Recovery(), httpx.ErrorHandler(deps.Logger))
	api := r.Group("/api")
	{
		api.GET("/orders/:id", deps.Orders.Get)
		api.POST("/orders", deps.Orders.Create)
	}
	return r
}
```

```go
package server_test

func TestMain(m *testing.M) {
	gin.SetMode(gin.TestMode) // no debug output, no per-route log lines
	os.Exit(m.Run())
}

func TestOrders(t *testing.T) {
	t.Parallel()
	tests := []struct {
		name       string
		method     string
		path       string
		body       string
		wantStatus int
		wantBody   string
	}{
		{"found", http.MethodGet, "/api/orders/o-1", "", http.StatusOK, `"id":"o-1"`},
		{"missing", http.MethodGet, "/api/orders/nope", "", http.StatusNotFound, `"error":"order not found"`},
		{"create", http.MethodPost, "/api/orders", `{"currency":"EUR","total_cents":100}`, http.StatusCreated, `"currency":"EUR"`},
		{"invalid", http.MethodPost, "/api/orders", `{"currency":"EUR"}`, http.StatusUnprocessableEntity, `"total_cents"`},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			r := server.NewRouter(testDeps(t)) // fresh fakes per subtest

			req := httptest.NewRequest(tt.method, tt.path, strings.NewReader(tt.body))
			if tt.body != "" {
				req.Header.Set("Content-Type", "application/json")
			}
			rec := httptest.NewRecorder()
			r.ServeHTTP(rec, req)

			if rec.Code != tt.wantStatus {
				t.Fatalf("status = %d, want %d; body: %s", rec.Code, tt.wantStatus, rec.Body)
			}
			if !strings.Contains(rec.Body.String(), tt.wantBody) {
				t.Errorf("body = %s, want substring %q", rec.Body, tt.wantBody)
			}
		})
	}
}
```

**Unit-level, with a test context.** Useful for a handler with many branches where building request bodies for each would be noise:

```go
func TestGetOrderHandler_NotFound(t *testing.T) {
	rec := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(rec)
	c.Request = httptest.NewRequest(http.MethodGet, "/api/orders/nope", nil)
	c.Params = gin.Params{{Key: "id", Value: "nope"}} // what the router would have set

	h := orders.NewHandler(&fakeStore{})
	h.Get(c)

	// the handler only calls c.Error; without the ErrorHandler middleware nothing is written yet
	if len(c.Errors) != 1 {
		t.Fatalf("errors = %v", c.Errors)
	}
	var apiErr *httpx.APIError
	if !errors.As(c.Errors.Last().Err, &apiErr) || apiErr.Status != http.StatusNotFound {
		t.Fatalf("unexpected error: %v", c.Errors.Last().Err)
	}
}
```

Notice what this test does *not* see: the JSON shape, the status code written, the middleware. That is why it is the exception.

Three things that trip people up:

- **`gin.SetMode(gin.TestMode)` once**, in `TestMain`; setting it inside parallel subtests is a data race on a global.
- **Binding reads `Content-Type`**: forget the header and `ShouldBindJSON` fails with `invalid request` instead of exercising your validation.
- **`c.Request.Context()`** is what the handlers must pass down, so a fake store that respects `ctx` can be tested for cancellation with `httptest.NewRequestWithContext` (Go 1.23).

Run `go test ./... -race -count=1`; `-race` matters because Gin shares the engine across goroutines in `t.Parallel` subtests, and a fake with an unguarded map is the first thing it will flag.""",
            },
        ]
    },
    # 21) Gin: *gin.Context usado en una goroutine; data race y datos de otra petición (usuario trae traza).
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Desde que mandamos el email de bienvenida en segundo plano, `go test -race` revienta y en producción algunos emails salen con el logo y el idioma de **otro** cliente (somos multi-tenant). Gin 1.10. El handler:

```go
func (h *Handler) Register(c *gin.Context) {
	var req RegisterRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid body"})
		return
	}
	user, err := h.users.Create(c.Request.Context(), req)
	if err != nil {
		_ = c.Error(err)
		return
	}
	go func() {
		locale := c.GetHeader("Accept-Language")
		tenant := c.GetString("tenant")
		if err := h.mailer.SendWelcome(c.Request.Context(), tenant, locale, user); err != nil {
			slog.Error("welcome email", "err", err)
		}
	}()
	c.JSON(http.StatusCreated, user)
}
```

Y lo que dice el detector:

```
WARNING: DATA RACE
Read at 0x00c0002b0f50 by goroutine 87:
  github.com/gin-gonic/gin.(*Context).Get()
      /root/go/pkg/mod/github.com/gin-gonic/gin@v1.10.0/context.go:270 +0x84
  github.com/gin-gonic/gin.(*Context).GetString()
      /root/go/pkg/mod/github.com/gin-gonic/gin@v1.10.0/context.go:301 +0x44
  example.com/shop/internal/users.(*Handler).Register.func1()
      /src/internal/users/handler.go:49 +0x6e

Previous write at 0x00c0002b0f50 by goroutine 85:
  github.com/gin-gonic/gin.(*Context).reset()
      /root/go/pkg/mod/github.com/gin-gonic/gin@v1.10.0/context.go:96 +0x1a4
  github.com/gin-gonic/gin.(*Engine).ServeHTTP()
      /root/go/pkg/mod/github.com/gin-gonic/gin@v1.10.0/gin.go:587 +0x15c
```""",
            },
            {
                "role": "assistant",
                "content": r"""La traza cuenta el bug entero: tu goroutine **lee** `c.Keys` (vía `GetString` → `Get`) mientras `Engine.ServeHTTP` **escribe** ese mismo campo en `(*Context).reset()`. Gin no crea un `*gin.Context` por petición: los saca de un `sync.Pool`. En cuanto tu handler retorna, ese objeto vuelve al pool, se resetea y se entrega a la **siguiente** petición. Tu goroutine, que sigue viva, lee el tenant y el idioma de otra persona. No es un bug de Gin: `c` solo es válido mientras dura el handler.

Detrás hay un segundo fallo que todavía no has visto: `c.Request.Context()` se cancela cuando el handler retorna (lo hace net/http), así que el envío acabará fallando con `context canceled` en cuanto el SMTP tarde un poco.

### Arreglo: la goroutine recibe valores, no el contexto

```go
type WelcomeEmail struct {
	To     string
	Name   string
	Tenant string
	Locale string
}

func (h *Handler) Register(c *gin.Context) {
	var req RegisterRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid body"})
		return
	}
	user, err := h.users.Create(c.Request.Context(), req)
	if err != nil {
		_ = c.Error(err)
		return
	}

	// Se copia aquí, mientras c todavía pertenece a esta petición.
	msg := WelcomeEmail{
		To:     user.Email,
		Name:   user.Name,
		Tenant: c.GetString("tenant"),
		Locale: c.GetHeader("Accept-Language"),
	}
	// Conserva los valores del contexto (request id, trazas) pero no su cancelación.
	base := context.WithoutCancel(c.Request.Context())

	h.background.Go(func() {
		ctx, cancel := context.WithTimeout(base, 10*time.Second)
		defer cancel()
		if err := h.mailer.SendWelcome(ctx, msg); err != nil {
			slog.ErrorContext(ctx, "welcome email failed", "err", err, "user_id", user.ID)
		}
	})

	c.JSON(http.StatusCreated, user)
}
```

Y el lanzador de tareas, que el servidor espera al apagarse:

```go
// Background ejecuta tareas fuera de la petición y permite esperarlas en el apagado.
type Background struct{ wg sync.WaitGroup }

func (b *Background) Go(fn func()) {
	b.wg.Add(1)
	go func() {
		defer b.wg.Done()
		defer func() {
			if r := recover(); r != nil {
				slog.Error("background task panicked", "panic", r)
			}
		}()
		fn()
	}()
}

// Wait se llama después de srv.Shutdown, antes de cerrar el pool de la BD.
func (b *Background) Wait() { b.wg.Wait() }
```

Por qué así y no de otra forma:

- **Valores, no `c.Copy()`.** `c.Copy()` es seguro para leer `Keys` y `Params`, pero conserva el mismo `*http.Request` con su contexto ya cancelado, y sigue siendo un `*gin.Context` que tienta a pasarlo como `context.Context`. El struct `WelcomeEmail` deja escrito qué necesita la tarea y se prueba sin Gin.
- **`context.WithoutCancel` (Go 1.21+).** Mantiene el request id y el span para que los logs del envío se correlacionen con la petición; el `WithTimeout` pone el límite que antes no existía.
- **`recover` dentro de la goroutine.** El middleware `Recovery` de Gin solo protege la goroutine del handler; un panic en la tuya tira el proceso entero. Desde Go 1.25, `sync.WaitGroup` tiene `Go(fn)`, pero el `recover` lo sigues necesitando.
- **Límite conocido.** Si el proceso muere de golpe (OOM, `kill -9`), el email se pierde. Si ese correo importa (verificación de cuenta), escríbelo en una tabla *outbox* en la misma transacción que crea el usuario y que lo envíe un worker.

### Comprobación

Este test reproduce el bug: muchas peticiones seguidas obligan al pool a reutilizar contextos.

```go
type fakeMailer struct{ sent chan WelcomeEmail }

func (f *fakeMailer) SendWelcome(_ context.Context, m WelcomeEmail) error {
	f.sent <- m
	return nil
}

func TestRegister_WelcomeEmailKeepsItsOwnTenant(t *testing.T) {
	mailer := &fakeMailer{sent: make(chan WelcomeEmail, 100)}
	bg := &Background{}
	h := NewHandler(newFakeUsers(), mailer, bg)

	r := gin.New()
	r.POST("/register", func(c *gin.Context) {
		c.Set("tenant", c.GetHeader("X-Tenant")) // simula el middleware de tenant
		h.Register(c)
	})

	for i := range 50 {
		body := fmt.Sprintf(`{"email":"u%d@example.com","name":"U%d"}`, i, i)
		req := httptest.NewRequest(http.MethodPost, "/register", strings.NewReader(body))
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("X-Tenant", fmt.Sprintf("t%d", i))
		r.ServeHTTP(httptest.NewRecorder(), req)
	}
	bg.Wait()
	close(mailer.sent)

	for m := range mailer.sent {
		n := strings.TrimSuffix(strings.TrimPrefix(m.To, "u"), "@example.com")
		if m.Tenant != "t"+n {
			t.Errorf("email to %s carries tenant %q, want %q", m.To, m.Tenant, "t"+n)
		}
	}
}
```

Con el handler original, `go test -race -count=10 ./internal/users` informa la carrera y, a menudo, también la aserción de tenant. Con el arreglo, las dos cosas desaparecen. Para prevenir la siguiente: en revisión, cualquier `go func` que capture `c` dentro de un handler de Gin se rechaza sin discusión.""",
            },
        ]
    },
    # 22) Gin: "You trusted all proxies", ClientIP falsificable y Cloudflare delante (multiturno, España).
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Al arrancar Gin me sale esto y no sé si importa:

```
[WARNING] You trusted all proxies, this is NOT safe. We recommend you to set a value.
Please check https://pkg.go.dev/github.com/gin-gonic/gin#readme-don-t-trust-all-proxies for details.
```

Uso `c.ClientIP()` para limitar los intentos de login por IP. ¿Lo puedo ignorar?""",
            },
            {
                "role": "assistant",
                "content": r"""No, y en tu caso menos que en ninguno: con la configuración por defecto **el cliente elige la IP que devuelve `c.ClientIP()`**, así que tu límite de intentos se esquiva cambiando una cabecera.

Por qué: Gin arranca confiando en todos los proxies y con `ForwardedByClientIP = true`. `ClientIP()` recorre `X-Forwarded-For` de derecha a izquierda, salta las IP de proxies confiables y devuelve la primera que no lo es. Si todas son confiables, llega al principio de la lista y devuelve la de más a la izquierda, que es justo la que escribe el cliente:

```bash
for i in $(seq 1 500); do
  curl -s -o /dev/null -H "X-Forwarded-For: 10.66.0.$((i % 250))" \
    -H 'Content-Type: application/json' \
    -d '{"email":"victima@example.com","password":"intento'"$i"'"}' \
    https://api.example.com/login
done
# Cada intento parece venir de una IP distinta: el límite nunca salta.
```

El arreglo es declarar quién está delante. Centralízalo en la función que construye el engine:

```go
func newEngine(trustedProxies []string) (*gin.Engine, error) {
	r := gin.New()
	r.Use(gin.Recovery())
	// nil: nadie es proxy; ClientIP() usa siempre RemoteAddr e ignora las cabeceras.
	// []string{"10.0.0.0/8"}: solo se cree X-Forwarded-For si la conexión viene de ese rango.
	if err := r.SetTrustedProxies(trustedProxies); err != nil {
		return nil, fmt.Errorf("trusted proxies: %w", err)
	}
	return r, nil
}
```

Si Gin está expuesto directamente, pasa `nil`. Si hay un balanceador, pasa su rango (léelo de configuración, no lo cableés en el código).

Comprobación sin red, que deja el comportamiento fijado para siempre:

```go
func TestClientIP_CannotBeSpoofed(t *testing.T) {
	r, err := newEngine([]string{"10.0.0.0/8"})
	if err != nil {
		t.Fatal(err)
	}
	var got string
	r.GET("/ip", func(c *gin.Context) { got = c.ClientIP() })

	tests := []struct{ name, remoteAddr, xff, want string }{
		{"cliente directo con cabecera falsa", "203.0.113.7:51000", "1.2.3.4", "203.0.113.7"},
		{"vía balanceador", "10.1.2.3:443", "198.51.100.9", "198.51.100.9"},
		{"vía balanceador, cliente añade una IP falsa", "10.1.2.3:443", "1.2.3.4, 198.51.100.9", "198.51.100.9"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := httptest.NewRequest(http.MethodGet, "/ip", nil)
			req.RemoteAddr = tt.remoteAddr
			req.Header.Set("X-Forwarded-For", tt.xff)
			r.ServeHTTP(httptest.NewRecorder(), req)
			if got != tt.want {
				t.Fatalf("ClientIP() = %s, want %s", got, tt.want)
			}
		})
	}
}
```

El tercer caso es el importante: el balanceador añade al final la IP que ve, y Gin se queda con esa, no con la que inventó el cliente.""",
            },
            {
                "role": "user",
                "content": "Vale. Pero en producción tenemos Cloudflare delante, luego el ingress del clúster de Kubernetes y luego el pod. ¿Qué pongo exactamente?",
            },
            {
                "role": "assistant",
                "content": r"""Con dos saltos delante tienes dos opciones correctas. La primera es más simple, pero depende de una condición de infraestructura que tienes que comprobar, no suponer.

**Opción A: confiar en la cabecera de Cloudflare.** Cloudflare manda la IP real del cliente en `CF-Connecting-IP`, y Gin trae una constante para eso:

```go
r, err := newEngine([]string{cfg.IngressCIDR}) // p. ej. "10.42.0.0/16", rango de los pods del ingress
if err != nil {
	return err
}
// Solo es seguro si el origen ÚNICAMENTE acepta tráfico que pasa por Cloudflare.
r.TrustedPlatform = gin.PlatformCloudflare
```

Ojo con el detalle: cuando `TrustedPlatform` está puesto y la cabecera viene, `ClientIP()` la devuelve **sin mirar quién la envió**. Si alguien encuentra la IP pública de tu balanceador y le habla directamente, manda `CF-Connecting-IP: 1.2.3.4` y volvéis al problema inicial. Por eso esta opción exige cerrar el origen: firewall o *security group* del balanceador que solo admita los rangos publicados por Cloudflare, o Cloudflare Tunnel, o *authenticated origin pulls* (mTLS entre Cloudflare y tu origen).

El `SetTrustedProxies` con el rango del ingress sigue sirviendo: cubre las peticiones que no traen la cabecera (sondas internas, tráfico entre servicios).

**Opción B: cadena de proxies confiables.** Metes en `SetTrustedProxies` el rango del ingress **y** los rangos de Cloudflare, y Gin recorre `X-Forwarded-For` saltándolos todos. Funciona sin cerrar el origen, pero tiene dos costes: mantener la lista de Cloudflare sincronizada en tu configuración (cambia de vez en cuando) y asegurarte de que tu ingress añade a `X-Forwarded-For` en vez de sobrescribirlo. Más piezas que pueden desalinearse en silencio.

Mi elección: **A con el origen cerrado**. Es una regla de red auditable, frente a una lista de CIDR replicada en cada servicio.

Cómo verificarlo de verdad:

1. Desde una máquina fuera de Cloudflare: `curl -H 'CF-Connecting-IP: 6.6.6.6' https://IP-DEL-BALANCEADOR/ip -k`. Debe fallar (timeout o rechazo). Si responde, la opción A no es segura todavía.
2. Durante un día, registra `ClientIP()` y `RemoteAddr` juntos en el login. Las IP deben ser variadas y públicas; si ves rangos de Cloudflare o del clúster, algo de la cadena está mal.
3. Añade al test anterior un caso con `TrustedPlatform` y `CF-Connecting-IP` para fijar el comportamiento.

Y una cosa más, independiente de todo esto: limita también **por cuenta** (email), no solo por IP. Un atacante con una botnet rota IP de verdad; el límite por cuenta es el que protege a la víctima concreta.""",
            },
        ]
    },
    # ---------------------------------------------------------------- Echo (4)
    # 23) Echo v4: validador, HTTPErrorHandler central, middlewares y apagado (system exacto).
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Empiezo un servicio nuevo con Echo v4. ¿Cómo lo dejo bien montado desde el principio? Me importa sobre todo validación de entrada, errores en JSON coherentes en toda la API y que se apague sin cortar peticiones.",
            },
            {
                "role": "assistant",
                "content": r"""Echo te da el enrutado y los middlewares, pero deja dos huecos que conviene rellenar el primer día: **no trae validador** (tienes que registrar uno que implemente `echo.Validator`) y su **manejador de errores por defecto** devuelve formatos distintos según el origen del error. La idea: los handlers devuelven `error` y nunca escriben respuestas de error; un único `HTTPErrorHandler` decide status y forma.

### 1. Validador

```go
// internal/httpx/validator.go
package httpx

import (
	"reflect"
	"strings"

	"github.com/go-playground/validator/v10"
)

// Validator adapta go-playground/validator a la interfaz echo.Validator.
type Validator struct{ v *validator.Validate }

func NewValidator() *Validator {
	v := validator.New(validator.WithRequiredStructEnabled())
	// Los errores usan el nombre JSON ("price_cents"), no el del struct ("PriceCents").
	v.RegisterTagNameFunc(func(f reflect.StructField) string {
		name, _, _ := strings.Cut(f.Tag.Get("json"), ",")
		if name == "-" {
			return ""
		}
		return name
	})
	return &Validator{v: v}
}

func (cv *Validator) Validate(i any) error { return cv.v.Struct(i) }
```

### 2. Errores: un solo sitio traduce error → HTTP

```go
// internal/httpx/errors.go
package httpx

import (
	"errors"
	"fmt"
	"log/slog"
	"net/http"

	"github.com/go-playground/validator/v10"
	"github.com/labstack/echo/v4"

	"example.com/shop/internal/domain"
)

type APIError struct {
	Status  int               `json:"-"`
	Code    string            `json:"code"`
	Message string            `json:"message"`
	Fields  map[string]string `json:"fields,omitempty"`
}

func (e *APIError) Error() string { return e.Code + ": " + e.Message }

func ErrorHandler(logger *slog.Logger) echo.HTTPErrorHandler {
	return func(err error, c echo.Context) {
		if c.Response().Committed {
			return // la cabecera ya salió: no se puede cambiar el status
		}
		apiErr := toAPIError(err)
		if apiErr.Status >= http.StatusInternalServerError {
			logger.ErrorContext(c.Request().Context(), "request failed",
				"err", err, "method", c.Request().Method, "route", c.Path())
		}
		var writeErr error
		if c.Request().Method == http.MethodHead {
			writeErr = c.NoContent(apiErr.Status)
		} else {
			writeErr = c.JSON(apiErr.Status, apiErr)
		}
		if writeErr != nil {
			logger.Error("writing error response", "err", writeErr)
		}
	}
}

func toAPIError(err error) *APIError {
	var (
		apiErr  *APIError
		httpErr *echo.HTTPError
		valErrs validator.ValidationErrors
	)
	switch {
	case errors.As(err, &apiErr):
		return apiErr
	case errors.As(err, &valErrs):
		fields := make(map[string]string, len(valErrs))
		for _, fe := range valErrs {
			fields[fe.Field()] = fe.Tag()
		}
		return &APIError{Status: http.StatusUnprocessableEntity, Code: "validation_failed",
			Message: "hay campos no válidos", Fields: fields}
	case errors.Is(err, domain.ErrNotFound):
		return &APIError{Status: http.StatusNotFound, Code: "not_found", Message: "recurso no encontrado"}
	case errors.Is(err, domain.ErrConflict):
		return &APIError{Status: http.StatusConflict, Code: "conflict", Message: "el recurso ya existe"}
	case errors.As(err, &httpErr):
		// Errores del propio Echo: ruta inexistente (404), método (405), Bind (400), BodyLimit (413).
		return &APIError{Status: httpErr.Code, Code: "http_error", Message: fmt.Sprint(httpErr.Message)}
	default:
		return &APIError{Status: http.StatusInternalServerError, Code: "internal", Message: "error interno"}
	}
}
```

`domain.ErrNotFound` y `domain.ErrConflict` son `errors.New(...)` en un paquete sin dependencias; los repositorios los envuelven con `%w` y el handler ni se entera de HTTP.

### 3. Montaje del `*echo.Echo`

```go
// internal/server/server.go
func New(logger *slog.Logger, products *catalog.Handler) *echo.Echo {
	e := echo.New()
	e.HideBanner = true
	e.HidePort = true
	e.Validator = httpx.NewValidator()
	e.HTTPErrorHandler = httpx.ErrorHandler(logger)

	// El orden importa: el primero envuelve a los demás.
	e.Use(middleware.RequestID())
	e.Use(middleware.RequestLoggerWithConfig(middleware.RequestLoggerConfig{
		LogMethod: true, LogURI: true, LogStatus: true, LogLatency: true,
		LogRequestID: true, LogError: true,
		HandleError: true, // registra el status que decidió ErrorHandler, no un 200 falso
		LogValuesFunc: func(c echo.Context, v middleware.RequestLoggerValues) error {
			logger.LogAttrs(c.Request().Context(), slog.LevelInfo, "request",
				slog.String("method", v.Method), slog.String("uri", v.URI),
				slog.Int("status", v.Status), slog.Duration("latency", v.Latency),
				slog.String("request_id", v.RequestID))
			return nil
		},
	}))
	e.Use(middleware.Recover())         // dentro del logger: un panic queda registrado como 500
	e.Use(middleware.BodyLimit("1M"))

	api := e.Group("/api")
	api.GET("/products/:id", products.Get)
	api.POST("/products", products.Create)
	return e
}
```

Un handler queda así de limpio:

```go
type createProductRequest struct {
	Name       string `json:"name" validate:"required,min=2,max=120"`
	PriceCents int64  `json:"price_cents" validate:"required,gt=0"`
	SKU        string `json:"sku" validate:"required,alphanum,len=8"`
}

func (h *Handler) Create(c echo.Context) error {
	var req createProductRequest
	if err := c.Bind(&req); err != nil {
		return err // *echo.HTTPError 400: JSON mal formado o tipo incorrecto
	}
	if err := c.Validate(&req); err != nil {
		return err // ValidationErrors → 422 con detalle por campo
	}
	p, err := h.products.Create(c.Request().Context(), req.Name, req.PriceCents, req.SKU)
	if err != nil {
		return err // domain.ErrConflict → 409; lo demás → 500 con log
	}
	return c.JSON(http.StatusCreated, p)
}
```

### 4. Arranque y apagado

Uso un `http.Server` propio en vez de `e.Start`: `*echo.Echo` es un `http.Handler`, y así los timeouts quedan explícitos y son iguales a los de tus otros servicios.

```go
func main() {
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	if err := run(ctx, logger); err != nil {
		logger.Error("server stopped", "err", err)
		os.Exit(1)
	}
}

func run(ctx context.Context, logger *slog.Logger) error {
	pool, err := pgxpool.New(ctx, os.Getenv("DATABASE_URL"))
	if err != nil {
		return fmt.Errorf("connect db: %w", err)
	}
	defer pool.Close()

	srv := &http.Server{
		Addr:              ":8080",
		Handler:           server.New(logger, catalog.NewHandler(catalog.NewPGRepo(pool))),
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       15 * time.Second,
		WriteTimeout:      30 * time.Second,
		IdleTimeout:       60 * time.Second,
	}
	errCh := make(chan error, 1)
	go func() { errCh <- srv.ListenAndServe() }()

	select {
	case err := <-errCh:
		return err // no pudo escuchar (puerto ocupado, permisos)
	case <-ctx.Done():
	}
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	return srv.Shutdown(shutdownCtx) // deja terminar las peticiones en curso
}
```

### Comprobación

```go
func TestCreateProduct_InvalidBodyIs422WithFields(t *testing.T) {
	e := server.New(slog.New(slog.DiscardHandler), catalog.NewHandler(&fakeRepo{}))
	req := httptest.NewRequest(http.MethodPost, "/api/products",
		strings.NewReader(`{"name":"x","price_cents":0}`))
	req.Header.Set(echo.HeaderContentType, echo.MIMEApplicationJSON)
	rec := httptest.NewRecorder()
	e.ServeHTTP(rec, req)

	if rec.Code != http.StatusUnprocessableEntity {
		t.Fatalf("status = %d, body = %s", rec.Code, rec.Body)
	}
	for _, want := range []string{`"name":"min"`, `"price_cents":"required"`, `"sku":"required"`} {
		if !strings.Contains(rec.Body.String(), want) {
			t.Errorf("body %s lacks %s", rec.Body, want)
		}
	}
}
```

`slog.DiscardHandler` es de Go 1.24; en 1.23 usa `slog.NewTextHandler(io.Discard, nil)`. Fíjate en `price_cents`: con `required`, el `0` cuenta como ausente y gana a `gt`, porque el validador se detiene en la primera regla que falla de cada campo. Añade un caso con `-5` para cubrir `gt`.""",
            },
        ]
    },
    # 24) Echo: asignación masiva e IDOR con c.Bind y GORM Save (usuario trae código, system variante).
    {
        "messages": [
            {
                "role": "system",
                "content": "Revisa el código como un ingeniero de seguridad: primero los problemas ordenados por gravedad, después la versión corregida.",
            },
            {
                "role": "user",
                "content": r"""Este handler de Echo pasó code review hace meses. QA acaba de reportar que un usuario normal se puso `"role": "admin"` mandándolo en el body. ¿Qué más tiene mal?

```go
type User struct {
	ID       int64  `json:"id" gorm:"primaryKey"`
	TenantID int64  `json:"tenant_id"`
	Email    string `json:"email"`
	Name     string `json:"name"`
	Role     string `json:"role"`
	Bio      string `json:"bio"`
}

// e.PUT("/users/:id", h.UpdateUser, jwtMiddleware)
func (h *Handler) UpdateUser(c echo.Context) error {
	var u User
	if err := c.Bind(&u); err != nil {
		return c.JSON(http.StatusBadRequest, err)
	}
	if err := h.db.Save(&u).Error; err != nil {
		return c.JSON(http.StatusInternalServerError, err)
	}
	return c.JSON(http.StatusOK, u)
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""Lo que vio QA es el síntoma más visible, pero no el peor. En orden de gravedad:

1. **Crítico: cualquiera puede modificar a cualquier usuario (IDOR).** El `:id` de la ruta no se usa: `ID` no tiene tag `param:"id"`, así que Echo lo rellena desde el body. Y aunque lo tuviera, `Bind` aplica primero los parámetros de ruta y luego el cuerpo, de modo que el `"id"` del body **pisa** al de la URL. Nada compara ese ID con el usuario del token, y `tenant_id` también viene del body: se puede escribir en otro tenant.
2. **Crítico: asignación masiva.** `Bind` sobre el modelo de persistencia rellena todo campo con tag `json`: `role`, `tenant_id`, `email`. Es el bug de QA.
3. **Alto: `Save` escribe todas las columnas, y a veces inserta.** Con clave primaria, GORM hace `UPDATE` de **todos** los campos: un body `{"id":5,"bio":"hola"}` deja vacíos el email, el nombre y el rol del usuario 5. Sin `id` (o con `0`), `Save` hace `INSERT`: el endpoint permite crear usuarios con el rol que se quiera.
4. **Medio: errores mal expuestos.** `c.JSON(500, err)` serializa el error tal cual (normalmente `{}`, a veces un struct del driver con detalles) y no queda nada en el log. Devuelve el `error` y deja que el `HTTPErrorHandler` decida.
5. **Bajo: sin validación y sin `WithContext`.** La consulta ignora la cancelación de la petición y acepta cualquier longitud.

### Versión corregida

Separo los casos: «editar mi perfil» y «cambiar el rol de alguien» son operaciones distintas con permisos distintos. Esta es la primera; la segunda va en `/admin` con `RequireRole("admin")` y auditoría.

```go
// Entrada: solo lo que un usuario puede cambiar de sí mismo.
// Punteros para distinguir «no enviado» de «enviado vacío» en un PATCH.
type updateMeRequest struct {
	Name *string `json:"name" validate:"omitempty,min=1,max=100"`
	Bio  *string `json:"bio" validate:"omitempty,max=500"`
}

// Salida: el modelo de GORM nunca cruza la frontera HTTP.
type meResponse struct {
	ID    int64  `json:"id"`
	Email string `json:"email"`
	Name  string `json:"name"`
	Bio   string `json:"bio"`
}

// e.PATCH("/me", h.UpdateMe, jwtMiddleware)
func (h *Handler) UpdateMe(c echo.Context) error {
	claims, ok := auth.ClaimsFrom(c)
	if !ok {
		return echo.ErrUnauthorized
	}
	var req updateMeRequest
	// BindBody: solo el cuerpo; ni la ruta ni la query pueden colar valores.
	if err := (&echo.DefaultBinder{}).BindBody(c, &req); err != nil {
		return err
	}
	if err := c.Validate(&req); err != nil {
		return err
	}
	changes := map[string]any{}
	if req.Name != nil {
		changes["name"] = *req.Name
	}
	if req.Bio != nil {
		changes["bio"] = *req.Bio
	}
	if len(changes) == 0 {
		return echo.NewHTTPError(http.StatusBadRequest, "no hay campos para actualizar")
	}

	ctx := c.Request().Context()
	scope := h.db.WithContext(ctx).Model(&User{}).
		Where("id = ? AND tenant_id = ?", claims.UserID, claims.TenantID)
	res := scope.Updates(changes) // solo estas columnas; jamás un INSERT
	if res.Error != nil {
		return fmt.Errorf("update me: %w", res.Error)
	}
	if res.RowsAffected == 0 {
		return echo.ErrNotFound
	}

	var u User
	if err := h.db.WithContext(ctx).
		Where("id = ? AND tenant_id = ?", claims.UserID, claims.TenantID).
		First(&u).Error; err != nil {
		return fmt.Errorf("reload user: %w", err)
	}
	return c.JSON(http.StatusOK, meResponse{ID: u.ID, Email: u.Email, Name: u.Name, Bio: u.Bio})
}
```

`auth.ClaimsFrom` lee lo que dejó el middleware JWT:

```go
func ClaimsFrom(c echo.Context) (*Claims, bool) {
	token, ok := c.Get("user").(*jwt.Token)
	if !ok {
		return nil, false
	}
	claims, ok := token.Claims.(*Claims)
	return claims, ok
}
```

Dos notas sobre el arreglo:

- La identidad sale **siempre del token**, nunca de la URL ni del body. Por eso la ruta pasa a ser `/me`: no hay ID que manipular.
- `RowsAffected == 0` significa «no existe en tu tenant» en Postgres. En MySQL cuenta filas *cambiadas*, así que un PATCH con los mismos valores daría un 404 falso; allí comprueba la existencia con el `First` y no con `RowsAffected`.

### Test de regresión

Con SQLite en memoria (driver puro Go `github.com/glebarez/sqlite`) basta para fijar el comportamiento:

```go
func TestUpdateMe_IgnoresPrivilegedFields(t *testing.T) {
	db, err := gorm.Open(sqlite.Open(filepath.Join(t.TempDir(), "test.db")), &gorm.Config{})
	if err != nil {
		t.Fatal(err)
	}
	if err := db.AutoMigrate(&User{}); err != nil {
		t.Fatal(err)
	}
	db.Create(&User{ID: 1, TenantID: 10, Email: "admin@acme.test", Name: "Admin", Role: "admin"})
	db.Create(&User{ID: 2, TenantID: 10, Email: "eve@acme.test", Name: "Eve", Role: "user"})

	e := echo.New()
	e.Validator = httpx.NewValidator()
	body := `{"id":1,"role":"admin","tenant_id":99,"name":"Eve 2"}`
	req := httptest.NewRequest(http.MethodPatch, "/me", strings.NewReader(body))
	req.Header.Set(echo.HeaderContentType, echo.MIMEApplicationJSON)
	c := e.NewContext(req, httptest.NewRecorder())
	c.Set("user", &jwt.Token{Claims: &auth.Claims{UserID: 2, TenantID: 10, Role: "user"}})

	if err := (&Handler{db: db}).UpdateMe(c); err != nil {
		t.Fatal(err)
	}

	var eve, admin User
	db.First(&eve, 2)
	db.First(&admin, 1)
	if eve.Role != "user" || eve.TenantID != 10 || eve.Name != "Eve 2" {
		t.Fatalf("eve = %+v", eve)
	}
	if admin.Name != "Admin" || admin.Role != "admin" {
		t.Fatalf("admin was modified: %+v", admin)
	}
}
```

El test manda exactamente el ataque (otro `id`, `role`, otro `tenant_id`) y comprueba que solo cambia el nombre del propio usuario. Para que no vuelva a pasar en otros handlers, la regla de revisión es simple: **nunca `Bind` sobre un struct con tags de GORM**.""",
            },
        ]
    },
    # 25) Echo: JWT con echo-jwt v4 + roles; después cómo testear rutas protegidas (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": "Con Echo v4 quiero proteger todo `/api` con JWT HS256 (los tokens los emite nuestro propio login) y tener claims propios con usuario, tenant y rol. Vi que `middleware.JWT` está deprecado. ¿Qué uso ahora y cómo lo dejo bien?",
            },
            {
                "role": "assistant",
                "content": r"""Usa `github.com/labstack/echo-jwt/v4`: es el reemplazo oficial de `middleware.JWT` (deprecado desde Echo v4.10) y trabaja con `github.com/golang-jwt/jwt/v5`. Te recomiendo darle un `ParseTokenFunc` propio en vez de solo `SigningKey`: con la configuración mínima se valida la firma y el `exp` si viene, pero no el emisor ni la audiencia, y un token **sin** `exp` se acepta para siempre.

```go
// internal/auth/jwt.go
package auth

import (
	"net/http"
	"strconv"
	"time"

	"github.com/golang-jwt/jwt/v5"
	echojwt "github.com/labstack/echo-jwt/v4"
	"github.com/labstack/echo/v4"
)

const (
	ContextKey = "user" // donde echo-jwt deja el *jwt.Token
	issuer     = "auth.acme.internal"
	audience   = "orders-api"
)

type Claims struct {
	UserID   int64  `json:"uid"`
	TenantID int64  `json:"tid"`
	Role     string `json:"role"`
	jwt.RegisteredClaims
}

func Middleware(secret []byte) echo.MiddlewareFunc {
	parser := jwt.NewParser(
		jwt.WithValidMethods([]string{jwt.SigningMethodHS256.Alg()}),
		jwt.WithIssuer(issuer),
		jwt.WithAudience(audience),
		jwt.WithExpirationRequired(),
		jwt.WithLeeway(30*time.Second), // tolera relojes ligeramente desfasados
	)
	return echojwt.WithConfig(echojwt.Config{
		ContextKey: ContextKey,
		ParseTokenFunc: func(c echo.Context, raw string) (any, error) {
			token, err := parser.ParseWithClaims(raw, new(Claims), func(*jwt.Token) (any, error) {
				return secret, nil
			})
			if err != nil {
				return nil, err
			}
			return token, nil
		},
		ErrorHandler: func(c echo.Context, err error) error {
			// Al cliente no le decimos si caducó o si la firma es mala.
			c.Response().Header().Set(echo.HeaderWWWAuthenticate, `Bearer realm="api"`)
			return echo.NewHTTPError(http.StatusUnauthorized, "token inválido o ausente").SetInternal(err)
		},
	})
}

func ClaimsFrom(c echo.Context) (*Claims, bool) {
	token, ok := c.Get(ContextKey).(*jwt.Token)
	if !ok {
		return nil, false
	}
	claims, ok := token.Claims.(*Claims)
	return claims, ok
}

// RequireRole va DESPUÉS de Middleware: 401 si no hay identidad, 403 si no tiene permiso.
func RequireRole(roles ...string) echo.MiddlewareFunc {
	allowed := make(map[string]struct{}, len(roles))
	for _, r := range roles {
		allowed[r] = struct{}{}
	}
	return func(next echo.HandlerFunc) echo.HandlerFunc {
		return func(c echo.Context) error {
			claims, ok := ClaimsFrom(c)
			if !ok {
				return echo.ErrUnauthorized
			}
			if _, ok := allowed[claims.Role]; !ok {
				return echo.ErrForbidden
			}
			return next(c)
		}
	}
}

// Issue lo usa el handler de login; mismo emisor y audiencia que valida Middleware.
func Issue(secret []byte, userID, tenantID int64, role string, ttl time.Duration) (string, error) {
	now := time.Now()
	claims := Claims{
		UserID: userID, TenantID: tenantID, Role: role,
		RegisteredClaims: jwt.RegisteredClaims{
			Issuer:    issuer,
			Audience:  jwt.ClaimStrings{audience},
			Subject:   strconv.FormatInt(userID, 10),
			IssuedAt:  jwt.NewNumericDate(now),
			ExpiresAt: jwt.NewNumericDate(now.Add(ttl)),
		},
	}
	return jwt.NewWithClaims(jwt.SigningMethodHS256, claims).SignedString(secret)
}
```

Las rutas:

```go
e.POST("/auth/login", authHandler.Login) // fuera del grupo protegido

api := e.Group("/api", auth.Middleware(cfg.JWTSecret))
api.GET("/orders", orders.List)
api.POST("/orders", orders.Create)

admin := api.Group("/admin", auth.RequireRole("admin"))
admin.DELETE("/orders/:id", orders.Delete)
```

Tres decisiones que no son obvias:

- **`WithValidMethods`** cierra la puerta a tokens con `alg` distinto del que esperas; es barato y elimina una clase entera de ataques.
- **El secreto se valida al arrancar**: si `JWT_SECRET` tiene menos de 32 bytes, el proceso no arranca. Un secreto corto de HS256 se puede romper por fuerza bruta offline con un solo token capturado.
- **TTL corto** (15 minutos) y renovación con un refresh token aparte. El rol viaja en el token, así que un cambio de rol tarda como mucho un TTL en aplicarse; si eso no es aceptable para `admin`, esa ruta debe consultar el rol en la BD.""",
            },
            {
                "role": "user",
                "content": "Genial. ¿Y cómo testeo los handlers protegidos sin pasar por el login cada vez?",
            },
            {
                "role": "assistant",
                "content": r"""En dos niveles, y cada uno prueba una cosa distinta:

| Nivel | Qué prueba | Cómo obtiene la identidad |
|---|---|---|
| Handler aislado | lógica del handler (filtra por tenant, mapea errores) | claims puestos a mano en el contexto |
| Router completo | middleware JWT + roles + handler | token real firmado con un secreto de test |

Un paquete de ayudas para tests evita repetir el montaje:

```go
// internal/auth/authtest/authtest.go
package authtest

import (
	"testing"
	"time"

	"github.com/golang-jwt/jwt/v5"
	"github.com/labstack/echo/v4"

	"example.com/shop/internal/auth"
)

// SetClaims simula lo que haría el middleware, para tests de un handler aislado.
func SetClaims(c echo.Context, claims *auth.Claims) {
	c.Set(auth.ContextKey, &jwt.Token{Claims: claims, Valid: true})
}

// Token firma con el mismo código que producción; un ttl negativo da un token caducado.
func Token(t testing.TB, secret []byte, c auth.Claims, ttl time.Duration) string {
	t.Helper()
	s, err := auth.Issue(secret, c.UserID, c.TenantID, c.Role, ttl)
	if err != nil {
		t.Fatal(err)
	}
	return s
}
```

**Nivel 1: handler aislado.**

```go
func TestListOrders_UsesTenantFromToken(t *testing.T) {
	e := echo.New()
	c := e.NewContext(httptest.NewRequest(http.MethodGet, "/api/orders", nil), httptest.NewRecorder())
	authtest.SetClaims(c, &auth.Claims{UserID: 7, TenantID: 42, Role: "user"})

	store := &fakeOrders{}
	if err := orders.NewHandler(store).List(c); err != nil {
		t.Fatal(err)
	}
	if store.lastTenant != 42 {
		t.Fatalf("queried tenant %d, want 42", store.lastTenant)
	}
}
```

**Nivel 2: matriz de autenticación a través del router.**

```go
func TestAdminDelete_AuthMatrix(t *testing.T) {
	secret := []byte("test-secret-with-at-least-32-bytes!")
	e := server.New(server.Config{JWTSecret: secret}, server.Deps{Orders: &fakeOrders{}})
	admin := auth.Claims{UserID: 1, TenantID: 1, Role: "admin"}

	tests := []struct {
		name  string
		token string
		want  int
	}{
		{"sin token", "", http.StatusUnauthorized},
		{"caducado", authtest.Token(t, secret, admin, -time.Minute), http.StatusUnauthorized},
		{"otra clave", authtest.Token(t, []byte("another-secret-also-32-bytes-long!!"), admin, time.Hour), http.StatusUnauthorized},
		{"rol user", authtest.Token(t, secret, auth.Claims{UserID: 2, TenantID: 1, Role: "user"}, time.Hour), http.StatusForbidden},
		{"admin", authtest.Token(t, secret, admin, time.Hour), http.StatusNoContent},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			req := httptest.NewRequest(http.MethodDelete, "/api/admin/orders/5", nil)
			if tt.token != "" {
				req.Header.Set(echo.HeaderAuthorization, "Bearer "+tt.token)
			}
			rec := httptest.NewRecorder()
			e.ServeHTTP(rec, req)
			if rec.Code != tt.want {
				t.Fatalf("status = %d, want %d; body: %s", rec.Code, tt.want, rec.Body)
			}
		})
	}
}
```

Detalles que hacen que esto sea fiable:

- El caso «caducado» usa `-time.Minute`, más allá del *leeway* de 30 s. Con `-10*time.Second` el token seguiría siendo aceptado, la respuesta sería un 204 y parecería un bug del middleware cuando el error está en el test.
- `Token` llama a `auth.Issue`, así que emisor y audiencia son los de producción. Si alguien cambia la audiencia solo en el parser, este test lo detecta.
- La matriz vive en un solo test: cuando añadas una ruta de admin, añade una fila y no un test nuevo.

Ejecuta `go test ./internal/... -race`. Si el nivel 2 da 404 en vez de 401, la ruta no está registrada en el grupo protegido: es justo el tipo de error que este test existe para atrapar.""",
            },
        ]
    },
    # 26) Inglés: transacción con sqlc + pgx v5 en un servicio Echo; stock negativo y pedidos sin líneas.
    {
        "messages": [
            {
                "role": "user",
                "content": "In our Echo service the create-order handler runs three sqlc queries in a row: insert the order, insert the items, decrement stock. Every few days we find orders with no items, and once the stock of a product went negative. Where should the transaction live, and how do I do it with sqlc + pgx v5 without passing a tx through every layer?",
            },
            {
                "role": "assistant",
                "content": r"""You have two separate bugs, and a transaction only fixes the first one.

1. **Orders without items: no transaction.** Each query auto-commits. If anything fails after the first insert (the client disconnects and `ctx` is canceled, an item insert hits a constraint, a deploy kills the pod) the order stays and the items never arrive.
2. **Negative stock: check-then-act.** If the code reads the stock, compares in Go and then runs `UPDATE ... SET stock = stock - n`, two concurrent requests can both pass the check. A transaction at the default `READ COMMITTED` level does not prevent that. The fix is to make the check and the write **one statement**.

### Where the transaction goes

In the **service** (the use case). The transaction boundary is a business decision, "placing an order is all or nothing", so it belongs where that rule lives. The handler should not know SQL exists, and a per-table repository cannot see the whole operation.

### Queries

```sql
-- name: CreateOrder :one
INSERT INTO orders (customer_id, status)
VALUES ($1, 'pending')
RETURNING *;

-- name: TakeStock :one
-- Check and decrement in one statement: no row back means not enough stock.
UPDATE products
SET stock = stock - @quantity
WHERE id = @product_id AND stock >= @quantity
RETURNING price_cents;

-- name: AddOrderItem :exec
INSERT INTO order_items (order_id, product_id, quantity, unit_price_cents)
VALUES ($1, $2, $3, $4);
```

Also add `CHECK (stock >= 0)` to `products`. It is the last line of defense if someone writes a different query tomorrow.

### A store that hands out transactional queries

sqlc generates `WithTx`, so the transaction never leaks into your function signatures:

```go
package store

import (
	"context"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"example.com/shop/internal/db"
)

type Store struct {
	pool *pgxpool.Pool
	q    *db.Queries
}

func New(pool *pgxpool.Pool) *Store { return &Store{pool: pool, q: db.New(pool)} }

// Queries is for single statements that need no transaction.
func (s *Store) Queries() *db.Queries { return s.q }

// InTx commits if fn returns nil and rolls back otherwise, including on panic.
func (s *Store) InTx(ctx context.Context, fn func(q *db.Queries) error) error {
	return pgx.BeginFunc(ctx, s.pool, func(tx pgx.Tx) error {
		return fn(s.q.WithTx(tx))
	})
}
```

### The use case

```go
package orders

import (
	"cmp"
	"context"
	"errors"
	"fmt"
	"slices"

	"github.com/jackc/pgx/v5"

	"example.com/shop/internal/db"
	"example.com/shop/internal/store"
)

var ErrOutOfStock = errors.New("out of stock")

type Line struct {
	ProductID int64
	Quantity  int32
}

type Service struct{ store *store.Store }

func NewService(s *store.Store) *Service { return &Service{store: s} }

func (s *Service) PlaceOrder(ctx context.Context, customerID int64, lines []Line) (db.Order, error) {
	lines = normalize(lines)
	var order db.Order
	err := s.store.InTx(ctx, func(q *db.Queries) error {
		var err error
		if order, err = q.CreateOrder(ctx, customerID); err != nil {
			return fmt.Errorf("create order: %w", err)
		}
		for _, l := range lines {
			price, err := q.TakeStock(ctx, db.TakeStockParams{ProductID: l.ProductID, Quantity: l.Quantity})
			if errors.Is(err, pgx.ErrNoRows) {
				// Missing product lands here too; "unavailable" is the right answer for both.
				return fmt.Errorf("product %d: %w", l.ProductID, ErrOutOfStock)
			}
			if err != nil {
				return fmt.Errorf("take stock: %w", err)
			}
			if err := q.AddOrderItem(ctx, db.AddOrderItemParams{
				OrderID: order.ID, ProductID: l.ProductID, Quantity: l.Quantity, UnitPriceCents: price,
			}); err != nil {
				return fmt.Errorf("add item: %w", err)
			}
		}
		return nil
	})
	if err != nil {
		return db.Order{}, err
	}
	return order, nil
}

// normalize merges duplicate products and sorts by ID, so concurrent orders lock
// product rows in the same order and cannot deadlock each other.
func normalize(lines []Line) []Line {
	qty := make(map[int64]int32, len(lines))
	for _, l := range lines {
		qty[l.ProductID] += l.Quantity
	}
	out := make([]Line, 0, len(qty))
	for id, n := range qty {
		out = append(out, Line{ProductID: id, Quantity: n})
	}
	slices.SortFunc(out, func(a, b Line) int { return cmp.Compare(a.ProductID, b.ProductID) })
	return out
}
```

The sort is not cosmetic: order A locks product 1 then 2, order B locks 2 then 1, and Postgres aborts one with `deadlock detected` (SQLSTATE `40P01`). Same lock order, no cycle.

### The handler only translates

```go
func (h *Handler) Create(c echo.Context) error {
	claims, ok := auth.ClaimsFrom(c)
	if !ok {
		return echo.ErrUnauthorized
	}
	var req createOrderRequest
	if err := c.Bind(&req); err != nil {
		return err
	}
	if err := c.Validate(&req); err != nil {
		return err
	}
	order, err := h.orders.PlaceOrder(c.Request().Context(), claims.UserID, req.Lines())
	if errors.Is(err, orders.ErrOutOfStock) {
		return echo.NewHTTPError(http.StatusConflict, "some products are out of stock")
	}
	if err != nil {
		return err
	}
	return c.JSON(http.StatusCreated, orderResponse{ID: order.ID, Status: order.Status})
}
```

### Proving both fixes

These need a real Postgres; a mock cannot show atomicity or row locks.

```go
func TestPlaceOrder_AllOrNothing(t *testing.T) {
	pool := testPool(t)
	ctx := context.Background()
	mustExec(t, pool, `INSERT INTO products (id, price_cents, stock) VALUES (1, 500, 10), (2, 900, 0)`)

	_, err := orders.NewService(store.New(pool)).PlaceOrder(ctx, 42,
		[]orders.Line{{ProductID: 1, Quantity: 2}, {ProductID: 2, Quantity: 1}})
	if !errors.Is(err, orders.ErrOutOfStock) {
		t.Fatalf("err = %v, want ErrOutOfStock", err)
	}
	var nOrders, stock int
	if err := pool.QueryRow(ctx, `SELECT count(*) FROM orders WHERE customer_id = 42`).Scan(&nOrders); err != nil {
		t.Fatal(err)
	}
	if err := pool.QueryRow(ctx, `SELECT stock FROM products WHERE id = 1`).Scan(&stock); err != nil {
		t.Fatal(err)
	}
	if nOrders != 0 || stock != 10 {
		t.Fatalf("partial write: orders=%d stock=%d", nOrders, stock)
	}
}

func TestPlaceOrder_LastUnitIsSoldOnce(t *testing.T) {
	pool := testPool(t)
	mustExec(t, pool, `INSERT INTO products (id, price_cents, stock) VALUES (1, 500, 1)`)
	svc := orders.NewService(store.New(pool))

	var wg sync.WaitGroup
	var sold atomic.Int32
	for i := range 20 {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_, err := svc.PlaceOrder(context.Background(), int64(i), []orders.Line{{ProductID: 1, Quantity: 1}})
			if err == nil {
				sold.Add(1)
			}
		}()
	}
	wg.Wait()
	if sold.Load() != 1 {
		t.Fatalf("sold %d times, want exactly 1", sold.Load())
	}
}

func testPool(t *testing.T) *pgxpool.Pool {
	t.Helper()
	dsn := os.Getenv("TEST_DATABASE_URL")
	if dsn == "" {
		t.Skip("TEST_DATABASE_URL not set")
	}
	pool, err := pgxpool.New(context.Background(), dsn)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(pool.Close)
	mustExec(t, pool, `TRUNCATE order_items, orders, products RESTART IDENTITY`)
	return pool
}

func mustExec(t *testing.T, pool *pgxpool.Pool, sql string) {
	t.Helper()
	if _, err := pool.Exec(context.Background(), sql); err != nil {
		t.Fatal(err)
	}
}
```

Run the second test against your old code first: it should report `sold` greater than 1. That confirms the diagnosis before you trust the fix.""",
            },
        ]
    },
    # ---------------------------------------------------------------- Fiber (4)
    # 27) Fiber: cuándo no usarlo; y si ya está en producción, qué reglas poner (multiturno, system exacto).
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Voy a arrancar una API nueva y vi benchmarks donde Fiber le saca muchísimo a Gin y a net/http. ¿Lo elijo?",
            },
            {
                "role": "assistant",
                "content": r"""No lo elijas por esos benchmarks. Fiber no es «Gin pero más rápido»: está construido sobre **fasthttp** en vez de `net/http`, y esa decisión trae costes que un benchmark de «hello world» no enseña.

### Qué cambia de verdad

| | net/http (chi, Gin, Echo) | Fiber v2 (fasthttp) |
|---|---|---|
| Compatibilidad con `http.Handler` | total | no; adaptador que convierte cada petición |
| Middlewares del ecosistema (OpenTelemetry, Prometheus, CORS) | se usan tal cual | versiones propias de Fiber o adaptador |
| HTTP/2 en el servidor | sí (con TLS; h2c desde Go 1.24 con `Server.Protocols`) | no; necesitas un proxy delante que lo termine |
| Cancelación si el cliente se desconecta | `r.Context()` se cancela | `c.UserContext()` es `context.Background()` salvo que tú pongas otro; no se cancela |
| Vida de los valores de la petición | strings normales | `c.Params`, `c.Query`, `c.Body`, etc. apuntan a buffers reutilizados; solo valen dentro del handler (salvo `Immutable: true`) |
| Tests | `httptest.NewRecorder` | `app.Test(req)` |
| Estilo de API | idiomático Go | inspirado en Express |

Las dos filas que más duelen en producción son la cancelación (una consulta lenta sigue ocupando una conexión de la BD aunque el móvil ya se haya ido) y la vida de los valores (bugs de datos cruzados entre peticiones que solo aparecen con carga).

### Dónde se va el tiempo de tu API

Cuenta rápida para un endpoint típico: parsear y validar JSON, una consulta a Postgres de 1-5 ms, serializar. La diferencia de sobrecoste entre routers está en el orden de **microsegundos** por petición. Si Fiber te ahorra 15 µs sobre 2 ms de BD, has ganado menos de un 1 % de latencia a cambio de salirte del ecosistema estándar. Los benchmarks miden justo la parte que en tu caso no importa.

### Cuándo sí tiene sentido

- El equipo viene de Express y la API de Fiber le ahorra fricción real.
- Un servicio casi sin I/O (un gateway, un servicio de caché en memoria) donde **has medido** que `net/http` es el cuello de botella.

Para una API de negocio con base de datos, mi elección por defecto es `net/http` con chi, o Gin si el equipo ya lo conoce.

### Cómo decidir con datos y no con benchmarks ajenos

Implementa un endpoint real (con su consulta) en los dos y lanza la misma carga con k6 o `hey`. Compara p99 y CPU por petición, y mira un perfil (`go tool pprof`): si el router no aparece entre las primeras funciones, la decisión no depende del rendimiento.""",
            },
            {
                "role": "user",
                "content": "Entendido para lo nuevo. Pero ya tenemos dos servicios en Fiber v2 en producción y no los vamos a reescribir. ¿Qué reglas ponemos para no pisar esas minas?",
            },
            {
                "role": "assistant",
                "content": r"""Seis reglas, casi todas en la configuración del `fiber.App` para que no dependan de la memoria de cada persona:

```go
package server

import (
	"context"
	"time"

	"github.com/gofiber/fiber/v2"
	fiberrecover "github.com/gofiber/fiber/v2/middleware/recover"
)

func New(deps Deps) *fiber.App {
	app := fiber.New(fiber.Config{
		Immutable:    true,             // 1. los valores de la petición son copias seguras
		ReadTimeout:  10 * time.Second, // 2. por defecto no hay límite
		WriteTimeout: 30 * time.Second,
		IdleTimeout:  60 * time.Second,
		BodyLimit:    1 << 20,          // 3. 1 MiB explícito (por defecto son 4 MiB)
		ErrorHandler: errorHandler,     // 4. un único sitio decide status y forma del error
		// Prefork se queda en false: se escala con réplicas, no con procesos dentro del pod.
	})
	app.Use(fiberrecover.New())
	app.Use(requestContext(5 * time.Second)) // 5. contexto con plazo en cada petición
	registerRoutes(app, deps)
	return app
}

// requestContext da a cada petición un contexto con timeout, porque fasthttp
// no cancela nada cuando el cliente se desconecta.
func requestContext(timeout time.Duration) fiber.Handler {
	return func(c *fiber.Ctx) error {
		ctx, cancel := context.WithTimeout(c.UserContext(), timeout)
		defer cancel()
		c.SetUserContext(ctx)
		return c.Next()
	}
}
```

Y las reglas de código que acompañan a esa configuración:

1. **`Immutable: true` por defecto.** Cuesta una asignación por cada valor que lees; en un servicio con base de datos no se nota. Si un perfil algún día dice lo contrario, se desactiva en ese servicio sabiendo lo que implica, y entonces cualquier valor que sobreviva al handler se copia con `utils.CopyString` o `strings.Clone`.
2. **Timeouts del servidor explícitos.** Sin `ReadTimeout`, un cliente lento retiene una conexión indefinidamente.
3. **Límite de cuerpo explícito**, ajustado al endpoint más grande que tengáis.
4. **Los handlers devuelven `error`** (`fiber.NewError` o errores de dominio) y nunca escriben respuestas de error a mano.
5. **Siempre `c.UserContext()` hacia abajo**: a pgx, a clientes HTTP, a todo. Nunca `context.Background()` en un handler, y nunca `c.Context()`, que en v2 es el `*fasthttp.RequestCtx`.
6. **`c` jamás sale del handler**: ni a goroutines, ni a structs que vivan más, ni a canales. Si una tarea necesita datos de la petición, se copian a un struct propio antes de lanzarla.

Para que se cumplan, ponlas en la plantilla de PR y añade un test por servicio que cree la app con `server.New` y compruebe `app.Config().Immutable` y los timeouts: si alguien toca la config, falla. Y para observabilidad, usa los middlewares de `gofiber/contrib` (hay uno de OpenTelemetry) en vez de adaptar los de `net/http`, que convierten cada petición.

Si dentro de un año alguno de esos servicios necesita una reescritura grande por otras razones, ese es el momento de pasarlo a `net/http`; antes, no compensa.""",
            },
        ]
    },
    # 28) Fiber: claves de un map que "cambian solas" por buffers reutilizados (usuario trae código y síntoma).
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Fiber v2. Tenemos un endpoint que registra el último acceso de cada dispositivo en un map en memoria (con mutex) y otro que lo lista. En producción el listado trae claves rarísimas: `ice-7f3a` en vez de `device-7f3a`, trozos de otras URLs como `ders?page=2`, y a veces la misma clave dos veces. En los tests no pasa nunca. ¿Será el mutex?

```go
type Tracker struct {
	mu       sync.Mutex
	lastSeen map[string]time.Time
}

func (t *Tracker) Touch(c *fiber.Ctx) error {
	id := c.Params("deviceId")
	t.mu.Lock()
	t.lastSeen[id] = time.Now()
	t.mu.Unlock()
	return c.SendStatus(fiber.StatusNoContent)
}

func (t *Tracker) List(c *fiber.Ctx) error {
	t.mu.Lock()
	defer t.mu.Unlock()
	return c.JSON(t.lastSeen)
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""No es el mutex, y el propio síntoma lo descarta. Un mutex mal usado produce lecturas inconsistentes o un `fatal error: concurrent map writes`, pero no puede **cambiar el texto de una clave** después de insertarla. Que `device-7f3a` acabe siendo `ice-7f3a` o `ders?page=2` (un trozo de otra URL) significa que la memoria de la clave se reescribió por debajo. En Fiber eso tiene una causa conocida.

### Diagnóstico

Fiber v2 no copia los valores de la petición. `c.Params`, `c.Query`, `c.Get`, `c.Body` y compañía convierten el `[]byte` del buffer interno a `string` **sin asignar memoria nueva**. Cuando el handler termina, el contexto y sus buffers vuelven a un pool y se reutilizan para la siguiente petición. Tu map conserva un `string` que apunta a ese buffer, así que su contenido pasa a ser lo que escriba la petición siguiente.

Una clave que cambia después de insertarse rompe el propio map: sigue guardada en el *bucket* que correspondía a su hash original, pero con otro contenido. De ahí los duplicados (la clave «nueva» se inserta en otro bucket) y las búsquedas que no encuentran claves que sí están.

Por qué no lo ven los tests: con una o dos peticiones por test, el buffer no llega a reutilizarse antes de que leáis el map.

### Arreglo

El cambio mínimo es copiar lo que sobrevive al handler:

```go
import "github.com/gofiber/fiber/v2/utils"

func (t *Tracker) Touch(c *fiber.Ctx) error {
	// La clave vive en el map más allá de esta petición: necesita su propia memoria.
	id := utils.CopyString(c.Params("deviceId"))
	t.mu.Lock()
	t.lastSeen[id] = time.Now()
	t.mu.Unlock()
	return c.SendStatus(fiber.StatusNoContent)
}
```

`strings.Clone` (Go 1.20+) hace lo mismo sin depender de Fiber.

Y la medida de fondo, para que el siguiente caso no exista: `fiber.New(fiber.Config{Immutable: true})`. Con eso todos los valores son copias; cuesta una asignación por acceso, irrelevante en un servicio con BD. Haría las dos cosas: el arreglo puntual ya, y `Immutable` en la config del servicio.

Además, después de desplegar, **reiniciad el proceso**: el map actual ya está corrupto y no se arregla solo.

### Dónde más buscar

El mismo patrón aparece en cualquier valor de la petición que sobreviva al handler. Revisad:

- Caches o maps en memoria cuya clave o valor salga de `c.Params`, `c.Query`, `c.Get`, `c.Cookies`.
- `c.Body()` guardado o enviado a un canal: es un `[]byte` del buffer, no una copia. (`c.BodyParser` sí es seguro: `encoding/json` crea strings nuevos al decodificar.)
- Goroutines que capturan `c` o esos valores.
- Logs asíncronos que reciben el string sin copiar.

### Test de regresión

Muchas peticiones seguidas sobre la misma app fuerzan la reutilización del contexto:

```go
func TestTracker_KeysSurviveLaterRequests(t *testing.T) {
	tr := &Tracker{lastSeen: map[string]time.Time{}}
	app := fiber.New() // sin Immutable a propósito: el test protege el código, no la config
	app.Post("/devices/:deviceId/touch", tr.Touch)

	const n = 500
	for i := range n {
		req := httptest.NewRequest(http.MethodPost, fmt.Sprintf("/devices/device-%04x/touch", i), nil)
		resp, err := app.Test(req, -1)
		if err != nil {
			t.Fatal(err)
		}
		resp.Body.Close()
	}

	tr.mu.Lock()
	defer tr.mu.Unlock()
	if len(tr.lastSeen) != n {
		t.Fatalf("got %d keys, want %d", len(tr.lastSeen), n)
	}
	for k := range tr.lastSeen {
		if !strings.HasPrefix(k, "device-") || len(k) != len("device-0000") {
			t.Fatalf("corrupted key %q", k)
		}
	}
}
```

Ejecutadlo primero contra el código original: debe fallar con claves corruptas o con menos de 500 claves. Si falla, el diagnóstico queda confirmado; después aplicad la copia y tiene que pasar con `go test -count=5`.""",
            },
        ]
    },
    # 29) Fiber: probar handlers con app.Test; después timeouts de app.Test en CI (multiturno, principiante).
    {
        "messages": [
            {
                "role": "user",
                "content": "Vengo de net/http y ahora estoy en un proyecto con Fiber v2. ¿Cómo pruebo los handlers si no hay `httptest.NewRecorder`?",
            },
            {
                "role": "assistant",
                "content": r"""Con `app.Test`. Recibe un `*http.Request` normal (el de `httptest.NewRequest` te sirve) y devuelve un `*http.Response`. Por dentro levanta el servidor de fasthttp sobre una conexión en memoria, así que la petición pasa por los middlewares, el router y el `ErrorHandler`, igual que en producción.

La clave es construir la app **con la misma función que usa `main`**. Si en el test haces `fiber.New()` a pelo, pierdes el `ErrorHandler` y los errores salen como texto plano en vez de tu JSON.

```go
// internal/server/server.go
package server

import (
	"errors"

	"github.com/gofiber/fiber/v2"

	"example.com/shop/internal/catalog"
	"example.com/shop/internal/domain"
)

type Deps struct {
	Products *catalog.Handler
}

func New(deps Deps) *fiber.App {
	app := fiber.New(fiber.Config{ErrorHandler: errorHandler})
	app.Get("/api/products/:id", deps.Products.Get)
	return app
}

func errorHandler(c *fiber.Ctx, err error) error {
	status, code := fiber.StatusInternalServerError, "internal"
	var fe *fiber.Error
	switch {
	case errors.As(err, &fe):
		status, code = fe.Code, "http_error"
	case errors.Is(err, domain.ErrNotFound):
		status, code = fiber.StatusNotFound, "not_found"
	}
	return c.Status(status).JSON(fiber.Map{"code": code})
}
```

El handler:

```go
func (h *Handler) Get(c *fiber.Ctx) error {
	id, err := c.ParamsInt("id")
	if err != nil || id <= 0 {
		return fiber.NewError(fiber.StatusBadRequest, "id inválido")
	}
	p, err := h.repo.Get(c.UserContext(), int64(id))
	if err != nil {
		return err // domain.ErrNotFound → 404 en errorHandler
	}
	return c.JSON(p)
}
```

Y el test, en tabla como harías con `net/http`:

```go
func TestGetProduct(t *testing.T) {
	repo := &fakeRepo{items: map[int64]catalog.Product{1: {ID: 1, Name: "Teclado"}}}
	app := server.New(server.Deps{Products: catalog.NewHandler(repo)})

	tests := []struct {
		name       string
		path       string
		wantStatus int
		wantBody   string
	}{
		{"existe", "/api/products/1", http.StatusOK, `"name":"Teclado"`},
		{"no existe", "/api/products/2", http.StatusNotFound, `"code":"not_found"`},
		{"id no numérico", "/api/products/abc", http.StatusBadRequest, `"code":"http_error"`},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			resp, err := app.Test(httptest.NewRequest(http.MethodGet, tt.path, nil))
			if err != nil {
				t.Fatal(err)
			}
			defer resp.Body.Close()
			body, err := io.ReadAll(resp.Body)
			if err != nil {
				t.Fatal(err)
			}
			if resp.StatusCode != tt.wantStatus {
				t.Fatalf("status = %d, want %d; body: %s", resp.StatusCode, tt.wantStatus, body)
			}
			if !strings.Contains(string(body), tt.wantBody) {
				t.Errorf("body = %s, want substring %s", body, tt.wantBody)
			}
		})
	}
}
```

El `fakeRepo` devuelve `domain.ErrNotFound` cuando el ID no está en el map. Diferencias con lo que conoces: no hay `ResponseRecorder` que inspeccionar, lees un `*http.Response` como si fueras un cliente, y por eso debes cerrar el cuerpo. A cambio, cada test cubre el camino completo.""",
            },
            {
                "role": "user",
                "content": "Funciona. Pero los tests de endpoints que van contra la base de datos de test a veces fallan en CI con un error de timeout de `app.Test`. En local nunca.",
            },
            {
                "role": "assistant",
                "content": r"""Es el timeout por defecto de `app.Test` en Fiber v2: **1 segundo**. Si el handler tarda más (en CI la BD comparte máquina con todo lo demás y la primera consulta tiene que calentar caches y conexiones), `app.Test` deja de esperar y devuelve un error, aunque el handler siga corriendo y acabe respondiendo bien.

El parámetro opcional es el timeout en milisegundos; `-1` lo desactiva. Yo no usaría `-1`: si un handler se queda colgado, el test esperaría hasta el `-timeout` de `go test` (10 minutos por defecto) y el fallo sería mucho menos claro. Mejor un límite generoso y explícito en un helper:

```go
const testRequestTimeout = 10 * time.Second

func doRequest(t *testing.T, app *fiber.App, req *http.Request) (*http.Response, []byte) {
	t.Helper()
	resp, err := app.Test(req, int(testRequestTimeout.Milliseconds()))
	if err != nil {
		t.Fatalf("%s %s: %v", req.Method, req.URL.Path, err)
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		t.Fatal(err)
	}
	return resp, body
}
```

Con eso, cada test queda en dos líneas y el timeout vive en un solo sitio.

Dos comprobaciones para no tapar un problema real con un número más alto:

1. **Mide cuánto tardan de verdad** en CI: `go test -v -run TestOrders ./...` imprime la duración de cada subtest. Si están en 1,2 s, el timeout era el problema. Si alguno anda por 8 s, hay algo lento que investigar (una migración por test, un pool nuevo por test, una consulta sin índice).
2. **Comparte el pool entre tests.** Crear un `pgxpool` y migrar en cada test es la causa más habitual de esa lentitud. Crea el pool una vez en `TestMain` y limpia con `TRUNCATE` entre tests.

Si en el futuro migráis a Fiber v3, la firma cambia: `app.Test` recibe un `fiber.TestConfig` con un `time.Duration` en vez de un entero de milisegundos. Con el helper, ese cambio se hace en una línea.""",
            },
        ]
    },
    # 30) Fiber: Prefork multiplica pools y rate limiters; "too many clients" (usuario trae error).
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Activamos `Prefork: true` en Fiber para aprovechar los 8 núcleos del servidor y al rato Postgres empezó a rechazar conexiones:

```
failed to connect to `user=shop database=shop`: 10.0.3.4:5432 (db.internal): server error: FATAL: sorry, too many clients already (SQLSTATE 53300)
```

El pool de pgx lo tenemos con `MaxConns = 25` y son 3 réplicas. Además, el rate limiter (el middleware `limiter` con almacenamiento en memoria) parece estar dejando pasar más peticiones de las configuradas. ¿Eso tiene que ver o son dos problemas distintos?""",
            },
            {
                "role": "assistant",
                "content": r"""Es el mismo problema. **Prefork no reparte un proceso entre núcleos: arranca un proceso hijo por núcleo**, y cada hijo ejecuta tu `main` desde el principio, con su propia copia de todo lo que se inicializa ahí.

### La cuenta

- Antes: 3 réplicas × 1 proceso × 25 conexiones = **75** como máximo.
- Ahora: 3 réplicas × 8 hijos × 25 = **600**, más las del proceso padre, que también ejecuta `main` hasta llegar a `app.Listen` (si hace `pool.Ping`, ya tiene una conexión abierta).

El `max_connections` por defecto de Postgres es 100. Encaja con lo que ves: va bien un rato y, cuando los pools de los hijos crecen con la carga, Postgres empieza a rechazar.

El rate limiter es la misma historia: cada hijo tiene su propio contador en memoria, y el kernel reparte las conexiones entre los 8 (con `SO_REUSEPORT`). Un cliente puede llegar a hacer hasta 8 veces el límite configurado por réplica.

Revisa también si tu `main` hace algo más que ahora ocurre 8 veces por réplica: migraciones al arrancar (8 procesos a la vez contra el mismo esquema), un cron o un worker en segundo plano (cada tarea se ejecuta 8 veces), caches en memoria (8 copias que además no coinciden entre sí).

### Por qué Prefork casi nunca compensa en Go

Prefork viene de entornos con un hilo por proceso (Node, Python), donde es la forma de usar varios núcleos. El runtime de Go ya reparte las goroutines entre todos los núcleos disponibles (`GOMAXPROCS`), así que un solo proceso los aprovecha. La ganancia que suele medirse es marginal y no compensa multiplicar todo el estado por proceso.

Un detalle de contenedores: antes de Go 1.25, `GOMAXPROCS` tomaba los núcleos del host e ignoraba el límite de CPU del contenedor (para eso existía `go.uber.org/automaxprocs`). Desde Go 1.25 respeta el límite del cgroup. Con Prefork y 8 hijos en un pod limitado a 2 CPU tienes, además, contención.

### Arreglo

1. **`Prefork: false`** y escala con réplicas, que es lo que tu orquestador ya sabe hacer.
2. **El tamaño del pool es un presupuesto global**, no un número por servicio: `(max_connections − reserva para admin y migraciones) / réplicas`. Con 100, reservando 10 y 3 réplicas, salen 30 por réplica; tu `25` está bien una vez quitado Prefork. Hazlo configurable:

```go
func newPool(ctx context.Context, dsn string, maxConns int32) (*pgxpool.Pool, error) {
	cfg, err := pgxpool.ParseConfig(dsn)
	if err != nil {
		return nil, fmt.Errorf("parse dsn: %w", err)
	}
	cfg.MaxConns = maxConns // presupuesto por réplica, viene de la configuración
	cfg.MinConns = 2
	cfg.MaxConnIdleTime = 5 * time.Minute
	cfg.MaxConnLifetime = 30 * time.Minute
	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		return nil, fmt.Errorf("create pool: %w", err)
	}
	if err := pool.Ping(ctx); err != nil {
		pool.Close()
		return nil, fmt.Errorf("ping db: %w", err)
	}
	return pool, nil
}
```

3. **El rate limiter necesita estado compartido** aunque quites Prefork, porque tienes 3 réplicas: con contadores en memoria, el límite real es 3 veces el configurado. El middleware acepta cualquier `fiber.Storage`; usa el de Redis del repositorio `gofiber/storage`:

```go
func rateLimit(storage fiber.Storage) fiber.Handler {
	return limiter.New(limiter.Config{
		Max:          100,
		Expiration:   time.Minute,
		Storage:      storage, // compartido entre réplicas
		KeyGenerator: func(c *fiber.Ctx) string { return c.IP() },
		LimitReached: func(c *fiber.Ctx) error {
			return c.Status(fiber.StatusTooManyRequests).JSON(fiber.Map{"code": "rate_limited"})
		},
	})
}
```

Si hay un balanceador delante, `c.IP()` devuelve la IP del balanceador: configura `ProxyHeader`, `EnableTrustedProxyCheck` y `TrustedProxies` en `fiber.Config`, o todos los clientes compartirán un único contador.

4. Si más adelante necesitas más conexiones de las que Postgres soporta, la respuesta es PgBouncer en modo *transaction*, no subir `max_connections`. Con PgBouncer anterior a 1.21 (sin soporte de *prepared statements* en ese modo), añade `default_query_exec_mode=simple_protocol` al DSN de pgx.

### Verificación

Pon `application_name=shop-api` en el DSN y, antes y después del cambio:

```sql
SELECT application_name, count(*) AS conns
FROM pg_stat_activity
GROUP BY application_name
ORDER BY conns DESC;
```

Con Prefork verás cifras de cientos; sin él, como mucho 3 × 25. Para el limiter, lanza 150 peticiones en un minuto desde una IP: deben volver al menos 50 respuestas `429`, repartidas entre réplicas como estén.""",
            },
        ]
    },
]
