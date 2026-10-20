"""Mobile: Flutter 3.2x, React Native 0.7x con Expo y SwiftUI (iOS 17+).

30 filas. Reparto aproximado: Flutter 12 · React Native/Expo 10 · SwiftUI 8.
Sigue entrenamiento/GUIA_DE_ESTILO.md.
"""

SISTEMA = (
    "Eres un asistente experto en programación, análisis y razonamiento. Respondes en el "
    "idioma del usuario (español por defecto), con precisión y sin relleno, y verificas tu "
    "trabajo antes de responder."
)

ROWS = [
    # 1) Flutter: BuildContext tras un await (error concreto, principiante-intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": """Tengo esto en un botón de guardar y el analizador me marca `Don't use 'BuildContext's across async gaps.` Funciona igual, ¿lo ignoro?

```dart
onPressed: () async {
  await repository.saveProfile(profile);
  ScaffoldMessenger.of(context).showSnackBar(
    const SnackBar(content: Text('Perfil guardado')),
  );
  Navigator.of(context).pop();
},
```""",
            },
            {
                "role": "assistant",
                "content": """No lo ignores: funciona mientras el usuario espera, y falla en cuanto no lo hace.

**Qué es el `BuildContext`.** No es un objeto de datos: es el `Element` del widget, su posición en el árbol. `ScaffoldMessenger.of(context)` y `Navigator.of(context)` suben por el árbol desde esa posición buscando un ancestro. Si durante el `await` el usuario cierra la pantalla, ese elemento se desmonta y el `context` queda desactivado. Al usarlo después pasa una de dos cosas:

- una excepción `Looking up a deactivated widget's ancestor is unsafe`, o
- peor: `Navigator.of(context).pop()` cierra **otra** pantalla, la que ahora está encima.

El aviso del analizador (`use_build_context_synchronously`) existe por eso. El arreglo es comprobar `context.mounted` después de cada `await` antes de tocar el contexto:

```dart
import 'package:flutter/material.dart';

class SaveProfileButton extends StatelessWidget {
  const SaveProfileButton({super.key, required this.repository, required this.profile});

  final ProfileRepository repository;
  final Profile profile;

  @override
  Widget build(BuildContext context) {
    return FilledButton(
      onPressed: () async {
        try {
          await repository.saveProfile(profile);
        } on Exception catch (error) {
          if (!context.mounted) return;
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('No se pudo guardar: $error')),
          );
          return;
        }
        // La pantalla pudo cerrarse durante el await: no tocamos un contexto muerto.
        if (!context.mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Perfil guardado')),
        );
        Navigator.of(context).pop();
      },
      child: const Text('Guardar'),
    );
  }
}
```

Dentro de un `State`, el equivalente es la propiedad `mounted` del propio `State`.

**¿Y capturar antes del `await`?** Es la otra solución que verás:

```dart
final messenger = ScaffoldMessenger.of(context);
final navigator = Navigator.of(context);
await repository.saveProfile(profile);
messenger.showSnackBar(const SnackBar(content: Text('Perfil guardado')));
navigator.pop();
```

Silencia el aviso, y para el `ScaffoldMessenger` es correcto: vive por encima de las rutas y sigue existiendo aunque la pantalla se cierre, así que el SnackBar se muestra en la pantalla anterior, que suele ser lo deseable. Pero para el `pop()` es un bug: si el usuario ya volvió atrás, `navigator.pop()` cierra la pantalla en la que está ahora. Para navegar después de un `await`, siempre `mounted`.

Comprobación: haz que el repositorio tarde (`await Future<void>.delayed(const Duration(seconds: 3))` en una implementación falsa), pulsa Guardar y vuelve atrás enseguida. Con el código original verás la excepción en consola o una pantalla de más cerrada; con el arreglo, nada.""",
            },
        ]
    },
    # 2) Flutter: RenderFlex overflow y unbounded height (multiturno, error concreto)
    {
        "messages": [
            {
                "role": "user",
                "content": """Me sale la franja amarilla y negra y en consola:

```
A RenderFlex overflowed by 42 pixels on the right.
```

Es una fila con un icono, el nombre del archivo y la fecha:

```dart
Row(
  children: [
    const Icon(Icons.description),
    const SizedBox(width: 8),
    Text(file.name),
    const SizedBox(width: 8),
    Text(file.modifiedLabel),
  ],
)
```""",
            },
            {
                "role": "assistant",
                "content": """El nombre del archivo es más largo que el espacio que queda, y nada le dice al `Text` que se ajuste.

La regla de layout de Flutter: **las restricciones bajan, los tamaños suben y el padre coloca**. Un `Row` pasa a sus hijos no flexibles un ancho **ilimitado** en el eje principal y les pregunta cuánto miden. El `Text` responde con el ancho de todo su contenido en una línea. Si la suma de los hijos supera el ancho del `Row`, este no puede encogerlos y pinta la franja de overflow con los píxeles que sobran: 42.

El arreglo es convertir el nombre en un hijo **flexible**, que recibe el espacio restante como límite, y decirle al texto qué hacer cuando no cabe:

```dart
Row(
  children: [
    const Icon(Icons.description),
    const SizedBox(width: 8),
    Expanded(
      child: Text(
        file.name,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
      ),
    ),
    const SizedBox(width: 8),
    Text(file.modifiedLabel),
  ],
)
```

Orden de cálculo: primero se miden los hijos rígidos (icono, separadores y fecha); el `Expanded` recibe exactamente lo que sobra y el `Text` se corta con puntos suspensivos.

`Expanded` o `Flexible`: `Expanded` obliga al hijo a ocupar todo el espacio restante; `Flexible` (con su `fit: FlexFit.loose` por defecto) le permite ocupar menos. Si quieres que la fecha quede pegada al nombre cuando este es corto, usa `Flexible`; si la quieres alineada a la derecha siempre, `Expanded`.

Comprobación con un test que fija una pantalla estrecha:

```dart
testWidgets('la fila no desborda con nombres largos', (tester) async {
  tester.view.physicalSize = const Size(320, 640);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  await tester.pumpWidget(MaterialApp(
    home: Scaffold(body: FileRow(file: FileItem(name: 'informe_trimestral_definitivo_v7_revisado.pdf', modifiedLabel: 'hace 2 h'))),
  ));

  expect(tester.takeException(), isNull);
});
```

Con el código original el test falla, porque el overflow se reporta como excepción en los tests.""",
            },
            {
                "role": "user",
                "content": "Arreglado. Ahora metí un `ListView` debajo de un encabezado dentro de un `Column` y sale `Vertical viewport was given unbounded height.`",
            },
            {
                "role": "assistant",
                "content": """Es el mismo principio en el otro eje. Un `Column` da a sus hijos no flexibles una altura ilimitada, y un `ListView` intenta ocupar toda la altura que le den para saber cuánto puede desplazarse. «Toda la altura de infinito» no es un tamaño, así que Flutter se niega.

El arreglo es darle a la lista el espacio que sobra:

```dart
Column(
  children: [
    const Padding(
      padding: EdgeInsets.all(16),
      child: Text('Archivos recientes', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w600)),
    ),
    Expanded(
      child: ListView.builder(
        itemCount: files.length,
        itemBuilder: (context, index) => FileRow(file: files[index]),
      ),
    ),
  ],
)
```

El encabezado queda fijo y la lista se desplaza debajo.

Verás en internet `shrinkWrap: true` como solución. Funciona, pero obliga a la lista a construir y medir **todos** sus elementos para conocer su altura total, así que pierdes la carga perezosa. Con 20 elementos da igual; con 2.000 es la causa de los tirones. Úsalo solo para listas cortas y acotadas.

Si lo que quieres es que el encabezado también se desplace con la lista, la herramienta es un `CustomScrollView` con slivers, que comparte un único scroll:

```dart
CustomScrollView(
  slivers: [
    const SliverToBoxAdapter(
      child: Padding(
        padding: EdgeInsets.all(16),
        child: Text('Archivos recientes', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w600)),
      ),
    ),
    SliverList.builder(
      itemCount: files.length,
      itemBuilder: (context, index) => FileRow(file: files[index]),
    ),
  ],
)
```

Comprobación: con 1.000 archivos falsos, abre la pestaña *Performance* de DevTools y haz scroll; con `Expanded` o slivers solo se construyen las filas visibles (añade un `debugPrint` en `FileRow.build` y verás unas pocas decenas, no mil).""",
            },
        ]
    },
    # 3) Flutter: go_router con login, pestañas que conservan su pila y parámetros (SISTEMA)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Estoy armando una app Flutter con login, una barra inferior con tres pestañas (Inicio, Buscar, Perfil) y detalle de producto con id en la URL. ¿Cómo lo monto con go_router para que cada pestaña conserve su pila y el login redirija bien?",
            },
            {
                "role": "assistant",
                "content": r"""Con tres piezas de go_router: `StatefulShellRoute.indexedStack` para las pestañas con pila propia, rutas anidadas para el detalle y un `redirect` global que escucha el estado de sesión con `refreshListenable`.

```dart
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

class AuthState extends ChangeNotifier {
  bool _isLoggedIn = false;
  bool get isLoggedIn => _isLoggedIn;

  void logIn() {
    _isLoggedIn = true;
    notifyListeners();
  }

  void logOut() {
    _isLoggedIn = false;
    notifyListeners();
  }
}

GoRouter createRouter(AuthState auth) {
  return GoRouter(
    initialLocation: '/home',
    refreshListenable: auth, // cada notifyListeners() reevalúa el redirect
    redirect: (context, state) {
      final goingToLogin = state.matchedLocation == '/login';
      if (!auth.isLoggedIn && !goingToLogin) {
        return '/login?from=${Uri.encodeComponent(state.uri.toString())}';
      }
      if (auth.isLoggedIn && goingToLogin) {
        final from = state.uri.queryParameters['from'];
        return (from != null && from.startsWith('/')) ? from : '/home';
      }
      return null; // sin redirección
    },
    routes: [
      GoRoute(path: '/login', builder: (context, state) => LoginScreen(auth: auth)),
      StatefulShellRoute.indexedStack(
        builder: (context, state, navigationShell) => MainShell(navigationShell: navigationShell),
        branches: [
          StatefulShellBranch(routes: [
            GoRoute(
              path: '/home',
              builder: (context, state) => const HomeScreen(),
              routes: [
                GoRoute(
                  path: 'products/:id', // /home/products/42
                  builder: (context, state) => ProductScreen(productId: state.pathParameters['id']!),
                ),
              ],
            ),
          ]),
          StatefulShellBranch(routes: [
            GoRoute(path: '/search', builder: (context, state) => const SearchScreen()),
          ]),
          StatefulShellBranch(routes: [
            GoRoute(path: '/profile', builder: (context, state) => const ProfileScreen()),
          ]),
        ],
      ),
    ],
  );
}

class MainShell extends StatelessWidget {
  const MainShell({super.key, required this.navigationShell});

  final StatefulNavigationShell navigationShell;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: navigationShell,
      bottomNavigationBar: NavigationBar(
        selectedIndex: navigationShell.currentIndex,
        // Tocar la pestaña activa vuelve a su raíz; tocar otra restaura su pila.
        onDestinationSelected: (index) => navigationShell.goBranch(
          index,
          initialLocation: index == navigationShell.currentIndex,
        ),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.home_outlined), label: 'Inicio'),
          NavigationDestination(icon: Icon(Icons.search), label: 'Buscar'),
          NavigationDestination(icon: Icon(Icons.person_outline), label: 'Perfil'),
        ],
      ),
    );
  }
}

void main() {
  final auth = AuthState();
  runApp(ShopApp(router: createRouter(auth)));
}

class ShopApp extends StatelessWidget {
  const ShopApp({super.key, required this.router});

  final GoRouter router;

  @override
  Widget build(BuildContext context) => MaterialApp.router(routerConfig: router);
}
```

`HomeScreen`, `SearchScreen`, `ProfileScreen`, `LoginScreen` y `ProductScreen` son tus pantallas normales; el login llama a `auth.logIn()` y no navega: el redirect lo hace solo.

Las decisiones que importan:

- **`indexedStack`** mantiene vivas las tres ramas en un `IndexedStack`: si entras al detalle de un producto en Inicio, cambias a Buscar y vuelves, sigues en el detalle, con su scroll.
- **El detalle es hija de `/home`**, así que se abre dentro de la rama y la barra inferior sigue visible. Si lo quieres a pantalla completa, por encima de la barra, decláralo como ruta de nivel superior con `parentNavigatorKey` apuntando al navegador raíz.
- **El router se crea una sola vez**, fuera de `build`. Crearlo dentro de un `build` lo reconstruye en cada repintado y pierde la pila de navegación.
- **`from` se valida** con `startsWith('/')` para aceptar solo rutas internas.
- **`context.go` frente a `context.push`**: `go('/home/products/42')` construye la pila que indica la URL (útil para deep links); `push` apila sobre la actual. Para un detalle dentro de la misma rama, cualquiera de los dos; para saltar entre ramas, `go`.

Comprobación: arranca sin sesión e intenta abrir `/home/products/42` con un deep link; debe mandarte al login y, tras entrar, llevarte al producto 42. Luego navega Inicio → producto → Buscar → Inicio: tienes que volver al producto, no a la lista.""",
            },
        ]
    },
    # 4) Flutter: Riverpod, watch frente a read y AsyncNotifier (system rioplatense)
    {
        "messages": [
            {"role": "system", "content": "Respondé en español rioplatense, directo y con código completo."},
            {
                "role": "user",
                "content": "Estoy con Riverpod y no termino de entender cuándo usar `ref.watch` y cuándo `ref.read`. Y quiero una lista de tareas que se cargue de una API y a la que se le puedan agregar tareas sin recargar todo.",
            },
            {
                "role": "assistant",
                "content": """La regla corta:

- **`ref.watch` en `build`** (de un widget o de un provider): te suscribe. Cuando el valor cambia, se reconstruye quien lo mira.
- **`ref.read` en callbacks** (`onPressed`, métodos del notifier): lectura puntual, sin suscripción. Usarlo en `build` «para optimizar» es un bug: el widget deja de enterarse de los cambios.
- **`ref.listen`** para efectos secundarios (mostrar un SnackBar, navegar) cuando cambia algo, sin reconstruir.

Para datos que vienen de una API y además se modifican, el patrón es un `AsyncNotifier`. Lo escribo con `flutter_riverpod` sin generación de código; la misma API sigue vigente en Riverpod 3.

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class Todo {
  const Todo({required this.id, required this.title});

  final String id;
  final String title;
}

abstract interface class TodoApi {
  Future<List<Todo>> fetchTodos();
  Future<Todo> createTodo(String title);
}

// Se inyecta en main con overrides; en los tests, con una implementación falsa.
final todoApiProvider = Provider<TodoApi>(
  (ref) => throw UnimplementedError('todoApiProvider se configura en ProviderScope'),
);

class TodosNotifier extends AsyncNotifier<List<Todo>> {
  @override
  Future<List<Todo>> build() => ref.watch(todoApiProvider).fetchTodos();

  Future<void> add(String title) async {
    final created = await ref.read(todoApiProvider).createTodo(title);
    // Leemos el estado DESPUÉS del await: pudo cambiar mientras esperábamos.
    final current = switch (state) {
      AsyncData(:final value) => value,
      _ => const <Todo>[],
    };
    state = AsyncData([...current, created]);
  }
}

final todosProvider = AsyncNotifierProvider<TodosNotifier, List<Todo>>(TodosNotifier.new);

class TodosScreen extends ConsumerWidget {
  const TodosScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final todos = ref.watch(todosProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Tareas')),
      body: todos.when(
        data: (items) => RefreshIndicator(
          onRefresh: () => ref.refresh(todosProvider.future),
          child: ListView.builder(
            itemCount: items.length,
            itemBuilder: (context, index) => ListTile(title: Text(items[index].title)),
          ),
        ),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, stackTrace) => Center(child: Text('No se pudieron cargar las tareas: $error')),
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () async {
          try {
            await ref.read(todosProvider.notifier).add('Nueva tarea');
          } on Exception catch (error) {
            if (!context.mounted) return;
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text('No se pudo agregar: $error')),
            );
          }
        },
        child: const Icon(Icons.add),
      ),
    );
  }
}

void main() {
  runApp(
    ProviderScope(
      overrides: [todoApiProvider.overrideWithValue(HttpTodoApi())], // tu implementación real
      child: const MaterialApp(home: TodosScreen()),
    ),
  );
}
```

Por qué `add` está escrito así y no con `AsyncValue.guard`:

- **Agregar no recarga la lista.** Se pide al servidor solo la tarea nueva y se añade al estado actual; la lista no pasa por `loading` ni parpadea.
- **Si falla, la lista queda como estaba.** Con `state = await AsyncValue.guard(...)`, un error al crear reemplazaría todo el estado por un `AsyncError` y la pantalla mostraría el error en lugar de las tareas. Acá la excepción sube al botón, que muestra un SnackBar, y los datos siguen en pantalla.
- **`ref.watch` en `build()` del notifier**: si mañana el `todoApiProvider` cambia (otro usuario, otra URL), la lista se recarga sola.

Comprobación: en un test, sobrescribí `todoApiProvider` con una API falsa que devuelve dos tareas y cuyo `createTodo` lanza una excepción. Tocá el botón: tienen que seguir viéndose las dos tareas y aparecer el SnackBar.""",
            },
        ]
    },
    # 5) Flutter: Cubit frente a Bloc, transformadores y BlocListener (multiturno)
    {
        "messages": [
            {
                "role": "user",
                "content": "En el equipo usamos flutter_bloc. ¿Cuándo uso Cubit y cuándo Bloc? Me parece que Bloc es mucho boilerplate para hacer lo mismo.",
            },
            {
                "role": "assistant",
                "content": """Para la mayoría de los casos tienes razón: empieza con **Cubit** y pasa a **Bloc** cuando necesites lo que solo Bloc da.

- **Cubit**: métodos que emiten estados. `cubit.toggle(id)` → `emit(nuevoEstado)`. Poco código, fácil de leer.
- **Bloc**: eventos que se transforman en estados. El valor añadido no es la ceremonia, son dos cosas concretas: **controlar la concurrencia de los eventos** (debounce, descartar, reiniciar) con transformadores, y tener un **registro de qué evento produjo qué estado**, útil para depurar flujos complejos.

Un Cubit es todo lo que necesita una lista de favoritos:

```dart
import 'package:bloc/bloc.dart';

