-- ============================================================================
-- THE BROKER INDEX — migration 3: broker claims + active listings
-- Paste this whole file into Supabase → SQL Editor → New query → Run.
-- Safe to re-run.
--
-- SCORE FIREWALL: nothing here touches reviews or scoring. Claiming a page
-- or posting listings NEVER affects a broker's rating or rank.
-- ============================================================================

-- profiles: allow 'broker' as a role in the signup dropdown
alter table public.profiles drop constraint if exists profiles_role_check;
alter table public.profiles add constraint profiles_role_check
  check (role in ('buyer','seller','both','other','broker'));

-- broker ownership (set only when an admin approves a claim)
alter table public.brokers add column if not exists claimed_by uuid references public.profiles(id) on delete set null;

-- ---------- CLAIMS ----------
create table if not exists public.broker_claims (
  id         uuid primary key default gen_random_uuid(),
  broker_id  uuid not null references public.brokers(id) on delete cascade,
  user_id    uuid not null references public.profiles(id) on delete cascade,
  work_email text not null,
  evidence   text not null default '',
  status     text not null default 'pending' check (status in ('pending','approved','rejected')),
  created_at timestamptz not null default now(),
  unique (broker_id, user_id)
);
-- verification method chosen by the claimant (multiple options, see app)
alter table public.broker_claims add column if not exists method text not null default 'email';
alter table public.broker_claims add column if not exists verify_code text not null default '';

create or replace function public.validate_claim()
returns trigger language plpgsql as $$
begin
  if length(new.work_email) > 120 or new.work_email !~ '^[^@\s]+@[^@\s]+\.[^@\s]+$' then
    raise exception 'enter a valid work email';
  end if;
  if length(new.evidence) > 500 then raise exception 'evidence too long (max 500 chars)'; end if;
  if new.method not in ('email','linkedin','phone','other') then raise exception 'unknown verification method'; end if;
  if length(new.verify_code) > 20 then raise exception 'code too long'; end if;
  return new;
end $$;
drop trigger if exists broker_claims_validate on public.broker_claims;
create trigger broker_claims_validate before insert or update on public.broker_claims
  for each row execute function public.validate_claim();

-- approving a claim assigns the broker page to the claimant and
-- auto-rejects other pending claims on the same broker
create or replace function public.apply_claim_approval()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  if new.status = 'approved' and old.status is distinct from 'approved' then
    update public.brokers set claimed_by = new.user_id where id = new.broker_id;
    update public.broker_claims set status = 'rejected'
      where broker_id = new.broker_id and id <> new.id and status = 'pending';
  end if;
  return new;
end $$;
drop trigger if exists broker_claims_apply on public.broker_claims;
create trigger broker_claims_apply after update on public.broker_claims
  for each row execute function public.apply_claim_approval();

-- ---------- LISTINGS (max 5 active per broker; claimed owner only) ----------
create table if not exists public.listings (
  id            uuid primary key default gen_random_uuid(),
  broker_id     uuid not null references public.brokers(id) on delete cascade,
  title         text not null,
  industry      text not null default '',
  state         text not null default '',
  price_label   text not null default 'Inquire for price',
  summary       text not null default '',
  url           text not null default '',
  contact_email text not null default '',
  status        text not null default 'active' check (status in ('active','inactive')),
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);
create index if not exists listings_broker on public.listings (broker_id) where status = 'active';
-- media (photo + blind-teaser PDF), stored in the listing-media bucket
alter table public.listings add column if not exists photo_url  text not null default '';
alter table public.listings add column if not exists teaser_url text not null default '';

