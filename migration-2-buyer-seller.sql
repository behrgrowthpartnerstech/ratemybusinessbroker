-- Migration 2: buyer-vs-seller review perspectives
-- Paste into Supabase → SQL Editor → Run. Safe to re-run.
alter table public.reviews add column if not exists reviewer_role text not null default 'buyer'
  check (reviewer_role in ('buyer','seller'));
