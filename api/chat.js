// Rule-based chat: prepared replies + job search over the saved matches.
// No Gemini, no API key, no quota. Hands over to a helpline/webpage when stuck.
import { loadJobs, searchMatches, handle, HttpError, rateLimit } from "./_lib.js";

// ---- Edit these ----
const FALLBACK = {
  helpline: "+91 00000 00000",
  page: "https://example.com/contact",
};
const MAX_MISSES = 2; // unmatched messages in a row before handing over

const CITIES = ["bengaluru", "bangalore", "hyderabad", "pune", "mumbai", "gurgaon", "gurugram", "delhi", "chennai", "noida", "remote", "india"];
const ROLES = ["data analyst", "data engineer", "data scientist", "analytics engineer", "business analyst", "quantitative analyst", "quant", "software", "sde", "developer", "engineer", "analyst"];

const FAQS = [
  { keywords: ["how does", "how it works", "how do you", "scoring", "scored", "score work"],
    reply: "Every day, a pipeline pulls new roles from company job boards, filters out ones that don't fit, and scores the rest from 0 to 10 against the owner's resume. Only matches scoring 7 or above are published here." },
  { keywords: ["resume", "cv", "my profile"],
    reply: "Use the 'Try it with your resume' button on the page to see how these jobs match your own resume." },
  { keywords: ["update", "updated", "daily", "refresh", "new jobs today"],
    reply: "The list updates once a day, in the evening India time. New matches appear automatically after each run." },
  { keywords: ["salary", "pay", "ctc", "stipend"],
    reply: "I only show pay when the posting states it. If a job says 'not stated', the company didn't list pay, and I won't guess." },
  { keywords: ["culture", "good company", "worth it", "hiring intent", "ghost"],
    reply: "I can't judge a company's culture or hiring intent. What I can show is how long a post has been live, whether it's still open, and how many roles the company has open. Long-open posts are sometimes ghost jobs." },
  { keywords: ["hi", "hello", "hey"],
    reply: "Hi! Ask me for jobs, like 'data analyst jobs in Bengaluru' or 'remote data engineer roles', or ask how the scoring works." },
  { keywords: ["thanks", "thank you", "bye"],
    reply: "Happy to help. Good luck with your search!" },
];

const handoff = reason => `${reason} For more help, call ${FALLBACK.helpline} or visit ${FALLBACK.page}`;
const NOT_UNDERSTOOD = "Sorry, I didn't quite get that.";

function formatJobs(results) {
  return results.map((j, i) => {
    const where = j.location ? ` (${j.location})` : "";
    const score = j.score != null ? ` · score ${j.score}` : "";
    const link = j.url || j.link || "";
    return `${i + 1}. ${j.title || "Untitled role"} at ${j.company || "Unknown company"}${where}${score}\n   ${link}`;
  }).join("\n");
}

export function getReply(messages, jobs) {
  const text = messages.at(-1).text.toLowerCase();

  // Count consecutive misses from earlier bot replies (the server keeps no memory).
  let misses = 0;
  for (let i = messages.length - 2; i >= 0; i--) {
    if (messages[i].role !== "assistant") continue;
    if (messages[i].text.startsWith(NOT_UNDERSTOOD)) misses++;
    else break;
  }

  if (/(human|person|agent|support|help ?line|contact)/.test(text)) {
    return handoff("Sure, here's how to reach us.");
  }

  // 1. Job search: look for a role or city in the message.
  const city = CITIES.find(c => text.includes(c));
  const role = ROLES.find(r => text.includes(r));
  if (role || city || /\b(jobs?|roles?|openings?|internships?)\b/.test(text)) {
    const results = searchMatches(jobs, {
      keywords: role || undefined,
      location: city && city !== "india" ? (city === "bangalore" ? "bengaluru" : city) : undefined,
      still_open_only: /open|active|live/.test(text) || undefined,
      max_results: 8,
    });
    if (results?.length) {
      return `Here are the top matches${role ? ` for "${role}"` : ""}${city ? ` in ${city}` : ""}:\n\n${formatJobs(results)}`;
    }
    return `I couldn't find saved matches${role ? ` for "${role}"` : ""}${city ? ` in ${city}` : ""}. Try a broader role (like "analyst") or drop the location.`;
  }

  // 2. Prepared answers.
  const faq = FAQS.find(f => f.keywords.some(k => text.includes(k)));
  if (faq) return faq.reply;

  // 3. Didn't understand: retry once, then hand over.
  if (misses + 1 >= MAX_MISSES) return handoff("Sorry, I couldn't find an answer to that.");
  return `${NOT_UNDERSTOOD} Try something like "data engineer jobs in Pune", or ask how the scoring works.`;
}

export default handle(async req => {
  rateLimit(req);
  const msgs = Array.isArray(req.body?.messages) ? req.body.messages.slice(-12) : [];
  if (!msgs.length || msgs.at(-1).role !== "user") throw new HttpError(400, "Send at least one user message.");
  for (const m of msgs) {
    if (typeof m.text !== "string") m.text = "";
    if (m.role === "user" && m.text.length > 800) {
      throw new HttpError(400, "Messages must be text under 800 characters.");
    }
    if (m.role !== "user") m.text = m.text.slice(0, 800); // old bot replies can be long
  }
  const jobs = await loadJobs(req);
  if (!jobs.length) {
    return { reply: "There are no saved matches yet. Check back after the next daily run.", steps: 0 };
  }
  return { reply: getReply(msgs, jobs), steps: 0 };
});
