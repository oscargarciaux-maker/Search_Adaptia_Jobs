-- Contrato v21: metas diarias por perfil y techo diario editable. El cupo de cada cargo lo calcula el panel con las
-- metas de sus perfiles; ya no hace falta repartir exactamente 120. Reemplaza solo las comprobaciones de 009 (sin
-- tablas nuevas): el techo va de 1 a 600 (120 si la configuración no lo trae); un borrador puede pasarlo mientras se
-- edita, pero para programar la suma de cupos activos va de 1 al techo.
begin;
create or replace function public.panel_guardar(p_revision integer,p_configuracion jsonb) returns jsonb
language plpgsql security definer set search_path='' as $$
declare nueva integer; techo integer;
begin
 if jsonb_typeof(p_configuracion->'clientes') is distinct from 'array' or jsonb_typeof(p_configuracion->'cargos') is distinct from 'array'
  or jsonb_typeof(p_configuracion->'perfiles') is distinct from 'array' then raise exception 'Configuración incompleta'; end if;
 techo:=coalesce((p_configuracion->>'techo_diario')::integer,120);
 if techo<1 or techo>600 then raise exception 'El techo diario va de 1 a 600'; end if;
 insert into public.panel_configuracion(id) values('principal') on conflict do nothing;
 update public.panel_configuracion set revision=revision+1,borrador=p_configuracion,actualizada_en=now()
 where id='principal' and revision=p_revision returning revision into nueva;
 if nueva is null then raise exception using errcode='40001',message='La configuración cambió; vuelve a cargarla'; end if;
 return jsonb_build_object('revision',nueva,'borrador',p_configuracion);
end;
$$;

create or replace function public.panel_publicar(p_revision integer) returns jsonb
language plpgsql security definer set search_path='' as $$
declare cfg jsonb; efectiva date; techo integer; total integer;
begin
 select borrador into cfg from public.panel_configuracion where id='principal' and revision=p_revision for update;
 if cfg is null then raise exception using errcode='40001',message='La configuración cambió; vuelve a cargarla'; end if;
 techo:=coalesce((cfg->>'techo_diario')::integer,120);
 select coalesce(sum((c->>'cupo')::integer),0) into total from jsonb_array_elements(cfg->'cargos') c
  where (c->>'activo')::boolean;
 if total<1 then raise exception 'Da una meta diaria a algún perfil antes de programar'; end if;
 if total>techo then raise exception 'Las metas superan el techo diario'; end if;
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
