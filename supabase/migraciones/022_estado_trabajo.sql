-- 27 nov (auditoría de exposición, hallazgo #2/#4; decisión de Oscar: «Supabase»): el detalle por cargo del estado de
-- trabajo (lote del día, vacantes ya entregadas, métricas por cargo, rotación con claves cargo@país, colas y el
-- reporte completo) deja la rama pública `publicado` y se guarda aquí, privado. La rama conserva solo cifras agregadas.
-- Aditiva: una tabla nueva con RLS y solo service_role; no toca tablas, funciones ni datos existentes.
-- `grupo`: 'vigente' = lo que lee la siguiente corrida; 'fallida' = copia de la última corrida que falló, solo para
-- diagnóstico y recuperación (nunca la lee una corrida). `contenido` es el archivo en gzip + base64.
begin;
create table if not exists public.estado_trabajo (
  grupo text not null check (grupo in ('vigente','fallida')),
  archivo text not null check (archivo ~ '^(trabajo|datos)/[a-z0-9_]+\.json$'),
  contenido text not null,
  sha256 text not null check (sha256 ~ '^[0-9a-f]{64}$'),
  ejecucion text not null default '',
  actualizado_en timestamptz not null default now(),
  primary key (grupo, archivo)
);
alter table public.estado_trabajo enable row level security;
revoke all on public.estado_trabajo from public, anon, authenticated, service_role;
grant select, insert, update on public.estado_trabajo to service_role;
commit;
