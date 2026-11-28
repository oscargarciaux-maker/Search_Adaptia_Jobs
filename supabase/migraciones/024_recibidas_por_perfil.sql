-- 28 nov (P-12.1): «lo que ya recibió» cada persona (`panel_asignaciones` por `perfil_id`) se lee completo una vez por
-- corrida, por páginas ordenadas por `id` (antes con OFFSET, sin orden y con un tope silencioso de 5.000 filas).
-- Este índice hace que esa lectura (`perfil_id = any(...)`) no recorra toda la tabla, que crece cada día con todos
-- los clientes, y sirve también para «¿esta persona ya recibió esta vacante?». Solo añade un índice: no toca tablas,
-- columnas, datos, permisos ni funciones.
begin;
create index if not exists panel_asignaciones_perfil_vacante on public.panel_asignaciones(perfil_id, vacante_id);
analyze public.panel_asignaciones;
commit;
