"""Otros lenguajes: PHP 8.3, Ruby 3, Swift 5.9+, Dart 3, Haskell, Elixir, Zig, Lua, Scala 3 y R."""

SISTEMA = (
    "Eres un asistente experto en programación, análisis y razonamiento. Respondes en el "
    "idioma del usuario (español por defecto), con precisión y sin relleno, y verificas tu "
    "trabajo antes de responder."
)

ROWS = [
    # 1) PHP 8.3: enums, readonly, match, promoción de constructor (system exacto)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "Tengo un PHP viejo lleno de constantes `STATUS_PENDING = 'pending'` y arrays de configuración. Estoy migrando a PHP 8.3, ¿qué construcciones modernas debería usar para un modelo de pedido con estado?"},
            {
                "role": "assistant",
                "content": r"""Tres piezas de PHP 8.1-8.3 sustituyen ese patrón: **enums con respaldo** para el estado, **clases `readonly` con promoción de constructor** para el modelo, y **`match`** para la lógica por estado.

```php
<?php
declare(strict_types=1);

namespace App\Orders;

enum OrderStatus: string
{
    case Pending = 'pending';
    case Paid = 'paid';
    case Shipped = 'shipped';
    case Cancelled = 'cancelled';

    public function label(): string
    {
        return match ($this) {
            self::Pending => 'Pendiente de pago',
            self::Paid => 'Pagado',
            self::Shipped => 'Enviado',
            self::Cancelled => 'Cancelado',
        };
    }

    public function canTransitionTo(self $next): bool
    {
        return match ($this) {
            self::Pending => in_array($next, [self::Paid, self::Cancelled], true),
            self::Paid => $next === self::Shipped || $next === self::Cancelled,
            self::Shipped, self::Cancelled => false,
        };
    }
}

final readonly class Order
{
    public function __construct(
        public int $id,
        public OrderStatus $status,
        public float $total,
        public ?string $note = null,
    ) {
        if ($total < 0) {
            throw new \InvalidArgumentException("Total cannot be negative: $total");
        }
    }

    public function withStatus(OrderStatus $next): self
    {
        if (!$this->status->canTransitionTo($next)) {
            throw new \DomainException("Cannot go from {$this->status->value} to {$next->value}");
        }
        return new self($this->id, $next, $this->total, $this->note);
    }
}
```

Por qué cada elección:

- **`enum OrderStatus: string`** (8.1): el tipo garantiza que `$order->status` solo puede ser uno de los cuatro casos; con constantes de cadena, cualquier `string` colaba. `OrderStatus::from('paid')` convierte desde la base de datos y lanza `ValueError` si el valor no existe; `tryFrom` devuelve `null`. `->value` da la cadena para persistir. Los métodos dentro del enum sustituyen a los `switch` repartidos por el código.
- **`match`** (8.0) comprueba con `===`, devuelve un valor y **lanza `UnhandledMatchError` si ningún brazo coincide**; con un enum, el IDE y PHPStan te avisan si olvidas un caso. Un `switch` con `==` compara de forma laxa y sigue en silencio.
- **`final readonly class`** (8.2): todas las propiedades son de solo lectura tras el constructor; cambiar de estado produce un objeto nuevo (`withStatus`). Para una entidad que un ORM necesite mutar, quita `readonly` de la clase y ponlo solo en `id`.
- **Promoción de constructor** (8.0): `public int $id` en la firma declara la propiedad, la tipa y la asigna. Los tipos son los de PHP, verificados en tiempo de ejecución con `strict_types=1` (sin él, `'3'` se convertiría a `3`).
- `?string $note = null` es un tipo anulable explícito; `float|int` o `int|null` también son válidos (tipos unión, 8.0).

Dos añadidos de 8.3 que encajan aquí: **constantes de clase tipadas** (`public const string TABLE = 'orders';`) y el atributo **`#[\Override]`**, que hace fallar la compilación si un método marcado no sobrescribe nada de la clase padre (detecta el típico *typo* al renombrar).

Uso y comprobación:

```php
$order = new Order(id: 1, status: OrderStatus::Pending, total: 99.5);
$paid = $order->withStatus(OrderStatus::Paid);

assert($paid->status === OrderStatus::Paid);
assert($order->status === OrderStatus::Pending);        // el original no cambió
assert(OrderStatus::tryFrom('refunded') === null);

try {
    $paid->withStatus(OrderStatus::Pending);
} catch (\DomainException $e) {
    echo $e->getMessage(), PHP_EOL;                       // Cannot go from paid to pending
}
```

Los argumentos con nombre (`id: 1`) son de 8.0 y hacen legible un constructor con varios parámetros del mismo tipo.""",
            },
        ]
    },
    # 2) PHP: comparación laxa y strict_types (código del usuario)
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Un formulario envía `code` y comparo contra una lista de códigos válidos. Hay entradas que pasan la validación sin estar en la lista. PHP 8.3:

```php
$validCodes = ['0', 'ABC', '1e3'];
$code = $_POST['code'];

if (in_array($code, $validCodes)) {
    grantAccess();
}

if ($code == 0) {
    echo "código cero";
}
```

Con `code=1000` entra el acceso y con `code=abc` imprime «código cero». ¿Qué está pasando?""",
            },
            {
                "role": "assistant",
                "content": r"""Las dos comparaciones son **laxas** (`==`), y PHP convierte los operandos antes de comparar. Los dos síntomas tienen explicación exacta:

- **`in_array('1000', ['0', 'ABC', '1e3'])` es `true`** porque `in_array` usa `==` por defecto, y al comparar dos cadenas **numéricas** PHP las compara como números: `'1000' == '1e3'` → `1000 == 1000.0` → `true`. Un código válido escrito en notación científica abre la puerta a cualquiera que escriba su equivalente decimal.
- **`'abc' == 0`** en PHP 8 es `false` (en PHP 7 era `true`: ese cambio fue uno de los grandes de la versión 8). Lo que te está pasando es que `$code` no es `'abc'` sino otra cosa: si el campo no llega, `$_POST['code']` es `null` con un aviso, y `null == 0` es `true`. O llega `''`, y `'' == 0` también es `false` en PHP 8 pero `'' == null` es `true`. Hay que ver el valor real; en cualquier caso, la comparación laxa con `0` es la que te deja en esa ambigüedad.

Arreglo: comparación **estricta** en todas partes, y validar el tipo del dato de entrada antes de usarlo.

```php
<?php
declare(strict_types=1);

$validCodes = ['0', 'ABC', '1e3'];

$code = $_POST['code'] ?? null;
if (!is_string($code) || $code === '') {
    http_response_code(400);
    exit('missing code');
}

if (in_array($code, $validCodes, strict: true)) {   // compara con ===: solo coincide la misma cadena
    grantAccess();
}

if ($code === '0') {
    echo "código cero";
}
```

Lo que cambia:

1. **`in_array(..., true)`**: tercer parámetro `strict`. Con `===`, `'1000'` y `'1e3'` son cadenas distintas. Lo mismo aplica a `array_search` y `array_keys` con valor: todos tienen el parámetro `strict`.
2. **`===` en vez de `==`**: no convierte tipos. Si necesitas comparar con un número, convierte tú de forma explícita y validada: `filter_var($code, FILTER_VALIDATE_INT)` devuelve `int` o `false`.
3. **`declare(strict_types=1)`** no afecta a `==` (eso es comparación, no paso de parámetros), pero evita que un `string` entre en una función tipada `int` por conversión silenciosa. Va en la primera línea de cada archivo.
4. **`??` y comprobación de tipo** para el dato de `$_POST`: puede no existir, puede ser un array (`code[]=x` en la URL) y puede estar vacío; `is_string` descarta los tres casos antes de comparar.

Las reglas de `==` que conviene conocer para leer código ajeno (PHP 8):

| Comparación | Resultado | Por qué |
|---|---|---|
| `'1e3' == '1000'` | `true` | Dos cadenas numéricas se comparan como números |
| `'abc' == 0` | `false` | Desde PHP 8, el número se convierte a cadena si la cadena no es numérica |
| `null == false`, `null == 0`, `null == ''` | `true` | `null` se convierte al tipo del otro operando |
| `'1' == '01'` | `true` | Numéricas |
| `'1' === '01'` | `false` | Tipo y valor |
| `[] == false` | `true` | Array vacío es falsy |

Una comprobación que reproduce tu bug y verifica el arreglo:

```php
var_dump(in_array('1000', $validCodes));          // bool(true)   <- el agujero
var_dump(in_array('1000', $validCodes, true));    // bool(false)
var_dump(null == 0, '' == 0, 'abc' == 0);         // true, false, false
```

Para que esto no vuelva a entrar, PHPStan en nivel 7 o superior marca `in_array` sin `strict` y las comparaciones laxas entre tipos distintos; Psalm tiene la regla equivalente. Y en código nuevo, `match` en vez de `switch`: compara siempre con `===`.""",
            },
        ]
    },
    # 3) PHP: Composer, PSR-4, autoload (multiturno)
    {
        "messages": [
            {"role": "user", "content": "Estoy montando un proyecto PHP desde cero sin framework. ¿Cómo organizo el código con Composer para no tener `require 'archivo.php'` por todas partes?"},
            {
                "role": "assistant",
                "content": r"""Con el **autoload PSR-4** de Composer: declaras que un prefijo de namespace corresponde a un directorio, y a partir de ahí PHP carga cada clase por su nombre completo la primera vez que la usas. Cero `require` manuales.

Estructura mínima:

```
proyecto/
├── composer.json
├── public/
│   └── index.php
├── src/
│   ├── Orders/
│   │   └── OrderRepository.php     → clase App\Orders\OrderRepository
│   └── Kernel.php                  → clase App\Kernel
└── tests/
    └── Orders/
        └── OrderRepositoryTest.php → clase App\Tests\Orders\OrderRepositoryTest
```

```json
{
    "name": "acme/proyecto",
    "type": "project",
    "require": {
        "php": "^8.3",
        "psr/log": "^3.0"
    },
    "require-dev": {
        "phpunit/phpunit": "^11.0",
        "phpstan/phpstan": "^1.11"
    },
    "autoload": {
        "psr-4": { "App\\": "src/" }
    },
    "autoload-dev": {
        "psr-4": { "App\\Tests\\": "tests/" }
    },
    "scripts": {
        "test": "phpunit",
        "analyse": "phpstan analyse src --level 8"
    },
    "config": {
        "sort-packages": true
    }
}
```

La regla PSR-4: el namespace `App\Orders\OrderRepository` se traduce al archivo `src/Orders/OrderRepository.php`; **un archivo por clase**, nombre del archivo igual al de la clase, directorios iguales a los subnamespaces, mayúsculas incluidas (en Linux el sistema de archivos distingue).

El punto de entrada carga el autoloader una vez:

```php
<?php
// public/index.php
declare(strict_types=1);

require dirname(__DIR__) . '/vendor/autoload.php';

use App\Kernel;

(new Kernel())->run();
```

Comandos del día a día:

```bash
composer install            # instala lo del composer.lock (o resuelve y crea el lock si no existe)
composer require monolog/monolog        # añade una dependencia y actualiza el lock
composer require --dev vimeo/psalm      # solo para desarrollo
composer dump-autoload                  # regenera el autoloader tras crear clases en rutas nuevas
composer test                           # ejecuta el script "test"
```

Tres cosas que importan:

1. **`require` frente a `require-dev`**: en producción se instala con `composer install --no-dev --optimize-autoloader`, y lo de `require-dev` (PHPUnit, PHPStan) no viaja. `--optimize-autoloader` genera un mapa de clases estático en vez de buscar en disco; úsalo siempre en el despliegue.
2. **`autoload-dev`** mantiene los tests fuera del autoloader de producción.
3. **`^8.3` en `php`**: Composer se niega a instalar paquetes incompatibles con esa versión y documenta el requisito. El acento circunflejo significa «compatible con»: `^3.0` acepta `3.x` pero no `4.0`.

Para el estilo de código, el estándar es **PSR-12** (sucesor de PSR-2): `php-cs-fixer` o `phpcs` lo aplican; `composer require --dev friendsofphp/php-cs-fixer` y un script `"fix": "php-cs-fixer fix src"`.

Comprobación: crea `src/Orders/OrderRepository.php` con `namespace App\Orders; final class OrderRepository {}` y en `index.php` escribe `new \App\Orders\OrderRepository();`. Debe funcionar sin ningún `require` adicional. Si da `Class not found`, los tres sospechosos son: el namespace no coincide con la ruta, el nombre del archivo no coincide con la clase, o falta `composer dump-autoload` tras cambiar `composer.json`.""",
            },
            {"role": "user", "content": "¿El `composer.lock` lo subo al repositorio? Un compañero dice que solo para aplicaciones, no para librerías, y no entiendo la diferencia."},
            {
                "role": "assistant",
                "content": r"""Tu compañero tiene razón, y la diferencia es quién decide las versiones finales.

**Aplicación (`"type": "project"`): sí, súbelo.** El `composer.lock` fija la versión exacta de cada dependencia (y de las dependencias de las dependencias) que se resolvió la última vez. Con el lock en el repositorio, `composer install` instala **las mismas versiones** en tu máquina, en la de tu compañero, en CI y en producción. Sin él, cada `install` resuelve de nuevo contra Packagist y dos despliegues con un día de diferencia pueden llevar versiones distintas de la misma librería, con un bug que «solo pasa en producción».

Flujo correcto en una aplicación:

```bash
composer require vendor/paquete     # cambia composer.json y composer.lock → commit de los dos
composer update vendor/paquete      # sube solo ese paquete dentro del rango permitido → commit del lock
composer update                     # sube todo lo que el rango permita; hazlo a propósito, no por accidente
composer install                    # lo que ejecutan CI y producción: nunca cambia el lock
```

En CI, `composer install` falla si `composer.json` y `composer.lock` no están sincronizados (`The lock file is not up to date with the latest changes in composer.json`), lo que te avisa de que alguien editó el JSON a mano sin regenerar el lock. Añade `composer validate --strict` al pipeline para detectarlo antes.

**Librería (`"type": "library"`): no lo subas.** Cuando alguien instala tu librería, Composer **ignora el lock de la librería**: resuelve las dependencias de todo el proyecto a la vez, con los rangos de tu `composer.json`. Tu lock no afecta a nadie y, si lo subes, dos problemas:

1. Tus tests en CI usan las versiones congeladas del lock y no las que tus usuarios tendrán, así que no detectas que una dependencia nueva rompe tu librería dentro del rango que declaras.
2. Cada `composer update` para mantener el lock al día es un commit sin valor.

Lo que una librería sí debe hacer: declarar rangos honestos (`"symfony/console": "^6.4 || ^7.0"`) y probar en CI contra los extremos del rango con `composer update --prefer-lowest` y `composer update` (más altas), para asegurar que ambos funcionan.

Un detalle para las dos: `/vendor/` va siempre en `.gitignore`; el lock es suficiente para reconstruirlo.

Comprobación práctica de que el lock hace su trabajo en tu aplicación: borra `vendor/`, ejecuta `composer install` y compara `composer show` con la salida en otra máquina; deben coincidir versión por versión.""",
            },
        ]
    },
    # 4) Ruby: bloques, procs, lambdas (system variante rioplatense)
    {
        "messages": [
            {"role": "system", "content": "Respondé en español rioplatense, con voseo, sin perder precisión técnica."},
            {"role": "user", "content": "Vengo de JavaScript y en Ruby no termino de entender los bloques. ¿Qué diferencia hay entre un bloque, un proc y una lambda, y qué es ese `&:upcase`?"},
            {
                "role": "assistant",
                "content": r"""Un **bloque** es un trozo de código que le pasás a un método, pero no es un objeto: no lo podés guardar en una variable. Cada método acepta **un** bloque implícito y lo ejecuta con `yield`.

```ruby
def repeat(times)
  times.times { |i| yield i }
end

repeat(3) { |i| puts "vuelta #{i}" }
```

Si querés guardar o pasar el bloque como objeto, lo convertís en **Proc** con `&` en la firma, o lo creás directamente:

```ruby
def repeat(times, &block)     # el & captura el bloque como objeto Proc
  times.times { |i| block.call(i) }
end

saludar = proc { |name| puts "hola #{name}" }
saludar.call("Ana")
repeat(2, &saludar)           # el & hace lo inverso: pasa un Proc como bloque
```

Una **lambda** es un Proc con dos diferencias, y las dos importan:

| | `proc { }` / bloque | `lambda { }` / `-> { }` |
|---|---|---|
| Argumentos de más o de menos | Los ignora o rellena con `nil` | `ArgumentError`, como un método |
| `return` adentro | Sale del **método que lo contiene** | Sale solo de la lambda |

```ruby
l = ->(a, b) { a + b }
l.call(1, 2)        # 3
l.(1, 2)            # 3, sintaxis abreviada
l.call(1)           # ArgumentError: wrong number of arguments (given 1, expected 2)

p = proc { |a, b| [a, b] }
p.call(1)           # [1, nil]  sin quejarse

def test
  pr = proc { return "desde el proc" }
  pr.call
  "nunca llego acá"
end
test                # "desde el proc"
```

Por eso en código que se parece a una función (callbacks guardados, valores de un hash, *strategies*) se usan lambdas, y los procs quedan para los bloques que pasan de un método a otro.

**`&:upcase`.** Es un atajo que combina dos cosas: `:upcase` es un **Symbol** (un nombre inmutable e internado; pensá en una cadena única para identificar cosas), y el `&` le pide al símbolo que se convierta en Proc con `to_proc`. El resultado es un Proc que recibe un objeto y le llama al método de ese nombre:

```ruby
%w[ana luis].map(&:upcase)            # ["ANA", "LUIS"]
%w[ana luis].map { |s| s.upcase }     # exactamente lo mismo, escrito largo
[1, 2, 3].select(&:even?)             # [2]
```

Sirve cuando el bloque es «llamá a este método sin argumentos». Si necesitás argumentos o lógica, escribís el bloque completo. En Ruby 3.4 además hay `it` como parámetro implícito (`map { it.upcase }`), y desde 2.7 los parámetros numerados (`map { _1.upcase }`).

Equivalencias con JavaScript para asentar la idea: un bloque es como la *callback* que le pasás a `arr.map(x => ...)`, pero sin ser un valor; una lambda es una *arrow function* de verdad; `&:upcase` es `x => x.upcase()`.

