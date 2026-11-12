-- Pruebas con datos ficticios. Nunca ejecutar este archivo en producción.
begin;
do $$ begin
  if has_table_privilege('anon','public.estado_operativo','SELECT') or
     has_table_privilege('authenticated','public.apify_reservas','SELECT') or
     has_table_privilege('service_role','public.apify_reservas','INSERT') or
     has_function_privilege('anon','public.apify_reservar(uuid,uuid,date,bigint,bigint,bigint)','EXECUTE') then
    raise exception 'Permisos públicos o escritura directa indebidos'; end if;
end $$;
-- Solo el fixture aislado retira sus datos dentro de una transacción revertida.
delete from public.estado_operativo;
delete from public.apify_reservas;
set local role service_role;
do $$
declare r jsonb; d date:=(now() at time zone 'America/Bogota')::date; mes text;
  id uuid:='11111111-1111-1111-1111-111111111111'; ex uuid:='22222222-2222-2222-2222-222222222222';
  a bigint; b bigint; total bigint; revision bigint; lote jsonb;
begin
  mes:=to_char(d,'YYYY-MM');
  begin
    perform public.operacion_inicializar('{}');
    raise exception 'Se inicializó sin corte';
  exception when raise_exception then if sqlerrm='Se inicializó sin corte' then raise; end if; end;
  perform public.operacion_inicializar(jsonb_build_object('mes',mes,'reservas',jsonb_build_object(d::text,0.01)));
  r:=public.apify_reservar(id,ex,d,5000000,3000000,25000);
  if (r->>'monto_micro')::bigint<>25000 then raise exception 'Reserva incorrecta'; end if;
  if (r->'estado'->'reservas'->>d::text)::numeric<>0.035 then raise exception 'Espejo no incluye reserva confirmada'; end if;
  if (public.apify_reservar(id,ex,d,5000000,3000000,25000)->>'monto_micro')::bigint<>0 then
    raise exception 'Solicitud repetida autorizó otro cargo'; end if;
  perform public.operacion_inicializar(r->'estado');
  select sum(micro_usd) into total from public.apify_reservas where fecha=d;
  if total<>35000 then raise exception 'Importar espejo contó dos veces: %',total; end if;
  perform public.operacion_inicializar(jsonb_build_object('mes',mes,'reservas',jsonb_build_object(d::text,0.005)));
  select sum(micro_usd) into total from public.apify_reservas where fecha=d;
  if total<>35000 then raise exception 'Corte viejo repuso crédito'; end if;
  begin
    perform public.apify_reservar('33333333-3333-3333-3333-333333333333',ex,d-1,5000000,3000000,25000);
    raise exception 'Fecha inválida autorizada';
  exception when raise_exception then if sqlerrm='Fecha inválida autorizada' then raise; end if; end;
  -- Dos solicitudes de la misma corrida respetan su tope independiente.
  r:=public.apify_reservar('33333333-3333-3333-3333-333333333333',ex,d,5000000,30000,25000);
  if (r->>'monto_micro')::bigint<>5000 then raise exception 'Tope de corrida ignorado'; end if;

  r:=public.estado_guardar('catalogo','[{"identificador":"a","revision":0,"payload":{"valor":1}}]');
  a:=(r->0->>'revision')::bigint;
  r:=public.estado_guardar('catalogo',jsonb_build_array(jsonb_build_object('identificador','a','revision',a,'payload','{"valor":2}'::jsonb)));
  b:=(r->0->>'revision')::bigint;
  if b<=a then raise exception 'Revisión no avanza'; end if;
  begin
    perform public.estado_confirmar('catalogo',jsonb_build_array(jsonb_build_object('identificador','a','revision',a)));
    raise exception 'Confirmación vieja borró lo nuevo';
  exception when raise_exception then if sqlerrm='Confirmación vieja borró lo nuevo' then raise; end if; end;
  if not exists(select 1 from public.estado_operativo where cola='catalogo' and identificador='a' and payload='{"valor":2}') then
    raise exception 'Se perdió pendiente actualizado'; end if;
  perform public.estado_confirmar('catalogo',jsonb_build_array(jsonb_build_object('identificador','a','revision',b)));
  r:=public.estado_guardar('catalogo','[{"identificador":"a","revision":0,"payload":{"valor":3}}]');
  if (r->0->>'revision')::bigint<=b then raise exception 'Recrear reinició revisión'; end if;
  -- Un conflicto revierte también los elementos previos del mismo lote.
  begin
    perform public.estado_guardar('catalogo','[{"identificador":"b","revision":0,"payload":{}},{"identificador":"a","revision":0,"payload":{}}]');
    raise exception 'Conflicto no detectado';
  exception when raise_exception then if sqlerrm='Conflicto no detectado' then raise; end if; end;
  if exists(select 1 from public.estado_operativo where cola='catalogo' and identificador='b') then
    raise exception 'Lote conflictivo quedó a medias'; end if;
  lote:=jsonb_build_object('fecha',d::text,'elegidas',jsonb_build_object('qa',
    '[ [{"id":"bbbbbbbbbbbbbbbb","_capturada_entrega":"2026-11-05T12:00:00Z"},"exacto"] ]'::jsonb));
  r:=public.estado_guardar('lote',jsonb_build_array(jsonb_build_object('identificador',d::text,'revision',0,'payload',lote)));
  revision:=(r->0->>'revision')::bigint;
  begin
    perform public.estado_guardar('lote',jsonb_build_array(jsonb_build_object('identificador',d::text,'revision',revision,
      'payload',jsonb_build_object('fecha',d::text,'elegidas','{}'::jsonb))));
    raise exception 'Se permitió vaciar un lote';
  exception when raise_exception then if sqlerrm='Se permitió vaciar un lote' then raise; end if; end;
  -- Registrar canónicamente permite retirar únicamente el temporal.
