-- Estado operativo aditivo. Aplicar tras esquema.sql y 002; no reinicia reservas ni borra historia.
begin;
create sequence if not exists public.estado_operativo_revision_seq;
create table if not exists public.estado_operativo (
  cola text not null check (cola in ('control','catalogo','ofertas','registro','lote')),
  identificador text not null,
  payload jsonb not null,
  revision bigint not null default nextval('public.estado_operativo_revision_seq'),
  actualizado_en timestamptz not null default now(),
  primary key (cola, identificador)
);
create table if not exists public.apify_reservas (
  solicitud text primary key,
  fecha date not null,
  ejecucion uuid,
  micro_usd bigint not null check (micro_usd >= 0),
  origen text not null check (origen in ('legado','central')),
  creado_en timestamptz not null default now()
);
create index if not exists apify_reservas_fecha on public.apify_reservas(fecha);
alter table public.estado_operativo enable row level security;
alter table public.apify_reservas enable row level security;
revoke all on public.estado_operativo, public.apify_reservas from public, anon, authenticated, service_role;
revoke all on sequence public.estado_operativo_revision_seq from public, anon, authenticated, service_role;
grant select on public.estado_operativo, public.apify_reservas to service_role;

create or replace function public.apify_estado() returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object('mes', to_char((now() at time zone 'America/Bogota')::date,'YYYY-MM'),
    'reservas', coalesce((select jsonb_object_agg(fecha::text,total/1000000.0) from
      (select fecha,sum(micro_usd) as total from public.apify_reservas
       where date_trunc('month',fecha::timestamp)=date_trunc('month',now() at time zone 'America/Bogota')
       group by fecha) s),'{}'::jsonb));
$$;

