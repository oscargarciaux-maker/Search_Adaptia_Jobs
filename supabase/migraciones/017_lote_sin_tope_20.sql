-- Contrato v27 (16 nov): el lote del día ya no se limita a 20 vacantes por cargo ni a 120 en total. Era la regla de
-- la primera versión (seis cargos por veinte); con metas por perfil (v21) y techo editable de hasta 600, un cargo
-- compartido por varios clientes y Comunidad pasa de 20, y la búsqueda manual del 15 nov falló al guardar su lote
-- («Rol o cantidad inválida»). Reemplaza solo estado_guardar con los topes del techo (600) y el resto idéntico a 003.
-- Además (inventario del 16 nov): `ofertas` y la vista `entrega_de_hoy` conservaban los permisos por defecto de
-- Supabase para anon/authenticated. RLS ya bloqueaba las filas, pero los permisos se quitan para no depender de eso.
begin;
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
        if r.key='' or jsonb_typeof(r.value)<>'array' or jsonb_array_length(r.value)>600 then raise exception 'Rol o cantidad inválida'; end if;
        for item in select value from jsonb_array_elements(r.value) loop
          if jsonb_typeof(item) is distinct from 'array' or jsonb_array_length(item)<>2
             or jsonb_typeof(item->0) is distinct from 'object' or item->>1 is null
             or item->>1 not in ('exacto','similar','cercano') or coalesce(item->0->>'_capturada_entrega','')='' then
            raise exception 'Snapshot o grado de selección inválido'; end if;
          id:=item->0->>'id';
          if id is null or id !~ '^[a-f0-9]{16}$' or id=any(ids) then raise exception 'Identidad de selección inválida/repetida'; end if;
          if exists(select 1 from public.entregas_diarias d where d.vacante_id=id
                    and (d.delivery_date<>v_identificador::date or d.role_id<>r.key)) then
            raise exception 'Vacante ya seleccionada en otra fecha o rol'; end if;
          ids:=array_append(ids,id);
          if not exists(select 1 from public.entregas_diarias d where d.vacante_id=id
                        and d.delivery_date=v_identificador::date and d.role_id=r.key) then completas:=false; end if;
        end loop;
      end loop;
      if cardinality(ids)>600 then raise exception 'Más de seiscientas por lote'; end if;
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
revoke all on function public.estado_guardar(text,jsonb) from public,anon,authenticated;
grant execute on function public.estado_guardar(text,jsonb) to service_role;
revoke all on table public.ofertas from anon,authenticated;
revoke all on table public.entrega_de_hoy from anon,authenticated;
notify pgrst,'reload schema';
commit;
