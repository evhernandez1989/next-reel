-- Next Reel watch parties. Paste into the Supabase SQL editor (Next Stop's project) and run once.
-- Separate reel_ tables; Next Stop's rooms/players/votes are untouched.
-- RLS on with NO policies: the browser's publishable key can't see these tables at all.
-- Only the Next Reel server, holding the secret key, reads and writes them.

create table if not exists reel_rooms (
  code        text primary key check (code ~ '^[A-Z]{4}$'),
  host_hash   text not null,
  host_player text not null,
  status      text not null default 'lobby' check (status in ('lobby', 'voting', 'revealed')),
  round       int  not null default 0,
  candidates  jsonb not null default '[]',
  winner      text,
  created_at  timestamptz not null default now(),
  touched_at  timestamptz not null default now()
);

create table if not exists reel_players (
  room_code text not null references reel_rooms(code) on delete cascade,
  id        text not null,
  name      text not null check (char_length(name) <= 24),
  joined_at timestamptz not null default now(),
  primary key (room_code, id)
);

create table if not exists reel_votes (
  room_code text not null references reel_rooms(code) on delete cascade,
  player    text not null,
  round     int  not null,
  pick      text not null,
  primary key (room_code, player, round)
);

create index if not exists reel_rooms_touched on reel_rooms (touched_at);

alter table reel_rooms   enable row level security;
alter table reel_players enable row level security;
alter table reel_votes   enable row level security;

revoke all on reel_rooms, reel_players, reel_votes from anon, authenticated;
