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
    const { messages } = await req.json();
    const LOVABLE_API_KEY = Deno.env.get("LOVABLE_API_KEY");
    if (!LOVABLE_API_KEY) throw new Error("LOVABLE_API_KEY is not configured");

    // Fetch real-time news context for grounding
    const latestNews = await fetchLatestNews(LOVABLE_API_KEY);

    const contextMessage = latestNews
      ? `\n\n--- REAL-TIME INTELLIGENCE FEED (fetched ${new Date().toISOString()}) ---\n${latestNews}\n--- END FEED ---\n\nUse the above real-time feed to ground your answers in current events. If the user asks about current situations, reference this data. Always note dates and sources.`
      : `\n\nNote: Real-time news feed is temporarily unavailable. Clearly state that your information may not reflect the very latest events and recommend the user check Lebanese media sources directly.`;

    const response = await fetch("https://ai.gateway.lovable.dev/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${LOVABLE_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "google/gemini-2.5-flash",
        web_search_options: { search_context_size: "high" },
        messages: [
          { role: "system", content: SYSTEM_PROMPT() + contextMessage },
          ...messages,
        ],
        stream: true,
      }),
    });

    if (!response.ok) {
      if (response.status === 429) {
        return new Response(JSON.stringify({ error: "Rate limit exceeded. Please wait a moment and try again." }), {
          status: 429,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        });
      }
      if (response.status === 402) {
        return new Response(JSON.stringify({ error: "AI credits exhausted. Please add funds in Settings → Workspace → Usage." }), {
          status: 402,
          headers: { ...corsHeaders, "Content-Type": "application/json" },
        });
      }
      const t = await response.text();
      console.error("AI gateway error:", response.status, t);
      return new Response(JSON.stringify({ error: "AI service temporarily unavailable." }), {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
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
