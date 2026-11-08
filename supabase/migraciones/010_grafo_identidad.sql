-- Resolver aliases sin joins repetidos sobre una CTE materializada y evitar escrituras sin cambios.
begin;
create or replace function public.reconciliar_ofertas() returns jsonb
language plpgsql security definer set search_path='' as $$
declare mapa jsonb; grafo jsonb; resueltas jsonb; r record; archivadas integer:=0; referencias boolean; raices jsonb; hay_ciclo boolean; falta_principal boolean;
begin
 perform pg_advisory_xact_lock(hashtextextended('adaptia.ofertas.unicas',0));
 select exists(select 1 from pg_constraint where contype='f' and confrelid='public.ofertas'::regclass) into referencias;
 -- Extraer una vez los metadatos; no recorrer una CTE sin índices por cada paso de cada identidad.
 with metadatos as materialized (
  select id,nullif(datos->>'duplicada_de','') siguiente,
   case when jsonb_typeof(datos->'ids_agrupados')='array' then datos->'ids_agrupados' else '[]'::jsonb end agrupados
  from public.catalogo_vacantes
 ), aliases as (
  select u.id origen,min(c.id) destino,count(distinct c.id) n
  from metadatos c cross join lateral jsonb_array_elements_text(c.agrupados) u(id)
  where c.id<>u.id and c.siguiente is null group by u.id
 )
 select coalesce(jsonb_object_agg(c.id,jsonb_build_array(
   coalesce(c.siguiente,case when a.n=1 then a.destino end),c.siguiente is not null)),'{}')
 into grafo from metadatos c left join aliases a on a.origen=c.id;
 -- JSONB busca por clave. Las identidades sin arista ya están resueltas y no entran en la recursión.
 select coalesce(jsonb_object_agg(key,key),'{}') into raices from jsonb_each(grafo);
 with recursive recorrido(origen,actual,siguiente,camino,explicitas,profundidad,ciclo,existe) as (
  select key,key,value->>0,array[key],
   case when (value->>1)::boolean then array[key] else '{}'::text[] end,0,false,true
  from jsonb_each(grafo) where value->>0 is not null
  union all
  select cam.origen,cam.siguiente,grafo->cam.siguiente->>0,cam.camino||cam.siguiente,
   cam.explicitas||case when (grafo->cam.siguiente->>1)::boolean then array[cam.siguiente] else '{}'::text[] end,
   cam.profundidad+1,cam.siguiente=any(cam.camino),grafo ? cam.siguiente
  from recorrido cam where cam.siguiente is not null and cam.profundidad<20 and not cam.ciclo
 ), terminales as (
  select distinct on(origen) * from recorrido order by origen,profundidad desc
 )
 select coalesce(jsonb_object_agg(t.origen,case when t.ciclo then
    (select min(x) from unnest(t.camino[array_position(t.camino,t.actual):array_length(t.camino,1)-1]) x)
    else t.actual end),'{}'),
  coalesce(bool_or((t.ciclo and
    t.camino[array_position(t.camino,t.actual):array_length(t.camino,1)-1] && t.explicitas)
    or (not t.ciclo and t.profundidad=20 and t.siguiente is not null)),false),
  coalesce(bool_or(not t.existe),false)
 into resueltas,hay_ciclo,falta_principal from terminales t;
 raices:=raices||resueltas;
 if hay_ciclo then raise exception 'Ciclo de identidades o cadena demasiado larga'; end if;
 if falta_principal then raise exception 'La identidad principal todavía no está sincronizada'; end if;
 with destinos as (
  select o.id,coalesce((
   select case when count(distinct candidatos.principal)=1 then min(candidatos.principal) end
   from (
    select raices->>c.id principal from public.catalogo_vacantes c
     where public.adaptia_urls_identidad(c.datos) @> array[public.adaptia_url_identidad(o.offer_url)]
    union all
    select raices->>e.vacante_id from public.entregas_diarias e
     where public.adaptia_urls_identidad(e.snapshot) @> array[public.adaptia_url_identidad(o.offer_url)]
   ) candidatos),raices->>o.vacante_id) principal
  from public.ofertas o
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
 with cambios as materialized (
 select o.id,m.value principal,(select public.adaptia_enlaces_unicos(jsonb_agg(u.url)) from (
   select c.datos->>'enlace' url from public.catalogo_vacantes c where c.id=m.value
   union all select c.datos->>'enlace_directo' from public.catalogo_vacantes c where c.id=m.value
   union all select jsonb_array_elements_text(c.datos->'enlaces_alternativos')
    from public.catalogo_vacantes c where c.id=m.value and jsonb_typeof(c.datos->'enlaces_alternativos')='array'
   union all select h.fila_original->>'offer_url' from public.ofertas_enlaces_historicos h where h.vacante_id=m.value
   union all select o.offer_url) u where coalesce(u.url,'')<>'') enlaces
 from public.ofertas o join jsonb_each_text(mapa) m on m.key=o.id::text
 )
 update public.ofertas o set vacante_id=c.principal,enlaces_alternativos=c.enlaces
 from cambios c where c.id=o.id and
  (o.vacante_id is distinct from c.principal or o.enlaces_alternativos is distinct from c.enlaces);
 return jsonb_build_object('archivadas',archivadas,'filas_unicas',(select count(*) from public.ofertas),
  'sin_identificar',(select count(*) from public.ofertas where vacante_id is null));
end;
$$;

select public.reconciliar_ofertas();
commit;
