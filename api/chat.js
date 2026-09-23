// A small agent: Gemini + one tool (search_matches) + a loop.
import { gemini, loadJobs, searchMatches, handle, HttpError } from "./_lib.js";

const MAX_STEPS = 5;
const SYSTEM = `You are the assistant on a personal job-search dashboard. You answer questions about the data roles
this dashboard has found and scored against its owner's resume.

You have one tool, search_matches, over the saved matches. Use it for any question about jobs; never answer from memory.

Rules:
1. NEVER invent a job, company, salary, or link. Everything you state must come from a tool result.
2. If salary is "not stated", say the posting does not state pay. Never estimate a market rate.
3. You cannot know a company's hiring intent or culture. If asked, say so plainly, then offer what the data has:
   days_live and freshness (long-open posts are often ghost jobs), still_open, and open_roles_at_company.
4. Short answers. Lead with the answer. Compact list, and include the URL for every job you mention.
5. If nothing matches, say so and suggest one specific thing to loosen.
6. If asked how this works: a daily Python pipeline on GitHub Actions pulls Greenhouse, Lever and Ashby boards,
   filters them with cheap rules, scores the survivors with Gemini in batches, and publishes the results as JSON;
   you are a serverless function using tool calls over that JSON.`;

const TOOLS = [{
  functionDeclarations: [{
    name: "search_matches",
    description: "Search the saved, scored job matches. All arguments optional.",
    parameters: {
      type: "OBJECT",
      properties: {
        keywords: { type: "STRING", description: "comma-separated words matched against title, company and description" },
        location: { type: "STRING", description: "substring, e.g. 'remote' or 'seattle'" },
        min_score: { type: "NUMBER", description: "minimum fit score 0-10" },
        still_open_only: { type: "BOOLEAN", description: "only postings still live on the company board" },
        max_results: { type: "NUMBER", description: "1-15, default 8" },
      },
    },
  }],
}];

export async function runChat(messages, jobs, callModel) {
  const contents = messages.map(m => ({ role: m.role === "assistant" ? "model" : "user", parts: [{ text: m.text }] }));
  for (let step = 0; step < MAX_STEPS; step++) {
    const data = await callModel({
      systemInstruction: { parts: [{ text: SYSTEM }] },
      contents, tools: TOOLS,
      generationConfig: { temperature: 0.3 },
    });
    const content = data?.candidates?.[0]?.content;
    if (!content?.parts) throw new HttpError(502, "The AI returned an empty reply.");
    const calls = content.parts.filter(p => p.functionCall);
    if (!calls.length) {
      return { reply: content.parts.map(p => p.text || "").join("").trim(), steps: step };
    }
    contents.push(content); // keep the model's turn verbatim (includes any thought signatures)
    contents.push({
      role: "user",
      parts: calls.map(c => ({
        functionResponse: { name: c.functionCall.name, response: { results: searchMatches(jobs, c.functionCall.args) } },
      })),
    });
  }
  return { reply: "I needed too many steps for that one. Try asking more specifically.", steps: MAX_STEPS };
}

export default handle(async req => {
  const msgs = Array.isArray(req.body?.messages) ? req.body.messages.slice(-12) : [];
  if (!msgs.length || msgs.at(-1).role !== "user") throw new HttpError(400, "Send at least one user message.");
  for (const m of msgs) {
    if (typeof m.text !== "string" || m.text.length > 800) throw new HttpError(400, "Messages must be text under 800 characters.");
  }
  const jobs = await loadJobs(req);
  if (!jobs.length) {
    return { reply: "There are no saved matches yet. The daily collector hasn't published any, so there's nothing for me to search. Check back after the next run.", steps: 0 };
  }
  return runChat(msgs, jobs, body => gemini(body));
});
