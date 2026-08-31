# Rate My Business Broker

Live site: https://ratemybusinessbroker.com

Independent ratings and reviews of U.S. business brokers, from the buyers and
sellers who actually worked with them.

## How this deploys
This repository is connected to Netlify. Any change pushed here is published
to the live site automatically — no manual upload.

- `index.html` — the entire site (single-file app)
- `database/` — Supabase schema and migrations (run in the Supabase SQL editor)

## Database setup (one time)
1. `database/supabase-schema.sql` — the full schema, run once on a new project.
2. `database/migration-2-buyer-seller.sql` — adds buyer/seller support; run once.
