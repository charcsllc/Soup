"""04_frameworks / 09: Spring Boot 3.x (Java 21) y Kotlin: Ktor 3 y Spring con Kotlin (reparto 20 / 10)."""

SISTEMA = (
    "Eres un asistente experto en programación, análisis y razonamiento. Respondes en el "
    "idioma del usuario (español por defecto), con precisión y sin relleno, y verificas tu "
    "trabajo antes de responder."
)

ROWS = [
    # ---------------------------------------------------------------- Spring Boot (20)
    # 1) Proyecto Spring Boot 3: starters, estructura por funcionalidad, @RestController con records (system exacto).
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Arranco una API REST con Spring Boot 3 y Java 21 contra Postgres. ¿Qué starters pongo y cómo organizo los paquetes para que no acabe siendo controller/service/repository con 40 clases en cada carpeta?",
            },
            {
                "role": "assistant",
                "content": r"""Organiza **por funcionalidad**, no por capa. Cada paquete agrupa todo lo de un concepto de negocio y expone lo mínimo; las clases internas pueden ser *package-private* y Spring las encuentra igual.

```
com.acme.shop
  ShopApplication.java
  catalog/
    Product.java                 // entidad JPA (package-private)
    ProductRepository.java
    ProductService.java          // pública: la usan otros módulos
    ProductController.java
    CreateProductRequest.java    // records públicos de entrada y salida
    ProductResponse.java
    ProductNotFoundException.java
  orders/
    ...
  shared/
    ApiExceptionHandler.java     // @RestControllerAdvice
```

### Starters (Maven, Boot 3.4)

```xml
<dependencies>
  <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-web</artifactId></dependency>
  <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-validation</artifactId></dependency>
  <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-data-jpa</artifactId></dependency>
  <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-actuator</artifactId></dependency>
  <dependency><groupId>org.flywaydb</groupId><artifactId>flyway-core</artifactId></dependency>
  <dependency><groupId>org.flywaydb</groupId><artifactId>flyway-database-postgresql</artifactId></dependency>
  <dependency><groupId>org.postgresql</groupId><artifactId>postgresql</artifactId><scope>runtime</scope></dependency>

  <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-starter-test</artifactId><scope>test</scope></dependency>
  <dependency><groupId>org.springframework.boot</groupId><artifactId>spring-boot-testcontainers</artifactId><scope>test</scope></dependency>
  <dependency><groupId>org.testcontainers</groupId><artifactId>postgresql</artifactId><scope>test</scope></dependency>
</dependencies>
```

Sin versiones: las gestiona el parent de Spring Boot. `flyway-database-postgresql` es necesario desde Flyway 10, que separó el soporte de cada base de datos en su propio módulo.

### Un módulo completo

```java
// catalog/Product.java
@Entity
@Table(name = "products")
class Product {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 120)
    private String name;

    @Column(name = "price_cents", nullable = false)
    private long priceCents;

    @Column(nullable = false, unique = true, length = 8)
    private String sku;

    protected Product() {
        // requerido por JPA
    }

    Product(String name, long priceCents, String sku) {
        this.name = name;
        this.priceCents = priceCents;
        this.sku = sku;
    }

    Long getId() { return id; }
    String getName() { return name; }
    long getPriceCents() { return priceCents; }
    String getSku() { return sku; }
}
```

```java
// catalog/CreateProductRequest.java
public record CreateProductRequest(
        @NotBlank @Size(max = 120) String name,
        @NotNull @Positive Long priceCents,
        @NotBlank @Pattern(regexp = "[A-Z0-9]{8}") String sku) {
}
```

```java
// catalog/ProductResponse.java
public record ProductResponse(long id, String name, long priceCents, String sku) {
    static ProductResponse from(Product p) {
        return new ProductResponse(p.getId(), p.getName(), p.getPriceCents(), p.getSku());
    }
}
```

```java
// catalog/ProductService.java
@Service
@Transactional(readOnly = true)
public class ProductService {
    private final ProductRepository products;

    ProductService(ProductRepository products) {
        this.products = products;
    }

    public ProductResponse get(long id) {
        return products.findById(id)
                .map(ProductResponse::from)
                .orElseThrow(() -> new ProductNotFoundException(id));
    }

    @Transactional
    public ProductResponse create(CreateProductRequest request) {
        Product saved = products.save(new Product(request.name(), request.priceCents(), request.sku()));
        return ProductResponse.from(saved);
    }
}
```

```java
// catalog/ProductController.java
@RestController
@RequestMapping("/api/products")
class ProductController {
    private final ProductService service;

    ProductController(ProductService service) {
        this.service = service;
    }

    @GetMapping("/{id}")
    ProductResponse get(@PathVariable long id) {
        return service.get(id);
    }

    @PostMapping
    ResponseEntity<ProductResponse> create(@Valid @RequestBody CreateProductRequest request,
                                           UriComponentsBuilder uri) {
        ProductResponse created = service.create(request);
        return ResponseEntity.created(uri.path("/api/products/{id}").build(created.id())).body(created);
    }
}
```

`ProductRepository` es `interface ProductRepository extends JpaRepository<Product, Long> {}`.

### `application.yml` mínimo

```yaml
spring:
  datasource:
    url: ${DATABASE_URL:jdbc:postgresql://localhost:5432/shop}
    username: ${DATABASE_USER:shop}
    password: ${DATABASE_PASSWORD:shop}
  jpa:
    open-in-view: false
    hibernate:
      ddl-auto: validate
```

### Las decisiones y su porqué

- **Records como DTO, entidad aparte.** La entidad nunca sale por HTTP: así un campo nuevo en la tabla no aparece solo en tu API y no expones relaciones *lazy* que revientan al serializar.
- **Inyección por constructor**, sin `@Autowired`: con un único constructor Spring lo usa solo, y las dependencias quedan `final` y visibles.
- **`ddl-auto: validate` + Flyway.** El esquema lo definen las migraciones versionadas (`src/main/resources/db/migration/V1__products.sql`); Hibernate solo comprueba que las entidades encajan y falla al arrancar si no.
- **`open-in-view: false`.** Por defecto está activado y mantiene la sesión de Hibernate abierta durante toda la petición, lo que esconde consultas *lazy* hasta producción. Desactivarlo te obliga a cargar los datos en el servicio, que es donde debe pasar.
- **`@Transactional(readOnly = true)` en la clase** y `@Transactional` en los métodos que escriben: las lecturas evitan el *dirty checking* y la intención queda escrita.

### Comprobación

`./mvnw spring-boot:run` con un Postgres local, y:

```bash
curl -i -X POST localhost:8080/api/products \
  -H 'Content-Type: application/json' \
  -d '{"name":"Teclado","priceCents":4999,"sku":"KEYB0001"}'
# HTTP/1.1 201, cabecera Location: http://localhost:8080/api/products/1
```

Si arranca y la migración ha creado la tabla, `validate` habrá pasado: es tu primera prueba de que entidades y esquema coinciden.""",
            },
        ]
    },
    # 2) Inyección por constructor vs @Autowired en campo; después prototype dentro de singleton (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": "En el proyecto hay `@Autowired` en campos por todos lados y un compañero dice que hay que pasar todo a inyección por constructor. ¿Es solo una cuestión de estilo?",
            },
            {
                "role": "assistant",
                "content": r"""No es estilo: cambia qué puedes garantizar sobre el objeto y cómo lo pruebas.

```java
// Antes: dependencias ocultas, mutables y nulas fuera de Spring
@Service
public class InvoiceService {
    @Autowired private InvoiceRepository invoices;
    @Autowired private TaxCalculator taxes;
    @Autowired private Clock clock;
}

// Después
@Service
public class InvoiceService {
    private final InvoiceRepository invoices;
    private final TaxCalculator taxes;
    private final Clock clock;

    public InvoiceService(InvoiceRepository invoices, TaxCalculator taxes, Clock clock) {
        this.invoices = invoices;
        this.taxes = taxes;
        this.clock = clock;
    }
}
```

Lo que ganas, en orden de importancia:

1. **Se prueba sin Spring.** `new InvoiceService(fakeRepo, new TaxCalculator(), Clock.fixed(...))` en un test JUnit normal, que tarda milisegundos. Con inyección en campo necesitas reflexión o levantar el contexto.
2. **El objeto nunca existe a medio construir.** Los campos son `final`; no hay forma de tener un `InvoiceService` con `taxes == null`.
3. **Las dependencias están a la vista.** Si el constructor tiene ocho parámetros, la clase hace demasiado. Con campos, ese olor queda escondido.
4. **Los ciclos fallan al arrancar.** Con constructores, A → B → A no se puede resolver y Spring lo dice con claridad. Desde Boot 2.6 las referencias circulares están prohibidas por defecto incluso con campos, pero el constructor hace imposible esquivarlo con `spring.main.allow-circular-references=true`.

Con un único constructor no hace falta `@Autowired` (Spring lo usa solo desde la versión 4.3). Si usáis Lombok, `@RequiredArgsConstructor` genera exactamente ese constructor.

El test que justifica el cambio:

```java
class InvoiceServiceTest {
    @Test
    void issuesInvoiceWithCurrentDate() {
        var clock = Clock.fixed(Instant.parse("2025-03-01T10:00:00Z"), ZoneOffset.UTC);
        var service = new InvoiceService(new InMemoryInvoiceRepository(), new TaxCalculator(), clock);

        Invoice invoice = service.issue(new IssueInvoiceCommand("C-1", 10_000));

        assertThat(invoice.issuedOn()).isEqualTo(LocalDate.of(2025, 3, 1));
    }
}
```

La migración se puede hacer clase a clase: no hay que cambiarlo todo de golpe.""",
            },
            {
                "role": "user",
                "content": "Perfecto. Otra cosa relacionada: tengo un `ReportBuilder` con estado marcado `@Scope(\"prototype\")` que inyecto en un servicio singleton, y parece que siempre es la misma instancia. ¿No se supone que prototype crea una nueva cada vez?",
            },
            {
                "role": "assistant",
                "content": r"""Crea una nueva **cada vez que se le pide al contenedor**. Tu singleton se lo pide una sola vez, al construirse, y guarda esa instancia para siempre. Además, como el singleton atiende peticiones concurrentes, varias de ellas comparten ese `ReportBuilder` con estado: ahora mismo tienes una condición de carrera, no solo una sorpresa.

Tres soluciones, de la que prefiero a la que menos:

**1. Que no sea un bean.** Un *builder* con estado y sin dependencias no necesita a Spring: créalo con `new` donde se usa. Si necesita dependencias, inyecta una fábrica sin estado:

```java
@Component
class ReportBuilderFactory {
    private final TemplateEngine templates;

    ReportBuilderFactory(TemplateEngine templates) {
        this.templates = templates;
    }

    ReportBuilder create() {
        return new ReportBuilder(templates); // uno nuevo por uso
    }
}
```

**2. `ObjectProvider` si de verdad debe ser un bean prototype** (por ejemplo, porque otros lo configuran con `@Bean`):

```java
@Service
class ReportService {
    private final ObjectProvider<ReportBuilder> builders;

    ReportService(ObjectProvider<ReportBuilder> builders) {
        this.builders = builders;
    }

    Report monthly(YearMonth month) {
        ReportBuilder builder = builders.getObject(); // nueva instancia en cada llamada
        return builder.title("Ventas " + month).rows(loadRows(month)).build();
    }
}
```

**3. Proxy de ámbito** (`@Scope(value = "prototype", proxyMode = ScopedProxyMode.TARGET_CLASS)`). Desaconsejado aquí: con prototype, **cada llamada a un método del proxy** crea una instancia nueva, así que `builder.title(...)` y `builder.rows(...)` irían a objetos distintos. Funciona bien para `@RequestScope` (una instancia por petición HTTP, que ya usa proxy por defecto) y mal para prototype.

Regla general: los beans singleton deben ser **sin estado** (o con estado inmutable o *thread-safe*). Si un bean necesita estado por operación, ese estado vive en un objeto nuevo por operación, no en el bean.

Comprobación rápida de que el arreglo hace lo que dices:

```java
@SpringBootTest
class ReportServiceTest {
    @Autowired ObjectProvider<ReportBuilder> builders;

    @Test
    void eachCallGetsAFreshBuilder() {
        assertThat(builders.getObject()).isNotSameAs(builders.getObject());
    }
}
```

Con la opción 1 ni siquiera necesitas este test: `new` siempre crea uno nuevo.""",
            },
        ]
    },
    # 3) Spring Data JPA: N+1 a partir del log de SQL; fetch join, EntityGraph, batch size y paginación (usuario trae log).
    {
        "messages": [
            {
                "role": "user",
                "content": r"""`GET /api/customers/{id}/orders` tarda 1,5 s para un cliente con 50 pedidos. Activé `spring.jpa.show-sql` y sale esto (recortado):

```
Hibernate: select o1_0.id,o1_0.created_at,o1_0.customer_id,o1_0.status from orders o1_0 where o1_0.customer_id=? order by o1_0.created_at desc
Hibernate: select i1_0.order_id,i1_0.id,i1_0.product_id,i1_0.quantity,i1_0.unit_price_cents from order_items i1_0 where i1_0.order_id=?
Hibernate: select i1_0.order_id,i1_0.id,i1_0.product_id,i1_0.quantity,i1_0.unit_price_cents from order_items i1_0 where i1_0.order_id=?
Hibernate: select i1_0.order_id,i1_0.id,i1_0.product_id,i1_0.quantity,i1_0.unit_price_cents from order_items i1_0 where i1_0.order_id=?
(así 50 veces)
```

El repositorio es `List<Order> findByCustomerIdOrderByCreatedAtDesc(Long customerId)` y el servicio mapea cada pedido a un DTO que incluye `order.getItems()`.""",
            },
            {
                "role": "assistant",
                "content": r"""Es el problema N+1 de libro: **1** consulta para los pedidos y **N** (una por pedido) para sus líneas. `items` es `@OneToMany`, que es *lazy* por defecto; cada `order.getItems()` en el mapeo dispara su propia consulta. 51 viajes a la base de datos, cada uno con su latencia de red, explican el segundo y medio.

### Opción 1: traer las líneas en la misma consulta

```java
public interface OrderRepository extends JpaRepository<Order, Long> {

    @Query("select o from Order o left join fetch o.items where o.customerId = :customerId order by o.createdAt desc")
    List<Order> findWithItemsByCustomerId(@Param("customerId") Long customerId);
}
```

O, sin JPQL, con un *entity graph* sobre el método derivado:

```java
@EntityGraph(attributePaths = "items")
List<Order> findByCustomerIdOrderByCreatedAtDesc(Long customerId);
```

Con Hibernate 6 ya no necesitas `distinct`: deduplica solo las entidades raíz que el `join` repite.

### Opción 2: carga por lotes, global y sin tocar consultas

```yaml
spring:
  jpa:
    properties:
      hibernate:
        default_batch_fetch_size: 50
```

Hibernate sigue cargando las líneas de forma *lazy*, pero al tocar la primera colección carga las de hasta 50 pedidos con un solo `where order_id in (...)`. Pasas de 51 consultas a 2. Es una buena red de seguridad para todo el proyecto, no solo para este endpoint.

### Cuidado si el endpoint pagina

`join fetch` sobre una colección **más** `Pageable` no hace lo que parece. Hibernate 6 avisa con:

```
HHH90003004: firstResult/maxResults specified with collection fetch; applying in memory
```

y trae **todas** las filas a memoria para paginar ahí. Con paginación, haz dos consultas: una página de IDs (`select o.id from Order o where ...` con `Pageable`) y luego `join fetch ... where o.id in :ids`. O usa la opción 2, que pagina bien porque no hace *join*.

### Si la pantalla solo muestra un resumen

Si el listado muestra «fecha, estado, número de líneas, total», no cargues entidades: proyecta a un DTO con una consulta agregada (`select new com.acme.orders.OrderSummary(o.id, o.createdAt, o.status, count(i), sum(i.quantity * i.unitPriceCents)) from Order o left join o.items i where ... group by o.id, o.createdAt, o.status`). Una consulta, sin *dirty checking*, sin colecciones.

### Comprobación: un test que cuenta consultas

```java
@DataJpaTest
class OrderRepositoryTest {
    @Autowired OrderRepository orders;
    @Autowired TestEntityManager em;
    @Autowired EntityManagerFactory emf;

    @Test
    void loadsOrdersWithItemsInOneStatement() {
        for (int i = 0; i < 5; i++) {
            Order order = new Order(42L);
            order.addItem(new OrderItem(7L, 1, 999));
            em.persist(order);
        }
        em.flush();
        em.clear(); // sin esto las colecciones salen de la caché de primer nivel y el test no mide nada

        Statistics stats = emf.unwrap(SessionFactory.class).getStatistics();
        stats.setStatisticsEnabled(true);
        stats.clear();

        List<Order> result = orders.findWithItemsByCustomerId(42L);
        result.forEach(o -> o.getItems().size());

        assertThat(result).hasSize(5);
        assertThat(stats.getPrepareStatementCount()).isEqualTo(1);
    }
}
```

Con el método original, el contador da 6 (1 + 5) y el test falla; con el `join fetch`, 1. Ese test es el que impide que alguien «simplifique» la consulta dentro de seis meses.

Si los tests de repositorio corren contra Postgres en Testcontainers y no contra una base embebida, añade `@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)` para que `@DataJpaTest` no intente sustituir tu `DataSource`.""",
            },
        ]
    },
    # 4) @Transactional y la self-invocation; excepciones checked que no hacen rollback (usuario trae código).
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Tenemos un bug grave: si la cuenta destino está bloqueada, el dinero sale de la cuenta origen y no vuelve. ¡Pero el método es `@Transactional`!

```java
@Service
public class TransferService {
    private static final Logger log = LoggerFactory.getLogger(TransferService.class);
    private final AccountRepository accounts;

    public TransferService(AccountRepository accounts) {
        this.accounts = accounts;
    }

    public void transferAll(List<TransferRequest> requests) {
        for (TransferRequest r : requests) {
            try {
                transfer(r);
            } catch (Exception e) {
                log.warn("transfer {} rejected: {}", r.id(), e.getMessage());
            }
        }
    }

    @Transactional
    public void transfer(TransferRequest r) throws InsufficientFundsException {
        Account from = accounts.findById(r.from()).orElseThrow();
        Account to = accounts.findById(r.to()).orElseThrow();
        from.withdraw(r.amount());   // InsufficientFundsException (checked)
        accounts.save(from);
        to.deposit(r.amount());      // AccountFrozenException (runtime) si está bloqueada
        accounts.save(to);
    }
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""Hay dos problemas. El primero causa el bug; el segundo te morderá en cuanto arregles el primero.

### 1. La llamada interna salta el proxy

`@Transactional` funciona porque Spring envuelve tu bean en un **proxy**: quien llama desde fuera habla con el proxy, el proxy abre la transacción y luego invoca tu método. Pero `transferAll` llama a `transfer(r)` **sobre `this`**, el objeto real, no sobre el proxy. La anotación se ignora y `transfer` corre sin transacción.

Sin transacción, cada `accounts.save(...)` usa la transacción propia del método `save` de Spring Data y hace *commit* al terminar. Secuencia del bug:

1. `accounts.save(from)` → *commit*: el saldo origen ya bajó en la base de datos.
2. `to.deposit(...)` lanza `AccountFrozenException`.
3. No hay transacción que deshacer. El dinero desapareció.

Puedes confirmarlo en un minuto poniendo esto como primera línea de `transfer`:

```java
log.debug("tx active: {}", TransactionSynchronizationManager.isActualTransactionActive());
```

Llamado desde `transferAll`, imprime `false`.

### 2. Las excepciones *checked* no hacen rollback por defecto

Aunque la transacción existiera, Spring solo hace *rollback* automático con `RuntimeException` y `Error`. Una `InsufficientFundsException` *checked* que salga del método hace **commit** de lo que hubiera hecho hasta ahí. Hoy no se nota porque `withdraw` lanza antes de escribir nada, pero basta con reordenar dos líneas para tener otro bug como este.

### Arreglo

Para un bucle donde cada elemento debe ser su propia unidad atómica, prefiero una transacción **explícita por elemento** con `TransactionTemplate`: se ve en el código dónde empieza y acaba, y no depende de proxies.

```java
@Service
public class TransferService {
    private static final Logger log = LoggerFactory.getLogger(TransferService.class);
    private final AccountRepository accounts;
    private final TransactionTemplate tx;

    public TransferService(AccountRepository accounts, PlatformTransactionManager txManager) {
        this.accounts = accounts;
        this.tx = new TransactionTemplate(txManager);
    }

    public BatchResult transferAll(List<TransferRequest> requests) {
        var result = new BatchResult();
        for (TransferRequest r : requests) {
            try {
                tx.executeWithoutResult(status -> doTransfer(r)); // una transacción por transferencia
                result.ok(r.id());
            } catch (TransferRejectedException e) {
                log.warn("transfer {} rejected: {}", r.id(), e.getMessage());
                result.rejected(r.id(), e.getMessage());
            }
        }
        return result;
    }

    private void doTransfer(TransferRequest r) {
        Account from = accounts.findById(r.from()).orElseThrow(() -> new AccountNotFoundException(r.from()));
        Account to = accounts.findById(r.to()).orElseThrow(() -> new AccountNotFoundException(r.to()));
        from.withdraw(r.amount()); // ahora lanza InsufficientFundsException, que es runtime
        to.deposit(r.amount());
        // sin save(): dentro de la transacción, las entidades gestionadas se guardan solas al hacer commit
    }
}
```

Cambios que acompañan:

- `InsufficientFundsException` y `AccountFrozenException` pasan a extender una `TransferRejectedException extends RuntimeException`. Así el *rollback* es automático y el `catch` del bucle solo captura rechazos de negocio, no cualquier `Exception` (que antes se tragaba también errores de base de datos).
- Si prefieres seguir con la anotación, la alternativa limpia es mover `transfer` a **otro bean** (`TransferExecutor`) y llamarlo desde `TransferService`: la llamada cruza el proxy. Inyectarse a uno mismo con `@Lazy` también funciona, pero es un truco que el siguiente lector no entenderá.
- Mantén `@Transactional(rollbackFor = Exception.class)` en mente para los casos en que no controles las excepciones *checked* que se lanzan.

### Test de regresión

Contra una base de datos real (H2 no reproduce bloqueos ni algunos *constraints* igual que Postgres; usa Testcontainers):

```java
@SpringBootTest
@Testcontainers
class TransferServiceIT {
    @Container
    @ServiceConnection
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16-alpine");

