-- ============================================================================
-- THE BROKER INDEX — migration 6: Sept 20 UX round
-- Paste into Supabase → SQL Editor → New query → Run. Safe to re-run.
--
-- What this adds:
--   * reviews: required deal context (industry, deal size), 'pending' status for
--     reviews of brokers not yet in the directory, moderation notes
--   * listing_requests → can be approved straight into a broker row, which
--     publishes any reviews waiting on it and notifies the reviewers
--   * profiles: public profile fields (blurb, buyer type, labels, acquisitions)
--   * watchlists: ranked order + private note ("My List")
--   * introductions: quiz "introduce me" requests
--   * interactions: the buyer dashboard's deal log
--   * notifications: in-app inbox (review published, etc.)
--   * site_stats(): hero counters (brokers / registered buyers / reviews)
--
-- SCORE FIREWALL: nothing here changes how a broker's rating is computed.
-- ============================================================================

-- ---------------------------------------------------------------- reviews
alter table public.reviews alter column broker_id drop not null;
alter table public.reviews add column if not exists request_id uuid references public.listing_requests(id) on delete set null;
alter table public.reviews add column if not exists industry  text not null default '';
alter table public.reviews add column if not exists deal_size text not null default '';
alter table public.reviews add column if not exists mod_note  text not null default '';   -- why held / what was flagged
alter table public.reviews add column if not exists mod_flags jsonb not null default '[]'::jsonb;

alter table public.reviews drop constraint if exists reviews_status_check;
alter table public.reviews add constraint reviews_status_check
  check (status in ('published','pending','removed','rejected'));

-- a review must point at a broker OR at a listing request (never neither)
alter table public.reviews drop constraint if exists reviews_target_chk;
alter table public.reviews add constraint reviews_target_chk
  check (broker_id is not null or request_id is not null);

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
  -- new reviews: all six parameters, a side, a stage, deal context and the write-up are required
  if tg_op = 'INSERT' then
    if n < 6 then raise exception 'all six parameters are required'; end if;
    if new.side not in ('buyer','seller') then raise exception 'choose buyer or seller'; end if;
    if length(trim(new.stage)) = 0 then raise exception 'deal stage is required'; end if;
    if length(trim(new.industry)) = 0 or length(trim(new.deal_size)) = 0 then raise exception 'deal context is required'; end if;
    if length(trim(new.text)) < 40 then raise exception 'tell us about your experience (at least 40 characters)'; end if;
  end if;
  if length(new.text) > 1500 or length(new.ctx) > 120 or length(new.stage) > 40
     or length(new.industry) > 60 or length(new.deal_size) > 30 or length(new.mod_note) > 500 then
    raise exception 'text too long';
  end if;
  new.updated_at := now();
  return new;
end $$;

-- members may submit as published or pending; only admins set anything else
drop policy if exists reviews_insert on public.reviews;
create policy reviews_insert on public.reviews for insert
  with check (author_id = auth.uid() and status in ('published','pending'));
drop policy if exists reviews_update on public.reviews;
create policy reviews_update on public.reviews for update
  using (author_id = auth.uid() or public.is_admin())
  with check ((author_id = auth.uid() and status in ('published','pending')) or public.is_admin());

create index if not exists reviews_pending on public.reviews (request_id) where status = 'pending';

-- ---------------------------------------------------------------- listing requests
alter table public.listing_requests add column if not exists city   text not null default '';
alter table public.listing_requests add column if not exists state  text not null default '';
alter table public.listing_requests add column if not exists broker_id uuid references public.brokers(id) on delete set null;

-- ---------------------------------------------------------------- profiles (public page)
alter table public.profiles add column if not exists headline     text not null default '';   -- "Serial acquirer", "First-time seller"…
alter table public.profiles add column if not exists bio          text not null default '';
alter table public.profiles add column if not exists labels       text[] not null default '{}';
alter table public.profiles add column if not exists acquisitions int  not null default 0;
alter table public.profiles add column if not exists target_size  text not null default '';
alter table public.profiles add column if not exists industries   text not null default '';
alter table public.profiles add column if not exists location     text not null default '';
alter table public.profiles add column if not exists list_public  boolean not null default true;

