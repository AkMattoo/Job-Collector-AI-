// Rule-based chatbot: prepared replies, no API, no quota.
// Hands over to a helpline / webpage when it can't help.

// ---- 1. Edit these to match your site ----
const FALLBACK = {
  helpline: "+91 00000 00000",          // your helpline number
  page: "https://example.com/contact",  // your help or contact page
};
const MAX_MISSES = 2;     // unmatched messages in a row before handing over
const MAX_MESSAGES = 12;  // total messages before suggesting a human

const TOPICS = [
  {
    keywords: ["hi", "hello", "hey", "start"],
    reply: "Hi! I can help you find jobs, explain how matches are scored, or show you how to try it with your resume. What would you like to know?",
  },
  {
    keywords: ["how", "work", "score", "scoring", "match", "rating"],
    reply: "Every day, the collector pulls new data roles from company job boards, filters out ones that don't fit, and scores the rest from 1 to 10 against the profile. Only jobs scoring 7 or above are shown.",
  },
  {
    keywords: ["resume", "cv", "upload", "my profile"],
    reply: "Use the 'Try it with your resume' button at the top of the page. Paste your resume and you'll see how the listed jobs match your profile.",
  },
  {
    keywords: ["update", "new jobs", "daily", "when", "refresh"],
    reply: "The list updates once a day, in the evening (India time). New matches appear automatically after each run.",
  },
  {
    keywords: ["location", "city", "remote", "bengaluru", "bangalore", "mumbai", "hyderabad", "pune"],
    reply: "Jobs are collected from across India, including Bengaluru, Hyderabad, Pune, Mumbai and Gurgaon. You can filter by location in the table.",
  },
  {
    keywords: ["apply", "application", "link"],
    reply: "Click any job in the table to open the original posting, then apply directly on the company's site.",
  },
  {
    keywords: ["thanks", "thank you", "bye", "great"],
    reply: "Happy to help! Good luck with your search.",
  },
];

const QUICK_REPLIES = ["How does scoring work?", "Try with my resume", "When are jobs updated?", "Talk to a person"];

// ---- 2. Matching logic ----
let misses = 0;
let messages = 0;

function handoff(reason) {
  return `${reason} For more help, call ${FALLBACK.helpline} or visit ${FALLBACK.page}`;
}

function getReply(input) {
  messages += 1;
  const text = input.toLowerCase().trim();

  if (/(human|person|agent|support|help ?line|contact)/.test(text)) {
    misses = 0;
    return handoff("Sure, here's how to reach us.");
  }

  // Score each topic by how many of its keywords appear in the message.
  let best = null;
  let bestScore = 0;
  for (const topic of TOPICS) {
    const score = topic.keywords.filter((k) => text.includes(k)).length;
    if (score > bestScore) {
      best = topic;
      bestScore = score;
    }
  }

  if (best) {
    misses = 0;
    const answer = best.reply;
    return messages >= MAX_MESSAGES
      ? `${answer}\n\n${handoff("If you still have questions,")}`
      : answer;
  }

  misses += 1;
  if (misses >= MAX_MISSES) {
    misses = 0;
    return handoff("Sorry, I couldn't find an answer to that.");
  }
  return "Sorry, I didn't quite get that. Try asking about scoring, your resume, job updates, or locations, or tap one of the buttons below.";
}

// ---- 3. Hook it up to your existing chat UI ----
// Replace your current fetch("/api/chat") call with:
//   const answer = getReply(userMessage);
//   showBotMessage(answer);
// and render QUICK_REPLIES as buttons that call getReply(buttonText).
