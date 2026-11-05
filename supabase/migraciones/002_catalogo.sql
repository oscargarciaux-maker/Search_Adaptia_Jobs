-- Migración aditiva del contrato de catálogo v2. Ejecutar tras supabase/esquema.sql.
-- No altera ni borra public.ofertas. Ejecutar en SQL Editor con permisos administrativos.
begin;

create table if not exists public.catalogo_vacantes (
  id text primary key check (id ~ '^[a-f0-9]{16}$'),
  contract_version text not null default 'v2' check (contract_version = 'v2'),
  datos jsonb not null,
  description_full text check (char_length(description_full) <= 30000),
  published_at timestamptz,
  first_seen_at timestamptz,
  last_seen_at timestamptz,
  observed_at timestamptz not null,
  status text not null check (status in ('active', 'closed', 'archived')),
  closed_at timestamptz,
  reason text
);

create index if not exists catalogo_activo_fecha on public.catalogo_vacantes
  (published_at desc nulls last, first_seen_at desc) where status = 'active';

create table if not exists public.entregas_diarias (
  vacante_id text primary key references public.catalogo_vacantes(id) on delete restrict,
  delivery_date date not null,
  role_id text not null,
  match_grade text not null check (match_grade in ('exact', 'similar', 'close')),
  selected_at timestamptz not null,
  snapshot jsonb not null
);
create index if not exists entregas_diarias_fecha_rol on public.entregas_diarias(delivery_date, role_id);
alter table public.entregas_diarias enable row level security;
revoke all on public.entregas_diarias from anon, authenticated;
grant select, insert on public.entregas_diarias to service_role;

create or replace function public.conservar_historia_catalogo() returns trigger
language plpgsql set search_path = '' as $$
begin
  if new.observed_at < old.observed_at then return old; end if;
  new.first_seen_at := least(old.first_seen_at, new.first_seen_at);
  new.last_seen_at := greatest(old.last_seen_at, new.last_seen_at);
  if old.status = 'closed' and new.status = 'active'
     and (new.last_seen_at is null or new.last_seen_at <= old.closed_at) then
    new.status := old.status;
    new.closed_at := old.closed_at;
    new.reason := old.reason;
  end if;
  return new;
end;
$$;

drop trigger if exists conservar_historia on public.catalogo_vacantes;
create trigger conservar_historia before update on public.catalogo_vacantes
for each row execute function public.conservar_historia_catalogo();

alter table public.catalogo_vacantes enable row level security;
revoke all on public.catalogo_vacantes from anon, authenticated;
grant select, insert, update on public.catalogo_vacantes to service_role;
revoke all on function public.conservar_historia_catalogo() from public;

notify pgrst, 'reload schema';
commit;
