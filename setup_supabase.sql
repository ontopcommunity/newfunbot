-- Chạy 1 lần trong Supabase Dashboard → SQL Editor → Run
-- Project: tdlubyvugaucfexezhrk

create table if not exists public.noitu_accounts (
  code text primary key,
  access_token text not null,
  refresh_token text not null,
  name text default '',
  level int default 1,
  xp int default 0,
  updated_at timestamptz default now(),
  created_at timestamptz default now()
);

alter table public.noitu_accounts enable row level security;

drop policy if exists "allow_all_service" on public.noitu_accounts;
create policy "allow_all_service" on public.noitu_accounts
  for all using (true) with check (true);

-- Index phụ
create index if not exists idx_noitu_accounts_level on public.noitu_accounts (level);