class FavoritesCubit extends Cubit<Set<String>> {
  FavoritesCubit() : super(const {});

  void toggle(String productId) {
    final updated = {...state};
    if (!updated.remove(productId)) updated.add(productId);
    emit(updated);
  }
}
```

Una búsqueda que se dispara mientras el usuario escribe es el caso típico de Bloc: quieres esperar 300 ms de calma y, si llega otra consulta mientras la anterior está en vuelo, cancelar la vieja. Con Cubit tendrías que programar a mano el temporizador y la cancelación; con Bloc es un transformador:

```dart
import 'package:bloc/bloc.dart';
import 'package:bloc_concurrency/bloc_concurrency.dart';
import 'package:stream_transform/stream_transform.dart';

sealed class SearchEvent {}

final class QueryChanged extends SearchEvent {
  QueryChanged(this.query);
  final String query;
}

sealed class SearchState {}

final class SearchIdle extends SearchState {}

final class SearchLoading extends SearchState {}

final class SearchSuccess extends SearchState {
  SearchSuccess(this.results);
  final List<String> results;
}

final class SearchFailure extends SearchState {
  SearchFailure(this.message);
  final String message;
}

abstract interface class SearchRepository {
  Future<List<String>> search(String query);
}

// Espera a que el usuario deje de escribir y descarta la búsqueda anterior si llega otra.
EventTransformer<E> debounceRestartable<E>(Duration duration) {
  return (events, mapper) => restartable<E>().call(events.debounce(duration), mapper);
}

class SearchBloc extends Bloc<SearchEvent, SearchState> {
  SearchBloc(this._repository) : super(SearchIdle()) {
    on<QueryChanged>(
      _onQueryChanged,
      transformer: debounceRestartable(const Duration(milliseconds: 300)),
    );
  }

  final SearchRepository _repository;

  Future<void> _onQueryChanged(QueryChanged event, Emitter<SearchState> emit) async {
    final query = event.query.trim();
    if (query.isEmpty) {
      emit(SearchIdle());
      return;
    }
    emit(SearchLoading());
    try {
      emit(SearchSuccess(await _repository.search(query)));
    } on Exception catch (error) {
      emit(SearchFailure('No se pudo buscar: $error'));
    }
  }
}
```

Con `restartable`, cuando llega un evento nuevo el manejador anterior se cancela y sus `emit` posteriores se ignoran: no hay respuestas antiguas pisando a las nuevas, que es el bug clásico de las búsquedas.

Los estados como clases `sealed` hacen que un `switch` sobre ellos sea exhaustivo: si añades un estado, el compilador te señala cada sitio que no lo trata.

Regla para el equipo: Cubit por defecto; Bloc cuando la feature tenga eventos que llegan rápido o en paralelo, o cuando el flujo sea lo bastante complejo como para querer el registro de eventos.""",
            },
            {
                "role": "user",
                "content": "¿Y en la UI, BlocBuilder o BlocListener? Quiero mostrar un SnackBar cuando falla y la lista cuando hay resultados.",
            },
            {
                "role": "assistant",
                "content": """Los dos, cada uno para lo suyo:

- **`BlocBuilder`** reconstruye UI. Su `builder` debe ser una función pura del estado: puede ejecutarse muchas veces.
- **`BlocListener`** ejecuta efectos secundarios **una vez por cambio de estado**: SnackBar, navegación, diálogos. Nunca muestres un SnackBar desde un `builder`, porque cada reconstrucción lo mostraría de nuevo.

```dart
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

class SearchPage extends StatelessWidget {
  const SearchPage({super.key, required this.repository});

  final SearchRepository repository;

  @override
  Widget build(BuildContext context) {
    return BlocProvider(
      create: (_) => SearchBloc(repository),
      child: const Scaffold(body: SafeArea(child: SearchView())),
    );
  }
}

class SearchView extends StatelessWidget {
  const SearchView({super.key});

  @override
  Widget build(BuildContext context) {
    return BlocListener<SearchBloc, SearchState>(
      listenWhen: (previous, current) => current is SearchFailure,
      listener: (context, state) {
        if (state is SearchFailure) {
          ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(state.message)));
        }
      },
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(16),
            child: TextField(
              decoration: const InputDecoration(labelText: 'Buscar'),
              onChanged: (text) => context.read<SearchBloc>().add(QueryChanged(text)),
            ),
          ),
          Expanded(
            child: BlocBuilder<SearchBloc, SearchState>(
              // Un fallo no reconstruye: se siguen viendo los últimos resultados.
              buildWhen: (previous, current) => current is! SearchFailure,
              builder: (context, state) => switch (state) {
                SearchIdle() => const Center(child: Text('Escribe para buscar')),
                SearchLoading() => const Center(child: CircularProgressIndicator()),
                SearchSuccess(:final results) => ListView.builder(
                    itemCount: results.length,
                    itemBuilder: (context, index) => ListTile(title: Text(results[index])),
                  ),
                SearchFailure() => const SizedBox.shrink(),
              },
            ),
          ),
        ],
      ),
    );
  }
}
```

Detalles:

- **`buildWhen` excluye `SearchFailure`**: cuando falla, la lista conserva los resultados anteriores y el SnackBar informa. La rama `SearchFailure()` del `switch` sigue siendo necesaria porque el `switch` sobre una clase `sealed` debe ser exhaustivo.
- **`context.read` en `onChanged`** (callback), nunca `context.watch`: es la misma regla de leer en callbacks y observar en `build`.
- Si en algún sitio necesitas reconstruir **y** reaccionar al mismo estado, `BlocConsumer` combina los dos con un solo widget.

Comprobación con `bloc_test`: un `blocTest` que añada `QueryChanged('ca')`, `QueryChanged('caf')` y `QueryChanged('café')` seguidos con `wait: const Duration(milliseconds: 400)` debe esperar `[SearchLoading(), SearchSuccess(...)]` una sola vez y comprobar con un repositorio falso que `search` se llamó solo con `'café'`.""",
            },
        ]
    },
    # 6) Flutter: FutureBuilder que recarga en cada rebuild (síntoma, intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo una pantalla con FutureBuilder que llama a la API, y cada vez que se abre el teclado o cambia algo en la pantalla vuelve a mostrar el spinner y hace otra petición. En el log del backend veo como 10 llamadas por visita.",
            },
            {
                "role": "assistant",
                "content": """Casi seguro estás creando el `Future` dentro de `build`, algo como `FutureBuilder(future: api.fetchOrders(), ...)`. Ese es el error, y el síntoma encaja punto por punto:

1. Abrir el teclado cambia el `MediaQuery` (el espacio inferior), y todo lo que depende de él se reconstruye.
2. Cada `build` ejecuta `api.fetchOrders()` otra vez: una petición nueva.
3. `FutureBuilder` recibe un `Future` distinto del anterior, se desuscribe del viejo y vuelve al estado `waiting`: el spinner.

`build` puede ejecutarse decenas de veces por segundo y debe ser barato y sin efectos secundarios. El `Future` se crea **una vez**, en el estado, y `build` solo lo consume:

```dart
import 'package:flutter/material.dart';

class OrdersScreen extends StatefulWidget {
  const OrdersScreen({super.key, required this.api});

  final OrdersApi api;

  @override
  State<OrdersScreen> createState() => _OrdersScreenState();
}

class _OrdersScreenState extends State<OrdersScreen> {
  late Future<List<Order>> _ordersFuture;

  @override
  void initState() {
    super.initState();
    _ordersFuture = widget.api.fetchOrders();
  }

  void _reload() {
    setState(() {
      _ordersFuture = widget.api.fetchOrders();
    });
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<Order>>(
      future: _ordersFuture,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text('No se pudieron cargar los pedidos: ${snapshot.error}'),
                const SizedBox(height: 8),
                FilledButton(onPressed: _reload, child: const Text('Reintentar')),
              ],
            ),
          );
        }
        if (!snapshot.hasData) {
          return const Center(child: CircularProgressIndicator());
        }
        final orders = snapshot.data!;
        return ListView.builder(
          itemCount: orders.length,
          itemBuilder: (context, index) => ListTile(
            title: Text('Pedido ${orders[index].id}'),
            subtitle: Text(orders[index].statusLabel),
          ),
        );
      },
    );
  }
}
```

Tres detalles que suelen fallar en la segunda versión:

- **`setState` con llaves.** `setState(() => _ordersFuture = widget.api.fetchOrders())` parece equivalente, pero la flecha devuelve el valor de la asignación, que es un `Future`, y `setState` lanza un error si su callback devuelve un `Future`. Con llaves, el callback devuelve `void`.
- **`hasData` antes que `connectionState`.** Al reintentar, `FutureBuilder` conserva los datos anteriores mientras espera el nuevo `Future`; preguntar por `hasData` en vez de por `ConnectionState.waiting` evita volver al spinner cuando ya hay algo que mostrar.
- **Si `widget.api` puede cambiar** (otro usuario, otro entorno), sobrescribe `didUpdateWidget` y recrea el `Future` cuando `oldWidget.api != widget.api`; si no, la pantalla seguiría mostrando los datos del cliente anterior.

Si la misma lista aparece en varias pantallas o necesitas caché entre visitas, ese es el momento de pasar a Riverpod o Bloc, que guardan el resultado fuera del widget.

Comprobación: pon un contador o un `debugPrint` en `fetchOrders` y abre y cierra el teclado diez veces en esa pantalla. Debe imprimirse una sola vez por visita, y otra más por cada pulsación de Reintentar.""",
            },
        ]
    },
    # 7) Flutter: dio con interceptor de token y refresco único ante 401 concurrentes (SISTEMA, avanzado)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "En Flutter con dio necesito: añadir el token a cada petición y, si el backend responde 401, refrescar el token UNA sola vez aunque haya 5 peticiones fallando en paralelo, y reintentarlas. ¿Cómo se hace bien?",
            },
            {
                "role": "assistant",
                "content": """El requisito difícil es «una sola vez». Con un `Interceptor` normal, cinco 401 simultáneos lanzan cinco refrescos; el segundo invalida el refresh token del primero y acabas con la sesión cerrada. dio trae la pieza exacta: **`QueuedInterceptor`**, que procesa los `onError` de uno en uno. El primero refresca; los otros cuatro esperan en la cola y, cuando les toca, ven que el token guardado ya no es el que enviaron y solo reintentan.

```dart
import 'package:dio/dio.dart';

abstract interface class TokenStore {
  Future<String?> readAccessToken();
  Future<String?> readRefreshToken();
  Future<void> save({required String accessToken, required String refreshToken});
  Future<void> clear();
}

/// Añade el token y, ante un 401, refresca una sola vez aunque fallen varias peticiones a la vez.
class AuthInterceptor extends QueuedInterceptor {
  AuthInterceptor({required Dio plainDio, required TokenStore tokens})
      : _plainDio = plainDio,
        _tokens = tokens;

  /// Cliente sin interceptores: refresca y reintenta sin volver a entrar en esta cola.
  final Dio _plainDio;
  final TokenStore _tokens;

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) async {
    final token = await _tokens.readAccessToken();
    if (token != null) options.headers['Authorization'] = 'Bearer $token';
    handler.next(options);
  }

  @override
  void onError(DioException error, ErrorInterceptorHandler handler) async {
    if (error.response?.statusCode != 401) {
      handler.next(error);
      return;
    }

    final request = error.requestOptions;
    final sentHeader = request.headers['Authorization'];
    final currentToken = await _tokens.readAccessToken();

    // Si otra petición ya refrescó mientras esta esperaba en la cola,
    // el token guardado no es el que se envió: basta con reintentar.
    final alreadyRefreshed = currentToken != null && sentHeader != 'Bearer $currentToken';
    if (!alreadyRefreshed && !await _refreshTokens()) {
      await _tokens.clear(); // refresh caducado: la app debe volver al login
      handler.next(error);
      return;
    }

    try {
      final newToken = await _tokens.readAccessToken();
      request.headers['Authorization'] = 'Bearer $newToken';
      handler.resolve(await _plainDio.fetch<dynamic>(request));
    } on DioException catch (retryError) {
      handler.next(retryError);
    }
  }

  Future<bool> _refreshTokens() async {
    final refreshToken = await _tokens.readRefreshToken();
    if (refreshToken == null) return false;
    try {
      final response = await _plainDio.post<Map<String, dynamic>>(
        '/auth/refresh',
        data: {'refresh_token': refreshToken},
      );
      final body = response.data;
      if (body == null) return false;
      await _tokens.save(
        accessToken: body['access_token'] as String,
        refreshToken: body['refresh_token'] as String,
      );
      return true;
    } on DioException {
      return false; // el 401 original se propaga al llamador
    }
  }
}

Dio createApiClient(TokenStore tokens) {
  final options = BaseOptions(
    baseUrl: 'https://api.example.com',
    connectTimeout: const Duration(seconds: 5),
    receiveTimeout: const Duration(seconds: 15),
  );
  final plainDio = Dio(options);
  return Dio(options)..interceptors.add(AuthInterceptor(plainDio: plainDio, tokens: tokens));
}
```

Decisiones y por qué:

- **Reintentar con `_plainDio`, no con el cliente principal.** Si el reintento pasara por el mismo `QueuedInterceptor` y volviera a dar 401, su `onError` quedaría en la cola detrás del que lo está esperando: un interbloqueo. Con un cliente sin interceptores, el reintento no entra en la cola, y el token se pone a mano.
- **Comparar el token enviado con el guardado** es lo que convierte cinco refrescos en uno. Es más robusto que un booleano «refrescando», que habría que resetear en todos los caminos de error.
- **Si el refresco falla, se limpia la sesión y se propaga el 401.** La navegación al login no es trabajo del cliente HTTP: tu router o tu gestor de estado observa la sesión vacía y redirige.
- **Coste aceptado:** `QueuedInterceptor` también serializa los `onRequest`. Como solo leen un token del almacenamiento, el retraso es despreciable; si `readAccessToken` fuera lento, cachea el token en memoria dentro del `TokenStore`.

Para los demás errores, traduce `DioException` a errores de tu dominio en un solo sitio, mirando `error.type`: `connectionTimeout` y `receiveTimeout` (red lenta), `connectionError` (sin conexión), `badResponse` (el servidor respondió con error) y `cancel` (cancelada a propósito, no se muestra).

Comprobación: en un test, usa un `HttpClientAdapter` falso que responda 401 a cualquier petición con el token viejo y 200 con el nuevo, y que cuente las llamadas a `/auth/refresh`. Lanza cinco peticiones con `Future.wait`: las cinco deben terminar en 200 y el contador de refrescos debe valer exactamente 1.""",
            },
        ]
    },
    # 8) Flutter: formularios con Form, validadores y controladores (principiante)
    {
        "messages": [
            {
                "role": "user",
                "content": "Soy nuevo en Flutter. Tengo un formulario de registro con email y contraseña y quiero validar antes de enviar. Lo hago con un montón de if en el onPressed y queda horrible. ¿Cuál es la forma correcta?",
            },
            {
                "role": "assistant",
                "content": r"""La forma idiomática es `Form` + `TextFormField` con un `validator` por campo. El `Form` agrupa los campos y, con una `GlobalKey<FormState>`, puedes validarlos todos de una vez; cada campo pinta su propio mensaje de error debajo.

```dart
import 'package:flutter/material.dart';

final _emailPattern = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$');

// Validadores como funciones puras: se prueban sin montar ningún widget.
String? validateEmail(String? value) {
  final email = value?.trim() ?? '';
  if (email.isEmpty) return 'Escribe tu correo';
  if (!_emailPattern.hasMatch(email)) return 'El correo no parece válido';
  return null; // null significa «válido»
}

String? validatePassword(String? value) {
  if (value == null || value.length < 8) return 'Mínimo 8 caracteres';
  return null;
}

class SignUpForm extends StatefulWidget {
  const SignUpForm({super.key, required this.onSubmit});

  final Future<void> Function(String email, String password) onSubmit;

  @override
  State<SignUpForm> createState() => _SignUpFormState();
}

