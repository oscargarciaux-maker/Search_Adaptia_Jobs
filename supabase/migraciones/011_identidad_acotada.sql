-- Recorrer solo las identidades que pueden decidir una oferta o que tienen duplicada_de explícito, con índices, en vez
-- de leer todo el catálogo en cada captura. Mismas aristas, ciclos, límites y escrituras que 010; los ciclos explícitos,
-- principales ausentes y cadenas explícitas se siguen rechazando en todo el catálogo.
begin;
-- Encontrar las referencias explícitas sin recorrer el catálogo. Índice por expresión (no parcial) para que ANALYZE
-- registre cuántas filas la tienen y el planificador no suponga que son casi todas.
create index if not exists catalogo_duplicada_de on public.catalogo_vacantes((nullif(datos->>'duplicada_de','')));
-- Cada paso consulta este índice por clave: sin lista pendiente, como los índices de enlaces de 008. Vaciarla ahora.
alter index public.catalogo_ids_agrupados set (fastupdate=off);
select gin_clean_pending_list('public.catalogo_ids_agrupados'::regclass);
analyze public.catalogo_vacantes;

-- Sin JIT: compilar el plan costaba más que ejecutarlo con estas estimaciones de índices.
create or replace function public.reconciliar_ofertas() returns jsonb
language plpgsql security definer set search_path='' set jit=off as $$
declare mapa jsonb; semillas text[]; raices jsonb; r record; archivadas integer:=0; referencias boolean; hay_ciclo boolean; falta_principal boolean;
begin
 perform pg_advisory_xact_lock(hashtextextended('adaptia.ofertas.unicas',0));
 select exists(select 1 from pg_constraint where contype='f' and confrelid='public.ofertas'::regclass) into referencias;
 -- Inicio del recorrido: la vacante de cada oferta, las que comparten su enlace (índices GIN) y toda referencia
 -- explícita, para seguir rechazando ciclos o principales ausentes aunque no toquen una oferta.
 with semillas as (
  select o.vacante_id id from public.ofertas o where o.vacante_id is not null
  union select c.id from public.catalogo_vacantes c where nullif(c.datos->>'duplicada_de','') is not null
  union select c.id from public.ofertas o join public.catalogo_vacantes c
   on public.adaptia_urls_identidad(c.datos) @> array[public.adaptia_url_identidad(o.offer_url)]
  union select e.vacante_id from public.ofertas o join public.entregas_diarias e
   on public.adaptia_urls_identidad(e.snapshot) @> array[public.adaptia_url_identidad(o.offer_url)]
 )
 select coalesce(array_agg(c.id),'{}') into semillas
 from semillas s join public.catalogo_vacantes c on c.id=s.id;
 -- Cada paso lee una fila por clave primaria y sus aliases por el índice de ids_agrupados (las mismas aristas de 010:
 -- duplicada_de explícita o un único grupo sin duplicada_de que la nombra).
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
 into raices,hay_ciclo,falta_principal from terminales t;
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
revoke all on function public.reconciliar_ofertas() from public,anon,authenticated;
grant execute on function public.reconciliar_ofertas() to service_role;

select public.reconciliar_ofertas();
commit;
