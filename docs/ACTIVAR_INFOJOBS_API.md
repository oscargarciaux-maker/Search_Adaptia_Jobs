# Activar la API oficial de InfoJobs (España)

Contrato v50 §3. Es optativo. Sin esto, InfoJobs se lee por su página de búsqueda, que pide captcha tras unas cinco
páginas: trae pocos avisos y a veces ninguno. Con la API oficial no hay captcha, cada aviso llega con su descripción
completa y su fecha de creación, y el enlace se comprueba preguntándole a InfoJobs si el aviso sigue activo.

## Qué necesitas
Una cuenta en InfoJobs y cinco minutos. La aplicación queda a tu nombre; si el proyecto se traspasa, el nuevo dueño
registra la suya y cambia los dos secretos.

## Pasos
1. Entra a <https://developer.infojobs.net/> y pulsa «Log in» con tu cuenta de InfoJobs.
2. Registra tu aplicación en <https://developer.infojobs.net/app/manage-app/create.xhtml>. El formulario exacto no lo
   pude ver sin cuenta: pide los datos de la aplicación (nombre y descripción; si pide una dirección de retorno, sirve
   cualquiera tuya, porque aquí solo se leen avisos públicos) y aceptar las condiciones de uso de la API.
3. InfoJobs te muestra dos datos: **Client ID** y **Client secret**. No los pegues en ningún chat ni archivo.
4. En GitHub, en el repositorio: Settings → Secrets and variables → Actions → «New repository secret». Crea dos:
   - `INFOJOBS_CLIENT_ID` con el Client ID;
   - `INFOJOBS_CLIENT_SECRET` con el Client secret.
5. Listo. La siguiente búsqueda completa los usa sola.

## Cómo saber que quedó activa
En el reporte de la búsqueda (`datos/salud_bodega.json`, fuente «InfoJobs») aparece `"modo": "api"` con cuántas
búsquedas y fichas leyó. Si dice `"modo": "pagina"`, los secretos no están (o tienen otro nombre). Si trae
`"error": "InfoJobs rechazó la clave…"`, alguno de los dos datos está mal copiado.

## Qué cambia con la clave
- Búsquedas: hasta `infojobs_api_busquedas` (40) por corrida y hasta `infojobs_api_fichas` (150) fichas, en
  `datos/config.yaml`. Empiezan bajos porque no conocemos el límite de uso que InfoJobs da a cada aplicación; si el
  reporte no muestra fallos, se pueden subir.
- La fecha de cada vacante es la de creación del aviso, no la de su última republicación.
- El enlace se comprueba con la ficha de la API: abierto si InfoJobs dice que está activo y el título coincide;
  cerrado si está archivado o borrado. La página del aviso sigue sin abrirse nunca (pide captcha).
- Si el aviso se postula en la página de la empresa, esa dirección queda como enlace directo.

## Límites
- Esta parte se construyó con la documentación pública de InfoJobs y se probó con respuestas de ejemplo. La primera
  búsqueda con la clave dirá si algún dato llega distinto; conviene mirar ese reporte.
- Las claves solo viajan en la cabecera de autenticación hacia `api.infojobs.net`. No van al repositorio, al navegador,
  a los reportes ni a los registros.
