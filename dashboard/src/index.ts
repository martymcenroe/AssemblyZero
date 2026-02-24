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
 */

import { Hono } from "hono";
import { cors } from "hono/cors";
import type { Env } from "./dynamo";
import { DASHBOARD_HTML } from "./frontend";
import {
  queryByRepo,
  queryByActor,
  queryByUser,
  queryByDate,
  queryErrors,
} from "./dynamo";

const app = new Hono<{ Bindings: Env }>();

// CORS for dashboard frontend
app.use("/api/*", cors());

// API key auth middleware
app.use("/api/*", async (c, next) => {
  // Health endpoint is public
  if (c.req.path === "/api/health") return next();

  const key = c.req.header("X-API-Key") ?? c.req.query("key");
  if (!key || key !== c.env.API_KEY) {
    return c.json({ error: "Unauthorized" }, 401);
  }
  return next();
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
  const result = await queryErrors(c.env);
  return c.json(result);
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

// Dashboard frontend — serve HTML at root
app.get("/", (c) => {
  return c.html(DASHBOARD_HTML);
});

export default app;
