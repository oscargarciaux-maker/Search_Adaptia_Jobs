-- Resolver identidades una vez por catálogo evita exceder el tiempo de RPC. No cambia el contrato ni elimina archivo.
begin;
create or replace function public.reconciliar_ofertas() returns jsonb
language plpgsql security definer set search_path='' as $$
declare mapa jsonb; r record; archivadas integer:=0; referencias boolean; raices jsonb; hay_ciclo boolean; falta_principal boolean;
begin
 perform pg_advisory_xact_lock(hashtextextended('adaptia.ofertas.unicas',0));
 select exists(select 1 from pg_constraint where contype='f' and confrelid='public.ofertas'::regclass) into referencias;
 with recursive aliases as materialized (
  select u.id origen,min(c.id) destino,count(distinct c.id) n
  from public.catalogo_vacantes c cross join lateral jsonb_array_elements_text(
   case when jsonb_typeof(c.datos->'ids_agrupados')='array' then c.datos->'ids_agrupados' else '[]'::jsonb end) u(id)
  where c.id<>u.id and coalesce(c.datos->>'duplicada_de','')=''
  group by u.id
 ), aristas as materialized (
  select c.id,coalesce(nullif(c.datos->>'duplicada_de',''),case when a.n=1 then a.destino end) siguiente
  from public.catalogo_vacantes c left join aliases a on a.origen=c.id
 ), recorrido(origen,actual,camino,profundidad,ciclo) as (
  select id,id,array[id],0,false from aristas
  union all
  select cam.origen,a.siguiente,cam.camino||a.siguiente,cam.profundidad+1,a.siguiente=any(cam.camino)
  from recorrido cam join aristas a on a.id=cam.actual
  where a.siguiente is not null and cam.profundidad<20 and not cam.ciclo
 ), terminales as (
  select distinct on(origen) origen,actual,profundidad,ciclo from recorrido order by origen,profundidad desc
 )
 select coalesce(jsonb_object_agg(t.origen,t.actual),'{}'),
  coalesce(bool_or(t.ciclo or (t.profundidad=20 and a.siguiente is not null)),false),
  coalesce(bool_or(a.id is null),false)
 into raices,hay_ciclo,falta_principal
 from terminales t left join aristas a on a.id=t.actual;
 if hay_ciclo then raise exception 'Ciclo de identidades o cadena demasiado larga'; end if;
 if falta_principal then raise exception 'La identidad principal todavía no está sincronizada'; end if;
 with enlaces as (
  select c.id,u.url from public.catalogo_vacantes c cross join lateral jsonb_array_elements_text(
    jsonb_build_array(c.datos->>'enlace',c.datos->>'enlace_directo')||
    case when jsonb_typeof(c.datos->'enlaces_alternativos')='array' then c.datos->'enlaces_alternativos' else '[]'::jsonb end) u(url)
  union all
  select e.vacante_id,u.url from public.entregas_diarias e cross join lateral jsonb_array_elements_text(
    jsonb_build_array(e.snapshot->>'enlace',e.snapshot->>'enlace_directo')||
    case when jsonb_typeof(e.snapshot->'_enlaces')='array' then e.snapshot->'_enlaces' else '[]'::jsonb end) u(url)
 ), identificadas as (
  select public.adaptia_url_identidad(url) url,min((raices->>id)) id,
         count(distinct (raices->>id)) n
  from enlaces where coalesce(url,'')<>'' group by public.adaptia_url_identidad(url)
 ), destinos as (
  select o.id,coalesce(case when i.n=1 then i.id end,
         (raices->>o.vacante_id)) principal
  from public.ofertas o left join identificadas i on i.url=public.adaptia_url_identidad(o.offer_url)
 )
 select coalesce(jsonb_object_agg(id::text,principal),'{}') into mapa from destinos where principal is not null;
 for r in
  select o.id,m.value principal,to_jsonb(o) original,
         row_number() over(partition by m.value order by o.id) posicion
  from public.ofertas o join jsonb_each_text(mapa) m on m.key=o.id::text
 loop
  if r.posicion>1 then
   if referencias then raise exception 'Hay referencias a ofertas históricas; conservarlas y planificar sus aliases antes de consolidar'; end if;
   insert into public.ofertas_enlaces_historicos(oferta_id,vacante_id,fila_original)
    values(r.id,r.principal,r.original) on conflict(oferta_id) do nothing;
   if not exists(select 1 from public.ofertas_enlaces_historicos h where h.oferta_id=r.id and h.fila_original=r.original) then
    raise exception 'El archivo histórico no coincide; no se retira ninguna fila'; end if;
   delete from public.ofertas where id=r.id;
   archivadas:=archivadas+1;
  end if;
 end loop;
 update public.ofertas o set vacante_id=m.value,
 enlaces_alternativos=(select public.adaptia_enlaces_unicos(jsonb_agg(u.url)) from (
   select c.datos->>'enlace' url from public.catalogo_vacantes c where c.id=m.value
   union all select c.datos->>'enlace_directo' from public.catalogo_vacantes c where c.id=m.value
   union all select jsonb_array_elements_text(c.datos->'enlaces_alternativos')
    from public.catalogo_vacantes c where c.id=m.value and jsonb_typeof(c.datos->'enlaces_alternativos')='array'
   union all select h.fila_original->>'offer_url' from public.ofertas_enlaces_historicos h where h.vacante_id=m.value
   union all select o.offer_url) u where coalesce(u.url,'')<>'')
 from jsonb_each_text(mapa) m where m.key=o.id::text and o.vacante_id is distinct from m.value;
 return jsonb_build_object('archivadas',archivadas,'filas_unicas',(select count(*) from public.ofertas),
  'sin_identificar',(select count(*) from public.ofertas where vacante_id is null));
end;
$$;

select public.reconciliar_ofertas();
commit;
