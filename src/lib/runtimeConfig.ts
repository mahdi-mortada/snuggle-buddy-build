const supabaseUrl = (import.meta.env.VITE_SUPABASE_URL ?? "").trim();
const supabasePublishableKey = (import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY ?? "").trim();
const localApiBaseUrl =
  (import.meta.env.VITE_LOCAL_API_BASE_URL ?? "").trim() || (import.meta.env.DEV ? "/api" : "");
const backendApiBaseUrl =
  (import.meta.env.VITE_BACKEND_URL ?? "").trim() || (import.meta.env.DEV ? "http://127.0.0.1:8000" : "");
const backendWsUrl =
  (import.meta.env.VITE_BACKEND_WS_URL ?? "").trim() || (backendApiBaseUrl ? `${backendApiBaseUrl}/ws/live-feed` : "");
const backendDevEmail = (import.meta.env.VITE_BACKEND_DEV_EMAIL ?? "").trim() || "admin@crisisshield.dev";
const backendDevPassword = (import.meta.env.VITE_BACKEND_DEV_PASSWORD ?? "").trim() || "admin12345";

export const runtimeConfig = {
  supabaseUrl,
  supabasePublishableKey,
  localApiBaseUrl,
  backendApiBaseUrl,
  backendWsUrl,
  backendDevEmail,
  backendDevPassword,
  hasSupabaseConfig: Boolean(supabaseUrl && supabasePublishableKey),
  hasBackendApi: Boolean(backendApiBaseUrl),
  hasChatBackend: Boolean(backendApiBaseUrl || localApiBaseUrl || (supabaseUrl && supabasePublishableKey)),
  newsUrl: supabaseUrl ? `${supabaseUrl}/functions/v1/fetch-news` : "",
  chatUrl: backendApiBaseUrl
    ? `${backendApiBaseUrl}/api/v1/chat`
    : localApiBaseUrl
      ? `${localApiBaseUrl}/crisis-chat`
      : (supabaseUrl ? `${supabaseUrl}/functions/v1/crisis-chat` : ""),
};
