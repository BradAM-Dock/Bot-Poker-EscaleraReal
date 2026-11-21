# Michi Novato · bot de ejemplo (dificultad fácil)

Bot de ejemplo para **PokerFight** (AICS PUCP), escrito en **Python** y sin
ninguna librería fuera de la estándar. Toda su inteligencia son **condicionales**:
una tabla de manos iniciales, una lectura de la jugada con conteos y un puñado
de reglas de poker escritas con `if`.

Es el primer rival contra el que conviene probar tu bot. Si no le ganas de forma
consistente, tu bot todavía no está listo para el torneo.

| | |
| --- | --- |
| Dificultad | Fácil |
| Lenguaje | Python 3.8+ (solo librería estándar) |
| Técnica | Reglas preflop y equidad Monte Carlo postflop |
| Mesas | Heads-up y mesas de 3 a 8 jugadores |
| Tiempo por jugada | Instantáneo |

---

## Cómo correrlo

### Contra la arena, en un torneo local

Ya está en el `torneo.json` de la raíz, así que `make torneo-local` lo hace
jugar contra los demás bots de ejemplo. Para sumarlo a otro torneo, agrégalo a
la lista de `participantes` (las rutas son relativas a la raíz del repositorio):

```json
{
  "id": "novato",
  "nombre": "Michi Novato",
  "comando": ["python", "bots/novato/bot.py", "-silencioso"]
}
```

y corre la arena como siempre:

```bash
./bin/arena correr -config torneo.json
```

La arena le agrega `-addr <host:puerto> -token <token>` al final del comando: el
bot ya los entiende. Quita `-silencioso` y corre la arena con `-verboso` para ver
qué piensa en cada jugada, las acciones públicas nuevas de los rivales y sus
fichas disponibles/apostadas. También señala los all-ins y las eliminaciones:

```
[flop] Rival: allin
Fichas: Michi Novato: saldo 940, apuesta 60 | Rival: saldo 0, apuesta 1.000 [ALL-IN]
```

### Contra una mesa suelta, a mano

```bash
./bin/mesa -addr :9000 -jugadores 2 -min-jugadores 2
python bots/novato/bot.py -addr localhost:9000 -token michi
./bin/aleatorio -addr localhost:9000 -token rival   # en otra terminal
```

### Pruebas

```bash
cd bots/novato
python -m unittest -v
```

### Usarlo como punto de partida en tu propio repositorio

No depende de nada de la arena: copia esta carpeta a tu repositorio, cambia
`estrategia.py` y en el `torneo.json` apunta el comando a donde lo tengas:

```json
{ "id": "mi-bot", "comando": ["python", "../mi-repo/bot.py"] }
```

---

## Cómo está armado

| Archivo | Qué hace | ¿Lo tienes que tocar? |
| ------- | -------- | -------------------- |
| `bot.py` | Bucle principal: recibe mensajes y responde los turnos. Reconecta si se corta la red. | No |
| `conexion.py` | Socket TCP, saludo y JSON Lines (el protocolo de la arena). | No: cópialo tal cual a tu bot |
| `turno.py` | Ayudantes: `apostar(total)`, `pagar()`, `por_igualar`, `rivales_en_mano`, `hablo_ultimo`... Nunca devuelven una acción inválida. | Rara vez |
| `cartas.py` | Lectura de la mano con conteos: categoría de la jugada, si usa tus cartas y cuántos *outs* tienes. | Si quieres leer mejor la mano |
| `equidad.py` | Simula cartas ocultas, compara manos y estima la equidad. | No |
| `estrategia.py` | **La estrategia.** `decidir(turno)` devuelve la acción y el motivo. | **Sí: aquí empieza tu bot** |
| `test_equidad.py` | Pruebas del evaluador y las simulaciones Monte Carlo. | Agrega las tuyas |
| `test_estrategia.py` | Pruebas de preflop, c-bet y decisiones postflop basadas en EV. | Agrega las tuyas |
| `test_rivales.py` | Pruebas de memoria y frecuencias por rival. | Agrega las tuyas |
| `test_bot_memoria.py` | Verifica que el bucle integre los mensajes con la memoria. | Agrega las tuyas |
| `memoria_rivales.py` | Estadisticas bayesianas por ID de rival, basadas en acciones publicas. | No |
| `benchmark_darwin.py` | Benchmark repetible en la arena contra Gato Darwin. | Ejecuta desde la raíz |
| `benchmark_6max.py` | Benchmark de seis bots con eliminaciones y rotación de asientos. | Ejecuta desde la raíz |
| `test_bot.py` | Pruebas sin mesa ni red. | Agrega las tuyas |

---

## La estrategia, regla por regla

### Antes del flop

Las dos cartas se clasifican en cinco grupos con tres preguntas: ¿son pareja?
¿son altas? ¿son del mismo palo?

| Grupo | Manos | Qué hace |
| ----- | ----- | -------- |
| Premium | JJ+, AK | Abre a 3 ciegas. Resube al triple; el all-in requiere QQ+ y AKs con hasta 100 ciegas efectivas, o KK+ por encima de 100. JJ puede pagar una 3-bet de hasta 10 ciegas heads-up si conserva al menos 20 ciegas. |
| Fuerte | 88-TT, AQ, AJ, KQ del mismo palo | Abre a 3 ciegas. Paga subidas de hasta 4 ciegas; AQ también puede pagar una 3-bet de hasta 10 ciegas heads-up si conserva al menos 20 ciegas. |
| Jugable | 22-77, AT, Ax del mismo palo, figuras | Si nadie entró y habla último, intenta robar las ciegas. Si no, entra solo barato. |
| Especulativa | Conectoras del mismo palo (65s+) | Entra barato y solo con varios rivales: ganan pozos grandes cuando ligan. |
| Basura | Todo lo demás | Pasa si es gratis; si no, se retira. |