create or replace function public.operacion_inicializar(p_importar jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare r record; f date; m bigint; centrales bigint; mes text;
begin
  perform pg_advisory_xact_lock(hashtextextended('adaptia.operacion.inicio',0));
  if not exists(select 1 from public.estado_operativo where cola='control' and identificador='inicializado')
     and (p_importar is null or not (p_importar ? 'mes') or jsonb_typeof(p_importar->'reservas') is distinct from 'object') then
    raise exception 'Falta presupuesto del corte inicial; no asumir saldo cero. Recuperar estado o inicializar una instancia nueva explícitamente';
  end if;
  if p_importar ? 'mes' then
    mes := p_importar->>'mes';
    if mes is null or mes !~ '^\d{4}-\d{2}$' or jsonb_typeof(p_importar->'reservas') is distinct from 'object' then
      raise exception 'Presupuesto legado inválido'; end if;
    perform pg_advisory_xact_lock(hashtextextended('adaptia.apify.'||mes,0));
    for r in select key,value from jsonb_each_text(p_importar->'reservas') order by key loop
      f := r.key::date;
      if to_char(f,'YYYY-MM')<>mes then raise exception 'Reserva fuera del mes del corte'; end if;
      m := ceil(r.value::numeric*1000000)::bigint;
      if m<0 or m>5000000 then raise exception 'Reserva legada fuera de límites'; end if;
      select coalesce(sum(micro_usd),0) into centrales from public.apify_reservas where fecha=f and origen='central';
      insert into public.apify_reservas(solicitud,fecha,micro_usd,origen)
        values ('legado:'||f::text,f,greatest(0,m-centrales),'legado')
        on conflict(solicitud) do update set micro_usd=greatest(public.apify_reservas.micro_usd,excluded.micro_usd);
    end loop;
  end if;
  insert into public.estado_operativo(cola,identificador,payload) values('control','inicializado','{"version":1}')
    on conflict do nothing;
  return public.apify_estado();
end;
$$;

create or replace function public.apify_reservar(p_solicitud uuid,p_ejecucion uuid,p_fecha date,
  p_mensual bigint,p_corrida bigint,p_monto bigint) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare usado_mes bigint; usado_dia bigint; usado_corrida bigint; disponible bigint; dias integer; mes text;
begin
  if not exists(select 1 from public.estado_operativo where cola='control' and identificador='inicializado') then
    raise exception 'Estado operativo no inicializado'; end if;
  if p_solicitud is null or p_ejecucion is null or p_fecha is distinct from (now() at time zone 'America/Bogota')::date
     or p_mensual is null or p_corrida is null or p_monto is null
     or p_mensual not between 0 and 5000000 or p_corrida not between 0 and 3000000 or p_monto<0 then
    raise exception 'Fecha o límites de presupuesto inválidos'; end if;
  mes := to_char(p_fecha,'YYYY-MM');
  perform pg_advisory_xact_lock(hashtextextended('adaptia.apify.'||mes,0));
  if exists(select 1 from public.apify_reservas where solicitud=p_solicitud::text) then
    return jsonb_build_object('monto_micro',0,'repetida',true,'estado',public.apify_estado()); end if;
  select coalesce(sum(micro_usd),0),coalesce(sum(micro_usd) filter(where fecha=p_fecha),0),
    coalesce(sum(micro_usd) filter(where ejecucion=p_ejecucion),0)
    into usado_mes,usado_dia,usado_corrida from public.apify_reservas where to_char(fecha,'YYYY-MM')=mes;
  dias := extract(day from (date_trunc('month',p_fecha::timestamp)+interval '1 month - 1 day'))::integer;
  disponible := greatest(0,least(p_monto,p_mensual-usado_mes,p_mensual/dias-usado_dia,p_corrida-usado_corrida));
  if disponible<2000 then disponible:=0; end if;
  if disponible>0 then
    insert into public.apify_reservas(solicitud,fecha,ejecucion,micro_usd,origen)
      values(p_solicitud::text,p_fecha,p_ejecucion,disponible,'central');
  end if;
  return jsonb_build_object('monto_micro',disponible,'repetida',false,'estado',public.apify_estado());
end;
$$;

create or replace function public.estado_guardar(p_cola text,p_elementos jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare e jsonb; anterior public.estado_operativo%rowtype; v_identificador text; esperado bigint; datos jsonb;
        revision_nueva bigint; salida jsonb:='[]'; r record; item jsonb; ids text[]; id text; completas boolean;
begin
  if p_cola is null or p_cola not in ('catalogo','ofertas','registro','lote')
     or jsonb_typeof(p_elementos) is distinct from 'array' or jsonb_array_length(p_elementos)>100 then
    raise exception 'Cola o lote de operaciones inválido'; end if;
  if not exists(select 1 from public.estado_operativo where cola='control' and identificador='inicializado') then
    raise exception 'Estado operativo no inicializado'; end if;
  perform pg_advisory_xact_lock(hashtextextended('adaptia.cola.'||p_cola,0));
  for e in select value from jsonb_array_elements(p_elementos) loop
    v_identificador:=e->>'identificador'; esperado:=(e->>'revision')::bigint; datos:=e->'payload';
    if coalesce(v_identificador,'')='' or esperado is null or esperado<0 or jsonb_typeof(datos) is distinct from 'object' then
      raise exception 'Operación pendiente inválida'; end if;
    select * into anterior from public.estado_operativo s where s.cola=p_cola and s.identificador=v_identificador for update;
    if coalesce(anterior.revision,0)<>esperado then raise exception 'Conflicto de revisión; releer estado'; end if;
    if p_cola='lote' then
      if datos->>'fecha' is distinct from v_identificador or jsonb_typeof(datos->'elegidas') is distinct from 'object' then
        raise exception 'Fecha o selección inválida'; end if;
      ids:='{}'; completas:=true;
      for r in select key,value from jsonb_each(datos->'elegidas') loop
        if r.key='' or jsonb_typeof(r.value)<>'array' or jsonb_array_length(r.value)>20 then raise exception 'Rol o cantidad inválida'; end if;
        for item in select value from jsonb_array_elements(r.value) loop
          if jsonb_typeof(item) is distinct from 'array' or jsonb_array_length(item)<>2
             or jsonb_typeof(item->0) is distinct from 'object' or item->>1 is null
             or item->>1 not in ('exacto','similar','cercano') or coalesce(item->0->>'_capturada_entrega','')='' then
            raise exception 'Snapshot o grado de selección inválido'; end if;
          id:=item->0->>'id';
          if id is null or id !~ '^[a-f0-9]{16}$' or id=any(ids) then raise exception 'Identidad de selección inválida/repetida'; end if;
          ids:=array_append(ids,id);
          if not exists(select 1 from public.entregas_diarias d where d.vacante_id=id
                        and d.delivery_date=v_identificador::date and d.role_id=r.key) then completas:=false; end if;
        end loop;
      end loop;
      if cardinality(ids)>120 then raise exception 'Más de ciento veinte por lote'; end if;
      -- El temporal puede haberse retirado tras confirmar. El registro canónico sigue protegiendo
      -- el mismo día frente a un proceso atrasado que intenta crear otra selección con revisión cero.
      for r in select d.role_id,d.vacante_id,d.match_grade,d.selected_at,d.snapshot from public.entregas_diarias d
               where d.delivery_date=v_identificador::date loop
        select value into item from jsonb_array_elements(coalesce(datos->'elegidas'->r.role_id,'[]'::jsonb))
          where value->0->>'id'=r.vacante_id;
        if item is null or ((item->0)-'_capturada_entrega') is distinct from (r.snapshot-'_capturada_entrega')
           or (item->0->>'_capturada_entrega')::timestamptz is distinct from r.selected_at
           or (case item->>1 when 'exacto' then 'exact' when 'similar' then 'similar' when 'cercano' then 'close' end)
              is distinct from r.match_grade then
          raise exception 'No se puede reemplazar una selección canónica; releer el lote del día'; end if;
      end loop;
      if anterior.payload is not null then
        for r in select key,value from jsonb_each(anterior.payload->'elegidas') loop
          for item in select value from jsonb_array_elements(r.value) loop
            if not coalesce(datos->'elegidas'->r.key,'[]'::jsonb) @> jsonb_build_array(item) then
              raise exception 'No se puede retirar o modificar una selección guardada'; end if;
          end loop;
        end loop;
      end if;
      if completas then
        delete from public.estado_operativo s where s.cola=p_cola and s.identificador=v_identificador;
        salida:=salida||jsonb_build_array(jsonb_build_object('identificador',v_identificador,'revision',0));
        continue;
      end if;
    end if;
    if anterior.payload=datos then revision_nueva:=anterior.revision;
    else
      insert into public.estado_operativo(cola,identificador,payload) values(p_cola,v_identificador,datos)
        on conflict(cola,identificador) do update set payload=excluded.payload,
          revision=nextval('public.estado_operativo_revision_seq'),actualizado_en=now()
        returning revision into revision_nueva;
    end if;
    salida:=salida||jsonb_build_array(jsonb_build_object('identificador',v_identificador,'revision',revision_nueva));
  end loop;
  return salida;
end;
$$;

create or replace function public.estado_confirmar(p_cola text,p_elementos jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare e jsonb; actual bigint; salida jsonb:='[]';
begin
  if p_cola is null or p_cola not in ('catalogo','ofertas','registro')
     or jsonb_typeof(p_elementos) is distinct from 'array' or jsonb_array_length(p_elementos)>100 then
    raise exception 'Confirmación de cola inválida'; end if;
  perform pg_advisory_xact_lock(hashtextextended('adaptia.cola.'||p_cola,0));
  for e in select value from jsonb_array_elements(p_elementos) loop
    select revision into actual from public.estado_operativo s
      where s.cola=p_cola and s.identificador=e->>'identificador' for update;
    if actual is not null and actual is distinct from (e->>'revision')::bigint then
      raise exception 'Confirmación antigua; releer estado'; end if;
    delete from public.estado_operativo s where s.cola=p_cola and s.identificador=e->>'identificador';
    salida:=salida||jsonb_build_array(e->>'identificador');
  end loop;
  return salida;
end;
$$;

revoke all on function public.apify_estado(),public.operacion_inicializar(jsonb),
 public.apify_reservar(uuid,uuid,date,bigint,bigint,bigint),public.estado_guardar(text,jsonb),public.estado_confirmar(text,jsonb)
 from public,anon,authenticated;
grant execute on function public.apify_estado(),public.operacion_inicializar(jsonb),
 public.apify_reservar(uuid,uuid,date,bigint,bigint,bigint),public.estado_guardar(text,jsonb),public.estado_confirmar(text,jsonb)
 to service_role;
notify pgrst,'reload schema';
commit;
