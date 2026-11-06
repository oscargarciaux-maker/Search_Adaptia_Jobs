# Raíz pública Supabase

`prod-ca-2021.crt` es un certificado público, sin clave privada. Se obtuvo por HTTPS verificado del enlace de producción
usado por el panel oficial de Supabase:

- Configuración oficial: <https://github.com/supabase/supabase/blob/master/apps/studio/hooks/custom-content/custom-content.json>,
  clave `ssl:certificate_url`, con `env=prod`.
- Descarga: <https://supabase-downloads.s3-ap-southeast-1.amazonaws.com/prod/ssl/prod-ca-2021.crt>.
- Instrucciones del proveedor: <https://supabase.com/docs/guides/platform/ssl-enforcement>.
- SHA-256 del certificado DER: `807025ad50d4ed219d2c9c7d299c004f824eb00cf7f65afef607d07b72e6cafa`.
- Sujeto/emisor: Supabase Root 2021 CA. Vencimiento: 26 de abril de 2031, 10:56:53 UTC.

El controlador combina esta raíz con las autoridades del sistema en un archivo temporal durante la conexión. Mantiene
`sslmode=verify-full`, incluido comprobar el nombre del servidor, y retira el archivo al terminar el intento. No descarga
certificados durante cada captura ni acepta como confiable uno obtenido del servidor sin verificar.

Para rotar esta raíz, contrastar la fuente oficial y revisar certificado, huella y pruebas por PR. No desactivar TLS
ni cambiar a `sslmode=require` para ocultar un error. Los archivos SQL de migración no se modifican por este cambio.
