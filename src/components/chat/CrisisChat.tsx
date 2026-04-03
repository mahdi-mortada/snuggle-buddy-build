import { useState, useRef, useEffect, useCallback } from 'react';
import { MessageSquare, X, Send, Bot, User, Loader2, Trash2 } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { toast } from 'sonner';
import { runtimeConfig } from '@/lib/runtimeConfig';
import type { Alert, DashboardStats, Incident } from '@/types/crisis';

type Message = { role: 'user' | 'assistant'; content: string };

const CHAT_URL = runtimeConfig.chatUrl;

const QUICK_PROMPTS = [
  "Summarize current situation in Beirut",
  "Which incidents are critical right now?",
  "Assess credibility of latest reports",
  "What regions need immediate attention?",
];

function buildLocalAssistantResponse({
  prompt,
  incidents = [],
  alerts = [],
  stats,
  lastUpdated,
}: {
  prompt: string;
  incidents?: Incident[];
  alerts?: Alert[];
  stats?: DashboardStats;
  lastUpdated?: Date;
}) {
  const lowerPrompt = prompt.toLowerCase();
  const criticalIncidents = incidents.filter((incident) => incident.severity === 'critical').slice(0, 3);
  const topIncidents = incidents.slice(0, 3);
  const topAlerts = alerts.slice(0, 3);
  const lastUpdatedText = lastUpdated ? lastUpdated.toLocaleString() : 'just now';

  const summaryLines = [
    'Local demo mode is active, so this answer is based on the incidents already loaded in the UI rather than the live AI backend.',
    `Total incidents shown: ${incidents.length}.`,
    stats ? `Average risk score: ${stats.avgRiskScore}. Active alerts: ${stats.activeAlerts}. Highest-risk region: ${stats.highestRiskRegion}.` : null,
    `Last dashboard refresh: ${lastUpdatedText}.`,
  ].filter(Boolean);

  if (lowerPrompt.includes('critical')) {
    if (criticalIncidents.length === 0) {
      return `${summaryLines.join('\n\n')}\n\nThere are no critical incidents in the current local dataset.`;
    }

    return `${summaryLines.join('\n\n')}\n\nCurrent critical incidents:\n${criticalIncidents
      .map((incident) => `- ${incident.title} (${incident.region}, risk ${incident.riskScore})`)
      .join('\n')}`;
  }

  if (lowerPrompt.includes('region') || lowerPrompt.includes('beirut')) {
    return `${summaryLines.join('\n\n')}\n\nRegions that need attention right now:\n${topIncidents
      .map((incident) => `- ${incident.region}: ${incident.title}`)
      .join('\n')}`;
  }

  if (lowerPrompt.includes('credibility') || lowerPrompt.includes('source')) {
    return `${summaryLines.join('\n\n')}\n\nTop sources in the local dataset:\n${topIncidents
      .map((incident) => `- ${incident.sourceInfo.name}: ${incident.sourceInfo.credibility} credibility (${incident.sourceInfo.credibilityScore}/100)`)
      .join('\n')}`;
  }

  return `${summaryLines.join('\n\n')}\n\nTop alerts:\n${topAlerts
    .map((alert) => `- ${alert.title} (${alert.region})`)
    .join('\n')}\n\nRecent incidents:\n${topIncidents
    .map((incident) => `- ${incident.title}`)
    .join('\n')}`;
}

