-- Contrato v48 (22 nov, decisión de Oscar): cada vacante del catálogo tiene un número corto y fijo («ID 1234») para
-- nombrarla en los mensajes de WhatsApp, en el panel y en el CSV. El identificador de 16 caracteres sigue siendo la
-- llave; el número solo la acompaña. Aditiva: una columna, una secuencia y un disparador; las vacantes ya guardadas se
-- numeran por orden de llegada y nunca se renumeran. No añade tablas ni toca otras columnas, funciones o permisos.
begin;
create sequence if not exists public.catalogo_vacantes_numero_seq as bigint;
alter table public.catalogo_vacantes add column if not exists numero bigint;
with orden as (
  select id, row_number() over (order by first_seen_at nulls last, observed_at, id) as n
  from public.catalogo_vacantes where numero is null)
update public.catalogo_vacantes c
   set numero = orden.n + coalesce((select max(numero) from public.catalogo_vacantes), 0)
  from orden where c.id = orden.id;
select setval('public.catalogo_vacantes_numero_seq',
              greatest(coalesce((select max(numero) from public.catalogo_vacantes), 0), 1),
              exists(select 1 from public.catalogo_vacantes));
alter sequence public.catalogo_vacantes_numero_seq owned by public.catalogo_vacantes.numero;
alter table public.catalogo_vacantes alter column numero set default nextval('public.catalogo_vacantes_numero_seq');
-- Una restauración de un respaldo anterior a esta migración trae numero nulo: se le da el siguiente.
create or replace function public.numerar_vacante() returns trigger
language plpgsql set search_path = '' as $$
begin
  if new.numero is null then new.numero := nextval('public.catalogo_vacantes_numero_seq'); end if;
  return new;
end $$;
drop trigger if exists numerar_vacante on public.catalogo_vacantes;
create trigger numerar_vacante before insert on public.catalogo_vacantes
  for each row execute function public.numerar_vacante();
-- El número nunca cambia una vez dado.
create or replace function public.conservar_numero_vacante() returns trigger
language plpgsql set search_path = '' as $$
begin
  new.numero := old.numero;
  return new;
end $$;
drop trigger if exists conservar_numero_vacante on public.catalogo_vacantes;
create trigger conservar_numero_vacante before update of numero on public.catalogo_vacantes
  for each row when (old.numero is not null) execute function public.conservar_numero_vacante();
alter table public.catalogo_vacantes alter column numero set not null;
create unique index if not exists catalogo_vacantes_numero on public.catalogo_vacantes(numero);
revoke all on sequence public.catalogo_vacantes_numero_seq from anon, authenticated;
grant usage, select on sequence public.catalogo_vacantes_numero_seq to service_role;
commit;