    @Autowired TransferService service;
    @Autowired AccountRepository accounts;

    @Test
    void frozenDestinationLeavesSourceUntouched() {
        Account from = accounts.save(Account.open("A", 10_000));
        Account to = accounts.save(Account.frozen("B", 0));

        BatchResult result = service.transferAll(List.of(new TransferRequest("t1", from.getId(), to.getId(), 2_500)));

        assertThat(result.rejectedIds()).containsExactly("t1");
        assertThat(accounts.findById(from.getId()).orElseThrow().getBalance()).isEqualTo(10_000);
    }
}
```

Con el código original este test falla con saldo 7.500; con el arreglo pasa. Es exactamente el escenario del incidente.""",
            },
        ]
    },
    # 5) Bean Validation en Spring 6.1+: @Valid, validación de parámetros sin @Validated, restricción propia.
    {
        "messages": [
            {
                "role": "user",
                "content": "Validación en Spring Boot 3.3: `@Valid` en el `@RequestBody` funciona, pero tengo dudas con los `@RequestParam`. ¿Hace falta poner `@Validated` en el controlador para que `@Min` funcione? Leí respuestas contradictorias. Y necesito una regla propia: que `from` sea anterior o igual a `to` en un filtro de fechas.",
            },
            {
                "role": "assistant",
                "content": r"""Las respuestas se contradicen porque **cambió en Spring Framework 6.1** (Spring Boot 3.2).

| | Antes de 6.1 (Boot ≤ 3.1) | Desde 6.1 (Boot ≥ 3.2) |
|---|---|---|
| `@Min` en `@RequestParam` / `@PathVariable` | necesitaba `@Validated` en la clase (validación por proxy AOP) | se valida solo, sin `@Validated` |
| Excepción si falla | `ConstraintViolationException` → **500** si no la manejas | `HandlerMethodValidationException` → **400** |

En Boot 3.3 **quita `@Validated` de los controladores**. La documentación de Spring lo recomienda explícitamente: con `@Validated` en la clase entra además la validación por proxy y puedes acabar validando dos veces o con la excepción que no esperas.

### Ejemplo completo con la regla propia

La regla compara dos campos, así que es una restricción **de clase**, no de campo:

```java
@Target(ElementType.TYPE)
@Retention(RetentionPolicy.RUNTIME)
@Constraint(validatedBy = DateRangeValidator.class)
public @interface ValidDateRange {
    String message() default "from debe ser anterior o igual a to";
    int maxDays() default 366;
    Class<?>[] groups() default {};
    Class<? extends Payload>[] payload() default {};
}
```

```java
public class DateRangeValidator implements ConstraintValidator<ValidDateRange, DateRangeQuery> {
    private int maxDays;

    @Override
    public void initialize(ValidDateRange annotation) {
        this.maxDays = annotation.maxDays();
    }

    @Override
    public boolean isValid(DateRangeQuery q, ConstraintValidatorContext ctx) {
        if (q == null || q.from() == null || q.to() == null) {
            return true; // los nulos los reporta @NotNull; aquí no se duplica el error
        }
        if (q.from().isAfter(q.to())) {
            return violation(ctx, "to", ctx.getDefaultConstraintMessageTemplate());
        }
        if (ChronoUnit.DAYS.between(q.from(), q.to()) > maxDays) {
            return violation(ctx, "to", "el rango no puede superar " + maxDays + " días");
        }
        return true;
    }

    private static boolean violation(ConstraintValidatorContext ctx, String field, String message) {
        ctx.disableDefaultConstraintViolation();
        ctx.buildConstraintViolationWithTemplate(message).addPropertyNode(field).addConstraintViolation();
        return false;
    }
}
```

```java
@ValidDateRange(maxDays = 92)
public record DateRangeQuery(
        @NotNull @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate from,
        @NotNull @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate to) {
}
```

```java
@RestController
@RequestMapping("/api/reports")
class SalesReportController {
    private final SalesReportService reports;

    SalesReportController(SalesReportService reports) {
        this.reports = reports;
    }

    // GET /api/reports/sales?from=2025-01-01&to=2025-03-31&limit=50
    @GetMapping("/sales")
    SalesReport sales(@Valid DateRangeQuery range,
                      @RequestParam(defaultValue = "50") @Min(1) @Max(500) int limit) {
        return reports.sales(range.from(), range.to(), limit);
    }
}
```

Detalles que importan:

- `DateRangeQuery` sin anotación se enlaza como `@ModelAttribute` desde los parámetros de la query; Spring 6 construye el *record* por su constructor.
- `addPropertyNode("to")` hace que el error aparezca asociado al campo `to`, no al objeto entero. El frontend puede pintarlo junto al input.
- El validador devuelve `true` con nulos: cada restricción comprueba una cosa y los mensajes no se duplican.

### Comprobación

```java
@WebMvcTest(SalesReportController.class)
class SalesReportControllerTest {
    @Autowired MockMvc mvc;
    @MockitoBean SalesReportService reports;

    @Test
    void rejectsInvertedRange() throws Exception {
        mvc.perform(get("/api/reports/sales").param("from", "2025-03-01").param("to", "2025-01-01"))
           .andExpect(status().isBadRequest());
    }

    @Test
    void rejectsLimitOutOfBounds() throws Exception {
        mvc.perform(get("/api/reports/sales").param("from", "2025-01-01").param("to", "2025-01-31").param("limit", "0"))
           .andExpect(status().isBadRequest());
    }

    @Test
    void acceptsValidRange() throws Exception {
        mvc.perform(get("/api/reports/sales").param("from", "2025-01-01").param("to", "2025-01-31"))
           .andExpect(status().isOk());
    }
}
```

`@MockitoBean` es el reemplazo de `@MockBean` desde Spring Framework 6.2 (Boot 3.4); en Boot 3.3 usa `@MockBean`. Si el segundo test devuelve 500 en vez de 400, tienes `@Validated` en la clase o un `@ExceptionHandler(Exception.class)` que se está quedando con la `HandlerMethodValidationException`.""",
            },
        ]
    },
    # 6) @RestControllerAdvice + ProblemDetail (RFC 9457) extendiendo ResponseEntityExceptionHandler (system variante: solo código).
    {
        "messages": [
            {"role": "system", "content": "Responde solo con código y comentarios breves."},
            {
                "role": "user",
                "content": "Spring Boot 3: manejo global de errores con ProblemDetail para 404 de recurso, 409 de conflicto de negocio, 400 de validación con detalle por campo y 500 sin filtrar detalles internos. Que los errores propios de Spring (405, 415, JSON mal formado, ruta inexistente) salgan con el mismo formato.",
            },
            {
                "role": "assistant",
                "content": r"""```java
package com.acme.shop.shared;

import jakarta.servlet.http.HttpServletRequest;
import java.net.URI;
import java.util.LinkedHashMap;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.ProblemDetail;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.context.request.WebRequest;
import org.springframework.web.servlet.mvc.method.annotation.ResponseEntityExceptionHandler;

// Heredar de ResponseEntityExceptionHandler da ProblemDetail a las excepciones de Spring MVC:
// 405, 415, 400 por JSON ilegible, 404 de ruta (NoResourceFoundException, Spring 6.1+), etc.
@RestControllerAdvice
public class ApiExceptionHandler extends ResponseEntityExceptionHandler {

    private static final Logger log = LoggerFactory.getLogger(ApiExceptionHandler.class);
    private static final URI TYPES = URI.create("https://api.acme.com/problems/");

    @ExceptionHandler(NotFoundException.class)
    ProblemDetail notFound(NotFoundException ex) {
        return problem(HttpStatus.NOT_FOUND, "not-found", "Recurso no encontrado", ex.getMessage());
    }

    @ExceptionHandler(BusinessConflictException.class)
    ProblemDetail conflict(BusinessConflictException ex) {
        ProblemDetail pd = problem(HttpStatus.CONFLICT, "conflict", "Conflicto", ex.getMessage());
        pd.setProperty("code", ex.code()); // código estable para que el cliente decida sin parsear texto
        return pd;
    }

    // Sin esto, el handler genérico de abajo convertiría un 403 de @PreAuthorize en 500.
    @ExceptionHandler(AccessDeniedException.class)
    ProblemDetail forbidden(AccessDeniedException ex) {
        return problem(HttpStatus.FORBIDDEN, "forbidden", "Acceso denegado", "No tienes permiso para esta operación");
    }

    // @Valid @RequestBody: se conserva el ProblemDetail de Spring y se añaden errores por campo.
    @Override
    protected ResponseEntity<Object> handleMethodArgumentNotValid(
            MethodArgumentNotValidException ex, HttpHeaders headers, HttpStatusCode status, WebRequest request) {
        ProblemDetail pd = ex.getBody();
        pd.setType(TYPES.resolve("validation"));
        pd.setTitle("Datos no válidos");
        Map<String, String> errors = new LinkedHashMap<>();
        ex.getBindingResult().getFieldErrors()
                .forEach(fe -> errors.putIfAbsent(fe.getField(), fe.getDefaultMessage()));
        pd.setProperty("errors", errors);
        return handleExceptionInternal(ex, pd, headers, status, request);
    }

    // Último recurso: se registra todo, al cliente no le llega nada interno.
    @ExceptionHandler(Exception.class)
    ProblemDetail unexpected(Exception ex, HttpServletRequest request) {
        log.error("Unhandled error on {} {}", request.getMethod(), request.getRequestURI(), ex);
        return problem(HttpStatus.INTERNAL_SERVER_ERROR, "internal", "Error interno", "Ha ocurrido un error inesperado");
    }

    private static ProblemDetail problem(HttpStatus status, String type, String title, String detail) {
        ProblemDetail pd = ProblemDetail.forStatusAndDetail(status, detail);
        pd.setType(TYPES.resolve(type));
        pd.setTitle(title);
        return pd;
    }
}
```

```java
// Excepciones de dominio: no saben nada de HTTP.
public class NotFoundException extends RuntimeException {
    public NotFoundException(String resource, Object id) {
        super(resource + " " + id + " no existe");
    }
}

public class BusinessConflictException extends RuntimeException {
    private final String code;

    public BusinessConflictException(String code, String message) {
        super(message);
        this.code = code;
    }

    public String code() {
        return code;
    }
}
```

```yaml
# application.yml
# No hace falta spring.mvc.problemdetails.enabled: al existir tu ResponseEntityExceptionHandler,
# el de Spring Boot se desactiva solo. Activar ambos no añade nada.
spring:
  jackson:
    default-property-inclusion: non_null
```

```java
// Comprobación: el mismo formato para errores propios y de Spring.
@WebMvcTest(ProductController.class)
@Import(ApiExceptionHandler.class)
@AutoConfigureMockMvc(addFilters = false) // aquí se prueba el formato de error, no la seguridad
class ApiExceptionHandlerTest {
    @Autowired MockMvc mvc;
    @MockitoBean ProductService service;

    @Test
    void notFoundIsProblemJson() throws Exception {
        when(service.get(99L)).thenThrow(new NotFoundException("Producto", 99L));
        mvc.perform(get("/api/products/99"))
           .andExpect(status().isNotFound())
           .andExpect(content().contentType("application/problem+json"))
           .andExpect(jsonPath("$.type").value("https://api.acme.com/problems/not-found"));
    }

    @Test
    void validationListsFields() throws Exception {
        mvc.perform(post("/api/products").contentType(MediaType.APPLICATION_JSON).content("{\"name\":\"\"}"))
           .andExpect(status().isBadRequest())
           .andExpect(jsonPath("$.errors.name").exists())
           .andExpect(jsonPath("$.errors.sku").exists());
    }

    @Test
    void malformedJsonUsesSameFormat() throws Exception {
        mvc.perform(post("/api/products").contentType(MediaType.APPLICATION_JSON).content("{not json"))
           .andExpect(status().isBadRequest())
           .andExpect(content().contentType("application/problem+json"));
    }

