import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type, x-supabase-client-platform, x-supabase-client-platform-version, x-supabase-client-runtime, x-supabase-client-runtime-version",
};

const today = () => new Date().toISOString().split("T")[0];

const SYSTEM_PROMPT = () => `You are CrisisShield AI — a real-time crisis intelligence assistant for Lebanon.
Today's date is ${today()}.

CRITICAL RULES:
- You MUST provide information that is current and up-to-date as of today (${today()}).
- NEVER repeat old news or reference events from your training data as if they are current.
- Do NOT repeat incident/alert items already listed in the provided CONTEXT or already mentioned in the conversation.
- If you are unsure whether information is current, explicitly state that and recommend verification.
- Always mention the date of events you reference.
- Clearly distinguish between confirmed current events and historical context.

Your role:
- Help analysts interpret incident data, risk scores, and alerts
- Provide situational awareness summaries for Lebanese regions (Beirut, North Lebanon, South Lebanon, Mount Lebanon, Bekaa, Nabatieh, Akkar, Baalbek-Hermel)
- Explain risk score components (sentiment, volume, keyword, behavior, geospatial)
- Suggest response protocols and escalation actions
- Analyze credibility of Lebanese media sources (LBCI, MTV, Al Jadeed, NNA, L'Orient Today, etc.)
- Cross-reference incidents and identify corroboration patterns

Guidelines:
- Be concise and actionable — analysts need fast answers
- Use severity language: LOW / GUARDED / ELEVATED / CRITICAL
- Reference specific data points when possible
- Flag unverified or low-credibility information
- Always recommend verification steps for unconfirmed reports
- Format responses with bullet points and headers for scannability
- When discussing current events, always note the date and source`;

// Fetch latest Lebanon news headlines via web search to ground the AI
async function fetchLatestNews(apiKey: string): Promise<string> {
  try {
    const res = await fetch("https://ai.gateway.lovable.dev/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "google/gemini-2.5-flash",
        web_search_options: { search_context_size: "high" },
        messages: [
          {
            role: "user",
            content: `Today is ${today()}. Search the web and provide a concise bullet-point summary of the latest Lebanon news from TODAY and the past 48 hours. Focus on:
- Security incidents, military activity, protests
- Political developments
- Humanitarian situations
- Economic updates
Include the date and source for each item. Only include verified, current news. Do NOT include any old or outdated information.`,
          },
        ],
      }),
    });

    if (!res.ok) {
      console.error("News fetch failed:", res.status);
      return "";
    }

    const data = await res.json();
    return data.choices?.[0]?.message?.content || "";
  } catch (e) {
    console.error("News fetch error:", e);
    return "";
  }
}

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const { messages, context } = await req.json();
    const LOVABLE_API_KEY = Deno.env.get("LOVABLE_API_KEY");

    const OPENAI_API_KEY = Deno.env.get("OPENAI_API_KEY");
    if (!OPENAI_API_KEY) throw new Error("OPENAI_API_KEY is not configured");

    const OPENAI_MODEL = Deno.env.get("OPENAI_MODEL") || "gpt-4o-mini";

    // Build grounding context from the frontend's live incidents/alerts first.
    // Fallback to web-search context only if the frontend didn't provide any context.
    const ctxIncidents = Array.isArray(context?.incidents) ? context.incidents : [];
    const ctxAlerts = Array.isArray(context?.alerts) ? context.alerts : [];
    const ctxStats = context?.stats;
    const ctxLastUpdated = typeof context?.lastUpdated === "string" ? context.lastUpdated : undefined;

    let contextMessage = "";

    if (ctxIncidents.length > 0 || ctxAlerts.length > 0) {
      const topIncidents = ctxIncidents
        .slice()
        .sort((a: any, b: any) => (b?.riskScore ?? 0) - (a?.riskScore ?? 0))
        .slice(0, 10);

      const incidentLines = topIncidents
        .map((i: any) => {
          const sev = String(i?.severity ?? "unknown").toUpperCase();
          const title = String(i?.title ?? "Untitled incident");
          const region = String(i?.region ?? "Unknown region");
          const risk = typeof i?.riskScore === "number" ? `${i.riskScore}/100` : "n/a";
          const srcName = String(i?.sourceInfo?.name ?? "Unknown source");
          const credScore = typeof i?.sourceInfo?.credibilityScore === "number" ? `${i.sourceInfo.credibilityScore}/100` : "n/a";
          const url = typeof i?.sourceUrl === "string" && i.sourceUrl ? ` (${i.sourceUrl})` : "";
          return `- [${sev}] ${title} — ${region} (risk: ${risk}). Source: ${srcName} (${credScore})${url}`;
        })
        .join("\n");

      const topAlerts = ctxAlerts
        .slice()
        .sort((a: any, b: any) => new Date(b?.createdAt ?? 0).getTime() - new Date(a?.createdAt ?? 0).getTime())
        .slice(0, 10);

      const alertLines = topAlerts
        .map((a: any) => {
          const sev = String(a?.severity ?? "unknown").toUpperCase();
          const title = String(a?.title ?? "Untitled alert");
          const region = String(a?.region ?? "Unknown region");
          const linkedCount = Array.isArray(a?.linkedIncidents) ? a.linkedIncidents.length : 0;
          const rec = typeof a?.recommendation === "string" && a.recommendation ? a.recommendation.split("\n").slice(0, 3).join(" ").trim() : "";
          return `- [${sev}] ${title} — ${region}. Linked incidents: ${linkedCount}${rec ? `. Recommendation: ${rec}` : ""}`;
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
        `\nUse ONLY the provided CONTEXT for the latest incidents/alerts. Do not invent new incidents or alerts not present in the context. If the user asks for something outside this context, respond that you don't have current data for it and recommend verification.`;
    } else {
      // Fetch real-time news context for grounding (web-search) as a fallback.
      if (!LOVABLE_API_KEY) {
        contextMessage = `\n\nNote: No live incidents/alerts context was provided by the frontend, and the fallback web-search API is not configured. Answer without inventing current events, and recommend verification with Lebanese media sources.`;
      } else {
        const latestNews = await fetchLatestNews(LOVABLE_API_KEY);
        contextMessage = latestNews
          ? `\n\n--- REAL-TIME INTELLIGENCE FEED (fetched ${new Date().toISOString()}) ---\n${latestNews}\n--- END FEED ---\n\nUse the above real-time feed to ground your answers in current events. If the user asks about current situations, reference this data. Always note dates and sources.`
          : `\n\nNote: Real-time news feed is temporarily unavailable. Clearly state that your information may not reflect the very latest events and recommend the user check Lebanese media sources directly.`;
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
        messages: [{ role: "system", content: SYSTEM_PROMPT() + contextMessage }, ...messages],
        stream: true,
      }),
    });

    if (!response.ok) {
      const t = await response.text();
      console.error("OpenAI error:", response.status, t);
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
  } catch (e) {
    console.error("chat error:", e);
    return new Response(JSON.stringify({ error: e instanceof Error ? e.message : "Unknown error" }), {
      status: 500,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});
