-- Consulta actual sin alterar el histórico v1 ni los snapshots de selección.
begin;
create or replace function public.adaptia_fecha_segura(valor text) returns timestamptz
language plpgsql stable set search_path = '' as $$
begin
  if valor !~ '^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$' then return null; end if;
  return valor::timestamptz;
exception when invalid_datetime_format or datetime_field_overflow then return null;
end;
$$;
revoke all on function public.adaptia_fecha_segura(text) from public, anon, authenticated;
grant execute on function public.adaptia_fecha_segura(text) to service_role;
create or replace view public.seleccion_estado_actual with (security_invoker = true) as
select e.delivery_date, e.role_id, e.vacante_id, e.match_grade,
       coalesce(c.datos->>'titulo', e.snapshot->>'titulo') as job_title,
       coalesce(c.datos->>'empresa', e.snapshot->>'empresa') as company_name,
       c.status as catalog_status, c.observed_at, c.reason,
       c.datos->>'rol_entrega_actual' as rol_entrega_actual,
       case when c.status = 'closed' then 'closed'
            when c.status = 'archived' then 'archived'
            when c.datos->>'rol_entrega_actual' is null then 'afinidad_por_confirmar'
            when c.datos->>'rol_entrega_actual' <> e.role_id then 'fuera_de_perfil'
            when c.status = 'active' and enlace.url is not null then 'lista'
            else 'por_verificar' end as estado_actual,
       case when c.status = 'active' and c.datos->>'rol_entrega_actual' = e.role_id
            then enlace.url end as url_utilizable,
       enlace.comprobada_en,
       c.datos->'verificacion'->>'motivo' as motivo_verificacion
from public.entregas_diarias e
left join public.catalogo_vacantes c on c.id = e.vacante_id
left join lateral (
  select r->>'url' as url, fecha.comprobada_en
  from jsonb_array_elements(case when jsonb_typeof(c.datos->'verificacion'->'enlaces') = 'array'
       then c.datos->'verificacion'->'enlaces' else '[]'::jsonb end) r
  cross join lateral (select public.adaptia_fecha_segura(r->>'comprobada_en') as comprobada_en) fecha
  where c.datos->'verificacion'->>'estado' = 'verificada' and r->>'estado' = 'verificada'
    and r->>'url' in (c.datos->>'enlace', c.datos->>'enlace_directo')
    and fecha.comprobada_en <= now() and fecha.comprobada_en > now() - interval '6 hours'
  order by fecha.comprobada_en desc limit 1
) enlace on true;

create or replace view public.resumen_entregas_actual with (security_invoker = true) as
select delivery_date, role_id, count(*) as seleccionadas,
       count(*) filter (where estado_actual = 'lista') as listas_ahora,
       count(*) filter (where estado_actual = 'por_verificar') as por_verificar,
       count(*) filter (where estado_actual in ('closed','archived')) as retiradas,
       count(*) filter (where estado_actual in ('fuera_de_perfil','afinidad_por_confirmar')) as revisar_afinidad
from public.seleccion_estado_actual group by delivery_date, role_id;
revoke all on public.seleccion_estado_actual, public.resumen_entregas_actual from public, anon, authenticated;
grant select on public.seleccion_estado_actual, public.resumen_entregas_actual to service_role;
notify pgrst, 'reload schema';
commit;
