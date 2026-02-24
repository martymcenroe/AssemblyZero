/**
 * AssemblyZero Telemetry API — CloudFlare Worker.
 *
 * Endpoints:
 *   GET /api/health
 *   GET /api/events?repo=X&limit=N
 *   GET /api/events/by-actor?actor=human|claude&limit=N
 *   GET /api/events/by-user?user=X&limit=N
 *   GET /api/summary/daily?date=YYYY-MM-DD
 *   GET /api/summary/weekly
 *   GET /api/errors
 *   GET /api/dashboard/overview
 *   GET /api/repos/:repo/summary
 *
 * Static assets (React SPA) served by Wrangler [assets] config.
 */

import { Hono } from "hono";
import { cors } from "hono/cors";
import { getCookie } from "hono/cookie";
import { verify } from "hono/jwt";
import type { Env } from "./dynamo";
import {
  queryByRepo,
  queryByActor,
  queryByUser,
  queryByDate,
  queryErrors,
} from "./dynamo";
import { auth } from "./auth";

const app = new Hono<{ Bindings: Env }>();

// CORS for dashboard frontend
app.use("/api/*", cors());

// Mount OAuth routes before auth middleware
app.route("/api/auth", auth);

// Dual-auth middleware: JWT cookie OR API key
app.use("/api/*", async (c, next) => {
  // Public endpoints
  if (c.req.path === "/api/health") return next();
  // Auth routes are handled by their own sub-app
  if (c.req.path.startsWith("/api/auth/")) return next();

  // Try JWT cookie first
  const token = getCookie(c, "session");
  if (token) {
    try {
      await verify(token, c.env.JWT_SECRET, "HS256");
      return next();
    } catch {
      // Invalid cookie — fall through to API key check
    }
  }

  // Try API key (header or query param)
  const key = c.req.header("X-API-Key") ?? c.req.query("key");
  if (key && key === c.env.API_KEY) {
    return next();
  }

  return c.json({ error: "Unauthorized" }, 401);
});

// Health check
app.get("/api/health", (c) => {
  return c.json({ status: "ok", service: "assemblyzero-telemetry-api" });
});

// Events by repo
app.get("/api/events", async (c) => {
  const repo = c.req.query("repo") ?? "AssemblyZero";
  const limit = parseInt(c.req.query("limit") ?? "50", 10);
  const result = await queryByRepo(c.env, repo, limit);
  return c.json(result);
});

// Events by actor
app.get("/api/events/by-actor", async (c) => {
  const actor = c.req.query("actor") ?? "claude";
  const limit = parseInt(c.req.query("limit") ?? "50", 10);
  const result = await queryByActor(c.env, actor, limit);
  return c.json(result);
});

// Events by user
app.get("/api/events/by-user", async (c) => {
  const user = c.req.query("user");
  if (!user) return c.json({ error: "user parameter required" }, 400);
  const limit = parseInt(c.req.query("limit") ?? "50", 10);
  const result = await queryByUser(c.env, user, limit);
  return c.json(result);
});

// Daily summary
app.get("/api/summary/daily", async (c) => {
  const date = c.req.query("date") ?? new Date().toISOString().slice(0, 10);
  const result = await queryByDate(c.env, date, 500);

  const summary = {
    date,
    total: result.items.length,
    by_actor: { human: 0, claude: 0 },
    by_type: {} as Record<string, number>,
    errors: 0,
  };

  for (const item of result.items) {
    const actor = (item.actor as string) ?? "unknown";
    if (actor === "human") summary.by_actor.human++;
    else if (actor === "claude") summary.by_actor.claude++;

    const eventType = (item.event_type as string) ?? "unknown";
    summary.by_type[eventType] = (summary.by_type[eventType] ?? 0) + 1;

    if (eventType.startsWith("error.") || eventType.endsWith(".error")) {
      summary.errors++;
    }
  }

  return c.json(summary);
});

// Weekly summary (last 7 days)
app.get("/api/summary/weekly", async (c) => {
  const days: { date: string; total: number; human: number; claude: number; errors: number }[] = [];

  for (let i = 0; i < 7; i++) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    const dateStr = d.toISOString().slice(0, 10);

    const result = await queryByDate(c.env, dateStr, 500);
    let human = 0,
      claude = 0,
      errors = 0;

    for (const item of result.items) {
      if (item.actor === "human") human++;
      else if (item.actor === "claude") claude++;
      const et = item.event_type as string;
      if (et?.startsWith("error.") || et?.endsWith(".error")) errors++;
    }

    days.push({ date: dateStr, total: result.items.length, human, claude, errors });
  }

  return c.json({ days });
});

// Error events
app.get("/api/errors", async (c) => {
  try {
    const result = await queryErrors(c.env);
    return c.json(result);
  } catch (e) {
    const message = e instanceof Error ? e.message : "Unknown error";
    return c.json({ items: [], error: message });
  }
});

// Dashboard overview
app.get("/api/dashboard/overview", async (c) => {
  const today = new Date().toISOString().slice(0, 10);
  const todayResult = await queryByDate(c.env, today, 500);

  let humanToday = 0,
    claudeToday = 0,
    errorsToday = 0;
  const recentErrors: unknown[] = [];

  for (const item of todayResult.items) {
    if (item.actor === "human") humanToday++;
    else if (item.actor === "claude") claudeToday++;
    const et = item.event_type as string;
    if (et?.startsWith("error.") || et?.endsWith(".error")) {
      errorsToday++;
      if (recentErrors.length < 5) recentErrors.push(item);
    }
  }

  return c.json({
    today: {
      date: today,
      total: todayResult.items.length,
      human: humanToday,
      claude: claudeToday,
      errors: errorsToday,
    },
    recent_errors: recentErrors,
  });
});

// Repo detail summary
app.get("/api/repos/:repo/summary", async (c) => {
  const repo = c.req.param("repo");
  const result = await queryByRepo(c.env, repo, 500);

  const byActor = { human: 0, claude: 0 };
  const byEventType: Record<string, number> = {};
  const dailyCounts: Record<string, number> = {};

  for (const item of result.items) {
    if (item.actor === "human") byActor.human++;
    else if (item.actor === "claude") byActor.claude++;

    const et = (item.event_type as string) ?? "unknown";
    byEventType[et] = (byEventType[et] ?? 0) + 1;

    if (item.timestamp) {
      const day = (item.timestamp as string).slice(0, 10);
      dailyCounts[day] = (dailyCounts[day] ?? 0) + 1;
    }
  }

  // Sort daily activity by date
  const dailyActivity = Object.entries(dailyCounts)
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([date, count]) => ({ date, count }));

  return c.json({
    repo,
    total_events: result.items.length,
    by_actor: byActor,
    by_event_type: byEventType,
    daily_activity: dailyActivity,
    recent_events: result.items.slice(0, 20),
  });
});

// SPA fallback — serve index.html for non-API routes
app.get("*", async (c) => {
  const url = new URL("/index.html", c.req.url);
  return c.env.ASSETS.fetch(new Request(url));
});

export default app;
