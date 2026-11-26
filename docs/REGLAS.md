# Reglas de la Quiniela (v1)

## Juego
- Cada quiniela tiene una lista de partidos (de una o varias ligas).
- Por cada partido el jugador marca **L** (gana local), **E** (empate) o **V** (gana visitante).
- **1 punto por acierto.**
- Cuenta el **resultado a los 90 minutos** (más el tiempo agregado). Prórroga y penales **no** cuentan.

## Partido estelar (desempate)
- Cada quiniela tiene **un** partido marcado como estelar ⭐.
- Además de su L/E/V, cada jugador pone el **marcador** de ese partido.
- Orden de la tabla:
  1. Más puntos.
  2. Atinó el marcador exacto del estelar.
  3. Menor distancia al marcador real: |goles local pronosticados − reales| + |goles visitante pronosticados − reales|.
  4. Si sigue el empate, comparten el lugar (y el premio se reparte).
- Si el partido estelar se anula, no hay desempate: quienes empaten en puntos comparten el lugar.

## Cierre de pronósticos
- Cada partido se **bloquea al pitazo inicial** (por partido, no por jornada).
- El marcador del estelar se bloquea al inicio del partido estelar.
- Los pronósticos de los demás se **revelan** cuando arranca cada partido.
- Si alguien no llenó un partido antes del cierre, ese partido vale 0 para esa persona.

## Partidos anulados
- Partido **pospuesto, suspendido o cancelado** = **anulado para todos** (nadie suma ese punto).
- Si se juega después y el admin lo reactiva antes de cerrar la quiniela, vuelve a contar.

## Datos y correcciones
- Los resultados se cargan solos (ESPN; respaldo API-Football).
- Solo el súper admin puede corregir un marcador a mano (afecta a todos los grupos); un partido corregido a mano ya no lo modifica el robot.
- Partidos que terminaron en prórroga sin desglose de 90' se marcan **"por revisar"** para que el súper admin confirme.

## Permisos
- **Súper admin (Carlos, dueño de la plataforma):** se configura en el servidor. Único que puede corregir marcadores (los partidos son compartidos entre grupos), moderar grupos y **autorizar quién puede crear grupos** (creación cerrada, con código que él entrega).
- **Dueño del grupo:** quien lo crea (con autorización). Arma quinielas, elige el estelar, invita/saca gente, marca pagos, nombra co-admins y puede transferir el grupo.
- **Co-admin:** lo nombra el dueño. Mismos permisos que el dueño excepto quitarle permisos al dueño o borrar el grupo.
- **Participante:** llena picks y ve la tabla.
- Un grupo nunca se queda sin dueño; si el dueño se va sin transferir, pasa al co-admin más antiguo.
- Nadie, ni los admins, ve los picks ajenos antes del pitazo.
- Cada cambio de permisos queda registrado.
- Al entrar se pide el **nombre** del participante (no apodo); así aparece en la tabla.

## Dinero
- La app **no cobra ni guarda dinero**. Solo muestra quién ya pagó (✅ / ⏳), marcado por el admin.
