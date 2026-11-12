-- Contrato v10: contacto de WhatsApp de cada cliente y borradores diarios para enviar a mano con un toque.
-- Datos personales solo aquí (privados, service_role); nunca en la configuración versionada, reportes ni artefactos.
begin;
create table if not exists public.panel_contactos (
 cliente_id uuid primary key,
 telefono text not null check (telefono ~ '^\+[1-9][0-9]{7,14}$'),
 nombre_saludo text not null default '' check (length(nombre_saludo) <= 60),
 consentimiento boolean not null default false,
 actualizado_en timestamptz not null default now()
);
create table if not exists public.panel_borradores (
 id uuid primary key default gen_random_uuid(),
 fecha date not null,
 cliente_id uuid not null,
 texto text not null check (length(texto) <= 4000),
 vacantes jsonb not null default '[]'::jsonb check (jsonb_typeof(vacantes) = 'array'),
 cargos jsonb not null default '[]'::jsonb check (jsonb_typeof(cargos) = 'array'),
 estado text not null default 'pendiente' check (estado in ('pendiente','abierto','enviado','descartado')),
 editado boolean not null default false,
 creado_en timestamptz not null default now(),
 actualizado_en timestamptz not null default now(),
 unique (fecha, cliente_id)
);
create index if not exists panel_borradores_cliente on public.panel_borradores(cliente_id, fecha desc);
alter table public.panel_contactos enable row level security;
alter table public.panel_borradores enable row level security;
revoke all on public.panel_contactos, public.panel_borradores from public, anon, authenticated;
grant all on public.panel_contactos, public.panel_borradores to service_role;
commit;
