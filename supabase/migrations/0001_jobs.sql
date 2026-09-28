-- Reel Forge render app: job status table + public bucket for finished videos.
-- Run this once in the Supabase project's SQL editor (or via `supabase db push`).

create table if not exists public.jobs (
  id uuid primary key,
  status text not null default 'queued',       -- queued | running | done | error
  progress text,
  topic text,
  language text,
  result_url text,
  error text,
  created_at timestamptz not null default now()
);

alter table public.jobs enable row level security;
-- The app only ever talks to this table with the SERVICE ROLE key (server-side,
-- in webapp/backend/supabase_client.py), which bypasses RLS. No public policies
-- are defined, so anon/browser clients cannot read or write jobs directly.

insert into storage.buckets (id, name, public)
values ('videos', 'videos', true)
on conflict (id) do nothing;
-- Public so a finished video's URL (supabase_client.upload_video's return value)
-- plays directly in the browser's <video> tag with no extra auth.
