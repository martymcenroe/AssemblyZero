/**
 * GitHub OAuth routes for the telemetry dashboard.
 *
 * Cookie-based JWT sessions restricted to a single GitHub user.
 */

import { Hono } from "hono";
import { getCookie, setCookie, deleteCookie } from "hono/cookie";
import { sign, verify } from "hono/jwt";
import type { Env } from "./dynamo";

const auth = new Hono<{ Bindings: Env }>();

/** Redirect to GitHub OAuth authorize page. */
auth.get("/github", (c) => {
  const state = crypto.randomUUID();

  setCookie(c, "oauth_state", state, {
    httpOnly: true,
    secure: true,
    sameSite: "Lax",
    path: "/",
    maxAge: 600,
  });

  const callbackUrl = new URL("/api/auth/callback", c.req.url).toString();
  const params = new URLSearchParams({
    client_id: c.env.GITHUB_CLIENT_ID,
    redirect_uri: callbackUrl,
    scope: "read:user",
    state,
  });

  return c.redirect(`https://github.com/login/oauth/authorize?${params}`);
});

/** Exchange code for token, verify user, set JWT cookie. */
auth.get("/callback", async (c) => {
  const code = c.req.query("code");
  const state = c.req.query("state");
  const savedState = getCookie(c, "oauth_state");

  deleteCookie(c, "oauth_state", { path: "/" });

  if (!code || !state || state !== savedState) {
    return c.json({ error: "Invalid OAuth state" }, 403);
  }

  // Exchange code for access token
  const tokenRes = await fetch("https://github.com/login/oauth/access_token", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({
      client_id: c.env.GITHUB_CLIENT_ID,
      client_secret: c.env.GITHUB_CLIENT_SECRET,
      code,
    }),
  });

  const tokenData = (await tokenRes.json()) as {
    access_token?: string;
    error?: string;
  };
  if (!tokenData.access_token) {
    return c.json({ error: "Failed to get access token" }, 403);
  }

  // Fetch GitHub user profile
  const userRes = await fetch("https://api.github.com/user", {
    headers: {
      Authorization: `Bearer ${tokenData.access_token}`,
      "User-Agent": "AssemblyZero-Telemetry",
    },
  });

  const user = (await userRes.json()) as {
    login?: string;
    avatar_url?: string;
  };

  // Verify allowed username
  const allowed = c.env.ALLOWED_GITHUB_USERNAME;
  if (user.login !== allowed) {
    return c.json({ error: "Unauthorized user" }, 403);
  }

  // Sign JWT and set session cookie
  const token = await sign(
    {
      sub: user.login,
      avatar: user.avatar_url,
      exp: Math.floor(Date.now() / 1000) + 86400,
    },
    c.env.JWT_SECRET,
  );

  setCookie(c, "session", token, {
    httpOnly: true,
    secure: true,
    sameSite: "Lax",
    path: "/",
    maxAge: 86400,
  });

  return c.redirect("/");
});

/** Return current user info from JWT cookie. */
auth.get("/user", async (c) => {
  const token = getCookie(c, "session");
  if (!token) {
    return c.json({ error: "Not authenticated" }, 401);
  }

  try {
    const payload = await verify(token, c.env.JWT_SECRET, "HS256");
    return c.json({ login: payload.sub, avatar: payload.avatar });
  } catch {
    deleteCookie(c, "session", { path: "/" });
    return c.json({ error: "Invalid session" }, 401);
  }
});

/** Clear session cookie. */
auth.post("/logout", (c) => {
  deleteCookie(c, "session", { path: "/" });
  return c.json({ ok: true });
});

export { auth };
