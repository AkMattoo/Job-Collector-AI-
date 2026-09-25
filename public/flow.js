// The guided intake flow. Deliberately pure and deliberately AI-free: the
// answers map onto fields the collector already stores, so matching is a
// filter, not a judgement. That makes it instant, free, and still working
// when the Gemini quota is gone.

const FLOW_STEPS = [
  {
    key: "role",
    question: "What kind of role are you after?",
    options: [
      { label: "Data analyst", value: ["data analyst", "analytics", "business analyst"] },
      { label: "Data engineer", value: ["data engineer", "engineer", "developer", "software"] },
      { label: "Data scientist", value: ["data scientist", "scientist", "machine learning"] },
      { label: "Any of them", value: [] },
    ],
  },
  {
    key: "location",
    question: "Where should it be?",
    options: [
      { label: "Bengaluru", value: "bangalore|bengaluru" },
      { label: "Pune", value: "pune" },
      { label: "Mumbai", value: "mumbai" },
      { label: "Hyderabad", value: "hyderabad" },
      { label: "Anywhere", value: "" },
    ],
  },
  {
    key: "freshness",
    question: "How recently posted?",
    options: [
      { label: "This week", value: 7 },
      { label: "Last two weeks", value: 14 },
      { label: "Doesn't matter", value: null },
    ],
  },
  {
    key: "fit",
    question: "How strong a fit?",
    options: [
      { label: "Strong only (8+)", value: 8 },
      { label: "Worth a look (7+)", value: 7 },
    ],
  },
];

function filterByAnswers(jobs, answers) {
  const roleWords = answers.role || [];
  const place = answers.location || "";
  const maxDays = answers.freshness;
  const minFit = answers.fit || 0;
  const placeRe = place ? new RegExp(place, "i") : null;

  return (jobs || []).filter(j => {
    if ((j.score ?? 0) < minFit) return false;
    if (!j.still_open) return false;
    if (placeRe && !placeRe.test(j.location || "")) return false;
    // days_live can be null when a posting carries no date - don't guess, keep it.
    if (maxDays !== null && maxDays !== undefined &&
        j.days_live !== null && j.days_live !== undefined && j.days_live > maxDays) return false;
    if (roleWords.length) {
      const hay = `${j.title || ""} ${j.snippet || ""}`.toLowerCase();
      if (!roleWords.some(w => hay.includes(w))) return false;
    }
    return true;
  }).sort((a, b) => b.score - a.score || (a.days_live ?? 999) - (b.days_live ?? 999));
}

// Says, in one line, which answer is most worth relaxing when nothing matched.
function loosenHint(jobs, answers) {
  const tries = [
    ["fit", "lowering the fit bar"],
    ["freshness", "widening the date range"],
    ["location", "opening it up to anywhere in India"],
    ["role", "including other role types"],
  ];
  for (const [key, phrase] of tries) {
    const relaxed = { ...answers };
    relaxed[key] = key === "role" ? [] : key === "location" ? "" : key === "freshness" ? null : 0;
    if (filterByAnswers(jobs, relaxed).length) return phrase;
  }
  return null;
}

if (typeof module !== "undefined") module.exports = { FLOW_STEPS, filterByAnswers, loosenHint };
