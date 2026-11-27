# Activar el «Reloj» (contrato v51)

Desde el 17 nov GitHub dispara los horarios de este repositorio con 7 a 11 horas de retraso. El «Reloj» hace que la
búsqueda de las 6:30 a. m. de Bogotá y la captura de cada hora arranquen a su hora, sin servicios externos: todo ocurre
dentro de GitHub.

## Qué necesitas
Dos minutos y permiso de administrador en el repositorio. Se hace una sola vez.

## Pasos
1. En GitHub, en el repositorio: **Settings → Environments → New environment**.
2. Nombre: `reloj` (en minúsculas, tal cual). Pulsa «Configure environment».
3. Marca **Wait timer**, escribe `30` y pulsa **Save protection rules**. No hace falta nada más en esa página (ni
   revisores ni secretos).
4. Ve a **Actions → Reloj → Run workflow** (rama principal, origen «manual») y pulsa «Run workflow».

## Cómo saber que quedó andando
- En Actions → Reloj aparece una corrida «Waiting» durante 30 minutos. Al terminar queda otra esperando: esa es la
  cadena. Siempre debe haber **una** corrida del Reloj esperando.
- En Actions → Captura horaria vuelve a haber una corrida cada hora.
- Al día siguiente, la «Bodega nocturna» arranca entre las 6:30 y las 7:00 a. m. de Bogotá.

## Si algo no va
| Lo que ves | Qué pasó | Qué hacer |
|---|---|---|
| La corrida del Reloj termina en rojo con «no tiene su temporizador» | El entorno `reloj` no tiene el «Wait timer» (o se llama distinto) | Repite los pasos 1 a 3 y vuelve a lanzarlo |
| No hay ninguna corrida del Reloj esperando | La cadena se cortó | Se reanuda sola con la siguiente búsqueda, con «Buscar ahora» o cuando GitHub dispare un horario. Para no esperar: Actions → Reloj → Run workflow |
| Hay dos corridas esperando | Una es de respaldo | Nada: al llegar su turno, una de las dos se retira |
| La búsqueda de hoy falló y el Reloj no la repite | Es a propósito: una búsqueda que falla se revisa antes de repetirla | Mira el fallo y usa «Buscar ahora» |
| Son más de las 7:00 p. m. y la búsqueda de hoy no corrió | A esa hora el Reloj ya no la empieza | Usa «Buscar ahora» si aún la quieres hoy |

## Detenerlo
Actions → Reloj → menú «…» → **Disable workflow**. Los horarios normales de GitHub siguen como respaldo.

## Qué hace exactamente
Cada 30 minutos: pide el siguiente relevo; si pasó una hora desde la última captura, pide la captura horaria; y desde
las 6:30 a. m. de Bogotá (y hasta las 7:00 p. m.), si hoy no hay búsqueda diaria hecha ni en marcha, la pide. No usa claves ni lee datos de
clientes. Deja unas 48 corridas cortas al día en Actions y en «Deployments»; la espera no gasta minutos.

## Si el proyecto se traspasa
El entorno `reloj` se crea igual en el repositorio nuevo (pasos 1 a 4). Si ese repositorio fuera **privado** en un plan
gratuito, GitHub no ofrece el temporizador de espera: el Reloj se quedaría parado (no gira sin pausa) y habría que usar
los horarios normales o un plan que lo incluya.
