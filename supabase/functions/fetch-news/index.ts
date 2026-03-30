import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type, x-supabase-client-platform, x-supabase-client-platform-version, x-supabase-client-runtime, x-supabase-client-runtime-version",
};

const today = () => new Date().toISOString().split("T")[0];

const SCHEMA = {
  name: "extract_news",
  description: "Extract structured Lebanon crisis news items",
  parameters: {
    type: "object",
    properties: {
      incidents: {
        type: "array",
        items: {
          type: "object",
          properties: {
            title: { type: "string", description: "Short headline" },
            description: { type: "string", description: "2-3 sentence summary" },
            category: {
              type: "string",
              enum: ["violence", "protest", "natural_disaster", "infrastructure", "health", "terrorism", "cyber", "other"],
            },
            severity: { type: "string", enum: ["low", "medium", "high", "critical"] },
            region: {
              type: "string",
              enum: ["Beirut", "North Lebanon", "South Lebanon", "Mount Lebanon", "Bekaa", "Nabatieh", "Akkar", "Baalbek-Hermel"],
            },
            locationName: { type: "string", description: "Specific place name within the region" },
            lat: { type: "number" },
            lng: { type: "number" },
            sourceName: { type: "string", description: "Name of the media source" },
            sourceUrl: { type: "string", description: "Direct URL to the original article/report" },
            sourceType: { type: "string", enum: ["tv", "newspaper", "news_agency", "social_media", "government", "ngo"] },
            credibilityScore: { type: "number", description: "0-100 credibility estimate" },
            sentimentScore: { type: "number", description: "-1 to 1 sentiment" },
            riskScore: { type: "number", description: "0-100 risk score" },
            keywords: { type: "array", items: { type: "string" } },
            publishedAt: { type: "string", description: "ISO date string of when the news was published" },
          },
          required: ["title", "description", "category", "severity", "region", "locationName", "lat", "lng", "sourceName", "sourceUrl", "sourceType", "credibilityScore", "sentimentScore", "riskScore", "keywords", "publishedAt"],
        },
      },
    },
    required: ["incidents"],
  },
};

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response(null, { headers: corsHeaders });
  }

  try {
    const LOVABLE_API_KEY = Deno.env.get("LOVABLE_API_KEY");
    if (!LOVABLE_API_KEY) throw new Error("LOVABLE_API_KEY is not configured");

    const prompt = `Today is ${today()}. Search the web for the LATEST Lebanon news from the past 24-48 hours. 

Search these sources specifically:
- LBCI (lbci.com)
- Al Jadeed / New TV (aljadeed.tv)
- Al Jazeera Arabic (aljazeera.net) - Lebanon coverage
- Al Mayadeen (almayadeen.net) - Lebanon coverage
- MTV Lebanon (mtv.com.lb)
- L'Orient Today (today.lorientlejour.com)
- NNA - National News Agency Lebanon (nna-leb.gov.lb)
- Naharnet (naharnet.com)
- The Daily Star Lebanon (dailystar.com.lb)
- Lebanese Armed Forces official statements
- Lebanese Red Cross updates
- Reuters / AFP Lebanon coverage

Return 10-15 REAL, CURRENT news items from today or the past 48 hours. 
Each must have a REAL working URL to the actual article.
Focus on: security, politics, economy, protests, infrastructure, health, and humanitarian issues in Lebanon.
Provide accurate GPS coordinates for each incident location.
Assess credibility based on the source reputation.
DO NOT invent or fabricate any news. Only return real, verifiable current events.`;

    const response = await fetch("https://ai.gateway.lovable.dev/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${LOVABLE_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "google/gemini-2.5-flash",
        web_search_options: { search_context_size: "high" },
        messages: [{ role: "user", content: prompt }],
        tools: [{ type: "function", function: SCHEMA }],
        tool_choice: { type: "function", function: { name: "extract_news" } },
      }),
    });

    if (!response.ok) {
      const t = await response.text();
      console.error("AI gateway error:", response.status, t);
      return new Response(JSON.stringify({ error: "Failed to fetch news", incidents: [] }), {
        status: 500,
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const data = await response.json();
    
    // Extract from tool call response
    const toolCall = data.choices?.[0]?.message?.tool_calls?.[0];
    let incidents = [];
    
    if (toolCall?.function?.arguments) {
      try {
        const parsed = typeof toolCall.function.arguments === "string"
          ? JSON.parse(toolCall.function.arguments)
          : toolCall.function.arguments;
        incidents = parsed.incidents || [];
      } catch (e) {
        console.error("Parse error:", e);
      }
    }

    // Fallback: try to parse from content if no tool call
    if (incidents.length === 0 && data.choices?.[0]?.message?.content) {
      try {
        const content = data.choices[0].message.content;
        const jsonMatch = content.match(/\{[\s\S]*"incidents"[\s\S]*\}/);
        if (jsonMatch) {
          incidents = JSON.parse(jsonMatch[0]).incidents || [];
        }
      } catch { /* ignore */ }
    }

    return new Response(JSON.stringify({ incidents, fetchedAt: new Date().toISOString() }), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  } catch (e) {
    console.error("fetch-news error:", e);
    return new Response(
      JSON.stringify({ error: e instanceof Error ? e.message : "Unknown error", incidents: [] }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
