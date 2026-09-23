// Shared by the serverless functions. Files starting with _ are not routes.
const MODEL = process.env.GEMINI_MODEL || "gemini-3.5-flash";
const URL = `https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent`;

// An AQ.-prefixed "auth key" (all new AI Studio keys since May 2026) is rejected
// on the x-goog-api-key header by some endpoints but accepted as a bearer token.
// Old AIza keys only work on x-goog-api-key. So: pick by prefix, fall back either way.
function authHeaders(key) {
  return key.startsWith("AQ.")
    ? [{ authorization: `Bearer ${key}` }, { "x-goog-api-key": key }]
    : [{ "x-goog-api-key": key }, { authorization: `Bearer ${key}` }];
}

export async function gemini(body, fetchImpl = fetch) {
  const key = process.env.GEMINI_API_KEY;
  if (!key) throw new HttpError(500, "Server is missing GEMINI_API_KEY.");
  const attempts = authHeaders(key.trim());
  let last = null;
  for (let i = 0; i < attempts.length; i++) {
    const r = await fetchImpl(URL, {
      method: "POST",
      headers: { "content-type": "application/json", ...attempts[i] },
      body: JSON.stringify(body),
    });
    if (r.ok) return r.json();
    const detail = (await r.text().catch(() => "")).slice(0, 400);
    console.error(`Gemini ${r.status} for model ${MODEL} (auth attempt ${i + 1}): ${detail}`);
    last = { status: r.status, detail };
    // Only an auth rejection is worth retrying with the other header.
    const authProblem = (r.status === 400 && /API_KEY_INVALID|API key not valid/i.test(detail))
      || r.status === 401 || r.status === 403;
    if (!authProblem) break;
  }
  const { status, detail } = last;
  if (status === 429) {
    const noFreeTier = /limit: ?0\b/.test(detail);
    throw new HttpError(429, noFreeTier
      ? `The model ${MODEL} has no free quota on this API key. Set GEMINI_MODEL to a free-tier model in Vercel.`
      : "The free AI quota is used up for now. Try again in a minute.");
  }
  if (status === 400 || status === 401 || status === 403) throw new HttpError(502, "The AI service rejected the request. Check GEMINI_API_KEY in Vercel.");
  if (status === 404) throw new HttpError(502, `The model ${MODEL} wasn't found. Check GEMINI_MODEL in Vercel.`);
  throw new HttpError(502, `The AI service returned ${status}.`);
}

// The jobs file ships with the deployment, so read it off disk. Fetching it over
// HTTP breaks under Deployment Protection: the function's call back into its own
// domain gets the auth page (HTML, status 200) instead of JSON.
const JOBS_PATHS = [
  "public/data/jobs.json",
  "data/jobs.json",
  "../public/data/jobs.json",
];

// Rate limiting. Honest caveat: Vercel may run several instances of a function,
// and each keeps its own counters, so the real cap is per-instance and a
// determined abuser could exceed it. It stops ordinary over-use, which is the
// point: one visitor clicking around must not drain the day's Gemini quota.
const PER_IP_PER_DAY = Number(process.env.CHAT_PER_IP_PER_DAY || 20);
const TOTAL_PER_DAY = Number(process.env.CHAT_TOTAL_PER_DAY || 200);
const counts = new Map();           // ip -> n, for the current day
let day = "";
let total = 0;

export function rateLimit(req, today = new Date().toISOString().slice(0, 10)) {
  if (today !== day) { day = today; counts.clear(); total = 0; }
  if (total >= TOTAL_PER_DAY) {
    throw new HttpError(429, "This demo has hit its daily AI budget. Try again tomorrow.");
  }
  const ip = String(req.headers["x-forwarded-for"] || "unknown").split(",")[0].trim();
  const n = (counts.get(ip) || 0) + 1;
  if (n > PER_IP_PER_DAY) {
    throw new HttpError(429, `You've used today's ${PER_IP_PER_DAY} questions on this demo. Try again tomorrow.`);
  }
  counts.set(ip, n);
  total += 1;
}

// Test-only: lets a test start from a clean slate.
export function _resetRateLimit() { day = ""; counts.clear(); total = 0; }

export async function loadJobs(req, fetchImpl = fetch) {
  const { readFile } = await import("node:fs/promises");
  const { join } = await import("node:path");
  for (const rel of JOBS_PATHS) {
    try {
      const raw = await readFile(join(process.cwd(), rel), "utf8");
      return JSON.parse(raw).jobs || [];
    } catch { /* try the next candidate */ }
  }
  // Last resort: the old HTTP path, but only trust an actual JSON response.
  try {
    const host = req.headers["x-forwarded-host"] || req.headers.host;
    const proto = req.headers["x-forwarded-proto"] || "https";
    const r = await fetchImpl(`${proto}://${host}/data/jobs.json`);
    const type = r.headers?.get?.("content-type") || "";
    if (!r.ok || !type.includes("json")) {
      console.error(`jobs.json over HTTP returned ${r.status} ${type || "(no content-type)"}`);
      return [];
    }
    return (await r.json()).jobs || [];
  } catch (e) {
    console.error("could not load jobs.json:", e.message);
    return [];
  }
}
// The one tool the chat agent has. Pure function so it can be tested.
export function searchMatches(jobs, a = {}) {
  const kw = String(a.keywords || "").toLowerCase().split(",").map(s => s.trim()).filter(Boolean);
  const loc = String(a.location || "").toLowerCase().trim();
  const min = Number.isFinite(+a.min_score) ? +a.min_score : 0;
  const max = Math.min(Math.max(+a.max_results || 8, 1), 15);
  return jobs
    .filter(j => j.score >= min)
    .filter(j => !a.still_open_only || j.still_open)
    .filter(j => !loc || j.location.toLowerCase().includes(loc))
    .filter(j => !kw.length || kw.some(k => `${j.title} ${j.company} ${j.snippet}`.toLowerCase().includes(k)))
    .slice(0, max)
    .map(j => ({
      title: j.title, company: j.company, location: j.location, score: j.score,
      salary: j.salary || "not stated", duration: j.duration || "not stated",
      days_live: j.days_live, freshness: j.freshness, still_open: j.still_open,
      open_roles_at_company: j.open_roles_at_company, why_it_fits: j.why_it_fits,
      tailored_bullets: j.tailored_bullets, url: j.url,
    }));
}

export class HttpError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}

export function handle(fn) {
  return async (req, res) => {
    if (req.method !== "POST") return res.status(405).json({ error: "POST only." });
    try {
      res.status(200).json(await fn(req));
    } catch (e) {
      res.status(e.status || 500).json({ error: e.status ? e.message : "Something went wrong on the server." });
      if (!e.status) console.error(e);
    }
  };
}
