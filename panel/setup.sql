-- Run once in your own Supabase project's SQL editor. No public policies.
create table if not exists public.panel_posts (
  id uuid primary key,
  created_at timestamptz not null default now(),
  caption text not null check (char_length(caption) between 1 and 2200),
  status text not null check (status in ('ready','queued','processing','uploading','published','failed','uncertain','deleting','deleted')),
  media_id text,
  instagram_url text,
  error text
);
alter table public.panel_posts enable row level security;
revoke all on public.panel_posts from anon, authenticated;
grant select, insert, update, delete on public.panel_posts to service_role;
create index if not exists panel_posts_queue on public.panel_posts(status, created_at);
insert into storage.buckets(id, name, public, file_size_limit, allowed_mime_types)
values ('kartal-panel', 'kartal-panel', false, 47185920, array['image/jpeg','video/mp4','application/json'])
on conflict (id) do update set public=false, file_size_limit=excluded.file_size_limit,
allowed_mime_types=excluded.allowed_mime_types;
