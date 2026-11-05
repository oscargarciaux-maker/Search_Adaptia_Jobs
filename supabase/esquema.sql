-- Base de datos de la entrega diaria (Contrato de datos de ofertas — Adaptia Jobs v1, docs/CONTRATO_DATOS_v1.md).
-- Se pega una sola vez en Supabase: SQL Editor > New query > pegar todo > Run. Se puede volver a correr sin dañar nada.
-- Las listas del contrato se guardan como arreglos de texto; language_requirements como JSON
-- ([{"language":"en","level":"B2","required":true}]). Vacío en el CSV = NULL aquí.

create table if not exists public.ofertas (
  id                    bigint generated always as identity primary key,
  -- Identidad
  external_id           text not null unique,
  job_title             text not null check (char_length(job_title) <= 300),
  company_name          text not null check (char_length(company_name) <= 300),
  offer_url             text,
  source_portal         text,
  status                text not null default 'active' check (status in ('active', 'expired')),
  -- Fechas
  published_date        date,
  scraped_at            timestamptz,
  -- Ubicación
  location              text,
  work_mode             text check (work_mode in ('remote', 'hybrid', 'onsite')),
  office_city           text,
  office_country        text check (office_country ~ '^[A-Z]{2}$'),
  hire_scope            text check (hire_scope in ('city', 'country', 'region', 'worldwide')),
  hire_countries        text[],
  hire_regions          text[],
  -- Idioma
  posting_language      text check (posting_language in ('es', 'en')),
  language_requirements jsonb,
  -- Perfil
  employment_type       text check (employment_type in ('full_time', 'part_time', 'contract', 'internship', 'freelance')),
  seniority             text check (seniority in ('intern', 'junior', 'mid', 'senior', 'lead')),
  years_experience_min  smallint check (years_experience_min between 0 and 40),
  years_experience_max  smallint check (years_experience_max between 0 and 40),
  -- Sector y habilidades (la plataforma completa con IA lo que llegue vacío)
  industries            text[],
  keywords_role         text[],
  keywords_technical    text[],
  keywords_soft         text[],
  -- Compensación
  salary_text           text,
  salary_min            numeric,
  salary_max            numeric,
  salary_currency       text check (salary_currency ~ '^[A-Z]{3}$'),
  salary_period         text check (salary_period in ('hour', 'month', 'year')),
  -- Contenido
  description_full      text check (char_length(description_full) <= 30000),
  company_about         text,
  summary               text,
  apply_email           text,
  company_website       text,
  -- Extras de la entrega diaria
  search_tag            text,        -- rol de la entrega (Product designer, QA…)
  delivery_date         date,        -- día en que se entregó
  source_type           text,        -- oferta o publicacion
  match_grade           text,        -- exact, similar o close (qué tan parecido es el cargo al rol)
  created_at            timestamptz not null default now()
);

create index if not exists ofertas_entrega on public.ofertas (delivery_date desc, search_tag);

-- Nadie entra sin la clave secreta: con RLS activo y sin políticas, la clave pública (anon/publishable) no ve nada.
alter table public.ofertas enable row level security;

-- La entrega más reciente, lista para exportar a Excel (Table Editor > entrega_de_hoy > Export > CSV)
create or replace view public.entrega_de_hoy with (security_invoker = true) as
  select * from public.ofertas
  where delivery_date = (select max(delivery_date) from public.ofertas)
  order by search_tag, id;