class _SignUpFormState extends State<SignUpForm> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _isSubmitting = false;

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return; // pinta los errores y se detiene
    setState(() {
      _isSubmitting = true;
    });
    try {
      await widget.onSubmit(_emailController.text.trim(), _passwordController.text);
    } finally {
      if (mounted) {
        setState(() {
          _isSubmitting = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Form(
      key: _formKey,
      autovalidateMode: AutovalidateMode.onUserInteraction,
      child: AutofillGroup(
        child: Column(
          children: [
            TextFormField(
              controller: _emailController,
              decoration: const InputDecoration(labelText: 'Correo'),
              keyboardType: TextInputType.emailAddress,
              textInputAction: TextInputAction.next,
              autofillHints: const [AutofillHints.email],
              validator: validateEmail,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _passwordController,
              decoration: const InputDecoration(labelText: 'Contraseña'),
              obscureText: true,
              textInputAction: TextInputAction.done,
              autofillHints: const [AutofillHints.newPassword],
              validator: validatePassword,
              onFieldSubmitted: (_) => _submit(),
            ),
            const SizedBox(height: 24),
            FilledButton(
              onPressed: _isSubmitting ? null : _submit, // null deshabilita el botón
              child: _isSubmitting
                  ? const SizedBox.square(dimension: 20, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Text('Crear cuenta'),
            ),
          ],
        ),
      ),
    );
  }
}
```

Lo que hace cada pieza:

- **`validate()`** ejecuta todos los `validator` y devuelve `true` solo si todos devuelven `null`. Sustituye a todos tus `if`.
- **`AutovalidateMode.onUserInteraction`**: un campo se valida en cuanto el usuario lo toca, no antes. Así el formulario no aparece lleno de errores en rojo al abrirse.
- **`dispose()` de los controladores**: cada `TextEditingController` reserva recursos; si no lo liberas, tienes una fuga cada vez que se abre la pantalla.
- **`textInputAction` y `autofillHints`**: «siguiente» en el teclado salta al otro campo, y el gestor de contraseñas del sistema puede rellenarlos.
- **El botón deshabilitado durante el envío** evita registros duplicados por doble toque. Si `onSubmit` lanza una excepción, sube a quien llamó (que decide cómo mostrarla) y el `finally` reactiva el botón igualmente.

Comprobación: como los validadores son funciones normales, se prueban en milisegundos:

```dart
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('validateEmail', () {
    expect(validateEmail(''), 'Escribe tu correo');
    expect(validateEmail('ana@'), 'El correo no parece válido');
    expect(validateEmail('  ana@correo.com '), isNull);
  });
}
```""",
            },
        ]
    },
    # 9) Flutter: theming Material 3, modo oscuro y ThemeExtension (inglés, intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": "How should I set up theming in a Flutter app with Material 3, light and dark modes, and a few custom brand tokens (like a 'success' color and a card radius) that don't exist in ColorScheme?",
            },
            {
                "role": "assistant",
                "content": """Three layers: a `ColorScheme` generated from your brand seed for everything Material already knows about, a `ThemeExtension` for the tokens it does not, and one function that builds both themes so light and dark can never drift apart.

```dart
import 'dart:ui' show lerpDouble;

import 'package:flutter/material.dart';

@immutable
class BrandTokens extends ThemeExtension<BrandTokens> {
  const BrandTokens({required this.success, required this.cardRadius});

  final Color success;
  final double cardRadius;

  @override
  BrandTokens copyWith({Color? success, double? cardRadius}) {
    return BrandTokens(
      success: success ?? this.success,
      cardRadius: cardRadius ?? this.cardRadius,
    );
  }

  @override
  BrandTokens lerp(ThemeExtension<BrandTokens>? other, double t) {
    if (other is! BrandTokens) return this;
    return BrandTokens(
      success: Color.lerp(success, other.success, t)!,
      cardRadius: lerpDouble(cardRadius, other.cardRadius, t)!,
    );
  }
}

const _brandSeed = Color(0xFF2E7D32);

ThemeData buildTheme(Brightness brightness) {
  final colorScheme = ColorScheme.fromSeed(seedColor: _brandSeed, brightness: brightness);
  final isLight = brightness == Brightness.light;

  return ThemeData(
    colorScheme: colorScheme, // Material 3 is the default since Flutter 3.16
    extensions: [
      BrandTokens(
        success: isLight ? const Color(0xFF1B873F) : const Color(0xFF7BD88F),
        cardRadius: 16,
      ),
    ],
    filledButtonTheme: FilledButtonThemeData(
      style: ButtonStyle(
        minimumSize: const WidgetStatePropertyAll(Size.fromHeight(48)),
        backgroundColor: WidgetStateProperty.resolveWith(
          (states) => states.contains(WidgetState.disabled)
              ? colorScheme.onSurface.withValues(alpha: 0.12)
              : colorScheme.primary,
        ),
      ),
    ),
  );
}

extension BrandThemeContext on BuildContext {
  BrandTokens get brand => Theme.of(this).extension<BrandTokens>()!;
}

class App extends StatelessWidget {
  const App({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      theme: buildTheme(Brightness.light),
      darkTheme: buildTheme(Brightness.dark),
      themeMode: ThemeMode.system,
      home: const HomeScreen(),
    );
  }
}
```

Using it in a widget:

```dart
class OrderStatusCard extends StatelessWidget {
  const OrderStatusCard({super.key, required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    final brand = context.brand;
    final textTheme = Theme.of(context).textTheme;

    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(brand.cardRadius)),
      child: ListTile(
        leading: Icon(Icons.check_circle, color: brand.success),
        title: Text(label, style: textTheme.titleMedium),
      ),
    );
  }
}
```

Why it is built this way:

- **`ColorScheme.fromSeed`** derives a full, contrast-checked palette (primary, containers, surfaces, outlines) for each brightness from one color. Hand-picking 30 roles is how dark mode ends up with unreadable combinations.
- **`ThemeExtension` instead of a global constants file**: the tokens travel with the theme, so they switch with dark mode and can be overridden for a subtree with a nested `Theme`. `lerp` matters because `MaterialApp` animates theme changes; without a real interpolation the success color would jump mid-transition.
- **`WidgetState` / `WidgetStateProperty`** are the names since Flutter 3.22; older code uses `MaterialState`, which is deprecated. Same for `withValues(alpha:)`, which replaced `withOpacity` in 3.27.
- **The extension getter uses `!`** on purpose: a missing `BrandTokens` is a setup bug and should fail loudly at the first use, not render default colors.

Verification: a widget test that forces dark mode and checks the token actually switches:

```dart
testWidgets('success color follows platform brightness', (tester) async {
  tester.platformDispatcher.platformBrightnessTestValue = Brightness.dark;
  addTearDown(tester.platformDispatcher.clearPlatformBrightnessTestValue);

  late BrandTokens tokens;
  await tester.pumpWidget(MaterialApp(
    theme: buildTheme(Brightness.light),
    darkTheme: buildTheme(Brightness.dark),
    home: Builder(builder: (context) {
      tokens = context.brand;
      return const SizedBox();
    }),
  ));

  expect(tokens.success, const Color(0xFF7BD88F));
});
```""",
            },
        ]
    },
    # 10) Flutter: estado que salta de fila sin keys (system revisor estricto, error concreto)
    {
        "messages": [
            {
                "role": "system",
                "content": "Eres un revisor de código estricto: señala el bug, su causa raíz y el arreglo mínimo, y añade un test de regresión.",
            },
            {
                "role": "user",
                "content": """Bug raro: tengo una lista de tareas donde cada fila se expande al tocarla. Si expando la primera y la borro, la segunda aparece expandida. ¿Qué pasa?

```dart
class TaskTile extends StatefulWidget {
  const TaskTile({super.key, required this.task, required this.onDelete});
  final Task task;
  final VoidCallback onDelete;

  @override
  State<TaskTile> createState() => _TaskTileState();
}

class _TaskTileState extends State<TaskTile> {
  bool _expanded = false;

  @override
  Widget build(BuildContext context) {
    return Column(children: [
      ListTile(
        title: Text(widget.task.title),
        trailing: IconButton(icon: const Icon(Icons.delete), onPressed: widget.onDelete),
        onTap: () => setState(() => _expanded = !_expanded),
      ),
      if (_expanded) Text(widget.task.notes),
    ]);
  }
}

// en el padre
ListView(
  children: [
    for (final task in tasks) TaskTile(task: task, onDelete: () => _delete(task.id)),
  ],
)
```""",
            },
            {
                "role": "assistant",
                "content": """**Bug:** el estado `_expanded` pertenece a una posición de la lista, no a una tarea.

**Causa raíz.** Al reconstruir, Flutter empareja cada widget nuevo con el elemento existente comparando **tipo y key en la misma posición**. Ninguna fila tiene key, así que la comparación es solo por tipo y orden. Al borrar la tarea A de `[A, B]`, la lista nueva es `[B]`: el widget de B cae en la posición 0, ve un `TaskTile` existente del mismo tipo y sin key, y **reutiliza su `State`**, que es el de A, con `_expanded = true`. El texto cambia (lo lee de `widget.task`), pero el estado interno se queda.

**Arreglo mínimo:** una key estable derivada de la identidad de la tarea.

```dart
TaskTile(key: ValueKey(task.id), task: task, onDelete: () => _delete(task.id))
```

Con la key, Flutter empareja por identidad: el `State` de A se desecha con A, y B conserva el suyo.

Qué key **no** usar:

- `UniqueKey()`: genera una key nueva en cada `build`, así que **todas** las filas pierden su estado en cada reconstrucción. Es peor que no poner nada.
- `ObjectKey(task)`: compara por identidad del objeto. Si tus tareas son inmutables y se recrean al editar (`task.copyWith(...)`), cada edición pierde el estado.
- El índice (`ValueKey(index)`): reproduce exactamente el bug que tienes.

Dos observaciones más de la revisión, fuera del bug pero en el mismo código:

1. **`ListView(children: [...])` construye todas las filas a la vez.** Con muchas tareas, usa `ListView.builder`, y con keys añade `findChildIndexCallback` para que al borrar o reordenar Flutter encuentre cada fila por su key en vez de reconstruir las siguientes.
2. **El estado de expansión es efímero y local**, así que `StatefulWidget` está bien. Si debe sobrevivir a salir de la pantalla, súbelo al modelo (`Set<String> expandedIds` en el padre o en tu gestor de estado) y el problema de keys desaparece de raíz.

Versión corregida del padre:

```dart
class TaskList extends StatelessWidget {
  const TaskList({super.key, required this.tasks, required this.onDelete});

  final List<Task> tasks;
  final ValueChanged<String> onDelete;

  @override
  Widget build(BuildContext context) {
    return ListView.builder(
      itemCount: tasks.length,
      itemBuilder: (context, index) {
        final task = tasks[index];
        return TaskTile(key: ValueKey(task.id), task: task, onDelete: () => onDelete(task.id));
      },
      findChildIndexCallback: (key) {
        final id = (key as ValueKey<String>).value;
        final index = tasks.indexWhere((task) => task.id == id);
        return index == -1 ? null : index;
      },
    );
  }
}
```

**Test de regresión** (falla sin la key, pasa con ella):

```dart
testWidgets('borrar una tarea no traslada su estado expandido a la siguiente', (tester) async {
  var tasks = const [
    Task(id: 'a', title: 'Comprar pan', notes: 'Integral'),
    Task(id: 'b', title: 'Llamar a Ana', notes: 'Por la tarde'),
  ];

  await tester.pumpWidget(MaterialApp(
    home: Scaffold(
      body: StatefulBuilder(
        builder: (context, setState) => TaskList(
          tasks: tasks,
          onDelete: (id) => setState(() {
            tasks = tasks.where((task) => task.id != id).toList();
          }),
        ),
      ),
    ),
  ));

  await tester.tap(find.text('Comprar pan'));
  await tester.pump();
  expect(find.text('Integral'), findsOneWidget);

  await tester.tap(find.byIcon(Icons.delete).first);
  await tester.pump();

  expect(find.text('Llamar a Ana'), findsOneWidget);
  expect(find.text('Por la tarde'), findsNothing); // sin key, aparecía expandida
});
```""",
            },
        ]
    },
    # 11) Flutter: tests de widgets con repositorio falso y navegación con go_router (multiturno)
    {
        "messages": [
            {
                "role": "user",
                "content": "¿Cómo pruebo un widget de Flutter que muestra una lista que viene de un repositorio? Nunca hice tests de widgets y no sé cómo evitar que llame a la API real.",
            },
            {
                "role": "assistant",
                "content": """La clave no está en el test sino en el diseño del widget: si recibe el repositorio desde fuera (por constructor o por tu gestor de estado), en el test le pasas uno falso y la API real nunca se toca. Asumo que `ProductListScreen` recibe `ProductRepository` por constructor, muestra un `CircularProgressIndicator` mientras carga, la lista al terminar y un mensaje con botón «Reintentar» si falla.

El repositorio falso más útil devuelve `Future`s que **tú** completas desde el test. Así controlas el momento exacto de cada estado, sin esperas reales:

```dart
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:my_shop/products/product.dart';
import 'package:my_shop/products/product_list_screen.dart';
import 'package:my_shop/products/product_repository.dart';

class FakeProductRepository implements ProductRepository {
  final List<Completer<List<Product>>> pending = [];

  @override
  Future<List<Product>> fetchProducts() {
    final completer = Completer<List<Product>>();
    pending.add(completer);
    return completer.future;
  }
}

Widget wrap(Widget child) => MaterialApp(home: child);

void main() {
  testWidgets('muestra un indicador y luego los productos', (tester) async {
    final repository = FakeProductRepository();
    await tester.pumpWidget(wrap(ProductListScreen(repository: repository)));

    expect(find.byType(CircularProgressIndicator), findsOneWidget);

    repository.pending.single.complete([const Product(id: '1', name: 'Café de Colombia')]);
    await tester.pump();

    expect(find.byType(CircularProgressIndicator), findsNothing);
    expect(find.text('Café de Colombia'), findsOneWidget);
  });

  testWidgets('si falla muestra el error y permite reintentar', (tester) async {
    final repository = FakeProductRepository();
    await tester.pumpWidget(wrap(ProductListScreen(repository: repository)));

    repository.pending.single.completeError(Exception('sin conexión'));
    await tester.pump();
    expect(find.textContaining('No se pudieron cargar'), findsOneWidget);

    await tester.tap(find.text('Reintentar'));
    await tester.pump();

    expect(repository.pending, hasLength(2)); // se lanzó una segunda petición
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
  });
}
```

Las piezas de la API de tests:

- **`pumpWidget`** monta el widget y dibuja el primer fotograma.
- **`pump()`** avanza un fotograma: procesa los `Future` completados y los `setState` pendientes. Después de completar el `Completer`, un `pump()` basta para ver la lista.
- **`find`** localiza widgets (`find.text`, `find.byType`, `find.byKey`) y los *matchers* comprueban cuántos hay: `findsOneWidget`, `findsNothing`, `findsNWidgets(3)`.
- **`tap`** simula el toque; siempre va seguido de un `pump` para ver el efecto.

La trampa de principiante: **no uses `pumpAndSettle()` mientras haya un spinner en pantalla.** `pumpAndSettle` avanza fotogramas hasta que no quede ninguna animación, y un `CircularProgressIndicator` anima para siempre: el test falla con `pumpAndSettle timed out`. Úsalo solo cuando las animaciones terminan solas (una transición de página, un `AnimatedContainer`).

Comprobación de que los tests prueban algo: rompe a propósito el widget (por ejemplo, que no muestre el spinner) y verifica que el primer test falla. Un test que nunca has visto fallar no demuestra nada.""",
            },
            {
                "role": "user",
                "content": "Perfecto, ya pasan. ¿Y cómo pruebo que al tocar un producto navega al detalle? Uso go_router.",
            },
            {
                "role": "assistant",
                "content": r"""Monta en el test un `GoRouter` con las rutas reales que intervienen y el repositorio falso, y usa `MaterialApp.router`. Asumo que la lista navega con `context.go('/products/${product.id}')` al tocar una fila.

```dart
import 'package:go_router/go_router.dart';
import 'package:my_shop/products/product_detail_screen.dart';

testWidgets('tocar un producto abre su detalle', (tester) async {
  final repository = FakeProductRepository();
  final router = GoRouter(
    initialLocation: '/products',
    routes: [
      GoRoute(
        path: '/products',
        builder: (context, state) => ProductListScreen(repository: repository),
        routes: [
          GoRoute(
            path: ':id',
            builder: (context, state) => ProductDetailScreen(productId: state.pathParameters['id']!),
          ),
        ],
      ),
    ],
  );
  addTearDown(router.dispose);

  await tester.pumpWidget(MaterialApp.router(routerConfig: router));
  repository.pending.single.complete([const Product(id: '7', name: 'Café de Colombia')]);
  await tester.pump();

  await tester.tap(find.text('Café de Colombia'));
  await tester.pump(); // empieza la transición de página
  await tester.pump(const Duration(milliseconds: 500)); // y la termina

  expect(find.byType(ProductDetailScreen), findsOneWidget);
  expect(router.routerDelegate.currentConfiguration.uri.path, '/products/7');
});
```

Por qué así:

- **Dos `pump` en lugar de `pumpAndSettle`.** La transición de página es una animación finita, pero si el detalle muestra un spinner mientras carga, `pumpAndSettle` volvería a quedarse esperando para siempre. Avanzar un tiempo fijo mayor que la transición es determinista.
- **Dos comprobaciones distintas.** `find.byType(ProductDetailScreen)` confirma qué se pinta; la URI confirma que el parámetro llegó bien a la ruta. Un bug típico es navegar a `/products/null` y que el detalle se muestre igualmente con un error dentro.
- **Rutas mínimas, pero reales.** No hace falta montar el router completo de la app; sí que las rutas del test tengan la misma forma que las de producción. Si las defines en una función compartida (`productRoutes(repository)`), el test usa exactamente las mismas.

Si el detalle también carga datos, dale su repositorio falso en el `builder` de la ruta y aplica el mismo patrón del `Completer`.""",
            },
        ]
    },
    # 12) Flutter: tirones en el scroll de un feed; medir en profile y atacar UI o raster (España)
    {
        "messages": [
            {
                "role": "user",
                "content": "Nuestra app Flutter va a tirones al hacer scroll en el feed (fotos grandes y texto). En el emulador y en debug es horrible. ¿Por dónde empiezo a mirar?",
            },
            {
                "role": "assistant",
                "content": """Por medir bien, porque lo que ves ahora no sirve como dato: en modo debug Flutter compila con JIT, ejecuta aserciones y desactiva optimizaciones, y el emulador añade su propia lentitud. Una app que va a tirones en debug puede ir fluida en release.

**1. Medir en las condiciones correctas.**

```bash
flutter run --profile   # en un móvil real, a ser posible de gama media
```

El modo *profile* tiene el rendimiento de release y conserva las herramientas de análisis. Abre DevTools → *Performance* y haz scroll en el feed. Cada barra es un fotograma; las rojas superan el presupuesto (16 ms a 60 Hz, 8 ms a 120 Hz). Lo importante es **en qué hilo** se va el tiempo:

- **Hilo UI** (tu código Dart: `build` y layout): demasiado trabajo al construir.
- **Hilo raster** (pintar en la GPU): lo que se dibuja es caro.

**2. Si el lento es el hilo UI**, por orden de frecuencia:

- **Lista no perezosa.** `ListView(children: posts.map(...).toList())` construye todos los posts al abrir. `ListView.builder` construye solo los visibles.
- **Trabajo pesado en `build`.** Formatear fechas, parsear JSON u ordenar listas dentro de `build` se repite en cada fotograma de una animación. Prepara esos datos al cargarlos, no al pintarlos.
- **`setState` demasiado arriba.** Un `setState` en la pantalla por un «me gusta» reconstruye el feed entero. Baja el estado al widget que cambia (el botón con su propio estado) o usa un selector de tu gestor de estado.
- **Faltan `const`.** Un widget `const` se reutiliza tal cual y Flutter se salta su reconstrucción. Activa la regla `prefer_const_constructors` del linter y deja que te los marque.

**3. Si el lento es el hilo raster:**

- **Imágenes decodificadas a tamaño completo.** Una foto de 4000 × 3000 ocupa 48 MB en memoria (4 bytes por píxel) aunque se muestre a 400 px de ancho, y decodificarla cuesta. Es la causa más frecuente en feeds:

```dart
import 'package:flutter/material.dart';

class FeedImage extends StatelessWidget {
  const FeedImage({super.key, required this.url});

  final String url;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final pixelRatio = MediaQuery.devicePixelRatioOf(context);
        return Image.network(
          url,
          // Decodifica al tamaño en pantalla, no al original.
          cacheWidth: (constraints.maxWidth * pixelRatio).round(),
          fit: BoxFit.cover,
          errorBuilder: (context, error, stackTrace) => const ColoredBox(color: Colors.black12),
        );
      },
    );
  }
}
```

Con `cached_network_image`, el equivalente es `memCacheWidth`. Y si controlas el backend, sirve miniaturas del tamaño adecuado: es la mejora más grande de todas, porque además ahorra datos.

- **`Opacity` y recortes en cada fila** pueden forzar capas intermedias costosas. Para animar la opacidad usa `FadeTransition` o `AnimatedOpacity`, y recorta solo la imagen que lo necesita, no la tarjeta entera.

**4. Verificar cada cambio** con la misma traza: mismo dispositivo, modo *profile* y mismo gesto de scroll, comparando el número de fotogramas rojos. Haz un cambio cada vez; si mejoran dos cosas a la vez, no sabrás cuál importaba. La pestaña *Memory* de DevTools confirma el arreglo de las imágenes: tras recorrer el feed, el consumo debe bajar de cientos de MB a unas decenas.""",
            },
        ]
    },
    # 13) React Native: Expo Router básico con pestañas y ruta dinámica (México, principiante)
    {
        "messages": [
            {
                "role": "user",
                "content": "Vengo de web con Next y estoy empezando con Expo. ¿Cómo funciona Expo Router? Necesito pestañas abajo (Inicio y Ajustes) y una pantalla de detalle de pedido que reciba el id.",
            },
            {
                "role": "assistant",
                "content": r"""Te va a resultar familiar: Expo Router es enrutado por archivos, como el App Router de Next. Cada archivo dentro de `app/` es una pantalla, `_layout.tsx` define el navegador que envuelve a sus hermanos, y los corchetes marcan segmentos dinámicos. La estructura para lo que pides:

```
app/
  _layout.tsx          ← Stack raíz
  (tabs)/
    _layout.tsx        ← barra de pestañas
    index.tsx          ← Inicio  (ruta "/")
    settings.tsx       ← Ajustes (ruta "/settings")
  orders/
    [id].tsx           ← detalle (ruta "/orders/1042")
