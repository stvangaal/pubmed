-- owner: project-infrastructure
-- Supabase schema for PubMed Monitor B2B features.
-- Run this in the Supabase SQL Editor to bootstrap the database.

-- User profiles (extends Supabase auth.users)
create table public.profiles (
  id uuid references auth.users on delete cascade primary key,
  display_name text,
  created_at timestamptz default now()
);

-- Auto-create profile on signup
create or replace function public.handle_new_user()
returns trigger as $$
begin
  insert into public.profiles (id)
  values (new.id);
  return new;
end;
$$ language plpgsql security definer;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- Domain subscriptions (per-domain for now; subdomain tags added later)
create table public.subscriptions (
  id uuid default gen_random_uuid() primary key,
  user_id uuid references public.profiles(id) on delete cascade not null,
  domain text not null,
  active boolean default true,
  created_at timestamptz default now(),
  unique(user_id, domain)
);

-- Digest archive
create table public.digests (
  id uuid default gen_random_uuid() primary key,
  domain text not null,
  run_date date not null,
  article_count int,
  content_html text,
  content_markdown text,
  blog_url text,
  created_at timestamptz default now(),
  unique(domain, run_date)
);

-- Article index (searchable, linkable)
create table public.articles (
  id uuid default gen_random_uuid() primary key,
  digest_id uuid references public.digests(id) on delete cascade not null,
  pmid text not null,
  title text,
  journal text,
  pub_date date,
  subdomain text,
  triage_score real,
  summary_short text,
  summary_full text,
  doi text,
  created_at timestamptz default now()
);

-- Row Level Security
alter table public.profiles enable row level security;
alter table public.subscriptions enable row level security;
alter table public.digests enable row level security;
alter table public.articles enable row level security;

-- Profiles: users can read/update their own
create policy "Users can view own profile"
  on public.profiles for select
  using (auth.uid() = id);

create policy "Users can update own profile"
  on public.profiles for update
  using (auth.uid() = id);

-- Subscriptions: users manage their own
create policy "Users can view own subscriptions"
  on public.subscriptions for select
  using (auth.uid() = user_id);

create policy "Users can insert own subscriptions"
  on public.subscriptions for insert
  with check (auth.uid() = user_id);

create policy "Users can update own subscriptions"
  on public.subscriptions for update
  using (auth.uid() = user_id);

create policy "Users can delete own subscriptions"
  on public.subscriptions for delete
  using (auth.uid() = user_id);

-- Digests & articles: public read (anyone can browse archive)
create policy "Digests are public"
  on public.digests for select
  using (true);

create policy "Articles are public"
  on public.articles for select
  using (true);

-- Service role can insert digests and articles (pipeline writes via service key)
create policy "Service role can insert digests"
  on public.digests for insert
  with check (true);

create policy "Service role can insert articles"
  on public.articles for insert
  with check (true);

-- RPC function: get subscriber emails for a domain (called by pipeline)
create or replace function public.get_subscriber_emails(target_domain text)
returns table(email text) as $$
begin
  return query
    select au.email
    from public.subscriptions s
    join auth.users au on au.id = s.user_id
    where s.domain = target_domain
      and s.active = true;
end;
$$ language plpgsql security definer;

-- Indexes for common queries
create index idx_subscriptions_domain on public.subscriptions(domain) where active = true;
create index idx_digests_domain_date on public.digests(domain, run_date desc);
create index idx_articles_digest on public.articles(digest_id);
create index idx_articles_subdomain on public.articles(subdomain);