Comprobá la diferencia de `return` vos mismo: cambiá el `proc` del método `test` por `lambda` y vas a obtener `"nunca llego acá"`.""",
            },
        ]
    },
    # 5) Ruby: Enumerable y lazy
    {
        "messages": [
            {"role": "user", "content": "Tengo una clase `Playlist` que guarda canciones en un array interno y he escrito `map`, `select`, `find`, `sort_by`, `first`, todos delegando al array. Tiene que haber una forma mejor en Ruby."},
            {
                "role": "assistant",
                "content": r"""La hay: incluye el módulo `Enumerable` y define **solo `each`**. Todos los demás métodos (`map`, `select`, `find`, `sort_by`, `first`, `min_by`, `group_by`, `sum`, `each_slice`, `lazy`, unos cincuenta) vienen gratis, implementados sobre tu `each`.

```ruby
Song = Data.define(:title, :artist, :seconds)   # Ruby 3.2+: objeto de valor inmutable

class Playlist
  include Enumerable

  def initialize(songs = [])
    @songs = songs.dup
  end

  def add(song)
    @songs << song
    self
  end

  def each(&block)
    return enum_for(:each) { @songs.size } unless block_given?
    @songs.each(&block)
    self
  end
end
```

Dos detalles del `each` que marcan la diferencia entre «funciona» y «es idiomático»:

- **`return enum_for(:each) unless block_given?`**: cuando alguien llama `playlist.each` sin bloque, devuelves un `Enumerator`, igual que hace `Array#each`. Eso permite `playlist.each.with_index`, `playlist.each_slice(2)` y encadenar. El bloque de `enum_for` opcional da el tamaño para `size` sin recorrer.
- **Devolver `self`** mantiene la convención de los `each` de la biblioteca estándar.

Con eso, todo esto funciona sin escribir nada más:

```ruby
pl = Playlist.new
  .add(Song.new("Blue", "Joni", 200))
  .add(Song.new("River", "Joni", 240))
  .add(Song.new("Harvest", "Neil", 190))

pl.map(&:title)                           # ["Blue", "River", "Harvest"]
pl.select { |s| s.artist == "Joni" }.size # 2
pl.min_by(&:seconds).title                # "Harvest"
pl.sum(&:seconds)                         # 630
pl.group_by(&:artist).transform_values(&:count)  # {"Joni"=>2, "Neil"=>1}
pl.sort_by { |s| [-s.seconds, s.title] }.map(&:title)  # orden descendente por duración
pl.each_with_index.map { |s, i| "#{i + 1}. #{s.title}" }
pl.include?(Song.new("Blue", "Joni", 200)) # true: Data compara por valor
pl.tally_by(&:artist)                      # {"Joni"=>2, "Neil"=>1}  (Ruby 3.1+)
```

Si además quieres `sort`, `min`, `max` sin bloque, define `<=>` en `Song` e incluye `Comparable` en ella; `Enumerable` lo usará.

**`lazy` para colecciones grandes o infinitas.** Los métodos de `Enumerable` son ansiosos: `select` recorre todo y crea un array antes de que `first` actúe. `lazy` encadena sin materializar:

```ruby
# Sin lazy: filtra las 10 000 y luego toma 3
pl.select { |s| s.seconds > 180 }.first(3)

# Con lazy: para en cuanto tiene 3
pl.lazy.select { |s| s.seconds > 180 }.map(&:title).first(3)

# Infinito: imposible sin lazy
(1..).lazy.map { |n| n * n }.select(&:even?).first(5)   # [4, 16, 36, 64, 100]
```

La regla: `lazy` compensa cuando la cadena tiene un `first`/`take`/`find` al final o la fuente es enorme; para arrays pequeños, la versión ansiosa es más rápida.

Comprobación de que tu clase es un `Enumerable` completo: `Playlist.include?(Enumerable)` es `true`, `pl.each.class` es `Enumerator`, y `pl.each_slice(2).to_a.size` es 2.""",
            },
        ]
    },
    # 6) Ruby: gems/Bundler y claves símbolo vs cadena (código del usuario)
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Script Ruby 3.3 que lee un YAML de configuración y falla con `undefined method 'fetch' for nil`. El YAML es:

```yaml
database:
  host: db.internal
  port: 5432
```

El código:

```ruby
require 'yaml'
config = YAML.load_file('config.yml')
db = config[:database]
host = db.fetch(:host)
```

También me pregunto cómo gestiono las gems que necesita (yaml, pg) para que otro pueda ejecutarlo.""",
            },
            {
                "role": "assistant",
                "content": r"""`config[:database]` devuelve `nil` porque las claves del hash que produce `YAML.load_file` son **cadenas** (`"database"`), no símbolos (`:database`). En Ruby `"database" != :database`; son objetos distintos, y un hash con clave cadena no encuentra nada al buscar por símbolo. De ahí el `nil` y el `fetch` sobre él.

Tres formas de arreglarlo, de más a menos recomendable:

**1. Pedir símbolos al cargar** (Psych 4 / Ruby 3.1+):

```ruby
require 'yaml'

config = YAML.safe_load_file('config.yml', symbolize_names: true)
db = config.fetch(:database)
host = db.fetch(:host)        # "db.internal"
port = db.fetch(:port)        # 5432 (entero: YAML tipa los escalares)
```

`symbolize_names: true` convierte las claves a símbolos en todos los niveles. `safe_load_file` en lugar de `load_file`: desde Ruby 3.1, `load_file` también es seguro por defecto (no instancia objetos arbitrarios), pero el nombre deja clara la intención. Y `fetch` en vez de `[]` para que una clave ausente lance `KeyError: key not found: :host` en lugar de propagar `nil` hasta un sitio lejano.

**2. Usar cadenas en el código**, si el hash lo consumen otras partes que esperan cadenas: `config.fetch("database").fetch("host")`.

**3. `transform_keys(&:to_sym)`** sobre un hash ya cargado (solo el primer nivel; para anidados, recursivo).

Lo que no conviene: `ActiveSupport::HashWithIndifferentAccess` para un script sin Rails; arrastra toda la gema para esconder una decisión que es mejor tomar.

**Gestión de gems con Bundler.** Un `Gemfile` en la raíz:

```ruby
# Gemfile
source "https://rubygems.org"

ruby "~> 3.3"

gem "pg", "~> 1.5"
```

`yaml` (Psych) es parte de la biblioteca estándar: no hace falta declararla. Luego:

```bash
bundle install          # resuelve, instala y escribe Gemfile.lock
bundle exec ruby script.rb
```

- `~> 1.5` es el operador «pesimista»: acepta `1.5`, `1.6`, `1.9` pero no `2.0`.
- **`Gemfile.lock` va al repositorio** (es un script/aplicación): fija las versiones exactas para quien lo ejecute después. `bundle install` instala lo del lock; `bundle update pg` sube una gema a propósito.
- **`bundle exec`** ejecuta el script con exactamente las gems del lock aunque en el sistema haya otras versiones. Para no escribirlo cada vez, el script puede empezar con `require "bundler/setup"`, que hace lo mismo desde dentro.
- `.ruby-version` con `3.3.x` deja que `rbenv`/`asdf` elijan el intérprete correcto.

Script completo:

```ruby
#!/usr/bin/env ruby
# frozen_string_literal: true

require "bundler/setup"
require "yaml"
require "pg"

config = YAML.safe_load_file("config.yml", symbolize_names: true)
db = config.fetch(:database)

conn = PG.connect(host: db.fetch(:host), port: db.fetch(:port), dbname: db.fetch(:name, "app"))
puts conn.exec("SELECT now()").getvalue(0, 0)
```

`# frozen_string_literal: true` hace inmutables los literales de cadena del archivo (menos asignaciones, y un error claro si algo intenta mutarlos); es la convención en Ruby moderno.

Comprobación: `ruby -ryaml -e 'p YAML.safe_load_file("config.yml").keys'` imprime `["database"]` (cadenas), y con `symbolize_names: true` imprime `[:database]`. Es la diferencia completa entre tu error y el script que funciona.""",
            },
        ]
    },
    # 7) Swift: optionals (multiturno)
    {
        "messages": [
            {"role": "user", "content": "Empiezo con Swift y me llenan el código de `!` para que compile. ¿Cómo se manejan bien los opcionales?"},
            {
                "role": "assistant",
                "content": r"""Un `String?` es «o un `String` o nada», y el compilador te obliga a decidir qué pasa en el caso de nada. Cada `!` es decirle «confía en mí, aquí nunca es `nil`»; cuando te equivocas, la app se cierra con `Fatal error: Unexpectedly found nil`. Las herramientas para no usarlo:

**1. `if let`: usa el valor dentro del bloque.**

```swift
let input: String? = readLine()

if let input {                    // Swift 5.7+: sin repetir el nombre
    print("has escrito \(input)")  // aquí input es String, no String?
} else {
    print("sin entrada")
}
```

**2. `guard let`: desenvuelve o sal.** Es el idiomático para precondiciones al principio de una función: el valor queda disponible en el resto del cuerpo, sin anidar.

```swift
func parsePort(_ text: String?) -> Int? {
    guard let text, let port = Int(text), (1...65535).contains(port) else {
        return nil
    }
    return port          // text y port son no opcionales desde el guard
}
```

**3. `??`: valor por defecto.**

```swift
let port = parsePort(ProcessInfo.processInfo.environment["PORT"]) ?? 8080
```

**4. Encadenamiento opcional `?.`: propaga el `nil`.** Si algo en la cadena es `nil`, el resultado entero es `nil` (y opcional).

```swift
struct User { var address: Address? }
struct Address { var city: String }

let user: User? = loadUser()
let city = user?.address?.city          // String?
let cityOrUnknown = user?.address?.city ?? "desconocida"
```

**5. `map` / `flatMap` sobre opcionales**, para transformar sin desenvolver:

```swift
let length = input.map { $0.count }               // Int?
let number = input.flatMap { Int($0) }            // Int? (Int(...) ya devuelve opcional; flatMap evita Int??)
```

**6. `switch` con patrones**, cuando quieres tratar los dos casos explícitamente:

```swift
switch user?.address {
case .some(let address): print(address.city)
case .none: print("sin dirección")
}
```

Cuándo `!` sí es aceptable: cuando `nil` sería un **error de programación** que quieres que explote en desarrollo, y lo dices: `let url = URL(string: "https://example.com")!` con una cadena literal que sabes válida. En cualquier dato que venga de fuera (red, usuario, disco), nunca.

Los **opcionales implícitos** (`var label: UILabel!`) existen por el ciclo de vida de UIKit (se asigna después del `init`); fuera de eso, evítalos.

Prueba mental para cada `!` que tengas: «¿qué pasa si aquí llega `nil`?». Si la respuesta es «la app debería cerrarse porque algo está muy roto», déjalo con un comentario; si es cualquier otra cosa, es uno de los seis patrones de arriba.""",
            },
            {"role": "user", "content": "¿Y para errores de verdad? Por ejemplo, parsear un número que viene de un archivo: `Int(texto)` me devuelve nil pero no sé por qué falló."},
            {
                "role": "assistant",
                "content": r"""Para eso Swift tiene errores tipados con `throws`: un opcional dice «no hay valor», un error dice **por qué**. Cuando el llamador necesita distinguir causas (vacío, no numérico, fuera de rango) o informar al usuario, se lanza un error.

```swift
enum ParseError: Error, Equatable {
    case empty
    case notANumber(String)
    case outOfRange(Int, ClosedRange<Int>)
}

func parsePort(_ text: String) throws -> Int {
    let trimmed = text.trimmingCharacters(in: .whitespaces)
    guard !trimmed.isEmpty else { throw ParseError.empty }
    guard let value = Int(trimmed) else { throw ParseError.notANumber(trimmed) }
    let valid = 1...65535
    guard valid.contains(value) else { throw ParseError.outOfRange(value, valid) }
    return value
}
```

Y el llamador elige cuánto le importa el detalle:

```swift
// 1) Tratar cada causa
do {
    let port = try parsePort(line)
    print("puerto \(port)")
} catch ParseError.empty {
    print("línea vacía")
} catch ParseError.notANumber(let raw) {
    print("'\(raw)' no es un número")
} catch ParseError.outOfRange(let v, let range) {
    print("\(v) fuera de \(range)")
} catch {
    print("error inesperado: \(error)")     // obligatorio: do/catch debe ser exhaustivo
}

// 2) Convertir a opcional cuando el motivo no importa
let port = try? parsePort(line)             // Int?

// 3) Propagar hacia arriba
func loadConfig() throws -> Config {
    let port = try parsePort(readPortLine())   // si falla, loadConfig lanza el mismo error
    return Config(port: port)
}
```

Tres cosas que conviene saber:

- **`try` es obligatorio** delante de cada llamada que puede lanzar; el compilador no deja olvidarlo. `try?` convierte en opcional, `try!` aborta si falla (misma regla que `!`: solo cuando el fallo es un bug).
- **`Result<Int, ParseError>`** es la alternativa cuando quieres guardar el resultado o pasarlo por un *callback*: `let r = Result { try parsePort(line) }` y luego `switch r { case .success(let p): ... case .failure(let e): ... }`. Con `async/await` ya casi no hace falta; `throws` es más directo.
- **Swift 6 añade `throws(ParseError)`**: errores tipados en la firma, de modo que el `catch` sabe el tipo exacto y no necesita el `catch` genérico final. En Swift 5.9/5.10 el tipo del error en `catch` es `any Error`.

Para que un error se lea bien al mostrarlo, adopta `LocalizedError`:

```swift
extension ParseError: LocalizedError {
    var errorDescription: String? {
        switch self {
        case .empty: "el valor está vacío"
        case .notANumber(let raw): "'\(raw)' no es un número entero"
        case .outOfRange(let v, let r): "\(v) está fuera del rango \(r.lowerBound)-\(r.upperBound)"
        }
    }
}
```

(Los `switch` como expresión sin `return` son de Swift 5.9.)

Prueba con XCTest, que es donde `Equatable` en el enum paga:

```swift
func testOutOfRange() {
    XCTAssertThrowsError(try parsePort("70000")) { error in
        XCTAssertEqual(error as? ParseError, .outOfRange(70000, 1...65535))
    }
}
```

Regla corta: opcional cuando «no hay» es un resultado normal y único; `throws` cuando hay varias formas de fallar o el llamador debe explicarlo.""",
            },
        ]
    },
    # 8) Swift: structs vs classes, protocols, some/any (system exacto)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "En Swift, ¿cuándo uso struct y cuándo class? Y en los protocolos veo `some Shape` y `any Shape`, no sé cuál elegir."},
            {
                "role": "assistant",
                "content": r"""**Struct por defecto; class cuando necesitas identidad o herencia.** Es la guía oficial de Apple y la razón es la semántica de copia.

| | `struct` (y `enum`) | `class` |
|---|---|---|
| Semántica | **Valor**: asignar o pasar copia | **Referencia**: varias variables, un objeto |
| Mutación | Solo en `var`, y los métodos que mutan llevan `mutating` | Cualquier referencia puede mutar |
| Herencia | No (sí conformar protocolos) | Sí |
| Identidad (`===`) | No tiene sentido | Sí |
| Memoria | Pila o *inline*; sin ARC | Heap, contador de referencias (ARC), posibles ciclos |
| Hilos | Seguro de compartir (cada uno tiene su copia) | Necesita sincronización (o `actor`) |

```swift
struct Point {
    var x: Double
    var y: Double

    mutating func move(dx: Double) { x += dx }       // mutating: cambia self (la copia)
    func moved(dx: Double) -> Point { Point(x: x + dx, y: y) }
}

var a = Point(x: 0, y: 0)
var b = a            // copia
b.move(dx: 5)
print(a.x, b.x)      // 0.0 5.0

final class Connection {
    var isOpen = false
    func open() { isOpen = true }
}
let c1 = Connection()
let c2 = c1          // misma instancia
c2.open()
print(c1.isOpen)     // true
```

`Connection` es una clase porque representa **una cosa concreta** con ciclo de vida (abrir, cerrar); copiarla no tendría sentido. `Point` es un valor: dos puntos con las mismas coordenadas son intercambiables. Lo mismo para modelos de datos, DTOs, configuraciones: struct. Para controladores de vista, gestores de recursos, nodos de un grafo con referencias mutuas: class.

Las colecciones de Swift (`Array`, `Dictionary`, `String`) son structs con *copy-on-write*: copiarlas es barato hasta que una de las copias muta. Puedes hacer lo mismo en tus structs con una clase interna de almacenamiento, pero rara vez hace falta.

**Protocolos: `some` frente a `any`.**

```swift
protocol Shape {
    var area: Double { get }
}
struct Circle: Shape { var r: Double; var area: Double { .pi * r * r } }
struct Square: Shape { var side: Double; var area: Double { side * side } }
```

- **`some Shape`** (tipo opaco): «un tipo concreto que conforma `Shape`, pero no te digo cuál». El compilador conoce el tipo real, así que no hay caja ni despacho dinámico; a cambio, **un solo tipo** por expresión.
- **`any Shape`** (existencial): «cualquier `Shape`, puede ser distinto en cada elemento». Se guarda en una caja con despacho dinámico; permite mezclar tipos.

```swift
func makeUnitCircle() -> some Shape { Circle(r: 1) }       // siempre Circle; el llamador solo ve Shape

func largest(_ shapes: [any Shape]) -> (any Shape)? {       // mezcla de Circle y Square
    shapes.max { $0.area < $1.area }
}

func totalArea(_ shapes: [some Shape]) -> Double {          // array homogéneo: [Circle] o [Square], no ambos
    shapes.reduce(0) { $0 + $1.area }
}
```

Regla de elección: parámetros y retornos con **un** tipo concreto desconocido → `some` (más rápido, y es lo que SwiftUI usa en `var body: some View`). Colecciones heterogéneas o un valor cuyo tipo cambia en tiempo de ejecución → `any`. Desde Swift 5.7, `any` es obligatorio escribirlo para existenciales de protocolos con requisitos `Self` o asociados, y desde Swift 6 se recomienda escribirlo siempre, para que el coste del despacho dinámico sea visible en el código.

**Extensiones de protocolo** para compartir comportamiento sin herencia, que es la respuesta a «necesito herencia, ¿entonces class?» la mayoría de las veces:

```swift
extension Shape {
    func describe() -> String { "\(Self.self) con área \(area)" }
}
print(Circle(r: 1).describe())   // Circle con área 3.14159...
```

Comprobación rápida de la semántica: cambia `struct Point` por `final class Point`, quita el `mutating`, y el `print(a.x, b.x)` pasa de `0.0 5.0` a `5.0 5.0`. Esa línea es la diferencia completa.""",
            },
        ]
    },
    # 9) Swift: async/await + Codable con fechas (código del usuario)
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Llamo a una API con async/await y me falla la decodificación con `DecodingError.typeMismatch(Swift.Double, ... Expected to decode Double but found a string`. El JSON es:

