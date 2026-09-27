# Google sign-in setup

Sign-in uses **Supabase Auth** with Google as the provider. It takes about 15 minutes and is
free. You create two things: a Supabase project and a Google OAuth client.

## 1. Create the Supabase project

1. Go to https://supabase.com, sign up, and create a **New project**. Pick the region
   **South Asia (Mumbai)**.
2. When it's ready, open **Project Settings -> API** (or **Data API**) and copy:
   - the **Project URL**, e.g. `https://abcdefgh.supabase.co`
   - the **publishable key** (called the **anon** key on older projects)

## 2. Create the Google OAuth client

1. Go to https://console.cloud.google.com and create a project (e.g. "My Career AI").
2. **APIs & Services -> OAuth consent screen**: choose **External**, fill in the app name
   and your email, and save. While the app is in *Testing* mode, add your own Google account
   under **Test users**.
3. **APIs & Services -> Credentials -> Create credentials -> OAuth client ID**:
   - Application type: **Web application**
   - **Authorised redirect URIs**: `https://<your-project>.supabase.co/auth/v1/callback`
     (Supabase shows this exact URL on its Google provider page).
4. Copy the **Client ID** and **Client secret**.

## 3. Connect them in Supabase

1. Supabase -> **Authentication -> Sign In / Providers -> Google**: enable it, paste the
   Client ID and Client secret, and save.
2. Supabase -> **Authentication -> URL Configuration**:
   - **Site URL**: `http://localhost:3000` for now (your real domain later)
   - **Redirect URLs**: add `http://localhost:3000/auth/callback` (and later
     `https://<your-domain>/auth/callback`). If you changed `WEB_HOST_PORT`, use that port.

## 4. Add the values to the app

In the root `.env` (never `.env.example`):

```
SUPABASE_URL=https://abcdefgh.supabase.co
SUPABASE_ANON_KEY=sb_publishable_...
```

Restart with `docker compose up`. The sign-in page now shows **Continue with Google**. The
development login stays underneath for local testing; in production set
`NEXT_PUBLIC_DEV_LOGIN=false` on the web app and `AUTH_MODE=supabase` on the API to remove it.

## How it works

- The browser signs in with Google through Supabase (PKCE flow) and gets a short-lived access
  token, which the Supabase client refreshes automatically.
- Every API request sends that token. The API verifies it against the project's public
  signing keys (`SUPABASE_URL/auth/v1/.well-known/jwks.json`) and creates the user on first
  sign-in.
- The publishable/anon key is designed to be public; it is safe in the browser.