export function CrisisChat({
  incidents,
  alerts,
  stats,
  lastUpdated,
}: {
  incidents?: Incident[];
  alerts?: Alert[];
  stats?: DashboardStats;
  lastUpdated?: Date;
}) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  useEffect(() => {
    if (open && inputRef.current) inputRef.current.focus();
  }, [open]);

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || isLoading) return;

    const userMsg: Message = { role: 'user', content: text.trim() };
    const allMessages = [...messages, userMsg];
    setMessages(allMessages);
    setInput('');
    setIsLoading(true);

    let assistantSoFar = '';

    const upsertAssistant = (chunk: string) => {
      assistantSoFar += chunk;
      setMessages(prev => {
        const last = prev[prev.length - 1];
        if (last?.role === 'assistant') {
          return prev.map((m, i) => (i === prev.length - 1 ? { ...m, content: assistantSoFar } : m));
        }
        return [...prev, { role: 'assistant', content: assistantSoFar }];
      });
    };

    try {
      const context = {
        incidents: incidents?.slice(0, 10) ?? [],
        alerts: alerts?.slice(0, 10) ?? [],
        stats: stats ?? undefined,
        lastUpdated: lastUpdated ? lastUpdated.toISOString() : undefined,
      };

      if (!runtimeConfig.hasChatBackend) {
        upsertAssistant(buildLocalAssistantResponse({ prompt: text, incidents, alerts, stats, lastUpdated }));
        return;
      }

      const resp = await fetch(CHAT_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(runtimeConfig.supabasePublishableKey
            ? { Authorization: `Bearer ${runtimeConfig.supabasePublishableKey}` }
            : {}),
        },
        body: JSON.stringify({ messages: allMessages, context }),
      });

      if (!resp.ok) {
        let errorMessage = 'Failed to get AI response.';

        try {
          const data = await resp.json();
          const details = typeof data?.details === 'string' ? data.details : '';
          const error = typeof data?.error === 'string' ? data.error : '';
          const combined = `${error} ${details}`.toLowerCase();

          if (combined.includes('invalid_api_key') || combined.includes('incorrect api key')) {
            errorMessage = 'The local OpenAI API key is invalid or expired. Update OPENAI_API_KEY in .env.';
          } else if (combined.includes('insufficient_quota') || combined.includes('exceeded your current quota')) {
            errorMessage = 'The OpenAI API key is valid, but the project has no remaining API quota or billing is not active.';
          } else if (error) {
            errorMessage = error;
          }
        } catch {
          // Ignore JSON parse errors and fall back to generic messaging.
        }

        if (resp.status === 429) {
          toast.error('Rate limit reached. Please wait a moment.');
        } else if (resp.status === 402) {
          toast.error('AI credits exhausted. Please add funds.');
        } else {
          toast.error(errorMessage);
        }
        upsertAssistant(`I couldn't answer because the live chat backend returned an error.\n\n${errorMessage}`);
        setIsLoading(false);
        return;
      }

      if (!resp.body) {
        toast.error('Failed to get AI response.');
        upsertAssistant("I couldn't answer because the live chat backend returned an empty response.");
        setIsLoading(false);
        return;
      }

      const contentType = resp.headers.get('content-type') || '';
      if (contentType.includes('application/json')) {
        const data = await resp.json();
        const answer = typeof data?.answer === 'string' ? data.answer : 'No answer was returned.';
        upsertAssistant(answer);
        return;
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let textBuffer = '';
      let streamDone = false;

      while (!streamDone) {
        const { done, value } = await reader.read();
        if (done) break;
        textBuffer += decoder.decode(value, { stream: true });

        let newlineIndex: number;
        while ((newlineIndex = textBuffer.indexOf('\n')) !== -1) {
          let line = textBuffer.slice(0, newlineIndex);
          textBuffer = textBuffer.slice(newlineIndex + 1);

          if (line.endsWith('\r')) line = line.slice(0, -1);
          if (line.startsWith(':') || line.trim() === '') continue;
          if (!line.startsWith('data: ')) continue;

          const jsonStr = line.slice(6).trim();
          if (jsonStr === '[DONE]') { streamDone = true; break; }

          try {
            const parsed = JSON.parse(jsonStr);
            const content = parsed.choices?.[0]?.delta?.content as string | undefined;
            if (content) upsertAssistant(content);
          } catch {
            textBuffer = line + '\n' + textBuffer;
            break;
          }
        }
      }

      // Final flush
      if (textBuffer.trim()) {
        for (let raw of textBuffer.split('\n')) {
          if (!raw) continue;
          if (raw.endsWith('\r')) raw = raw.slice(0, -1);
          if (raw.startsWith(':') || raw.trim() === '') continue;
          if (!raw.startsWith('data: ')) continue;
          const jsonStr = raw.slice(6).trim();
          if (jsonStr === '[DONE]') continue;
          try {
            const parsed = JSON.parse(jsonStr);
            const content = parsed.choices?.[0]?.delta?.content as string | undefined;
            if (content) upsertAssistant(content);
          } catch { /* ignore */ }
        }
      }
    } catch (e) {
      console.error('Chat error:', e);
      const fallback = buildLocalAssistantResponse({ prompt: text, incidents, alerts, stats, lastUpdated });
      upsertAssistant(`I couldn't reach the live chat backend, so here's a local dashboard-based fallback.\n\n${fallback}`);
      toast.error('Live AI was unavailable, so the assistant answered from local dashboard data instead.');
    } finally {
      setIsLoading(false);
    }
  }, [messages, isLoading, incidents, alerts, stats, lastUpdated]);

  return (
    <>
      {/* Floating trigger button */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full bg-primary text-primary-foreground shadow-lg hover:bg-primary/90 transition-all hover:scale-105 flex items-center justify-center"
        >
          <MessageSquare className="w-6 h-6" />
          <span className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-success animate-pulse" />
        </button>
      )}

      {/* Chat panel */}
      {open && (
        <div className="fixed bottom-6 right-6 z-50 w-[400px] h-[560px] flex flex-col rounded-2xl border border-border bg-card shadow-2xl animate-fade-in-up overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-border/50 bg-card/80 backdrop-blur-sm shrink-0">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center">
                <Bot className="w-4.5 h-4.5 text-primary" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-foreground">CrisisShield AI</h3>
                <div className="flex items-center gap-1">
                  <span className="relative flex h-1.5 w-1.5">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-75" />
                    <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-success" />
                  </span>
                  <span className="text-[9px] text-muted-foreground uppercase tracking-wider">Online</span>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-1">
              {messages.length > 0 && (
                <button
                  onClick={() => setMessages([])}
                  className="p-1.5 rounded-lg hover:bg-accent transition-colors" title="Clear chat"
                >
                  <Trash2 className="w-4 h-4 text-muted-foreground" />
                </button>
              )}
              <button
                onClick={() => setOpen(false)}
                className="p-1.5 rounded-lg hover:bg-accent transition-colors"
              >
                <X className="w-4 h-4 text-muted-foreground" />
              </button>
            </div>
          </div>

          {/* Messages */}
          <div ref={scrollRef} className="flex-1 overflow-auto scrollbar-thin p-4 space-y-4">
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full text-center gap-4">
                <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center">
                  <Bot className="w-6 h-6 text-primary" />
                </div>
                <div>
                  <h4 className="text-sm font-semibold text-foreground mb-1">CrisisShield AI Assistant</h4>
                  <p className="text-xs text-muted-foreground max-w-[260px]">
                    Ask about incidents, risk scores, regional threats, or source credibility.
                  </p>
                </div>
                <div className="grid grid-cols-1 gap-1.5 w-full">
                  {QUICK_PROMPTS.map((prompt) => (
                    <button
                      key={prompt}
                      onClick={() => sendMessage(prompt)}
                      className="text-left text-[11px] px-3 py-2 rounded-lg bg-secondary/40 text-foreground/70 border border-border/30 hover:bg-secondary/60 hover:text-foreground transition-colors"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, i) => (
              <div key={i} className={`flex gap-2 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                <div className={`w-6 h-6 rounded-md flex items-center justify-center shrink-0 mt-0.5 ${
                  msg.role === 'user' ? 'bg-primary/20' : 'bg-accent/60'
                }`}>
                  {msg.role === 'user'
                    ? <User className="w-3.5 h-3.5 text-primary" />
                    : <Bot className="w-3.5 h-3.5 text-foreground/70" />
                  }
                </div>
                <div className={`max-w-[85%] rounded-xl px-3 py-2 text-sm ${
                  msg.role === 'user'
                    ? 'bg-primary text-primary-foreground rounded-tr-sm'
                    : 'bg-secondary/40 text-foreground border border-border/20 rounded-tl-sm'
                }`}>
                  {msg.role === 'assistant' ? (
                    <div className="prose prose-sm prose-invert max-w-none [&>*:first-child]:mt-0 [&>*:last-child]:mb-0 [&_p]:my-1 [&_ul]:my-1 [&_li]:my-0.5 [&_h1]:text-sm [&_h2]:text-sm [&_h3]:text-xs">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                  ) : (
                    <p>{msg.content}</p>
                  )}
                </div>
              </div>
            ))}

            {isLoading && messages[messages.length - 1]?.role !== 'assistant' && (
              <div className="flex gap-2">
                <div className="w-6 h-6 rounded-md bg-accent/60 flex items-center justify-center shrink-0">
                  <Bot className="w-3.5 h-3.5 text-foreground/70" />
                </div>
                <div className="bg-secondary/40 rounded-xl rounded-tl-sm px-3 py-2 border border-border/20">
                  <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
                </div>
              </div>
            )}
          </div>

          {/* Input */}
          <div className="shrink-0 border-t border-border/50 p-3 bg-card/80 backdrop-blur-sm">
            <form
              onSubmit={(e) => { e.preventDefault(); sendMessage(input); }}
              className="flex items-center gap-2"
            >
              <input
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Ask about the crisis situation..."
                className="flex-1 bg-secondary/40 border border-border/30 rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground outline-none focus:border-primary/50 transition-colors"
                disabled={isLoading}
              />
              <button
                type="submit"
                disabled={!input.trim() || isLoading}
                className="p-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                <Send className="w-4 h-4" />
              </button>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