create or replace function public.validate_profile()
returns trigger language plpgsql as $$
begin
  if length(new.headline) > 60 or length(new.bio) > 600 or length(new.target_size) > 30
     or length(new.industries) > 200 or length(new.location) > 80 or array_length(new.labels,1) > 6
     or new.acquisitions < 0 or new.acquisitions > 999 then
    raise exception 'profile field too long';
  end if;
  return new;
end $$;
drop trigger if exists profiles_validate on public.profiles;
create trigger profiles_validate before insert or update on public.profiles
  for each row execute function public.validate_profile();

-- ---------------------------------------------------------------- My List: ranked + notes
alter table public.watchlists add column if not exists rank int  not null default 999;
alter table public.watchlists add column if not exists note text not null default '';
alter table public.watchlists add column if not exists created_at timestamptz not null default now();

-- public lists are readable by everyone; private ones only by their owner
drop policy if exists watch_all  on public.watchlists;
drop policy if exists watch_read on public.watchlists;
drop policy if exists watch_write on public.watchlists;
create policy watch_read on public.watchlists for select
  using (user_id = auth.uid()
     or exists (select 1 from public.profiles p where p.id = watchlists.user_id and p.list_public));
create policy watch_write on public.watchlists for all
  using (user_id = auth.uid()) with check (user_id = auth.uid());
grant select on public.watchlists to anon, authenticated;
grant insert, update, delete on public.watchlists to authenticated;

-- ---------------------------------------------------------------- quiz introductions
create table if not exists public.introductions (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid references public.profiles(id) on delete set null,
  name        text not null,
  email       text not null,
  note        text not null default '',
  state       text not null default '',
  industry    text not null default '',
  deal_size   text not null default '',
  timeline    text not null default '',
  priorities  text[] not null default '{}',
  broker_ids  uuid[] not null default '{}',
  consent     boolean not null default false,
  status      text not null default 'new' check (status in ('new','sent','declined')),
  created_at  timestamptz not null default now()
);
create or replace function public.validate_intro()
returns trigger language plpgsql as $$
begin
  if new.email !~ '^[^@\s]+@[^@\s]+\.[^@\s]+$' then raise exception 'enter a valid email'; end if;
  if not new.consent then raise exception 'consent is required to pass your details to a broker'; end if;
  if array_length(new.broker_ids,1) is null or array_length(new.broker_ids,1) > 5 then raise exception 'pick 1 to 5 brokers'; end if;
  if length(new.name) > 80 or length(new.note) > 600 then raise exception 'text too long'; end if;
  return new;
end $$;
drop trigger if exists intro_validate on public.introductions;
create trigger intro_validate before insert on public.introductions
  for each row execute function public.validate_intro();
alter table public.introductions enable row level security;
drop policy if exists intro_insert on public.introductions;
drop policy if exists intro_read   on public.introductions;
drop policy if exists intro_update on public.introductions;
create policy intro_insert on public.introductions for insert with check (true);   -- anyone, even signed out
create policy intro_read   on public.introductions for select using (user_id = auth.uid() or public.is_admin());
create policy intro_update on public.introductions for update using (public.is_admin()) with check (public.is_admin());
grant insert on public.introductions to anon, authenticated;
grant select, update on public.introductions to authenticated;

-- ---------------------------------------------------------------- buyer dashboard: deal log
create table if not exists public.interactions (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references public.profiles(id) on delete cascade,
  broker_id   uuid references public.brokers(id) on delete set null,
  kind        text not null check (kind in ('contacted','replied','cim','loi','closed','passed')),
  happened_at date not null default current_date,
  note        text not null default '',
  created_at  timestamptz not null default now()
);
create index if not exists interactions_user on public.interactions (user_id, happened_at);
alter table public.interactions enable row level security;
drop policy if exists inter_all on public.interactions;
create policy inter_all on public.interactions for all
  using (user_id = auth.uid()) with check (user_id = auth.uid() and length(note) <= 200);
grant select, insert, update, delete on public.interactions to authenticated;

-- ---------------------------------------------------------------- notifications
create table if not exists public.notifications (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references public.profiles(id) on delete cascade,
  kind       text not null default 'info',
  text       text not null,
  url        text not null default '',
  read       boolean not null default false,
  created_at timestamptz not null default now()
);
create index if not exists notif_user on public.notifications (user_id, read);
alter table public.notifications enable row level security;
drop policy if exists notif_read   on public.notifications;
drop policy if exists notif_update on public.notifications;
create policy notif_read   on public.notifications for select using (user_id = auth.uid());
create policy notif_update on public.notifications for update using (user_id = auth.uid()) with check (user_id = auth.uid());
grant select, update on public.notifications to authenticated;

