-- Reconciliar por lotes cortos en vez de recorrer todas las ofertas en una sola llamada (57014 del 27 nov).
-- SQL 011 rehacía en cada llamada el trabajo de TODAS las ofertas (unas 6.000 y +250-350 por día) y de todas las
-- referencias explícitas del catálogo; con el volumen actual rozaba el límite de 8 s de la API. Aquí cada llamada
-- trabaja con un lote fijo (500 ofertas o 5.000 referencias) y devuelve dónde seguir. Mismas aristas, mismos rechazos
-- (ciclos explícitos, principales ausentes, cadenas largas), mismo archivo y mismas escrituras solo si cambian.
-- Cada lote es una transacción propia e idempotente. `reconciliar_ofertas()` se conserva: recorre todos los lotes
-- en una sola transacción (instalador y diagnóstico) y da el mismo resultado que 011. No crea tablas ni columnas.
begin;
-- Recorrer las referencias explícitas en orden de id sin leerlas todas en cada lote.
create index if not exists catalogo_referencias_explicitas on public.catalogo_vacantes(id)
 where nullif(datos->>'duplicada_de','') is not null;
analyze public.catalogo_vacantes;

-- El mismo recorrido de 011, desde las semillas dadas: raíz de cada una y si hay ciclo explícito, cadena de más de 20
-- eslabones o una principal que todavía no está en el catálogo.
create or replace function public.adaptia_raices_identidad(semillas text[],
 out raices jsonb, out hay_ciclo boolean, out falta_principal boolean)
