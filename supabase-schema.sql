-- ============================================================================
-- THE BROKER INDEX — production schema (Supabase / Postgres)
-- Paste this whole file into Supabase → SQL Editor → New query → Run.
-- Safe to re-run: it drops and recreates its own objects.
-- ============================================================================

-- ---------- PROFILES (public identity = username; email stays in auth.users) --
create table if not exists public.profiles (
  id         uuid primary key references auth.users(id) on delete cascade,
  username   text unique,
  role       text not null default 'buyer' check (role in ('buyer','seller','both','other')),
  tier       text not null default 'member' check (tier in ('member','verified')),
  is_admin   boolean not null default false,
  created_at timestamptz not null default now()
);

-- ---------- helper: admin check (used by security policies) ----------
create or replace function public.is_admin()
returns boolean language sql stable security definer set search_path = public as
$$ select coalesce((select is_admin from public.profiles where id = auth.uid()), false) $$;

-- auto-create an empty profile on signup
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id) values (new.id) on conflict do nothing;
  return new;
end $$;
drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users for each row execute function public.handle_new_user();

-- members may edit their own username/role, never their own tier/admin flag
create or replace function public.guard_profile_update()
returns trigger language plpgsql as $$
begin
  if not public.is_admin() then
    if new.tier is distinct from old.tier or new.is_admin is distinct from old.is_admin then
      raise exception 'only an admin can change tier or admin status';
    end if;
  end if;
  return new;
end $$;
drop trigger if exists profiles_guard on public.profiles;
create trigger profiles_guard before update on public.profiles
  for each row execute function public.guard_profile_update();

-- ---------- BROKERS (directory: only the admin writes) ----------
create table if not exists public.brokers (
  id         uuid primary key default gen_random_uuid(),
  slug       text unique not null,
  name       text not null,
  firm       text not null default 'Independent',
  city       text not null default '—',
  state      text not null default '—',
  specialty  text not null default 'general SMB',
  photo      text not null default '',
  website    text not null default '',
  source     text not null default 'admin-added',
  rank_pin   integer check (rank_pin is null or rank_pin >= 1),
  created_at timestamptz not null default now()
);
create index if not exists brokers_name_state on public.brokers (lower(name), state);

