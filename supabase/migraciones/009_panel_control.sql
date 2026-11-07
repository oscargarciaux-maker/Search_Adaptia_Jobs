-- Configuración y resultados privados del operador. Sin acceso anónimo o autenticado directo.
begin;
create table if not exists public.panel_configuracion (
 id text primary key default 'principal' check(id='principal'), revision integer not null default 0,
 borrador jsonb not null default '{"clientes":[],"cargos":[],"perfiles":[]}'::jsonb,
 actualizada_en timestamptz not null default now()
);
create table if not exists public.panel_versiones (
 revision integer primary key, vigente_desde date not null, configuracion jsonb not null,
 creada_en timestamptz not null default now()
);
create table if not exists public.panel_ejecuciones (
 id uuid primary key default gen_random_uuid(), fecha date not null unique,
 revision integer not null references public.panel_versiones(revision) on delete restrict,
 estado text not null default 'en_curso' check(estado in ('en_curso','completa','parcial','fallida')),
 resumen jsonb not null default '{}'::jsonb, iniciada_en timestamptz not null default now(), terminada_en timestamptz
);
create table if not exists public.panel_asignaciones (
 id uuid primary key default gen_random_uuid(),
 ejecucion_id uuid not null references public.panel_ejecuciones(id) on delete restrict,
 cliente_id uuid not null, perfil_id uuid not null, cargo_id uuid not null,
 vacante_id text not null references public.catalogo_vacantes(id) on delete restrict,
 match_grade text not null check(match_grade in ('exact','similar','close')),
 explicacion jsonb not null, filtros jsonb not null, cargo_configuracion jsonb not null,
 creada_en timestamptz not null default now(), unique(ejecucion_id,perfil_id,vacante_id)
);
create index if not exists panel_asignaciones_cliente on public.panel_asignaciones(cliente_id,ejecucion_id);
create index if not exists panel_versiones_vigencia on public.panel_versiones(vigente_desde desc,revision desc);
alter table public.panel_configuracion enable row level security;
alter table public.panel_versiones enable row level security;
alter table public.panel_ejecuciones enable row level security;
alter table public.panel_asignaciones enable row level security;
revoke all on public.panel_configuracion,public.panel_versiones,public.panel_ejecuciones,public.panel_asignaciones
 from public,anon,authenticated;
grant all on public.panel_configuracion,public.panel_versiones,public.panel_ejecuciones,public.panel_asignaciones to service_role;

create or replace function public.panel_guardar(p_revision integer,p_configuracion jsonb) returns jsonb
language plpgsql security definer set search_path='' as $$
declare nueva integer;
begin
 if jsonb_typeof(p_configuracion->'clientes') is distinct from 'array' or jsonb_typeof(p_configuracion->'cargos') is distinct from 'array'
  or jsonb_typeof(p_configuracion->'perfiles') is distinct from 'array' then raise exception 'Configuración incompleta'; end if;
 if (select coalesce(sum((c->>'cupo')::integer),0) from jsonb_array_elements(p_configuracion->'cargos') c
  where (c->>'activo')::boolean)>120 then raise exception 'Los cupos superan 120'; end if;
 insert into public.panel_configuracion(id) values('principal') on conflict do nothing;
 update public.panel_configuracion set revision=revision+1,borrador=p_configuracion,actualizada_en=now()
 where id='principal' and revision=p_revision returning revision into nueva;
 if nueva is null then raise exception using errcode='40001',message='La configuración cambió; vuelve a cargarla'; end if;
 return jsonb_build_object('revision',nueva,'borrador',p_configuracion);
end;
$$;

create or replace function public.panel_publicar(p_revision integer) returns jsonb
language plpgsql security definer set search_path='' as $$
declare cfg jsonb; efectiva date;
begin
 select borrador into cfg from public.panel_configuracion where id='principal' and revision=p_revision for update;
 if cfg is null then raise exception using errcode='40001',message='La configuración cambió; vuelve a cargarla'; end if;
 if (select coalesce(sum((c->>'cupo')::integer),0) from jsonb_array_elements(cfg->'cargos') c
  where (c->>'activo')::boolean)<>120 then raise exception 'Reparte exactamente 120 vacantes'; end if;
 if exists(select 1 from jsonb_array_elements(cfg->'cargos') c where (c->>'activo')::boolean and (c->>'cupo')::integer>0
  and not exists(select 1 from jsonb_array_elements(cfg->'perfiles') p
   join jsonb_array_elements(cfg->'clientes') cl on cl->>'id'=p->>'cliente_id'
   where p->>'cargo_id'=c->>'id' and (p->>'activo')::boolean and (cl->>'activo')::boolean)) then
  raise exception 'Cada cargo necesita un perfil activo'; end if;
 efectiva:=((now() at time zone 'America/Bogota')::date+1);
 insert into public.panel_versiones(revision,vigente_desde,configuracion) values(p_revision,efectiva,cfg)
 on conflict(revision) do nothing;
 select vigente_desde into efectiva from public.panel_versiones where revision=p_revision;
 return jsonb_build_object('revision',p_revision,'vigente_desde',efectiva);
end;
$$;
revoke all on function public.panel_guardar(integer,jsonb),public.panel_publicar(integer) from public,anon,authenticated;
grant execute on function public.panel_guardar(integer,jsonb),public.panel_publicar(integer) to service_role;
notify pgrst,'reload schema';
commit;
