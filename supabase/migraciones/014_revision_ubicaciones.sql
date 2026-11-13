-- Contrato v16: bandeja «Por confirmar» (vacantes cuya ubicación no se pudo confirmar sola y que le servirían a algún
-- cliente) y reglas de ubicación decididas por el operador. Privadas: solo la credencial de servicio.
begin;
create table if not exists public.panel_revisiones (
 vacante_id text primary key references public.catalogo_vacantes(id) on delete restrict,
 estado text not null default 'pendiente' check (estado in ('pendiente','confirmada','descartada','saltada','vencida')),
 motivo text not null default '' check (length(motivo) <= 200),
 pista text not null default '' check (length(pista) <= 600),
 ubicacion text not null default '' check (length(ubicacion) <= 300),
 sugerencia jsonb not null default '[]'::jsonb check (jsonb_typeof(sugerencia) = 'array'),
 paises jsonb not null default '[]'::jsonb check (jsonb_typeof(paises) = 'array'),
 perfiles jsonb not null default '[]'::jsonb check (jsonb_typeof(perfiles) = 'array'),
 prioridad integer not null default 0,
 creada_en timestamptz not null default now(),
 decidida_en timestamptz,
 actualizada_en timestamptz not null default now()
);
create index if not exists panel_revisiones_pendientes on public.panel_revisiones(estado, prioridad desc);
create index if not exists panel_revisiones_ubicacion on public.panel_revisiones(ubicacion);
create table if not exists public.panel_reglas_ubicacion (
 texto text primary key check (length(texto) between 2 and 300),
 resultado jsonb not null check (jsonb_typeof(resultado) = 'object'),
 origen text not null check (origen in ('operador','aprendida')),
 activa boolean not null default true,
 usos integer not null default 0,
 conflictos integer not null default 0,
 ejemplos jsonb not null default '[]'::jsonb check (jsonb_typeof(ejemplos) = 'array'),
 creada_en timestamptz not null default now(),
 actualizada_en timestamptz not null default now()
);
alter table public.panel_revisiones enable row level security;
alter table public.panel_reglas_ubicacion enable row level security;
revoke all on public.panel_revisiones, public.panel_reglas_ubicacion from public, anon, authenticated;
grant all on public.panel_revisiones, public.panel_reglas_ubicacion to service_role;
commit;
