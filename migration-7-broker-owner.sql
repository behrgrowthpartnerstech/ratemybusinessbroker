-- ============================================================================
-- THE BROKER INDEX — migration 7: broker owner dashboard
-- Paste into Supabase → SQL Editor → New query → Run. Safe to re-run.
--
-- Lets the verified owner of a claimed broker page (brokers.claimed_by = them)
-- edit their own details and bio, and manage their listings (table + storage
-- bucket already exist from migration 3). They can NEVER touch reviews,
-- scores, rank_pin, slug or ownership — enforced by trigger, not by the UI.
-- Approving a claim now also drops a notification for the new owner.
-- ============================================================================

alter table public.brokers add column if not exists bio text not null default '';
alter table public.brokers add column if not exists linkedin text not null default '';
alter table public.brokers add column if not exists logo     text not null default '';
alter table public.brokers add column if not exists phone    text not null default '';

-- owner may update their row; the trigger below limits WHICH columns
drop policy if exists brokers_owner_update on public.brokers;
create policy brokers_owner_update on public.brokers for update
  using (claimed_by = auth.uid()) with check (claimed_by = auth.uid());
grant update on public.brokers to authenticated;

create or replace function public.guard_broker_owner_update()
returns trigger language plpgsql as $$
begin
  if auth.uid() is not null and not public.is_admin() then
    if new.claimed_by is distinct from old.claimed_by or new.rank_pin is distinct from old.rank_pin
       or new.slug is distinct from old.slug or new.source is distinct from old.source
       or new.id is distinct from old.id or new.created_at is distinct from old.created_at then
      raise exception 'only an admin can change ownership, slug, rank pin or source';
    end if;
    if length(new.name) < 2 or length(new.name) > 80 or length(new.firm) > 80 or length(new.city) > 60
       or length(new.state) > 2 or length(new.specialty) > 200 or length(new.bio) > 1200
       or length(new.website) > 200 or length(new.linkedin) > 200 or length(new.photo) > 300
       or length(new.logo) > 300 or length(new.phone) > 30 then
      raise exception 'field too long';
    end if;
    if new.website <> '' and new.website !~* '^https?://' then raise exception 'website must start with http(s)://'; end if;
    if new.linkedin <> '' and new.linkedin !~* '^https?://' then raise exception 'LinkedIn must start with http(s)://'; end if;
  end if;
  return new;
end $$;
drop trigger if exists brokers_owner_guard on public.brokers;
create trigger brokers_owner_guard before update on public.brokers
  for each row execute function public.guard_broker_owner_update();

-- claim approval → assign page + notify the new owner
create or replace function public.apply_claim_approval()
returns trigger language plpgsql security definer set search_path = public as $$
declare b record;
begin
  if new.status = 'approved' and old.status is distinct from 'approved' then
    update public.brokers set claimed_by = new.user_id where id = new.broker_id;
    update public.broker_claims set status = 'rejected'
      where broker_id = new.broker_id and id <> new.id and status = 'pending';
    select name, slug into b from public.brokers where id = new.broker_id;
    insert into public.notifications (user_id, kind, text, url)
      values (new.user_id, 'claim_approved', 'Your claim on ' || b.name || ' is approved. You can now manage the page.', '/broker-dashboard.html');
  elsif new.status = 'rejected' and old.status = 'pending' then
    insert into public.notifications (user_id, kind, text, url)
      values (new.user_id, 'claim_rejected', 'We could not verify your claim. Reply to our email or try again with a work address at your firm.', '/claim.html');
  end if;
  return new;
end $$;

-- listings: public inquiry counter (owner sees interest without exposing inquirers)
create table if not exists public.listing_inquiries (
  id         uuid primary key default gen_random_uuid(),
  listing_id uuid not null references public.listings(id) on delete cascade,
  user_id    uuid references public.profiles(id) on delete set null,
  name       text not null,
  email      text not null,
  message    text not null default '',
  created_at timestamptz not null default now()
);
create or replace function public.validate_inquiry()
returns trigger language plpgsql as $$
begin
  if new.email !~ '^[^@\s]+@[^@\s]+\.[^@\s]+$' then raise exception 'enter a valid email'; end if;
  if length(new.name) > 80 or length(new.message) > 800 then raise exception 'text too long'; end if;
  return new;
end $$;
drop trigger if exists inquiry_validate on public.listing_inquiries;
create trigger inquiry_validate before insert on public.listing_inquiries for each row execute function public.validate_inquiry();
alter table public.listing_inquiries enable row level security;
drop policy if exists inq_insert on public.listing_inquiries;
drop policy if exists inq_read   on public.listing_inquiries;
create policy inq_insert on public.listing_inquiries for insert with check (true);
create policy inq_read   on public.listing_inquiries for select
  using (public.is_admin() or exists (select 1 from public.listings l where l.id = listing_inquiries.listing_id and public.owns_broker(l.broker_id)));
grant insert on public.listing_inquiries to anon, authenticated;
grant select on public.listing_inquiries to authenticated;
grant select on public.listings to anon, authenticated;
grant insert, update, delete on public.listings to authenticated;