```

Los paréntesis de `(tabs)` crean un **grupo**: organiza archivos y comparte layout, pero no aparece en la URL.

```tsx
// app/_layout.tsx
import { Stack } from "expo-router";

export default function RootLayout() {
  return (
    <Stack>
      <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
      <Stack.Screen name="orders/[id]" options={{ title: "Pedido" }} />
    </Stack>
  );
}
```

```tsx
// app/(tabs)/_layout.tsx
import Ionicons from "@expo/vector-icons/Ionicons";
import { Tabs } from "expo-router";

export default function TabsLayout() {
  return (
    <Tabs>
      <Tabs.Screen
        name="index"
        options={{
          title: "Inicio",
          tabBarIcon: ({ color, size }) => <Ionicons name="home-outline" color={color} size={size} />,
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          title: "Ajustes",
          tabBarIcon: ({ color, size }) => <Ionicons name="settings-outline" color={color} size={size} />,
        }}
      />
    </Tabs>
  );
}
```

```tsx
// app/(tabs)/index.tsx
import { Link } from "expo-router";
import { FlatList, Pressable, Text } from "react-native";

const orders = [
  { id: "1042", total: "$350.00" },
  { id: "1043", total: "$129.50" },
];

export default function HomeScreen() {
  return (
    <FlatList
      data={orders}
      keyExtractor={(order) => order.id}
      renderItem={({ item }) => (
        <Link href={{ pathname: "/orders/[id]", params: { id: item.id } }} asChild>
          <Pressable style={{ padding: 16 }}>
            <Text>Pedido #{item.id} · {item.total}</Text>
          </Pressable>
        </Link>
      )}
    />
  );
}
```

```tsx
// app/orders/[id].tsx
import { Stack, useLocalSearchParams } from "expo-router";
import { Text, View } from "react-native";

