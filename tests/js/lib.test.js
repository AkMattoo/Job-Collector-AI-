import { test } from "node:test";
import assert from "node:assert/strict";
import { searchMatches, gemini } from "../../api/_lib.js";
import { runChat } from "../../api/chat.js";
import { mergeScores } from "../../api/match.js";

const JOBS = [
  { title: "Data Engineer", company: "Acme", location: "Seattle, WA", score: 9, still_open: true, snippet: "bigquery etl", url: "u1" },
  { title: "Analytics Engineer", company: "Ramp", location: "Remote", score: 7, still_open: false, snippet: "dbt", url: "u2" },
];

test("searchMatches filters and caps", () => {
  assert.equal(searchMatches(JOBS, { location: "remote" }).length, 1);
  assert.equal(searchMatches(JOBS, { min_score: 8 })[0].url, "u1");
  assert.equal(searchMatches(JOBS, { still_open_only: true }).length, 1);
  assert.equal(searchMatches(JOBS, { keywords: "dbt, spark" })[0].company, "Ramp");
  assert.equal(searchMatches(JOBS, {})[1].salary, "not stated");
});

test("agent loop: calls the tool, feeds results back, then answers", async () => {
  const seen = [];
  const replies = [
    { candidates: [{ content: { role: "model", parts: [{ functionCall: { name: "search_matches", args: { location: "remote" } } }] } }] },
    { candidates: [{ content: { role: "model", parts: [{ text: "One remote match: Analytics Engineer at Ramp (u2)." }] } }] },
  ];
  const out = await runChat([{ role: "user", text: "any remote?" }], JOBS, async body => { seen.push(body); return replies.shift(); });
  assert.equal(out.steps, 1);
  assert.match(out.reply, /Ramp/);
  const fr = seen[1].contents.at(-1).parts[0].functionResponse;
  assert.equal(fr.response.results.length, 1);
  assert.equal(fr.response.results[0].company, "Ramp");
});

test("agent loop stops after max steps", async () => {
  const loop = { candidates: [{ content: { parts: [{ functionCall: { name: "search_matches", args: {} } }] } }] };
  const out = await runChat([{ role: "user", text: "x" }], JOBS, async () => loop);
  assert.equal(out.steps, 5);
});

test("mergeScores ignores garbage and bad indexes", () => {
  const good = { candidates: [{ content: { parts: [{ text: JSON.stringify([{ index: 1, score: 8, reason: "ok" }, { index: 9, score: 9, reason: "x" }]) }] } }] };
  assert.deepEqual(mergeScores(JOBS, good).map(r => r.url), ["u2"]);
  assert.deepEqual(mergeScores(JOBS, { candidates: [{ content: { parts: [{ text: "nope" }] } }] }), []);
});

test("an AQ. key is sent as a bearer token first", async () => {
  process.env.GEMINI_API_KEY = "AQ.fake";
  const seen = [];
  const fake = async (_url, opts) => {
    seen.push(opts.headers);
    return { ok: true, json: async () => ({ ok: 1 }) };
  };
  await gemini({}, fake);
  assert.equal(seen.length, 1);
  assert.equal(seen[0].authorization, "Bearer AQ.fake");
});

test("an auth rejection is retried with the other header", async () => {
  process.env.GEMINI_API_KEY = "AQ.fake";
  const seen = [];
  const fake = async (_url, opts) => {
    seen.push(opts.headers);
    if (seen.length === 1) {
      return { ok: false, status: 400, text: async () => '{"error":{"status":"API_KEY_INVALID"}}' };
    }
    return { ok: true, json: async () => ({ ok: 1 }) };
  };
  await gemini({}, fake);
  assert.equal(seen.length, 2);
  assert.equal(seen[1]["x-goog-api-key"], "AQ.fake");
});

test("a non-auth error is not retried with the other header", async () => {
  process.env.GEMINI_API_KEY = "AIzaFake";
  let calls = 0;
  const fake = async () => {
    calls++;
    return { ok: false, status: 429, text: async () => "quota" };
  };
  await assert.rejects(() => gemini({}, fake), /quota is used up/);
  assert.equal(calls, 1);
});
