import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type, x-supabase-client-platform, x-supabase-client-platform-version, x-supabase-client-runtime, x-supabase-client-runtime-version",
};

const today = () => new Date().toISOString().split("T")[0];

const SYSTEM_PROMPT = () => `You are CrisisShield AI, a real-time crisis intelligence assistant for Lebanon.
Today's date is ${today()}.

CRITICAL RULES:
- You MUST provide information that is current and up-to-date as of today (${today()}).
- NEVER repeat old news or reference events from your training data as if they are current.
- For time-sensitive factual questions such as officeholders, leaders, ministers, latest events, prices, schedules, or "who is X now", you MUST answer only from grounded context provided below.
- If grounded context for a time-sensitive question is missing or inconclusive, say that you cannot verify the current answer as of ${today()} and recommend checking an official or primary source.
- Do NOT repeat incident or alert items already listed in the provided context or already mentioned in the conversation.
- If you are unsure whether information is current, explicitly state that and recommend verification.
- Always mention the date of events you reference.
- Clearly distinguish between confirmed current events and historical context.

Your role:
- Help analysts interpret incident data, risk scores, and alerts.
- Provide situational awareness summaries for Lebanese regions.
- Explain risk score components.
- Suggest response protocols and escalation actions.
- Analyze credibility of Lebanese media sources.
- Cross-reference incidents and identify corroboration patterns.

Guidelines:
- Be concise and actionable.
- Use severity language: LOW / GUARDED / ELEVATED / CRITICAL.
- Reference specific data points when possible.
- Flag unverified or low-credibility information.
- Always recommend verification steps for unconfirmed reports.
- Format responses with bullet points and headers for scannability.
- When discussing current events, always note the date and source.
- Treat grounded context as higher priority than model memory.`;

function latestUserMessage(messages: Array<{ role?: string; content?: string }>): string {
  for (let i = messages.length - 1; i >= 0; i--) {
    const message = messages[i];
    if (message?.role === "user" && typeof message.content === "string" && message.content.trim()) {
      return message.content.trim();
    }
  }
  return "";
}

