-- Ejecutar tras SQL 001–004, solo en PostgreSQL aislado. Todo se revierte.
begin;
insert into public.catalogo_vacantes(id,datos,observed_at,status)
select lpad(n::text,16,'b'),jsonb_build_object('titulo','QA Engineer','empresa','Ensayo',
 'rol_entrega_actual',case when n=5 then '' else 'qa' end,
 'enlace','https://jobs.lever.co/acme/'||n,
 'verificacion',jsonb_build_object('estado','verificada','enlaces',jsonb_build_array(jsonb_build_object(
 'url',case when n=7 then 'https://jobs.lever.co/otra/1' else 'https://jobs.lever.co/acme/'||n end,
 'estado','verificada','comprobada_en',case when n=2 then to_char(now()-interval '7 hours','YYYY-MM-DD"T"HH24:MI:SS"Z"')
 when n=6 then 'now' when n=8 then '2026-02-31T00:00:00Z'
 when n=9 then to_char(now()+interval '1 hour','YYYY-MM-DD"T"HH24:MI:SS"Z"')
 else to_char(now(),'YYYY-MM-DD"T"HH24:MI:SS"Z"') end)))),now(),
 case when n=3 then 'closed' when n=4 then 'archived' else 'active' end
from generate_series(1,9) n;
insert into public.entregas_diarias(vacante_id,delivery_date,role_id,match_grade,selected_at,snapshot)
select lpad(n::text,16,'b'),current_date,'qa','exact',now(),'{"titulo":"QA histórico"}' from generate_series(1,9) n;
insert into public.ofertas(external_id,job_title,company_name,status)
values('historico-v4','QA histórico','Ensayo','active');

set local role service_role;
do $$
begin
 if (select estado_actual from public.seleccion_estado_actual where vacante_id=lpad('1',16,'b')) <> 'lista'
 then raise exception 'Se perdió enlace vigente'; end if;
 if (select listas_ahora from public.resumen_entregas_actual where role_id='qa' and delivery_date=current_date) <> 1
 then raise exception 'Se aprobaron enlaces caducados, ajenos o fechas incorrectas'; end if;
 if (select retiradas from public.resumen_entregas_actual where role_id='qa' and delivery_date=current_date) <> 2
 then raise exception 'Un cierre no se reflejó en la selección'; end if;
 if (select revisar_afinidad from public.resumen_entregas_actual where role_id='qa' and delivery_date=current_date) <> 1
 then raise exception 'Se contó cargo fuera de perfil'; end if;
 if exists(select 1 from public.seleccion_estado_actual where estado_actual <> 'lista' and url_utilizable is not null)
 then raise exception 'Se expuso enlace no apto'; end if;
end;
$$;
reset role;
do $$
begin
 if has_table_privilege('anon','public.seleccion_estado_actual','SELECT') or
    has_table_privilege('authenticated','public.resumen_entregas_actual','SELECT')
 then raise exception 'Las vistas tienen acceso público'; end if;
 if (select snapshot->>'titulo' from public.entregas_diarias where vacante_id=lpad('3',16,'b')) <> 'QA histórico' or
    (select status from public.ofertas where external_id='historico-v4') <> 'active'
 then raise exception 'Se reescribió el histórico'; end if;
end;
$$;
rollback;