```json
{"id": 7, "created_at": "2024-05-01T10:30:00Z", "total_amount": "99.50", "items": [{"sku": "A1", "qty": 2}]}
```

Mi modelo:

```swift
struct Order: Codable {
    let id: Int
    let createdAt: Date
    let totalAmount: Double
    let items: [Item]
}
struct Item: Codable { let sku: String; let qty: Int }

func fetchOrder(id: Int) async throws -> Order {
    let (data, _) = try await URLSession.shared.data(from: URL(string: "https://api.example.com/orders/\(id)")!)
    return try JSONDecoder().decode(Order.self, from: data)
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""Hay tres desajustes entre el JSON y el modelo; el error que ves es el tercero, pero los dos primeros saltarían justo después de arreglarlo.

1. **Nombres**: el JSON usa `created_at` y tu propiedad es `createdAt`. Sin configuración, `JSONDecoder` busca la clave `createdAt`, no la encuentra y lanza `keyNotFound`. Arreglo: `decoder.keyDecodingStrategy = .convertFromSnakeCase`.
2. **Fechas**: `Date` por defecto se decodifica como un `Double` (segundos desde 2001). Tu `created_at` es una cadena ISO 8601. Arreglo: `decoder.dateDecodingStrategy = .iso8601`.
3. **`total_amount` es una cadena `"99.50"`**, no un número. Es el `typeMismatch` del mensaje. La API envía el importe como texto (habitual para no perder precisión decimal). Dos opciones: decodificarlo a mano, o, mejor, usar `Decimal` para dinero y convertir desde la cadena.

Modelo corregido con un `init(from:)` solo para el campo problemático:

```swift
import Foundation

struct Order: Codable {
    let id: Int
    let createdAt: Date
    let totalAmount: Decimal
    let items: [Item]

    private enum CodingKeys: String, CodingKey {
        case id, createdAt, totalAmount, items
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(Int.self, forKey: .id)
        createdAt = try c.decode(Date.self, forKey: .createdAt)
        items = try c.decode([Item].self, forKey: .items)

        let raw = try c.decode(String.self, forKey: .totalAmount)
        guard let amount = Decimal(string: raw, locale: Locale(identifier: "en_US_POSIX")) else {
            throw DecodingError.dataCorruptedError(forKey: .totalAmount, in: c,
                                                   debugDescription: "'\(raw)' is not a decimal number")
        }
        totalAmount = amount
    }

    func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(id, forKey: .id)
        try c.encode(createdAt, forKey: .createdAt)
        try c.encode(items, forKey: .items)
        try c.encode("\(totalAmount)", forKey: .totalAmount)   // simétrico: vuelve a salir como cadena
    }
}

struct Item: Codable {
    let sku: String
    let qty: Int
}
```

Y el decodificador configurado **una vez**, no en cada llamada:

```swift
enum API {
    static let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.keyDecodingStrategy = .convertFromSnakeCase
        d.dateDecodingStrategy = .iso8601
        return d
    }()
}