-- ---------- REVIEWS ----------
create table if not exists public.reviews (
  id         uuid primary key default gen_random_uuid(),
  broker_id  uuid not null references public.brokers(id) on delete cascade,
  author_id  uuid not null references public.profiles(id) on delete cascade,
  ratings    jsonb not null,                     -- subset of the six params, values 1..5
  text       text not null default '',
  ctx        text not null default '',
  stage      text not null default '',
  status     text not null default 'published' check (status in ('published','removed')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (broker_id, author_id)                  -- one review per broker per member
);
create index if not exists reviews_broker on public.reviews (broker_id) where status = 'published';

-- validate ratings: known keys only, integers 1..5, at least one; cap text lengths
create or replace function public.validate_review()
returns trigger language plpgsql as $$
declare k text; v numeric; n int := 0;
begin
  if jsonb_typeof(new.ratings) is distinct from 'object' then
    raise exception 'ratings must be an object';
  end if;
  for k, v in select key, (value)::numeric from jsonb_each_text(new.ratings) loop
    if k not in ('professionalism','transparency','consistency','collaboration','command','documentation') then
      raise exception 'unknown rating key %', k;
    end if;
    if v < 1 or v > 5 or v <> round(v) then
      raise exception 'rating % out of range', k;
    end if;
    n := n + 1;
  end loop;
  if n = 0 then raise exception 'rate at least one parameter'; end if;
  if length(new.text) > 1500 or length(new.ctx) > 120 or length(new.stage) > 40 then
    raise exception 'text too long';
  end if;
  new.updated_at := now();
  return new;
end $$;
drop trigger if exists reviews_validate on public.reviews;
create trigger reviews_validate before insert or update on public.reviews
  for each row execute function public.validate_review();

-- ---------- VOTES / REPORTS / REQUESTS / PREFS / WATCHLIST / VERIFICATION ----
create table if not exists public.review_votes (
  review_id uuid not null references public.reviews(id) on delete cascade,
  voter_id  uuid not null references public.profiles(id) on delete cascade,
  primary key (review_id, voter_id)
);

create table if not exists public.reports (
  id          uuid primary key default gen_random_uuid(),
  review_id   uuid references public.reviews(id) on delete cascade,
  reporter_id uuid references public.profiles(id) on delete set null,
  reason      text not null,
  detail      text not null default '',
  status      text not null default 'open' check (status in ('open','dismissed','edited','removed')),
  created_at  timestamptz not null default now()
);

create table if not exists public.listing_requests (
  id           uuid primary key default gen_random_uuid(),
  name         text not null,
  firm         text not null default '',
  location     text not null default '',
  info         text not null default '',
  requested_by uuid references public.profiles(id) on delete set null,
  status       text not null default 'open' check (status in ('open','approved','dismissed')),
  created_at   timestamptz not null default now()
);

create table if not exists public.personal_prefs (   -- Beli-style ties, personal list only
  user_id  uuid not null references public.profiles(id) on delete cascade,
  pair_key text not null,                            -- "slugA|slugB" sorted
  winner   text not null,
  primary key (user_id, pair_key)
);

create table if not exists public.watchlists (
  user_id   uuid not null references public.profiles(id) on delete cascade,
  broker_id uuid not null references public.brokers(id) on delete cascade,
  primary key (user_id, broker_id)
);

create table if not exists public.verification_requests (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references public.profiles(id) on delete cascade,
  kind       text not null default 'other',
  status     text not null default 'pending' check (status in ('pending','approved','rejected')),
  created_at timestamptz not null default now()
);

-- ---------- ROW-LEVEL SECURITY ----------
alter table public.profiles              enable row level security;
alter table public.brokers               enable row level security;
alter table public.reviews               enable row level security;
alter table public.review_votes          enable row level security;
alter table public.reports               enable row level security;
alter table public.listing_requests      enable row level security;
alter table public.personal_prefs        enable row level security;
alter table public.watchlists            enable row level security;
alter table public.verification_requests enable row level security;

-- profiles: readable by all (holds no private data); self-update guarded by trigger
drop policy if exists profiles_read   on public.profiles;
drop policy if exists profiles_update on public.profiles;
create policy profiles_read   on public.profiles for select using (true);
create policy profiles_update on public.profiles for update
  using (id = auth.uid() or public.is_admin())
  with check (id = auth.uid() or public.is_admin());

-- brokers: world-readable; ONLY the admin writes (members physically cannot)
drop policy if exists brokers_read  on public.brokers;
drop policy if exists brokers_admin on public.brokers;
create policy brokers_read  on public.brokers for select using (true);
create policy brokers_admin on public.brokers for all
  using (public.is_admin()) with check (public.is_admin());

-- reviews: published ones public; authors manage their own; admin can do anything
drop policy if exists reviews_read   on public.reviews;
drop policy if exists reviews_insert on public.reviews;
drop policy if exists reviews_update on public.reviews;
drop policy if exists reviews_delete on public.reviews;
create policy reviews_read on public.reviews for select
  using (status = 'published' or author_id = auth.uid() or public.is_admin());
create policy reviews_insert on public.reviews for insert
  with check (author_id = auth.uid() and status = 'published');
create policy reviews_update on public.reviews for update
  using (author_id = auth.uid() or public.is_admin())
  with check ((author_id = auth.uid() and status = 'published') or public.is_admin());
create policy reviews_delete on public.reviews for delete
  using (author_id = auth.uid() or public.is_admin());

-- votes: public counts, own votes writable
drop policy if exists votes_read   on public.review_votes;
drop policy if exists votes_write  on public.review_votes;
drop policy if exists votes_delete on public.review_votes;
create policy votes_read   on public.review_votes for select using (true);
create policy votes_write  on public.review_votes for insert with check (voter_id = auth.uid());
create policy votes_delete on public.review_votes for delete using (voter_id = auth.uid());

-- reports: signed-in members file them; only admin reads/works the queue
drop policy if exists reports_insert on public.reports;
drop policy if exists reports_admin  on public.reports;
create policy reports_insert on public.reports for insert
  with check (reporter_id = auth.uid());
create policy reports_admin on public.reports for select using (public.is_admin());
drop policy if exists reports_update on public.reports;
create policy reports_update on public.reports for update
  using (public.is_admin()) with check (public.is_admin());

-- listing requests: members ask; admin sees and decides
drop policy if exists lreq_insert on public.listing_requests;
drop policy if exists lreq_read   on public.listing_requests;
drop policy if exists lreq_update on public.listing_requests;
create policy lreq_insert on public.listing_requests for insert
  with check (requested_by = auth.uid());
create policy lreq_read on public.listing_requests for select
  using (requested_by = auth.uid() or public.is_admin());
create policy lreq_update on public.listing_requests for update
  using (public.is_admin()) with check (public.is_admin());

-- prefs & watchlists: strictly personal
drop policy if exists prefs_all on public.personal_prefs;
create policy prefs_all on public.personal_prefs for all
  using (user_id = auth.uid()) with check (user_id = auth.uid());
drop policy if exists watch_all on public.watchlists;
create policy watch_all on public.watchlists for all
  using (user_id = auth.uid()) with check (user_id = auth.uid());

-- verification: request your own; admin reviews
drop policy if exists verif_insert on public.verification_requests;
drop policy if exists verif_read   on public.verification_requests;
drop policy if exists verif_update on public.verification_requests;
create policy verif_insert on public.verification_requests for insert
  with check (user_id = auth.uid());
create policy verif_read on public.verification_requests for select
  using (user_id = auth.uid() or public.is_admin());
create policy verif_update on public.verification_requests for update
  using (public.is_admin()) with check (public.is_admin());

-- ---------- KEEP-ALIVE ----------
-- A tiny public function the weekly ping calls; the call itself counts as
-- project activity, which is what prevents free-tier pausing.
create or replace function public.keepalive()
returns text language sql stable as
$$ select 'alive at ' || now()::text $$;
grant execute on function public.keepalive() to anon, authenticated;

-- ============================================================================
-- AFTER RUNNING THIS FILE:
-- 1. Sign in to the live site once with YOUR email (magic link).
-- 2. Come back to the SQL editor and run the line below with your email,
--    which makes your account the admin:
--
--    update public.profiles set is_admin = true, tier = 'verified'
--    where id = (select id from auth.users where email = 'behrfamily100@gmail.com');
--
-- ============================================================================
