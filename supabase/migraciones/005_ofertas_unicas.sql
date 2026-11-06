-- Una fila por vacante. Las copias por enlace se conservan íntegramente en un archivo privado.
begin;
alter table public.ofertas add column if not exists vacante_id text references public.catalogo_vacantes(id) on delete restrict;
alter table public.ofertas add column if not exists enlaces_alternativos jsonb;
create table if not exists public.ofertas_enlaces_historicos (
 oferta_id bigint primary key, vacante_id text not null, fila_original jsonb not null,
 archivada_en timestamptz not null default now()
);
alter table public.ofertas_enlaces_historicos enable row level security;
revoke all on public.ofertas_enlaces_historicos from public,anon,authenticated,service_role;
grant select on public.ofertas_enlaces_historicos to service_role;
create unique index if not exists archivo_oferta_por_enlace on public.ofertas_enlaces_historicos
 (vacante_id,(fila_original->>'external_id'));
create index if not exists catalogo_ids_agrupados on public.catalogo_vacantes using gin((datos->'ids_agrupados'));

create or replace function public.adaptia_url_identidad(valor text) returns text
language plpgsql immutable strict set search_path='' as $$
declare u text:=split_part(valor,'#',1); numero text; consulta text;
begin
 if u ~ '^https?://([a-z0-9-]+\.)?linkedin\.com/jobs/view/' then
  numero:=substring(u from '/jobs/view/(?:[^/?#]*-)?([0-9]+)');
  if numero is not null then return 'linkedin:'||numero; end if;
 end if;
 if u ~ '^https?://([a-z0-9-]+\.)?indeed\.[^/]+/' then
  numero:=substring(u from '[?&]jk=([a-zA-Z0-9]+)');
  if numero is not null then return 'indeed:'||numero; end if;
 end if;
 select string_agg(p,'&' order by n) into consulta
 from unnest(string_to_array(split_part(u,'?',2),'&')) with ordinality t(p,n)
 where split_part(p,'=',1) !~* '^(utm_.*|gclid|fbclid|trk|trkinfo|trackingid|refid|ref|lever-source|gh_src|source|src)$';
 return regexp_replace(split_part(u,'?',1),'/$','')||case when coalesce(consulta,'')<>'' then '?'||consulta else '' end;
end;
$$;

create or replace function public.adaptia_enlaces_unicos(enlaces jsonb) returns jsonb
language sql immutable set search_path='' as $$
 select coalesce(jsonb_agg(url order by url),'[]'::jsonb) from (
  select distinct on (public.adaptia_url_identidad(url)) url
  from jsonb_array_elements_text(coalesce(enlaces,'[]'::jsonb)) t(url)
  where coalesce(url,'')<>''
  order by public.adaptia_url_identidad(url),length(url),url
 ) unicos;
$$;

create or replace function public.adaptia_vacante_principal(valor text) returns text
language plpgsql stable set search_path='' as $$
declare siguiente text; visitadas text[]:='{}'; actual text:=valor; destinos bigint;
begin
 for paso in 1..20 loop
  if actual=any(visitadas) then raise exception 'Ciclo de identidades de vacante'; end if;
  visitadas:=array_append(visitadas,actual);
  select datos->>'duplicada_de' into siguiente from public.catalogo_vacantes where id=actual;
  if coalesce(siguiente,'')='' then
   select min(id),count(*) into siguiente,destinos from public.catalogo_vacantes
    where datos->'ids_agrupados' ? actual and id<>actual and coalesce(datos->>'duplicada_de','')='';
   if destinos<>1 then return actual; end if;
  end if;
  if coalesce(siguiente,'')='' then return actual; end if;
  if not exists(select 1 from public.catalogo_vacantes where id=siguiente) then
   raise exception 'La identidad principal todavía no está sincronizada'; end if;
  actual:=siguiente;
 end loop;
 raise exception 'Cadena de identidades demasiado larga';
end;
$$;

create or replace function public.adaptia_vacante_por_url(valor text) returns text
language sql stable strict set search_path='' as $$
 with enlaces as (
  select c.id,u.url from public.catalogo_vacantes c cross join lateral jsonb_array_elements_text(
   jsonb_build_array(c.datos->>'enlace',c.datos->>'enlace_directo')||
   case when jsonb_typeof(c.datos->'enlaces_alternativos')='array' then c.datos->'enlaces_alternativos' else '[]'::jsonb end) u(url)
  union all
  select e.vacante_id,u.url from public.entregas_diarias e cross join lateral jsonb_array_elements_text(
   jsonb_build_array(e.snapshot->>'enlace',e.snapshot->>'enlace_directo')||
   case when jsonb_typeof(e.snapshot->'_enlaces')='array' then e.snapshot->'_enlaces' else '[]'::jsonb end) u(url)
 ), candidatos as (
  select distinct public.adaptia_vacante_principal(id) id from enlaces
  where public.adaptia_url_identidad(url)=public.adaptia_url_identidad(valor)
 ) select case when count(*)=1 then min(id) end from candidatos;
