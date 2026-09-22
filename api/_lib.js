// Shared by the serverless functions. Files starting with _ are not routes.
const MODEL = process.env.GEMINI_MODEL || "gemini-3.5-flash";
const URL = `https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent`;

export async function gemini(body, fetchImpl = fetch) {
  const key = process.env.GEMINI_API_KEY;
  if (!key) throw new HttpError(500, "Server is missing GEMINI_API_KEY.");
  const r = await fetchImpl(URL, {
    method: "POST",
    headers: { "content-type": "application/json", "x-goog-api-key": key },
    body: JSON.stringify(body),
  });
  if (r.status === 429) throw new HttpError(429, "The free AI quota is used up for now. Try again later.");
  if (!r.ok) throw new HttpError(502, `The AI service returned ${r.status}.`);
  return r.json();
}

export async function loadJobs(req, fetchImpl = fetch) {
  const host = req.headers["x-forwarded-host"] || req.headers.host;
  const proto = req.headers["x-forwarded-proto"] || "https";
  const r = await fetchImpl(`${proto}://${host}/data/jobs.json`);
  if (!r.ok) return [];
  return (await r.json()).jobs || [];
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
