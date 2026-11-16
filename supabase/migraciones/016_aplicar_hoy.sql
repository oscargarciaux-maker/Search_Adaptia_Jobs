-- Contrato v27: «Aplicar hoy». El borrador rige desde hoy (fecha de Bogotá) para las búsquedas que falten hoy: la
-- manual, la segunda pasada y las horarias. No toca lo ya entregado ni las asignaciones guardadas. Si la búsqueda de
-- hoy ya existe y terminó, pasa a la versión nueva y anota la anterior en su resumen; si sigue corriendo (iniciada hace
-- menos de 160 min, el tope del flujo), se rechaza para que conserve su versión. Sin tablas nuevas; 009 y 015 no cambian.
begin;
create or replace function public.panel_publicar_hoy(p_revision integer) returns jsonb
language plpgsql security definer set search_path='' as $$
declare cfg jsonb; dia date; techo integer; total integer; ejec record; hay boolean;
begin
 select borrador into cfg from public.panel_configuracion where id='principal' and revision=p_revision for update;
 if cfg is null then raise exception using errcode='40001',message='La configuración cambió; vuelve a cargarla'; end if;
 techo:=coalesce((cfg->>'techo_diario')::integer,120);
 select coalesce(sum((c->>'cupo')::integer),0) into total from jsonb_array_elements(cfg->'cargos') c
  where (c->>'activo')::boolean;
 if total<1 then raise exception 'Da una meta diaria a algún perfil antes de aplicar'; end if;
 if total>techo then raise exception 'Las metas superan el techo diario'; end if;
 if exists(select 1 from jsonb_array_elements(cfg->'cargos') c where (c->>'activo')::boolean and (c->>'cupo')::integer>0
  and not exists(select 1 from jsonb_array_elements(cfg->'perfiles') p
   join jsonb_array_elements(cfg->'clientes') cl on cl->>'id'=p->>'cliente_id'
   where p->>'cargo_id'=c->>'id' and (p->>'activo')::boolean and (cl->>'activo')::boolean)) then
  raise exception 'Cada cargo necesita un perfil activo'; end if;
 dia:=(now() at time zone 'America/Bogota')::date;
 select id,estado,revision,iniciada_en into ejec from public.panel_ejecuciones where fecha=dia for update;
 hay:=found;
 if hay and ejec.estado='en_curso' and ejec.iniciada_en>now()-interval '160 minutes' then
  raise exception 'Hay una búsqueda en curso; espera a que termine para aplicar hoy'; end if;
 insert into public.panel_versiones(revision,vigente_desde,configuracion) values(p_revision,dia,cfg)
 on conflict(revision) do update set vigente_desde=least(public.panel_versiones.vigente_desde,excluded.vigente_desde);
 if hay and ejec.revision<>p_revision then
  update public.panel_ejecuciones set revision=p_revision,
   resumen=resumen||jsonb_build_object('revisiones_anteriores',
    coalesce(resumen->'revisiones_anteriores','[]'::jsonb)||to_jsonb(ejec.revision))
  where id=ejec.id;
 end if;
 return jsonb_build_object('revision',p_revision,'vigente_desde',dia);
end;
$$;
revoke all on function public.panel_publicar_hoy(integer) from public,anon,authenticated;
grant execute on function public.panel_publicar_hoy(integer) to service_role;
notify pgrst,'reload schema';
commit;