language sql stable set search_path='' set jit=off as $$
 with recursive recorrido(origen,actual,siguiente,camino,explicitas,profundidad,ciclo,existe) as (
  select s.id,s.id,p.siguiente,array[s.id],case when p.explicita then array[s.id] else '{}'::text[] end,0,false,true
  from unnest(semillas) s(id) cross join lateral (
   select coalesce(nullif(c.datos->>'duplicada_de',''),(
     select case when count(distinct a.id)=1 then min(a.id) end from public.catalogo_vacantes a
     where a.datos->'ids_agrupados' ? c.id and jsonb_typeof(a.datos->'ids_agrupados')='array'
      and a.id<>c.id and nullif(a.datos->>'duplicada_de','') is null)) siguiente,
    nullif(c.datos->>'duplicada_de','') is not null explicita
   from public.catalogo_vacantes c where c.id=s.id) p
  union all
  select cam.origen,cam.siguiente,p.siguiente,cam.camino||cam.siguiente,
   cam.explicitas||case when p.explicita then array[cam.siguiente] else '{}'::text[] end,
   cam.profundidad+1,cam.siguiente=any(cam.camino),p.existe
  from recorrido cam cross join lateral (
   select case when c.id is not null then coalesce(nullif(c.datos->>'duplicada_de',''),(
     select case when count(distinct a.id)=1 then min(a.id) end from public.catalogo_vacantes a
     where a.datos->'ids_agrupados' ? c.id and jsonb_typeof(a.datos->'ids_agrupados')='array'
      and a.id<>c.id and nullif(a.datos->>'duplicada_de','') is null)) end siguiente,
    coalesce(nullif(c.datos->>'duplicada_de','') is not null,false) explicita,
    c.id is not null existe
   from (select cam.siguiente nodo) n left join public.catalogo_vacantes c on c.id=n.nodo) p
  where cam.siguiente is not null and cam.profundidad<20 and not cam.ciclo
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
 from terminales t;
$$;

-- Comprobar un tramo de las referencias explícitas del catálogo (aunque no toquen ninguna oferta). Solo lee.
create or replace function public.reconciliar_referencias_lote(desde text default '', limite integer default 5000)
returns jsonb language plpgsql security definer set search_path='' set jit=off as $$
declare lote text[]; v record;
begin
 if limite is null or limite<1 or limite>20000 then raise exception 'Lote de referencias fuera de rango'; end if;
 select coalesce(array_agg(id order by id),'{}') into lote from (
  select c.id from public.catalogo_vacantes c
  where nullif(c.datos->>'duplicada_de','') is not null and c.id>coalesce(desde,'') order by c.id limit limite) s;
 select * into v from public.adaptia_raices_identidad(lote);
 if v.hay_ciclo then raise exception 'Ciclo de identidades o cadena demasiado larga'; end if;
 if v.falta_principal then raise exception 'La identidad principal todavía no está sincronizada'; end if;
 return jsonb_build_object('revisadas',cardinality(lote),
  'siguiente',case when cardinality(lote)=limite then lote[limite] end);
end;
$$;

-- Consolidar un lote de ofertas (id > desde, en orden). Se suman al trabajo las ofertas que ya ocupan alguna de las
-- principales del lote, para decidir con todas a la vista: queda la de menor id, como en 011. Recorrer los lotes en
-- orden da el mismo estado final que 011 de una vez.
create or replace function public.reconciliar_ofertas_lote(desde bigint default 0, limite integer default 500)
returns jsonb language plpgsql security definer set search_path='' set jit=off as $$
declare lote bigint[]; trabajo bigint[]; nuevas bigint[]; semillas text[]; v record; mapa jsonb:='{}';
 r record; archivadas integer:=0; referencias boolean;
begin
 if limite is null or limite<1 or limite>5000 then raise exception 'Lote de ofertas fuera de rango'; end if;
 perform pg_advisory_xact_lock(hashtextextended('adaptia.ofertas.unicas',0));
 select exists(select 1 from pg_constraint where contype='f' and confrelid='public.ofertas'::regclass) into referencias;
 select coalesce(array_agg(id order by id),'{}') into lote from (
  select o.id from public.ofertas o where o.id>coalesce(desde,0) order by o.id limit limite) s;
 trabajo:=lote; nuevas:=lote;
 while cardinality(nuevas)>0 loop
  -- Semillas como en 011: la vacante de cada oferta y las que comparten su enlace (índices GIN).
  with semillas as (
   select o.vacante_id id from public.ofertas o where o.id=any(nuevas) and o.vacante_id is not null
   union select c.id from public.ofertas o join public.catalogo_vacantes c
    on public.adaptia_urls_identidad(c.datos) @> array[public.adaptia_url_identidad(o.offer_url)] where o.id=any(nuevas)
   union select e.vacante_id from public.ofertas o join public.entregas_diarias e
    on public.adaptia_urls_identidad(e.snapshot) @> array[public.adaptia_url_identidad(o.offer_url)] where o.id=any(nuevas)
  )
  select coalesce(array_agg(c.id),'{}') into semillas from semillas s join public.catalogo_vacantes c on c.id=s.id;
  select * into v from public.adaptia_raices_identidad(semillas);
  if v.hay_ciclo then raise exception 'Ciclo de identidades o cadena demasiado larga'; end if;
  if v.falta_principal then raise exception 'La identidad principal todavía no está sincronizada'; end if;
  with destinos as (
   select o.id,coalesce((
    select case when count(distinct candidatos.principal)=1 then min(candidatos.principal) end
    from (
     select v.raices->>c.id principal from public.catalogo_vacantes c
      where public.adaptia_urls_identidad(c.datos) @> array[public.adaptia_url_identidad(o.offer_url)]
     union all
     select v.raices->>e.vacante_id from public.entregas_diarias e
      where public.adaptia_urls_identidad(e.snapshot) @> array[public.adaptia_url_identidad(o.offer_url)]
    ) candidatos),v.raices->>o.vacante_id) principal
   from public.ofertas o where o.id=any(nuevas)
  )
  select mapa||coalesce(jsonb_object_agg(id::text,principal),'{}') into mapa from destinos where principal is not null;
  -- Ofertas fuera del trabajo que ya ocupan una de estas principales (índice único ofertas_por_vacante).
  select coalesce(array_agg(o.id),'{}') into nuevas from public.ofertas o
  where o.vacante_id in (select m.value from jsonb_each_text(mapa) m) and not o.id=any(trabajo);
  trabajo:=trabajo||nuevas;
 end loop;
 for r in
  select o.id,m.value principal,to_jsonb(o) original,
         row_number() over(partition by m.value order by o.id) posicion
  from public.ofertas o join jsonb_each_text(mapa) m on m.key=o.id::text where o.id=any(trabajo)
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
 from public.ofertas o join jsonb_each_text(mapa) m on m.key=o.id::text where o.id=any(trabajo)
 )
 update public.ofertas o set vacante_id=c.principal,enlaces_alternativos=c.enlaces
 from cambios c where c.id=o.id and
  (o.vacante_id is distinct from c.principal or o.enlaces_alternativos is distinct from c.enlaces);
 return jsonb_build_object('archivadas',archivadas,
  'siguiente',case when cardinality(lote)=limite then lote[limite] end,
  'filas_unicas',(select count(*) from public.ofertas),
  'sin_identificar',(select count(*) from public.ofertas where vacante_id is null));
end;
$$;

-- Todo de una vez, en una sola transacción, para el instalador y el diagnóstico (sin límite de la API).
create or replace function public.reconciliar_ofertas() returns jsonb
language plpgsql security definer set search_path='' set jit=off as $$
declare r jsonb; cursor_referencias text:=''; cursor_ofertas bigint:=0; archivadas integer:=0;
begin
 loop
  r:=public.reconciliar_referencias_lote(cursor_referencias,5000);
  exit when r->>'siguiente' is null;
  cursor_referencias:=r->>'siguiente';
 end loop;
 loop
  r:=public.reconciliar_ofertas_lote(cursor_ofertas,500);
  archivadas:=archivadas+(r->>'archivadas')::integer;
  exit when r->>'siguiente' is null;
  cursor_ofertas:=(r->>'siguiente')::bigint;
 end loop;
 return jsonb_build_object('archivadas',archivadas,'filas_unicas',r->'filas_unicas','sin_identificar',r->'sin_identificar');
end;
$$;
revoke all on function public.adaptia_raices_identidad(text[]),public.reconciliar_referencias_lote(text,integer),
 public.reconciliar_ofertas_lote(bigint,integer),public.reconciliar_ofertas() from public,anon,authenticated;
grant execute on function public.reconciliar_referencias_lote(text,integer),public.reconciliar_ofertas_lote(bigint,integer),
 public.reconciliar_ofertas() to service_role;

select public.reconciliar_ofertas();
notify pgrst,'reload schema';
commit;
