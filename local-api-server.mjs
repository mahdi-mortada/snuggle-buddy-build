import { createServer } from "node:http";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import dotenv from "dotenv";

dotenv.config();

const __dirname = dirname(fileURLToPath(import.meta.url));

function loadEnvFile(filePath) {
  if (!existsSync(filePath)) return {};

  const entries = {};
  const raw = readFileSync(filePath, "utf8");

  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;

    const equalsIndex = trimmed.indexOf("=");
    if (equalsIndex === -1) continue;

    const key = trimmed.slice(0, equalsIndex).trim();
    let value = trimmed.slice(equalsIndex + 1).trim();

    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }

    entries[key] = value;
  }

  return entries;
}

const env = {
  ...loadEnvFile(join(__dirname, ".env")),
  ...loadEnvFile(join(__dirname, ".env.local")),
  ...process.env,
};

const PORT = Number(env.LOCAL_API_PORT || 8787);
const OPENAI_API_KEY = (process.env.OPENAI_API_KEY || "").trim();
const OPENAI_MODEL = (env.OPENAI_MODEL || "gpt-4o-mini").trim();
const OPENAI_SEARCH_MODEL = (env.OPENAI_SEARCH_MODEL || "gpt-4o-mini-search-preview").trim();

console.log("API KEY LOADED:", !!process.env.OPENAI_API_KEY);

function sendJson(res, statusCode, payload) {
  res.writeHead(statusCode, {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "authorization, content-type",
  });
  res.end(JSON.stringify(payload));
}

function latestUserMessage(messages) {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const message = messages[i];
    if (message?.role === "user" && typeof message.content === "string" && message.content.trim()) {
      return message.content.trim();
    }
  }
  return "";
}

function isCurrentFactQuestion(input) {
  const text = input.toLowerCase();
  const patterns = [
    /\bwho is\b/,
    /\bcurrent\b/,
    /\btoday\b/,
    /\blatest\b/,
    /\bas of\b/,
    /\bnow\b/,
    /\bprime minister\b/,
    /\bpresident\b/,
    /\bminister\b/,
    /\bceo\b/,
    /\bgovernor\b/,
    /\bmayor\b/,
    /\bleader\b/,
  ];

  return patterns.some((pattern) => pattern.test(text));
}

function formatContext(context) {
  const incidents = Array.isArray(context?.incidents) ? context.incidents : [];
  const alerts = Array.isArray(context?.alerts) ? context.alerts : [];
  const stats = context?.stats;
  const lastUpdated = typeof context?.lastUpdated === "string" ? context.lastUpdated : "unknown";

  const incidentLines = incidents
    .slice(0, 10)
    .map((incident) => {
      const source = incident?.sourceInfo?.name || incident?.source || "Unknown source";
      const risk = typeof incident?.riskScore === "number" ? incident.riskScore : "n/a";
      return `- ${incident?.title || "Untitled incident"} (${incident?.region || "Unknown region"}, risk ${risk}, source ${source})`;
    })
    .join("\n");

  const alertLines = alerts
    .slice(0, 10)
    .map((alert) => `- ${alert?.title || "Untitled alert"} (${alert?.region || "Unknown region"})`)
    .join("\n");

  const statsLine = stats
    ? `Stats: avgRiskScore ${stats.avgRiskScore ?? "n/a"}, activeAlerts ${stats.activeAlerts ?? "n/a"}, highestRiskRegion ${stats.highestRiskRegion ?? "n/a"}, totalIncidents24h ${stats.totalIncidents24h ?? "n/a"}.`
    : "";

  return [
    `Dashboard context last updated: ${lastUpdated}.`,
    statsLine,
    incidentLines ? `Incidents:\n${incidentLines}` : "",
    alertLines ? `Alerts:\n${alertLines}` : "",
  ]
    .filter(Boolean)
    .join("\n\n");
}

function buildSystemPrompt({ useSearch, contextText }) {
  const currentDate = new Date().toISOString().split("T")[0];

  return `You are CrisisShield AI, a crisis intelligence assistant for Lebanon.
Today's date is ${currentDate}.

Rules:
- Use the provided dashboard context for incident and alert questions.
- Never present stale information as current.
- ${useSearch ? "You are using a web-search model for this question. Base time-sensitive claims on current web results." : "If a question requires current facts beyond the dashboard context, say that the local assistant needs live search and avoid guessing."}
- Always mention dates when answering current-event or officeholder questions.
- Keep answers concise, practical, and easy to scan.

${contextText ? `Dashboard context:\n${contextText}` : ""}`;
}

async function readJsonBody(req) {
  const chunks = [];
  for await (const chunk of req) {
    chunks.push(chunk);
  }

  const raw = Buffer.concat(chunks).toString("utf8");
  return raw ? JSON.parse(raw) : {};
}

async function handleChat(req, res) {
  if (!OPENAI_API_KEY) {
    sendJson(res, 500, {
      error: "OPENAI_API_KEY is missing from .env or .env.local.",
    });
    return;
  }

  const body = await readJsonBody(req);
  const messages = Array.isArray(body?.messages) ? body.messages : [];
  const context = body?.context || {};
  const userQuestion = latestUserMessage(messages);
  const useSearch = isCurrentFactQuestion(userQuestion);
  const model = useSearch ? OPENAI_SEARCH_MODEL : OPENAI_MODEL;
  const contextText = formatContext(context);

  const payload = {
    model,
    messages: [{ role: "system", content: buildSystemPrompt({ useSearch, contextText }) }, ...messages],
    temperature: useSearch ? 0.2 : 0.4,
  };

  if (useSearch) {
    payload.web_search_options = { search_context_size: "high" };
  }

  const response = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${OPENAI_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorText = await response.text();
    sendJson(res, response.status, {
      error: "OpenAI chat request failed.",
      details: errorText,
      model,
    });
    return;
  }

  const data = await response.json();
  const answer = data?.choices?.[0]?.message?.content;

  sendJson(res, 200, {
    answer: typeof answer === "string" ? answer : "No answer was returned.",
    model,
    mode: useSearch ? "web-search" : "context",
  });
}

const server = createServer(async (req, res) => {
  if (!req.url) {
    sendJson(res, 400, { error: "Missing request URL." });
    return;
  }

  if (req.method === "OPTIONS") {
    res.writeHead(204, {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Headers": "authorization, content-type",
      "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    });
    res.end();
    return;
  }

  if (req.method === "GET" && req.url === "/api/health") {
    sendJson(res, 200, { ok: true });
    return;
  }

  if (req.method === "POST" && req.url === "/api/crisis-chat") {
    try {
      await handleChat(req, res);
    } catch (error) {
      sendJson(res, 500, {
        error: "Local chat server failed.",
        details: error instanceof Error ? error.message : String(error),
      });
    }
    return;
  }

  sendJson(res, 404, { error: "Not found." });
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`Local API server running at http://127.0.0.1:${PORT}`);
});
