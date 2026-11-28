-- 28 nov (sección 8.2, decisión de Oscar): prueba de Apify al ritmo de Starter antes de comprarlo.
-- La 003 reparte el tope del mes entre los días (5/30 ≈ 0,17 por día) y no admite topes de más de USD 5. Esta
-- migración añade, sin tocar la 003 ni sus datos:
-- 1. `apify_reservar_ritmo`: la misma reserva durable, con un ritmo diario propio (`p_diario`, p. ej. 0,63 = 19/30) y
--    un tope del mes de hasta USD 100 (el máximo que Apify deja fijar en Starter). Nunca se pasa del tope del mes, ni
--    del ritmo del día, ni del tope por corrida, aunque haya reintentos (misma solicitud = misma reserva).
-- 2. `apify_bloqueos` + `apify_marcar_agotado`: cuando Apify dice que se acabó el crédito del plan, el mes queda
--    bloqueado y ninguna corrida vuelve a reservar hasta el mes siguiente (aviso, no avería).
-- 3. `apify_estado` devuelve además `bloqueado` (true/false) para el espejo local trabajo/apify_presupuesto.json.
-- `apify_reservar` (003) sigue existiendo para una corrida con el código anterior.
begin;
create table if not exists public.apify_bloqueos (
  mes text primary key check (mes ~ '^\d{4}-\d{2}$'),
  creado_en timestamptz not null default now()
);
alter table public.apify_bloqueos enable row level security;
revoke all on public.apify_bloqueos from public, anon, authenticated, service_role;
grant select on public.apify_bloqueos to service_role;

create or replace function public.apify_estado() returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object('mes', to_char((now() at time zone 'America/Bogota')::date,'YYYY-MM'),
    'reservas', coalesce((select jsonb_object_agg(fecha::text,total/1000000.0) from
      (select fecha,sum(micro_usd) as total from public.apify_reservas
       where date_trunc('month',fecha::timestamp)=date_trunc('month',now() at time zone 'America/Bogota')
       group by fecha) s),'{}'::jsonb),
    'bloqueado', exists(select 1 from public.apify_bloqueos
       where mes=to_char((now() at time zone 'America/Bogota')::date,'YYYY-MM')));
$$;

create or replace function public.apify_reservar_ritmo(p_solicitud uuid,p_ejecucion uuid,p_fecha date,
  p_mensual bigint,p_diario bigint,p_corrida bigint,p_monto bigint) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare usado_mes bigint; usado_dia bigint; usado_corrida bigint; disponible bigint; v_mes text;
begin
  if not exists(select 1 from public.estado_operativo where cola='control' and identificador='inicializado') then
    raise exception 'Estado operativo no inicializado'; end if;
  if p_solicitud is null or p_ejecucion is null or p_fecha is distinct from (now() at time zone 'America/Bogota')::date
     or p_mensual is null or p_diario is null or p_corrida is null or p_monto is null
     or p_mensual not between 0 and 100000000 or p_diario not between 0 and p_mensual
     or p_corrida not between 0 and p_mensual or p_monto<0 then
    raise exception 'Fecha o límites de presupuesto inválidos'; end if;
  v_mes := to_char(p_fecha,'YYYY-MM');
  perform pg_advisory_xact_lock(hashtextextended('adaptia.apify.'||v_mes,0));
  if exists(select 1 from public.apify_reservas where solicitud=p_solicitud::text) then
    return jsonb_build_object('monto_micro',0,'repetida',true,'estado',public.apify_estado()); end if;
  if exists(select 1 from public.apify_bloqueos b where b.mes=v_mes) then
    return jsonb_build_object('monto_micro',0,'repetida',false,'estado',public.apify_estado()); end if;
  select coalesce(sum(micro_usd),0),coalesce(sum(micro_usd) filter(where fecha=p_fecha),0),
    coalesce(sum(micro_usd) filter(where ejecucion=p_ejecucion),0)
    into usado_mes,usado_dia,usado_corrida from public.apify_reservas where to_char(fecha,'YYYY-MM')=v_mes;
  disponible := greatest(0,least(p_monto,p_mensual-usado_mes,p_diario-usado_dia,p_corrida-usado_corrida));
  if disponible<2000 then disponible:=0; end if;
  if disponible>0 then
    insert into public.apify_reservas(solicitud,fecha,ejecucion,micro_usd,origen)
      values(p_solicitud::text,p_fecha,p_ejecucion,disponible,'central');
  end if;
  return jsonb_build_object('monto_micro',disponible,'repetida',false,'estado',public.apify_estado());
end;
$$;

create or replace function public.apify_marcar_agotado(p_fecha date) returns jsonb
language plpgsql security definer set search_path = '' as $$
begin
  if p_fecha is distinct from (now() at time zone 'America/Bogota')::date then
    raise exception 'Fecha inválida'; end if;
  insert into public.apify_bloqueos(mes) values(to_char(p_fecha,'YYYY-MM')) on conflict do nothing;
  return public.apify_estado();
end;
$$;

revoke all on function public.apify_reservar_ritmo(uuid,uuid,date,bigint,bigint,bigint,bigint),
 public.apify_marcar_agotado(date) from public,anon,authenticated;
grant execute on function public.apify_reservar_ritmo(uuid,uuid,date,bigint,bigint,bigint,bigint),
 public.apify_marcar_agotado(date) to service_role;
notify pgrst,'reload schema';
commit;
