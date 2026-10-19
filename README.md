# Next Reel

Movie and TV roulette, in the spirit of [Next Stop](https://www.nextstoprr.com). Pick the services you pay for, say whether free, rental or buy is fine, choose genres and flavour, and spin. Three come up and one gets watched. In a watch party everyone votes from their own phone and the winner reveals to the room.

## How it's built

| Piece | What |
|---|---|
| Front end | `public/`: plain HTML/CSS/JS, no build step. Prefs live in each phone's localStorage |
| API | `api/*.py`: Vercel Python functions (standard library only), all routed through `lib/core.py` |
| Titles | `lib/tmdb.py`: live from TMDB (watch providers by JustWatch) when `TMDB_API_KEY` is set; otherwise the bundled `public/catalog.json` |
| Parties | `lib/rooms.py`: Supabase tables `reel_rooms`, `reel_players`, `reel_votes` (see `supabase/schema.sql`); RLS on, no policies, server-only key |

## Environment (Vercel → Settings → Environment Variables)

| Name | What | Needed for |
|---|---|---|
| `TMDB_API_KEY` | TMDB v3 API key, or a v4 read token | Live titles and posters |
| `SUPABASE_URL` | `https://<project>.supabase.co` | Watch parties |
| `SUPABASE_SECRET_KEY` | Secret key (`sb_secret_…`) or legacy service_role key; **server only, never `VITE_`/`NEXT_PUBLIC_`** | Watch parties |

With none set, the app still works: built-in catalog, and parties say "almost ready".

## Run locally

```sh
python3 dev_server.py                       # http://127.0.0.1:8860, rooms in memory
TMDB_API_KEY=... python3 dev_server.py      # live titles
python3 -m unittest discover -s tests
```

Edit titles in `catalog.py`, then run `python3 catalog.py` to rebuild `public/catalog.json`. A test fails if it's stale.

This product uses the TMDB API but is not endorsed or certified by TMDB.