export default function OrderScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();

  return (
    <View style={{ padding: 16 }}>
      <Stack.Screen options={{ title: `Pedido #${id}` }} />
      <Text>Detalle del pedido {id}</Text>
    </View>
  );
}
```

Diferencias con Next que conviene tener claras desde ahorita:

- **El layout elige el tipo de navegación.** `Stack` apila pantallas con la animación nativa y el gesto de volver; `Tabs` pinta la barra inferior. En web solo había páginas; aquí cada layout decide cómo se transita.
- **El detalle está fuera de `(tabs)`**, a propósito: así se abre encima de la barra de pestañas, a pantalla completa. Si lo metieras dentro de `(tabs)`, aparecería como una pestaña más.
- **`asChild` en `Link`** pasa la navegación al `Pressable`; sin él, `Link` renderiza su propio `Text`.
- **`useLocalSearchParams`** devuelve los parámetros de esta pantalla. Llegan como cadenas: si el id es numérico, conviértelo y valídalo.
- **No hay componentes de servidor.** Todo corre en el dispositivo; los datos se piden con `fetch` o una librería como TanStack Query.

Comprobación: `npx expo start`, abre la app, toca un pedido y verifica que el título dice «Pedido #1042» y que el gesto de volver regresa a Inicio. Los deep links salen gratis: con el `scheme` definido en `app.json` (por ejemplo `"scheme": "mitienda"`), `npx uri-scheme open mitienda://orders/1042 --ios` abre directamente el detalle.""",
            },
        ]
    },
    # 14) Expo Router: rutas protegidas con Redirect, SecureStore y 401 desde el cliente HTTP (SISTEMA, multiturno)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "En Expo Router, ¿cómo protejo las pantallas para que sin sesión mande al login? Lo intenté con un useEffect que hace `router.replace('/login')` en el layout raíz y a veces me sale `Attempted to navigate before mounting the Root Layout component`.",
            },
            {
                "role": "assistant",
                "content": """Ese error dice exactamente qué pasa: tu efecto navega antes de que el layout raíz haya montado un navegador (`Slot`, `Stack` o `Tabs`). Si en el primer render el layout raíz devuelve un spinner o `null` mientras lee la sesión, no hay navegador al que pedirle nada.

El patrón que lo evita tiene dos reglas:

1. **El layout raíz siempre renderiza un navegador**, desde el primer render.
2. **La protección es declarativa**: el layout del grupo protegido devuelve `<Redirect>` cuando no hay sesión. No hay navegación imperativa ni efectos.

```
app/
  _layout.tsx        ← SessionProvider + Slot (siempre)
  login.tsx          ← pública
  (app)/
    _layout.tsx      ← sin sesión → <Redirect href="/login" />
    index.tsx        ← protegida (ruta "/")
```

```tsx
// src/session.tsx
import * as SecureStore from "expo-secure-store";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

const TOKEN_KEY = "session-token";

type SessionValue = {
  token: string | null;
  isLoading: boolean;
  signIn: (token: string) => Promise<void>;
  signOut: () => Promise<void>;
};

const SessionContext = createContext<SessionValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    SecureStore.getItemAsync(TOKEN_KEY)
      .then(setToken)
      .catch((error: unknown) => console.warn("No se pudo leer la sesión guardada", error))
      .finally(() => setIsLoading(false));
  }, []);

  const signIn = useCallback(async (newToken: string) => {
    await SecureStore.setItemAsync(TOKEN_KEY, newToken);
    setToken(newToken);
  }, []);

  const signOut = useCallback(async () => {
    await SecureStore.deleteItemAsync(TOKEN_KEY);
    setToken(null);
  }, []);

  const value = useMemo(
    () => ({ token, isLoading, signIn, signOut }),
    [token, isLoading, signIn, signOut],
  );
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession debe usarse dentro de <SessionProvider>");
  return value;
}
```

```tsx
// app/_layout.tsx
import { Slot } from "expo-router";
import { SessionProvider } from "@/src/session";

export default function RootLayout() {
  return (
    <SessionProvider>
      <Slot />
    </SessionProvider>
  );
}
```

```tsx
// app/(app)/_layout.tsx
import { Redirect, Stack } from "expo-router";
import { ActivityIndicator, View } from "react-native";
import { useSession } from "@/src/session";

export default function ProtectedLayout() {
  const { token, isLoading } = useSession();

  if (isLoading) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center" }}>
        <ActivityIndicator />
      </View>
    );
  }
  if (!token) return <Redirect href="/login" />;
  return <Stack />;
}
```

En `login.tsx`, tras un login correcto: `await signIn(token); router.replace("/");`. Uso `replace` y no `push` para que el botón de volver no regrese al login.

Por qué cada decisión:

- **`expo-secure-store` y no AsyncStorage** para el token: SecureStore usa el Keychain de iOS y el Keystore de Android; AsyncStorage guarda texto plano accesible en un dispositivo comprometido.
- **El estado de carga vive en el grupo protegido**, no en la raíz. La raíz monta el navegador al instante y el error desaparece.
- **El cierre de sesión no navega.** `signOut()` pone el token a `null`, el layout protegido se vuelve a renderizar y devuelve `<Redirect>`. La navegación es consecuencia del estado, así que no puede desincronizarse.

Las versiones recientes de Expo Router añaden además rutas protegidas declarativas (`Stack.Protected` con una condición `guard`); el patrón con `Redirect` funciona igual en todas las versiones.

Comprobación: arranca sin token y abre la app: debes ver el login sin el error en consola. Inicia sesión, cierra la app por completo y vuelve a abrirla: debe entrar directamente. Llama a `signOut()` desde Ajustes: debe volver al login sin código de navegación adicional.""",
            },
            {
                "role": "user",
                "content": "Y si el token expira con la app abierta y la API devuelve 401, ¿cómo lo mando al login desde mi cliente de fetch, que está fuera de los componentes?",
            },
            {
                "role": "assistant",
                "content": r"""No lo mandes al login desde el cliente: haz que el cliente avise de que la sesión murió y deja que el estado haga el resto. El cliente HTTP no debe conocer el router; solo necesita dos funciones inyectadas: cómo obtener el token y qué hacer ante un 401.

```ts
// src/api.ts
export class UnauthorizedError extends Error {
  constructor() {
    super("La sesión expiró");
    this.name = "UnauthorizedError";
  }
}

export type ApiRequest = <T>(path: string, init?: RequestInit) => Promise<T>;

type ApiClientOptions = {
  baseUrl: string;
  getToken: () => string | null;
  onUnauthorized: () => void;
};

export function createApiClient({ baseUrl, getToken, onUnauthorized }: ApiClientOptions): ApiRequest {
  return async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    const token = getToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);

    const response = await fetch(`${baseUrl}${path}`, { ...init, headers });
    if (response.status === 401) {
      onUnauthorized();
      throw new UnauthorizedError();
    }
    if (!response.ok) throw new Error(`HTTP ${response.status} en ${path}`);
    return (await response.json()) as T;
  };
}
```

El `SessionProvider` crea el cliente y lo expone en el contexto. Cambia respecto a la versión anterior en tres puntos: un `ref` con el token para que el cliente lea siempre el valor actual sin recrearse, el `request` creado una sola vez, y el valor del contexto ampliado:

```tsx
// src/session.tsx (SessionProvider ampliado)
import * as SecureStore from "expo-secure-store";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { createApiClient, type ApiRequest } from "@/src/api";

const TOKEN_KEY = "session-token";

type SessionValue = {
  token: string | null;
  isLoading: boolean;
  signIn: (token: string) => Promise<void>;
  signOut: () => Promise<void>;
  request: ApiRequest;
};

const SessionContext = createContext<SessionValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const tokenRef = useRef<string | null>(null);

  const applyToken = useCallback((next: string | null) => {
    tokenRef.current = next; // el cliente lo lee al instante, sin esperar al re-render
    setToken(next);
  }, []);

  useEffect(() => {
    SecureStore.getItemAsync(TOKEN_KEY)
      .then(applyToken)
      .catch((error: unknown) => console.warn("No se pudo leer la sesión guardada", error))
      .finally(() => setIsLoading(false));
  }, [applyToken]);

  const signIn = useCallback(async (newToken: string) => {
    await SecureStore.setItemAsync(TOKEN_KEY, newToken);
    applyToken(newToken);
  }, [applyToken]);

  const signOut = useCallback(async () => {
    await SecureStore.deleteItemAsync(TOKEN_KEY);
    applyToken(null);
  }, [applyToken]);

  const request = useMemo(
    () =>
      createApiClient({
        baseUrl: process.env.EXPO_PUBLIC_API_URL ?? "",
        getToken: () => tokenRef.current,
        onUnauthorized: () => {
          void signOut();
        },
      }),
    [signOut],
  );

  const value = useMemo(
    () => ({ token, isLoading, signIn, signOut, request }),
    [token, isLoading, signIn, signOut, request],
  );
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession debe usarse dentro de <SessionProvider>");
  return value;
}
```

Uso en cualquier pantalla: `const { request } = useSession();` y luego `await request<Order[]>("/orders")`, o como `queryFn` de TanStack Query.

Qué pasa ante un 401, paso a paso: el cliente llama a `onUnauthorized` → `signOut()` borra el token → el layout de `(app)` se re-renderiza con `token === null` → devuelve `<Redirect href="/login" />`. El cliente además lanza `UnauthorizedError`, para que la pantalla que hizo la petición no intente pintar datos que no llegaron.

Dos detalles:

- **Varios 401 a la vez** (cinco peticiones en paralelo) llaman cinco veces a `signOut`. Es idempotente (borrar una clave inexistente no falla y poner `null` dos veces no cambia nada), así que no hace falta coordinarlos.
- **`EXPO_PUBLIC_API_URL`** se incrusta en el bundle al compilar: sirve para URLs, nunca para secretos.

Comprobación: con la app abierta, invalida el token en el servidor (o haz que tu API de pruebas responda 401) y refresca una pantalla protegida: la app debe ir al login sola, y en consola solo debe aparecer el `UnauthorizedError` de esa petición.""",
            },
        ]
    },
    # 15) React Native: separar estado de servidor (TanStack Query) y de cliente (Zustand) (Colombia)
    {
        "messages": [
            {
                "role": "user",
                "content": "Tenemos una app con Expo donde todo vive en un Context gigante: usuario, carrito, filtros y los datos del servidor (productos, pedidos). Cada cambio re-renderiza media app y se siente pesada. ¿Cómo lo partimos?",
            },
            {
                "role": "assistant",
                "content": r"""Ese Context mezcla dos tipos de estado que tienen necesidades opuestas, y el re-render masivo es la consecuencia directa: cuando cambia cualquier campo del valor del Context, **todos** los componentes que lo consumen se vuelven a renderizar, aunque solo lean el usuario.

Pártanlo por tipo de estado:

| Tipo | Ejemplos | Herramienta |
|---|---|---|
| Estado del servidor | productos, pedidos | TanStack Query: caché, reintentos, refresco, deduplicación |
| Estado del cliente | carrito, preferencias | Zustand: store pequeño con selectores |
| Estado de navegación | filtros de una lista | parámetros de la ruta (Expo Router) |
| Sesión | usuario, token | un Context pequeño que cambia muy poco |

**Datos del servidor con TanStack Query.** Dejan de copiarlos a un estado propio: la caché es la fuente de verdad.

```tsx
// app/_layout.tsx
import { QueryClient, QueryClientProvider, focusManager } from "@tanstack/react-query";
import { Stack } from "expo-router";
import { useEffect } from "react";
import { AppState, Platform, type AppStateStatus } from "react-native";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 2 } },
});

// En móvil no existe el evento de foco de la ventana: se lo damos desde AppState.
function onAppStateChange(status: AppStateStatus) {
  if (Platform.OS !== "web") focusManager.setFocused(status === "active");
}

export default function RootLayout() {
  useEffect(() => {
    const subscription = AppState.addEventListener("change", onAppStateChange);
    return () => subscription.remove();
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <Stack />
    </QueryClientProvider>
  );
}
```

```ts
// src/api/products.ts
import { useQuery } from "@tanstack/react-query";

export type Product = { id: string; name: string; price: number };

async function fetchProducts(category: string): Promise<Product[]> {
  const url = `${process.env.EXPO_PUBLIC_API_URL}/products?category=${encodeURIComponent(category)}`;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return (await response.json()) as Product[];
}

export function useProducts(category: string) {
  return useQuery({
    queryKey: ["products", category],
    queryFn: () => fetchProducts(category),
  });
}
```

**Carrito con Zustand**, persistido para que sobreviva a cerrar la app:

```ts
// src/stores/cart.ts
import AsyncStorage from "@react-native-async-storage/async-storage";
import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

type CartItem = { productId: string; quantity: number };

type CartState = {
  items: CartItem[];
  add: (productId: string) => void;
  remove: (productId: string) => void;
  clear: () => void;
};

export const useCartStore = create<CartState>()(
  persist(
    (set) => ({
      items: [],
      add: (productId) =>
        set((state) => {
          const exists = state.items.some((item) => item.productId === productId);
          return {
            items: exists
              ? state.items.map((item) =>
                  item.productId === productId ? { ...item, quantity: item.quantity + 1 } : item,
                )
              : [...state.items, { productId, quantity: 1 }],
          };
        }),
      remove: (productId) =>
        set((state) => ({ items: state.items.filter((item) => item.productId !== productId) })),
      clear: () => set({ items: [] }),
    }),
    { name: "cart", storage: createJSONStorage(() => AsyncStorage) },
  ),
);
```

Lo que elimina los re-renders son los **selectores**: cada componente se suscribe solo a lo que lee.

```tsx
import { Pressable, Text } from "react-native";
import { useShallow } from "zustand/react/shallow";
import { useCartStore } from "@/src/stores/cart";

// Se re-renderiza solo cuando cambia el número total, no con cualquier cambio del carrito.
export function CartBadge() {
  const count = useCartStore((state) => state.items.reduce((total, item) => total + item.quantity, 0));
  return <Text>{count}</Text>;
}

// Las acciones son estables: este botón no se re-renderiza al cambiar el carrito.
export function AddToCartButton({ productId }: { productId: string }) {
  const add = useCartStore((state) => state.add);
  return (
    <Pressable accessibilityRole="button" onPress={() => add(productId)}>
      <Text>Agregar</Text>
    </Pressable>
  );
}

// Si un selector devuelve un objeto nuevo, useShallow compara por campos y evita renders de más.
export function CartSummary() {
  const { items, clear } = useCartStore(useShallow((state) => ({ items: state.items, clear: state.clear })));
  return (
    <Pressable accessibilityRole="button" onPress={clear}>
      <Text>Vaciar carrito ({items.length})</Text>
    </Pressable>
  );
}
```

La trampa típica: un selector que devuelve un objeto o array **nuevo** en cada llamada (`(state) => ({ items: state.items, clear: state.clear })`) sin `useShallow` hace que Zustand vea un valor distinto cada vez; en Zustand 5 termina en un bucle de renders. Con `useShallow`, se comparan los campos uno a uno.

**Filtros en la ruta**: `useLocalSearchParams` para leerlos y `router.setParams({ category })` para cambiarlos. Así sobreviven al volver atrás y se pueden compartir como deep link.

Migración sin romper nada: muevan primero una consulta (productos) a TanStack Query, luego el carrito a Zustand, y por último dejen en el Context solo la sesión. Comprobación en cada paso: en React DevTools activen *Highlight updates when components render* y agreguen un producto al carrito; solo deben destellar el badge y el resumen, no la lista de productos.""",
            },
        ]
    },
    # 16) React Native: FlatList lenta con 2.000 mensajes, optimizar antes de FlashList (intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": "Tengo un FlatList con unos 2.000 mensajes de chat y en Android de gama media se queda en blanco al hacer scroll rápido y va lento. ¿Me paso a FlashList o hay algo que arreglar antes?",
            },
            {
                "role": "assistant",
                "content": """Arregla antes lo básico; muchas veces basta. Y si no basta, FlashList rinde mejor sobre una lista bien hecha que sobre una mal hecha.

**Qué significan los huecos en blanco.** `FlatList` renderiza por ventanas: monta las filas cercanas a la zona visible en el hilo de JavaScript y desmonta las lejanas. Si el scroll va más rápido de lo que el hilo JS tarda en renderizar filas, el hilo nativo muestra la zona sin contenido todavía: blanco. Es decir, el cuello de botella es el **hilo JS**. Confírmalo con el *Perf Monitor* (menú de desarrollo → *Perf Monitor*): si los FPS de JS caen a un dígito mientras los de UI siguen altos, es esto.

**1. Lo que suele estar mal**, en este orden:

```tsx
import { memo, useCallback } from "react";
import { FlatList, StyleSheet, Text, View, type ListRenderItem } from "react-native";

type Message = { id: string; author: string; text: string; sentAtLabel: string };

// memo: la fila solo se re-renderiza si cambia SU mensaje, no cuando llega otro.
const MessageRow = memo(function MessageRow({ message }: { message: Message }) {
  return (
    <View style={styles.row}>
      <Text style={styles.author}>{message.author}</Text>
      <Text>{message.text}</Text>
      <Text style={styles.time}>{message.sentAtLabel}</Text>
    </View>
  );
});

export function MessageList({ messages }: { messages: Message[] }) {
  // renderItem estable: si se recrea en cada render, memo no sirve de nada.
  const renderItem = useCallback<ListRenderItem<Message>>(
    ({ item }) => <MessageRow message={item} />,
    [],
  );

  return (
    <FlatList
      data={messages}               // ordenados del más nuevo al más viejo
      inverted                      // el más nuevo abajo, como en cualquier chat
      keyExtractor={(message) => message.id}
      renderItem={renderItem}
      initialNumToRender={15}
      maxToRenderPerBatch={10}
      windowSize={11}               // ~5 pantallas por arriba y por abajo, en vez de 21
      removeClippedSubviews         // en Android libera las vistas fuera de pantalla
    />
  );
}

const styles = StyleSheet.create({
  row: { paddingHorizontal: 16, paddingVertical: 8 },
  author: { fontWeight: "600", marginBottom: 2 },
  time: { fontSize: 12, color: "#666", marginTop: 2 },
});
```

Puntos que más pesan:

- **`keyExtractor` con un id estable.** Sin él, o con el índice, React no puede reutilizar filas y remonta de más.
- **Fila con `memo` y `renderItem` estable.** Cuando llega un mensaje nuevo, sin esto se re-renderizan las 30 filas montadas; con esto, una.
- **Nada caro dentro de la fila.** Formatear fechas con `Intl` o calcular cosas en cada render se multiplica por cada fila; precalcula `sentAtLabel` al recibir el mensaje.
- **`windowSize` más pequeño** reduce el trabajo por scroll a cambio de más riesgo de blanco en flings muy rápidos. Ajústalo midiendo.
- **Si todas las filas midieran lo mismo**, `getItemLayout` le ahorraría a la lista medirlas. En un chat las alturas varían, así que no aplica.

**2. Mide en release**, no en desarrollo: el modo desarrollo de React Native es varias veces más lento. `npx expo run:android --variant release` en el dispositivo de gama media.

**3. Si después sigue sin dar la talla, FlashList.** La diferencia de fondo: en vez de montar y desmontar filas, **recicla** las vistas que salen de pantalla para las que entran, con lo que el hilo JS trabaja mucho menos en scroll rápido.

```tsx
import { FlashList } from "@shopify/flash-list";

<FlashList
  data={messages}
  inverted
  keyExtractor={(message) => message.id}
  renderItem={renderItem}
  estimatedItemSize={64}
/>
```

Eso es FlashList 1.x, que necesita `estimatedItemSize` (la altura media aproximada). FlashList 2 ya no lo pide, pero exige la nueva arquitectura de React Native y cambia algunas props; si estás en una versión reciente de Expo con la nueva arquitectura activa, revisa su guía de migración antes de copiar ejemplos de la v1.

La trampa del reciclaje: **no guardes estado local en la fila** (`useState` para «expandido», por ejemplo). Al reciclarse, esa vista pasa a mostrar otro mensaje y arrastra el estado del anterior. Ese estado va en el padre, indexado por id.

Comprobación: misma prueba antes y después, en release: un fling fuerte desde abajo hasta arriba del historial. Cuenta los huecos en blanco y mira los FPS de JS en el Perf Monitor.""",
            },
        ]
    },
    # 17) React Native: swipe para descartar con Reanimated y Gesture Handler (avanzado)
    {
        "messages": [
            {
                "role": "user",
                "content": "Quiero una tarjeta que se arrastre horizontalmente y que, si la suelto pasado un umbral, salga volando y se elimine (swipe para descartar). Con la API Animated de React Native me va a tirones cuando la lista está cargando datos. ¿Cómo se hace con Reanimated?",
            },
            {
                "role": "assistant",
                "content": r"""Los tirones vienen de que el gesto pasa por el hilo de JavaScript: cada movimiento del dedo es un evento que JS tiene que procesar, y si JS está ocupado cargando datos, la tarjeta se congela. Reanimated junto con Gesture Handler ejecutan tanto el gesto como la animación en el **hilo de UI**, en funciones llamadas *worklets*, así que el hilo JS puede estar bloqueado y la tarjeta sigue al dedo.

Código para Reanimated 3 y Gesture Handler 2:

```tsx
import { StyleSheet, Text, useWindowDimensions } from "react-native";
import { Gesture, GestureDetector } from "react-native-gesture-handler";
import Animated, {
  interpolate,
  runOnJS,
  useAnimatedStyle,
  useSharedValue,
  withSpring,
  withTiming,
} from "react-native-reanimated";

const DISMISS_DISTANCE_RATIO = 0.35; // fracción del ancho de pantalla
const DISMISS_VELOCITY = 1000;       // px/s: un lanzamiento rápido descarta aunque sea corto

type SwipeCardProps = { title: string; onDismiss: () => void };

export function SwipeCard({ title, onDismiss }: SwipeCardProps) {
  const { width } = useWindowDimensions();
  const translateX = useSharedValue(0);
  const threshold = width * DISMISS_DISTANCE_RATIO;

  const pan = Gesture.Pan()
    .activeOffsetX([-10, 10]) // solo se activa con movimiento horizontal: no roba el scroll vertical
    .onUpdate((event) => {
      translateX.value = event.translationX;
    })
    .onEnd((event) => {
      const shouldDismiss =
        Math.abs(event.translationX) > threshold || Math.abs(event.velocityX) > DISMISS_VELOCITY;
      if (!shouldDismiss) {
        translateX.value = withSpring(0);
        return;
      }
      const direction = Math.sign(event.translationX) || 1;
      translateX.value = withTiming(direction * width * 1.2, { duration: 200 }, (finished) => {
        // Este callback corre en el hilo de UI; onDismiss es JS normal: hay que cruzar de hilo.
        if (finished) runOnJS(onDismiss)();
      });
    });

  const animatedStyle = useAnimatedStyle(() => ({
    transform: [
      { translateX: translateX.value },
      { rotate: `${interpolate(translateX.value, [-width, 0, width], [-12, 0, 12])}deg` },
    ],
    opacity: interpolate(Math.abs(translateX.value), [0, width], [1, 0.3]),
  }));

  return (
    <GestureDetector gesture={pan}>
      <Animated.View style={[styles.card, animatedStyle]}>
        <Text style={styles.title}>{title}</Text>
      </Animated.View>
    </GestureDetector>
  );
}

const styles = StyleSheet.create({
  card: {
    marginHorizontal: 16,
    marginVertical: 8,
    padding: 20,
    borderRadius: 16,
    backgroundColor: "white",
    elevation: 2,
    shadowColor: "#000",
    shadowOpacity: 0.1,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 2 },
  },
  title: { fontSize: 16, fontWeight: "600" },
});
```

Las piezas y por qué:

- **`useSharedValue`** es un valor que vive en el hilo de UI. Cambiarlo no provoca un render de React; solo actualiza el estilo animado.
- **Los callbacks del gesto (`onUpdate`, `onEnd`) se convierten en worklets** automáticamente con el plugin de Babel de Reanimated (Expo lo configura solo). Por eso pueden leer y escribir `translateX.value` sin pasar por JS.
- **`runOnJS(onDismiss)()`**: el callback de `withTiming` corre en UI, y `onDismiss` (que actualiza estado de React) tiene que ejecutarse en JS. Llamarlo directamente desde un worklet hace que la app se cierre con un error.
- **El umbral combina distancia y velocidad**: un lanzamiento rápido y corto también descarta, que es como se comportan las apps nativas.
- **`activeOffsetX`** evita conflictos con un `FlatList` vertical: el gesto no se activa hasta que el dedo se mueve 10 px en horizontal.

Requisito de montaje: la raíz de la app debe estar envuelta en `GestureHandlerRootView` (en Expo Router, en `app/_layout.tsx`, con `style={{ flex: 1 }}`); sin él, los gestos no responden.

Si estás en Reanimated 4 (requiere la nueva arquitectura), el código es casi igual, pero las utilidades para cambiar de hilo se movieron al paquete `react-native-worklets`; revisa su guía de migración para el sustituto de `runOnJS`.

Comprobación del motivo del cambio: añade temporalmente un botón que bloquee el hilo JS dos segundos (`const end = Date.now() + 2000; while (Date.now() < end) {}`), púlsalo y arrastra la tarjeta enseguida. Con Reanimated, la tarjeta sigue al dedo y vuelve a su sitio con el muelle; solo la eliminación de la lista espera a que JS se libere.""",
            },
        ]
    },
    # 18) Expo: EAS Build, perfiles y EAS Update (SISTEMA, multiturno, principiante-intermedio)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Es la primera vez que voy a publicar una app de Expo en las tiendas. ¿Qué es eso de EAS Build, development build, perfiles...? Hasta ahora hice todo con Expo Go.",
            },
            {
                "role": "assistant",
                "content": """Expo Go te sirvió para aprender, pero no es tu app: es una app de Expo, ya compilada, con un conjunto fijo de módulos nativos, que carga tu JavaScript. Para publicar necesitas **tu propio binario**, y EAS Build lo compila en la nube por ti, sin necesidad de un Mac para iOS.

Los tres tipos de build que vas a usar:

| Build | Para qué | Quién lo instala |
|---|---|---|
| **development** | desarrollar con tus librerías nativas; recarga en caliente como Expo Go | tú y tu equipo |
| **preview** | probar algo idéntico a producción antes de publicar | testers internos |
| **production** | subir a App Store y Google Play | los usuarios, vía tiendas |

**Pasos:**

```bash
npm install -g eas-cli
eas login
eas build:configure          # crea eas.json y vincula el proyecto
```

```json
{
  "cli": { "version": ">= 12.0.0", "appVersionSource": "remote" },
  "build": {
    "development": {
      "developmentClient": true,
      "distribution": "internal"
    },
    "preview": {
      "distribution": "internal",
      "android": { "buildType": "apk" }
    },
    "production": {
      "autoIncrement": true
    }
  },
  "submit": {
    "production": {}
  }
}
```

En `app.json`, los identificadores que las tiendas usan para siempre (elígelos bien, no se pueden cambiar después de publicar):

```json
{
  "expo": {
    "name": "Mi Tienda",
    "slug": "mi-tienda",
    "version": "1.0.0",
    "ios": { "bundleIdentifier": "com.mitienda.app" },
    "android": { "package": "com.mitienda.app" }
  }
}
```

```bash
eas build --profile preview --platform android      # APK para probar en tu móvil
eas build --profile production --platform all       # binarios para las tiendas
eas submit --platform ios                           # sube el último build a App Store Connect
eas submit --platform android                       # y a Google Play Console
```

Qué hace cada opción de `eas.json`:

- **`developmentClient: true`** incluye `expo-dev-client`: el build se comporta como Expo Go pero con *tus* módulos nativos.
- **`distribution: "internal"`** genera binarios instalables directamente (APK, o builds de iOS para dispositivos registrados), sin pasar por la tienda.
- **`appVersionSource: "remote"` + `autoIncrement`**: EAS lleva la cuenta del número de build (`versionCode` en Android, `buildNumber` en iOS) y lo sube solo; las tiendas rechazan un número repetido.
- **Credenciales**: EAS genera y guarda el keystore de Android y los certificados de iOS. Pierde el keystore de Android y no podrás actualizar la app nunca más; dejar que EAS lo custodie evita ese desastre.

Requisitos que no dependen de Expo: cuenta de Apple Developer (99 USD al año) y de Google Play Console (25 USD, pago único).

Un aviso importante sobre variables de entorno: las que empiezan por `EXPO_PUBLIC_` se incrustan en el bundle y cualquiera puede leerlas descompilando la app. Sirven para URLs públicas, nunca para claves secretas, que deben quedarse en tu backend. Las variables por entorno (desarrollo, preview, producción) se configuran en el panel de expo.dev o con `eas env:create`.

Comprobación: instala el APK del perfil preview en un Android real y recorre los flujos principales. Es exactamente el código que irá a producción, así que lo que falle ahí (permisos, URLs de producción, iconos) fallaría en la tienda.""",
            },
            {
                "role": "user",
                "content": "¿Y si después de publicar encuentro un bug pequeño? ¿Tengo que pasar otra vez por la revisión de Apple?",
            },
            {
                "role": "assistant",
                "content": """Depende de dónde esté el bug. Si está solo en JavaScript o en assets (imágenes, textos), no: **EAS Update** publica el bundle nuevo y las apps instaladas lo descargan sin pasar por la tienda. Si el arreglo toca código nativo, sí necesitas un build nuevo y revisión.

**Lo que se puede actualizar por aire y lo que no:**

| Cambio | EAS Update | Build nuevo |
|---|---|---|
| Lógica en JS/TS, estilos, textos, imágenes | sí | no |
| Añadir una librería con código nativo | no | sí |
| Permisos, `app.json` nativo (iconos, splash, scheme) | no | sí |
| Subir de versión del SDK de Expo | no | sí |

**Configuración, una sola vez:**

```bash
npx expo install expo-updates
eas update:configure
```

Esto añade a `app.json` la URL de actualizaciones y una **runtime version**, que es la pieza clave: identifica qué parte nativa necesita un bundle. Un update solo se entrega a binarios con la misma runtime version, así que nunca llegará JS que llame a un módulo nativo que ese binario no tiene.

```json
{
  "expo": {
    "runtimeVersion": { "policy": "appVersion" }
  }
}
```

Con `appVersion`, la runtime version es la `version` de `app.json`. La regla operativa: **cada vez que hagas un cambio nativo, sube `version`** y haz build nuevo. La política `fingerprint` lo calcula sola a partir del código nativo y evita olvidos, a cambio de ser menos predecible al leerla.

Luego asocia cada perfil de `eas.json` a un canal, para que los testers y los usuarios reciban updates distintos:

```json
{
  "build": {
    "preview": { "distribution": "internal", "channel": "preview" },
    "production": { "autoIncrement": true, "channel": "production" }
  }
}
```

Los canales se graban en el binario al compilar, así que hay que hacer un build nuevo después de añadirlos.

**Publicar un arreglo:**

```bash
eas update --channel preview --message "Corrige el total del carrito con descuentos"
# probado en preview:
eas update --channel production --message "Corrige el total del carrito con descuentos"
```

Por defecto, la app descarga el update al abrirse y lo aplica en el **siguiente** arranque. Si un update sale mal, `eas update:republish` vuelve a publicar un grupo anterior en el canal.

Sobre Apple: sus normas permiten actualizar código interpretado (JavaScript) siempre que no cambie el propósito principal de la app ni añada funciones que debieran revisarse. Arreglar bugs entra de lleno; lanzar una funcionalidad grande por aire es arriesgado.

Comprobación del flujo completo antes de necesitarlo de verdad: con un build preview instalado, cambia un texto visible, publica en el canal `preview`, abre la app, ciérrala y vuelve a abrirla. En el segundo arranque debe verse el texto nuevo.""",
            },
        ]
    },
    # 19) Expo Go: TurboModule no encontrado con librería nativa (error concreto)
    {
        "messages": [
            {
                "role": "user",
                "content": """Instalé con npm una librería de escáner de códigos de barras para React Native, y en Expo Go la app se cae al abrir la pantalla:

```
Invariant Violation: TurboModuleRegistry.getEnforcing(...): 'BarcodeScanner' could not be found. Verify that a module by this name is registered in the native binary.
```

En el emulador con Expo Go pasa lo mismo. ¿La librería está rota?""",
            },
            {
                "role": "assistant",
                "content": """No está rota: el mensaje lo dice literalmente, *registered in the native binary*. La librería tiene una parte en JavaScript (que `npm install` sí trajo) y una parte nativa en Swift/Kotlin que tiene que estar **compilada dentro de la app**. Expo Go es una app ya compilada por Expo, con un conjunto fijo de módulos nativos (los del SDK de Expo); tu librería no está dentro, así que cuando el JS pide el módulo nativo `BarcodeScanner`, no existe.

Tienes dos caminos.

**Camino 1: usar el módulo del SDK de Expo, que ya está en Expo Go.** Para leer códigos de barras, `expo-camera` lo trae incorporado:

```bash
npx expo install expo-camera
```

```tsx
import { CameraView, useCameraPermissions } from "expo-camera";
import { useState } from "react";
import { Button, StyleSheet, Text, View } from "react-native";

export default function ScannerScreen() {
  const [permission, requestPermission] = useCameraPermissions();
  const [scannedCode, setScannedCode] = useState<string | null>(null);

  if (!permission) {
    return <View style={styles.center} />; // aún se está consultando el estado del permiso
  }

  if (!permission.granted) {
    return (
      <View style={styles.center}>
        <Text style={styles.message}>Necesitamos la cámara para leer el código.</Text>
        <Button title="Dar permiso" onPress={requestPermission} />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <CameraView
        style={StyleSheet.absoluteFill}
        facing="back"
        barcodeScannerSettings={{ barcodeTypes: ["ean13", "qr"] }}
        // undefined detiene la lectura: evita disparar el callback 30 veces por segundo
        onBarcodeScanned={scannedCode ? undefined : ({ data }) => setScannedCode(data)}
      />
      {scannedCode && (
        <View style={styles.result}>
          <Text style={styles.message}>Código: {scannedCode}</Text>
          <Button title="Escanear otro" onPress={() => setScannedCode(null)} />
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: 24 },
  message: { fontSize: 16, marginBottom: 12, textAlign: "center" },
  result: { position: "absolute", bottom: 40, left: 20, right: 20, padding: 16, borderRadius: 12, backgroundColor: "white" },
});
```

Y el texto del permiso de iOS, en `app.json`:

```json
{
  "expo": {
    "plugins": [
      ["expo-camera", { "cameraPermission": "Usamos la cámara para leer códigos de barras." }]
    ]
  }
}
```

**Camino 2: seguir con tu librería y crear un *development build*.** Es tu propia versión de «Expo Go» con tus módulos nativos dentro:

```bash
npx expo install expo-dev-client
npx expo run:android            # compila en local (necesita Android Studio); en iOS, run:ios con Xcode
# o en la nube, sin herramientas locales:
eas build --profile development --platform android
```

Instalas ese build en el dispositivo y `npx expo start` se conecta a él igual que antes a Expo Go. Si la librería necesita permisos o configuración nativa, revisa si trae un *config plugin* para declararlo en `app.json`.

Mi recomendación: si `expo-camera` cubre los formatos que necesitas, camino 1, porque sigues pudiendo usar Expo Go y no añades una dependencia nativa más que mantener. El camino 2 es inevitable en cuanto uses cualquier librería nativa fuera del SDK, así que tarde o temprano conviene tenerlo montado.

Para no volver a tropezar: antes de instalar una librería, búscala en reactnative.directory, que indica si funciona en Expo Go o necesita un development build.

Comprobación: con el camino 1, abre la pantalla en Expo Go, concede el permiso y apunta a un código EAN-13 de cualquier producto; debe mostrarse el número, y no debe volver a dispararse hasta pulsar «Escanear otro».""",
            },
        ]
    },
    # 20) React Native: pantalla con cabecera, carrusel y lista paginada sin anidar listas (intermedio)
    {
        "messages": [
            {
                "role": "user",
                "content": "Necesito una pantalla de inicio con un banner arriba, un carrusel horizontal de categorías y debajo una lista larga de productos que se carga paginada. Lo metí todo dentro de un ScrollView y la consola me tira un warning de que las VirtualizedLists no deberían ir dentro de ScrollViews. ¿Cómo se estructura bien?",
            },
            {
                "role": "assistant",
                "content": r"""El warning señala un problema real, no estético: un `FlatList` vertical dentro de un `ScrollView` vertical no sabe qué parte de él es visible (el que hace scroll es el `ScrollView`), así que renderiza **todos** sus elementos. Pierdes la virtualización, que es la razón de usar `FlatList`, y con cientos de productos la pantalla se vuelve lenta y consume mucha memoria.

La estructura correcta invierte la relación: **la lista larga es el contenedor de scroll de la pantalla**, y el banner y el carrusel van en su cabecera (`ListHeaderComponent`). El carrusel puede ser otro `FlatList`, porque es horizontal: listas anidadas con distinta orientación no tienen el problema.

```tsx
import { useInfiniteQuery } from "@tanstack/react-query";
import { ActivityIndicator, Button, FlatList, Image, StyleSheet, Text, View } from "react-native";

type Product = { id: string; name: string; price: number };
type Category = { id: string; name: string };
type ProductPage = { items: Product[]; nextCursor: string | null };

const CATEGORIES: Category[] = [
  { id: "coffee", name: "Café" },
  { id: "tea", name: "Té" },
  { id: "snacks", name: "Snacks" },
  { id: "gifts", name: "Regalos" },
];

async function fetchProductPage(cursor: string | null): Promise<ProductPage> {
  const query = cursor ? `?limit=20&cursor=${encodeURIComponent(cursor)}` : "?limit=20";
  const response = await fetch(`${process.env.EXPO_PUBLIC_API_URL}/products${query}`);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return (await response.json()) as ProductPage;
}

// Componente estable: si se definiera en línea dentro de HomeScreen,
// se remontaría en cada render y el carrusel perdería su posición de scroll.
function HomeHeader() {
  return (
    <View>
      <Image source={{ uri: "https://cdn.example.com/banner-otono.jpg" }} style={styles.banner} accessibilityLabel="Promoción de otoño" />
      <FlatList
        horizontal
        data={CATEGORIES}
        keyExtractor={(category) => category.id}
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.categories}
        renderItem={({ item }) => <Text style={styles.chip}>{item.name}</Text>}
      />
    </View>
  );
}

function ProductRow({ product }: { product: Product }) {
  return (
    <View style={styles.row}>
      <Text style={styles.name}>{product.name}</Text>
      <Text>${product.price.toFixed(2)}</Text>
    </View>
  );
}

export default function HomeScreen() {
  const query = useInfiniteQuery({
    queryKey: ["products"],
    queryFn: ({ pageParam }) => fetchProductPage(pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) => lastPage.nextCursor,
  });

  const products = query.data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <FlatList
      data={products}
      keyExtractor={(product) => product.id}
      renderItem={({ item }) => <ProductRow product={item} />}
      ListHeaderComponent={HomeHeader}
      ListEmptyComponent={
        query.isPending ? (
          <ActivityIndicator style={styles.footer} />
        ) : query.isError ? (
          <View style={styles.footer}>
            <Text>No se pudieron cargar los productos.</Text>
            <Button title="Reintentar" onPress={() => void query.refetch()} />
          </View>
        ) : null
      }
      onEndReached={() => {
        if (query.hasNextPage && !query.isFetchingNextPage) void query.fetchNextPage();
      }}
      onEndReachedThreshold={0.5}
      ListFooterComponent={query.isFetchingNextPage ? <ActivityIndicator style={styles.footer} /> : null}
      refreshing={query.isRefetching}
      onRefresh={() => void query.refetch()}
    />
  );
}

const styles = StyleSheet.create({
  banner: { width: "100%", aspectRatio: 16 / 9 },
  categories: { gap: 8, paddingHorizontal: 16, paddingVertical: 12 },
  chip: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 999, backgroundColor: "#eee" },
  row: { flexDirection: "row", justifyContent: "space-between", paddingHorizontal: 16, paddingVertical: 12 },
  name: { fontWeight: "500" },
  footer: { padding: 24, alignItems: "center" },
});
```

Por qué cada pieza:

- **`ListHeaderComponent` recibe el componente, no una función en línea.** Pasar `() => <View>...</View>` crea un componente nuevo en cada render y React desmonta y vuelve a montar la cabecera entera.
- **La guarda en `onEndReached`.** El evento puede dispararse varias veces seguidas cerca del final; sin comprobar `hasNextPage` e `isFetchingNextPage`, pedirías la misma página dos veces.
- **`onEndReachedThreshold={0.5}`**: pide la siguiente página cuando falta media pantalla para el final, así el usuario casi nunca ve el spinner del pie.
- **Paginación por cursor** en lugar de por número de página: si entran productos nuevos mientras el usuario hace scroll, con `page=2` verías duplicados; el cursor continúa exactamente donde quedó.
- **La query se arma a mano** en vez de con `URLSearchParams`, cuya implementación en React Native ha sido incompleta según la versión.

Comprobación: el warning desaparece de la consola; con un `console.log` en `ProductRow`, al abrir la pantalla deben renderizarse solo las filas visibles más un margen, no todas; y haciendo scroll hasta el final, la pestaña de red debe mostrar una petición por página, sin duplicados.""",
            },
        ]
    },
    # 21) React Native: formulario de login con react-hook-form, zod y teclado (system variante)
    {
        "messages": [
            {
                "role": "system",
                "content": "Responde con el código necesario y comentarios breves; la explicación, en no más de cinco viñetas al final.",
            },
            {
                "role": "user",
                "content": "Formulario de login en React Native con react-hook-form y zod: email y contraseña, que el teclado no tape los campos, que «siguiente» en el teclado pase al otro campo y que el botón muestre que está cargando.",
            },
            {
                "role": "assistant",
                "content": """```tsx
import { zodResolver } from "@hookform/resolvers/zod";
import { useRef } from "react";
import { Controller, useForm } from "react-hook-form";
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
} from "react-native";
import { z } from "zod";

const loginSchema = z.object({
  email: z.string().trim().email("Correo no válido"),
  password: z.string().min(8, "Mínimo 8 caracteres"),
});

export type LoginValues = z.infer<typeof loginSchema>;

type LoginScreenProps = { onLogin: (values: LoginValues) => Promise<void> };

export function LoginScreen({ onLogin }: LoginScreenProps) {
  const passwordRef = useRef<TextInput>(null);
  const {
    control,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
    mode: "onTouched", // valida al salir de cada campo, no en cada tecla desde el inicio
  });

  const submit = handleSubmit(async (values) => {
    try {
      await onLogin(values);
    } catch (error) {
      // el error del servidor se muestra en el formulario, no se pierde
      setError("root", { message: error instanceof Error ? error.message : "No se pudo iniciar sesión" });
    }
  });

  return (
    // iOS no redimensiona la vista con el teclado; Android sí (adjustResize en Expo)
    <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
        <Text style={styles.label}>Correo</Text>
        <Controller
          control={control}
          name="email"
          render={({ field: { onChange, onBlur, value } }) => (
            <TextInput
              style={[styles.input, errors.email && styles.inputError]}
              value={value}
              onChangeText={onChange}
              onBlur={onBlur}
              accessibilityLabel="Correo"
              autoCapitalize="none"
              autoComplete="email"
              keyboardType="email-address"
              textContentType="emailAddress"
              returnKeyType="next"
              submitBehavior="submit" // pasa al siguiente campo sin cerrar el teclado
              onSubmitEditing={() => passwordRef.current?.focus()}
            />
          )}
        />
        {errors.email && <Text style={styles.error}>{errors.email.message}</Text>}

        <Text style={styles.label}>Contraseña</Text>
        <Controller
          control={control}
          name="password"
          render={({ field: { onChange, onBlur, value } }) => (
            <TextInput
              ref={passwordRef}
              style={[styles.input, errors.password && styles.inputError]}
              value={value}
              onChangeText={onChange}
              onBlur={onBlur}
              accessibilityLabel="Contraseña"
              secureTextEntry
              autoComplete="current-password"
              textContentType="password"
              returnKeyType="go"
              onSubmitEditing={() => void submit()}
            />
          )}
        />
        {errors.password && <Text style={styles.error}>{errors.password.message}</Text>}

        {errors.root && (
          <Text style={styles.error} accessibilityLiveRegion="polite">
            {errors.root.message}
          </Text>
        )}

        <Pressable
          style={[styles.button, isSubmitting && styles.buttonDisabled]}
          onPress={() => void submit()}
          disabled={isSubmitting} // evita el doble envío
          accessibilityRole="button"
          accessibilityState={{ disabled: isSubmitting, busy: isSubmitting }}
        >
          {isSubmitting ? <ActivityIndicator color="white" /> : <Text style={styles.buttonText}>Entrar</Text>}
        </Pressable>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  container: { flexGrow: 1, justifyContent: "center", padding: 24, gap: 4 },
  label: { fontWeight: "600", marginTop: 12 },
  input: { borderWidth: 1, borderColor: "#999", borderRadius: 8, paddingHorizontal: 12, paddingVertical: 10, fontSize: 16 },
  inputError: { borderColor: "#b91c1c" },
  error: { color: "#b91c1c", fontSize: 13 },
  button: { marginTop: 24, height: 48, borderRadius: 8, backgroundColor: "#1d4ed8", alignItems: "center", justifyContent: "center" },
  buttonDisabled: { opacity: 0.6 },
  buttonText: { color: "white", fontSize: 16, fontWeight: "600" },
});
```

- **`Controller`** conecta cada `TextInput` (que no es un input HTML) con react-hook-form; zod valida y tipa en un solo sitio con `z.infer`.
- **`KeyboardAvoidingView` + `ScrollView`** resuelven el teclado en pantallas pequeñas; `keyboardShouldPersistTaps="handled"` hace que el primer toque en el botón lo pulse en vez de solo cerrar el teclado. Para formularios largos, `react-native-keyboard-controller` da un control más fino.
- **`submitBehavior="submit"`** sustituye al antiguo `blurOnSubmit={false}` (deprecado) y mantiene el teclado abierto al saltar de campo.
- **`autoComplete` y `textContentType`** activan el autorrelleno de contraseñas de iOS y Android.
- Comprobación: toca «Entrar» con los campos vacíos (deben salir ambos errores), escribe un correo y pulsa «siguiente» (el foco pasa a la contraseña), y con un `onLogin` que tarde 2 s el botón debe mostrar el indicador e ignorar un segundo toque.""",
            },
        ]
    },
    # 22) React Native: tests de componentes con jest-expo y Testing Library (inglés)
    {
        "messages": [
            {
                "role": "user",
                "content": "How do I set up component tests in an Expo app? I want to test a screen that fetches data with TanStack Query, without hitting the network.",
            },
            {
                "role": "assistant",
                "content": """Use the `jest-expo` preset with React Native Testing Library, mock the data-fetching module at its boundary, and give every test its own `QueryClient`.

**Setup:**

```bash
npx expo install jest-expo jest @types/jest --dev
npx expo install @testing-library/react-native --dev
```

```json
{
  "scripts": { "test": "jest" },
  "jest": { "preset": "jest-expo" }
}
```

`jest-expo` configures Babel, mocks Expo's native modules and sets up the React Native environment, so you do not maintain any of that yourself.

**The screen under test** keeps network code in its own module, which is what makes it mockable:

```ts
// src/products/api.ts
export type Product = { id: string; name: string };

export async function fetchProducts(): Promise<Product[]> {
  const response = await fetch(`${process.env.EXPO_PUBLIC_API_URL}/products`);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return (await response.json()) as Product[];
}
```

```tsx
// src/products/ProductsScreen.tsx
import { useQuery } from "@tanstack/react-query";
import { FlatList, Pressable, Text, View } from "react-native";
import { fetchProducts } from "./api";

export function ProductsScreen() {
  const { data, isPending, isError, refetch } = useQuery({ queryKey: ["products"], queryFn: fetchProducts });

  if (isPending) return <Text>Loading…</Text>;
  if (isError) {
    return (
      <View>
        <Text>Could not load products</Text>
        <Pressable accessibilityRole="button" onPress={() => void refetch()}>
          <Text>Retry</Text>
        </Pressable>
      </View>
    );
  }
  return <FlatList data={data} keyExtractor={(product) => product.id} renderItem={({ item }) => <Text>{item.name}</Text>} />;
}
```

**The tests:**

```tsx
// src/products/ProductsScreen.test.tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, userEvent } from "@testing-library/react-native";
import type { ReactNode } from "react";
import { fetchProducts } from "./api";
import { ProductsScreen } from "./ProductsScreen";

jest.mock("./api");
const mockedFetchProducts = jest.mocked(fetchProducts);

function renderWithClient(ui: ReactNode) {
  // A fresh client per test: no cache leaks between tests, no retries slowing failures down.
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

afterEach(() => {
  jest.resetAllMocks();
});

test("shows products once they load", async () => {
  mockedFetchProducts.mockResolvedValue([{ id: "1", name: "Cold brew" }]);

  renderWithClient(<ProductsScreen />);

  expect(screen.getByText("Loading…")).toBeOnTheScreen();
  expect(await screen.findByText("Cold brew")).toBeOnTheScreen();
});

test("recovers after a failed request when the user retries", async () => {
  mockedFetchProducts
    .mockRejectedValueOnce(new Error("offline"))
    .mockResolvedValueOnce([{ id: "1", name: "Cold brew" }]);
  const user = userEvent.setup();

  renderWithClient(<ProductsScreen />);
  await user.press(await screen.findByRole("button", { name: "Retry" }));

  expect(await screen.findByText("Cold brew")).toBeOnTheScreen();
  expect(mockedFetchProducts).toHaveBeenCalledTimes(2);
});
```

Why each choice:

- **Mock the module, not `fetch`.** `jest.mock("./api")` replaces exactly the boundary the screen depends on, and `jest.mocked` keeps the mock typed. Mocking global `fetch` couples the tests to URLs and response shapes that belong to the API module's own tests.
- **`retry: false`.** TanStack Query retries three times with backoff by default; an error test would wait several seconds and could time out.
- **`find*` queries for anything async.** `findByText` waits (and retries) until the element appears; `getByText` right after render only sees the loading state. Reaching for `waitFor` plus `getBy*` is the same thing, written longer.
- **`findByRole("button", { name: "Retry" })`** queries the way a screen reader sees the UI. If someone drops `accessibilityRole`, the test fails, which is a feature.
- **`toBeOnTheScreen`** ships with React Native Testing Library 12.4+; older setups needed `@testing-library/jest-native`.

Verification that the tests protect something: change the button text to "Try again" or remove the `isError` branch, and the second test must fail. Then restore it.""",
            },
        ]
    },
    # 23) SwiftUI: @State y @Binding entre padre e hija (principiante)
    {
        "messages": [
            {
                "role": "user",
                "content": "Empiezo con SwiftUI. Tengo una vista padre con un texto que depende de si las notificaciones están activas, y el Toggle está en una vista hija. Cuando lo cambio en la hija, el padre no se entera. A la hija le paso el Bool y dentro le puse `@State var isOn: Bool` para que el Toggle compilara.",
            },
            {
                "role": "assistant",
                "content": """El problema está justo en ese `@State` de la hija. Un `Bool` en Swift es un **tipo de valor**: al pasarlo, la hija recibe una copia, y `@State` convierte esa copia en estado **propio** de la hija. El Toggle modifica el estado de la hija; el del padre nunca se toca.

Lo que necesitas es una **binding**: una referencia de lectura y escritura al estado de otra vista. Las dos piezas:

- **`@State`** en la vista **dueña** del dato. SwiftUI guarda el valor fuera de la estructura de la vista (las vistas se recrean constantemente) y vuelve a dibujar cuando cambia.
- **`@Binding`** en la vista que lo **usa sin ser su dueña**. No guarda nada: lee y escribe en el `@State` del padre.

```swift
import SwiftUI

struct SettingsView: View {
    @State private var notificationsEnabled = false

    var body: some View {
        Form {
            NotificationsRow(isOn: $notificationsEnabled)
            Text(notificationsEnabled ? "Te avisaremos de cada pedido" : "No recibirás avisos")
                .foregroundStyle(.secondary)
        }
    }
}

struct NotificationsRow: View {
    @Binding var isOn: Bool

    var body: some View {
        Toggle("Notificaciones", isOn: $isOn)
    }
}

#Preview {
    SettingsView()
}

#Preview("Fila suelta") {
    NotificationsRow(isOn: .constant(true))
}
```

El `$` convierte el estado en binding: `notificationsEnabled` es el `Bool`; `$notificationsEnabled` es la `Binding<Bool>` que apunta a él. Dentro de la hija pasa igual: `isOn` lee el valor y `$isOn` es la binding que necesita el `Toggle`.

Tres reglas que evitan los errores típicos:

1. **`@State` siempre `private`.** Pertenece a esa vista. Si otra vista necesita el dato, se lo pasas como valor (solo lectura) o como binding (lectura y escritura).
2. **Un `@State` inicializado desde fuera solo toma el valor la primera vez.** Si el padre luego pasa otro valor, se ignora. Es la segunda cara de tu bug: aunque el padre cambiara, la hija seguiría mostrando su copia. Si el dato viene del padre, es un `let` (solo lectura) o un `@Binding`, nunca un `@State`.
3. **En la preview de la hija, `.constant(true)`** crea una binding fija. Sirve para ver la vista; la interacción se prueba en la preview del padre.

Comprobación: en la preview de `SettingsView`, pulsa el Toggle y el texto de debajo debe cambiar al instante. Con tu versión, el Toggle se movía pero el texto se quedaba fijo, que es la firma de «dos copias del mismo dato».""",
            },
        ]
    },
    # 24) SwiftUI: migrar de ObservableObject a @Observable en iOS 17 (SISTEMA, intermedio-avanzado)
    {
        "messages": [
            {"role": "system", "content": SISTEMA},
            {
                "role": "user",
                "content": "Tengo una app SwiftUI con `ObservableObject`, `@Published`, `@StateObject` y `@ObservedObject` por todas partes. Ahora el mínimo es iOS 17. ¿Me conviene pasar a `@Observable`? ¿Qué cambia exactamente?",
            },
            {
                "role": "assistant",
                "content": """Sí, si el mínimo ya es iOS 17. Y no es solo menos código: cambia **qué** se vuelve a dibujar.

**Qué cambia por dentro.** Con `ObservableObject`, cualquier `@Published` que cambie dispara `objectWillChange`, y **todas** las vistas que observan el objeto se invalidan, lean o no esa propiedad. Con `@Observable` (framework Observation), SwiftUI registra qué propiedades lee cada `body` y solo redibuja las vistas que leyeron la propiedad que cambió. En una pantalla con un modelo grande, la diferencia se nota.

**Equivalencias:**

| Antes (Combine) | Ahora (Observation) |
|---|---|
| `class Model: ObservableObject` | `@Observable final class Model` |
| `@Published var name = ""` | `var name = ""` |
| `@StateObject private var model = Model()` | `@State private var model = Model()` |
| `@ObservedObject var model: Model` | `var model: Model`, o `@Bindable var model: Model` si necesitas `$model.name` |
| `@EnvironmentObject var model: Model` | `@Environment(Model.self) private var model` |
| `.environmentObject(model)` | `.environment(model)` |

Ejemplo migrado completo:

```swift
import Observation
import SwiftUI

protocol ProfileAPI: Sendable {
    func updateProfile(name: String, bio: String) async throws
}

@MainActor
@Observable
final class ProfileModel {
    var name = ""
    var bio = ""
    private(set) var isSaving = false

    @ObservationIgnored private let api: ProfileAPI

    init(api: ProfileAPI) {
        self.api = api
    }

    func save() async throws {
        isSaving = true
        defer { isSaving = false }
        try await api.updateProfile(name: name, bio: bio)
    }
}

struct ProfileScreen: View {
    @State private var model: ProfileModel

    init(api: ProfileAPI) {
        _model = State(initialValue: ProfileModel(api: api))
    }

    var body: some View {
        ProfileForm(model: model)
    }
}

struct ProfileForm: View {
    @Bindable var model: ProfileModel
    @State private var errorMessage: String?

    var body: some View {
        Form {
            TextField("Nombre", text: $model.name)
            TextField("Biografía", text: $model.bio, axis: .vertical)
            Button("Guardar") {
                Task {
                    do {
                        try await model.save()
                        errorMessage = nil
                    } catch {
                        errorMessage = error.localizedDescription
                    }
                }
            }
            .disabled(model.isSaving)
            if let errorMessage {
                Text(errorMessage).foregroundStyle(.red)
            }
        }
    }
}
```

Lo que conviene saber antes de migrar en masa:

- **`@Bindable` solo donde hay bindings.** Una vista que solo lee el modelo lo recibe como `var model: ProfileModel` a secas y se actualiza igual; `@Bindable` hace falta únicamente para escribir `$model.name`.
- **`@State` con un objeto no se comporta igual que `@StateObject`.** `@StateObject` recibía el inicializador como *autoclosure* y lo ejecutaba una sola vez. `@State` conserva una sola instancia, pero la expresión que lo inicializa se evalúa cada vez que el padre recrea la estructura de la vista, y las instancias sobrantes se descartan. Si el `init` de tu modelo hace trabajo (abrir conexiones, lanzar peticiones), muévelo a un método que llames desde `.task`.
- **`@ObservationIgnored`** para propiedades que no deben provocar redibujos: dependencias, cachés, formateadores.
- **`@MainActor` en los modelos de UI**: todas sus mutaciones ocurren en el hilo principal y el compilador lo verifica, en lugar de descubrirlo en ejecución con el aviso morado.
- **Se puede migrar por partes**: un objeto `@Observable` y otro `ObservableObject` conviven en la misma app sin problema. Empieza por los modelos más leídos.

Comprobación de la ganancia: añade `let _ = Self._printChanges()` al principio del `body` de dos vistas que lean propiedades distintas del mismo modelo. Con `ObservableObject`, escribir en el nombre imprime las dos; con `@Observable`, solo la que lee `name`.""",
            },
        ]
    },
    # 25) SwiftUI: NavigationStack programático y deep links (usuario en inglés pide español, multiturno)
    {
        "messages": [
            {
                "role": "user",
                "content": "In SwiftUI, how do I do programmatic navigation with NavigationStack? I need to push a product detail after a search and pop back to root after checkout. Please answer in Spanish, my team in Madrid will read it.",
            },
            {
                "role": "assistant",
                "content": """Con navegación basada en **valores**: la pila es un array que tú controlas, y cada valor se traduce en una pantalla mediante `navigationDestination(for:)`. Navegar es modificar el array: `append` para avanzar y `removeAll()` para volver a la raíz.

```swift
import SwiftUI

struct Product: Hashable, Identifiable {
    let id: UUID
    let name: String
}

enum Route: Hashable {
    case product(Product)
    case checkout
}

@MainActor
@Observable
final class Router {
    var path: [Route] = []

    func show(_ route: Route) { path.append(route) }
    func popToRoot() { path.removeAll() }
}

struct ShopRootView: View {
    @State private var router = Router()

    var body: some View {
        NavigationStack(path: $router.path) {
            SearchView()
                .navigationDestination(for: Route.self) { route in
                    switch route {
                    case .product(let product):
                        ProductDetailView(product: product)
                    case .checkout:
                        CheckoutView()
                    }
                }
        }
        .environment(router)
    }
}

struct SearchView: View {
    @Environment(Router.self) private var router
    @State private var query = ""

    private static let catalog = [
        Product(id: UUID(), name: "Cafetera italiana"),
        Product(id: UUID(), name: "Molinillo manual"),
    ]

    private var results: [Product] {
        Self.catalog.filter { query.isEmpty || $0.name.localizedCaseInsensitiveContains(query) }
    }

    var body: some View {
        List(results) { product in
            NavigationLink(value: Route.product(product)) {
                Text(product.name)
            }
        }
        .searchable(text: $query)
        .onSubmit(of: .search) {
            // Navegación programática: con un único resultado, se abre directamente.
            if results.count == 1, let product = results.first {
                router.show(.product(product))
            }
        }
        .navigationTitle("Buscar")
    }
}

struct ProductDetailView: View {
    @Environment(Router.self) private var router
    let product: Product

    var body: some View {
        VStack(spacing: 16) {
            Text(product.name).font(.title)
            Button("Comprar") { router.show(.checkout) }
                .buttonStyle(.borderedProminent)
        }
        .navigationTitle("Producto")
    }
}

struct CheckoutView: View {
    @Environment(Router.self) private var router

    var body: some View {
        Button("Confirmar pago") {
            router.popToRoot() // tras pagar, de vuelta a la búsqueda de un salto
        }
        .navigationTitle("Pago")
    }
}
```

Por qué así:

- **`[Route]` en lugar de `NavigationPath`.** `NavigationPath` admite valores de tipos distintos, pero es opaco: no puedes inspeccionar qué contiene. Con un enum tienes una pila tipada que se lee, se compara en tests y se puede guardar.
- **El `Router` va al entorno**, así que cualquier pantalla de la pila navega sin recibir closures nivel a nivel.
- **`navigationDestination` se declara una vez, cerca de la raíz y fuera de contenedores perezosos.** Dentro de un `List` o un `LazyVStack`, SwiftUI no lo encuentra cuando la fila no está cargada, avisa en consola y la navegación falla de forma intermitente.
- **`NavigationLink(value:)` y `router.show(...)` son la misma operación**: añadir un valor a `path`. Por eso conviven sin conflicto.

Comprobación: busca «cafetera» y pulsa Intro; debe abrirse el detalle. Pulsa Comprar y luego Confirmar pago: tienes que volver a la búsqueda de un salto, sin pasar por el detalle.""",
            },
            {
                "role": "user",
                "content": "Great. And how would a push notification or a universal link open a specific product directly?",
            },
            {
                "role": "assistant",
                "content": r"""Con `onOpenURL` y rutas que se puedan **reconstruir a partir de una URL**. Eso obliga a un cambio en el diseño anterior: `Route.product(Product)` lleva el objeto entero, y desde una URL solo tienes el id. La ruta debe llevar el identificador, y la pantalla de detalle, cargar el producto.

```swift
import Foundation

enum Route: Hashable, Codable {
    case product(id: UUID)
    case checkout
}

extension Router {
    /// Acepta mitienda://product/<uuid> y https://tienda.example.com/products/<uuid>
    func handle(_ url: URL) {
        let isCustomScheme = url.scheme == "mitienda" && url.host() == "product"
        let isUniversalLink = url.host() == "tienda.example.com"
            && url.pathComponents.dropLast().last == "products"
        guard isCustomScheme || isUniversalLink,
              let id = UUID(uuidString: url.lastPathComponent) else { return }
        path = [.product(id: id)] // pila limpia: «atrás» vuelve a la raíz, no a donde estaba el usuario
    }
}
```

En la raíz, una sola línea más, y el destino cambia a `case .product(let id): ProductDetailView(productID: id)`, que carga el producto en su `.task`:

```swift
NavigationStack(path: $router.path) {
    SearchView()
        .navigationDestination(for: Route.self) { route in
            switch route {
            case .product(let id):
                ProductDetailView(productID: id)
            case .checkout:
                CheckoutView()
            }
        }
}
.onOpenURL { url in router.handle(url) }
.environment(router)
```

`onOpenURL` recibe tanto el esquema propio como los universal links (estos requieren además el *entitlement* de Associated Domains y el archivo `apple-app-site-association` en tu dominio).

Para las **notificaciones push**, pon la URL en el payload (por ejemplo, una clave `deeplink`) y, en el delegado de `UNUserNotificationCenter`, llama al mismo `handle(_:)`. Así hay un único punto de entrada para todos los deep links. Dos detalles: mueve el `Router` al `App` para que el delegado pueda alcanzarlo, y guarda la URL pendiente si la notificación abre la app en frío, para aplicarla cuando la interfaz exista.

Ventaja extra de que `Route` sea `Codable`: puedes guardar `router.path` con `JSONEncoder` al pasar a segundo plano y restaurar la navegación al volver.

Tests del parser, con Swift Testing:

```swift
import Foundation
import Testing
@testable import Shop

@MainActor
struct RouterDeepLinkTests {
    @Test func abreProductoDesdeEsquemaPropio() {
        let router = Router()
        let id = UUID()
        router.handle(URL(string: "mitienda://product/\(id.uuidString)")!)
        #expect(router.path == [.product(id: id)])
    }

    @Test func abreProductoDesdeUniversalLink() {
        let router = Router()
        let id = UUID()
        router.handle(URL(string: "https://tienda.example.com/products/\(id.uuidString)")!)
        #expect(router.path == [.product(id: id)])
    }

    @Test func ignoraURLsAjenas() {
        let router = Router()
        router.handle(URL(string: "https://otra.example.com/products/123")!)
        #expect(router.path.isEmpty)
    }
}
```

Comprobación manual en el simulador: `xcrun simctl openurl booted "mitienda://product/<uuid de un producto real>"` debe abrir el detalle aunque la app estuviera en otra pantalla, y «atrás» debe llevar a la búsqueda.""",
            },
        ]
    },
    # 26) SwiftUI: ForEach con ids duplicados (error concreto)
    {
        "messages": [
            {
                "role": "user",
                "content": r"""En SwiftUI tengo una lista de etiquetas y en consola sale esto, y a veces al borrar una se borra otra:

```
ForEach<Array<String>, String, Text>: the ID Swift occurs multiple times within the collection, this will give undefined results!
```

```swift
@State private var tags = ["Swift", "iOS", "Swift"]

List {
    ForEach(tags, id: \.self) { tag in
        Text(tag)
    }
    .onDelete { offsets in tags.remove(atOffsets: offsets) }
}
```""",
            },
            {
                "role": "assistant",
                "content": r"""El aviso es exacto: con `id: \.self` le dices a SwiftUI que **el propio texto es la identidad** de cada fila. Hay dos «Swift», así que dos filas comparten identidad y SwiftUI no puede distinguirlas. A partir de ahí el comportamiento está indefinido: al borrar, anima o elimina la vista equivocada, y el estado de una fila (un campo en edición, una selección) puede saltar a la otra.

La identidad en `ForEach` tiene que ser **única** dentro de la colección y **estable** mientras el elemento exista. Un `String` usado como id falla la primera condición con duplicados, y la segunda en cuanto permites editar el texto: al cambiarlo, SwiftUI cree que es otro elemento y recrea la fila, que pierde el foco.

**Arreglo: un modelo con identidad propia**, y decidir explícitamente si los duplicados tienen sentido:

```swift
import SwiftUI

struct Tag: Identifiable, Hashable {
    let id: UUID
    var name: String

    init(id: UUID = UUID(), name: String) {
        self.id = id
        self.name = name
    }
}

struct TagListView: View {
    @State private var tags = [Tag(name: "Swift"), Tag(name: "iOS")]
    @State private var newTagName = ""

    var body: some View {
        List {
            ForEach(tags) { tag in
                Text(tag.name)
            }
            .onDelete { offsets in tags.remove(atOffsets: offsets) }

            Section("Nueva etiqueta") {
                TextField("Nombre", text: $newTagName)
                    .onSubmit(addTag)
            }
        }
    }

    private func addTag() {
        let name = newTagName.trimmingCharacters(in: .whitespacesAndNewlines)
        let isDuplicate = tags.contains { $0.name.caseInsensitiveCompare(name) == .orderedSame }
        guard !name.isEmpty, !isDuplicate else { return }
        tags.append(Tag(name: name))
        newTagName = ""
    }
}
```

Con `Identifiable`, `ForEach(tags)` usa `tag.id` sin indicarlo. Y como dos etiquetas con el mismo nombre no tienen sentido en este dominio, `addTag` las rechaza en el origen: el id único arregla el bug de SwiftUI; la validación arregla el dato.

Tres errores de identidad que conviene reconocer:

- **`var id: UUID { UUID() }`** como propiedad calculada: genera un id nuevo **cada vez que se lee**, así que en cada render todas las filas parecen nuevas y se destruyen y recrean continuamente. El id se asigna una vez y se guarda (`let id`).
- **El índice como id** (`ForEach(Array(tags.enumerated()), id: \.offset)`): al borrar la fila 0, la que era 1 pasa a ser 0 y hereda la identidad de la borrada. Es exactamente tu bug con otro disfraz.
- **Datos del servidor**: usa el id que trae el backend, no un `UUID()` generado al decodificar, o cada recarga cambiará todas las identidades y perderás animaciones y selección.

Comprobación: con tu código, desliza para borrar el segundo «Swift» y verás desaparecer la fila equivocada o una animación incoherente, además del aviso. Con el modelo nuevo, el aviso desaparece, el duplicado no se puede crear y al borrar se va exactamente la fila deslizada.""",
            },
        ]
    },
    # 27) SwiftUI: .task para cargar datos con cancelación y .task(id:) para búsqueda con debounce (multiturno)
    {
        "messages": [
            {
                "role": "user",
                "content": "En SwiftUI, ¿dónde hago la llamada a la API al abrir una pantalla? Ahora la tengo en `.onAppear { Task { await cargar() } }`, a veces se dispara dos veces y, si salgo rápido de la pantalla, la petición sigue en curso.",
            },
            {
                "role": "assistant",
                "content": r"""Usa el modificador `.task`. Hace lo mismo que tu `onAppear` + `Task`, con una diferencia clave: la tarea queda **ligada a la vida de la vista**. Cuando la vista desaparece, SwiftUI cancela la tarea, y la cancelación se propaga a las llamadas `async` en curso, las de `URLSession` incluidas. El `Task { }` dentro de `onAppear` es una tarea no estructurada: nadie la cancela, y por eso la petición sigue viva al salir.

```swift
import SwiftUI

struct Order: Identifiable, Decodable, Sendable {
    let id: Int
    let total: Decimal
}

protocol OrdersService: Sendable {
    func fetchOrders() async throws -> [Order]
}

@MainActor
@Observable
final class OrdersModel {
    enum LoadState {
        case idle
        case loading
        case loaded([Order])
        case failed(String)

        var hasContent: Bool {
            if case .loaded = self { return true }
            return false
        }
    }

    private(set) var state: LoadState = .idle
    private let service: OrdersService

    init(service: OrdersService) {
        self.service = service
    }

    func load() async {
        if !state.hasContent { state = .loading } // al refrescar, la lista sigue visible
        do {
            state = .loaded(try await service.fetchOrders())
        } catch {
            guard !Task.isCancelled else { return } // la vista desapareció: no hay nada que mostrar
            state = .failed(error.localizedDescription)
        }
    }
}

struct OrdersView: View {
    @State private var model: OrdersModel

    init(service: OrdersService) {
        _model = State(initialValue: OrdersModel(service: service))
    }

    var body: some View {
        content
            .task { await model.load() }
            .navigationTitle("Pedidos")
    }

    @ViewBuilder
    private var content: some View {
        switch model.state {
        case .idle, .loading:
            ProgressView()
        case .loaded(let orders):
            List(orders) { order in
                LabeledContent("Pedido \(order.id)", value: order.total, format: .currency(code: "EUR"))
            }
            .refreshable { await model.load() }
        case .failed(let message):
            ContentUnavailableView {
                Label("No se pudieron cargar los pedidos", systemImage: "wifi.exclamationmark")
            } description: {
                Text(message)
            } actions: {
                Button("Reintentar") {
                    Task { await model.load() }
                }
            }
        }
    }
}
```

Decisiones:

- **El modelo es `@MainActor`**: el estado de la UI solo se modifica en el hilo principal y el compilador lo garantiza. La petición no bloquea ese hilo: `await` lo libera mientras espera.
- **La cancelación no es un error que mostrar.** Al salir de la pantalla, la petición termina lanzando `CancellationError` o `URLError(.cancelled)`, según dónde la pille la cancelación. `guard !Task.isCancelled` cubre ambos casos sin enumerar tipos.
- **`hasContent` evita el parpadeo al refrescar**: el pull to refresh no vuelve a `.loading`, así que la lista sigue visible mientras llegan los datos nuevos.
- **Sobre el «se dispara dos veces»**: `.task` también se ejecuta cada vez que la vista **vuelve a aparecer**, por ejemplo al regresar de un detalle. Si no quieres recargar al volver, protégelo: `.task { if !model.state.hasContent { await model.load() } }`. Uso `hasContent` y no `.idle` porque, si una carga se canceló a medias, el estado se quedó en `.loading` y debe reintentarse.

Comprobación: con un servicio de prueba que tarde 3 segundos y un `print` antes y después del `await`, entra en la pantalla y sal enseguida. Debe imprimirse el inicio, no el final, y no debe aparecer ningún error en pantalla.""",
            },
            {
                "role": "user",
                "content": "Ahora tengo una búsqueda: un campo de texto, y quiero llamar a la API mientras escribe, pero sin lanzar una petición por cada letra y cancelando la anterior si sigue escribiendo.",
            },
            {
                "role": "assistant",
                "content": """`.task(id:)` hace las dos cosas casi solo. Cuando el valor de `id` cambia, SwiftUI **cancela la tarea anterior** y arranca una nueva. Si la tarea empieza con una espera corta, esa espera es el *debounce*: mientras el usuario sigue tecleando, cada tarea se cancela durante el `sleep` y nunca llega a hacer la petición.

```swift
import SwiftUI

struct Product: Identifiable, Decodable, Sendable {
    let id: Int
    let name: String
}

protocol ProductSearchService: Sendable {
    func search(_ text: String) async throws -> [Product]
}

struct ProductSearchView: View {
    let service: ProductSearchService

    @State private var query = ""
    @State private var results: [Product] = []
    @State private var errorMessage: String?

    var body: some View {
        List(results) { product in
            Text(product.name)
        }
        .overlay {
            if let errorMessage {
                ContentUnavailableView(
                    "Error en la búsqueda",
                    systemImage: "exclamationmark.triangle",
                    description: Text(errorMessage)
                )
            }
        }
        .searchable(text: $query)
        .task(id: query) {
            let text = query.trimmingCharacters(in: .whitespacesAndNewlines)
            guard text.count >= 2 else {
                results = []
                return
            }
            do {
                // Debounce: si query cambia durante la espera, esta tarea se cancela aquí y no busca.
                try await Task.sleep(for: .milliseconds(300))
                results = try await service.search(text)
                errorMessage = nil
            } catch {
                guard !Task.isCancelled else { return } // cancelada por una tecla nueva: es lo esperado
                errorMessage = error.localizedDescription
            }
        }
        .navigationTitle("Buscar")
    }
}
```

Cómo se comporta al escribir «café» deprisa: «c» no llega al mínimo de dos caracteres; «ca» arranca una tarea que espera 300 ms; antes de que termine llega «caf», SwiftUI cancela la de «ca» (su `Task.sleep` lanza `CancellationError`) y arranca otra; igual con «café». Solo la última sobrevive a la espera y hace la petición.

Y si el usuario escribe mientras una petición ya está en vuelo, la cancelación llega a `URLSession`, que la aborta: una respuesta lenta de «caf» nunca puede pisar los resultados de «café». Ese es el bug clásico de las búsquedas, y aquí no hay código que lo evite porque la estructura no lo permite.

No hace falta modelo aparte para algo tan local; si la búsqueda creciera (filtros, paginación), la lógica de dentro del `.task` pasaría a un método `search(_:) async` del modelo, igual que con los pedidos.

Comprobación: con un servicio de prueba que registre cada llamada, escribe «cafetera» de corrido: debe registrarse una sola búsqueda. Escribe «ca», espera medio segundo y sigue escribiendo: deben ser dos.""",
            },
        ]
    },
    # 28) SwiftUI: MVVM testeable con @Observable, protocolo de repositorio y Swift Testing (inglés, avanzado)
    {
        "messages": [
            {
                "role": "user",
                "content": "What's a sane MVVM setup in SwiftUI with @Observable that I can actually unit test? Our view models call URLSession directly and tests are basically impossible.",
            },
            {
                "role": "assistant",
                "content": """The fix is one seam: the view model depends on a small protocol, not on `URLSession`. Everything else follows from that.

**Layers:** the View renders state and forwards intents; the ViewModel holds UI state and decides what happens; the Repository talks to the network. Only the repository knows about HTTP.

```swift
import Foundation

struct Article: Identifiable, Equatable, Decodable, Sendable {
    let id: Int
    let title: String
}

protocol ArticleRepository: Sendable {
    func latest() async throws -> [Article]
}

struct RemoteArticleRepository: ArticleRepository {
    let baseURL: URL
    let session: URLSession

    func latest() async throws -> [Article] {
        let (data, response) = try await session.data(from: baseURL.appending(path: "articles/latest"))
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            throw URLError(.badServerResponse)
        }
        return try JSONDecoder().decode([Article].self, from: data)
    }
}
```

```swift
import Observation

@MainActor
@Observable
final class ArticleListViewModel {
    private(set) var articles: [Article] = []
    private(set) var errorMessage: String?
    private(set) var isLoading = false

    private let repository: ArticleRepository

    init(repository: ArticleRepository) {
        self.repository = repository
    }

    func refresh() async {
        isLoading = true
        defer { isLoading = false }
        do {
            articles = try await repository.latest()
            errorMessage = nil
        } catch {
            // Keep whatever was already on screen; only report the failure.
            errorMessage = "Couldn't load articles. Pull to retry."
        }
    }
}
```

```swift
import SwiftUI

struct ArticleListView: View {
    @State private var viewModel: ArticleListViewModel

    init(repository: ArticleRepository) {
        _viewModel = State(initialValue: ArticleListViewModel(repository: repository))
    }

    var body: some View {
        List(viewModel.articles) { article in
            Text(article.title)
        }
        .overlay {
            if viewModel.articles.isEmpty, let message = viewModel.errorMessage {
                ContentUnavailableView(message, systemImage: "exclamationmark.triangle")
            }
        }
        .refreshable { await viewModel.refresh() }
        .task { await viewModel.refresh() }
    }
}
```

**The tests**, with Swift Testing and a scripted fake. An actor keeps the fake `Sendable` while letting it change its answer between calls:

```swift
import Foundation
import Testing
@testable import News

actor ScriptedArticleRepository: ArticleRepository {
    private var results: [Result<[Article], URLError>]

    init(_ results: [Result<[Article], URLError>]) {
        self.results = results
    }

    func latest() async throws -> [Article] {
        try results.removeFirst().get()
    }
}

@MainActor
struct ArticleListViewModelTests {
    @Test func loadsArticles() async {
        let articles = [Article(id: 1, title: "Swift 6 migration notes")]
        let viewModel = ArticleListViewModel(repository: ScriptedArticleRepository([.success(articles)]))

        await viewModel.refresh()

        #expect(viewModel.articles == articles)
        #expect(viewModel.errorMessage == nil)
        #expect(viewModel.isLoading == false)
    }

    @Test func keepsPreviousArticlesWhenRefreshFails() async {
        let articles = [Article(id: 1, title: "Swift 6 migration notes")]
        let viewModel = ArticleListViewModel(
            repository: ScriptedArticleRepository([.success(articles), .failure(URLError(.notConnectedToInternet))])
        )

        await viewModel.refresh()
        await viewModel.refresh()

        #expect(viewModel.articles == articles)
        #expect(viewModel.errorMessage != nil)
    }
}
```

Why this shape:

- **The protocol sits at the boundary you want to replace**, the network. Mocking `URLSession` itself means faking HTTP details in every view-model test; here view-model tests talk about articles, not status codes.
- **`@MainActor` on the view model** matches how SwiftUI reads it and makes the tests deterministic: no thread hopping inside `refresh()` that the test has to wait for.
- **`Result<_, URLError>` in the fake** instead of `any Error`, because `URLError` is `Sendable` and the actor's state must be too under Swift 6 checking.
- **`RemoteArticleRepository` gets its own tests** with a `URLProtocol` subclass registered on an ephemeral `URLSessionConfiguration`, which serves canned responses. That is the one place where HTTP details are worth asserting.
- **One view model per screen, not per row.** Rows take plain values; a view model per cell multiplies objects and lifecycles for no gain.

Verification: both tests run in milliseconds with no network. Break the view model by clearing `articles` in the `catch` and the second test must fail.""",
            },
        ]
    },
    # 29) SwiftUI: SwiftData frente a Core Data y lo mínimo para empezar (system breve)
    {
        "messages": [
            {"role": "system", "content": "Responde de forma breve y concreta."},
            {
                "role": "user",
                "content": "¿Me conviene SwiftData o Core Data para una app nueva (iOS 17+) que guarda notas offline? ¿Cómo se ve lo mínimo?",
            },
            {
                "role": "assistant",
                "content": r"""SwiftData, para una app nueva con iOS 17 como mínimo y un modelo sencillo como notas. Es la capa moderna sobre el mismo motor de almacenamiento que Core Data, con modelos en Swift puro y consultas integradas en SwiftUI.

```swift
import SwiftData
import SwiftUI

@Model
final class Note {
    var title: String
    var content: String
    var createdAt: Date

    init(title: String, content: String = "", createdAt: Date = .now) {
        self.title = title
        self.content = content
        self.createdAt = createdAt
    }
}

@main
struct NotesApp: App {
    var body: some Scene {
        WindowGroup {
            NotesListView()
        }
        .modelContainer(for: Note.self)
    }
}

struct NotesListView: View {
    @Query(sort: \Note.createdAt, order: .reverse) private var notes: [Note]
    @Environment(\.modelContext) private var context

    var body: some View {
        NavigationStack {
            List {
                ForEach(notes) { note in
                    Text(note.title)
                }
                .onDelete { offsets in
                    for index in offsets {
                        context.delete(notes[index])
                    }
                }
            }
            .toolbar {
                Button("Nueva", systemImage: "plus") {
                    context.insert(Note(title: "Nota \(notes.count + 1)"))
                }
            }
            .navigationTitle("Notas")
        }
    }
}

#Preview {
    NotesListView()
        .modelContainer(for: Note.self, inMemory: true)
}
```

- `@Model` convierte la clase en entidad persistente; `@Query` observa la base de datos y la lista se actualiza sola; el contexto guarda automáticamente.
- **Cuándo Core Data:** si tienes que soportar iOS anteriores al 17, ya tienes un store de Core Data en producción, o necesitas control fino (fetch requests muy afinadas, migraciones complejas, procesamiento por lotes).
- **Precauciones con SwiftData:** es más joven y algunos fallos de iOS 17 se corrigieron en iOS 18; prueba en la versión mínima que soportes. Si piensas sincronizar con CloudKit, todas las propiedades necesitan valor por defecto u opcional y no puedes usar `@Attribute(.unique)`; diséñalo así desde el principio.
- Comprobación: crea dos notas, cierra la app desde el selector de apps y vuelve a abrirla; deben seguir ahí, la más reciente arriba.""",
            },
        ]
    },
    # 30) SwiftUI: identidad estructural, cuándo se conserva o se reinicia @State (avanzado)
    {
        "messages": [
            {
                "role": "user",
                "content": "Dos bugs de SwiftUI que creo que son el mismo: un contador con @State en una vista hija se reinicia a 0 cuando cambio un filtro en el padre, y en otra pantalla quiero lo contrario, que un formulario se reinicie al cambiar de cliente, y no lo hace. No entiendo cuándo SwiftUI conserva el @State.",
            },
            {
                "role": "assistant",
                "content": """Son el mismo concepto visto desde los dos lados: **el `@State` vive exactamente lo que vive la identidad de la vista**. Mientras SwiftUI considere que es «la misma vista», conserva el estado aunque cambien sus parámetros; cuando decide que es otra, lo destruye y crea uno nuevo.

SwiftUI determina la identidad de dos formas:

- **Estructural**: la posición en la jerarquía. Cada rama de un `if`/`else` es una posición distinta, aunque contenga el mismo tipo de vista.
- **Explícita**: un identificador que das tú, con `.id(_:)` o con los ids de `ForEach`.

**Bug 1: el contador se reinicia.** Casi seguro el padre hace algo así:

```swift
if showOnlyFavorites {
    CounterView()
        .border(.yellow)
} else {
    CounterView()
}
```

Para ti es «la misma vista con o sin borde»; para SwiftUI son dos vistas en dos ramas distintas. Al cambiar el filtro, destruye la de una rama (con su `@State`) y crea la de la otra desde cero. El arreglo es **una sola vista con un modificador que cambia de valor**:

```swift
CounterView()
    .border(showOnlyFavorites ? Color.yellow : Color.clear)
```

El mismo problema aparece con la extensión `.if(condición) { $0.modificador() }` que circula por internet: por dentro es un `if`/`else` y cambia la identidad cada vez que cambia la condición. Por eso conviene evitarla. `AnyView` tiene un efecto parecido: borra la información de tipo que SwiftUI usa para seguir la identidad.

**Bug 2: el formulario no se reinicia.** Es el caso inverso:

```swift
struct CustomerEditor: View {
    let customer: Customer
    @State private var draftName: String

    init(customer: Customer) {
        self.customer = customer
        _draftName = State(initialValue: customer.name)
    }

    var body: some View {
        Form {
            TextField("Nombre", text: $draftName)
        }
    }
}
```

`State(initialValue:)` solo se usa cuando **se crea la identidad**. Al cambiar de cliente, `CustomerEditor` sigue en la misma posición, así que es la misma vista: recibe el `customer` nuevo, pero el `@State` existente se conserva y el valor inicial nuevo se ignora. Ves el borrador del cliente anterior.

El arreglo es atar la identidad al cliente:

```swift
CustomerEditor(customer: selectedCustomer)
    .id(selectedCustomer.id) // otro cliente, otra vista: el borrador se crea de nuevo
```

Cuidado con dos cosas de `.id`:

- **Recrea el subárbol entero**: pierde el scroll, el foco y vuelve a ejecutar sus `.task`. Es justo lo que quieres aquí; úsalo a propósito, no como arreglo genérico de «no se actualiza».
- **Nunca `.id(UUID())`** en el `body`: genera una identidad nueva en cada render, así que la vista se destruye y se recrea constantemente.

Regla general para decidir: si el estado debe **sobrevivir** a cambios del padre, mantén la vista en la misma posición estructural y varía solo los valores de sus modificadores; si debe **reiniciarse** cuando cambia una entidad, dale `.id` con el identificador de esa entidad.

Comprobación: añade `let _ = Self._printChanges()` al principio del `body` de `CounterView` y de `CustomerEditor`. Cuando SwiftUI cree una vista nueva verás `@identity changed`; cuando solo actualice parámetros, `@self changed`. Antes del arreglo 1, cambiar el filtro debe mostrar el primero; después, ninguno de los dos o solo el segundo. En el bug 2 es al revés: con `.id`, cambiar de cliente debe mostrar `@identity changed`.""",
            },
        ]
    },
]