func fetchOrder(id: Int) async throws -> Order {
    guard let url = URL(string: "https://api.example.com/orders/\(id)") else {
        throw URLError(.badURL)
    }
    let (data, response) = try await URLSession.shared.data(from: url)
    guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
        throw URLError(.badServerResponse)
    }
    return try API.decoder.decode(Order.self, from: data)
}
```

Notas:

- Con `.convertFromSnakeCase`, las `CodingKeys` siguen siendo los nombres en camelCase; la conversión ocurre antes de buscar la clave.
- **`.iso8601` no acepta fracciones de segundo** (`2024-05-01T10:30:00.123Z`). Si la API las envía, usa `.custom` con un `ISO8601DateFormatter` cuyas `formatOptions` incluyan `.withFractionalSeconds`, o en iOS 15+/macOS 12+ `Date.ISO8601FormatStyle(includingFractionalSeconds: true)`.
- `Decimal` en vez de `Double` para importes: `99.50` como `Double` es `99.5000000000000071` en binario; con `Decimal` las sumas de céntimos cuadran.
- La respuesta HTTP se comprueba: `URLSession` **no lanza** por un 404 o un 500; te entrega el cuerpo de error y la decodificación falla con un mensaje engañoso.
- La función ya es `async throws`; desde una vista o un `Task`, `let order = try await fetchOrder(id: 7)`. Con Swift 6 y comprobación estricta de concurrencia, `Order` e `Item` conforman `Sendable` automáticamente al ser structs de valores `Sendable`, así que cruzan sin avisos entre actores.

Prueba de decodificación con el JSON exacto que has pegado, sin red:

```swift
let json = #"{"id": 7, "created_at": "2024-05-01T10:30:00Z", "total_amount": "99.50", "items": [{"sku": "A1", "qty": 2}]}"#
let order = try API.decoder.decode(Order.self, from: Data(json.utf8))
assert(order.totalAmount == Decimal(string: "99.50"))
assert(order.items.first?.qty == 2)
```

Si esa línea pasa, el único fallo que puede quedar en producción es de red o de estado HTTP, y ambos ya lanzan con un error reconocible.""",
            },
        ]
    },
    # 10) Dart: null safety y promoción de campos
    {
        "messages": [
            {"role": "user", "content": "En Dart 3, ¿por qué esto no compila si acabo de comprobar que no es null?\n\n```dart\nclass Cart {\n  Coupon? coupon;\n  double discount() {\n    if (coupon != null) {\n      return coupon.percent / 100;  // error: 'coupon' can't be unconditionally accessed\n    }\n    return 0;\n  }\n}\n```"},
            {
                "role": "assistant",
                "content": r"""Porque la **promoción de tipo** (que `coupon != null` convierta `Coupon?` en `Coupon` dentro del `if`) solo funciona con **variables locales**, parámetros y, desde Dart 3.2, **campos privados y `final`**. Tu `coupon` es un campo público y mutable: entre la comprobación y el uso, otro código (un *getter* sobrescrito en una subclase, otro hilo de eventos, una llamada que mute `this`) podría ponerlo a `null`, y el compilador no puede garantizar nada.

Tres arreglos, según lo que quieras expresar:

**1. Copiar a una variable local** (la solución universal):

```dart
double discount() {
  final coupon = this.coupon;      // captura el valor actual
  if (coupon != null) {
    return coupon.percent / 100;   // promovido: aquí es Coupon
  }
  return 0;
}
```

**2. Hacer el campo privado y final** (Dart 3.2+), si no necesita cambiar tras construir el objeto:

```dart
class Cart {
  final Coupon? _coupon;
  Cart({Coupon? coupon}) : _coupon = coupon;

  double discount() => _coupon != null ? _coupon.percent / 100 : 0;   // promueve
}
```

La promoción de campos privados exige que ningún otro miembro de la biblioteca (el archivo) declare un *getter* con el mismo nombre; de ahí la restricción a privados.

**3. Operadores de nulabilidad** cuando la lógica cabe en una expresión:

```dart
double discount() => (coupon?.percent ?? 0) / 100;
```

`?.` devuelve `null` si `coupon` es `null`; `??` da el valor por defecto. Para un campo que debe tener valor antes de usarse pero no en el constructor, `late Coupon coupon;` aplaza la comprobación al tiempo de ejecución (lanza `LateInitializationError` si se lee antes de asignar); úsalo solo cuando el ciclo de vida lo garantice.

El resto del sistema de nulabilidad de Dart 3, para tener el mapa:

```dart
String? maybe;            // puede ser null
String sure = maybe!;     // ! afirma que no es null; lanza si lo es. Evítalo salvo que sea un bug que lo sea.
String safe = maybe ?? 'por defecto';
maybe ??= 'solo si era null';         // asignación condicional
int? len = maybe?.length;             // encadenamiento
void greet({required String name}) {} // parámetro con nombre obligatorio; sin required sería String? implícito
```

`required` en parámetros con nombre es lo que evita el `String?` accidental: un parámetro con nombre sin valor por defecto y sin `required` tiene que ser anulable.

Comprobación: con la versión 1, cambia `return 0;` por `return coupon.percent;` fuera del `if` y verás el mismo error del compilador, porque fuera del `if` la variable local sigue siendo `Coupon?`. Dentro, `coupon.percent` compila sin `!`.""",
            },
        ]
    },
    # 11) Dart 3: clases sealed, switch como expresión, patrones y records (system exacto)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "Vengo de Kotlin. En Dart 3 quiero modelar el resultado de un pago: aprobado (id de transacción e importe), rechazado (motivo) o pendiente de verificación 3DS (una URL). Ahora tengo una clase con un campo `type` de tipo String y un montón de `if (r.type == 'approved')` con casts. ¿Cómo se hace bien?"},
            {
                "role": "assistant",
                "content": r"""Con una **clase `sealed`** y un **`switch` como expresión con patrones** (Dart 3.0+). Es el equivalente directo de `sealed class` + `when` en Kotlin: el compilador conoce todos los subtipos, te obliga a tratarlos, y dentro de cada rama ya tienes el tipo concreto, sin casts.

```dart
sealed class PaymentResult {
  const PaymentResult();
}

final class Approved extends PaymentResult {
  const Approved({required this.transactionId, required this.amountCents});
  final String transactionId;
  final int amountCents;
}

final class Declined extends PaymentResult {
  const Declined(this.reason);
  final String reason;
}

final class NeedsVerification extends PaymentResult {
  const NeedsVerification(this.redirectUrl);
  final Uri redirectUrl;
}

String describe(PaymentResult result) => switch (result) {
      Approved(:final transactionId, :final amountCents) =>
        'Cobro $transactionId por ${(amountCents / 100).toStringAsFixed(2)} €',
      Declined(reason: 'insufficient_funds') => 'Fondos insuficientes',
      Declined(:final reason) => 'Pago rechazado: $reason',
      NeedsVerification(:final redirectUrl) => 'Completa la verificación en $redirectUrl',
    };
```

Qué hace cada pieza:

- **`sealed`**: la clase es abstracta implícitamente y sus subtipos directos solo pueden declararse en la misma biblioteca (el mismo archivo). Por eso el compilador sabe que la lista está cerrada. Si mañana añades `Refunded`, cada `switch` que no la trate deja de compilar con `non_exhaustive_switch_expression`. Con tu campo `type` de tipo String, un `'aproved'` mal escrito compila y falla en producción.
- **`final class`** en los subtipos: nadie fuera de la biblioteca puede extenderlos ni implementarlos, así que la jerarquía queda cerrada también por debajo.
- **Patrones de objeto**: `Approved(:final transactionId)` comprueba el tipo y extrae el *getter* a una variable del mismo nombre (abreviatura de `transactionId: final transactionId`). `Declined(reason: 'insufficient_funds')` compara el campo con una constante.
- **El orden importa**: gana el primer caso que encaja. El `Declined` específico va antes que el general; si los inviertes, el específico nunca se ejecuta.

El mismo mecanismo sirve para construir el resultado desde el JSON de la pasarela, con **patrones de mapa** que comprueban a la vez que la clave existe y el tipo del valor:

```dart
PaymentResult parsePaymentResult(Map<String, Object?> json) => switch (json) {
      {'status': 'approved', 'transaction_id': String id, 'amount_cents': int cents} =>
        Approved(transactionId: id, amountCents: cents),
      {'status': 'declined', 'reason': String reason} => Declined(reason),
      {'status': 'requires_action', 'redirect_url': String url} =>
        NeedsVerification(Uri.parse(url)),
      _ => throw FormatException('Unknown payment payload: $json'),
    };
```

Los patrones de mapa ignoran las claves que no mencionas, y como un `Map` no es un tipo cerrado, aquí el `_` final es obligatorio.

Para devolver varios valores sin crear una clase, Dart 3 tiene **records**, que se desestructuran con la misma sintaxis:

```dart
(int approved, int declined) countOutcomes(Iterable<PaymentResult> results) {
  var approved = 0, declined = 0;
  for (final result in results) {
    switch (result) {
      case Approved():
        approved++;
      case Declined():
        declined++;
      case NeedsVerification():
        break;
    }
  }
  return (approved, declined);
}

// uso
final (approved, declined) = countOutcomes(results);
```

En Dart 3 un `case` con cuerpo no necesita `break` (no hay caída al siguiente), y un `switch` como sentencia sobre un tipo `sealed` también tiene que ser exhaustivo.

Una diferencia con Kotlin que conviene saber: las clases de Dart **no** tienen igualdad por valor automática (no hay `data class`); los records sí. Si necesitas `==` y `copyWith` en las clases, escríbelos o usa `freezed`.

Comprobación con `package:test`:

```dart
import 'package:test/test.dart';

void main() {
  test('describe usa el mensaje específico para fondos insuficientes', () {
    expect(describe(const Declined('insufficient_funds')), 'Fondos insuficientes');
    expect(describe(const Declined('expired_card')), 'Pago rechazado: expired_card');
  });

  test('parsePaymentResult rechaza payloads desconocidos', () {
    expect(() => parsePaymentResult({'status': 'weird'}), throwsFormatException);
  });
}
```

Y la prueba de que la exhaustividad trabaja para ti: añade `final class Refunded extends PaymentResult { const Refunded(); }` y ejecuta `dart analyze`. Debe marcar error en `describe` y en `countOutcomes`; en `parsePaymentResult` no, porque su `_` ya cubre cualquier caso.""",
            },
        ]
    },
    # 12) Dart: futures en paralelo con records y trabajo de CPU en un isolate (multiturno)
    {
        "messages": [
            {"role": "user", "content": "En una app Flutter, al abrir el perfil cargo tres cosas y tarda la suma de las tres:\n\n```dart\nfinal profile = await api.fetchProfile(userId);\nfinal orders = await api.fetchOrders(userId);\nfinal notifications = await api.fetchNotifications(userId);\n```\n\n¿Cómo lo paralelizo? ¿Y qué pasa si falla una?"},
            {
                "role": "assistant",
                "content": r"""Lanza las tres peticiones **antes** de esperar ninguna y espera el conjunto. En Dart un `Future` empieza a ejecutarse cuando lo creas, no cuando haces `await`; tu código crea el segundo solo después de que termine el primero, y por eso los tiempos se suman.

Desde Dart 3, la forma idiomática es `.wait` sobre un **record** de futures, que conserva el tipo de cada posición:

```dart
import 'dart:async';
import 'dart:developer';

Future<ProfileScreenData> loadProfileScreen(Api api, String userId) async {
  final (profile, orders, notifications) = await (
    api.fetchProfile(userId),
    api.fetchOrders(userId),
    notificationsOrEmpty(api, userId),
  ).wait;
  return ProfileScreenData(profile, orders, notifications);
}
```

`profile` sale como `Profile` y `orders` como `List<Order>`. Con `Future.wait([...])` obtendrías una `List<Object>` y tendrías que volver a los casts.

**Si falla una.** `.wait` espera a que terminen las tres y, si alguna falló, lanza `ParallelWaitError`. Su campo `values` trae lo que sí llegó (con `null` en las posiciones que fallaron) y `errors` trae un `AsyncError?` por posición. Así puedes saber qué falló sin perder el resto.

Pero antes de capturar errores, decide qué es imprescindible. Perfil y pedidos lo son: sin ellos la pantalla no tiene sentido. Las notificaciones no: si fallan, la pantalla se muestra igual. Esa decisión se codifica **en el future opcional**, no en el `catch` general:

```dart
Future<List<AppNotification>> notificationsOrEmpty(Api api, String userId) async {
  try {
    return await api.fetchNotifications(userId).timeout(const Duration(seconds: 3));
  } on TimeoutException {
    return const [];
  } on ApiException catch (error, stackTrace) {
    log('notifications failed', error: error, stackTrace: stackTrace);
    return const [];
  }
}
```

(`ApiException` es la excepción de tu cliente HTTP; asumo que existe una.) Con esto, `loadProfileScreen` solo lanza si fallan perfil o pedidos, y en la UI basta un `try { ... } on ParallelWaitError catch (e) { ... }` para mostrar el estado de error.

Un detalle: `timeout` deja de **esperar**, pero no cancela la petición HTTP, que sigue en curso hasta que el servidor responda. Si necesitas cancelar de verdad, el cliente tiene que soportarlo (por ejemplo, el `CancelToken` de Dio).

Comprobación con un `Api` falso donde cada método tarda 300 ms (`Future.delayed`): la versión secuencial tarda unos 900 ms y la paralela unos 300.

```dart
test('carga en paralelo', () async {
  final stopwatch = Stopwatch()..start();
  await loadProfileScreen(FakeApi(delay: const Duration(milliseconds: 300)), 'u1');
  expect(stopwatch.elapsedMilliseconds, lessThan(600));
});
```""",
            },
            {"role": "user", "content": "Funciona. Pero ahora la lista de pedidos es un JSON de 8 MB y al parsearlo la UI se congela medio segundo, aunque todo es async. ¿Async no era para eso?"},
            {
                "role": "assistant",
                "content": r"""No: `async` te da **concurrencia** en un solo hilo, no **paralelismo**. Mientras esperas la red, el *event loop* atiende otras cosas (dibujar frames, gestos). Pero `jsonDecode` y el mapeo a objetos son trabajo de CPU **síncrono**: mientras se ejecutan, el *isolate* principal no hace nada más y Flutter no puede pintar. A 60 fps tienes unos 16 ms por frame; 500 ms de parseo son unos 30 frames perdidos.

La solución es mover ese trabajo a otro *isolate* (un hilo con su propia memoria). Desde Dart 2.19 existe `Isolate.run`:

```dart
import 'dart:convert';
import 'dart:isolate';

Future<List<Order>> parseOrders(String body) {
  return Isolate.run(() {
    final data = jsonDecode(body) as List<Object?>;
    return [
      for (final item in data) Order.fromJson(item as Map<String, Object?>),
    ];
  });
}
```

Y en el cliente: `final body = response.body; return parseOrders(body);`.

Cuatro cosas que deciden si funciona bien:

1. **Qué cruza la frontera.** Las variables que captura el *closure* se copian al nuevo isolate; aquí solo `body`, y copiar 8 MB de texto es mucho más barato que parsearlos. El resultado vuelve sin copia, porque `Isolate.run` lo entrega con `Isolate.exit`.
2. **No captures de más.** Si el *closure* menciona `this` (un `State`, un servicio con un socket abierto), Dart intenta enviar ese objeto y falla con un `ArgumentError` del tipo «Illegal argument in isolate message». Por eso `parseOrders` es una función de nivel superior que recibe solo la cadena.
3. **Crear un isolate cuesta unos milisegundos.** Compensa con cargas grandes; para un JSON de 5 KB es más caro que parsear en línea. No lo apliques por sistema: mide.
4. **Web.** Si la app también compila para web, usa `compute(parseOrders, body)` de Flutter: hace lo mismo en móvil y escritorio, y en web, donde no hay isolates, ejecuta la función en el hilo principal en lugar de fallar.

Comprobación: en DevTools, pestaña Performance, antes verás un frame del hilo de UI de ~500 ms con `jsonDecode` dentro; después, frames por debajo de 16 ms y el trabajo fuera del hilo de UI. Y la lógica sigue siendo testeable en la VM, donde los isolates existen:

```dart
test('parseOrders convierte la lista', () async {
  const body = '[{"id": 1, "total": 10.5}, {"id": 2, "total": 3.0}]';
  expect(await parseOrders(body), hasLength(2));
});
```""",
            },
        ]
    },
    # 13) Haskell: Either, do en Either, traverse y partitionEithers
    {
        "messages": [
            {"role": "user", "content": "Estoy aprendiendo Haskell. Tengo que leer un archivo con líneas `nombre,edad` y quiero que si una línea está mal me diga cuál y por qué. En Python haría un for con try/except y un contador de línea. ¿Cómo sería lo idiomático?"},
            {
                "role": "assistant",
                "content": r"""En Haskell el `try/except` se sustituye por **valores**: cada línea se convierte en un `Either RowError Person`, y `traverse` recorre la lista y se detiene en el primer `Left`. El número de línea lo aportas tú con `zip [1 ..]`; no hay contador mutable.

```haskell
module Main (main) where

import Data.Char (isSpace)
import Data.Either (partitionEithers)
import Data.List (dropWhileEnd)
import Text.Read (readMaybe)

data Person = Person { name :: String, age :: Int }
  deriving (Show, Eq)

data RowError
  = WrongFieldCount Int Int   -- número de línea, campos encontrados
  | EmptyName Int
  | BadAge Int String         -- número de línea, texto recibido
  deriving (Show, Eq)

splitOn :: Char -> String -> [String]
splitOn sep s = case break (== sep) s of
  (chunk, [])       -> [chunk]
  (chunk, _ : rest) -> chunk : splitOn sep rest

trim :: String -> String
trim = dropWhileEnd isSpace . dropWhile isSpace

parseRow :: Int -> String -> Either RowError Person
parseRow lineNo line =
  case map trim (splitOn ',' line) of
    [rawName, rawAge] -> do
      validName <- if null rawName then Left (EmptyName lineNo) else Right rawName
      validAge <- case readMaybe rawAge of
        Just n | n >= 0 && n < 150 -> Right n
        _                          -> Left (BadAge lineNo rawAge)
      pure (Person validName validAge)
    fields -> Left (WrongFieldCount lineNo (length fields))

-- Se detiene en el primer error
parseAll :: String -> Either RowError [Person]
parseAll = traverse (uncurry parseRow) . zip [1 ..] . lines

-- Recoge todos los errores y todas las filas válidas
parseReport :: String -> ([RowError], [Person])
parseReport = partitionEithers . zipWith parseRow [1 ..] . lines

main :: IO ()
main = do
  input <- readFile "people.csv"
  case parseAll input of
    Left err     -> putStrLn ("error: " ++ show err)
    Right people -> mapM_ print people
```

Cómo se lee, pieza a pieza:

1. **`do` dentro de `Either`.** Cada `<-` saca el valor de un `Right`; si aparece un `Left`, el resto del bloque no se ejecuta y ese `Left` es el resultado. Es tu `try/except`, pero visible en el tipo: quien llama a `parseRow` no recibe una `Person`, recibe un `Either`, y el compilador no le deja usarla sin decidir qué hace con el error.
2. **`traverse`.** Su tipo, especializado aquí, es `(a -> Either e b) -> [a] -> Either e [b]`: aplica la función a cada elemento y, si todas dan `Right`, devuelve la lista completa; si alguna da `Left`, devuelve el primero. Es el «for + append + raise» de Python en una sola función, y funciona igual con `Maybe`, `IO` o cualquier `Applicative`.
3. **Errores como tipo de datos, no como cadenas.** Quien consume `BadAge 2 "x"` puede hacer *pattern matching* (resaltar la celda de la línea 2) y los tests comparan con `==`. El texto para humanos se genera al final, en un solo sitio.
4. **`readMaybe` y no `read`.** `read` es una función parcial: con `"x"` lanza una excepción (`Prelude.read: no parse`) que se escapa del tipo. `readMaybe` devuelve `Nothing` y te obliga a tratarlo.
5. **`partitionEithers`** cuando quieres el informe completo (todas las líneas malas, como haría un validador de formularios) en lugar de parar en la primera.

Comprobación en GHCi (`ghci Main.hs`):

```
ghci> parseAll "ana,30\nluis,x\neva,20"
Left (BadAge 2 "x")
ghci> parseReport "ana,30\n,40\neva,20,extra"
([EmptyName 2,WrongFieldCount 3 3],[Person {name = "ana", age = 30}])
```

La primera para en la línea 2; la segunda sigue y te da las dos líneas malas con su motivo y la única buena.

Para un CSV real, con comillas y comas dentro de los campos, usa la librería `cassava` y `Data.Text` en lugar de `String`; la estructura de `Either` + `traverse` no cambia.""",
            },
        ]
    },
    # 14) Haskell: fuga de memoria por pereza (foldl, Data.Map perezoso, String) (código del usuario)
    {
        "messages": [
            {"role": "system", "content": "Eres un revisor de código estricto. Ve al grano: causa, arreglo mínimo y cómo comprobarlo."},
            {
                "role": "user",
                "content": r"""Este programa cuenta palabras de un archivo de 300 MB y se come 9 GB de RAM antes de que lo mate el sistema:

```haskell
import qualified Data.Map as Map

main :: IO ()
main = do
  contents <- readFile "corpus.txt"
  let counts = foldl (\m w -> Map.insertWith (+) w 1 m) Map.empty (words contents)
  print (Map.size counts)
  print (sum (Map.elems counts))
```

Compilo con `ghc -O2`. ¿Dónde está la fuga?""",
            },
            {
                "role": "assistant",
                "content": r"""No es una fuga en el sentido de C: es **pereza acumulada**. Hay tres causas y se suman; ordenadas por impacto:

1. **`foldl` es perezoso en el acumulador.** No inserta nada mientras recorre la lista: construye una cadena de *thunks* `insertWith ... (insertWith ... (insertWith ... Map.empty))` con un eslabón por palabra, y solo la evalúa cuando `print` pide el tamaño. Cada eslabón retiene su palabra, así que todo el texto queda vivo en memoria a la vez. `-O2` a veces rescata un `foldl` con acumulador simple gracias al análisis de estrictez, pero con un `Map` no puedes contar con ello.
2. **`Data.Map` es perezoso en los valores.** Incluso insertando de verdad, `insertWith (+) w 1` guarda el *thunk* `1 + viejo` sin sumarlo. Para «de» o «la», que aparecen millones de veces, el valor es una cadena de millones de sumas pendientes.
3. **`String` es una lista enlazada de `Char`.** Cada carácter es una celda de lista de unos 24 bytes en 64 bits. 300 MB de texto retenidos como `String` son del orden de 7 GB: casi toda tu cifra de 9 GB viene de aquí, multiplicada por la causa 1, que impide liberar nada.

Arreglo mínimo, un cambio por causa:

```haskell
module Main (main) where

import Data.List (foldl')
import qualified Data.Map.Strict as Map
import qualified Data.Text as T
import qualified Data.Text.IO as TIO

main :: IO ()
main = do
  contents <- TIO.readFile "corpus.txt"
  let counts = foldl' (\m w -> Map.insertWith (+) w (1 :: Int) m) Map.empty (T.words contents)
  print (Map.size counts)
  print (sum (Map.elems counts))
```

- **`foldl'`** evalúa el acumulador en cada paso (a forma normal débil). Como `Map` es estricto en su estructura, eso basta para que cada inserción se complete antes de pasar a la siguiente palabra. Desde GHC 9.10, `foldl'` también se exporta desde el `Prelude`.
- **`Data.Map.Strict`** evalúa el valor al insertar: el contador es un `Int` real, no una suma pendiente. Hacen falta las dos cosas: con `foldl'` y el `Map` perezoso, la estructura se construye pero los valores siguen siendo *thunks*.
- **`Data.Text`** guarda el texto en un búfer compacto (UTF-8 desde `text` 2.0): el archivo ocupa en memoria aproximadamente lo que ocupa en disco. Las claves del mapa son trozos de ese búfer, que de todos modos está vivo durante todo el programa.
- `(1 :: Int)` fija el tipo: sin anotación, el literal se resolvería a `Integer`, que funciona pero es más lento.

Comprobación: compila con `ghc -O2 -rtsopts Main.hs` y ejecuta las dos versiones con `./Main +RTS -s`. Mira la línea `maximum residency`: en la original crece con el tamaño del archivo hasta que el sistema la mata; en la corregida queda en torno al tamaño del archivo más el mapa de palabras distintas. Si quieres ver qué ocupaba el *heap*, `./Main +RTS -hT -i0.5` genera `Main.hp` (perfil por tipo de cierre, sin compilar con *profiling*); en la original lo dominan celdas de lista y *thunks*.

Si algún día el archivo no cabe en memoria, lee en *streaming* (por líneas con `withFile` y `TIO.hGetLine`, o con `streaming`/`conduit`) y guarda como clave `T.copy w`, para que cada palabra no retenga el bloque entero del que salió.""",
            },
        ]
    },
    # 15) Haskell: newtypes y constructores inteligentes (usuario en inglés)
    {
        "messages": [
            {"role": "user", "content": "In Haskell, how do I stop mixing up user IDs and order IDs? Both are `Int` and last week I passed them in the wrong order to a function. I'd also like emails to be validated once instead of everywhere."},
            {
                "role": "assistant",
                "content": r"""Wrap each concept in a `newtype`, and for values that need validation, hide the constructor and export a **smart constructor** instead. Both are free at runtime: a `newtype` is erased after type checking.

```haskell
{-# LANGUAGE OverloadedStrings #-}
module Domain
  ( UserId (..)
  , OrderId (..)
  , Email        -- the type only: the Email constructor stays private
  , mkEmail
  , emailText
  ) where

import Data.Text (Text)
import qualified Data.Text as T

newtype UserId = UserId Int
  deriving (Show, Eq, Ord)

newtype OrderId = OrderId Int
  deriving (Show, Eq, Ord)

newtype Email = Email Text
  deriving (Show, Eq, Ord)

mkEmail :: Text -> Either Text Email
mkEmail raw
  | T.count "@" trimmed /= 1       = invalid
  | T.null local || T.null domain  = invalid
  | not ("." `T.isInfixOf` domain) = invalid
  | otherwise                      = Right (Email (T.toLower trimmed))
  where
    trimmed = T.strip raw
    (local, rest) = T.breakOn "@" trimmed
    domain = T.drop 1 rest
    invalid = Left ("invalid email: " <> raw)

emailText :: Email -> Text
emailText (Email t) = t
```

What each decision buys you:

- **`newtype`, not `type`.** `type UserId = Int` is only an alias: the compiler still treats it as `Int` and happily accepts an `OrderId` in its place. A `newtype` is a distinct type, so swapping arguments becomes a compile error:

```
ghci> :{
ghci| describe :: UserId -> OrderId -> String
ghci| describe (UserId u) (OrderId o) = "user " <> show u <> ", order " <> show o
ghci| :}
ghci> describe (OrderId 7) (UserId 3)
<interactive>: error:
    • Couldn't match expected type ‘UserId’ with actual type ‘OrderId’
```

- **No `Num` instance on IDs.** Adding two user IDs is meaningless, so don't derive it. `Eq` and `Ord` are enough to use them as `Map` keys.
- **Export `Email`, not `Email (..)`.** Outside the module, the only way to obtain an `Email` is `mkEmail`. Every function that takes an `Email` can rely on it being valid, so validation happens once, at the boundary (the HTTP handler, the CSV importer), and nowhere else. This is the "parse, don't validate" idea: the type records that the check already happened.
- **Don't derive `Read` for `Email`.** It would be a second, unvalidated way to build one. The same goes for `FromJSON` via generic deriving: write it by hand on top of `mkEmail`.
- **Zero-cost conversions.** When you need the raw values in bulk, `coerce` from `Data.Coerce` turns `[UserId]` into `[Int]` without traversing the list.

The validation rules are deliberately simple; the point is *where* they live, not how clever they are.

Checks in GHCi:

```
ghci> mkEmail "  Ana@Example.com "
Right (Email "ana@example.com")
ghci> mkEmail "ana@@example.com"
Left "invalid email: ana@@example.com"
ghci> mkEmail "ana@localhost"
Left "invalid email: ana@localhost"
```

And a QuickCheck property that pins the invariant down (`Arbitrary Text` comes from the `quickcheck-instances` package):

```haskell
prop_validEmailsHaveOneAt :: Text -> Bool
prop_validEmailsHaveOneAt t = case mkEmail t of
  Left _  -> True
  Right e -> T.count "@" (emailText e) == 1
```""",
            },
        ]
    },
    # 16) Elixir: with, tuplas etiquetadas y pattern matching en cabeceras (system exacto)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "Tengo una función en Elixir (Phoenix) que crea una transferencia entre cuentas y es un `case` dentro de otro `case` con cuatro niveles: valida el importe, busca las dos cuentas, comprueba que no sean la misma y que haya saldo. ¿Cómo se aplana esto de forma idiomática?"},
            {
                "role": "assistant",
                "content": r"""Con `with`, funciones pequeñas que devuelven tuplas etiquetadas (`{:ok, valor}` / `{:error, motivo}`) y *pattern matching* en las cabeceras de esas funciones. Cada nivel de `case` se convierte en una línea.

```elixir
defmodule Bank.Transfers do
  alias Bank.{Accounts, Ledger}

  @spec create(map()) :: {:ok, Ledger.Transfer.t()} | {:error, atom()}
  def create(params) do
    with {:ok, amount} <- parse_amount(params["amount"]),
         {:ok, from} <- Accounts.fetch(params["from_id"]),
         {:ok, to} <- Accounts.fetch(params["to_id"]),
         :ok <- ensure_distinct(from, to),
         :ok <- ensure_funds(from, amount) do
      Ledger.transfer(from, to, amount)
    end
  end

  defp parse_amount(value) when is_integer(value) and value > 0, do: {:ok, value}

  defp parse_amount(value) when is_binary(value) do
    case Integer.parse(value) do
      {amount, ""} when amount > 0 -> {:ok, amount}
      _ -> {:error, :invalid_amount}
    end
  end

  defp parse_amount(_), do: {:error, :invalid_amount}

  defp ensure_distinct(%{id: id}, %{id: id}), do: {:error, :same_account}
  defp ensure_distinct(_from, _to), do: :ok

  defp ensure_funds(%{balance: balance}, amount) when balance >= amount, do: :ok
  defp ensure_funds(_account, _amount), do: {:error, :insufficient_funds}
end
```

Y en `Accounts`, la convención que hace funcionar el `with`:

```elixir
def fetch(id) do
  case Repo.get(Account, id) do
    nil -> {:error, :not_found}
    account -> {:ok, account}
  end
end
```

Por qué así:

1. **`with` sin `else`.** Cada cláusula `patrón <- expresión` tiene que encajar para seguir. Si una no encaja, `with` devuelve **ese valor tal cual**: `{:error, :not_found}`, `{:error, :insufficient_funds}`. Como cada función ya devuelve un error con significado, no hace falta `else`. Un `else` con muchas cláusulas que intentan adivinar qué paso falló es un antipatrón documentado en Elixir («complex else clauses in with»): si lo necesitas, es que alguna función devuelve errores ambiguos.
2. **Varias cabeceras en lugar de `if`.** `parse_amount` tiene una cláusula por forma de entrada (entero, cadena, cualquier otra cosa), con guardas. `Integer.parse("100abc")` devuelve `{100, "abc"}`, y el patrón `{amount, ""}` exige que no sobre nada.
3. **La misma variable dos veces en un patrón** (`%{id: id}, %{id: id}`) significa «los dos `id` son iguales». Es la forma idiomática de comparar en la cabecera.
4. **El orden de las cláusulas del `with` es el orden de coste**: primero lo que no toca la base de datos (el importe), después las lecturas.

Una advertencia de corrección: `ensure_funds` es una comprobación rápida para devolver un error claro, no una garantía. Dos transferencias simultáneas pueden pasarla con el mismo saldo. La garantía vive en `Ledger.transfer`, dentro de una transacción de Ecto que relee las cuentas con `lock: "FOR UPDATE"` y vuelve a comprobar el saldo.

En el controlador, Phoenix tiene el complemento natural: `action_fallback`. El controlador solo trata el caso feliz y los errores van a un único módulo:

```elixir
defmodule BankWeb.TransferController do
  use BankWeb, :controller

  action_fallback BankWeb.FallbackController

  def create(conn, params) do
    with {:ok, transfer} <- Bank.Transfers.create(params) do
      conn
      |> put_status(:created)
      |> json(%{id: transfer.id})
    end
  end
end

defmodule BankWeb.FallbackController do
  use BankWeb, :controller

  def call(conn, {:error, :not_found}) do
    conn |> put_status(:not_found) |> json(%{error: "account_not_found"})
  end

  def call(conn, {:error, reason}) when is_atom(reason) do
    conn |> put_status(:unprocessable_entity) |> json(%{error: Atom.to_string(reason)})
  end
end
```

Comprobación: estos tests no necesitan base de datos, precisamente porque el `with` corta en la primera cláusula que falla.

```elixir
defmodule Bank.TransfersTest do
  use ExUnit.Case, async: true

  alias Bank.Transfers

  test "rechaza un importe no numérico sin tocar la base de datos" do
    assert {:error, :invalid_amount} =
             Transfers.create(%{"amount" => "diez", "from_id" => 1, "to_id" => 2})
  end

  test "rechaza cero y negativos" do
    assert {:error, :invalid_amount} = Transfers.create(%{"amount" => "0"})
    assert {:error, :invalid_amount} = Transfers.create(%{"amount" => -5})
  end
end
```""",
            },
        ]
    },
    # 17) Elixir: GenServer, supervisión y "let it crash" (multiturno)
    {
        "messages": [
            {"role": "user", "content": "Necesito en Elixir un contador de peticiones por cliente en memoria para un límite de tasa sencillo, con ventana de un minuto. ¿Lo hago con un GenServer? ¿Cómo lo estructuro?"},
            {
                "role": "assistant",
                "content": r"""Sí, un GenServer es la herramienta para «estado en memoria con acceso serializado». Estructura estándar: una **API de cliente** (funciones públicas que se ejecutan en el proceso que llama) y unos **callbacks** (que se ejecutan dentro del GenServer), en el mismo módulo.

```elixir
defmodule MyApp.RateCounter do
  use GenServer

  @window_ms 60_000

  # --- API de cliente: se ejecuta en el proceso que llama ---

  def start_link(opts) do
    limit = Keyword.fetch!(opts, :limit)
    GenServer.start_link(__MODULE__, limit, name: Keyword.get(opts, :name, __MODULE__))
  end

  @spec hit(term(), GenServer.server()) :: :ok | {:error, :rate_limited}
  def hit(client_id, server \\ __MODULE__) do
    GenServer.call(server, {:hit, client_id})
  end

  # --- Callbacks: se ejecutan dentro del proceso del GenServer ---

  @impl true
  def init(limit) do
    schedule_reset()
    {:ok, %{limit: limit, counts: %{}}}
  end

  @impl true
  def handle_call({:hit, client_id}, _from, %{limit: limit, counts: counts} = state) do
    count = Map.get(counts, client_id, 0)

    if count < limit do
      {:reply, :ok, %{state | counts: Map.put(counts, client_id, count + 1)}}
    else
      {:reply, {:error, :rate_limited}, state}
    end
  end

  @impl true
  def handle_info(:reset, state) do
    schedule_reset()
    {:noreply, %{state | counts: %{}}}
  end

  defp schedule_reset, do: Process.send_after(self(), :reset, @window_ms)
end
```

Y se arranca bajo el supervisor de la aplicación, en `application.ex`:

```elixir
children = [
  {MyApp.RateCounter, limit: 100}
]

Supervisor.start_link(children, strategy: :one_for_one, name: MyApp.Supervisor)
```

`use GenServer` genera `child_spec/1`, que llama a `start_link(limit: 100)`; por eso basta la tupla.

Decisiones y por qué:

- **`call` y no `cast`** en `hit`: el llamador necesita la respuesta (dejar pasar o no). `cast` es para «haz esto y no me contestes».
- **No hay condiciones de carrera**: el GenServer procesa un mensaje cada vez, así que leer y actualizar el contador es atómico sin *locks*.
- **El reinicio de la ventana es un mensaje** que el proceso se envía a sí mismo con `Process.send_after`, y se trata en `handle_info`. Es una ventana fija (todos los contadores a cero cada minuto); para un límite sencillo basta.
- **El nombre es configurable** (`:name`) para poder arrancar instancias aisladas en los tests.

El límite de este diseño es que **todo pasa por un solo proceso**: cada `hit` es un mensaje a un único buzón. Para unos miles de peticiones por segundo va sobrado; si se convierte en cuello de botella, el paso siguiente es una tabla ETS con `:ets.update_counter(table, key, {2, 1}, {key, 0})`, que incrementa de forma atómica desde cualquier proceso sin pasar por un buzón.

Comprobación:

```elixir
test "limita tras N peticiones por cliente" do
  pid = start_supervised!({MyApp.RateCounter, limit: 2, name: :test_counter})

  assert :ok = MyApp.RateCounter.hit("a", pid)
  assert :ok = MyApp.RateCounter.hit("a", pid)
  assert {:error, :rate_limited} = MyApp.RateCounter.hit("a", pid)
  assert :ok = MyApp.RateCounter.hit("b", pid)
end
```""",
            },
            {"role": "user", "content": "¿Y si el GenServer se cae por un bug? ¿Pierdo los contadores? Lo de «let it crash» me da un poco de miedo."},
            {
                "role": "assistant",
                "content": r"""Sí, los pierdes: el supervisor arranca un proceso **nuevo**, que pasa por `init/1` y empieza con `counts: %{}`. Y para este caso es exactamente lo que quieres.

**Qué significa «let it crash» de verdad.** No significa ignorar errores. Significa no escribir código defensivo para los errores **que no esperas**: en lugar de intentar arreglar un estado que un bug ha dejado inconsistente, dejas que el proceso muera y el supervisor lo devuelve a un estado conocido y correcto. Los errores que sí esperas (cliente desconocido, entrada inválida) se tratan con tuplas `{:error, ...}` como siempre.

La pregunta de diseño es entonces: **¿qué estado puede perderse?** Para un límite de tasa, perder los contadores significa que todos los clientes estrenan ventana un minuto antes de tiempo. Es un fallo «abierto» y aceptable. Si el estado no pudiera perderse (saldos, pedidos), no viviría solo en un GenServer: estaría en la base de datos, o en una tabla ETS propiedad de otro proceso más simple que sobreviva al que falla.

Tres detalles operativos que sí debes cuidar:

1. **Durante el reinicio, las llamadas fallan.** `GenServer.call` a un proceso que no existe o que muere mientras atiende hace que **el llamador** salga con un *exit*. Y si el GenServer tarda más de 5 s (el *timeout* por defecto de `call`), también. En un *plug* de límite de tasa, eso tumbaría la petición del usuario por un problema del contador. Captura el *exit* y deja pasar:

```elixir
defmodule MyAppWeb.RateLimit do
  @spec allowed?(term()) :: boolean()
  def allowed?(client_id) do
    MyApp.RateCounter.hit(client_id) == :ok
  catch
    :exit, _reason -> true
  end
end
```

   Este `catch` no contradice «let it crash»: es la frontera donde decides conscientemente que un contador caído no debe tirar la API.

2. **Intensidad de reinicios.** Por defecto un supervisor admite 3 reinicios en 5 segundos (`max_restarts: 3`, `max_seconds: 5`). Si un bug hace que el contador muera en bucle, el supervisor se rinde, muere él también y el fallo escala hacia arriba. Es deliberado: un reinicio que no arregla nada no debe repetirse para siempre. Pon los procesos frágiles bajo su propio supervisor para que su caída no arrastre a hermanos que no tienen nada que ver.

3. **Que el fallo se vea.** Cada caída deja un informe en el *logger* con el motivo y el último mensaje; añade una métrica o alerta sobre reinicios. «Let it crash» sin observabilidad es «let it crash en silencio».

Comprobación del comportamiento de reinicio:

```elixir
test "el supervisor reinicia el contador con el estado limpio" do
  pid = Process.whereis(MyApp.RateCounter)
  ref = Process.monitor(pid)

  Process.exit(pid, :kill)
  assert_receive {:DOWN, ^ref, :process, ^pid, :killed}

  # el supervisor registra un proceso nuevo con el mismo nombre
  Process.sleep(50)
  new_pid = Process.whereis(MyApp.RateCounter)
  assert is_pid(new_pid) and new_pid != pid
  assert :ok = MyApp.RateCounter.hit("a")
end
```""",
            },
        ]
    },
    # 18) Elixir: Stream, NimbleCSV y Task.async_stream con contrapresión
    {
        "messages": [
            {"role": "user", "content": "Tengo que importar un CSV de 4 GB en Elixir: por cada fila llamo a una API externa para enriquecerla y guardo el resultado en Postgres. Con `File.read!` + `String.split` el nodo se queda sin memoria. ¿Cómo lo planteo?"},
            {
                "role": "assistant",
                "content": r"""Tres cambios: leer en *streaming* con `File.stream!`, parsear con una librería de CSV que también trabaje en *streaming*, y paralelizar las llamadas con `Task.async_stream`, que limita la concurrencia y aplica contrapresión. La memoria pasa a depender de cuántas filas hay en vuelo, no del tamaño del archivo.

Dependencias en `mix.exs`:

```elixir
{:nimble_csv, "~> 1.2"},
{:req, "~> 0.5"}
```

```elixir
defmodule Importer do
  require Logger

  alias NimbleCSV.RFC4180, as: CSV

  @max_concurrency 20
  @batch_size 500

  @spec run(Path.t(), keyword()) :: %{ok: non_neg_integer(), error: non_neg_integer()}
  def run(path, opts \\ []) do
    enrich = Keyword.get(opts, :enrich, &enrich_remote/1)
    persist = Keyword.get(opts, :persist, &persist_records/1)

    path
    |> File.stream!()
    |> CSV.parse_stream()
    |> Stream.flat_map(&to_record/1)
    |> Task.async_stream(enrich,
      max_concurrency: @max_concurrency,
      timeout: 15_000,
      on_timeout: :kill_task,
      ordered: false
    )
    |> Stream.map(&classify/1)
    |> Stream.chunk_every(@batch_size)
    |> Enum.reduce(%{ok: 0, error: 0}, fn batch, acc -> handle_batch(batch, acc, persist) end)
  end

  defp to_record([id, email, country]), do: [%{id: id, email: email, country: country}]

  defp to_record(other) do
    Logger.warning("skipping malformed row: #{inspect(other)}")
    []
  end

  defp classify({:ok, {:ok, record}}), do: {:ok, record}
  defp classify({:ok, {:error, reason}}), do: {:error, reason}
  defp classify({:exit, reason}), do: {:error, {:exit, reason}}

  defp handle_batch(batch, acc, persist) do
    {oks, errors} = Enum.split_with(batch, &match?({:ok, _}, &1))
    records = Enum.map(oks, fn {:ok, record} -> record end)
    if records != [], do: persist.(records)
    Enum.each(errors, fn {:error, reason} -> Logger.warning("enrich failed: #{inspect(reason)}") end)
    %{acc | ok: acc.ok + length(records), error: acc.error + length(errors)}
  end

  defp enrich_remote(record) do
    case Req.get("https://geo.example.com/v1/lookup", params: [email: record.email], receive_timeout: 10_000) do
      {:ok, %Req.Response{status: 200, body: body}} -> {:ok, Map.put(record, :geo, body)}
      {:ok, %Req.Response{status: status}} -> {:error, {:http_status, status, record.id}}
      {:error, exception} -> {:error, {:transport, Exception.message(exception), record.id}}
    end
  end

  defp persist_records(records), do: MyApp.Repo.insert_all("enriched_customers", records)
end
```

Por qué cada pieza:

1. **`File.stream!`** devuelve un *stream* perezoso de líneas: nada se lee hasta que alguien al final de la tubería pide elementos. `File.read!` cargaba los 4 GB y `String.split` creaba otra copia troceada.
2. **`CSV.parse_stream`** (de NimbleCSV) parsea línea a línea respetando las comillas: una coma dentro de `"Pérez, Ana"` no parte el campo, que es justo lo que rompe `String.split(",")`. Por defecto descarta la cabecera.
3. **`Stream.flat_map(&to_record/1)`**: devolver `[registro]` o `[]` filtra y transforma en un paso, y una fila mal formada se registra y se salta en vez de tumbar la importación con un `FunctionClauseError`.
4. **`Task.async_stream`** mantiene como máximo 20 tareas en vuelo y solo pide más filas al *stream* de arriba cuando termina alguna: esa es la contrapresión que acota la memoria. `ordered: false` entrega los resultados según terminan, así una llamada lenta no frena a las demás. Con `on_timeout: :kill_task`, una llamada que se pasa de 15 s llega como `{:exit, :timeout}`; sin esa opción, el *timeout* mataría al proceso que consume el *stream*, es decir, a toda la importación.
5. **`Stream.chunk_every(500)`**: un `insert_all` por cada 500 filas en lugar de 500 *inserts*.
6. **`enrich` y `persist` inyectables**: los tests no llaman a la API ni a la base de datos.

**El número que importa no es la memoria, es la API.** Asumiendo unos 200 bytes por fila, 4 GB son unos 20 millones de filas. Con 20 llamadas concurrentes de ~200 ms tienes unas 100 por segundo: 20 000 000 / 100 = 200 000 s, unas **55 horas**. Antes de subir `@max_concurrency`, mira el límite de tasa del proveedor, si tiene un endpoint por lotes y si puedes deduplicar (si enriqueces por dominio de correo, hay muchos menos dominios que filas y una caché en un mapa o en ETS elimina la mayoría de llamadas). Req ya reintenta por defecto los errores transitorios en peticiones GET, así que no añadas otro bucle de reintentos encima.

Comprobación con un archivo pequeño y dobles de prueba:

```elixir
test "cuenta filas correctas y fallidas sin llamar a la API real" do
  path = Path.join(System.tmp_dir!(), "import_test.csv")
  File.write!(path, "id,email,country\n1,a@x.com,ES\n2,b@x.com,MX\n3,bad,AR\n")

  fake_enrich = fn
    %{email: "bad"} = record -> {:error, {:invalid_email, record.id}}
    record -> {:ok, Map.put(record, :geo, %{})}
  end

  test_pid = self()
  persist = fn records -> send(test_pid, {:persisted, length(records)}) end

  assert %{ok: 2, error: 1} = Importer.run(path, enrich: fake_enrich, persist: persist)
  assert_received {:persisted, 2}
end
```

Y en el archivo real, `:erlang.memory(:total)` durante la importación debe quedarse estable en lugar de crecer con el progreso.""",
            },
        ]
    },
    # 19) Zig: uniones de error, try/catch, errdefer y allocators explícitos
    {
        "messages": [
            {"role": "system", "content": "Responde con código completo y sus tests; explica solo lo que no sea evidente."},
            {"role": "user", "content": "Estoy aprendiendo Zig (0.14). No entiendo cuándo usar `try`, `catch` y `errdefer`, ni por qué todo me pide un allocator. ¿Me lo enseñas con algo real, tipo parsear una línea de config `clave = valor`?"},
            {
                "role": "assistant",
                "content": r"""```zig
const std = @import("std");

pub const ParseError = error{ MissingSeparator, EmptyKey, InvalidPort };

pub const Entry = struct {
    key: []u8,
    value: []u8,

    pub fn deinit(self: Entry, allocator: std.mem.Allocator) void {
        allocator.free(self.key);
        allocator.free(self.value);
    }
};

/// Parsea "clave = valor". El llamador es dueño de la memoria y debe llamar a deinit.
pub fn parseEntry(allocator: std.mem.Allocator, line: []const u8) (ParseError || std.mem.Allocator.Error)!Entry {
    const eq = std.mem.indexOfScalar(u8, line, '=') orelse return error.MissingSeparator;
    const raw_key = std.mem.trim(u8, line[0..eq], " \t");
    if (raw_key.len == 0) return error.EmptyKey;
    const raw_value = std.mem.trim(u8, line[eq + 1 ..], " \t");

    const key = try allocator.dupe(u8, raw_key);
    errdefer allocator.free(key); // solo se ejecuta si algo de aquí abajo devuelve un error
    const value = try allocator.dupe(u8, raw_value);

    return .{ .key = key, .value = value };
}

pub fn parsePort(text: []const u8) ParseError!u16 {
    const port = std.fmt.parseInt(u16, text, 10) catch |err| switch (err) {
        error.Overflow, error.InvalidCharacter => return error.InvalidPort,
    };
    if (port == 0) return error.InvalidPort;
    return port;
}

pub fn main() !void {
    var arena = std.heap.ArenaAllocator.init(std.heap.page_allocator);
    defer arena.deinit(); // libera todo lo reservado con el arena de una vez

    const entry = try parseEntry(arena.allocator(), "port = 8080");
    const port = try parsePort(entry.value);
    std.debug.print("{s} -> {d}\n", .{ entry.key, port });
}

test "parseEntry recorta espacios y devuelve memoria propia" {
    const entry = try parseEntry(std.testing.allocator, "  port = 8080 ");
    defer entry.deinit(std.testing.allocator);
    try std.testing.expectEqualStrings("port", entry.key);
    try std.testing.expectEqualStrings("8080", entry.value);
    try std.testing.expectEqual(@as(u16, 8080), try parsePort(entry.value));
}

test "errores de formato" {
    try std.testing.expectError(error.MissingSeparator, parseEntry(std.testing.allocator, "port 8080"));
    try std.testing.expectError(error.EmptyKey, parseEntry(std.testing.allocator, " = 8080"));
    try std.testing.expectError(error.InvalidPort, parsePort("70000"));
    try std.testing.expectError(error.InvalidPort, parsePort("80a"));
}

test "sin fugas cuando falla la segunda reserva" {
    var failing = std.testing.FailingAllocator.init(std.testing.allocator, .{ .fail_index = 1 });
    try std.testing.expectError(error.OutOfMemory, parseEntry(failing.allocator(), "port=8080"));
}
```

Ejecuta los tests con `zig test config.zig` y el programa con `zig run config.zig`.

Lo que no es evidente:

- **`E!T` es «un error del conjunto `E` o un `T`»**, y el compilador no te deja usar el `T` sin decidir qué haces con el error. `try expr` es exactamente `expr catch |err| return err`: propaga hacia arriba. `catch` es para **tratar** el error aquí: dar un valor por defecto, traducirlo (como `parsePort`, que convierte `Overflow` e `InvalidCharacter` en `InvalidPort`) o abortar. `orelse` es lo mismo para opcionales (`?T`), como el `indexOfScalar` que devuelve `?usize`.
- **El `switch` sobre el error es exhaustivo**: si una versión futura de `parseInt` añade un error nuevo, `parsePort` deja de compilar en vez de tratarlo mal en silencio. Un `catch return error.InvalidPort` también valdría, pero perdería esa protección.
- **`errdefer` frente a `defer`**: `defer` se ejecuta siempre al salir del bloque; `errdefer`, solo si se sale con un error. Aquí, si la reserva de `value` falla, `key` ya está reservada y nadie más la liberaría: el `errdefer` la libera. Si todo va bien, la propiedad de `key` pasa al llamador dentro de `Entry` y el `errdefer` no hace nada. Es el patrón para construir algo en varios pasos sin fugas.
- **Por qué el allocator es un parámetro**: Zig no tiene reservas ocultas. Ver `allocator` en la firma te dice que la función reserva memoria y que tú eliges dónde: un arena que se libera de golpe (en `main` no hace falta llamar a `deinit` de cada `Entry`), un búfer fijo en la pila (`std.heap.FixedBufferAllocator`), o `std.testing.allocator`, que hace fallar el test si algo no se libera.
- **El tercer test** usa `FailingAllocator` con `fail_index = 1`: la primera reserva funciona y la segunda falla. Borra la línea del `errdefer` y vuelve a ejecutarlo: el test pasa a fallar con un informe de fuga que señala la reserva de `key`. Es la comprobación de que el `errdefer` hace su trabajo, no solo de que el código compila.""",
            },
        ]
    },
    # 20) Zig: genéricos con comptime y cuándo usar anytype (multiturno)
    {
        "messages": [
            {"role": "user", "content": "En Zig, ¿cómo hago una estructura genérica? Por ejemplo un buffer circular de tamaño fijo para cualquier tipo. En C usaría macros o void*."},
            {
                "role": "assistant",
                "content": r"""En Zig un genérico es **una función que se ejecuta en tiempo de compilación y devuelve un tipo**. Los parámetros `comptime` (el tipo del elemento y la capacidad) se conocen al compilar, así que cada combinación genera un tipo concreto, sin `void*` ni macros, y con código Zig normal.

```zig
const std = @import("std");

pub fn RingBuffer(comptime T: type, comptime capacity: usize) type {
    if (capacity == 0) @compileError("RingBuffer capacity must be greater than zero");

    return struct {
        const Self = @This();

        items: [capacity]T = undefined,
        head: usize = 0, // índice del elemento más antiguo
        len: usize = 0,

        pub fn push(self: *Self, value: T) error{Full}!void {
            if (self.len == capacity) return error.Full;
            self.items[(self.head + self.len) % capacity] = value;
            self.len += 1;
        }

        /// Si está lleno, sobrescribe el más antiguo (útil para «los últimos N eventos»).
        pub fn pushOverwrite(self: *Self, value: T) void {
            if (self.len == capacity) {
                self.items[self.head] = value;
                self.head = (self.head + 1) % capacity;
            } else {
                self.items[(self.head + self.len) % capacity] = value;
                self.len += 1;
            }
        }

        pub fn pop(self: *Self) ?T {
            if (self.len == 0) return null;
            const value = self.items[self.head];
            self.head = (self.head + 1) % capacity;
            self.len -= 1;
            return value;
        }

        pub fn isEmpty(self: *const Self) bool {
            return self.len == 0;
        }
    };
}

test "orden FIFO y error cuando está lleno" {
    var rb = RingBuffer(u32, 2){};
    try rb.push(1);
    try rb.push(2);
    try std.testing.expectError(error.Full, rb.push(3));
    try std.testing.expectEqual(@as(?u32, 1), rb.pop());
    try rb.push(3);
    try std.testing.expectEqual(@as(?u32, 2), rb.pop());
    try std.testing.expectEqual(@as(?u32, 3), rb.pop());
    try std.testing.expectEqual(@as(?u32, null), rb.pop());
}

test "pushOverwrite conserva los últimos N" {
    var rb = RingBuffer(u8, 3){};
    for ([_]u8{ 1, 2, 3, 4, 5 }) |v| rb.pushOverwrite(v);
    try std.testing.expectEqual(@as(?u8, 3), rb.pop());
    try std.testing.expectEqual(@as(?u8, 4), rb.pop());
    try std.testing.expectEqual(@as(?u8, 5), rb.pop());
    try std.testing.expect(rb.isEmpty());
}
```

Lo importante:

- **`RingBuffer(u32, 2)` es un tipo**, y `RingBuffer(u32, 3)` es otro distinto. El compilador evalúa la función una vez por combinación y memoriza el resultado, de modo que dos usos con los mismos argumentos dan exactamente el mismo tipo.
- **`@compileError`** convierte un uso inválido (`capacity = 0`) en un error de compilación con tu mensaje, no en un fallo en ejecución.
- **Sin reservas de memoria**: el array va dentro de la estructura, así que el buffer puede vivir en la pila, en un global o dentro de otra estructura. No hay allocator en ninguna firma porque no hace falta.
- **`capacity` conocida al compilar** permite que `% capacity` con una potencia de dos se compile como una máscara de bits, sin que escribas nada especial.
- **`= undefined`** en `items`: no se inicializa porque nunca se lee una posición antes de escribirla (lo garantizan `head` y `len`). En modo Debug, Zig rellena la memoria `undefined` con `0xaa` para que un error de lógica se note.

Traza del primer test, para verificar los índices: `push(1)` escribe en 0; `push(2)` en 1; el tercero da `Full`; `pop` lee la posición 0 y mueve `head` a 1; `push(3)` escribe en `(1 + 1) % 2 = 0`; los dos `pop` siguientes leen 1 y 0. Sale 1, 2, 3: orden FIFO correcto aunque el 3 esté físicamente antes que el 2.""",
            },
            {"role": "user", "content": "¿Y cuándo se usa `anytype` en vez de `comptime T: type`? He visto cosas como `fn maxOf(a: anytype, b: @TypeOf(a))`."},
            {
                "role": "assistant",
                "content": r"""`anytype` es un parámetro cuyo tipo se **infiere del argumento** en cada llamada; `comptime T: type` es un tipo que el llamador **escribe** explícitamente. Las dos cosas generan una instancia por tipo; la diferencia está en qué contrato queda escrito.

```zig
fn maxOf(a: anytype, b: @TypeOf(a)) @TypeOf(a) {
    return if (a > b) a else b;
}

fn sumInts(comptime T: type, values: []const T) T {
    if (@typeInfo(T) != .int) @compileError("sumInts expects an integer type, got " ++ @typeName(T));
    var total: T = 0;
    for (values) |v| total += v;
    return total;
}

test "maxOf y sumInts" {
    try std.testing.expectEqual(@as(u8, 7), maxOf(@as(u8, 3), 7));
    try std.testing.expectEqual(@as(i32, 6), sumInts(i32, &[_]i32{ 1, 2, 3 }));
}
```

(Para el máximo, en código real usa el *builtin* `@max(a, b)`; `maxOf` está aquí solo para mostrar la forma.)

Cuándo cada uno:

| | `comptime T: type` | `anytype` |
|---|---|---|
| Hay que **devolver un tipo** (contenedores) | Obligatorio | No sirve |
| El tipo no se deduce de ningún argumento (`sumInts(i32, &.{})` con slice vacío, conversiones) | Necesario | No hay de dónde inferirlo |
| El tipo es obvio por el argumento y el requisito es simple («algo comparable») | Verboso | Natural |
| Documentación de la firma | Dice qué tipo espera | No dice nada: hay que leer el cuerpo |
| Mensajes de error | En la llamada, o en tu `@compileError` | Aparecen dentro del cuerpo, a veces lejos del error real |

Regla práctica: en **APIs públicas**, `comptime T: type` más una comprobación explícita con `@compileError` cuando el tipo deba cumplir algo; así el que se equivoca lee tu mensaje y no un error en la línea 40 de tu función. `anytype` para utilidades internas pequeñas donde el requisito es evidente, y en `b: @TypeOf(a)` para obligar a que dos argumentos tengan el mismo tipo, como en `maxOf`.

Dos notas de versión y de seguridad:

- En Zig 0.14 las etiquetas de `@typeInfo` son minúsculas (`.int`, `.float`, `.pointer`); en 0.13 y anteriores eran `.Int`, `.Float`. Si copias ejemplos antiguos, ese es el primer error que verás.
- `total += v` **comprueba desbordamiento** en Debug y ReleaseSafe: un `sumInts(u8, &.{ 200, 100 })` termina con *panic* («integer overflow») en lugar de devolver 44. Si quieres aritmética modular, es `+%=`; si quieres un error manejable, `std.math.add(T, total, v)` devuelve `error.Overflow`. Elegir uno de los tres es parte del contrato de la función, y conviene decidirlo explícitamente.""",
            },
        ]
    },
    # 21) Zig: slice que apunta a la pila de una función que ya terminó (usuario en inglés, código del usuario)
    {
        "messages": [
            {
                "role": "user",
                "content": r"""This Zig function sometimes returns garbage. The test passes, but in my real program the ID prints as junk. Zig 0.14.

```zig
const std = @import("std");

fn formatId(id: u32) []const u8 {
    var buf: [16]u8 = undefined;
    const text = std.fmt.bufPrint(&buf, "ID-{d}", .{id}) catch unreachable;
    return text;
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""`buf` lives in `formatId`'s stack frame. `bufPrint` returns a slice that points into `buf`, and you return that slice. When the function returns, the frame is released and the next call reuses that memory, so the slice now points at whatever the next function wrote there. It is a dangling pointer, and Zig does not stop you: there is no borrow checker, and the compiler does not track lifetimes in general.

**Why the test passes.** Undefined behavior that happens to look right. In the test, nothing overwrote that stack region between the return and the assertion. In your program, the very next call (often `std.debug.print` itself, which uses plenty of stack) overwrites it before the bytes are read.

Three fixes, depending on who should own the memory:

**1. The caller provides the buffer** (idiomatic, no allocation, my default):

```zig
fn formatId(buf: []u8, id: u32) ![]u8 {
    return std.fmt.bufPrint(buf, "ID-{d}", .{id});
}

// caller
var buf: [16]u8 = undefined;
const text = try formatId(&buf, 42);
std.debug.print("{s}\n", .{text});
```

The lifetime is now visible in the signature: `text` is valid exactly as long as `buf`, and `buf` lives in the caller's frame. A buffer that is too small becomes `error.NoSpaceLeft` instead of corruption.

**2. Allocate**, when the string must outlive the caller or its size is unbounded:

```zig
fn formatIdAlloc(allocator: std.mem.Allocator, id: u32) ![]u8 {
    return std.fmt.allocPrint(allocator, "ID-{d}", .{id});
}

// caller
const text = try formatIdAlloc(allocator, 42);
defer allocator.free(text);
```

**3. Return the bytes by value** in a small fixed-size struct:

```zig
const IdText = struct {
    buf: [16]u8 = undefined,
    len: usize = 0,

    pub fn slice(self: *const IdText) []const u8 {
        return self.buf[0..self.len];
    }
};

fn formatIdValue(id: u32) IdText {
    var out = IdText{};
    // "ID-" plus at most 10 digits for a u32 is 13 bytes, so 16 always fits
    const written = std.fmt.bufPrint(&out.buf, "ID-{d}", .{id}) catch unreachable;
    out.len = written.len;
    return out;
}
```

Returning `out` copies the whole array into the caller, which is the point. Keep the result in a variable before slicing it (`const id_text = formatIdValue(42);` and then `id_text.slice()`), so the slice points into memory you own.

About `catch unreachable`: in your original it was actually true (13 bytes always fit in 16), but it is a promise that is only checked in Debug and ReleaseSafe, where it panics. In ReleaseFast and ReleaseSmall, reaching `unreachable` is undefined behavior. Keep it only where the bound is provable, and leave a comment with the arithmetic, as above.

The general rule: never return a pointer or slice into a local variable of the function. String literals are fine (`return "ID-unknown";` has static lifetime), and so is anything owned by a parameter or by `self`. Since the compiler will not catch this for you, the defense is the API shape: a function that returns a slice should show in its signature where the memory comes from, whether that is a buffer parameter, an allocator parameter or a field of `self`.

Tests for option 1:

```zig
test "formatId writes into the caller's buffer" {
    var buf: [16]u8 = undefined;
    try std.testing.expectEqualStrings("ID-4294967295", try formatId(&buf, std.math.maxInt(u32)));
}

test "a buffer that is too small is an error, not memory corruption" {
    var small: [4]u8 = undefined;
    try std.testing.expectError(error.NoSpaceLeft, formatId(&small, 12345));
}
```""",
            },
        ]
    },
    # 22) Lua 5.4: metatablas, __index, métodos con ":" y herencia (system exacto)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {"role": "user", "content": "En Lua 5.4, ¿cuál es la forma idiomática de hacer «clases»? Veo código con `setmetatable` y `__index` y no entiendo qué hace cada cosa."},
            {
                "role": "assistant",
                "content": r"""Lua no tiene clases: tiene **tablas** y **metatablas**. Una «clase» es una tabla con los métodos, y cada instancia es una tabla con sus datos cuya metatabla dice «lo que no encuentres en mí, búscalo en la clase». Ese «búscalo en» es `__index`.

```lua
-- account.lua
local Account = {}
Account.__index = Account

function Account.new(owner, balance)
  if type(owner) ~= "string" or owner == "" then
    error("owner must be a non-empty string", 2)
  end
  local self = setmetatable({}, Account)
  self.owner = owner
  self.balance = balance or 0
  return self
end

function Account:deposit(amount)
  assert(type(amount) == "number" and amount > 0, "amount must be a positive number")
  self.balance = self.balance + amount
  return self
end

function Account:withdraw(amount)
  if amount > self.balance then
    return nil, "insufficient funds"
  end
  self.balance = self.balance - amount
  return self.balance
end

function Account.__tostring(account)
  return string.format("Account(%s, %.2f)", account.owner, account.balance)
end

return Account
```

Qué hace cada línea clave:

1. **`setmetatable({}, Account)`**: la instancia es una tabla vacía con `Account` como metatabla. Los datos (`owner`, `balance`) van en la instancia.
2. **`Account.__index = Account`**: cuando lees `a.deposit` y la instancia no tiene esa clave, Lua consulta el campo `__index` de su metatabla; como es la propia tabla `Account`, encuentra el método allí. Los métodos existen una sola vez y los comparten todas las instancias.
3. **Los dos puntos.** `function Account:deposit(amount)` es azúcar de `function Account.deposit(self, amount)`, y `a:deposit(10)` es `a.deposit(a, 10)`. El error clásico es llamar con punto: `a.deposit(10)` pasa `10` como `self` y falla con `attempt to index a number value (local 'self')`.
4. **`__tostring`** es un metamétodo: lo usan `print(a)` y `tostring(a)`.

Dos convenciones de errores que conviene seguir: `error(msg, 2)` atribuye el error a quien llamó a `new` (nivel 2), no a una línea interna; y para fallos **esperables**, como el saldo insuficiente, se devuelve `nil, mensaje` (igual que `io.open`) en lugar de lanzar, para que el llamador decida con `local balance, err = a:withdraw(500)`.

**Herencia**: el mismo mecanismo, encadenado.

```lua
-- savings_account.lua
local Account = require("account")

local SavingsAccount = setmetatable({}, { __index = Account })
SavingsAccount.__index = SavingsAccount
SavingsAccount.__tostring = Account.__tostring

function SavingsAccount.new(owner, balance, rate)
  local self = Account.new(owner, balance)
  self.rate = rate
  return setmetatable(self, SavingsAccount)
end

function SavingsAccount:addInterest()
  local interest = self.balance * self.rate
  if interest > 0 then
    self:deposit(interest)
  end
  return self.balance
end

return SavingsAccount
```

La búsqueda de `s:deposit` recorre la cadena instancia → `SavingsAccount` → `Account`. La línea no evidente es `SavingsAccount.__tostring = Account.__tostring`: **los metamétodos no se heredan** por `__index`. Lua los busca directamente en la metatabla, con acceso crudo, así que sin esa línea `print(s)` mostraría `table: 0x...`. Lo mismo vale para `__eq`, `__lt` o `__add`.

Comprobación:

```lua
local Account = require("account")
local SavingsAccount = require("savings_account")

local a = Account.new("Ana", 100)
a:deposit(50)
print(a)                         --> Account(Ana, 150.00)
print(a:withdraw(500))           --> nil   insufficient funds

local s = SavingsAccount.new("Luis", 200, 0.05)
print(s:addInterest())           --> 210.0
print(s)                         --> Account(Luis, 210.00)

assert(getmetatable(s) == SavingsAccount)
assert(s.deposit == Account.deposit)        -- el método es el mismo objeto, compartido
assert(not pcall(Account.new, ""))          -- owner vacío lanza error
```

`210.0` sale con decimal porque `200 * 0.05` es un número de coma flotante en Lua 5.4, que distingue enteros y flotantes.

La alternativa, cuando necesitas privacidad real, son los *closures*: `new` devuelve una tabla de funciones que capturan variables locales. Cada instancia lleva sus propias funciones (más memoria) y nadie puede tocar el saldo desde fuera. Para muchas instancias y código normal, el patrón de metatablas de arriba es el estándar.""",
            },
        ]
    },
    # 23) Lua: el operador # con huecos y table.remove dentro de un bucle (código del usuario)
    {
        "messages": [
            {
                "role": "user",
                "content": r"""Oigan, tengo este código en Lua 5.4 y no entiendo dos cosas:

```lua
local fields = {"a", "b", nil, "d"}
print(#fields)   -- ¿4 o 2? en un lado me dio 4

local tags = {"x", "", "y", "", "", "z"}
for i = 1, #tags do
  if tags[i] == "" then
    table.remove(tags, i)
  end
end
print(table.concat(tags, ","))   -- sale x,y,,z y esperaba x,y,z
```""",
            },
            {
                "role": "assistant",
                "content": r"""Son dos problemas distintos de la misma familia: las listas de Lua son tablas, y sus reglas solo se cumplen si la tabla es una **secuencia** (claves 1..n sin ningún `nil` en medio).

**1. `#` con huecos.** El operador de longitud solo está definido para secuencias. Con un `nil` en medio, el manual permite que `#t` devuelva cualquier «borde»: un índice `i` donde `t[i]` no es `nil` y `t[i + 1]` sí lo es. En `{"a", "b", nil, "d"}` hay dos bordes, 2 y 4, y **los dos son respuestas correctas**. Cuál obtienes depende de cómo se repartió la tabla internamente, que cambia según cómo la construyas. No es aleatorio, pero no está garantizado, así que no puedes depender de él.

La solución no es «calcular bien la longitud», es **no guardar `nil` en una lista**:

- Si necesitas marcar «sin valor», usa `false` o un valor centinela (`local NONE = {}` y comparas con `NONE`).
- Si de verdad necesitas posiciones vacías, guarda la longitud aparte, como hace `table.pack(...)`, que devuelve la tabla con un campo `n`. Para argumentos variables, `select("#", ...)` sí cuenta los `nil`.
- Recuerda que `ipairs` se detiene en el primer `nil` y que `pairs` no garantiza ningún orden.

**2. `table.remove` dentro de un `for` hacia delante.** Traza con tu lista:

| `i` | Lista antes | Acción | Lista después |
|---|---|---|---|
| 1 | x, "", y, "", "", z | `x` se queda | igual |
| 2 | x, "", y, "", "", z | borra la posición 2; todo se desplaza | x, y, "", "", z |
| 3 | x, y, "", "", z | borra la posición 3 | x, y, "", z |
| 4 | x, y, "", z | `z` se queda | igual |
| 5, 6 | | `tags[i]` es `nil` | igual |

Dos fallos a la vez: al borrar en `i`, el elemento siguiente baja a la posición `i`, que el bucle ya no vuelve a mirar (por eso se salva un `""`), y el límite `#tags` se calculó **una vez** al empezar (6), así que el bucle sigue más allá del final real.

Tres arreglos, de más simple a más eficiente:

```lua
-- a) Recorrer hacia atrás: borrar no afecta a lo que queda por visitar.
for i = #tags, 1, -1 do
  if tags[i] == "" then
    table.remove(tags, i)
  end
end

-- b) Construir una tabla nueva (lo más claro si no necesitas mutar la original).
local function filter(list, keep)
  local result = {}
  for _, value in ipairs(list) do
    if keep(value) then
      result[#result + 1] = value
    end
  end
  return result
end

-- c) Compactar en sitio en una sola pasada: O(n).
local function filter_in_place(list, keep)
  local n = #list
  local j = 0
  for i = 1, n do
    local value = list[i]
    if keep(value) then
      j = j + 1
      list[j] = value
    end
  end
  for i = j + 1, n do
    list[i] = nil
  end
  return list
end
```

La (a) es correcta, pero cada `table.remove` desplaza todo lo que hay detrás: con muchos borrados en una lista grande es O(n²). La (c) mueve cada elemento como mucho una vez y deja la tabla como una secuencia válida (limpia la cola con `nil` desde el final de lo conservado).

Comprobación:

```lua
local not_empty = function(v) return v ~= "" end

local tags = filter_in_place({"x", "", "y", "", "", "z"}, not_empty)
assert(table.concat(tags, ",") == "x,y,z" and #tags == 3)

assert(table.concat(filter({"", "", "a"}, not_empty), ",") == "a")
assert(#filter({}, not_empty) == 0)
```""",
            },
        ]
    },
    # 24) Lua: corrutinas como generadores y manejo de errores (multiturno)
    {
        "messages": [
            {"role": "user", "content": "¿Para qué sirven las corrutinas en Lua? Leí que no son hilos. Dame un caso práctico de verdad, no el típico productor-consumidor de juguete."},
            {
                "role": "assistant",
                "content": r"""Una corrutina es una función que puede **pausarse** (`coroutine.yield`) y **reanudarse** después (`coroutine.resume`) conservando su pila: variables locales, punto de ejecución y llamadas en curso. No son hilos: solo se ejecuta una a la vez y cada una cede el control explícitamente, así que no hay condiciones de carrera ni *locks*.

El caso práctico más útil es **convertir un recorrido recursivo en un iterador**. Recorrer un árbol en orden con recursión es trivial; convertirlo en un iterador para un `for` sin corrutinas obliga a gestionar una pila a mano. Con una corrutina, la pila de la recursión **es** el estado del iterador:

```lua
local function inorder(root)
  return coroutine.wrap(function()
    local function walk(node)
      if node == nil then return end
      walk(node.left)
      coroutine.yield(node.value)
      walk(node.right)
    end
    walk(root)
  end)
end

local tree = {
  value = 5,
  left = { value = 2, right = { value = 3 } },
  right = { value = 8 },
}

for value in inorder(tree) do
  io.write(value, " ")
end
print()   --> 2 3 5 8
```

Cómo funciona:

- `coroutine.wrap` crea la corrutina y devuelve una función que, cada vez que se llama, la reanuda hasta el siguiente `yield` y devuelve lo que se pasó a `yield`.
- El `for ... in` genérico llama a esa función en cada vuelta. Cuando `walk(root)` termina, la corrutina acaba sin devolver nada, el `for` recibe `nil` y se detiene.
- El `yield` ocurre **a tres niveles de recursión de profundidad** y aun así pausa todo: eso es lo que no puede hacer un iterador normal sin una pila explícita.

Traza para verificar el orden: `walk(5)` baja a `walk(2)`, que baja a `walk(nil)` y vuelve; entrega 2; baja a `walk(3)`, que entrega 3; vuelve a `walk(5)`, que entrega 5; baja a `walk(8)`, que entrega 8. Salida: `2 3 5 8`.

El mismo patrón sirve para paginar una API («dame el siguiente elemento» mientras la corrutina pide páginas cuando se le acaban), para leer un formato con estado (un *tokenizer* que hace `yield` de cada *token*) y, en entornos como OpenResty o los motores de juegos con Lua, para escribir código asíncrono que parece secuencial: el entorno reanuda la corrutina cuando llega la respuesta de red o pasa el siguiente frame.""",
            },
            {"role": "user", "content": "¿Y si dentro de la corrutina hay un error? Con `wrap` se me cae todo el programa y la traza no dice dónde fue."},
            {
                "role": "assistant",
                "content": r"""`coroutine.wrap` **relanza** el error en quien la llamó, y la traza que ves es la del llamador, no la de dentro de la corrutina. `coroutine.resume` hace lo contrario: nunca lanza y te devuelve el resultado como `pcall`, con `true, valores...` o `false, mensaje`.

```lua
local co = coroutine.create(function(a)
  local b = coroutine.yield(a * 2)
  if b == nil then error("missing value") end
  return a + b
end)

print(coroutine.resume(co, 10))   --> true   20
print(coroutine.resume(co, 5))    --> true   15
print(coroutine.status(co))       --> dead
print(coroutine.resume(co))       --> false  cannot resume dead coroutine
```

Traza: el primer `resume` arranca con `a = 10` y se pausa en el `yield`, que entrega 20. El segundo `resume` hace que ese `yield` devuelva 5, así que `b = 5` y la función termina con 15. A partir de ahí la corrutina está muerta y reanudarla es un error, devuelto como valor.

Para tener la comodidad de `wrap` (una función que llamas) con un error que diga **dónde** falló dentro de la corrutina, envuélvela tú y adjunta la traza de la propia corrutina con `debug.traceback(co, mensaje)`:

```lua
local function safe_wrap(fn)
  local co = coroutine.create(fn)
  return function(...)
    local result = table.pack(coroutine.resume(co, ...))
    if not result[1] then
      error(debug.traceback(co, result[2]), 0)
    end
    return table.unpack(result, 2, result.n)
  end
end
```

Detalles que lo hacen correcto:

- **`table.pack` y `result.n`**: la corrutina puede entregar `nil` como valor legítimo; con `n` no se pierde ningún valor al desempaquetar.
- **`debug.traceback(co, msg)`** recorre la pila **de la corrutina**, que sigue disponible porque una corrutina muerta por error conserva su pila. Ahí sale la línea real del `error`.
- **`error(..., 0)`**: nivel 0 para no anteponer otra posición al mensaje, que ya trae la traza completa.

Y si la corrutina se queda a medias (suspendida) porque el consumidor dejó de iterar, Lua 5.4 tiene `coroutine.close(co)`, que la cierra y ejecuta las variables `<close>` pendientes; úsalo cuando la corrutina tenga recursos abiertos (un archivo, una conexión).

Comprobación con el iterador del árbol, rompiendo un nodo a propósito:

```lua
local next_value = safe_wrap(function()
  coroutine.yield(1)
  local broken = nil
  coroutine.yield(broken.value)   -- falla aquí, en la segunda reanudación
end)

print(next_value())               --> 1
local ok, message = pcall(next_value)
print(ok)                         --> false
print(message)                    -- "attempt to index a nil value (local 'broken')" y la traza de la corrutina
```""",
            },
        ]
    },
    # 25) Scala 3: enum como ADT, match exhaustivo y opaque types
    {
        "messages": [
            {"role": "user", "content": "Paso de Java a Scala 3. ¿Cómo modelo el estado de un envío (creado, en tránsito con ubicación, entregado con fecha, devuelto con motivo) y un código de seguimiento que no sea un String cualquiera?"},
            {
                "role": "assistant",
                "content": r"""Con un **`enum` con parámetros** para el estado (un tipo algebraico: cada caso lleva sus propios datos) y un **`opaque type`** para el código de seguimiento, con un único constructor que valida.

```scala
//> using scala 3.3

import java.time.Instant

object tracking:
  opaque type TrackingCode = String

  object TrackingCode:
    private val Format = "[A-Z]{2}[0-9]{9}[A-Z]{2}".r

    def from(raw: String): Either[String, TrackingCode] =
      val normalized = raw.trim.toUpperCase
      if Format.matches(normalized) then Right(normalized)
      else Left(s"invalid tracking code: $raw")

    extension (code: TrackingCode) def value: String = code

import tracking.TrackingCode

enum Shipment:
  case Created(code: TrackingCode)
  case InTransit(code: TrackingCode, location: String)
  case Delivered(code: TrackingCode, at: Instant)
  case Returned(code: TrackingCode, reason: String)

def describe(shipment: Shipment): String = shipment match
  case Shipment.Created(code)             => s"${code.value}: creado"
  case Shipment.InTransit(code, location) => s"${code.value}: en tránsito en $location"
  case Shipment.Delivered(code, at)       => s"${code.value}: entregado el $at"
  case Shipment.Returned(code, reason)    => s"${code.value}: devuelto ($reason)"

def deliver(shipment: Shipment, at: Instant): Either[String, Shipment] = shipment match
  case Shipment.InTransit(code, _) => Right(Shipment.Delivered(code, at))
  case other                       => Left(s"cannot deliver a shipment in state $other")

@main def demo(): Unit =
  val result =
    for
      code      <- TrackingCode.from(" rr123456785es ")
      delivered <- deliver(Shipment.InTransit(code, "Madrid"), Instant.parse("2025-03-04T10:00:00Z"))
    yield describe(delivered)
  println(result)   // Right(RR123456785ES: entregado el 2025-03-04T10:00:00Z)
```

Ejecútalo con `scala run shipments.scala` (desde Scala 3.5 el comando `scala` es Scala CLI) o con `scala-cli run`.

Las decisiones, comparadas con lo que harías en Java:

- **`enum` con casos parametrizados** equivale a una `sealed interface` con `record`s en Java 21, en cuatro líneas. Cada caso es una *case class*: igualdad por valor, `toString` legible y *pattern matching* con desestructuración.
- **El `match` es exhaustivo.** Si añades `case Lost(code: TrackingCode)` y no lo tratas en `describe`, el compilador avisa con «match may not be exhaustive» y te dice qué caso falta. Compila con `-Werror` (`//> using option -Werror` en Scala CLI) para que ese aviso sea un error; en un modelo de estados es lo que quieres.
- **`opaque type TrackingCode = String`**: dentro de `object tracking` es un `String`; fuera, es un tipo distinto. No puedes pasar un `String` donde se espera un `TrackingCode` (`val c: TrackingCode = "RR123456785ES"` no compila) ni al revés, y la única forma de obtener uno es `TrackingCode.from`, que valida. En ejecución no hay envoltorio: es un `String` sin coste. Una `case class TrackingCode(value: String)` también funcionaría, pero asigna un objeto por código y deja `apply` y `copy` públicos, que permiten crear códigos sin validar.
- **La extensión `value` vive en el objeto compañero** del tipo opaco, y por eso está disponible en cualquier sitio sin importarla: el compilador busca extensiones en el compañero del tipo.
- **`Either[String, _]` + `for`**: cada `<-` continúa con el `Right` y se detiene en el primer `Left`, sin excepciones. Es la forma idiomática de encadenar validaciones y transiciones.
- **Transiciones como funciones** (`deliver`) que devuelven `Either`: la regla «solo se entrega lo que está en tránsito» vive en un sitio y se prueba sin infraestructura.

Comprobación de los tres caminos:

```scala
assert(TrackingCode.from("rr123456785es").isRight)
assert(TrackingCode.from("ABC").isLeft)

val Right(code) = TrackingCode.from("RR123456785ES"): @unchecked
assert(deliver(Shipment.Created(code), Instant.EPOCH).isLeft)
```

El formato del ejemplo es el de los envíos postales internacionales: dos letras, nueve dígitos y dos letras (`RR123456785ES`).""",
            },
        ]
    },
    # 26) Scala 3: type classes con given/using, extension y derives (multiturno)
    {
        "messages": [
            {"role": "user", "content": "En Scala 3 quiero exportar a CSV distintos tipos sin meter un método `toCsv` en cada clase, porque algunas vienen de librerías que no controlo. ¿Esto es lo de type classes con given y using?"},
            {
                "role": "assistant",
                "content": r"""Sí. Una *type class* separa **el comportamiento** («cómo se escribe un `A` en CSV») **del tipo**: defines la interfaz como un `trait` genérico, das una instancia (`given`) por tipo, y las funciones la piden con `using`. Puedes dar instancias para tipos que no son tuyos, sin tocarlos.

```scala
trait CsvEncoder[A]:
  def header: List[String]
  def encode(value: A): List[String]

object CsvEncoder:
  def apply[A](using encoder: CsvEncoder[A]): CsvEncoder[A] = encoder

private def escapeField(field: String): String =
  if field.exists(c => c == ',' || c == '"' || c == '\n') then
    "\"" + field.replace("\"", "\"\"") + "\""
  else field

extension [A](rows: Seq[A])(using encoder: CsvEncoder[A])
  def toCsv: String =
    (encoder.header +: rows.map(encoder.encode))
      .map(_.map(escapeField).mkString(","))
      .mkString("\n")
```

Instancias, una para un tipo tuyo y otra para uno de una librería (`java.awt.Point`, que no puedes modificar):

```scala
final case class Article(sku: String, name: String, priceCents: Long)

object Article:
  given CsvEncoder[Article] with
    def header = List("sku", "name", "price")
    def encode(article: Article) =
      List(article.sku, article.name, BigDecimal(article.priceCents, 2).toString)

object PointCsv:
  given CsvEncoder[java.awt.Point] with
    def header = List("x", "y")
    def encode(point: java.awt.Point) = List(point.x.toString, point.y.toString)
```

Uso:

```scala
import PointCsv.given

@main def demo(): Unit =
  println(List(Article("A1", "Taza, grande", 1999), Article("B2", "Plato", 450)).toCsv)
  println(List(java.awt.Point(1, 2)).toCsv)
```

Salida:

```
sku,name,price
A1,"Taza, grande",19.99
B2,Plato,4.50
x,y
1,2
```

Cómo encaja cada pieza:

- **`extension [A](rows: Seq[A])(using encoder: CsvEncoder[A])`**: `.toCsv` solo existe para listas de tipos con instancia. Con un tipo sin instancia, el error es **de compilación** («No given instance of type CsvEncoder[...] was found»), no un fallo en ejecución.
- **Dónde poner los `given`.** La instancia de `Article` está en su objeto compañero: el compilador la encuentra sin ningún `import`, porque busca en el compañero del tipo y en el de la *type class*. La de `Point` no puede ir en el compañero de `Point` (no es tuyo), así que va en un objeto y se importa con `import PointCsv.given`. En Scala 3 el comodín `*` **no** importa los `given`; hace falta `given` explícito, para que siempre se vea de dónde sale una instancia.
- **El escape** sigue la norma habitual de CSV (RFC 4180): campos con coma, comillas o salto de línea van entre comillas, y las comillas internas se duplican. Por eso `Taza, grande` sale entrecomillado.
- **`BigDecimal(1999, 2)`** construye 19,99 a partir del valor sin escala y la escala; nada de `Double` para dinero.

Sobre la sintaxis: `given ... with` es la de Scala 3.0 a 3.5; las versiones recientes añaden una forma nueva, pero esta sigue siendo válida.""",
            },
            {"role": "user", "content": "¿Y puedo derivar la instancia automáticamente para case classes, como hace circe con `derives`? No quiero escribir el header a mano en 30 clases."},
            {
                "role": "assistant",
                "content": r"""Sí. `derives CsvEncoder` en una *case class* hace que el compilador llame a `CsvEncoder.derived`, y esa función obtiene en tiempo de compilación los **nombres** y los **tipos** de los campos a través de un `Mirror`. Solo necesitas una segunda *type class* para codificar cada campo individual.

```scala
import scala.compiletime.{constValueTuple, summonAll}
import scala.deriving.Mirror

trait FieldEncoder[A]:
  def encode(value: A): String

object FieldEncoder:
  given FieldEncoder[String] = value => value
  given FieldEncoder[Int] = _.toString
  given FieldEncoder[Long] = _.toString
  given FieldEncoder[BigDecimal] = _.toString
  given [A](using inner: FieldEncoder[A]): FieldEncoder[Option[A]] = _.fold("")(inner.encode)

trait CsvEncoder[A]:
  def header: List[String]
  def encode(value: A): List[String]

object CsvEncoder:
  def apply[A](using encoder: CsvEncoder[A]): CsvEncoder[A] = encoder

  def fromFields[A](labels: List[String], fieldEncoders: List[FieldEncoder[Any]]): CsvEncoder[A] =
    new CsvEncoder[A] {
      def header: List[String] = labels
      def encode(value: A): List[String] =
        value.asInstanceOf[Product].productIterator.zip(fieldEncoders)
          .map((field, fieldEncoder) => fieldEncoder.encode(field))
          .toList
    }

  inline def derived[A](using mirror: Mirror.ProductOf[A]): CsvEncoder[A] =
    fromFields(
      constValueTuple[mirror.MirroredElemLabels].toList.map(_.toString),
      summonAll[Tuple.Map[mirror.MirroredElemTypes, FieldEncoder]].toList
        .asInstanceOf[List[FieldEncoder[Any]]],
    )
```

Uso, sin escribir nada más por clase:

```scala
final case class Customer(id: Long, name: String, email: Option[String]) derives CsvEncoder

@main def demo(): Unit =
  println(List(Customer(1, "Ana", Some("ana@example.com")), Customer(2, "Luis", None)).toCsv)
```

```
id,name,email
1,Ana,ana@example.com
2,Luis,
```

Qué pasa en compilación:

1. `derives CsvEncoder` genera en el compañero de `Customer` un `given CsvEncoder[Customer] = CsvEncoder.derived`.
2. El compilador sintetiza un `Mirror.ProductOf[Customer]`, cuyos miembros de tipo describen la clase: `MirroredElemLabels` es la tupla de tipos literales `("id", "name", "email")` y `MirroredElemTypes` es `(Long, String, Option[String])`.
3. `constValueTuple` convierte los nombres en valores (el header), y `summonAll[Tuple.Map[..., FieldEncoder]]` busca un `FieldEncoder` por campo. **Si un campo no tiene instancia** (por ejemplo, un `java.time.LocalDate`), la compilación falla en la línea del `derives` señalando la instancia que falta. Añades un `given FieldEncoder[LocalDate]` y listo.
4. `derived` es `inline` porque necesita esos tipos concretos en el punto de uso; el objeto en sí se crea en `fromFields`, que es un método normal. Así la clase anónima no se duplica en cada sitio donde se deriva (el compilador avisa si haces el `new` dentro del método `inline`).

Los dos `asInstanceOf` son el precio de trabajar campo a campo con tipos heterogéneos: son seguros porque el `Mirror` garantiza que el campo i tiene el tipo del codificador i, en el mismo orden. Están confinados en una función de diez líneas, no repartidos por el código.

Limitaciones a conocer: esto cubre *case classes* (productos). Para jerarquías `sealed` o `enum` haría falta tratar `Mirror.SumOf`, y los campos anidados (una *case class* dentro de otra) necesitarían aplanarse. Si vas a exportar mucho, una librería como `fs2-data-csv` ya trae derivación completa; lo de arriba es el mecanismo que usan por dentro y sirve bien para un caso acotado como el tuyo.""",
            },
        ]
    },
    # 27) Scala: List como lista enlazada, O(n²) escondido y groupMapReduce (usuario en inglés, código del usuario)
    {
        "messages": [
            {
                "role": "user",
                "content": r"""This Scala 3 function takes minutes with 200k orders (about 50k customers). What's wrong with it?

```scala
final case class Order(customerId: String, amount: BigDecimal)

def topCustomers(orders: List[Order], n: Int): List[(String, BigDecimal)] =
  var totals = List.empty[(String, BigDecimal)]
  for i <- 0 until orders.length do
    val o = orders(i)
    val idx = totals.indexWhere(_._1 == o.customerId)
    if idx >= 0 then
      totals = totals.updated(idx, (o.customerId, totals(idx)._2 + o.amount))
    else
      totals = totals :+ (o.customerId, o.amount)
  totals.sortBy(-_._2).take(n)
```""",
            },
            {
                "role": "assistant",
                "content": r"""`List` is a singly linked list, and almost every operation in that loop walks it from the head. Four hidden linear costs, each paid once per order:

| Expression | Cost on a `List` | Why |
|---|---|---|
| `orders(i)` | O(i) | Indexing follows `i` links from the head |
| `totals.indexWhere(...)` | O(k), k = customers seen | Linear search for the customer |
| `totals.updated(idx, ...)` | O(idx) | Rebuilds every node before `idx` |
| `totals :+ x` | O(k) | Appending copies the whole list |

With n = 200,000 orders, `orders(i)` alone costs about n²/2 = 2 × 10¹⁰ steps, and the `totals` operations add roughly n × k with k up to 50,000, another 10¹⁰. That is your minutes.

The fix is not a faster loop; it is the right operation. "Sum amounts per key" is exactly `groupMapReduce`, which does it in one pass with a hash map:

```scala
final case class Order(customerId: String, amount: BigDecimal)

def topCustomers(orders: Iterable[Order], n: Int): List[(String, BigDecimal)] =
  orders
    .groupMapReduce(_.customerId)(_.amount)(_ + _)
    .toList
    .sortBy(_._2)(Ordering[BigDecimal].reverse)
    .take(n)
```

- `groupMapReduce(key)(value)(combine)`: groups by `customerId`, maps each order to its `amount`, and reduces each group with `+`. One traversal, no intermediate lists per customer, unlike `groupBy(...).view.mapValues(_.map(_.amount).sum)`.
- Sorting k = 50,000 totals is O(k log k), negligible here. If n were tiny and k were in the millions, a bounded priority queue would avoid the full sort, but at this size the sort is not worth replacing.
- `Ordering[BigDecimal].reverse` reads more clearly than negating the key, and it works for types that have no unary minus.
- The parameter is `Iterable[Order]`, so callers can pass a `Vector`, a `List` or a view without converting.

Total cost: O(n + k log k), well under a second for your sizes.

When you do need indexed access or appends, pick the collection for it:

- **`List`**: O(1) prepend, head and tail. Ideal for recursion and building in reverse.
- **`Vector`**: effectively constant-time indexing, append and `updated`. The general-purpose immutable sequence.
- **`ArrayBuffer`** or **`ListBuffer`**: local mutable builders, fine inside a function as long as the mutability does not leak out.
- **`Map`**: lookup by key, which is what `indexWhere` was emulating.

A test with munit that pins the behavior, including a customer that appears twice:

```scala
class TopCustomersSuite extends munit.FunSuite {
  test("sums per customer and sorts by total, descending") {
    val orders = List(
      Order("a", BigDecimal(10)),
      Order("b", BigDecimal(5)),
      Order("a", BigDecimal(7)),
      Order("c", BigDecimal(20)),
    )
    assertEquals(topCustomers(orders, 2), List(("c", BigDecimal(20)), ("a", BigDecimal(17))))
  }
}
```

Expected by hand: a = 10 + 7 = 17, b = 5, c = 20; sorted descending c, a, b; the top two are c and a.""",
            },
        ]
    },
    # 28) R: vectorización, 1:length y crecer vectores (código del usuario, revisor estricto)
    {
        "messages": [
            {"role": "system", "content": "Eres un revisor de código estricto. Señala cada problema con su causa y propón el cambio mínimo."},
            {
                "role": "user",
                "content": r"""Revisa esta función de R. Con 200 000 valores tarda una eternidad y a veces devuelve cosas raras:

```r
normalize_scores <- function(scores) {
  result <- c()
  for (i in 1:length(scores)) {
    z <- (scores[i] - mean(scores)) / sd(scores)
    result <- c(result, z)
  }
  result
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""Cinco problemas: dos de rendimiento y tres de corrección.

**Rendimiento**

1. **`mean(scores)` y `sd(scores)` dentro del bucle.** Se recalculan en cada vuelta y cada cálculo recorre los 200 000 valores: 200 000 × 200 000 = 4 × 10¹⁰ operaciones. Esa es la eternidad. Ambos valores son constantes: se calculan una vez, fuera.
2. **`result <- c(result, z)`.** Cada concatenación crea un vector nuevo y copia el anterior: otra vez O(n²), ahora en copias de memoria.

**Corrección**

3. **`1:length(scores)` con un vector vacío** da `1:0`, que es `c(1, 0)`: el bucle se ejecuta dos veces, `scores[1]` es `NA` y la función devuelve `NA` en lugar de un vector vacío. Esa es una de las «cosas raras». Si alguna vez necesitas un índice, es `seq_along(scores)`.
4. **Un solo `NA` en los datos** hace que `mean` y `sd` sean `NA`, y entonces **todos** los resultados son `NA`.
5. **Un vector constante** (todas las puntuaciones iguales) tiene `sd` igual a 0, y la división da `NaN` en todas las posiciones. Con un solo valor, `sd` es `NA`.

Versión corregida: R está vectorizado, así que la operación se aplica al vector entero y el bucle sobra.

```r
normalize_scores <- function(scores, na.rm = TRUE) {
  stopifnot(is.numeric(scores))
  if (length(scores) == 0L) {
    return(numeric(0))
  }
  center <- mean(scores, na.rm = na.rm)
  spread <- sd(scores, na.rm = na.rm)
  if (is.na(spread) || spread == 0) {
    stop("scores needs at least two distinct non-missing values", call. = FALSE)
  }
  (scores - center) / spread
}
```

- Una pasada para la media, otra para la desviación y una operación vectorial ejecutada en C. Con 200 000 valores son milisegundos.
- Con `na.rm = TRUE`, los `NA` no contaminan al resto y se quedan como `NA` **en su posición**, que es lo que espera quien luego une el resultado con los datos originales.
- El caso degenerado falla con un mensaje claro en lugar de devolver `NaN` en silencio.

`scale(scores)` hace el mismo cálculo, pero devuelve una matriz de una columna con atributos (`scaled:center`, `scaled:scale`); si la usas, `as.vector(scale(scores))`.

Si en otro caso de verdad necesitas un bucle: `seq_along` para los índices, reserva el vector antes (`out <- numeric(length(x))`, luego `out[i] <- ...`) y, si aplicas una función elemento a elemento, `vapply(x, f, numeric(1))` en lugar de `sapply`: `vapply` comprueba que cada resultado es un número y falla si no, mientras que `sapply` puede devolverte una lista sin avisar.

Tests con `testthat`:

```r
library(testthat)

test_that("devuelve z-scores", {
  expect_equal(normalize_scores(c(2, 4, 6)), c(-1, 0, 1))
})

test_that("conserva los NA en su posición sin contaminar el resto", {
  z <- normalize_scores(c(2, NA, 6))
  expect_true(is.na(z[2]))
  expect_equal(z[c(1, 3)], c(-1, 1) / sqrt(2))
})

test_that("vector vacío y vector constante", {
  expect_identical(normalize_scores(numeric(0)), numeric(0))
  expect_error(normalize_scores(c(5, 5, 5)), "two distinct")
})
```

Cuentas de los dos primeros: en `c(2, 4, 6)` la media es 4 y la desviación típica muestral es √((4 + 0 + 4) / 2) = 2, así que los z-scores son −1, 0 y 1. En `c(2, NA, 6)` la media es 4 y la desviación es √((4 + 4) / 1) = 2√2, de modo que los extremos quedan en ∓1/√2.""",
            },
        ]
    },
    # 29) R: dplyr con .by, slice_max y NA; versión en R base (multiturno)
    {
        "messages": [
            {"role": "user", "content": "Tengo un data frame de ventas (date, store, product, units, price) y quiero por tienda y mes: ingresos totales, ticket medio y el producto más vendido. Uso R 4.3 con dplyr y me salen NA por todos lados."},
            {
                "role": "assistant",
                "content": r"""Los `NA` vienen de que `sum` y `mean` devuelven `NA` en cuanto hay un solo valor ausente. Pero `na.rm = TRUE` sin más los esconde, y entonces infravaloras los ingresos sin enterarte. La solución completa es quitarlos del cálculo **y contarlos** en una columna.

Asumo una fila por ticket y que `date` ya es de clase `Date` (si viene como texto del CSV, conviértela antes con `lubridate::ymd(date)`; compruébalo con `class(sales$date)`).

```r
library(dplyr)       # >= 1.1.0 para .by, by y join_by
library(lubridate)

monthly <- sales |>
  mutate(
    month = floor_date(date, "month"),
    revenue = units * price
  ) |>
  summarise(
    total_revenue = sum(revenue, na.rm = TRUE),
    tickets = n(),
    avg_ticket = mean(revenue, na.rm = TRUE),
    missing_price = sum(is.na(price)),
    .by = c(store, month)
  )

top_products <- sales |>
  mutate(month = floor_date(date, "month")) |>
  summarise(units = sum(units, na.rm = TRUE), .by = c(store, month, product)) |>
  slice_max(units, n = 1, with_ties = FALSE, by = c(store, month)) |>
  select(store, month, top_product = product)

report <- monthly |>
  left_join(top_products, by = join_by(store, month)) |>
  arrange(store, month)
```

Decisiones:

- **`.by` en `summarise`** agrupa solo para esa operación y devuelve un resultado sin agrupar; con `group_by()` tendrías que acordarte de `ungroup()`. En `slice_max` el argumento se llama `by`, sin punto.
- **`missing_price`** convierte el problema silencioso en un dato visible: si un mes tiene 0 ingresos pero `missing_price` es mayor que 0, sabes por qué.
- **El producto más vendido es un cálculo aparte**, porque necesita agrupar también por producto. `with_ties = FALSE` garantiza una fila por tienda y mes aunque haya empate.
- **Una trampa que evité con los nombres**: dentro de `summarise`, cada expresión ve los resultados de las anteriores. Si hubiera escrito `revenue = sum(revenue)` y después `mean(revenue)`, la media se calcularía sobre la suma ya resumida (un solo valor) y no sobre los tickets. Por eso la suma se llama `total_revenue`.

Comprobación con un ejemplo que puedes calcular a mano:

```r
sales <- tibble(
  date = as.Date(c("2024-01-05", "2024-01-20", "2024-01-21", "2024-02-02")),
  store = "A",
  product = c("cafe", "te", "cafe", "te"),
  units = c(2, 1, 3, 4),
  price = c(1.5, 2, 1.5, NA)
)
```

Ingresos por fila: 3, 2, 4,5 y `NA`. Debe salir:

- **Enero**: `total_revenue` 9,5; `tickets` 3; `avg_ticket` 3,17; `missing_price` 0; `top_product` cafe (5 unidades contra 1).
- **Febrero**: `total_revenue` 0; `tickets` 1; `avg_ticket` `NaN` (la media de un conjunto vacío tras quitar el `NA`); `missing_price` 1; `top_product` te.

Febrero es justo el caso que antes te salía como `NA`: ahora dice explícitamente «hubo una venta y no tiene precio».""",
            },
            {"role": "user", "content": "¿Y cómo lo hago con R base, sin dependencias? Es para un script que corre en un servidor donde no me dejan instalar paquetes."},
            {
                "role": "assistant",
                "content": r"""Con `split` + `lapply` + `do.call(rbind, ...)`: partes el data frame por tienda y mes, calculas una fila por grupo con R base y las apilas. Es más explícito que `aggregate`, que se complica cuando quieres varias métricas distintas por grupo.

```r
sales$month <- format(sales$date, "%Y-%m")

groups <- split(sales, list(sales$store, sales$month), drop = TRUE)

rows <- lapply(groups, function(g) {
  revenue <- g$units * g$price
  units_by_product <- tapply(g$units, g$product, sum, na.rm = TRUE)
  data.frame(
    store = g$store[1],
    month = g$month[1],
    total_revenue = sum(revenue, na.rm = TRUE),
    tickets = nrow(g),
    avg_ticket = mean(revenue, na.rm = TRUE),
    missing_price = sum(is.na(g$price)),
    top_product = names(units_by_product)[which.max(units_by_product)]
  )
})

report <- do.call(rbind, rows)
report <- report[order(report$store, report$month), ]
rownames(report) <- NULL
```

Piezas:

- **`split(..., drop = TRUE)`** crea una lista de data frames, uno por combinación de tienda y mes que **existe** en los datos; sin `drop = TRUE` también aparecerían combinaciones vacías.
- **`tapply(g$units, g$product, sum, na.rm = TRUE)`** suma unidades por producto dentro del grupo y devuelve un vector con nombres; `which.max` da la posición del máximo y `names(...)` el producto.
- **`do.call(rbind, rows)`** apila la lista de data frames de una fila en uno solo. Desde R 4.0, `data.frame` no convierte texto en factores por defecto, así que `store` y `top_product` quedan como texto.
- **`format(date, "%Y-%m")`** da el mes como texto (`"2024-01"`), mientras que la versión con dplyr lo daba como fecha (`2024-01-01`). Si vas a comparar o a unir ambos informes, usa la misma representación.

Una diferencia sutil con la versión anterior: **los empates**. `which.max` devuelve el primer máximo en el orden de `tapply`, que es alfabético por producto; `slice_max(with_ties = FALSE)` se queda con la primera fila en el orden de los datos. Si el empate importa para el negocio, decide la regla (por ejemplo, alfabética) y aplícala explícitamente en las dos versiones.

Comprobación con el mismo ejemplo de cuatro filas: enero debe dar 9,5 / 3 / 3,17 / 0 / cafe y febrero 0 / 1 / `NaN` / 1 / te. Si tienes acceso a una máquina con dplyr, compara las columnas numéricas de los dos informes con `all.equal(report$total_revenue, report_dplyr$total_revenue)`; deben coincidir exactamente, porque las dos versiones hacen las mismas sumas.""",
            },
        ]
    },
    # 30) R: factores y as.numeric (usuario en inglés que pide la respuesta en español)
    {
        "messages": [
            {"role": "user", "content": "Quick R question, but please answer in Spanish, it's for a junior on my team. R 4.3. I read a CSV with `read.csv('ventas.csv', stringsAsFactors = TRUE)` (copied from an old tutorial). The `price` column shows values like 10.5, 20 and 7.25, but `as.numeric(df$price)` gives me 1, 2, 3. Why?"},
            {
                "role": "assistant",
                "content": r"""Se combinan dos cosas: la columna `price` se leyó como **texto**, y `stringsAsFactors = TRUE` convirtió ese texto en un **factor**. `as.numeric` sobre un factor no convierte los valores: devuelve sus **códigos internos**.

**Qué es un factor.** Es un vector de enteros más una tabla de etiquetas (los *levels*). R guarda `price` como «código 1, código 2, código 3» y aparte la lista de niveles. Los niveles se ordenan **como texto**, y como texto `"10.5"` < `"20"` < `"7.25"` (se compara carácter a carácter: `"1"` < `"2"` < `"7"`). Por eso 10.5 recibe el código 1, 20 el 2 y 7.25 el 3, que es exactamente lo que ves.

```r
f <- factor(c("10.5", "20", "7.25"))
levels(f)                     # "10.5" "20"   "7.25"
as.integer(f)                 # 1 2 3            <- los códigos internos
as.numeric(as.character(f))   # 10.50 20.00 7.25 <- primero a texto, luego a número
as.numeric(levels(f))[f]      # lo mismo, convirtiendo cada nivel una sola vez
```

**Por qué la columna era texto.** `read.csv` solo convierte una columna a número si **todos** sus valores se pueden leer como número. Basta un valor como `"N/A"`, `"12,5"` (coma decimal) o `"1.200,00"` (separador de miles) para que la columna entera quede como texto. Ese es el problema de fondo; el factor solo lo agravó.

**Arreglo en origen**, no después:

```r
df <- read.csv("ventas.csv", na.strings = c("", "NA", "N/A"))
str(df)                        # price debe aparecer como num
```

- Quita `stringsAsFactors = TRUE`: desde R 4.0 el valor por defecto es `FALSE`, y para datos numéricos nunca lo quieres.
- `na.strings` le dice a R qué textos significan «sin valor».
- Si los datos usan coma decimal, `read.csv2()` (separador `;` y decimal `,`) o `read.csv(..., dec = ",")`.

Si `price` sigue saliendo como `chr`, localiza los valores culpables antes de convertir:

```r
price_num <- suppressWarnings(as.numeric(df$price))
unique(df$price[is.na(price_num) & !is.na(df$price)])   # los que no son números
```

Con `readr` el diagnóstico viene incluido: `readr::read_csv("ventas.csv", col_types = readr::cols(price = readr::col_double()))` fuerza el tipo, y `readr::problems(df)` lista las filas y valores que no encajaron.

**Regla para el equipo**: los factores son para variables **categóricas** con un conjunto conocido de valores (país, estado de un pedido), útiles en modelos y para fijar el orden en gráficos. Nunca para números ni para texto libre.

Comprobación: añade `stopifnot(is.numeric(df$price))` justo después de leer el CSV. Si algún día vuelve a entrar un valor raro, el script falla en la carga, con un mensaje claro, y no tres pasos después con una suma sin sentido.""",
            },
        ]
    },
]
