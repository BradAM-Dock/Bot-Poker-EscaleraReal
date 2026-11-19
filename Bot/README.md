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
qué piensa en cada jugada:

```
[flop   ] Ah Kd | mesa Kc 7d 2h | bet 60       | par (buena): apuesto medio pozo
[turn   ] Ah Kd | mesa Kc 7d 2h 9s | call         | par (buena): pago
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
| `test_bot.py` | Pruebas sin mesa ni red. | Agrega las tuyas |

---

## La estrategia, regla por regla

### Antes del flop

Las dos cartas se clasifican en cinco grupos con tres preguntas: ¿son pareja?
¿son altas? ¿son del mismo palo?

| Grupo | Manos | Qué hace |
| ----- | ----- | -------- |
| Premium | JJ+, AK | Abre a 3 ciegas. Si ya subieron, resube al triple (o all-in si la subida es grande). |
| Fuerte | 88-TT, AQ, AJ, KQ del mismo palo | Abre a 3 ciegas. Paga subidas de hasta 4 ciegas. |
| Jugable | 22-77, AT, Ax del mismo palo, figuras | Si nadie entró y habla último, intenta robar las ciegas. Si no, entra solo barato. |
| Especulativa | Conectoras del mismo palo (65s+) | Entra barato y solo con varios rivales: ganan pozos grandes cuando ligan. |
| Basura | Todo lo demás | Pasa si es gratis; si no, se retira. |

### Después del flop

`equidad.py` completa cada reparto al azar y compara las mejores manos,
incluyendo desempates. Una victoria cuenta como `1`, una derrota como `0` y
los empates se reparten entre los jugadores empatados. Usa hasta 500
simulaciones por decisión y limita el tiempo de cálculo.

Si nadie apostó, apuesta medio pozo cuando la equidad es alta, con un umbral
mayor contra más rivales. Ante una apuesta, compara la equidad con el precio de
pagar y añade un margen conservador. Con equidad muy alta puede resubir por
valor. Por ahora los rivales se simulan con cartas aleatorias: sus rangos no se
ajustan todavía a sus acciones.

---

## Cómo ganarle (y por dónde mejorarlo)

Esta versión ya estima equidad postflop, pero todavía tiene límites:

1. **No lee al rival**: simula cartas aleatorias y no ajusta los rangos según
   las acciones o las cartas mostradas.
2. **El preflop sigue siendo una tabla fija** de grupos de manos.
3. **La estimación tiene ruido** porque usa un número limitado de repartos;
   las decisiones cerca de un umbral pueden variar entre ejecuciones.
4. **La estrategia de apuestas aún es básica**: usa umbrales fijos y un farol
   de river sencillo, no una política equilibrada por situaciones.

Tu bot debería explotar al menos dos de estas cuatro cosas. Y si quieres un rival
más duro, prueba contra **Gato Darwin**, el bot intermedio en Go, cuya estrategia
fue entrenada con un algoritmo genético.

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