end $$;
reset role;
insert into public.catalogo_vacantes(id,datos,observed_at,status) values('bbbbbbbbbbbbbbbb','{}',now(),'active') on conflict do nothing;
insert into public.entregas_diarias(vacante_id,delivery_date,role_id,match_grade,selected_at,snapshot)
 values('bbbbbbbbbbbbbbbb',(now()at time zone 'America/Bogota')::date,'qa','exact','2026-11-05T12:00:00Z',
   '{"id":"bbbbbbbbbbbbbbbb","_capturada_entrega":"2026-11-05T12:00:00Z"}') on conflict do nothing;
set local role service_role;
do $$ declare r jsonb; fila public.estado_operativo%rowtype;
begin
  select * into fila from public.estado_operativo where cola='lote';
  r:=public.estado_guardar('lote',jsonb_build_array(jsonb_build_object('identificador',fila.identificador,'revision',fila.revision,'payload',fila.payload)));
  if (r->0->>'revision')::bigint<>0 or exists(select 1 from public.estado_operativo where cola='lote') then
    raise exception 'No se retiró temporal confirmado'; end if;
  if not exists(select 1 from public.entregas_diarias where vacante_id='bbbbbbbbbbbbbbbb') then
    raise exception 'Se perdió histórico canónico'; end if;
  begin
    perform public.estado_guardar('lote',jsonb_build_array(jsonb_build_object('identificador',fila.identificador,
      'revision',0,'payload',jsonb_build_object('fecha',fila.identificador,'elegidas','{}'::jsonb))));
    raise exception 'Un proceso antiguo pudo reemplazar el canónico tras limpiar temporal';
  exception when raise_exception then
    if sqlerrm='Un proceso antiguo pudo reemplazar el canónico tras limpiar temporal' then raise; end if;
  end;
  begin
    perform public.estado_guardar('lote',jsonb_build_array(jsonb_build_object('identificador',((fila.identificador::date)+1)::text,
      'revision',0,'payload',jsonb_set(fila.payload,'{fecha}',to_jsonb(((fila.identificador::date)+1)::text)))));
    raise exception 'Se permitió repetir la vacante en otro día';
  exception when raise_exception then
    if sqlerrm='Se permitió repetir la vacante en otro día' then raise; end if;
  end;
  -- Pasada de la mañana (11 nov 2026): completar el día conservando intacto lo registrado se acepta...
  r:=public.estado_guardar('lote',jsonb_build_array(jsonb_build_object('identificador',fila.identificador,'revision',0,
    'payload',jsonb_set(fila.payload,'{elegidas,qa}',(fila.payload->'elegidas'->'qa')||
      '[[{"id":"cccccccccccccccc","_capturada_entrega":"2026-11-05T13:00:00Z"},"exacto"]]'::jsonb))));
  if (r->0->>'revision')::bigint=0 then raise exception 'No se guardó el lote ampliado'; end if;
  -- ...pero no si un paso intermedio reescribió el snapshot registrado (p. ej. su verificación).
  begin
    perform public.estado_guardar('lote',jsonb_build_array(jsonb_build_object('identificador',fila.identificador,
      'revision',(r->0->>'revision')::bigint,'payload',jsonb_set(fila.payload,'{elegidas,qa,0,0,verificacion}','{"estado":"verificada"}'))));
    raise exception 'Se aceptó un snapshot canónico alterado';
  exception when raise_exception then
    if sqlerrm='Se aceptó un snapshot canónico alterado' then raise; end if;
    if sqlerrm not like 'No se puede reemplazar una selección canónica%' then raise; end if;
  end;
end $$;
reset role;
rollback;