-- ---------------------------------------------------------------- admin: approve a listing request into a real broker
-- Creates the broker, marks the request approved, publishes every review that
-- was waiting on it, and drops a notification for each reviewer.
create or replace function public.admin_approve_listing_request(req uuid, p_slug text default null, p_specialty text default 'general SMB')
returns uuid language plpgsql security definer set search_path = public as $$
declare r record; bid uuid; s text; base text; i int := 0; rv record;
begin
  if not public.is_admin() then raise exception 'admin only'; end if;
  select * into r from public.listing_requests where id = req;
  if r.id is null then raise exception 'request not found'; end if;
  if r.broker_id is not null then return r.broker_id; end if;
  base := coalesce(nullif(p_slug,''), lower(regexp_replace(regexp_replace(r.name || '-' || coalesce(nullif(r.state,''),'x'), '[^a-zA-Z0-9]+', '-', 'g'), '(^-|-$)', '', 'g')));
  s := base;
  while exists (select 1 from public.brokers where slug = s) loop i := i + 1; s := base || '-' || i; end loop;
  insert into public.brokers (slug, name, firm, city, state, specialty, source)
    values (s, r.name, coalesce(nullif(r.firm,''),'Independent'), coalesce(nullif(r.city,''), nullif(r.location,''), '—'),
            coalesce(nullif(upper(r.state),''),'—'), coalesce(nullif(p_specialty,''),'general SMB'), 'member-request')
    returning id into bid;
  update public.listing_requests set status = 'approved', broker_id = bid where id = req;
  for rv in select id, author_id from public.reviews where request_id = req and status = 'pending' loop
    update public.reviews set broker_id = bid, status = 'published' where id = rv.id;
    insert into public.notifications (user_id, kind, text, url)
      values (rv.author_id, 'review_live', 'Your review of ' || r.name || ' is now live. Thank you for adding to the record.', '/broker-' || s || '.html');
  end loop;
  return bid;
end $$;
grant execute on function public.admin_approve_listing_request(uuid, text, text) to authenticated;

-- admin: link a pending review to an EXISTING broker (dedupe path) and publish it
create or replace function public.admin_publish_pending_review(rid uuid, bid uuid)
returns void language plpgsql security definer set search_path = public as $$
declare rv record; b record;
begin
  if not public.is_admin() then raise exception 'admin only'; end if;
  select * into rv from public.reviews where id = rid;
  select * into b from public.brokers where id = bid;
  if rv.id is null or b.id is null then raise exception 'not found'; end if;
  update public.reviews set broker_id = bid, status = 'published' where id = rid;
  if rv.request_id is not null then update public.listing_requests set status = 'approved', broker_id = bid where id = rv.request_id; end if;
  insert into public.notifications (user_id, kind, text, url)
    values (rv.author_id, 'review_live', 'Your review of ' || b.name || ' is now live.', '/broker-' || b.slug || '.html');
end $$;
grant execute on function public.admin_publish_pending_review(uuid, uuid) to authenticated;

-- ---------------------------------------------------------------- hero counters
create or replace function public.site_stats()
returns json language sql stable security definer set search_path = public as $$
  select json_build_object(
    'brokers', (select count(*) from public.brokers),
    'buyers',  (select count(*) from public.profiles where role in ('buyer','both') and username is not null),
    'members', (select count(*) from public.profiles where username is not null),
    'reviews', (select count(*) from public.reviews where status = 'published'))
$$;
grant execute on function public.site_stats() to anon, authenticated;

-- ---------------------------------------------------------------- grants sanity (some projects were missing these)
grant select on public.brokers, public.reviews, public.profiles, public.review_votes to anon, authenticated;
grant insert, update, delete on public.reviews to authenticated;
grant select, insert, update on public.listing_requests to authenticated;
grant select, insert, update on public.broker_claims to authenticated;

-- ---------------------------------------------------------------- monthly broker digest support
alter table public.profiles add column if not exists digest_opt_out boolean not null default false;
-- The scheduled email function (server-side, service key only) needs owner emails.
-- This view is NOT readable by the browser roles.
create or replace view public.auth_email as select id, email from auth.users;
revoke all on public.auth_email from anon, authenticated;