create or replace function public.validate_listing()
returns trigger language plpgsql as $$
declare n int;
begin
  if length(new.title) < 4 or length(new.title) > 90 then
    raise exception 'title must be 4-90 characters';
  end if;
  if length(new.industry) > 40 or length(new.state) > 30 or length(new.price_label) > 40
     or length(new.summary) > 240 or length(new.url) > 300 or length(new.contact_email) > 120
     or length(new.photo_url) > 300 or length(new.teaser_url) > 300 then
    raise exception 'field too long';
  end if;
  if new.url <> '' and new.url !~* '^https?://' then
    raise exception 'listing link must start with http:// or https://';
  end if;
  if new.contact_email <> '' and new.contact_email !~ '^[^@\s]+@[^@\s]+\.[^@\s]+$' then
    raise exception 'invalid contact email';
  end if;
  if new.status = 'active' then
    select count(*) into n from public.listings
      where broker_id = new.broker_id and status = 'active' and id <> new.id;
    if n >= 5 then
      raise exception 'limit reached: 5 active listings per broker (deactivate one first)';
    end if;
  end if;
  new.updated_at := now();
  return new;
end $$;
drop trigger if exists listings_validate on public.listings;
create trigger listings_validate before insert or update on public.listings
  for each row execute function public.validate_listing();

-- owner check helper (used by security policies)
create or replace function public.owns_broker(b uuid)
returns boolean language sql stable security definer set search_path = public as
$$ select coalesce((select claimed_by = auth.uid() from public.brokers where id = b), false) $$;

-- ---------- ROW-LEVEL SECURITY ----------
alter table public.broker_claims enable row level security;
alter table public.listings      enable row level security;

drop policy if exists claims_insert on public.broker_claims;
drop policy if exists claims_read   on public.broker_claims;
drop policy if exists claims_update on public.broker_claims;
create policy claims_insert on public.broker_claims for insert
  with check (auth.uid() = user_id);
create policy claims_read on public.broker_claims for select
  using (user_id = auth.uid() or public.is_admin());
create policy claims_update on public.broker_claims for update
  using (public.is_admin()) with check (public.is_admin());

drop policy if exists listings_read   on public.listings;
drop policy if exists listings_insert on public.listings;
drop policy if exists listings_update on public.listings;
drop policy if exists listings_delete on public.listings;
create policy listings_read on public.listings for select
  using (status = 'active' or public.owns_broker(broker_id) or public.is_admin());
create policy listings_insert on public.listings for insert
  with check (public.owns_broker(broker_id) or public.is_admin());
create policy listings_update on public.listings for update
  using (public.owns_broker(broker_id) or public.is_admin())
  with check (public.owns_broker(broker_id) or public.is_admin());
create policy listings_delete on public.listings for delete
  using (public.owns_broker(broker_id) or public.is_admin());

-- ---------- STORAGE: listing photos & blind-teaser PDFs ----------
-- Bucket enforces type + size at the server: images/PDF only, 5MB max.
-- Files live under <broker_id>/<listing_id>/..., and only the verified
-- owner of that broker page (or admin) can write there. Public can read.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('listing-media','listing-media', true, 5242880,
        array['image/jpeg','image/png','image/webp','application/pdf'])
on conflict (id) do update
  set public = true,
      file_size_limit = excluded.file_size_limit,
      allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists "listing media read"   on storage.objects;
drop policy if exists "listing media insert" on storage.objects;
drop policy if exists "listing media update" on storage.objects;
drop policy if exists "listing media delete" on storage.objects;
create policy "listing media read" on storage.objects for select
  using (bucket_id = 'listing-media');
create policy "listing media insert" on storage.objects for insert
  with check (bucket_id = 'listing-media'
    and (public.owns_broker(((storage.foldername(name))[1])::uuid) or public.is_admin()));
create policy "listing media update" on storage.objects for update
  using (bucket_id = 'listing-media'
    and (public.owns_broker(((storage.foldername(name))[1])::uuid) or public.is_admin()));
create policy "listing media delete" on storage.objects for delete
  using (bucket_id = 'listing-media'
    and (public.owns_broker(((storage.foldername(name))[1])::uuid) or public.is_admin()));
