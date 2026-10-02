# Keeping the Wharf-ai usage log in Supabase

Without a database, the usage log (questions, costs, thumbs up and down, flagged
numbers) and saved chats live in a SQLite file on the app's disk, and Streamlit
Cloud wipes that file on every restart and redeploy. With `USAGE_DATABASE_URL`
set to a Postgres connection string, `usage.py` keeps them in two tables,
`wharf_questions` and `wharf_chats`, which it creates on first use. Supabase's
free plan is plenty for this.

## 1. Create the project (about 5 minutes)

1. Go to <https://supabase.com> and sign in (GitHub or email).
2. If asked, create an organisation (any name, **Free** plan).
3. Click **New project** and fill in:
   - **Name**: `freo-coach-view`
   - **Database password**: click **Generate a password**, then save it in your
     password manager. You need it in step 2 and can't see it again (you can reset it).
     A password with only letters and digits saves URL-encoding trouble later.
   - **Region**: **Asia-Pacific (Sydney)**, the closest to Perth.
4. Click **Create new project** and wait a minute or two while it sets up.

## 2. Copy the connection string

1. In the project, click **Connect** at the top of the page.
2. Under **Connection string**, choose the **Session pooler** method (not
   "Direct connection": the direct address is IPv6 only on the free plan, and
   Streamlit Cloud connects over IPv4).
3. Copy the URI. It looks like:

   ```
   postgresql://postgres.abcdefghijklmnop:[YOUR-PASSWORD]@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres
   ```

   (The host may start `aws-1-` instead of `aws-0-`; copy it as shown.)
4. Replace `[YOUR-PASSWORD]` (brackets included) with the password from step 1.
   If the password has characters like `@`, `:`, `/`, `#` or `%`, URL-encode them
   (`@` is `%40`), or reset the password to letters and digits
   (**Project Settings -> Database -> Reset database password**).
5. Add `?sslmode=require` to the end.

## 3. Put it in the secrets

The connection string holds the password: it goes in secrets only, never in
the code (the repo is public).

**Locally**, in `.streamlit/secrets.toml` (gitignored), above any `[auth]`
section:

```toml
USAGE_DATABASE_URL = "postgresql://postgres.abcdefghijklmnop:PASSWORD@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres?sslmode=require"
```

Check it connects (this creates the two tables and reads the counts):

```bash
.venv/bin/python -c "import usage; print(usage.summary())"
```

You should see `'store': 'Postgres (USAGE_DATABASE_URL)'` and `'error': None`.

**On Streamlit Cloud**: open the app, **Settings -> Secrets**, add the same
line **above** the `[auth]` section (`[auth]` must stay last), and **Save**. The
app restarts.

## 4. Check it's working

1. In the app, ask Wharf-ai a question.
2. Open the usage page (the chart icon next to `?`, admins only). The note at
   the bottom should say the log is kept in Postgres.
3. In Supabase, open **Table Editor**: `wharf_questions` has your question.
   Both tables show row-level security as enabled, with no policies. That's
   deliberate: Supabase's public Data API can't read them, while the app
   connects as the database owner and can.

## Before switching over

The first deploy with the database starts a fresh log; the rows in the old
SQLite file aren't copied across. If you want them, download the CSV from the
usage page first.

## Things to know

- **Free projects pause after about a week with no activity** (in the
  off-season, say). While paused, Wharf-ai keeps working but nothing is
  logged and the caps read 0; the usage page shows a warning. Restore the
  project from the Supabase dashboard (one click). If that becomes a nuisance, a
  weekly GitHub Action that runs `select 1` keeps it awake.
- **If the database is unreachable**, the app tries again after a minute
  rather than on every click, so a down database never slows the app.
- **Tests**: `tests/test_usage_pg.py` empties the `wharf_` tables, so it only
  runs when `USAGE_TEST_DATABASE_URL` is set, and CI points that at a
  throwaway Postgres. Never set it to the live database.
- **Reviewing feedback**: `python evals/review_feedback.py` reads the log from
  whichever store `usage.py` is set up for (Postgres once the secret is in
  `.streamlit/secrets.toml`).
