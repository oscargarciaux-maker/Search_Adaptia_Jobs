-- Ajustes privados del operador (contrato v10): por ahora, destinatarios y tipos de alertas por correo.
-- Fuera de la configuración versionada: un cambio de correo se aplica al momento y no se copia en cada versión.
begin;
create table if not exists public.panel_ajustes (
 clave text primary key check (clave ~ '^[a-z_]{2,40}$'),
 valor jsonb not null,
 actualizado_en timestamptz not null default now()
);
alter table public.panel_ajustes enable row level security;
revoke all on public.panel_ajustes from public, anon, authenticated;
grant all on public.panel_ajustes to service_role;
commit;