### Después del flop

`equidad.py` completa cada reparto al azar y compara las mejores manos,
incluyendo desempates. Una victoria cuenta como `1`, una derrota como `0` y
los empates se reparten entre los jugadores empatados. Usa hasta 2.000
simulaciones por decisión y limita el tiempo de cálculo.

Si nadie apostó, apuesta medio pozo cuando la equidad es alta, con un umbral
mayor contra más rivales. Ante una apuesta, calcula el EV incremental del call
(`equidad × pozo_si_paga − coste`) y exige un margen conservador. Con equidad
muy alta puede resubir por valor. Las manos rivales se ponderan por su última
acción pública (check, call, bet, raise o all-in), y la memoria bayesiana
modera esos rangos con las frecuencias observadas por ID de rival. Las cartas
reveladas en showdown calibran además, con suavizado bayesiano, la frecuencia
de manos fuertes asociada a cada tipo de agresión y calle; son evidencia
limitada a manos mostradas, no una probabilidad exacta. Solo utiliza el
historial público y las cartas mostradas; se mantiene en RAM mientras vive el
proceso del bot. En heads-up también descuenta la parte de la apuesta rival
que no puede cubrir un call all-in corto. Si ya hay un rival all-in, o el call
corto es multiway, conserva el criterio anterior porque la equidad no separa
quién puede ganar cada sub-pozo.

Como variación, cuando Michi fue el último agresor preflop, queda heads-up,
habla después de que el rival pasó y el flop tiene tres palos distintos sin
tres rangos dentro de una ventana de cinco valores, intenta una c-bet de un
tercio del pozo con probabilidad del 65%. Esta regla usa el tamaño pequeño
independientemente de la equidad Monte Carlo; el resto de las decisiones
postflop mantiene sus umbrales habituales. El sorteo se inicializa con el ID de
la mano, por lo que un mismo reparto toma la misma rama en benchmarks repetidos.

---

## Cómo medirse y seguir mejorando

Para simular partidas sin integrar los bots manualmente, desde la raíz de este
repositorio compila una vez los binarios de la arena y corre el benchmark. Por
ejemplo, cinco aleatorios contra Michi:

```bash
cd pokerfight-arena-participantes-main
go build -o bin/ ./cmd/... ./bots/...
cd ..
python Bot/benchmark_6max.py --scenario random --hands 50 --seeds 10 --seed 20261123
```

Para probar a Darwin junto a cuatro aleatorios:

```bash
python Bot/benchmark_6max.py --scenario darwin-random --hands 50 --seeds 10 --seed 20261123
```

`--scenario kit` conserva el grupo de referencia Michi, Darwin, Base,
Estadístico, Bandido y Espía. Cada comando valida y ejecuta las mesas
automáticamente, asigna semillas reproducibles a los aleatorios, rota los seis
asientos y guarda resultados e historiales en una carpeta nueva bajo
`Bot/benchmarks/`. Compara puesto medio, fichas, victorias, top 3,
eliminaciones y timeouts. Usa varias semillas: una mesa aislada tiene mucha
varianza. Reduciendo `--seeds` o `--rotations` puedes hacer una prueba rápida.
También genera `fichas_por_mano.csv`, con el stack de cierre, cambios, all-ins y
eliminaciones acumuladas por participante después de cada mano. Para imprimir
esa evolución en la terminal, incluyendo los all-ins y quién agotó sus fichas,
agrega `--show-stacks`; con muchas rotaciones la salida será extensa.

```bash
python Bot/benchmark_6max.py --scenario darwin-random --seeds 1 --rotations 1 --show-stacks
```

Esto mide una ronda de seis jugadores, no la clasificatoria completa de diez
rondas con reasignación de mesas y stacks acumulados. El benchmark
`benchmark_darwin.py` sigue disponible como prueba secundaria heads-up.

Esta versión pondera los rangos por la última acción pública (check, call,
bet, raise o all-in) y por frecuencias bayesianas observadas para cada ID:
agresión por calle, folds ante apuestas, entradas preflop y manos fuertes
mostradas después de agresión. Las cartas reveladas también calibran la
frecuencia de manos fuertes por tipo de agresión y calle, con una prior
conservadora para evitar sobreajustar pocas muestras. La memoria vive en el
proceso y se reinicia si este termina; solo usa historial público y cartas
reveladas en showdown.
Preflop conserva una tabla base, pero puede pagar con una mano fuerte ante un
agresor frecuente sin evidencia de un rango fuerte, si el precio es bajo y
quedan pocos rivales. Al evaluar ese ajuste, limita las cartas mostradas a
agresiones preflop del mismo tipo, sin mezclar showdowns postflop. También
conserva umbrales postflop y un cálculo de call que no modela las apuestas de
calles futuras.

---

## Requisitos del torneo que ya cumple

- Acepta `-addr` y `-token` (lo único que pasa la arena).
- Se identifica con el `id_jugador` de la bienvenida, nunca con el token.
- Manda `monto` como el **total** de la ronda y respeta la subida mínima.
- Nunca se retira cuando pasar es gratis.
- Responde al instante: muy lejos del límite de 5 segundos por jugada.
- Si se corta la conexión, vuelve con el mismo token y recupera su silla.

---

Hecho por AICS PUCP para la competencia PokerFight · [@aicspucp](https://instagram.com/aicspucp)