    @Test
    void wrongMethodIs405ProblemJson() throws Exception {
        mvc.perform(delete("/api/products"))
           .andExpect(status().isMethodNotAllowed())
           .andExpect(content().contentType("application/problem+json"));
    }
}
```""",
            },
        ]
    },
    # 7) Spring Security 6: SecurityFilterChain como resource server JWT (Keycloak), roles del claim y @PreAuthorize (system exacto).
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Spring Boot 3.4 + Spring Security 6. Los tokens los emite Keycloak. Quiero: `/actuator/health` público, `/api/admin/**` solo con rol ADMIN, todo lo demás autenticado. Los roles vienen en el claim `realm_access.roles` y Spring no los ve: todo el mundo recibe 403 en admin, incluso los admins.",
            },
            {
                "role": "assistant",
                "content": r"""El 403 de los admins tiene una causa concreta: el conversor por defecto de Spring Security lee las autoridades del claim **`scope`** (o `scp`) y las prefija con `SCOPE_`. Tus roles están en `realm_access.roles`, un claim anidado que Spring no mira, así que nadie tiene `ROLE_ADMIN`. Hay que decirle de dónde sacarlos.

### Dependencia y configuración

```xml
<dependency>
  <groupId>org.springframework.boot</groupId>
  <artifactId>spring-boot-starter-oauth2-resource-server</artifactId>
</dependency>
```

```yaml
spring:
  security:
    oauth2:
      resourceserver:
        jwt:
          issuer-uri: https://sso.acme.com/realms/shop
          audiences: shop-api
```

Con `issuer-uri`, Spring descubre el JWKS de Keycloak, verifica la firma y comprueba `iss` y `exp`. `audiences` añade la comprobación de `aud`: sin ella, un token emitido para **otra** aplicación del mismo realm sería aceptado por tu API.

### Cadena de filtros

```java
@Configuration
@EnableMethodSecurity
class SecurityConfig {

    @Bean
    SecurityFilterChain api(HttpSecurity http) throws Exception {
        http
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/actuator/health/**").permitAll()
                .requestMatchers("/api/admin/**").hasRole("ADMIN")
                .anyRequest().authenticated())
            .oauth2ResourceServer(oauth -> oauth
                .jwt(jwt -> jwt.jwtAuthenticationConverter(keycloakAuthenticationConverter())))
            .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .csrf(csrf -> csrf.disable()); // sin cookies de sesión: el token va en Authorization
        return http.build();
    }

    static JwtAuthenticationConverter keycloakAuthenticationConverter() {
        JwtAuthenticationConverter converter = new JwtAuthenticationConverter();
        converter.setJwtGrantedAuthoritiesConverter(SecurityConfig::realmRoles);
        converter.setPrincipalClaimName("preferred_username");
        return converter;
    }

    static Collection<GrantedAuthority> realmRoles(Jwt jwt) {
        Map<String, Object> realmAccess = jwt.getClaimAsMap("realm_access");
        if (realmAccess == null || !(realmAccess.get("roles") instanceof Collection<?> roles)) {
            return List.of();
        }
        return roles.stream()
                .map(String::valueOf)
                .map(role -> (GrantedAuthority) new SimpleGrantedAuthority("ROLE_" + role.toUpperCase(Locale.ROOT)))
                .toList();
    }
}
```

`hasRole("ADMIN")` busca la autoridad `ROLE_ADMIN`; por eso el conversor añade el prefijo. El `toUpperCase` es porque en Keycloak los roles suelen estar en minúsculas (`admin`).

Para reglas que dependen del recurso, usa seguridad por método:

```java
@PreAuthorize("hasRole('ADMIN') or #customerId == authentication.name")
public List<OrderSummary> ordersOf(String customerId) {
    return orders.findSummaries(customerId);
}
```

### Comprobación en dos partes

Ojo con una trampa de los tests: el post-procesador `jwt()` de `spring-security-test` **no pasa por tu conversor**; las autoridades se las das tú. Sirve para probar las reglas de URL, pero no prueba que leas bien `realm_access`. Por eso son dos tests.

```java
// 1. Reglas de acceso por URL
@WebMvcTest(AdminController.class)
@Import(SecurityConfig.class)
class AdminSecurityTest {
    @Autowired MockMvc mvc;
    @MockitoBean JwtDecoder jwtDecoder; // evita que el contexto intente contactar con Keycloak
    @MockitoBean AdminService adminService;

    @Test
    void anonymousGets401() throws Exception {
        mvc.perform(get("/api/admin/users")).andExpect(status().isUnauthorized());
    }

    @Test
    void userGets403() throws Exception {
        mvc.perform(get("/api/admin/users").with(jwt().authorities(new SimpleGrantedAuthority("ROLE_USER"))))
           .andExpect(status().isForbidden());
    }

    @Test
    void adminGets200() throws Exception {
        mvc.perform(get("/api/admin/users").with(jwt().authorities(new SimpleGrantedAuthority("ROLE_ADMIN"))))
           .andExpect(status().isOk());
    }
}

// 2. El conversor lee el claim de Keycloak
class RealmRolesTest {
    @Test
    void mapsRealmRolesToSpringRoles() {
        Jwt jwt = Jwt.withTokenValue("token")
                .header("alg", "RS256")
                .claim("realm_access", Map.of("roles", List.of("admin", "offline_access")))
                .build();

        assertThat(SecurityConfig.realmRoles(jwt))
                .extracting(GrantedAuthority::getAuthority)
                .containsExactlyInAnyOrder("ROLE_ADMIN", "ROLE_OFFLINE_ACCESS");
    }
}
```

Y una prueba manual contra el entorno real: decodifica un token de un admin (`jq -R 'split(".") | .[1] | @base64d | fromjson'` sobre el token) y confirma que `realm_access.roles` contiene `admin` y que `aud` incluye `shop-api`. Si `aud` no lo incluye, necesitas un *audience mapper* en el cliente de Keycloak, no tocar Spring.""",
            },
        ]
    },
    # 8) Migración de WebSecurityConfigurerAdapter a SecurityFilterChain; después CSRF de SPA con 403 (multiturno, usuario trae error).
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Migrando de Boot 2.7 a 3.3 la configuración de seguridad no compila:

```
[ERROR] SecurityConfig.java:[18,38] cannot find symbol
  symbol: class WebSecurityConfigurerAdapter
[ERROR] SecurityConfig.java:[27,17] cannot find symbol
  symbol:   method antMatchers(java.lang.String)
```

La clase actual:

```java
@Configuration
@EnableWebSecurity
@EnableGlobalMethodSecurity(prePostEnabled = true)
public class SecurityConfig extends WebSecurityConfigurerAdapter {
    @Autowired private UserDetailsService userDetailsService;

    @Override
    protected void configure(HttpSecurity http) throws Exception {
        http.csrf().csrfTokenRepository(CookieCsrfTokenRepository.withHttpOnlyFalse())
            .and()
            .authorizeRequests()
            .antMatchers("/public/**", "/login").permitAll()
            .antMatchers("/admin/**").hasRole("ADMIN")
            .anyRequest().authenticated()
            .and()
            .formLogin().loginProcessingUrl("/login");
    }

    @Override
    protected void configure(AuthenticationManagerBuilder auth) throws Exception {
        auth.userDetailsService(userDetailsService).passwordEncoder(new BCryptPasswordEncoder());
    }
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""Spring Security 6 eliminó `WebSecurityConfigurerAdapter` (deprecado desde 5.7). La configuración pasa a ser **beans**: un `SecurityFilterChain` para las reglas y beans normales para el resto. Equivalencias:

| Spring Security 5 | Spring Security 6 |
|---|---|
| `extends WebSecurityConfigurerAdapter` + `configure(HttpSecurity)` | `@Bean SecurityFilterChain` |
| `authorizeRequests()` | `authorizeHttpRequests(...)` |
| `antMatchers` / `mvcMatchers` | `requestMatchers` |
| `.and()` encadenado | DSL con lambdas (el estilo sin lambdas está deprecado desde 6.1 y desaparece en 7) |
| `@EnableGlobalMethodSecurity(prePostEnabled = true)` | `@EnableMethodSecurity` (`prePostEnabled` ya es `true` por defecto) |
| `configure(AuthenticationManagerBuilder)` | beans `UserDetailsService` y `PasswordEncoder`; Boot monta el proveedor |

```java
@Configuration
@EnableMethodSecurity
public class SecurityConfig {

    @Bean
    SecurityFilterChain web(HttpSecurity http) throws Exception {
        http
            .csrf(csrf -> csrf.csrfTokenRepository(CookieCsrfTokenRepository.withHttpOnlyFalse()))
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/public/**", "/login", "/error").permitAll()
                .requestMatchers("/admin/**").hasRole("ADMIN")
                .anyRequest().authenticated())
            .formLogin(form -> form.loginProcessingUrl("/login"));
        return http.build();
    }

    @Bean
    PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }
}
```

Tu `UserDetailsService` ya es un bean (lo inyectabas con `@Autowired`), así que Spring Boot lo combina con el `PasswordEncoder` y monta el `DaoAuthenticationProvider` sin que escribas nada.

Fíjate en el **`/error` permitido**: no estaba en tu configuración y no es un descuido. En Spring Security 6, `authorizeHttpRequests` aplica las reglas a **todos** los *dispatch*, incluido el reenvío interno a `/error`. Sin esa línea, un usuario anónimo que provoca un 404 o un 500 en una ruta pública recibe un 401, y los errores reales quedan ocultos.

Comprobación de que las reglas son las mismas que antes:

```java
@WebMvcTest
@Import(SecurityConfig.class)
class SecurityRulesTest {
    @Autowired MockMvc mvc;
    @MockitoBean UserDetailsService userDetailsService;

    @Test
    void publicIsOpen() throws Exception {
        mvc.perform(get("/public/info")).andExpect(status().isNotFound()); // 404, no 401: llega a MVC
    }

    @Test
    void adminRequiresRole() throws Exception {
        mvc.perform(get("/admin/panel").with(user("ana").roles("USER"))).andExpect(status().isForbidden());
    }

    @Test
    void anonymousIsRedirectedToLogin() throws Exception {
        mvc.perform(get("/orders")).andExpect(status().is3xxRedirection());
    }
}
```

El primer test usa una ruta sin controlador a propósito: espera 404, lo que demuestra que la petición pasó la seguridad. MockMvc no hace el reenvío interno a `/error`, así que esa regla compruébala una vez a mano con la aplicación arrancada: `curl -i localhost:8080/public/no-existe` debe dar 404, no 401.""",
            },
            {
                "role": "user",
                "content": "Compila y los GET van bien. Pero ahora todos los POST desde el frontend (React, sesión con cookie, axios manda el `X-XSRF-TOKEN`) dan 403. Antes de migrar funcionaban.",
            },
            {
                "role": "assistant",
                "content": r"""No es tu migración: es un cambio de comportamiento de Spring Security 6 en CSRF que afecta justo a las SPA. Hay dos piezas:

1. **Token protegido contra BREACH.** En 6.0 el manejador por defecto pasó a ser `XorCsrfTokenRequestAttributeHandler`: el token que espera en la cabecera es una versión **enmascarada** y distinta en cada respuesta. La cookie `XSRF-TOKEN` contiene el token **sin enmascarar**. Axios copia la cookie a la cabecera tal cual, así que el valor no coincide con lo que Spring espera: 403.
2. **Carga diferida.** En 6.0 el token se carga solo cuando algo lo pide. Si ninguna respuesta lo usa, la cookie `XSRF-TOKEN` ni siquiera se escribe y el primer POST va sin token.

La solución que documenta Spring Security para SPA: aceptar el token en claro en la cabecera y forzar que la cookie se escriba.

```java
@Bean
SecurityFilterChain web(HttpSecurity http) throws Exception {
    http
        .csrf(csrf -> csrf
            .csrfTokenRepository(CookieCsrfTokenRepository.withHttpOnlyFalse())
            .csrfTokenRequestHandler(new CsrfTokenRequestAttributeHandler())) // token sin enmascarar
        .addFilterAfter(new CsrfCookieFilter(), BasicAuthenticationFilter.class)
        .authorizeHttpRequests(auth -> auth
            .requestMatchers("/public/**", "/login", "/error").permitAll()
            .requestMatchers("/admin/**").hasRole("ADMIN")
            .anyRequest().authenticated())
        .formLogin(form -> form.loginProcessingUrl("/login"));
    return http.build();
}
```

```java
// Fuerza la carga del token diferido para que CookieCsrfTokenRepository escriba la cookie.
final class CsrfCookieFilter extends OncePerRequestFilter {
    @Override
    protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
            throws ServletException, IOException {
        CsrfToken token = (CsrfToken) request.getAttribute(CsrfToken.class.getName());
        if (token != null) {
            token.getToken();
        }
        chain.doFilter(request, response);
    }
}
```

**El trade-off, dicho claro:** con `CsrfTokenRequestAttributeHandler` renuncias a la mitigación BREACH para el token de la cabecera. En una API JSON consumida por una SPA es aceptable: BREACH necesita que el token aparezca reflejado en respuestas comprimidas junto a datos controlados por el atacante, y tu API no pinta el token en HTML. Si la misma aplicación sirve también páginas renderizadas en servidor con formularios, la documentación de Spring muestra un manejador combinado que usa el token enmascarado para los formularios y el plano para la cabecera; úsalo en ese caso.

Lo que **no** hay que hacer: `csrf.disable()`. Usas sesión con cookie, que el navegador manda sola en cualquier petición a tu dominio; sin CSRF, cualquier web que visite tu usuario puede hacer POST en su nombre.

Comprobación:

```java
@Test
void postWithCookieTokenInHeaderIsAccepted() throws Exception {
    MvcResult first = mvc.perform(get("/orders").with(user("ana"))).andReturn();
    Cookie xsrf = first.getResponse().getCookie("XSRF-TOKEN");
    assertThat(xsrf).isNotNull(); // la cookie existe gracias a CsrfCookieFilter

    mvc.perform(post("/orders").with(user("ana"))
            .cookie(xsrf)
            .header("X-XSRF-TOKEN", xsrf.getValue())
            .contentType(MediaType.APPLICATION_JSON)
            .content("{\"productId\":1,\"quantity\":2}"))
       .andExpect(status().isCreated());
}

@Test
void postWithoutTokenIsRejected() throws Exception {
    mvc.perform(post("/orders").with(user("ana")).contentType(MediaType.APPLICATION_JSON).content("{}"))
       .andExpect(status().isForbidden());
}
```

El primer test reproduce exactamente lo que hace axios: copia la cookie en la cabecera. Si pasa aquí y sigue fallando en el navegador, revisa que el frontend y la API estén en el mismo sitio (o que axios tenga `withXSRFToken` activado para peticiones a otro origen, desde axios 1.6).""",
            },
        ]
    },
    # 9) Configuración: @ConfigurationProperties con records, perfiles, variables de entorno; después secretos en Kubernetes (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Cuál es la forma buena de manejar configuración en Spring Boot 3? Ahora tenemos `@Value(\"${payments.url}\")` repartidos por 20 clases, un `application-dev.yml` y un `application-prod.yml`, y nadie sabe qué propiedades existen.",
            },
            {
                "role": "assistant",
                "content": r"""Agrupa cada bloque de configuración en un *record* con `@ConfigurationProperties`. Ganas tres cosas que `@Value` no da: un único sitio que documenta qué existe, tipos de verdad (`Duration`, `URI`) y validación **al arrancar**.

```java
@ConfigurationProperties(prefix = "payments")
@Validated
public record PaymentsProperties(
        @NotNull URI baseUrl,
        @NotBlank String apiKey,
        @DefaultValue("5s") Duration timeout,
        @DefaultValue("3") @Min(0) @Max(10) int maxRetries) {
}
```

```java
@SpringBootApplication
@ConfigurationPropertiesScan // registra todos los @ConfigurationProperties del paquete
public class ShopApplication {
    public static void main(String[] args) {
        SpringApplication.run(ShopApplication.class, args);
    }
}
```

Quien lo necesita lo inyecta como cualquier dependencia:

```java
@Component
class PaymentsClient {
    private final RestClient http;

    PaymentsClient(RestClient.Builder builder, PaymentsProperties props) {
        var factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(props.timeout());
        factory.setReadTimeout(props.timeout());
        this.http = builder.baseUrl(props.baseUrl().toString())
                .defaultHeader("X-Api-Key", props.apiKey())
                .requestFactory(factory)
                .build();
    }
}
```

### Ficheros y perfiles

```yaml
# application.yml: valores comunes y por defecto
payments:
  base-url: https://sandbox.payments.example
  timeout: 3s
```

```yaml
# application-prod.yml: solo lo que cambia en producción
payments:
  base-url: https://api.payments.example
  timeout: 2s
```

El `api-key` no está en ningún fichero: llega del entorno. Precedencia, de más a menos fuerte: argumentos de línea de comandos, variables de entorno, `application-{perfil}.yml`, `application.yml`. El perfil se activa con `SPRING_PROFILES_ACTIVE=prod`.

### El detalle de las variables de entorno

La regla canónica para pasar de propiedad a variable: puntos a guiones bajos, **quitar los guiones** y mayúsculas. `payments.base-url` es `PAYMENTS_BASEURL` y `payments.api-key` es `PAYMENTS_APIKEY`. Es el error más común: alguien define `PAYMENTS_API_KEY` y no entiende por qué no se aplica.

### Por qué esto es mejor que lo que tenéis

- **Falla pronto.** Si falta `PAYMENTS_APIKEY`, la aplicación no arranca y el mensaje dice qué propiedad y qué regla (`must not be blank`). Con `@Value` lo descubres en la primera llamada al proveedor de pagos.
- **Los perfiles solo contienen diferencias.** Nada de `@Profile("prod")` en el código para cambiar valores: el código es el mismo en todos los entornos.
- **Autocompletado en el IDE.** Con `spring-boot-configuration-processor` como dependencia opcional, el IDE conoce y documenta cada propiedad.

### Comprobación

```java
class PaymentsPropertiesTest {
    private final ApplicationContextRunner runner = new ApplicationContextRunner()
            .withUserConfiguration(Config.class);

    @EnableConfigurationProperties(PaymentsProperties.class)
    static class Config {
    }

    @Test
    void failsFastWithoutApiKey() {
        runner.withPropertyValues("payments.base-url=https://x.example")
              .run(ctx -> assertThat(ctx).hasFailed());
    }

    @Test
    void appliesDefaults() {
        runner.withPropertyValues("payments.base-url=https://x.example", "payments.api-key=k")
              .run(ctx -> {
                  PaymentsProperties p = ctx.getBean(PaymentsProperties.class);
                  assertThat(p.timeout()).isEqualTo(Duration.ofSeconds(5));
                  assertThat(p.maxRetries()).isEqualTo(3);
              });
    }
}
```

`ApplicationContextRunner` levanta solo lo necesario, sin servidor: estos tests tardan milisegundos.""",
            },
            {
                "role": "user",
                "content": "¿Y en Kubernetes los secretos cómo los paso? ¿Variables de entorno desde un Secret está bien?",
            },
            {
                "role": "assistant",
                "content": r"""Funciona, pero hay una opción mejor para secretos que Spring Boot soporta de serie: **montar el Secret como ficheros** y leerlo con `configtree`.

Por qué prefiero ficheros a variables de entorno para secretos:

- Las variables de entorno se filtran con facilidad: aparecen en `kubectl describe pod` si alguien las define en línea, en volcados de diagnóstico, en el endpoint `/actuator/env` si se expone por error, y las heredan los procesos hijos.
- Un Secret montado como volumen se actualiza en el pod cuando cambia el Secret (las variables de entorno no, hasta reiniciar). Ojo: Spring lee los ficheros al arrancar, así que igualmente necesitas reiniciar para que la aplicación use el valor nuevo, pero el fichero ya está listo.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: shop-api
spec:
  template:
    spec:
      containers:
        - name: app
          image: registry.acme.com/shop-api:1.8.0
          env:
            - name: SPRING_PROFILES_ACTIVE
              value: prod
            - name: SPRING_CONFIG_IMPORT
              value: "optional:configtree:/etc/secrets/"
          volumeMounts:
            - name: app-secrets
              mountPath: /etc/secrets
              readOnly: true
      volumes:
        - name: app-secrets
          secret:
            secretName: shop-api-secrets
```

Con `configtree`, **el nombre de cada fichero es el nombre de la propiedad** y su contenido, el valor. Así que las claves del Secret deben llamarse como la propiedad:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: shop-api-secrets
type: Opaque
stringData:
  payments.api-key: "valor-real-desde-tu-gestor-de-secretos"
  spring.datasource.password: "otro-valor"
```

El `optional:` hace que en local, donde `/etc/secrets/` no existe, la aplicación arranque igual con lo que tengas en el entorno.

Dos protecciones más:

1. **No expongas `/actuator/env` ni `/actuator/configprops`** en producción. Si los necesitas, Spring Boot 3 enmascara todos los valores por defecto (`management.endpoint.env.show-values=never`); no lo cambies.
2. **El Secret no se escribe a mano en el repositorio.** Que lo genere tu gestor (External Secrets Operator, Sealed Secrets, el CSI driver de tu nube); el YAML de arriba es solo para que veas la forma.

Comprobación dentro del pod, sin imprimir el valor:

```bash
kubectl exec deploy/shop-api -- ls /etc/secrets
# payments.api-key  spring.datasource.password
```

Si la aplicación arranca, la validación de `PaymentsProperties` ya ha comprobado que el valor llegó y no está vacío.""",
            },
        ]
    },
    # 10) Inglés: Actuator para Kubernetes (probes, grupos de health, puerto de gestión, Prometheus) (system variante).
    {
        "messages": [
            {"role": "system", "content": "Be concise: configuration first, then only the reasoning that changes a decision."},
            {
                "role": "user",
                "content": "We're moving a Spring Boot 3.4 service to Kubernetes. How should I set up Actuator for liveness/readiness probes and Prometheus metrics? Last time someone put the DB check in the liveness probe and a database blip restarted every pod.",
            },
            {
                "role": "assistant",
                "content": r"""```yaml
# application.yml
management:
  server:
    port: 8081                      # management endpoints off the public port
  endpoints:
    web:
      exposure:
        include: health,info,prometheus
  endpoint:
    health:
      probes:
        enabled: true               # /actuator/health/liveness and /readiness
        add-additional-paths: true  # also /livez and /readyz on the MAIN port (8080)
      show-details: never
      group:
        readiness:
          include: readinessState,db
  health:
    livenessstate:
      enabled: true
    readinessstate:
      enabled: true
spring:
  lifecycle:
    timeout-per-shutdown-phase: 25s
```

```xml
<dependency>
  <groupId>io.micrometer</groupId>
  <artifactId>micrometer-registry-prometheus</artifactId>
</dependency>
```

```yaml
# deployment.yaml (container section)
ports:
  - name: http
    containerPort: 8080
  - name: management
    containerPort: 8081
livenessProbe:
  httpGet: { path: /livez, port: http }
  periodSeconds: 10
  failureThreshold: 3
readinessProbe:
  httpGet: { path: /readyz, port: http }
  periodSeconds: 5
  failureThreshold: 2
startupProbe:
  httpGet: { path: /livez, port: http }
  periodSeconds: 5
  failureThreshold: 30            # up to 150 s to start before liveness kicks in
lifecycle:
  preStop:
    exec: { command: ["sh", "-c", "sleep 10"] }
terminationGracePeriodSeconds: 45
```

Why each choice:

- **Liveness answers "is this JVM stuck?", nothing else.** It contains only `livenessState`. If it included the database, a DB outage makes every pod fail liveness, Kubernetes restarts all of them, and you get a restart storm on top of the outage. Restarting cannot fix a database.
- **Readiness includes `db`.** A pod that cannot reach the database should stop receiving traffic; it should not be killed.
- **Probes on the main port.** With a separate management port, `/actuator/health/liveness` on 8081 can answer UP while the 8080 connector is saturated or dead. `add-additional-paths` serves `/livez` and `/readyz` from the main server, so the probe checks the path real traffic uses.
- **Management port not exposed.** Your Service and Ingress only route 8080. Prometheus scrapes 8081 inside the cluster (`/actuator/prometheus`), so metrics and health details are not public.
- **`show-details: never`.** Probes only need the status code; details leak versions and hostnames.
- **Shutdown sequence.** Graceful shutdown is the default since Boot 3.4. On SIGTERM, Boot flips readiness to `REFUSING_TRAFFIC` and lets in-flight requests finish for up to `timeout-per-shutdown-phase`. The `preStop` sleep covers the seconds it takes for endpoints to be removed from the Service, during which new requests can still arrive. Keep `terminationGracePeriodSeconds` above sleep plus shutdown phase (10 + 25 < 45).
- **Startup probe** stops liveness from killing a slow-starting JVM (Flyway migrations, cold caches).

Verification:

```bash
kubectl port-forward deploy/orders-api 8080 8081
curl -s localhost:8080/livez                  # {"status":"UP"}
curl -s localhost:8080/readyz                 # {"status":"UP"}
curl -s localhost:8081/actuator/prometheus | grep http_server_requests_seconds_count | head -3
```

Then test the failure you care about: block the database (scale it to zero in staging, or a NetworkPolicy). Readiness must go DOWN, pods must leave the Service endpoints (`kubectl get endpoints orders-api`), and the restart count in `kubectl get pods` must stay at 0.""",
            },
        ]
    },
    # 11) Suite de tests lenta: caché de contextos, slices (@WebMvcTest) y @MockitoBean.
    {
        "messages": [
            {
                "role": "user",
                "content": "Nuestra suite de tests de Spring Boot tarda 9 minutos y casi todos los tests son `@SpringBootTest`. En los logs veo el banner de Spring arrancar muchísimas veces. ¿Por dónde empiezo?",
            },
            {
                "role": "assistant",
                "content": r"""Que el banner salga muchas veces es la pista principal: Spring está creando **un contexto nuevo** para muchas clases de test, y cada arranque cuesta entre 3 y 15 segundos. El framework de tests cachea contextos y los reutiliza, pero solo cuando la configuración es **idéntica**. Tu problema casi seguro es que no lo es.

### 1. Mide antes de tocar nada

```properties
# src/test/resources/application-test.properties o logback-test.xml equivalente
logging.level.org.springframework.test.context.cache=DEBUG
```

Al final de la ejecución verás líneas como:

```
Spring test ApplicationContext cache statistics: [DefaultContextCache@1f2a3b size = 14, maxSize = 32, parentContextCount = 0, hitCount = 61, missCount = 14]
```

`missCount = 14` significa 14 arranques. El objetivo realista es 3 o 4 (uno por tipo de slice y uno o dos de integración).

### 2. Qué rompe la caché

Cada una de estas cosas genera una clave de contexto distinta:

- **Un conjunto distinto de `@MockitoBean`/`@MockBean` por clase.** Es la causa número uno: la clase A mockea `PaymentsClient`, la B mockea `PaymentsClient` y `Mailer`, y son dos contextos.
- `@TestPropertySource` o `properties = ...` con valores distintos.
- `@ActiveProfiles` distintos.
- **`@DirtiesContext`**: tira el contexto y obliga a crear otro. Suele estar ahí «porque un test ensuciaba la base de datos».

### 3. Arreglo por capas

**a) Lo que no necesita Spring, sin Spring.** Servicios con dependencias inyectadas por constructor se prueban con `new` y fakes. Milisegundos por test.

**b) Controladores con `@WebMvcTest`.** Solo levanta la capa web (controladores, advice, filtros, conversores), sin JPA ni servicios:

```java
@WebMvcTest(ProductController.class)
class ProductControllerTest {
    @Autowired MockMvc mvc;
    @MockitoBean ProductService service;

    @Test
    void returnsProduct() throws Exception {
        when(service.get(1L)).thenReturn(new ProductResponse(1L, "Teclado", 4999, "KEYB0001"));

        mvc.perform(get("/api/products/1"))
           .andExpect(status().isOk())
           .andExpect(jsonPath("$.name").value("Teclado"));
    }
}
```

`@MockitoBean` sustituye a `@MockBean` desde Spring Framework 6.2 (Boot 3.4), que queda deprecado. Y en 6.2 tienes también `MockMvcTester`, con aserciones AssertJ, si prefieres ese estilo.

**c) Integración: una sola configuración compartida.** Una clase base con todo lo que varía hoy entre clases:

```java
@SpringBootTest
@ActiveProfiles("test")
@Import(TestcontainersConfig.class)
public abstract class IntegrationTest {
    @MockitoBean protected PaymentsClient payments; // los mocks de sistemas externos, todos aquí
    @MockitoBean protected Mailer mailer;

    @Autowired protected JdbcTemplate jdbc;

    @BeforeEach
    void cleanDatabase() {
        jdbc.execute("TRUNCATE order_items, orders, products RESTART IDENTITY CASCADE");
    }
}
```

Todas las clases de integración heredan de ella y **no declaran mocks propios**. Si una necesita un comportamiento distinto del mock, lo configura con `when(...)` en su test; eso no cambia la clave del contexto.

**d) Fuera `@DirtiesContext`.** El `TRUNCATE` del `@BeforeEach` resuelve lo que motivaba casi todos. Los que queden (un test que cambia un bean singleton) son un olor a revisar uno por uno.

### 4. Orden de trabajo

1. Activa el log y anota `missCount`.
2. Crea la clase base y migra las clases de integración; mide de nuevo.
3. Pasa a `@WebMvcTest` los tests que solo comprueban HTTP (status, JSON, validación).
4. Pasa a tests unitarios puros los que en realidad prueban lógica de servicio.

Después del paso 2 sueles bajar a menos de la mitad del tiempo. Comprueba el resultado con el mismo log: `missCount` debe acercarse al número de configuraciones distintas que **decidiste** tener, no al número de clases de test.""",
            },
        ]
    },
    # 12) Inglés: Testcontainers con @ServiceConnection, Flyway y desarrollo local (system exacto).
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "We test our Spring Boot 3.4 repositories against H2 and production runs Postgres. Last week a migration with a Postgres-only feature passed CI and broke prod. How do I set up Testcontainers properly, and can the same setup run the app locally?",
            },
            {
                "role": "assistant",
                "content": r"""Yes to both, and since Spring Boot 3.1 it takes very little code. The key piece is `@ServiceConnection`: Boot reads the container's host, port and credentials and builds the `DataSource` from them, so there is no `@DynamicPropertySource` boilerplate.

### Dependencies

```xml
<dependency>
  <groupId>org.springframework.boot</groupId>
  <artifactId>spring-boot-testcontainers</artifactId>
  <scope>test</scope>
</dependency>
<dependency>
  <groupId>org.testcontainers</groupId>
  <artifactId>postgresql</artifactId>
  <scope>test</scope>
</dependency>
<dependency>
  <groupId>org.testcontainers</groupId>
  <artifactId>junit-jupiter</artifactId>
  <scope>test</scope>
</dependency>
```

Remove H2 from the test scope. Keeping it "for fast tests" is how the next Postgres-only migration slips through.

### One container definition, reused everywhere

```java
@TestConfiguration(proxyBeanMethods = false)
public class TestcontainersConfig {

    @Bean
    @ServiceConnection
    PostgreSQLContainer<?> postgres() {
        // Pin the same major version as production.
        return new PostgreSQLContainer<>(DockerImageName.parse("postgres:16-alpine"));
    }
}
```

Declaring the container as a bean ties its lifecycle to the Spring context. Because the test framework caches contexts, every test class that uses the same configuration shares one running container.

### Repository tests

```java
@DataJpaTest
@Import(TestcontainersConfig.class)
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
class ProductRepositoryIT {

    @Autowired ProductRepository products;

    @Test
    void findsBySkuIgnoringCase() {
        products.save(new Product("Keyboard", 4999, "KEYB0001"));

        assertThat(products.findBySkuIgnoreCase("keyb0001")).isPresent();
    }
}
```

`replace = NONE` stops `@DataJpaTest` from swapping your configured database for an embedded one. Flyway runs at context startup, so **every migration is executed against real Postgres** on every build. That alone would have caught last week's bug.

### Full-stack tests

```java
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@Import(TestcontainersConfig.class)
class OrderFlowIT {

    @Autowired TestRestTemplate http;
    @Autowired JdbcTemplate jdbc;

    @BeforeEach
    void clean() {
        jdbc.execute("TRUNCATE order_items, orders, products RESTART IDENTITY CASCADE");
    }

    @Test
    void createsOrder() {
        jdbc.update("INSERT INTO products (name, price_cents, sku, stock) VALUES ('Keyboard', 4999, 'KEYB0001', 5)");

        ResponseEntity<String> res = http.postForEntity("/api/orders",
                Map.of("items", List.of(Map.of("sku", "KEYB0001", "quantity", 2))), String.class);

        assertThat(res.getStatusCode()).isEqualTo(HttpStatus.CREATED);
        assertThat(jdbc.queryForObject("SELECT stock FROM products WHERE sku = 'KEYB0001'", Integer.class)).isEqualTo(3);
    }
}
```

Note the explicit `TRUNCATE`. With `RANDOM_PORT`, the request is served on a different thread with its own transaction, so a `@Transactional` on the test class would **not** roll back what the server wrote. Clean up explicitly instead.

### Running the app locally against the same container

Create this in `src/test/java`, next to your application class:

```java
public class TestShopApplication {
    public static void main(String[] args) {
        SpringApplication.from(ShopApplication::main)
                .with(TestcontainersConfig.class)
                .run(args);
    }
}
```

Run it from the IDE or with `./mvnw spring-boot:test-run` (`./gradlew bootTestRun` on Gradle). Postgres starts in Docker, Boot connects to it, and nobody needs a local database install.

### Speed and CI

- First run pulls the image; after that, container start is a few seconds, paid once per cached context.
- For local iteration only, `testcontainers.reuse.enable=true` in `~/.testcontainers.properties` plus `.withReuse(true)` on the container keeps it alive between runs. Do not rely on it in CI.
- CI needs a Docker daemon. GitHub-hosted Ubuntu runners have one.

### Verification

Reproduce last week's incident on purpose: add a migration that uses a Postgres-only feature (say, `CREATE INDEX ... USING gin`) and a test touching that table. It should pass with this setup and fail on H2. Then run `./mvnw verify` and confirm a single `Creating container for image: postgres:16-alpine` line per distinct test context.""",
            },
        ]
    },
    # 13) @WebMvcTest falla: "JPA metamodel must not be empty" por @EnableJpaAuditing en la clase principal (usuario trae traza).
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Escribí mi primer `@WebMvcTest` y ni siquiera arranca:

```
java.lang.IllegalStateException: Failed to load ApplicationContext for [WebMergedContextConfiguration@5c1bd44c testClass = com.acme.shop.catalog.ProductControllerTest, ...]
...
Caused by: org.springframework.beans.factory.BeanCreationException: Error creating bean with name 'jpaAuditingHandler': Cannot resolve reference to bean 'jpaMappingContext' while setting constructor argument
...
Caused by: java.lang.IllegalArgumentException: JPA metamodel must not be empty
```

La clase principal:

```java
@SpringBootApplication
@EnableJpaAuditing
@EnableScheduling
public class ShopApplication {
    public static void main(String[] args) {
        SpringApplication.run(ShopApplication.class, args);
    }
}
```

¿Tengo que mockear algo de JPA en el test?""",
            },
            {
                "role": "assistant",
                "content": r"""No mockees nada: el problema está en la clase principal, no en el test.

**Qué pasa.** `@WebMvcTest` levanta solo la capa web: no configura JPA. Pero para arrancar usa tu clase `@SpringBootApplication` como configuración raíz, **con todas sus anotaciones**. `@EnableJpaAuditing` registra `jpaAuditingHandler`, que necesita el metamodelo de JPA; en un contexto sin JPA, el metamodelo está vacío y el arranque falla. La traza lo dice en orden: no se puede crear `jpaAuditingHandler` → porque `jpaMappingContext` falla → porque el metamodelo está vacío.

`@EnableScheduling` tiene el mismo defecto, aunque no rompa: en cada test de controlador estás arrancando tus tareas programadas.

**Arreglo.** Saca cada `@Enable...` de un área concreta a su propia clase `@Configuration`:

```java
@SpringBootApplication
public class ShopApplication {
    public static void main(String[] args) {
        SpringApplication.run(ShopApplication.class, args);
    }
}
```

```java
@Configuration(proxyBeanMethods = false)
@EnableJpaAuditing
class JpaConfig {
}
```

```java
@Configuration(proxyBeanMethods = false)
@EnableScheduling
@ConditionalOnProperty(name = "app.scheduling.enabled", havingValue = "true", matchIfMissing = true)
class SchedulingConfig {
}
```

Por qué funciona: los *test slices* excluyen del escaneo las clases `@Configuration` del usuario. La aplicación real las sigue cargando (el escaneo normal las encuentra), pero `@WebMvcTest` ya no. Es lo que recomienda la documentación de Spring Boot: no ensuciar la clase principal con configuración de un área concreta.

El `@ConditionalOnProperty` es un extra: en `application-test.yml` pones `app.scheduling.enabled: false` y las tareas tampoco arrancan en los `@SpringBootTest`, donde sí se escanea todo.

**La consecuencia que hay que conocer.** Como los slices excluyen esas clases, un `@DataJpaTest` que compruebe `createdAt` o `lastModifiedBy` tampoco tendrá auditoría. Impórtala explícitamente allí donde la pruebes:

```java
@DataJpaTest
@Import(JpaConfig.class)
class ProductAuditingTest {
    @Autowired ProductRepository products;

    @Test
    void setsCreatedAt() {
        Product saved = products.saveAndFlush(new Product("Teclado", 4999, "KEYB0001"));
        assertThat(saved.getCreatedAt()).isNotNull();
    }
}
```

**Comprobación.** Vuelve a lanzar `ProductControllerTest`: debe arrancar en uno o dos segundos y sin ninguna línea de Hibernate en el log (si aparece Hibernate, algo sigue trayendo JPA al slice). Ejecuta también el `ProductAuditingTest`; si `createdAt` sale `null`, falta el `@Import`. Y revisa la clase principal en busca de otros intrusos con el mismo patrón: `@EnableJpaRepositories`, `@EntityScan`, `@EnableCaching`, `@ComponentScan` con filtros propios.""",
            },
        ]
    },
    # 14) Hilos virtuales en Spring Boot 3.2+: qué cambia, pinning, pools como nuevo límite (system exacto).
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Leí que con Java 21 basta poner `spring.threads.virtual.enabled=true` para que Spring Boot escale muchísimo más. Tenemos una API MVC con JPA que además llama por HTTP a otros dos servicios. ¿Lo activamos en producción sin más?",
            },
            {
                "role": "assistant",
                "content": r"""Activarlo es razonable; hacerlo «sin más», no. Los hilos virtuales quitan un límite (los 200 hilos de Tomcat) y dejan al descubierto los siguientes. Si no los conoces de antemano, el primer pico de tráfico te los enseña en producción.

### Qué hace la propiedad (Spring Boot 3.2+, Java 21+)

- Tomcat atiende cada petición en un hilo virtual en vez de en su pool de hilos de plataforma.
- El `TaskExecutor` de `@Async`, el *scheduler* y los listeners de Kafka y RabbitMQ también pasan a usar hilos virtuales.

Ventaja real en tu caso: mientras una petición espera a la base de datos o a otro servicio, su hilo virtual se aparca y no ocupa un hilo del sistema operativo. Una API dominada por I/O aguanta muchas más peticiones concurrentes con la misma memoria.

### Los nuevos límites

**1. El pool de conexiones pasa a ser el embudo.** Antes, como mucho 200 peticiones llegaban a pedir conexión a Hikari (10 por defecto). Ahora pueden llegar miles, y todas esperan en la cola de Hikari hasta `connectionTimeout` (30 s por defecto). El síntoma es latencia enorme seguida de `SQLTransientConnectionException`, no un error claro. Fíjalo así:

```yaml
spring:
  threads:
    virtual:
      enabled: true
  datasource:
    hikari:
      maximum-pool-size: 20
      connection-timeout: 2s   # falla rápido en vez de acumular esperas de 30 s
server:
  tomcat:
    max-connections: 2000      # el tope natural de concurrencia ahora es este
```

**2. Los servicios de los que dependes no escalan contigo.** Si tus 2.000 peticiones concurrentes llaman al servicio de inventario, le mandas 2.000 llamadas simultáneas. Pon un límite explícito por dependencia:

```java
@Component
class InventoryClient {
    private static final int MAX_CONCURRENT_CALLS = 50;
    private final Semaphore permits = new Semaphore(MAX_CONCURRENT_CALLS);
    private final RestClient http;

    InventoryClient(RestClient.Builder builder, InventoryProperties props) {
        this.http = builder.baseUrl(props.baseUrl()).build();
    }

    Stock stockOf(String sku) {
        try {
            if (!permits.tryAcquire(500, TimeUnit.MILLISECONDS)) {
                throw new DependencyBusyException("inventory");
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new DependencyBusyException("inventory");
        }
        try {
            return http.get().uri("/stock/{sku}", sku).retrieve().body(Stock.class);
        } finally {
            permits.release();
        }
    }
}
```

Con hilos virtuales, un `Semaphore` es la herramienta correcta: bloquear es barato, y lo que limitas es el acceso al recurso escaso, no los hilos.

**3. *Pinning* en Java 21 a 23.** Un hilo virtual que se bloquea **dentro de un bloque `synchronized`** queda clavado a su hilo portador, y portadores hay tantos como núcleos. Si varios se clavan a la vez, todo se para. Afecta a tu código y a librerías antiguas (drivers JDBC viejos, clientes HTTP antiguos). Java 24 resolvió el caso de `synchronized` (JEP 491). Si puedes, usa Java 24 o superior (Java 25 es LTS). Si sigues en 21:
   - actualiza el driver JDBC (pgjdbc 42.6 en adelante ya usa `ReentrantLock` en vez de `synchronized`);
   - diagnostica con `-Djdk.tracePinnedThreads=full` o con el evento de JFR `jdk.VirtualThreadPinned`.

**4. `ThreadLocal` como caché deja de servir.** Cada petición tiene un hilo nuevo, así que lo cacheado por hilo se recrea cada vez y multiplica la memoria. El contexto de seguridad, MDC y transacciones de Spring siguen funcionando igual; el problema está en cachés propias o de librerías.

**5. CPU no mejora.** Si un endpoint es intensivo en CPU, los hilos virtuales no lo aceleran.

### Plan de activación

1. En *staging*, prueba de carga con el perfil de tráfico real, antes y después.
2. Vigila `hikaricp_connections_pending` (Micrometer), latencias p99 y errores de las dependencias.
3. Graba un JFR durante la prueba y busca eventos `jdk.VirtualThreadPinned` de más de 20 ms.
4. Comprueba que de verdad se usan: `jcmd <pid> Thread.dump_to_file -format=json hilos.json` lista los hilos virtuales con su pila.

**Criterio de éxito:** a igual hardware, más throughput o igual throughput con menos memoria, **sin** subir la p99 ni los errores de las dependencias. Si la p99 sube, casi siempre es el punto 1 o el 2.""",
            },
        ]
    },
    # 15) WebFlux vs MVC + hilos virtuales para un agregador; después SSE (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": "Vamos a hacer un servicio BFF que por cada petición llama a 5 APIs internas y combina las respuestas. Parte del equipo quiere WebFlux «porque es para esto»; nadie lo ha usado en serio. Java 21, Spring Boot 3.4. ¿WebFlux o MVC?",
            },
            {
                "role": "assistant",
                "content": r"""Con Java 21 y un equipo sin experiencia en programación reactiva, **Spring MVC con hilos virtuales**. El argumento clásico a favor de WebFlux, «no bloquear hilos mientras esperas I/O», lo cubren ahora los hilos virtuales sin cambiar el modelo de programación.

| Criterio | MVC + hilos virtuales | WebFlux |
|---|---|---|
| Esperar a 5 APIs en paralelo | `CompletableFuture` sobre un executor de hilos virtuales | `Mono.zip` |
| Trazas de error | pilas normales, legibles | pilas de operadores de Reactor, hay que aprender a leerlas |
| Depurar paso a paso | sí | difícil |
| Librerías bloqueantes (JDBC, SDKs) | se usan tal cual | hay que aislarlas en otro scheduler o sustituirlas (R2DBC) |
| Streaming con *backpressure* | limitado | su punto fuerte |
| Curva de aprendizaje | ninguna | real: el error típico es bloquear dentro de la cadena y tumbar el event loop |

### La versión MVC

```java
@Configuration(proxyBeanMethods = false)
class ConcurrencyConfig {
    @Bean(destroyMethod = "close")
    ExecutorService fanOutExecutor() {
        return Executors.newVirtualThreadPerTaskExecutor();
    }
}
```

```java
@Service
class DashboardService {
    private static final Duration BUDGET = Duration.ofSeconds(2);

    private final ProfileClient profiles;
    private final OrdersClient orders;
    private final RecommendationsClient recommendations;
    private final ExecutorService executor;

    DashboardService(ProfileClient profiles, OrdersClient orders,
                     RecommendationsClient recommendations, ExecutorService fanOutExecutor) {
        this.profiles = profiles;
        this.orders = orders;
        this.recommendations = recommendations;
        this.executor = fanOutExecutor;
    }

    Dashboard load(String customerId) {
        var profile = CompletableFuture.supplyAsync(() -> profiles.get(customerId), executor);
        var recent = CompletableFuture.supplyAsync(() -> orders.recent(customerId), executor);
        // Las recomendaciones son prescindibles: si fallan, la página se pinta sin ellas.
        var recs = CompletableFuture.supplyAsync(() -> recommendations.forCustomer(customerId), executor)
                .exceptionally(ex -> List.of());

        CompletableFuture.allOf(profile, recent, recs)
                .orTimeout(BUDGET.toMillis(), TimeUnit.MILLISECONDS)
                .join(); // CompletionException si una obligatoria falla o se agota el presupuesto

        return new Dashboard(profile.join(), recent.join(), recs.join());
    }
}
```

El tiempo total es el de la llamada más lenta, no la suma. Cada cliente usa `RestClient` con sus propios timeouts, y el `orTimeout` pone el presupuesto global de la petición.

Para comparar, lo mismo en WebFlux:

```java
Mono<Dashboard> load(String customerId) {
    return Mono.zip(
                    profiles.get(customerId),
                    orders.recent(customerId),
                    recommendations.forCustomer(customerId).onErrorReturn(List.of()))
            .map(t -> new Dashboard(t.getT1(), t.getT2(), t.getT3()))
            .timeout(Duration.ofSeconds(2));
}
```

Es más corto, sí. El coste no está en estas líneas, sino en todo lo demás: clientes reactivos de punta a punta, seguridad y transacciones reactivas, y nadie en el equipo que sepa diagnosticar un `blockOptional` metido en mitad de la cadena.

**Cómo verificar la decisión:** un prototipo del endpoint con las 5 llamadas simuladas con 200 ms de latencia (WireMock con `fixedDelayMilliseconds`), 1.000 usuarios concurrentes con k6. La respuesta debe rondar los 200 ms, no 1 s; si ronda 1 s, las llamadas no están yendo en paralelo.""",
            },
            {
                "role": "user",
                "content": "Vale, pero una pantalla necesita recibir cambios de precio en vivo con Server-Sent Events. ¿Eso no es justo lo que justifica WebFlux?",
            },
            {
                "role": "assistant",
                "content": r"""No necesariamente. Spring MVC sirve SSE con `SseEmitter`, y con hilos virtuales mantener miles de conexiones abiertas ya no cuesta un hilo de plataforma por cliente. WebFlux empieza a compensar cuando la **fuente** de los eventos es reactiva y necesitas *backpressure* de punta a punta (un cliente lento no debe hacer que se acumule memoria en el servidor). Para «empujar cambios de precio a pantallas», MVC basta.

```java
@Component
class PriceBroadcaster {
    private static final Logger log = LoggerFactory.getLogger(PriceBroadcaster.class);
    private final Set<SseEmitter> emitters = ConcurrentHashMap.newKeySet();

    SseEmitter subscribe() {
        SseEmitter emitter = new SseEmitter(Duration.ofMinutes(30).toMillis());
        emitter.onCompletion(() -> emitters.remove(emitter));
        emitter.onTimeout(() -> emitters.remove(emitter));
        emitter.onError(ex -> emitters.remove(emitter));
        emitters.add(emitter);
        return emitter;
    }

    void publish(PriceChanged event) {
        SseEmitter.SseEventBuilder message = SseEmitter.event()
                .name("price")
                .id(event.sku() + ":" + event.version())
                .data(event);
        for (SseEmitter emitter : emitters) {
            try {
                emitter.send(message);
            } catch (IOException | IllegalStateException e) {
                // cliente desconectado: se descarta sin afectar a los demás
                emitters.remove(emitter);
                log.debug("dropping SSE subscriber: {}", e.getMessage());
            }
        }
    }

    @Scheduled(fixedRate = 15_000)
    void heartbeat() {
        publishComment("keep-alive"); // evita que proxies cierren conexiones inactivas
    }

    private void publishComment(String text) {
        for (SseEmitter emitter : emitters) {
            try {
                emitter.send(SseEmitter.event().comment(text));
            } catch (IOException | IllegalStateException e) {
                emitters.remove(emitter);
            }
        }
    }
}
```

```java
@RestController
class PriceStreamController {
    private final PriceBroadcaster broadcaster;

    PriceStreamController(PriceBroadcaster broadcaster) {
        this.broadcaster = broadcaster;
    }

    @GetMapping(path = "/api/prices/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    ResponseEntity<SseEmitter> stream() {
        return ResponseEntity.ok()
                .header("X-Accel-Buffering", "no") // nginx: no acumular la respuesta en buffer
                .body(broadcaster.subscribe());
    }
}
```

Lo que importa en producción, más que el framework:

- **Varias réplicas.** Cada instancia solo conoce a sus suscriptores. El cambio de precio debe llegar a todas: que cada réplica se suscriba a un tema (Redis pub/sub, Kafka) y llame a `publish`.
- **Reconexión.** El navegador reconecta solo y manda `Last-Event-ID`; por eso los eventos llevan `id`. Si perder un cambio importa, al reconectar envía el estado actual de los precios que pinta esa pantalla.
- **Proxies.** Heartbeat cada 15 s y buffering desactivado; si no, el balanceador cierra conexiones «inactivas» o retiene los eventos.
- **Límite de conexiones.** Cada suscriptor ocupa una conexión de Tomcat: ajusta `server.tomcat.max-connections` a lo que esperas.

Comprobación: `curl -N localhost:8080/api/prices/stream` en una terminal, publica un cambio en otra y el evento debe aparecer al instante. Para carga, abre 5.000 conexiones con k6 y mira memoria y latencia de entrega del evento. Si algún día la fuente es un `Flux` de un cliente reactivo y los clientes lentos empiezan a acumular memoria, ese es el momento de mirar WebFlux para este endpoint concreto.""",
            },
        ]
    },
    # 16) LazyInitializationException al desactivar open-in-view (usuario trae traza).
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Al arrancar salía el aviso `spring.jpa.open-in-view is enabled by default. Therefore, database queries may be performed during view rendering...` y lo desactivé como recomiendan. Ahora `GET /api/orders/{id}` revienta:

```
org.hibernate.LazyInitializationException: failed to lazily initialize a collection of role: com.acme.shop.orders.Order.items: could not initialize proxy - no Session
	at org.hibernate.collection.spi.AbstractPersistentCollection.throwLazyInitializationException(AbstractPersistentCollection.java:635)
	at org.hibernate.collection.spi.AbstractPersistentCollection.withTemporarySessionIfNeeded(AbstractPersistentCollection.java:218)
	at org.hibernate.collection.spi.PersistentBag.iterator(PersistentBag.java:376)
	at com.fasterxml.jackson.databind.ser.std.CollectionSerializer.serializeContents(CollectionSerializer.java:115)
```

El controlador hace `return orderRepository.findById(id).orElseThrow();`. ¿Vuelvo a activar open-in-view?""",
            },
            {
                "role": "assistant",
                "content": r"""No lo vuelvas a activar: desactivarlo fue lo correcto, y lo que ves es un problema que ya existía y que open-in-view escondía.

**Lectura de la traza, de abajo arriba:** Jackson (`CollectionSerializer`) está serializando `Order.items`; esa colección es *lazy*; al iterarla, Hibernate intenta cargarla y no hay sesión abierta porque la transacción de `findById` terminó al salir del repositorio. Con open-in-view activado, la sesión seguía abierta hasta el final de la petición y la carga ocurría durante la serialización: una consulta oculta por cada colección *lazy* que tocara Jackson, fuera del control del servicio.

El problema de fondo es **devolver la entidad JPA desde el controlador**. Eso acopla tu API a tu esquema y deja que el serializador decida qué consultas se ejecutan.

### Arreglo: el servicio carga lo necesario y devuelve un DTO

```java
public interface OrderRepository extends JpaRepository<Order, Long> {
    @EntityGraph(attributePaths = "items")
    Optional<Order> findWithItemsById(Long id);
}
```

```java
public record OrderResponse(long id, String status, Instant createdAt, List<Line> items, long totalCents) {
    public record Line(long productId, int quantity, long unitPriceCents) {
    }

    static OrderResponse from(Order order) {
        List<Line> lines = order.getItems().stream()
                .map(i -> new Line(i.getProductId(), i.getQuantity(), i.getUnitPriceCents()))
                .toList();
        long total = lines.stream().mapToLong(l -> l.quantity() * l.unitPriceCents()).sum();
        return new OrderResponse(order.getId(), order.getStatus().name(), order.getCreatedAt(), lines, total);
    }
}
```

```java
@Service
public class OrderQueryService {
    private final OrderRepository orders;

    public OrderQueryService(OrderRepository orders) {
        this.orders = orders;
    }

    @Transactional(readOnly = true)
    public OrderResponse get(long id) {
        Order order = orders.findWithItemsById(id).orElseThrow(() -> new NotFoundException("Pedido", id));
        return OrderResponse.from(order); // el mapeo ocurre dentro de la transacción
    }
}
```

```java
@GetMapping("/api/orders/{id}")
OrderResponse get(@PathVariable long id) {
    return orderQueryService.get(id);
}
```

Dos razones por las que esto es mejor que cualquier atajo:

- El `@EntityGraph` trae pedido y líneas en **una** consulta. Con open-in-view eran dos, y en un listado serían N+1.
- El DTO se construye dentro de la transacción. Fuera del servicio solo viajan *records* inmutables sin proxies de Hibernate: ya no puede haber `LazyInitializationException` en el controlador.

### Atajos que no debes tomar

- **`FetchType.EAGER` en `items`.** Arregla este endpoint y carga las líneas en todos los sitios donde se lee un `Order`, incluidos los que no las necesitan.
- **`hibernate.enable_lazy_load_no_trans=true`.** Abre una sesión nueva para cada carga *lazy*: es open-in-view por la puerta de atrás, con N+1 garantizado.
- **El módulo `jackson-datatype-hibernate`** para que ignore lo no inicializado: el JSON cambia según qué se haya cargado antes. Una API no debe comportarse así.

### Comprobación

```java
@SpringBootTest
@AutoConfigureMockMvc
@Import(TestcontainersConfig.class)
class OrderEndpointIT {
    @Autowired MockMvc mvc;
    @Autowired OrderRepository orders;

    @Test
    void returnsOrderWithItemsWithoutOpenSession() throws Exception {
        Order order = new Order(42L);
        order.addItem(new OrderItem(7L, 2, 999));
        long id = orders.save(order).getId();

        mvc.perform(get("/api/orders/{id}", id).with(user("ana")))
           .andExpect(status().isOk())
           .andExpect(jsonPath("$.items.length()").value(1))
           .andExpect(jsonPath("$.totalCents").value(1998));
    }
}
```

Con `spring.jpa.open-in-view=false` en la configuración, este test falla con el controlador antiguo y pasa con el nuevo. Después, busca el resto: `grep -rn "Repository" src/main/java --include=*Controller.java` te da la lista de controladores que hablan con repositorios directamente, que son los candidatos a tener el mismo problema.""",
            },
        ]
    },
    # 17) Paginación: aviso de PageImpl (Spring Data 3.3), contrato propio, Slice/Window y max-page-size (usuario trae aviso).
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Devuelvo `Page<ProductResponse>` desde un controlador y desde que subimos a Boot 3.3 sale esto en el log:

```
Serializing PageImpl instances as-is is not supported, meaning that there is no guarantee about the stability of the resulting JSON structure!
	For a stable JSON structure, please use Spring Data's PagedModel (globally via @EnableSpringDataWebSupport(pageSerializationMode = VIA_DTO))
	or Spring HATEOAS and Spring Data's PagedResourcesAssembler as documented in https://docs.spring.io/spring-data/commons/reference/repositories/core-extensions.html#core.web.pageables.
```

Además, en la tabla de productos (12 millones de filas) cada página tarda casi un segundo. ¿Qué hago con las dos cosas?""",
            },
            {
                "role": "assistant",
                "content": r"""Son dos problemas distintos con un origen común: el JSON y la consulta los está decidiendo `Page`, no tú.

### 1. El aviso: el JSON de `PageImpl` no es un contrato

Serializar `PageImpl` vuelca sus *getters* internos (`pageable`, `sort`, `numberOfElements`, `first`, `last`...). Si Spring Data cambia una clase interna, tu API cambia sin que nadie toque tu código. Por eso Spring Data 3.3 empezó a avisar.

Tienes dos salidas:

**a) La rápida, global:**

```java
@Configuration(proxyBeanMethods = false)
@EnableSpringDataWebSupport(pageSerializationMode = EnableSpringDataWebSupport.PageSerializationMode.VIA_DTO)
class WebConfig {
}
```

Todas las `Page` pasan a serializarse como `PagedModel`: `{"content": [...], "page": {"size", "number", "totalElements", "totalPages"}}`. Ojo: **cambia el JSON** respecto al de antes. Si tienes clientes en producción, es un cambio incompatible.

**b) La que prefiero: tu propio contrato.**

```java
public record PageResponse<T>(List<T> items, int page, int size, long totalItems, int totalPages) {
    public static <T> PageResponse<T> from(Page<T> page) {
        return new PageResponse<>(page.getContent(), page.getNumber(), page.getSize(),
                page.getTotalElements(), page.getTotalPages());
    }
}
```

Defines tú los nombres, puedes reproducir los campos que ya consumen tus clientes y el JSON solo cambia cuando cambies este *record*.

### 2. La lentitud: el `count(*)`

Cada `Page` ejecuta **dos** consultas: la página y un `select count(*)` con los mismos filtros para calcular `totalElements`. En 12 millones de filas, el `count` es casi seguro lo que tarda. Además, `OFFSET` alto obliga a recorrer y descartar todas las filas anteriores: la página 50.000 es lenta aunque quites el `count`.

Según lo que necesite la pantalla:

**¿Necesita «página X de Y»?** Si no (scroll infinito, «cargar más»), usa `Slice`: pide `size + 1` filas para saber si hay más y no hace `count`.

```java
Slice<Product> findByCategory(String category, Pageable pageable);
```

**¿Se navega muy hondo?** Paginación por clave (*keyset*): «dame 20 con `id` mayor que el último que vi». Spring Data 3.1+ lo soporta con `Window` y `ScrollPosition`:

```java
public interface ProductRepository extends JpaRepository<Product, Long> {
    Window<Product> findFirst20ByCategoryOrderByIdAsc(String category, ScrollPosition position);
}
```

```java
@GetMapping("/api/products")
CursorPage<ProductResponse> list(@RequestParam String category,
                                 @RequestParam(required = false) Long after) {
    ScrollPosition position = after == null
            ? ScrollPosition.keyset()
            : ScrollPosition.forward(Map.of("id", after));
    Window<Product> window = products.findFirst20ByCategoryOrderByIdAsc(category, position);
    List<ProductResponse> items = window.getContent().stream().map(ProductResponse::from).toList();
    Long next = window.hasNext() && !items.isEmpty() ? items.get(items.size() - 1).id() : null;
    return new CursorPage<>(items, next);
}

public record CursorPage<T>(List<T> items, Long nextCursor) {
}
```

La consulta resultante es `where category = ? and id > ? order by id limit 21`: con un índice en `(category, id)` cuesta lo mismo la primera página que la millonésima.

**Si sí necesitas el total**, que sea aproximado o cacheado: «más de 10.000 resultados» es suficiente para casi cualquier interfaz.

### 3. Un límite que conviene poner ya

Por defecto, un cliente puede pedir `?size=2000`. Bájalo:

```yaml
spring:
  data:
    web:
      pageable:
        max-page-size: 100
```

### Comprobación

- Activa `spring.jpa.show-sql` y llama al endpoint: con `Page` verás dos consultas; con `Slice` o `Window`, una.
- Lanza `EXPLAIN ANALYZE` de la consulta *keyset* con un cursor alto: debe usar el índice y tardar milisegundos.
- Un test de contrato con `jsonPath("$.items")` y `jsonPath("$.nextCursor")` fija la forma del JSON para que no vuelva a depender de una clase interna.""",
            },
        ]
    },
    # 18) Revisión: actualizaciones perdidas; @Version, versión del cliente e If-Match (system variante, usuario trae código).
    {
        "messages": [
            {
                "role": "system",
                "content": "Eres un revisor de código estricto. Señala primero los problemas concretos y después propone el cambio mínimo que los resuelve.",
            },
            {
                "role": "user",
                "content": r"""En el backoffice dos operadores editan el mismo producto y el segundo pisa el cambio del primero sin aviso. Añadí `@Version` a la entidad y sigue pasando. ¿Qué falta?

```java
@Entity
public class Product {
    @Id @GeneratedValue private Long id;
    private String name;
    private long priceCents;
    private int stock;
    @Version private Long version;
    // getters y setters
}

@PutMapping("/api/admin/products/{id}")
ProductResponse update(@PathVariable long id, @RequestBody UpdateProductRequest req) {
    Product p = repo.findById(id).orElseThrow();
    p.setName(req.name());
    p.setPriceCents(req.priceCents());
    p.setStock(req.stock());
    return ProductResponse.from(repo.save(p));
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""Problemas, de más a menos grave:

1. **`@Version` no ve el conflicto que te importa.** El operador A abrió el formulario a las 10:00 (versión 3). B guardó a las 10:02 (versión 4). A guarda a las 10:05: tu código **vuelve a leer** el producto, obtiene la versión 4 y la actualiza a 5. Hibernate solo detecta cambios concurrentes **entre la lectura y la escritura de esta misma petición**, que duran milisegundos. El conflicto real ocurre entre lo que el operador **vio** y lo que hay ahora, y esa versión no viaja en tu petición.
2. **El stock se sobrescribe con un valor absoluto.** Si A ve 10 unidades y escribe 8 (vendió 2) mientras un pedido descontó 1, el resultado correcto es 7 y tú guardas 8. El stock no se edita: se ajusta.
3. **Sin `@Transactional` explícito**, el `findById` y el `save` van en transacciones distintas, lo que agranda la ventana de carrera incluso para el caso que `@Version` sí cubre.
4. **Menor:** `save` sobre una entidad gestionada es redundante, y la respuesta no devuelve la versión, así que el cliente no puede hacer la siguiente edición de forma segura.

### Cambio mínimo

La versión que el cliente vio viaja en la petición y se compara explícitamente.

```java
public record UpdateProductRequest(
        @NotBlank @Size(max = 120) String name,
        @Positive long priceCents,
        @NotNull Long version) {   // la versión que el operador tenía en pantalla
}

public record ProductResponse(long id, String name, long priceCents, int stock, long version) {
    static ProductResponse from(Product p) {
        return new ProductResponse(p.getId(), p.getName(), p.getPriceCents(), p.getStock(), p.getVersion());
    }
}
```

```java
@Service
public class ProductAdminService {
    private final ProductRepository repo;

    public ProductAdminService(ProductRepository repo) {
        this.repo = repo;
    }

    @Transactional
    public ProductResponse update(long id, UpdateProductRequest req) {
        Product p = repo.findById(id).orElseThrow(() -> new NotFoundException("Producto", id));
        if (!p.getVersion().equals(req.version())) {
            throw new StaleEditException(id, req.version(), p.getVersion());
        }
        p.setName(req.name());
        p.setPriceCents(req.priceCents());
        return ProductResponse.from(repo.saveAndFlush(p)); // flush: la versión nueva va en la respuesta
    }
}
```

La comparación explícita cubre el conflicto «humano» (minutos). El `@Version` sigue cubriendo la carrera de milisegundos entre dos peticiones simultáneas: en ese caso, Hibernate lanza `ObjectOptimisticLockingFailureException` al hacer `flush`. Las dos situaciones son el mismo error para el usuario:

```java
@ExceptionHandler({StaleEditException.class, ObjectOptimisticLockingFailureException.class})
ProblemDetail staleEdit(RuntimeException ex) {
    ProblemDetail pd = ProblemDetail.forStatusAndDetail(HttpStatus.CONFLICT,
            "El producto cambió mientras lo editabas. Recarga para ver la versión actual.");
    pd.setProperty("code", "stale_edit");
    return pd;
}
```

El stock sale de este endpoint y pasa a una operación relativa y atómica:

```java
@Modifying
@Query("update Product p set p.stock = p.stock + :delta, p.version = p.version + 1 where p.id = :id and p.stock + :delta >= 0")
int adjustStock(@Param("id") long id, @Param("delta") int delta);
```

Si devuelve 0, el ajuste dejaría el stock negativo (o el producto no existe) y lo rechazas. Incrementar `version` aquí es necesario: un `update` JPQL no pasa por el mecanismo de `@Version`, y si no lo subes, un formulario abierto no se enteraría del ajuste.

Si prefieres HTTP estándar, la misma idea se expresa con `ETag: "4"` en el GET e `If-Match: "4"` en el PUT, respondiendo 412 si no coincide. Es mejor para clientes genéricos; el campo `version` en el cuerpo es más simple para un backoffice propio. Lo importante es que la versión **viaje**.

### Test de regresión

```java
@Test
void secondEditWithStaleVersionIsRejected() {
    Product p = repo.saveAndFlush(new Product("Teclado", 4999, 10));
    long seen = p.getVersion();

    service.update(p.getId(), new UpdateProductRequest("Teclado ES", 4999, seen));          // operador B

    assertThatThrownBy(() -> service.update(p.getId(), new UpdateProductRequest("Teclado", 3999, seen))) // operador A
            .isInstanceOf(StaleEditException.class);
    assertThat(repo.findById(p.getId()).orElseThrow().getName()).isEqualTo("Teclado ES");
}
```

Es exactamente el incidente: dos ediciones partiendo de la misma versión. Con tu código actual, la segunda gana; con el cambio, la segunda recibe 409 y el nombre de B se conserva.""",
            },
        ]
    },
    # 19) Inglés: RestClient (Spring 6.1) con timeouts y errores; después interfaces @HttpExchange (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": "Spring Boot 3.4, Spring MVC. To call other HTTP services, should I use RestTemplate, WebClient or the new RestClient? And how do I set timeouts and error handling properly?",
            },
            {
                "role": "assistant",
                "content": r"""Use **`RestClient`** (Spring Framework 6.1+). It is synchronous like `RestTemplate`, shares its infrastructure (message converters, request factories, interceptors), but has a fluent API. `RestTemplate` is in maintenance mode. `WebClient` makes sense only if you are on WebFlux or genuinely need a reactive pipeline; pulling Reactor into an MVC app just to make HTTP calls is not worth it, especially with virtual threads available.

### A configured client per downstream service

```java
@Configuration(proxyBeanMethods = false)
class InventoryClientConfig {

    @Bean
    RestClient inventoryRestClient(RestClient.Builder builder, InventoryProperties props) {
        HttpClient jdkClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofSeconds(2))
                .build();
        JdkClientHttpRequestFactory factory = new JdkClientHttpRequestFactory(jdkClient);
        factory.setReadTimeout(Duration.ofSeconds(3));

        return builder
                .baseUrl(props.baseUrl())
                .requestFactory(factory)
                .defaultHeader(HttpHeaders.ACCEPT, MediaType.APPLICATION_JSON_VALUE)
                .defaultStatusHandler(HttpStatusCode::is5xxServerError, (request, response) -> {
                    throw new InventoryUnavailableException(response.getStatusCode().value());
                })
                .build();
    }
}
```

Inject `RestClient.Builder` rather than calling `RestClient.builder()`: Boot's auto-configured builder carries the Jackson setup and observability (each call shows up in `http.client.requests` metrics and traces). It is prototype-scoped, so customizing it here does not leak into other clients.

### The client class

```java
@Component
public class InventoryClient {
    private final RestClient http;

    InventoryClient(RestClient inventoryRestClient) {
        this.http = inventoryRestClient;
    }

    // Reservation goes through retrieve(): the default 5xx handler applies, other 4xx throw.
    public Reservation reserve(String sku, int quantity) {
        return http.post()
                .uri("/stock/{sku}/reservations", sku)
                .contentType(MediaType.APPLICATION_JSON)
                .body(new ReserveRequest(quantity))
                .retrieve()
                .body(Reservation.class);
    }

    // Lookup uses exchange(): a missing SKU is a normal answer here, not an error.
    public Optional<Stock> stockOf(String sku) {
        return http.get()
                .uri("/stock/{sku}", sku)
                .exchange((request, response) -> {
                    HttpStatusCode status = response.getStatusCode();
                    if (status.value() == 404) {
                        return Optional.empty();
                    }
                    if (status.is5xxServerError()) {
                        throw new InventoryUnavailableException(status.value());
                    }
                    if (status.isError()) {
                        throw new IllegalStateException("inventory rejected the lookup: " + status.value());
                    }
                    return Optional.ofNullable(response.bodyTo(Stock.class));
                });
    }
}
```

Why these choices:

- **Two timeouts.** Connect timeout catches a dead host fast; read timeout bounds a slow response. Without them the JDK client waits indefinitely and your request threads pile up.
- **5xx → a domain exception** declared once on the builder, so callers handle "inventory unavailable" without knowing HTTP. Other 4xx still raise `HttpClientErrorException`, which is what you want for bugs on your side (400 means you sent something wrong).
- **`exchange()` for the lookup.** It hands you the raw response and skips the status handlers, so 404 becomes `Optional.empty()` without trying to parse an error body as `Stock`. The price is that you must handle the other statuses yourself, which is why the 5xx check is repeated there.
- **Retries are not here on purpose.** Add them only for idempotent calls and with backoff (Spring Retry or Resilience4j), or you multiply load on a struggling service.

### Testing without a network

```java
class InventoryClientTest {
    private final RestClient.Builder builder = RestClient.builder().baseUrl("http://inventory");
    private final MockRestServiceServer server = MockRestServiceServer.bindTo(builder).build();
    private final InventoryClient client = new InventoryClient(builder.build());

    @Test
    void mapsStock() {
        server.expect(requestTo("http://inventory/stock/KEYB0001"))
              .andRespond(withSuccess("{\"sku\":\"KEYB0001\",\"available\":5}", MediaType.APPLICATION_JSON));

        assertThat(client.stockOf("KEYB0001")).map(Stock::available).contains(5);
    }

    @Test
    void unknownSkuIsEmpty() {
        server.expect(requestTo("http://inventory/stock/NOPE0000")).andRespond(withResourceNotFound());

        assertThat(client.stockOf("NOPE0000")).isEmpty();
    }
}
```

`MockRestServiceServer.bindTo(RestClient.Builder)` exists since 6.1. Note it replaces the request factory, so timeouts are not exercised here; that is fine, they are configuration, not logic.""",
            },
            {
                "role": "user",
                "content": "Is there something like Feign, a declarative interface, without pulling in Spring Cloud?",
            },
            {
                "role": "assistant",
                "content": r"""Yes: **HTTP interface clients**, built into Spring Framework 6. You declare an interface with `@HttpExchange` annotations and Spring generates the implementation on top of your `RestClient`.

```java
@HttpExchange(url = "/stock", accept = MediaType.APPLICATION_JSON_VALUE)
public interface InventoryApi {

    @GetExchange("/{sku}")
    Stock get(@PathVariable String sku);

    @PostExchange("/{sku}/reservations")
    Reservation reserve(@PathVariable String sku, @RequestBody ReserveRequest request);
}
```

```java
@Configuration(proxyBeanMethods = false)
class InventoryApiConfig {

    @Bean
    InventoryApi inventoryApi(RestClient inventoryRestClient) {
        HttpServiceProxyFactory factory = HttpServiceProxyFactory
                .builderFor(RestClientAdapter.create(inventoryRestClient))
                .build();
        return factory.createClient(InventoryApi.class);
    }
}
```

Everything you configured on the `RestClient` (timeouts, base URL, the 5xx handler, observability) applies to every method of the interface, because the proxy just issues calls through it.

Trade-offs against the hand-written client:

| | `@HttpExchange` interface | Hand-written `RestClient` class |
|---|---|---|
| Boilerplate | almost none | some |
| Per-call special cases (404 as empty, custom headers per call) | awkward | natural |
| Readability as an API contract | excellent | depends on the author |

A pattern that combines both: the interface for the raw HTTP contract, and a thin `InventoryClient` that wraps it and applies the domain mapping:

```java
@Component
public class InventoryClient {
    private final InventoryApi api;

    InventoryClient(InventoryApi api) {
        this.api = api;
    }

    public Optional<Stock> stockOf(String sku) {
        try {
            return Optional.of(api.get(sku));
        } catch (HttpClientErrorException.NotFound e) {
            return Optional.empty();
        }
    }
}
```

Testing works the same way: bind `MockRestServiceServer` to the builder, build the `RestClient`, create the proxy from it, and assert on the requests the interface produces. Add one test per method that checks the exact path and HTTP verb; that is where annotation typos hide (`@GetExchange("{sku}")` without the slash, for example).""",
            },
        ]
    },
    # 20) Docker para Spring Boot: imagen por capas, memoria de la JVM en contenedor y OOMKilled.
    {
        "messages": [
            {
                "role": "user",
                "content": "Nuestro Dockerfile de Spring Boot es `FROM openjdk:17` + `COPY target/app.jar` + `java -jar`. La imagen pesa más de 600 MB, cada build sube todo de nuevo y en Kubernetes, con límite de 1 GiB, a veces el pod muere con `OOMKilled` aunque el heap no parece lleno. ¿Cómo lo hacemos bien? Ya estamos en Boot 3.4 y Java 21.",
            },
            {
                "role": "assistant",
                "content": r"""Tres problemas distintos: la imagen base, las capas y la memoria. El tercero es el que te tira el servicio.

### 1. Imagen base

Las imágenes `openjdk` de Docker Hub están deprecadas desde 2022 y no reciben actualizaciones. Usa una distribución mantenida y **solo el JRE** en la imagen final: `eclipse-temurin:21-jre`. Bajas cientos de MB y la superficie de vulnerabilidades.

### 2. Capas que no cambian en cada build

Un *fat jar* es un único fichero: cambias una línea de tu código y la capa entera (con 80 MB de dependencias) se reconstruye y se vuelve a subir. Spring Boot puede extraer el jar en capas ordenadas de menos a más cambiantes. Desde Boot 3.3 se hace con `-Djarmode=tools`:

```dockerfile
# syntax=docker/dockerfile:1
FROM eclipse-temurin:21-jdk AS build
WORKDIR /src
COPY .mvn/ .mvn/
COPY mvnw pom.xml ./
RUN --mount=type=cache,target=/root/.m2 ./mvnw -B -q dependency:go-offline
COPY src/ src/
RUN --mount=type=cache,target=/root/.m2 ./mvnw -B -q package -DskipTests \
 && cp target/*.jar application.jar \
 && java -Djarmode=tools -jar application.jar extract --layers --destination extracted

FROM eclipse-temurin:21-jre
RUN useradd --system --uid 10001 --no-create-home spring
WORKDIR /app
COPY --from=build /src/extracted/dependencies/ ./
COPY --from=build /src/extracted/spring-boot-loader/ ./
COPY --from=build /src/extracted/snapshot-dependencies/ ./
COPY --from=build /src/extracted/application/ ./
USER 10001
ENV JAVA_TOOL_OPTIONS="-XX:MaxRAMPercentage=65 -XX:+ExitOnOutOfMemoryError"
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "application.jar"]
```

- Las dependencias van en la primera capa: si no tocas el `pom.xml`, Docker la reutiliza y el push solo sube tu código (unos KB).
- `ENTRYPOINT` en forma de array: `java` es el PID 1 y recibe el `SIGTERM` de Kubernetes. El apagado ordenado está activo por defecto desde Boot 3.4.
- Usuario sin privilegios: un fallo en la aplicación no da root en el contenedor.

La alternativa sin Dockerfile es `./mvnw spring-boot:build-image` (Buildpacks): genera capas, usuario no root y calcula la memoria de la JVM por ti. Es buena opción si no necesitas controlar la imagen.

### 3. `OOMKilled` con el heap «sin llenar»

`OOMKilled` no es un `OutOfMemoryError` de Java: es el kernel matando el proceso porque **toda** la memoria del contenedor superó el límite. El heap es solo una parte. La JVM también usa:

| Zona | Orden de magnitud típico en una API Spring |
|---|---|
| Heap | lo que fijes |
| Metaspace (clases) | 100-200 MB |
| Pilas de hilos | ~1 MB por hilo de plataforma |
| Code cache (JIT) | hasta 240 MB |
| Buffers directos (red, NIO) | variable |

En Java 21, si no fijas nada, el heap máximo es el **25 %** del límite del contenedor. Lo habitual es que alguien haya puesto `-Xmx900m` con un límite de 1 GiB: el heap cabe, la suma no.

Regla práctica: heap en torno al 60-70 % del límite con `-XX:MaxRAMPercentage` (en vez de un `-Xmx` fijo que no se adapta si cambias el límite) y el resto para lo demás. Con 1 GiB, 65 % deja unos 650 MB de heap y ~370 MB para el resto. `-XX:+ExitOnOutOfMemoryError` hace que un `OutOfMemoryError` real termine el proceso y Kubernetes lo reinicie limpio, en vez de dejarlo vivo y roto.

### Comprobación

1. Tamaño: `docker images` debe mostrar en torno a 300 MB (JRE ~200 MB más tu aplicación); `docker history` muestra la capa de dependencias separada de la tuya.
2. Capas: cambia un controlador, reconstruye y haz push: solo debe subirse una capa pequeña.
3. Memoria real dentro del pod, con la aplicación bajo carga. Añade temporalmente `-XX:NativeMemoryTracking=summary` a `JAVA_TOOL_OPTIONS` y ejecuta:

```bash
kubectl exec deploy/shop-api -- jcmd 1 VM.native_memory summary
```

Esa salida reparte el total por zonas. Si `committed` total se acerca al límite del contenedor, ya sabes qué zona crecer o recortar. Hasta que hagas esta medición, cualquier porcentaje es una estimación; con ella, es una decisión.""",
            },
        ]
    },
    # ---------------------------------------------------------------- Kotlin: Ktor 3 y Spring con Kotlin (10)
    # 21) Ktor 3: proyecto base con ContentNegotiation, StatusPages, rutas por funcionalidad y test (system exacto).
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Quiero empezar una API pequeña con Ktor 3 y Kotlin. ¿Cómo la monto para que no sea todo un `Application.kt` gigante: JSON, errores, rutas y un test?",
            },
            {
                "role": "assistant",
                "content": r"""Ktor no trae nada instalado por defecto: cada capacidad es un *plugin* que instalas tú. La estructura que escala separa **el arranque** (leer configuración y construir dependencias) de **la configuración de la aplicación** (plugins y rutas), para que los tests puedan pasar sus propias dependencias.

```
src/main/kotlin/com/acme/shop/
  Application.kt          # main + module(): lee config y construye dependencias
  Configure.kt            # configure(deps): plugins y rutas
  catalog/
    ProductRoutes.kt
    ProductService.kt
    ProductRepository.kt
src/main/resources/
  application.conf
  logback.xml
```

### `build.gradle.kts`

```kotlin
plugins {
    kotlin("jvm") version "2.1.20"
    kotlin("plugin.serialization") version "2.1.20"
    id("io.ktor.plugin") version "3.1.3"
}

application {
    mainClass.set("io.ktor.server.netty.EngineMain")
}

val ktorVersion = "3.1.3"

dependencies {
    implementation("io.ktor:ktor-server-core:$ktorVersion")
    implementation("io.ktor:ktor-server-netty:$ktorVersion")
    implementation("io.ktor:ktor-server-content-negotiation:$ktorVersion")
    implementation("io.ktor:ktor-serialization-kotlinx-json:$ktorVersion")
    implementation("io.ktor:ktor-server-status-pages:$ktorVersion")
    implementation("ch.qos.logback:logback-classic:1.5.18")

    testImplementation("io.ktor:ktor-server-test-host:$ktorVersion")
    testImplementation("io.ktor:ktor-client-content-negotiation:$ktorVersion")
    testImplementation(kotlin("test"))
}
```

### Arranque

```kotlin
// Application.kt
package com.acme.shop

import com.acme.shop.catalog.InMemoryProductRepository
import com.acme.shop.catalog.ProductService
import io.ktor.server.application.Application
import io.ktor.server.netty.EngineMain

fun main(args: Array<String>) = EngineMain.main(args)

// Referenciado desde application.conf. Aquí se decide qué implementaciones reales se usan.
fun Application.module() {
    val products = ProductService(InMemoryProductRepository())
    configure(products)
}
```

```hocon
# application.conf
ktor {
  deployment {
    port = 8080
    port = ${?PORT}
  }
  application {
    modules = [ com.acme.shop.ApplicationKt.module ]
  }
}
```

### Plugins y rutas

```kotlin
// Configure.kt
package com.acme.shop

import com.acme.shop.catalog.ProductService
import com.acme.shop.catalog.productRoutes
import io.ktor.http.HttpStatusCode
import io.ktor.serialization.kotlinx.json.json
import io.ktor.server.application.Application
import io.ktor.server.application.install
import io.ktor.server.application.log
import io.ktor.server.plugins.BadRequestException
import io.ktor.server.plugins.contentnegotiation.ContentNegotiation
import io.ktor.server.plugins.statuspages.StatusPages
import io.ktor.server.response.respond
import io.ktor.server.routing.routing
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

@Serializable
data class ErrorResponse(val code: String, val message: String)

class NotFound(message: String) : RuntimeException(message)

fun Application.configure(products: ProductService) {
    install(ContentNegotiation) {
        json(Json {
            ignoreUnknownKeys = true // un campo nuevo del cliente no rompe la API
            explicitNulls = false
        })
    }
    install(StatusPages) {
        exception<BadRequestException> { call, cause ->
            call.respond(HttpStatusCode.BadRequest, ErrorResponse("bad_request", cause.message ?: "petición no válida"))
        }
        exception<NotFound> { call, cause ->
            call.respond(HttpStatusCode.NotFound, ErrorResponse("not_found", cause.message ?: "no encontrado"))
        }
        exception<Throwable> { call, cause ->
            call.application.log.error("Unhandled error", cause)
            call.respond(HttpStatusCode.InternalServerError, ErrorResponse("internal", "error interno"))
        }
    }
    routing {
        productRoutes(products)
    }
}
```

```kotlin
// catalog/ProductRoutes.kt
package com.acme.shop.catalog

import io.ktor.http.HttpHeaders
import io.ktor.http.HttpStatusCode
import io.ktor.server.plugins.BadRequestException
import io.ktor.server.request.receive
import io.ktor.server.response.respond
import io.ktor.server.routing.Route
import io.ktor.server.routing.get
import io.ktor.server.routing.post
import io.ktor.server.routing.route

fun Route.productRoutes(products: ProductService) {
    route("/api/products") {
        get("/{id}") {
            val id = call.parameters["id"]?.toLongOrNull() ?: throw BadRequestException("id debe ser numérico")
            call.respond(products.get(id))
        }
        post {
            val request = call.receive<CreateProductRequest>() // JSON inválido → BadRequestException
            val created = products.create(request)
            call.response.headers.append(HttpHeaders.Location, "/api/products/${created.id}")
            call.respond(HttpStatusCode.Created, created)
        }
    }
}
```

```kotlin
// catalog/ProductService.kt
package com.acme.shop.catalog

import com.acme.shop.NotFound
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicLong
import kotlinx.serialization.Serializable

@Serializable
data class CreateProductRequest(val name: String, val priceCents: Long)

@Serializable
data class ProductResponse(val id: Long, val name: String, val priceCents: Long)

interface ProductRepository {
    suspend fun findById(id: Long): ProductResponse?
    suspend fun create(name: String, priceCents: Long): ProductResponse
}

class InMemoryProductRepository : ProductRepository {
    private val items = ConcurrentHashMap<Long, ProductResponse>()
    private val nextId = AtomicLong(1)

    override suspend fun findById(id: Long) = items[id]

    override suspend fun create(name: String, priceCents: Long): ProductResponse {
        val product = ProductResponse(nextId.getAndIncrement(), name, priceCents)
        items[product.id] = product
        return product
    }
}

class ProductService(private val repo: ProductRepository) {
    suspend fun get(id: Long): ProductResponse = repo.findById(id) ?: throw NotFound("producto $id no existe")

    suspend fun create(request: CreateProductRequest): ProductResponse = repo.create(request.name, request.priceCents)
}
```

Un detalle de `StatusPages` que muerde a todo el mundo: elige el manejador **más específico** según la jerarquía de clases. Sin el `exception<BadRequestException>` explícito, un JSON mal formado caería en el de `Throwable` y respondería 500 en vez de 400.

### Test

```kotlin
package com.acme.shop

import com.acme.shop.catalog.CreateProductRequest
import com.acme.shop.catalog.InMemoryProductRepository
import com.acme.shop.catalog.ProductResponse
import com.acme.shop.catalog.ProductService
import io.ktor.client.call.body
import io.ktor.client.request.get
import io.ktor.client.request.post
import io.ktor.client.request.setBody
import io.ktor.http.ContentType
import io.ktor.http.HttpStatusCode
import io.ktor.http.contentType
import io.ktor.serialization.kotlinx.json.json
import io.ktor.server.config.MapApplicationConfig
import io.ktor.server.testing.testApplication
import kotlin.test.Test
import kotlin.test.assertEquals
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation as ClientContentNegotiation

class ProductRoutesTest {
    @Test
    fun `crea y recupera un producto`() = testApplication {
        environment { config = MapApplicationConfig() } // no cargar los módulos de application.conf
        application { configure(ProductService(InMemoryProductRepository())) }
        val client = createClient { install(ClientContentNegotiation) { json() } }

        val created = client.post("/api/products") {
            contentType(ContentType.Application.Json)
            setBody(CreateProductRequest("Teclado", 4999))
        }
        assertEquals(HttpStatusCode.Created, created.status)
        val id = created.body<ProductResponse>().id

        assertEquals(HttpStatusCode.OK, client.get("/api/products/$id").status)
        assertEquals(HttpStatusCode.NotFound, client.get("/api/products/999").status)
        assertEquals(HttpStatusCode.BadRequest, client.get("/api/products/abc").status)
    }
}
```

Fíjate en el alias del import: cliente y servidor tienen un plugin llamado `ContentNegotiation` en paquetes distintos, y mezclarlos es el error de compilación más común en los tests de Ktor. El `environment { config = MapApplicationConfig() }` evita que `testApplication` cargue también los módulos declarados en `application.conf`, que instalaría los plugins dos veces. Ejecuta `./gradlew test`; luego `./gradlew run` y un `curl localhost:8080/api/products/1` te confirma que el arranque real usa la misma configuración.""",
            },
        ]
    },
    # 22) Ktor: autenticación JWT; después autorización por rol con un plugin de ruta (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": "En Ktor 3, ¿cómo protejo rutas con JWT? Los tokens los emitimos nosotros mismos con HS256 en un endpoint de login.",
            },
            {
                "role": "assistant",
                "content": r"""Con el plugin `Authentication` y el proveedor `jwt` (`io.ktor:ktor-server-auth-jwt`, que usa `com.auth0:java-jwt`). La idea: la configuración del JWT vive en un objeto, y el **mismo** objeto sirve para emitir tokens en el login y para verificarlos, así emisor, audiencia y secreto no pueden desalinearse.

```kotlin
package com.acme.shop.auth

import com.auth0.jwt.JWT
import com.auth0.jwt.algorithms.Algorithm
import io.ktor.http.HttpStatusCode
import io.ktor.server.application.Application
import io.ktor.server.application.ApplicationCall
import io.ktor.server.application.install
import io.ktor.server.auth.Authentication
import io.ktor.server.auth.jwt.JWTPrincipal
import io.ktor.server.auth.jwt.jwt
import io.ktor.server.auth.principal
import io.ktor.server.config.ApplicationConfig
import io.ktor.server.response.respond
import java.time.Duration
import java.time.Instant

data class JwtConfig(
    val secret: String,
    val issuer: String,
    val audience: String,
    val realm: String,
    val ttl: Duration,
) {
    init {
        require(secret.toByteArray().size >= 32) { "jwt.secret debe tener al menos 32 bytes" }
    }

    private val algorithm get() = Algorithm.HMAC256(secret)

    fun issue(userId: Long, role: String, now: Instant = Instant.now()): String =
        JWT.create()
            .withIssuer(issuer)
            .withAudience(audience)
            .withSubject(userId.toString())
            .withClaim("role", role)
            .withIssuedAt(now)
            .withExpiresAt(now.plus(ttl))
            .sign(algorithm)

    fun verifier() = JWT.require(algorithm)
        .withIssuer(issuer)
        .withAudience(audience)
        .acceptLeeway(30) // segundos de tolerancia entre relojes
        .build()

    companion object {
        fun from(config: ApplicationConfig) = JwtConfig(
            secret = config.property("jwt.secret").getString(),
            issuer = config.property("jwt.issuer").getString(),
            audience = config.property("jwt.audience").getString(),
            realm = config.property("jwt.realm").getString(),
            ttl = Duration.ofMinutes(config.property("jwt.ttlMinutes").getString().toLong()),
        )
    }
}

const val JWT_AUTH = "auth-jwt"

fun Application.configureAuthentication(jwtConfig: JwtConfig) {
    install(Authentication) {
        jwt(JWT_AUTH) {
            realm = jwtConfig.realm
            verifier(jwtConfig.verifier())
            validate { credential ->
                // Firma, emisor, audiencia y exp ya están comprobados; aquí, que los claims sean usables.
                val hasUser = credential.payload.subject?.toLongOrNull() != null
                val hasRole = credential.payload.getClaim("role").asString() != null
                if (hasUser && hasRole) JWTPrincipal(credential.payload) else null
            }
            challenge { _, _ ->
                call.respond(HttpStatusCode.Unauthorized, mapOf("code" to "unauthorized"))
            }
        }
    }
}

val ApplicationCall.userId: Long
    get() = principal<JWTPrincipal>()?.subject?.toLongOrNull()
        ?: error("userId solo existe dentro de authenticate(JWT_AUTH)")

val ApplicationCall.role: String?
    get() = principal<JWTPrincipal>()?.getClaim("role", String::class)
```

Configuración, con el secreto llegando del entorno:

```hocon
jwt {
  secret = ${JWT_SECRET}
  issuer = "shop-auth"
  audience = "shop-api"
  realm = "shop"
  ttlMinutes = 15
}
```

Rutas:

```kotlin
routing {
    post("/auth/login") {
        val request = call.receive<LoginRequest>()
        val user = users.authenticate(request.email, request.password)
            ?: return@post call.respond(HttpStatusCode.Unauthorized, mapOf("code" to "invalid_credentials"))
        call.respond(TokenResponse(jwtConfig.issue(user.id, user.role)))
    }

    authenticate(JWT_AUTH) {
        get("/api/me") {
            call.respond(users.profile(call.userId))
        }
    }
}
```

Por qué así:

- **`validate` devuelve `null` si faltan claims**: el token está bien firmado pero no sirve, y Ktor responde con tu `challenge` (401). Mejor que descubrirlo con un `NullPointerException` dentro de un handler.
- **`init` con `require`**: un secreto corto hace que la aplicación no arranque. HS256 con un secreto débil se rompe por fuerza bruta offline con un solo token capturado.
- **`userId` como extensión**: los handlers no repiten el `principal<JWTPrincipal>()?.subject?.toLong...` en cada sitio.

Comprobación:

```kotlin
class AuthTest {
    private val jwt = JwtConfig("test-secret-with-at-least-32-bytes!", "shop-auth", "shop-api", "shop", Duration.ofMinutes(5))

    private fun ApplicationTestBuilder.app() {
        environment { config = MapApplicationConfig() }
        application { configure(jwt, fakeDeps()) }
    }

    @Test
    fun `sin token es 401`() = testApplication {
        app()
        assertEquals(HttpStatusCode.Unauthorized, client.get("/api/me").status)
    }

    @Test
    fun `token caducado es 401`() = testApplication {
        app()
        val expired = jwt.issue(7, "user", now = Instant.now().minus(Duration.ofHours(1)))
        assertEquals(HttpStatusCode.Unauthorized, client.get("/api/me") { bearerAuth(expired) }.status)
    }

    @Test
    fun `token valido es 200`() = testApplication {
        app()
        assertEquals(HttpStatusCode.OK, client.get("/api/me") { bearerAuth(jwt.issue(7, "user")) }.status)
    }
}
```

El token caducado se emite «hace una hora» con 5 minutos de vida: muy por encima de los 30 s de margen, así que el test no depende del reloj.""",
            },
            {
                "role": "user",
                "content": "Bien. Ahora necesito que `/api/admin/**` solo lo puedan usar los que tienen rol `admin`. ¿Ktor tiene algo como `hasRole`?",
            },
            {
                "role": "assistant",
                "content": r"""No trae autorización por roles, pero se resuelve con un **plugin de ruta** pequeño que se engancha justo después de la autenticación (`AuthenticationChecked`), que es el patrón que muestra la documentación de Ktor para control de acceso basado en roles.

```kotlin
package com.acme.shop.auth

import io.ktor.http.HttpStatusCode
import io.ktor.server.application.createRouteScopedPlugin
import io.ktor.server.auth.AuthenticationChecked
import io.ktor.server.response.respond
import io.ktor.server.routing.Route

class RoleAuthorizationConfig {
    var roles: Set<String> = emptySet()
}

val RoleAuthorization = createRouteScopedPlugin(
    name = "RoleAuthorization",
    createConfiguration = ::RoleAuthorizationConfig,
) {
    val allowed = pluginConfig.roles
    require(allowed.isNotEmpty()) { "RoleAuthorization necesita al menos un rol" }

    on(AuthenticationChecked) { call ->
        val role = call.role
        if (role == null || role !in allowed) {
            call.respond(HttpStatusCode.Forbidden, mapOf("code" to "forbidden"))
        }
    }
}

// Azúcar para que las rutas se lean como la regla de negocio.
fun Route.requireRole(vararg roles: String, build: Route.() -> Unit) {
    install(RoleAuthorization) { this.roles = roles.toSet() }
    build()
}
```

Uso:

```kotlin
authenticate(JWT_AUTH) {
    get("/api/me") { call.respond(users.profile(call.userId)) }

    route("/api/admin") {
        requireRole("admin") {
            get("/users") { call.respond(users.listAll()) }
            delete("/orders/{id}") {
                val id = call.parameters["id"]?.toLongOrNull() ?: throw BadRequestException("id no válido")
                orders.cancel(id, by = call.userId)
                call.respond(HttpStatusCode.NoContent)
            }
        }
    }
}
```

Tres decisiones:

- **El plugin va dentro de `authenticate`.** El orden importa: primero se sabe quién eres (401 si no se sabe) y después qué puedes hacer (403). Fuera de `authenticate`, `call.role` sería siempre `null` y todo daría 403, incluso para quien no envió token y debería recibir 401.
- **`install` en un `route` concreto**: el plugin solo afecta a ese subárbol. No hay una lista global de patrones de URL que mantener sincronizada con las rutas.
- **El rol viene del token.** Un cambio de rol tarda como mucho el TTL (15 minutos) en aplicarse. Si para `admin` eso no es aceptable, consulta el rol en la base de datos dentro del plugin, a costa de una consulta por petición.

Comprobación: la matriz completa, incluido que el handler **no** se ejecuta cuando se rechaza:

```kotlin
@Test
fun `admin requiere rol admin`() = testApplication {
    val orders = RecordingOrders()
    environment { config = MapApplicationConfig() }
    application { configure(jwt, fakeDeps(orders = orders)) }

    assertEquals(HttpStatusCode.Unauthorized, client.delete("/api/admin/orders/5").status)
    assertEquals(HttpStatusCode.Forbidden,
        client.delete("/api/admin/orders/5") { bearerAuth(jwt.issue(7, "user")) }.status)
    assertEquals(emptyList(), orders.cancelled) // el 403 no llegó al handler

    assertEquals(HttpStatusCode.NoContent,
        client.delete("/api/admin/orders/5") { bearerAuth(jwt.issue(1, "admin")) }.status)
    assertEquals(listOf(5L), orders.cancelled)
}
```

La aserción del medio es la importante: un 403 que deja correr el handler sería peor que no tener control, porque daría una falsa sensación de seguridad.""",
            },
        ]
    },
    # 23) Ktor + Exposed: HikariCP, newSuspendedTransaction, dispatcher limitado al pool y conflictos de unicidad.
    {
        "messages": [
            {
                "role": "user",
                "content": "Ktor 3 con Exposed y Postgres. Vi ejemplos que llaman a `transaction { }` directamente dentro de las rutas. ¿Está bien eso? ¿Cómo se monta la capa de datos como corresponde?",
            },
            {
                "role": "assistant",
                "content": r"""Funciona, pero tiene dos problemas: `transaction { }` es **bloqueante** (JDBC) y, llamado desde una ruta, bloquea un hilo del motor de Ktor; y mezcla SQL con HTTP. Lo correcto es un repositorio que ejecute las consultas en un *dispatcher* para I/O, con un pool de conexiones de verdad. Asumo Exposed 0.5x/0.6x (paquetes `org.jetbrains.exposed.sql.*`); en Exposed 1.0 los paquetes cambian de nombre (`org.jetbrains.exposed.v1...`) y conviene seguir su guía de migración.

### Conexión y migraciones

```kotlin
package com.acme.shop.db

import com.zaxxer.hikari.HikariConfig
import com.zaxxer.hikari.HikariDataSource
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.Dispatchers
import org.flywaydb.core.Flyway
import org.jetbrains.exposed.sql.Database
import org.jetbrains.exposed.sql.Transaction
import org.jetbrains.exposed.sql.transactions.experimental.newSuspendedTransaction

data class DbConfig(val url: String, val user: String, val password: String, val poolSize: Int)

class Db(config: DbConfig) : AutoCloseable {
    private val dataSource = HikariDataSource(HikariConfig().apply {
        jdbcUrl = config.url
        username = config.user
        password = config.password
        maximumPoolSize = config.poolSize
        isAutoCommit = false
        transactionIsolation = "TRANSACTION_READ_COMMITTED"
        validate()
    })

    // Tantos hilos como conexiones: más hilos solo esperarían a Hikari bloqueados.
    private val dispatcher: CoroutineDispatcher = Dispatchers.IO.limitedParallelism(config.poolSize)

    val database: Database

    init {
        Flyway.configure().dataSource(dataSource).load().migrate()
        database = Database.connect(dataSource)
    }

    suspend fun <T> query(block: suspend Transaction.() -> T): T =
        newSuspendedTransaction(dispatcher, database) { block() }

    override fun close() = dataSource.close()
}
```

### Tabla y repositorio

```kotlin
package com.acme.shop.catalog

import com.acme.shop.db.Db
import org.jetbrains.exposed.dao.id.LongIdTable
import org.jetbrains.exposed.exceptions.ExposedSQLException
import org.jetbrains.exposed.sql.ResultRow
import org.jetbrains.exposed.sql.SqlExpressionBuilder.eq
import org.jetbrains.exposed.sql.SqlExpressionBuilder.like
import org.jetbrains.exposed.sql.insertAndGetId
import org.jetbrains.exposed.sql.selectAll

object Products : LongIdTable("products") {
    val name = varchar("name", 120)
    val priceCents = long("price_cents")
    val sku = varchar("sku", 8).uniqueIndex()
}

data class Product(val id: Long, val name: String, val priceCents: Long, val sku: String)

class DuplicateSku(sku: String) : RuntimeException("ya existe un producto con SKU $sku")

private const val UNIQUE_VIOLATION = "23505"

class ExposedProductRepository(private val db: Db) {

    suspend fun findById(id: Long): Product? = db.query {
        Products.selectAll().where { Products.id eq id }.map(::toProduct).singleOrNull()
    }

    suspend fun searchByName(prefix: String, limit: Int): List<Product> = db.query {
        Products.selectAll()
            .where { Products.name like "$prefix%" }
            .orderBy(Products.name)
            .limit(limit)
            .map(::toProduct)
    }

    suspend fun create(name: String, priceCents: Long, sku: String): Product = try {
        db.query {
            val id = Products.insertAndGetId {
                it[Products.name] = name
                it[Products.priceCents] = priceCents
                it[Products.sku] = sku
            }
            Product(id.value, name, priceCents, sku)
        }
    } catch (e: ExposedSQLException) {
        if (e.sqlState == UNIQUE_VIOLATION) throw DuplicateSku(sku) else throw e
    }

    private fun toProduct(row: ResultRow) =
        Product(row[Products.id].value, row[Products.name], row[Products.priceCents], row[Products.sku])
}
```

En `Application.module()`:

```kotlin
val db = Db(DbConfig(
    url = environment.config.property("db.url").getString(),
    user = environment.config.property("db.user").getString(),
    password = environment.config.property("db.password").getString(),
    poolSize = environment.config.property("db.poolSize").getString().toInt(),
))
monitor.subscribe(ApplicationStopped) { db.close() }
configure(ProductService(ExposedProductRepository(db)))
```

### Las decisiones

- **`newSuspendedTransaction` con un dispatcher propio.** El hilo de la petición queda libre mientras JDBC bloquea otro hilo. `Dispatchers.IO` a secas permite 64 hilos; con un pool de 10 conexiones, 54 se quedarían bloqueados esperando a Hikari. `limitedParallelism(poolSize)` hace que la espera sea una cola de corrutinas, que no cuesta hilos.
- **Una transacción por operación de negocio, no por consulta.** Si un caso de uso hace tres escrituras que deben ser atómicas, van dentro del mismo `db.query { }`. Y nunca una llamada HTTP dentro: retendrías una conexión mientras esperas a otro servicio.
- **Esquema con Flyway**, no con `SchemaUtils.create`. `create` sirve para prototipos; en producción quieres migraciones versionadas y revisables.
- **El conflicto de unicidad se traduce** a una excepción de dominio que `StatusPages` convierte en 409, en lugar de dejar que un `ExposedSQLException` llegue al cliente como 500.

### Comprobación

Contra Postgres real con Testcontainers, porque el código `23505` y el `like` dependen del motor:

```kotlin
class ExposedProductRepositoryTest {
    companion object {
        private val postgres = PostgreSQLContainer<Nothing>("postgres:16-alpine").apply { start() }
        private val db = Db(DbConfig(postgres.jdbcUrl, postgres.username, postgres.password, poolSize = 4))
    }

    private val repo = ExposedProductRepository(db)

    @Test
    fun `sku duplicado lanza DuplicateSku`() = runTest {
        repo.create("Teclado", 4999, "DUPL0001")
        assertFailsWith<DuplicateSku> { repo.create("Otro", 100, "DUPL0001") }
    }

    @Test
    fun `busca por prefijo`() = runTest {
        repo.create("Ratón óptico", 1999, "MOUS0001")
        assertEquals(listOf("Ratón óptico"), repo.searchByName("Ratón", 10).map { it.name })
    }
}
```

Si el primer test devuelve un `ExposedSQLException` en vez de `DuplicateSku`, revisa que la restricción `UNIQUE` exista en la migración: el `uniqueIndex()` del objeto `Products` solo documenta, no crea nada si el esquema lo hace Flyway.""",
            },
        ]
    },
    # 24) Ktor testApplication: DuplicatePluginException por application.conf + application { } (usuario trae traza).
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Con `./gradlew run` el servidor de Ktor arranca bien, pero mi primer test revienta antes de hacer ninguna petición:

```
io.ktor.server.application.DuplicatePluginException: Please make sure that you use unique name for the plugin and don't install it twice. Conflicting application plugin is already installed with the same key as `ContentNegotiation`
	at io.ktor.server.application.ApplicationPluginKt.install(ApplicationPlugin.kt:112)
	at com.acme.shop.plugins.SerializationKt.configureSerialization(Serialization.kt:11)
	at com.acme.shop.ApplicationKt.module(Application.kt:15)
	at com.acme.shop.ProductRoutesTest$test products$1$1.invoke(ProductRoutesTest.kt:18)
```

El test:

```kotlin
@Test
fun `test products`() = testApplication {
    application { module() }
    val response = client.get("/api/products/1")
    assertEquals(HttpStatusCode.OK, response.status)
    val product = response.body<ProductResponse>()
    assertEquals("Teclado", product.name)
}
```

Solo llamo a `module()` una vez. ¿De dónde sale el segundo `install`?""",
            },
            {
                "role": "assistant",
                "content": r"""Del fichero `application.conf`. `testApplication`, por defecto, carga la configuración de `src/main/resources` (está en el classpath de los tests) y **ejecuta los módulos de `ktor.application.modules`**. Tu `module()` corre una vez por la configuración y otra por tu `application { module() }`; la segunda llamada intenta instalar `ContentNegotiation` otra vez y Ktor lo impide. En `./gradlew run` no pasa porque solo existe la primera vía.

La traza encaja con esa lectura: la línea `ProductRoutesTest.kt:18` es tu `application { module() }`, y el plugin ya estaba instalado cuando llegó.

### Arreglo

Hay dos formas. Elige una y úsala en todos los tests:

**A) Dejar que el test use la configuración y quitar tu llamada.**

```kotlin
@Test
fun `devuelve un producto`() = testApplication {
    val response = client.get("/api/products/1")
    assertEquals(HttpStatusCode.OK, response.status)
}
```

Es lo más corto, pero el test usa las dependencias reales que construye `module()` (la base de datos de verdad, clientes HTTP reales). Sirve para pruebas de humo, no para tests aislados.

**B) Configuración vacía y módulo explícito con dependencias de test** (la que recomiendo):

```kotlin
@Test
fun `devuelve un producto`() = testApplication {
    environment { config = MapApplicationConfig() } // nada de application.conf
    application { configure(ProductService(FakeProductRepository(ProductResponse(1, "Teclado", 4999)))) }
    val client = createClient { install(ClientContentNegotiation) { json() } }

    val response = client.get("/api/products/1")

    assertEquals(HttpStatusCode.OK, response.status)
    assertEquals("Teclado", response.body<ProductResponse>().name)
}
```

con el import con alias:

```kotlin
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation as ClientContentNegotiation
```

Para esto, separa `module()` en dos: `module()` lee la configuración y construye las dependencias reales; `configure(deps)` instala plugins y rutas. Producción llama a `module()`, los tests a `configure(...)`. Si algún test necesita propiedades, pásalas: `MapApplicationConfig("jwt.secret" to "secreto-de-test-con-32-bytes-o-mas")`.

### El siguiente error que te habrías encontrado

Tu test original tenía un segundo problema, escondido detrás del primero: `client` (el cliente por defecto de `testApplication`) **no tiene `ContentNegotiation`**. Al llegar a `response.body<ProductResponse>()` habría fallado con `NoTransformationFoundException`, porque el cliente no sabe convertir JSON en tu clase. Por eso la versión B crea su propio cliente con `createClient`. Y por eso el alias: servidor y cliente tienen un plugin llamado `ContentNegotiation` en paquetes distintos; si importas el del servidor en el test, el código compila hasta que lo instalas en el cliente y no encaja.

### Comprobación

1. Ejecuta el test con la opción B: debe pasar sin tocar `application.conf`.
2. Para asegurarte de que no se cargan módulos por la puerta de atrás, añade temporalmente un `println("module() real")` en `module()`: no debe aparecer en la salida de `./gradlew test`.
3. Repite el patrón en una función de ayuda (`fun ApplicationTestBuilder.app(deps: Deps)`) para que el siguiente test no vuelva a caer en lo mismo.""",
            },
        ]
    },
    # 25) Inglés: ktor-client: timeouts, reintentos solo idempotentes, expectSuccess y MockEngine.
    {
        "messages": [
            {
                "role": "user",
                "content": "I'm calling a payments API from a Ktor 3 service with `HttpClient(CIO)` and default settings. Sometimes requests hang for minutes and errors come back as successful responses with an error body. How should the client be configured, and how do I test it?",
            },
            {
                "role": "assistant",
                "content": r"""Both symptoms come from the defaults: there are **no timeouts**, and **non-2xx responses are not exceptions** (`expectSuccess = false`), so a 500 with an error body is treated like any other response and your code tries to parse it. Configure the client once, per downstream service, and inject it.

```kotlin
package com.acme.shop.payments

import io.ktor.client.HttpClient
import io.ktor.client.engine.HttpClientEngine
import io.ktor.client.engine.cio.CIO
import io.ktor.client.plugins.HttpRequestRetry
import io.ktor.client.plugins.HttpTimeout
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.plugins.defaultRequest
import io.ktor.http.HttpMethod
import io.ktor.serialization.kotlinx.json.json
import java.io.IOException
import kotlinx.serialization.json.Json

data class PaymentsConfig(val baseUrl: String, val apiKey: String)

fun paymentsHttpClient(config: PaymentsConfig, engine: HttpClientEngine = CIO.create()): HttpClient =
    HttpClient(engine) {
        expectSuccess = true // 4xx → ClientRequestException, 5xx → ServerResponseException

        install(ContentNegotiation) {
            json(Json { ignoreUnknownKeys = true })
        }
        install(HttpTimeout) {
            connectTimeoutMillis = 2_000
            socketTimeoutMillis = 5_000
            requestTimeoutMillis = 8_000 // upper bound per attempt; each retry gets its own budget
        }
        install(HttpRequestRetry) {
            maxRetries = 2
            // Only idempotent requests are retried; a retried POST could charge twice.
            retryIf { request, response -> request.method == HttpMethod.Get && response.status.value >= 500 }
            retryOnExceptionIf { request, cause -> request.method == HttpMethod.Get && cause is IOException }
            exponentialDelay()
        }
        defaultRequest {
            url(config.baseUrl) // keep the trailing slash: "https://api.pay.example/v1/"
            headers.append("X-Api-Key", config.apiKey)
        }
    }
```

The gateway that uses it maps HTTP outcomes to domain results:

```kotlin
package com.acme.shop.payments

import io.ktor.client.HttpClient
import io.ktor.client.call.body
import io.ktor.client.plugins.ClientRequestException
import io.ktor.client.request.header
import io.ktor.client.request.post
import io.ktor.client.request.setBody
import io.ktor.http.ContentType
import io.ktor.http.HttpStatusCode
import io.ktor.http.contentType
import kotlinx.serialization.Serializable

@Serializable
data class ChargeRequest(val orderId: String, val amountCents: Long, val currency: String)

@Serializable
data class Charge(val id: String, val status: String)

@Serializable
data class Decline(val reason: String)

sealed interface ChargeResult {
    data class Approved(val charge: Charge) : ChargeResult
    data class Declined(val reason: String) : ChargeResult
}

class PaymentsGateway(private val http: HttpClient) {

    suspend fun charge(request: ChargeRequest): ChargeResult = try {
        val charge: Charge = http.post("charges") {
            contentType(ContentType.Application.Json)
            // Lets the provider deduplicate if *we* retry at a higher level.
            header("Idempotency-Key", "charge-${request.orderId}")
            setBody(request)
        }.body()
        ChargeResult.Approved(charge)
    } catch (e: ClientRequestException) {
        if (e.response.status == HttpStatusCode.PaymentRequired) {
            ChargeResult.Declined(e.response.body<Decline>().reason)
        } else {
            throw e // other 4xx are bugs on our side: let them surface
        }
    }
}
```

The reasoning behind each piece:

- **Three timeouts, three failure modes.** Connect: the host is unreachable. Socket: the connection is open but silent. Request: the whole exchange takes too long. Without them, a hung peer holds your coroutine (and whatever it holds, like a DB connection) indefinitely.
- **Retries only for `GET`.** `retryOnServerErrors()` would retry the `POST` as well. For a charge, "the server failed after charging" and "the server failed before charging" look identical from the outside.
- **`402` is a business answer, not an exception.** Mapping it to `Declined` keeps the caller's `when` exhaustive over a sealed type.
- **`defaultRequest` and the trailing slash.** With `https://api.pay.example/v1` (no slash), the relative `"charges"` resolves to `https://api.pay.example/charges`, dropping `/v1`. That one costs an afternoon if nobody tells you.
- **One client for the application's lifetime.** `HttpClient` owns a connection pool; creating one per request leaks sockets. Close it on shutdown with `monitor.subscribe(ApplicationStopped) { client.close() }`.

### Testing with `MockEngine`

`ktor-client-mock` replaces the network, and since the engine is a parameter, the test exercises the real configuration:

```kotlin
class PaymentsGatewayTest {
    private val config = PaymentsConfig("https://api.pay.example/v1/", "test-key")
    private val json = headersOf(HttpHeaders.ContentType, ContentType.Application.Json.toString())

    @Test
    fun `402 maps to Declined`() = runTest {
        val engine = MockEngine { request ->
            assertEquals("/v1/charges", request.url.encodedPath)
            assertEquals("charge-o-1", request.headers["Idempotency-Key"])
            respond("{\"reason\":\"insufficient_funds\"}", HttpStatusCode.PaymentRequired, json)
        }
        val gateway = PaymentsGateway(paymentsHttpClient(config, engine))

        val result = gateway.charge(ChargeRequest("o-1", 1_000, "EUR"))

        assertEquals(ChargeResult.Declined("insufficient_funds"), result)
    }

    @Test
    fun `POST is not retried on 503`() = runTest {
        var calls = 0
        val engine = MockEngine { calls++; respondError(HttpStatusCode.ServiceUnavailable) }
        val gateway = PaymentsGateway(paymentsHttpClient(config, engine))

        assertFailsWith<ServerResponseException> { gateway.charge(ChargeRequest("o-2", 1_000, "EUR")) }
        assertEquals(1, calls)
    }
}
```

The second test is the one that protects your money: if someone swaps the retry policy for `retryOnServerErrors()`, `calls` becomes 3 and the build fails.""",
            },
        ]
    },
    # 26) Ktor: validación con RequestValidation; después errores por campo con un receive validado (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": "Vengo de Spring y en Ktor echo de menos `@Valid`. ¿Cómo validan ustedes los bodies de las peticiones?",
            },
            {
                "role": "assistant",
                "content": r"""Ktor trae el plugin **`RequestValidation`** (`io.ktor:ktor-server-request-validation`): registras una función por tipo y Ktor la ejecuta automáticamente en cada `call.receive<T>()`. Si devuelve `Invalid`, lanza `RequestValidationException`, que conviertes en respuesta con `StatusPages`.

```kotlin
package com.acme.shop.catalog

import io.ktor.http.HttpStatusCode
import io.ktor.server.application.Application
import io.ktor.server.application.install
import io.ktor.server.plugins.requestvalidation.RequestValidation
import io.ktor.server.plugins.requestvalidation.RequestValidationException
import io.ktor.server.plugins.requestvalidation.ValidationResult
import io.ktor.server.plugins.statuspages.StatusPagesConfig
import io.ktor.server.response.respond
import kotlinx.serialization.Serializable

@Serializable
data class CreateProductRequest(val name: String, val priceCents: Long, val sku: String)

@Serializable
data class ValidationErrors(val code: String, val errors: List<String>)

private val SKU_FORMAT = Regex("[A-Z0-9]{8}")

fun Application.configureValidation() {
    install(RequestValidation) {
        validate<CreateProductRequest> { req ->
            val errors = buildList {
                if (req.name.isBlank()) add("name: es obligatorio")
                if (req.name.length > 120) add("name: máximo 120 caracteres")
                if (req.priceCents <= 0) add("priceCents: debe ser mayor que 0")
                if (!SKU_FORMAT.matches(req.sku)) add("sku: 8 caracteres A-Z o 0-9")
            }
            if (errors.isEmpty()) ValidationResult.Valid else ValidationResult.Invalid(errors)
        }
    }
}

// Se llama desde el install(StatusPages) central.
fun StatusPagesConfig.validationErrors() {
    exception<RequestValidationException> { call, cause ->
        call.respond(HttpStatusCode.UnprocessableEntity, ValidationErrors("validation_failed", cause.reasons))
    }
}
```

La ruta no cambia: `val request = call.receive<CreateProductRequest>()` ya devuelve un objeto validado o lanza.

Dos capas de error que conviene distinguir:

- **JSON mal formado o campo obligatorio ausente.** Lo detecta kotlinx.serialization antes de validar (`{"name": "x"}` sin `priceCents` no puede construir el objeto) y Ktor lanza `BadRequestException` → 400. Si quieres que un campo ausente sea un error de validación con mensaje propio, decláralo con valor por defecto o anulable y compruébalo en `validate`.
- **JSON correcto con valores no válidos.** Lo detecta tu `validate` → 422.

Comprobación:

```kotlin
@Test
fun `body invalido devuelve 422 con todos los errores`() = testApplication {
    environment { config = MapApplicationConfig() }
    application { configure(fakeDeps()) }
    val client = createClient { install(ClientContentNegotiation) { json() } }

    val response = client.post("/api/products") {
        contentType(ContentType.Application.Json)
        setBody(CreateProductRequest(name = "", priceCents = 0, sku = "abc"))
    }

    assertEquals(HttpStatusCode.UnprocessableEntity, response.status)
    assertEquals(3, response.body<ValidationErrors>().errors.size)
}
```

El test comprueba que se devuelven **todos** los errores a la vez, no solo el primero: el usuario corrige el formulario de una pasada.""",
            },
            {
                "role": "user",
                "content": "Funciona, pero el frontend quiere un mapa campo → mensaje, no una lista de strings. Partir los strings por `:` me parece un hack.",
            },
            {
                "role": "assistant",
                "content": r"""Lo es. `ValidationResult.Invalid` solo transporta strings, así que si quieres estructura, el plugin se te queda corto. La alternativa limpia es que cada DTO sepa validarse y devuelva directamente el mapa, y una extensión de `receive` que lo aplique:

```kotlin
package com.acme.shop.validation

import io.ktor.server.application.ApplicationCall
import io.ktor.server.request.receive

interface Validatable {
    fun validate(): Map<String, String>
}

class ValidationException(val fields: Map<String, String>) : RuntimeException("validation failed")

suspend inline fun <reified T : Validatable> ApplicationCall.receiveValid(): T {
    val body = receive<T>()
    val errors = body.validate()
    if (errors.isNotEmpty()) throw ValidationException(errors)
    return body
}
```

```kotlin
@Serializable
data class CreateProductRequest(val name: String, val priceCents: Long, val sku: String) : Validatable {
    override fun validate(): Map<String, String> = buildMap {
        when {
            name.isBlank() -> put("name", "es obligatorio")
            name.length > 120 -> put("name", "máximo 120 caracteres")
        }
        if (priceCents <= 0) put("priceCents", "debe ser mayor que 0")
        if (!SKU_FORMAT.matches(sku)) put("sku", "8 caracteres A-Z o 0-9")
    }

    private companion object {
        val SKU_FORMAT = Regex("[A-Z0-9]{8}")
    }
}
```

```kotlin
@Serializable
data class FieldErrors(val code: String, val fields: Map<String, String>)

fun StatusPagesConfig.validationErrors() {
    exception<ValidationException> { call, cause ->
        call.respond(HttpStatusCode.UnprocessableEntity, FieldErrors("validation_failed", cause.fields))
    }
}
```

En la ruta: `val request = call.receiveValid<CreateProductRequest>()`.

El trade-off frente a `RequestValidation`:

| | `RequestValidation` | `Validatable` + `receiveValid` |
|---|---|---|
| Se aplica solo | sí, en cualquier `receive` | solo si usas `receiveValid` |
| Forma del error | lista de strings | la que tú definas |
| Dónde vive la regla | en la configuración de la app | junto al DTO |

El riesgo de la segunda es que alguien escriba `receive` en vez de `receiveValid` y se salte la validación. Mitígalo con una regla de revisión, o con un test por endpoint que mande un body inválido (que deberías tener de todas formas). Para mí compensa: las reglas quedan al lado de los campos que validan, y el `when` deja claro que de `name` se informa un solo error, el más relevante.

No uses las dos a la vez: dos sitios con reglas para el mismo DTO acaban divergiendo.

Comprobación con el formato nuevo:

```kotlin
val errors = response.body<FieldErrors>().fields
assertEquals(setOf("name", "priceCents", "sku"), errors.keys)
assertEquals("es obligatorio", errors["name"])
```

Y un test unitario de `validate()`, sin Ktor, para los casos límite (`name` de 120 y de 121 caracteres): es una función pura y se prueba en milisegundos.""",
            },
        ]
    },
    # 27) Ktor: CallId + CallLogging con MDC y un plugin propio con createApplicationPlugin (system variante: rioplatense).
    {
        "messages": [
            {"role": "system", "content": "Respondé en español rioplatense, con voseo, directo y técnico."},
            {
                "role": "user",
                "content": "En Ktor necesito que cada línea de log lleve un request id (y que se devuelva en la respuesta), y además quiero medir cuánto tarda cada endpoint y mandarlo en una cabecera. ¿Hay plugins para eso o lo escribo yo?",
            },
            {
                "role": "assistant",
                "content": r"""Para el request id hay plugins oficiales y no tiene sentido escribirlo vos: **`CallId`** lo genera o lo toma de la cabecera, y **`CallLogging`** lo mete en el MDC de SLF4J. La cabecera de tiempos sí te conviene escribirla como plugin propio: son diez líneas y te sirve para entender cómo funcionan los plugins de Ktor.

### Request id en cada línea de log

```kotlin
package com.acme.shop.observability

import io.ktor.http.HttpHeaders
import io.ktor.server.application.Application
import io.ktor.server.application.install
import io.ktor.server.plugins.callid.CallId
import io.ktor.server.plugins.callid.callIdMdc
import io.ktor.server.plugins.calllogging.CallLogging
import io.ktor.server.request.httpMethod
import io.ktor.server.request.path
import java.util.UUID
import org.slf4j.event.Level

private val VALID_REQUEST_ID = Regex("[A-Za-z0-9-]{8,64}")

fun Application.configureCallTracing() {
    install(CallId) {
        retrieveFromHeader(HttpHeaders.XRequestId)        // si el balanceador ya trae uno, se respeta
        generate { UUID.randomUUID().toString() }
        verify { VALID_REQUEST_ID.matches(it) }           // no aceptar cualquier cosa que mande el cliente
        replyToHeader(HttpHeaders.XRequestId)
    }
    install(CallLogging) {
        level = Level.INFO
        callIdMdc("request_id")
        filter { call -> call.request.path().startsWith("/api") }
        format { call -> "${call.request.httpMethod.value} ${call.request.path()} -> ${call.response.status()}" }
    }
}
```

Y en `logback.xml`, que el patrón lo muestre:

```xml
<pattern>%d{HH:mm:ss.SSS} %-5level [%X{request_id}] %logger{36} - %msg%n</pattern>
```

Fijate en el `verify`: sin él, un cliente te puede mandar un `X-Request-Id` de 10 KB o con saltos de línea y te ensucia los logs (o te inyecta líneas falsas).

Ojo con un caso: si lanzás trabajo en **otro scope** (una corrutina que sobrevive a la petición), el MDC no viaja solo. Capturalo con `MDCContext()` de `kotlinx-coroutines-slf4j` al lanzar esa corrutina.

### Plugin propio: tiempo de respuesta

```kotlin
package com.acme.shop.observability

import io.ktor.server.application.createApplicationPlugin
import io.ktor.util.AttributeKey

private val RequestStartKey = AttributeKey<Long>("RequestStartNanos")

val ResponseTime = createApplicationPlugin(name = "ResponseTime") {
    onCall { call ->
        call.attributes.put(RequestStartKey, System.nanoTime())
    }
    onCallRespond { call, _ ->
        val start = call.attributes.getOrNull(RequestStartKey) ?: return@onCallRespond
        val elapsedMs = (System.nanoTime() - start) / 1_000_000
        call.response.headers.append("Server-Timing", "app;dur=$elapsedMs")
    }
}
```

`install(ResponseTime)` en tu `configure()`. Cómo funciona:

- **`onCall`** corre al principio de cada llamada; guardás el instante en los `attributes` de la llamada, que es el almacén por petición de Ktor (nada de variables globales ni `ThreadLocal`, que con corrutinas no sirven).
- **`onCallRespond`** corre cuando se va a enviar la respuesta, antes de escribir las cabeceras, así que todavía podés añadir una.
- Usé **`Server-Timing`** en vez de un `X-Response-Time` inventado: es una cabecera estándar y las DevTools del navegador la muestran en la pestaña de red.

El tiempo medido es el de tu aplicación hasta empezar a responder; no incluye la escritura del cuerpo por la red. Para métricas de verdad (percentiles por ruta) no te alcanza con una cabecera: usá `ktor-server-metrics-micrometer` con un registro de Prometheus, que publica `ktor.http.server.requests` por ruta y status.

### Comprobación

```kotlin
@Test
fun `devuelve request id y Server-Timing`() = testApplication {
    environment { config = MapApplicationConfig() }
    application { configure(fakeDeps()) }

    val generated = client.get("/api/products/1")
    assertNotNull(generated.headers[HttpHeaders.XRequestId])
    assertTrue(generated.headers["Server-Timing"]!!.startsWith("app;dur="))

    val propagated = client.get("/api/products/1") { header(HttpHeaders.XRequestId, "abc-12345678") }
    assertEquals("abc-12345678", propagated.headers[HttpHeaders.XRequestId])

    val rejected = client.get("/api/products/1") { header(HttpHeaders.XRequestId, "malo con espacios") }
    assertNotEquals("malo con espacios", rejected.headers[HttpHeaders.XRequestId])
}
```

El último caso es el que importa: cuando `verify` devuelve `false`, `CallId` descarta ese valor y pasa al siguiente proveedor, que es tu `generate`, así que la respuesta lleva un id nuevo y nunca el que mandó el cliente. Corré el test y mirá la salida: cada línea de log de las tres peticiones tiene que tener su id entre corchetes.""",
            },
        ]
    },
    # 28) Spring con Kotlin: clases finales, proxies de CGLIB y NPE en un servicio @Transactional (usuario trae traza).
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Spring Boot 3 con Kotlin. Al principio Spring se quejaba de que la clase era final, así que pusimos `open class OrderService`. Ahora arranca, pero cualquier llamada al servicio da esto:

```
java.lang.NullPointerException: Cannot invoke "com.acme.shop.orders.OrderRepository.save(Object)" because "this.orders" is null
	at com.acme.shop.orders.OrderService.placeOrder(OrderService.kt:18)
	at com.acme.shop.orders.OrderController.create(OrderController.kt:24)
```

```kotlin
@Service
open class OrderService(private val orders: OrderRepository) {
    @Transactional
    fun placeOrder(command: PlaceOrder): Order {
        val order = Order(customerId = command.customerId)
        command.items.forEach { order.addItem(it.productId, it.quantity) }
        return orders.save(order)
    }
}
```

¿Cómo puede ser null algo que se inyecta por constructor y no es nullable?""",
            },
            {
                "role": "assistant",
                "content": r"""Porque el objeto que ejecuta `placeOrder` **no es tu `OrderService`, sino el proxy** que Spring crea para aplicar `@Transactional`, y ese proxy nunca pasó por tu constructor.

### Qué está pasando

1. `@Transactional` hace que Spring cree una subclase de `OrderService` con CGLIB. Esa subclase sobrescribe los métodos para abrir la transacción y luego delegar en tu instancia real, que sí tiene `orders` inyectado.
2. El proxy se instancia **sin llamar al constructor** (con Objenesis), así que sus propios campos quedan a `null`, con independencia de que Kotlin los declare no anulables.
3. En Kotlin, las clases **y los métodos** son `final` por defecto. Abriste la clase, pero `placeOrder` sigue siendo final: CGLIB no puede sobrescribirlo.
4. Resultado: el controlador llama a `placeOrder` sobre el proxy, el método final se ejecuta **en el propio proxy** (no se delega), lee `this.orders` del proxy, y es `null`. Y de paso, no hay transacción.

La traza lo confirma: el NPE ocurre dentro de `OrderService.placeOrder`, no en el repositorio, y el campo nulo es `this.orders`.

### Arreglo: el plugin `kotlin-spring`

No abras clases a mano. El plugin de compilación `kotlin-spring` (una configuración preparada de *all-open*) abre automáticamente las clases y sus métodos cuando llevan anotaciones de Spring: `@Component` y derivadas (`@Service`, `@Configuration`...), `@Transactional`, `@Async`, `@Cacheable` y `@SpringBootTest`.

```kotlin
// build.gradle.kts
plugins {
    kotlin("jvm") version "2.1.20"
    kotlin("plugin.spring") version "2.1.20"
    kotlin("plugin.jpa") version "2.1.20"
    id("org.springframework.boot") version "3.4.5"
    id("io.spring.dependency-management") version "1.1.7"
}

// Las entidades también deben ser abiertas para que Hibernate pueda crear proxies lazy.
allOpen {
    annotation("jakarta.persistence.Entity")
    annotation("jakarta.persistence.MappedSuperclass")
    annotation("jakarta.persistence.Embeddable")
}
```

Y el servicio vuelve a ser idiomático, sin `open`:

```kotlin
@Service
class OrderService(private val orders: OrderRepository) {
    @Transactional
    fun placeOrder(command: PlaceOrder): Order {
        val order = Order(customerId = command.customerId)
        command.items.forEach { order.addItem(it.productId, it.quantity) }
        return orders.save(order)
    }
}
```

Lo que hace cada plugin:

- **`plugin.spring`**: abre lo anotado con Spring. Es lo que te faltaba; el error del principio («la clase no puede ser final») era el síntoma.
- **`plugin.jpa`**: genera el constructor sin argumentos que JPA exige en las entidades, sin que tengas que escribirlo.
- **`allOpen` para entidades**: Hibernate crea subclases para las relaciones *lazy*; con entidades finales, o no hay carga diferida o falla.

Si creas proyectos desde start.spring.io con Kotlin, todo esto ya viene configurado. Este problema aparece casi siempre en proyectos montados a mano.

### Comprobación

```kotlin
@SpringBootTest
class OrderServiceProxyTest(@Autowired private val service: OrderService) {

    @Test
    fun `el servicio es un proxy y el metodo corre en una transaccion`() {
        assertTrue(AopUtils.isAopProxy(service))
        assertFalse(Modifier.isFinal(OrderService::class.java.getMethod("placeOrder", PlaceOrder::class.java).modifiers))
    }
}
```

El segundo `assert` es el que habría detectado tu bug antes de producción: comprueba que el método es sobrescribible. Después, en el propio `placeOrder`, un `check(TransactionSynchronizationManager.isActualTransactionActive())` temporal te confirma que la transacción está activa; quítalo cuando lo veas pasar.

Revisa además el resto de clases donde se añadió `open` a mano: con el plugin ya no hace falta, y cualquier método que se quedó sin `open` en una de ellas tiene este mismo bug latente.""",
            },
        ]
    },
    # 29) Spring con Kotlin: @field: en Bean Validation y entidades JPA que no deben ser data class (multiturno).
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Spring Boot 3 con Kotlin. Tengo esto y la validación no hace nada, el POST con `name` vacío se guarda igual:

```kotlin
data class CreateUserRequest(
    @NotBlank val name: String,
    @Email val email: String,
)

@PostMapping("/api/users")
fun create(@Valid @RequestBody request: CreateUserRequest): UserResponse = users.create(request)
```""",
            },
            {
                "role": "assistant",
                "content": r"""Las anotaciones están en el sitio equivocado del bytecode. En Kotlin, `@NotBlank val name: String` en un constructor primario podría aplicarse al parámetro del constructor, a la propiedad, al campo o al *getter*, y la regla por defecto elige **el parámetro**. Bean Validation, al validar un objeto con `@Valid`, mira los **campos y getters**, no los parámetros del constructor. Las restricciones existen, pero nadie las lee.

Se arregla indicando el destino con `@field:`:

```kotlin
data class CreateUserRequest(
    @field:NotBlank
    @field:Size(max = 100)
    val name: String,

    @field:NotBlank
    @field:Email
    val email: String,
)
```

Las versiones recientes de Kotlin (2.2) incorporan una opción para que las anotaciones de un parámetro-propiedad se apliquen también a la propiedad y al campo; mientras no la actives en tu compilación, escribe `@field:` explícito.

Un segundo detalle relacionado con la nulabilidad: si el JSON **no trae** `name`, Jackson (con `jackson-module-kotlin`) ni siquiera puede construir el objeto, porque `name` no admite `null`, y Spring responde 400 por `HttpMessageNotReadableException` antes de validar. Es correcto, pero con una forma de error distinta a la de `@NotBlank`. Si quieres que «falta el campo» y «campo vacío» salgan igual en tu `ProblemDetail`, declara el campo como `String?` con `@field:NotNull` y `@field:NotBlank`, y usa `request.name!!` solo después de validar.

Comprobación:

```kotlin
@WebMvcTest(UserController::class)
class UserControllerTest(@Autowired private val mvc: MockMvc) {
    @MockitoBean
    private lateinit var users: UserService

    @Test
    fun `nombre vacio es 400`() {
        mvc.post("/api/users") {
            contentType = MediaType.APPLICATION_JSON
            content = "{\"name\":\"\",\"email\":\"ana@example.com\"}"
        }.andExpect { status { isBadRequest() } }
    }
}
```

`mvc.post { }` es el DSL de MockMvc para Kotlin que trae Spring. Antes del arreglo este test da 200; después, 400.""",
            },
            {
                "role": "user",
                "content": "Entendido. Ya que estamos: ¿las entidades JPA pueden ser `data class`? Queda mucho más corto.",
            },
            {
                "role": "assistant",
                "content": r"""Para entidades, no. Las tres funciones que `data class` genera chocan con cómo trabaja Hibernate:

1. **`equals`/`hashCode` sobre todas las propiedades.** El `id` cambia de `null` a un valor al persistir, así que el `hashCode` de la entidad cambia mientras está dentro de un `HashSet`: el set deja de encontrarla. Y dos instancias que representan la misma fila con un campo modificado dejan de ser «iguales».
2. **`toString` recorre todas las propiedades**, incluidas las colecciones *lazy*: una línea de log dispara consultas, lanza `LazyInitializationException` fuera de la transacción, o entra en recursión infinita con relaciones bidireccionales (`Order` imprime sus `items`, que imprimen su `order`...).
3. **`copy()`** crea otra instancia con el mismo `id` que Hibernate no gestiona: invita a modificar la copia y esperar que se guarde.

Usa una clase normal y escribe `equals`/`hashCode` a propósito:

```kotlin
@Entity
@Table(name = "orders")
class Order(
    @Column(name = "customer_id", nullable = false)
    var customerId: Long,
) {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    var id: Long? = null

    @OneToMany(mappedBy = "order", cascade = [CascadeType.ALL], orphanRemoval = true)
    var items: MutableList<OrderItem> = mutableListOf()
        protected set

    fun addItem(productId: Long, quantity: Int) {
        items += OrderItem(order = this, productId = productId, quantity = quantity)
    }

    // Igualdad por identidad de base de datos; las entidades nuevas (id null) solo son iguales a sí mismas.
    override fun equals(other: Any?): Boolean {
        if (this === other) return true
        if (other == null || Hibernate.getClass(this) != Hibernate.getClass(other)) return false
        other as Order
        return id != null && id == other.id
    }

    // Constante por clase: no cambia al asignarse el id.
    override fun hashCode(): Int = Hibernate.getClass(this).hashCode()

    override fun toString() = "Order(id=$id, customerId=$customerId)"
}
```

Por qué cada pieza:

- **`Hibernate.getClass`** en vez de `javaClass`: una referencia *lazy* es una subclase proxy de `Order`, y debe ser igual a la entidad real con el mismo `id`.
- **`hashCode` constante**: suena ineficiente, pero las colecciones de entidades son pequeñas y es la única forma de que el valor no cambie al persistir.
- **`toString` explícito** sin colecciones.
- **`protected set`** en `items`: desde fuera solo se añade con `addItem`, que mantiene los dos lados de la relación.

Los `data class` siguen siendo perfectos para **DTOs** (`CreateUserRequest`, `OrderResponse`): ahí la igualdad por valor es justo lo que quieres.

Comprobación del punto 1, que es el que más daño hace en silencio:

```kotlin
@DataJpaTest
class OrderEqualityTest(@Autowired private val em: TestEntityManager) {
    @Test
    fun `sigue en el set despues de persistir`() {
        val order = Order(customerId = 42)
        val set = hashSetOf(order)

        em.persistAndFlush(order) // asigna el id

        assertTrue(order in set)
    }
}
```

Con una `data class` este test falla: el `hashCode` cambió al asignarse el `id` y el set ya no encuentra el objeto que contiene.""",
            },
        ]
    },
    # 30) Decisión: Ktor o Spring Boot para un equipo Kotlin.
    {
        "messages": [
            {
                "role": "user",
                "content": "Somos un equipo de 6 que programa en Kotlin y vamos a reescribir un monolito Node en 4 o 5 servicios. Unos quieren Ktor por ligero, otros Spring Boot por el ecosistema. ¿Cómo lo decidimos sin que sea una pelea de gustos?",
            },
            {
                "role": "assistant",
                "content": r"""Convirtiendo la pregunta en requisitos y viendo cuántos trae resueltos cada opción. La diferencia real no es «ligero contra pesado»: es **ensamblar tú las piezas** (Ktor) contra **recibirlas integradas** (Spring Boot).

### Lo que cada uno te da de serie

| Necesidad | Ktor 3 | Spring Boot 3 con Kotlin |
|---|---|---|
| HTTP, JSON, rutas | sí, con plugins | sí |
| Corrutinas | nativas en todo el framework | soportadas en WebFlux; en MVC lo natural es código bloqueante con hilos virtuales |
| Inyección de dependencias | manual, Koin, o el plugin de DI que añadió Ktor 3.2 | el núcleo de Spring |
| Seguridad (OAuth2, JWT, sesiones, CSRF) | plugins básicos; el resto lo construyes | Spring Security completo |
| Acceso a datos | eliges (Exposed, jOOQ, JDBC) y lo integras | Spring Data JPA/JDBC, transacciones declarativas |
| Mensajería (Kafka, RabbitMQ) | clientes directos | Spring Kafka / AMQP integrados |
| Salud, métricas, configuración operativa | plugins sueltos | Actuator |
| Tests de integración | `testApplication`, muy rápido | slices, Testcontainers integrado, más lentos de arrancar |
| Arranque y memoria | muy bajos | mayores (mejoran con CDS o GraalVM nativo) |

### Cómo decidir

1. **Listad los requisitos de los 5 servicios**, no los gustos: ¿OAuth2 contra un IdP corporativo? ¿Kafka con reintentos y *dead letter*? ¿Transacciones que cruzan varias tablas? ¿Alguno es solo un proxy o un *gateway*?
2. **Contad cuántos son «infraestructura que alguien tiene que construir y mantener» en Ktor.** Cada fila de la tabla donde Ktor dice «lo construyes» es código vuestro, con sus bugs y sin la documentación de miles de proyectos detrás. Con 6 personas, ese mantenimiento compite con el producto.
3. **Pesad la experiencia del equipo.** Si nadie ha mantenido Spring en producción, su curva (proxies, configuración automática, el orden de los filtros de seguridad) también es un coste real. Si venís de Node, Ktor se parece más a Express.

Regla práctica que suele salir de ese ejercicio:

- Servicios con **seguridad compleja, mensajería o mucho acceso a datos transaccional** → Spring Boot. Lo que ahorráis en integración supera lo que pagáis en arranque y memoria.
- Servicios **pequeños y focalizados** (un *gateway*, un servicio de notificaciones, algo con muchas conexiones concurrentes y poca lógica) → Ktor encaja muy bien.
- **No mezcléis por gusto.** Dos frameworks en 5 servicios significa dos formas de hacer logs, configuración, seguridad y tests. Mezclad solo si un servicio concreto lo justifica con un requisito medible.

### Cómo convertirlo en evidencia

Una semana de *spike* con el requisito **más arriesgado** implementado en los dos, no un «hola mundo»: por ejemplo, el endpoint autenticado contra vuestro IdP que lee de Postgres y publica en Kafka. Medid:

- horas hasta tenerlo funcionando con tests;
- líneas de código propio de infraestructura (configuración de seguridad, transacciones, reintentos);
- memoria y tiempo de arranque en un contenedor con los límites reales;
- p99 bajo una carga realista con k6.

Si Ktor gana en arranque y memoria pero pierde por días en seguridad y mensajería, la decisión está tomada con datos y el equipo la entiende. Si ningún servicio necesita lo que Spring integra, Ktor es la elección más simple, y también estará justificada.

Dejadlo escrito en un ADR de una página con la tabla de requisitos y los resultados del *spike*. Dentro de un año, cuando alguien pregunte «¿por qué no usamos X?», la respuesta estará ahí y no en la memoria de quien ganó la discusión.""",
            },
        ]
    },
]