function isCurrentFactQuestion(input: string): boolean {
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

async function fetchWebGrounding(
  apiKey: string,
  userQuestion: string,
  mode: "latest_news" | "current_fact",
): Promise<string> {
  try {
    const prompt =
      mode === "current_fact"
        ? `Today is ${today()}. Search the web and answer this user question using only current, verifiable sources: "${userQuestion}".

Prioritize official Lebanese government sources, official institutions, Reuters, AP, and the National News Agency when relevant.
Rules:
- Give the direct answer first.
- Include the exact date of the source or event you rely on.
- Mention the source for each key claim.
- If the answer cannot be verified from current sources, say that clearly.
- Do not use outdated background knowledge as if it were current.`
        : `Today is ${today()}. Search the web and provide a concise bullet-point summary of the latest Lebanon news from TODAY and the past 48 hours. Focus on:
- Security incidents, military activity, protests
- Political developments
- Humanitarian situations
- Economic updates
Include the date and source for each item. Only include verified, current news. Do NOT include any old or outdated information.`;

    const response = await fetch("https://ai.gateway.lovable.dev/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "google/gemini-2.5-flash",
        web_search_options: { search_context_size: "high" },
        messages: [{ role: "user", content: prompt }],
      }),
    });

    if (!response.ok) {
      console.error("Web grounding fetch failed:", response.status);
      return "";
    }

    const data = await response.json();
    return data.choices?.[0]?.message?.content || "";
  } catch (error) {
    console.error("Web grounding error:", error);
    return "";
  }
}

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const { messages, context } = await req.json();
    const safeMessages = Array.isArray(messages) ? messages : [];
    const LOVABLE_API_KEY = Deno.env.get("LOVABLE_API_KEY");

    const OPENAI_API_KEY = Deno.env.get("OPENAI_API_KEY");
    if (!OPENAI_API_KEY) throw new Error("OPENAI_API_KEY is not configured");

    const OPENAI_MODEL = Deno.env.get("OPENAI_MODEL") || "gpt-4o-mini";

    const ctxIncidents = Array.isArray(context?.incidents) ? context.incidents : [];
    const ctxAlerts = Array.isArray(context?.alerts) ? context.alerts : [];
    const ctxStats = context?.stats;
    const ctxLastUpdated = typeof context?.lastUpdated === "string" ? context.lastUpdated : undefined;
    const currentUserQuestion = latestUserMessage(safeMessages);
    const needsCurrentFactGrounding = isCurrentFactQuestion(currentUserQuestion);

    let contextMessage = "";
    let webGroundingMessage = "";

    if (ctxIncidents.length > 0 || ctxAlerts.length > 0) {
      const topIncidents = ctxIncidents
        .slice()
        .sort((a: any, b: any) => (b?.riskScore ?? 0) - (a?.riskScore ?? 0))
        .slice(0, 10);

      const incidentLines = topIncidents
        .map((incident: any) => {
          const severity = String(incident?.severity ?? "unknown").toUpperCase();
          const title = String(incident?.title ?? "Untitled incident");
          const region = String(incident?.region ?? "Unknown region");
          const risk = typeof incident?.riskScore === "number" ? `${incident.riskScore}/100` : "n/a";
          const sourceName = String(incident?.sourceInfo?.name ?? "Unknown source");
          const credibilityScore =
            typeof incident?.sourceInfo?.credibilityScore === "number"
              ? `${incident.sourceInfo.credibilityScore}/100`
              : "n/a";
          const url =
            typeof incident?.sourceUrl === "string" && incident.sourceUrl ? ` (${incident.sourceUrl})` : "";

          return `- [${severity}] ${title} - ${region} (risk: ${risk}). Source: ${sourceName} (${credibilityScore})${url}`;
        })
        .join("\n");

      const topAlerts = ctxAlerts
        .slice()
        .sort((a: any, b: any) => new Date(b?.createdAt ?? 0).getTime() - new Date(a?.createdAt ?? 0).getTime())
        .slice(0, 10);

      const alertLines = topAlerts
        .map((alert: any) => {
          const severity = String(alert?.severity ?? "unknown").toUpperCase();
          const title = String(alert?.title ?? "Untitled alert");
          const region = String(alert?.region ?? "Unknown region");
          const linkedCount = Array.isArray(alert?.linkedIncidents) ? alert.linkedIncidents.length : 0;
          const recommendation =
            typeof alert?.recommendation === "string" && alert.recommendation
              ? alert.recommendation.split("\n").slice(0, 3).join(" ").trim()
              : "";

          return `- [${severity}] ${title} - ${region}. Linked incidents: ${linkedCount}${recommendation ? `. Recommendation: ${recommendation}` : ""}`;
        })
        .join("\n");

      const statsLines = ctxStats
        ? `- Risk overview: avgRiskScore ${ctxStats.avgRiskScore ?? "n/a"}/100, activeAlerts ${ctxStats.activeAlerts ?? "n/a"}, highestRiskRegion ${ctxStats.highestRiskRegion ?? "n/a"}. TotalIncidents24h: ${ctxStats.totalIncidents24h ?? "n/a"}.`
        : "";

      contextMessage =
        `\n\n--- ACTIVE CONTEXT (from frontend; lastUpdated: ${ctxLastUpdated ?? "unknown"}) ---\n` +
        `${statsLines ? statsLines + "\n" : ""}` +
        `${incidentLines ? `\nINCIDENTS:\n${incidentLines}` : ""}` +
        `${alertLines ? `\nALERTS:\n${alertLines}` : ""}\n` +
        `\nUse this ACTIVE CONTEXT for incident and alert questions. Do not invent new incidents or alerts not present in the context.`;
    } else if (!LOVABLE_API_KEY) {
      contextMessage =
        `\n\nNote: No live incidents or alerts context was provided by the frontend, and the fallback web-search API is not configured. ` +
        `Answer without inventing current events, and recommend verification with Lebanese media sources.`;
    } else {
      const latestNews = await fetchWebGrounding(LOVABLE_API_KEY, currentUserQuestion, "latest_news");
      contextMessage = latestNews
        ? `\n\n--- REAL-TIME INTELLIGENCE FEED (fetched ${new Date().toISOString()}) ---\n${latestNews}\n--- END FEED ---\n\nUse the above real-time feed to ground your answers in current events. Always note dates and sources.`
        : `\n\nNote: Real-time news feed is temporarily unavailable. Clearly state that your information may not reflect the very latest events and recommend the user check Lebanese media sources directly.`;
    }

    if (needsCurrentFactGrounding) {
      if (!LOVABLE_API_KEY) {
        webGroundingMessage =
          `\n\n--- CURRENT-FACT GROUNDING ---\n` +
          `No live web grounding is available for this time-sensitive question. Do not answer from memory. State that you cannot verify the current answer as of ${today()}.\n` +
          `--- END CURRENT-FACT GROUNDING ---`;
      } else {
        const factGrounding = await fetchWebGrounding(LOVABLE_API_KEY, currentUserQuestion, "current_fact");
        webGroundingMessage = factGrounding
          ? `\n\n--- CURRENT-FACT GROUNDING (fetched ${new Date().toISOString()}) ---\n${factGrounding}\n--- END CURRENT-FACT GROUNDING ---\n\nFor this time-sensitive question, prioritize CURRENT-FACT GROUNDING over model memory and historical context.`
          : `\n\n--- CURRENT-FACT GROUNDING ---\n` +
            `Live web grounding for this time-sensitive question is unavailable. Do not guess. Say that you cannot verify the current answer as of ${today()}.\n` +
            `--- END CURRENT-FACT GROUNDING ---`;
      }
    }

    const response = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${OPENAI_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: OPENAI_MODEL,
        messages: [{ role: "system", content: SYSTEM_PROMPT() + contextMessage + webGroundingMessage }, ...safeMessages],
        stream: true,
      }),
    });

    if (!response.ok) {
      const text = await response.text();
      console.error("OpenAI error:", response.status, text);
      const status = response.status === 429 ? 429 : 500;

      return new Response(
        JSON.stringify({
          error: status === 429 ? "Rate limit exceeded. Please wait a moment and try again." : "ChatGPT service temporarily unavailable.",
        }),
        { status, headers: { ...corsHeaders, "Content-Type": "application/json" } },
      );
    }

    return new Response(response.body, {
      headers: { ...corsHeaders, "Content-Type": "text/event-stream" },
    });
  } catch (error) {
    console.error("chat error:", error);
    return new Response(JSON.stringify({ error: error instanceof Error ? error.message : "Unknown error" }), {
      status: 500,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});
