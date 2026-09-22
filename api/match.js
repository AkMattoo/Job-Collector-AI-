// Rescore the current top matches against an uploaded resume. One AI call, capped.
import { gemini, loadJobs, handle, HttpError } from "./_lib.js";

const TOP = 20;

export function buildMatchPrompt(resume, jobs) {
  const list = jobs.map((j, i) =>
    `### JOB ${i}\nTitle: ${j.title}\nCompany: ${j.company}\nLocation: ${j.location}\nSummary: ${j.snippet}`).join("\n\n");
  return `Score how well each job fits the candidate below, 0-10. Be strict: below 6 means not worth applying.
Penalise roles that need experience the resume does not show. You only have a short summary of each job.

RESUME:
${resume}

For each job return index, score, and reason (one sentence, max 15 words).

${list}`;
}

export function mergeScores(jobs, data) {
  let items = [];
  try { items = JSON.parse(data.candidates[0].content.parts[0].text); } catch { items = []; }
  const byIdx = new Map((Array.isArray(items) ? items : [])
    .filter(x => Number.isInteger(x.index) && x.index >= 0 && x.index < jobs.length && Number.isInteger(x.score))
    .map(x => [x.index, x]));
  return jobs
    .map((j, i) => byIdx.has(i) ? { title: j.title, company: j.company, location: j.location, url: j.url,
      salary: j.salary, score: byIdx.get(i).score, reason: byIdx.get(i).reason } : null)
    .filter(Boolean)
    .sort((a, b) => b.score - a.score);
}

export default handle(async req => {
  const resume = String(req.body?.resume || "").trim();
  if (resume.length < 200) throw new HttpError(400, "Couldn't read enough text from that resume. If it's a scanned PDF, export a text-based one.");
  const jobs = (await loadJobs(req)).filter(j => j.still_open).slice(0, TOP);
  if (!jobs.length) throw new HttpError(409, "There are no open matches to score against yet.");
  const data = await gemini({
    contents: [{ parts: [{ text: buildMatchPrompt(resume.slice(0, 12000), jobs) }] }],
    generationConfig: {
      temperature: 0.2, responseMimeType: "application/json",
      responseSchema: { type: "ARRAY", items: { type: "OBJECT",
        properties: { index: { type: "INTEGER" }, score: { type: "INTEGER" }, reason: { type: "STRING" } },
        required: ["index", "score", "reason"] } },
    },
  });
  return { results: mergeScores(jobs, data), scored_against: jobs.length };
});
