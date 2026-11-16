-- Contrato v34 (16 nov): «Por confirmar» rápido. Cada noche la búsqueda guarda en la propia fila de la bandeja un
-- resumen corto de la vacante (título, empresa, ubicación, modalidad, salario, idioma, publicación, enlace, país
-- detectado y sugerencia), y el panel lista las pendientes sin leer el catálogo ni las descripciones. Aditiva: una
-- columna nueva con valor por defecto; no cambia filas, permisos ni funciones existentes. No añade tablas.
begin;
alter table public.panel_revisiones
  add column if not exists resumen jsonb not null default '{}'::jsonb;
alter table public.panel_revisiones drop constraint if exists panel_revisiones_resumen_objeto;
alter table public.panel_revisiones
  add constraint panel_revisiones_resumen_objeto check (jsonb_typeof(resumen) = 'object');
commit;
