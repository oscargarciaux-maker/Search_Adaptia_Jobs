-- Ejecutar solo en PostgreSQL de prueba tras esquema.sql y la migración 002.
begin;
insert into public.catalogo_vacantes
(id, datos, description_full, first_seen_at, last_seen_at, observed_at, status)
values ('aaaaaaaaaaaaaaaa', '{"titulo":"UX Designer"}', 'Descripción original',
        '2026-11-01T10:00:00Z', '2026-11-01T10:00:00Z', '2026-11-01T10:00:00Z', 'active');

-- Una captura nueva preserva primera detección.
update public.catalogo_vacantes set first_seen_at = '2026-11-02T10:00:00Z', last_seen_at = '2026-11-02T10:00:00Z',
  observed_at = '2026-11-02T10:00:00Z' where id = 'aaaaaaaaaaaaaaaa';
-- Una respuesta vieja no reemplaza lo nuevo.
update public.catalogo_vacantes set description_full = 'Respuesta antigua', observed_at = '2026-11-01T12:00:00Z'
  where id = 'aaaaaaaaaaaaaaaa';
update public.catalogo_vacantes set status = 'closed', closed_at = '2026-11-03T10:00:00Z',
  observed_at = '2026-11-03T10:00:00Z' where id = 'aaaaaaaaaaaaaaaa';
-- Releer una caché no reabre una oferta cerrada.
update public.catalogo_vacantes set status = 'active', closed_at = null, observed_at = '2026-11-03T11:00:00Z'
  where id = 'aaaaaaaaaaaaaaaa';

do $$
begin
  if (select first_seen_at <> '2026-11-01T10:00:00Z' from public.catalogo_vacantes limit 1) then
    raise exception 'Se perdió primera detección'; end if;
  if (select status <> 'closed' from public.catalogo_vacantes limit 1) then
    raise exception 'Una caché reabrió una oferta'; end if;
  if (select description_full <> 'Descripción original' from public.catalogo_vacantes limit 1) then
    raise exception 'Una respuesta vieja sobrescribió contenido'; end if;
  if has_table_privilege('anon', 'public.catalogo_vacantes', 'SELECT') or
     has_table_privilege('authenticated', 'public.entregas_diarias', 'SELECT') then
    raise exception 'Hay acceso público al catálogo'; end if;
end;
$$;

-- Volver a verla realmente sí permite reabrirla.
update public.catalogo_vacantes set status = 'active', closed_at = null, last_seen_at = '2026-11-04T10:00:00Z',
  observed_at = '2026-11-04T10:00:00Z' where id = 'aaaaaaaaaaaaaaaa';
set local role service_role;
update public.catalogo_vacantes set observed_at = '2026-11-04T11:00:00Z'
  where id = 'aaaaaaaaaaaaaaaa';
insert into public.ofertas(external_id, job_title, company_name) values ('prueba-identidad', 'UX Designer', 'Empresa');
insert into public.entregas_diarias(vacante_id, delivery_date, role_id, match_grade, selected_at, snapshot)
 values ('aaaaaaaaaaaaaaaa', '2026-11-04', 'ux-ui-designer', 'exact', '2026-11-04T10:00:00Z', '{"id":"aaaaaaaaaaaaaaaa"}');
insert into public.entregas_diarias(vacante_id, delivery_date, role_id, match_grade, selected_at, snapshot)
 values ('aaaaaaaaaaaaaaaa', '2026-11-05', 'ux-ui-designer', 'exact', '2026-11-05T10:00:00Z', '{}')
 on conflict (vacante_id) do nothing;
reset role;
do $$
begin
  if (select delivery_date <> '2026-11-04' from public.entregas_diarias limit 1) then
    raise exception 'Se sobrescribió una entrega histórica'; end if;
  begin
    delete from public.catalogo_vacantes where id = 'aaaaaaaaaaaaaaaa';
    raise exception 'Se permitió borrar una oferta referenciada';
  exception when foreign_key_violation then null;
  end;
end;
$$;
rollback;