$$;

create or replace function public.reconciliar_ofertas() returns jsonb
language plpgsql security definer set search_path='' as $$
declare mapa jsonb; r record; archivadas integer:=0;
begin
 perform pg_advisory_xact_lock(hashtextextended('adaptia.ofertas.unicas',0));
 with enlaces as (
  select c.id,u.url from public.catalogo_vacantes c cross join lateral jsonb_array_elements_text(
    jsonb_build_array(c.datos->>'enlace',c.datos->>'enlace_directo')||
    case when jsonb_typeof(c.datos->'enlaces_alternativos')='array' then c.datos->'enlaces_alternativos' else '[]'::jsonb end) u(url)
  union all
  select e.vacante_id,u.url from public.entregas_diarias e cross join lateral jsonb_array_elements_text(
    jsonb_build_array(e.snapshot->>'enlace',e.snapshot->>'enlace_directo')||
    case when jsonb_typeof(e.snapshot->'_enlaces')='array' then e.snapshot->'_enlaces' else '[]'::jsonb end) u(url)
 ), identificadas as (
  select public.adaptia_url_identidad(url) url,min(public.adaptia_vacante_principal(id)) id,
         count(distinct public.adaptia_vacante_principal(id)) n
  from enlaces where coalesce(url,'')<>'' group by public.adaptia_url_identidad(url)
 ), destinos as (
  select o.id,coalesce(case when i.n=1 then i.id end,
         public.adaptia_vacante_principal(o.vacante_id)) principal
  from public.ofertas o left join identificadas i on i.url=public.adaptia_url_identidad(o.offer_url)
 )
 select coalesce(jsonb_object_agg(id::text,principal),'{}') into mapa from destinos where principal is not null;
 for r in
  select o.id,m.value principal,to_jsonb(o) original,
         row_number() over(partition by m.value order by o.id) posicion
  from public.ofertas o join jsonb_each_text(mapa) m on m.key=o.id::text
 loop
  if r.posicion>1 then
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
create unique index if not exists ofertas_por_vacante on public.ofertas(vacante_id) where vacante_id is not null;

create or replace function public.conservar_oferta_unica() returns trigger
language plpgsql security definer set search_path='' as $$
declare previa public.ofertas%rowtype;
begin
 perform pg_advisory_xact_lock(hashtextextended('adaptia.ofertas.unicas',0));
 new.vacante_id:=coalesce(new.vacante_id,public.adaptia_vacante_por_url(new.offer_url));
 if new.vacante_id is null then return new; end if;
 new.vacante_id:=public.adaptia_vacante_principal(new.vacante_id);
 select * into previa from public.ofertas where vacante_id=new.vacante_id;
 if found then
  if previa.external_id<>new.external_id then
   insert into public.ofertas_enlaces_historicos(oferta_id,vacante_id,fila_original)
    values(new.id,new.vacante_id,to_jsonb(new)) on conflict do nothing;
  end if;
  update public.ofertas set enlaces_alternativos=public.adaptia_enlaces_unicos(
    coalesce(previa.enlaces_alternativos,'[]'::jsonb)||coalesce(new.enlaces_alternativos,'[]'::jsonb)||
    jsonb_build_array(previa.offer_url,new.offer_url))
   where id=previa.id;
  return null;
 end if;
 return new;
end;
$$;
drop trigger if exists oferta_unica on public.ofertas;
create trigger oferta_unica before insert on public.ofertas for each row execute function public.conservar_oferta_unica();
revoke all on function public.adaptia_vacante_por_url(text),public.adaptia_enlaces_unicos(jsonb),public.adaptia_url_identidad(text),public.adaptia_vacante_principal(text),
 public.reconciliar_ofertas(),public.conservar_oferta_unica() from public,anon,authenticated;
grant execute on function public.reconciliar_ofertas(),public.adaptia_url_identidad(text),
 public.adaptia_vacante_principal(text) to service_role;
notify pgrst,'reload schema';
commit;
