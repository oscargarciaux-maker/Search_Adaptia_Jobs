# Contrato de datos v48 — «(ID N)» en cada vacante, mensajes de días anteriores y tope de comprobación en «Buscar ahora» (22 nov 2026)

Decisiones de Oscar del 22 nov. Sin IA. Añade la SQL 020; no modifica ninguna migración registrada.

## 1. Número corto de cada vacante: «(ID 1234)»
- **SQL 020** añade a `catalogo_vacantes`:
  - la columna `numero` (bigint, único, no nulo);
  - la secuencia `catalogo_vacantes_numero_seq`;
  - dos disparadores: uno da el siguiente número a cada vacante nueva (también a una fila restaurada de un respaldo
    anterior, que no trae número) y otro impide cambiarlo;
  - sin valor por defecto: el buscador reenvía cada vacante varias veces al día y el disparador reutiliza su número,
    así no se gastan números en cada envío.
- Las vacantes ya guardadas se numeran por orden de llegada (`first_seen_at`, `observed_at`, `id`) y nunca se
  renumeran.
- El identificador de 16 caracteres (`id`) sigue siendo la llave en todas las tablas; el número solo lo acompaña.
- Los respaldos y el traspaso incluyen ahora **tres secuencias** (`respaldo.SECUENCIAS`).
- **Dónde se ve:**
  - en cada vacante de los mensajes de WhatsApp (borradores diarios, «Copiar WhatsApp» y posts):
    `1. Product Designer · Acme (Remoto) (ID 1234)`;
  - en Vacantes (lista y ficha) y en «Por confirmar» (lista, ficha y tarjetas del detalle del cliente);
  - en los CSV:
    - `/api/base.csv` añade al final la columna `numero`; las columnas del contrato v1 y sus extras no cambian;
    - `/api/revisiones.csv` añade `numero` antes de `vacante_id`; al subirlo se sigue leyendo `vacante_id`.
- Si la base aún no aplicó la SQL 020 (el panel se publica antes de que «Preparar Supabase» la aplique), el número no
  aparece y nada se rompe (`repositorio.numeros` devuelve vacío).

## 2. Mensaje de WhatsApp de cualquier día
- **Desde el detalle del cliente** (Resumen), cada día con vacantes tiene el botón «Tomar vacantes». Abre Vacantes con
  ese cliente y ese día, y deja el foco en «Copiar WhatsApp».
- En Vacantes, el día se elige en un **calendario** (como en la descarga del CSV). Si ese día no hubo búsqueda, lo dice.
- **De un día anterior:**
  - entran las vacantes listas y las ya entregadas ese día que siguen siendo compatibles; nunca las retiradas ni las
    por confirmar;
  - las que no tienen el enlace comprobado en las últimas 24 h (v31) **se comprueban al momento**, en orden y solo
    las que podrían entrar (`cuantas`·2 + 5, por los 2 por empresa);
  - tope de 30 s (`SEGUNDOS_DIA_ANTERIOR`), con la pausa de LinkedIn;
  - las cerradas y las que no se alcanzaron a comprobar no van; el diálogo dice cuántas se quitaron;
  - la comprobación positiva se guarda en el catálogo, como al confirmar en «Por confirmar»;
  - el mensaje empieza con «Te comparto N vacantes … que siguen abiertas», no con «Hoy encontré…».
- Siguen 2 por empresa, «Cuántas», «Tengo N más…» y las partes de 10 (v43).
- Nada se envía solo: el operador copia el mensaje y lo envía.

## 3. Tope de comprobación de enlaces solo en «Buscar ahora» (faltantes)
- **Causa.** La búsqueda #41 (19 nov) tardó 19 min en comprobar enlaces con un tope de 240 s. El tope solo contaba el
  tiempo de abrir enlaces, no el de ordenar las candidatas: `cola_de_seleccion` repite la selección del día hasta 12
  veces por ronda, en hasta 4 rondas, sobre unas 8.800 vacantes.
- **En «Buscar ahora» para quien falta** (`verificacion_enlaces.contar_orden`):
  - el tiempo de ordenar cuenta dentro del tope (240 s), y ordenar usa como mucho la mitad de lo que queda: la otra
    mitad es siempre para abrir enlaces;
  - `cola_de_seleccion` no empieza otra selección que no alcanzaría a terminar antes del límite y devuelve lo que
    lleva;
  - la primera comprobación usa como mucho 240 − 60 s; los 60 s restantes quedan para las vacantes nuevas del
    refuerzo y del rescate.
- **La búsqueda completa de la mañana no cambia** (decisión de Oscar).
