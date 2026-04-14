import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import Dashboard from "./pages/Dashboard";
import IncidentMap from "./pages/IncidentMap";
import Analytics from "./pages/Analytics";
import Alerts from "./pages/Alerts";
import OfficialFeeds from "./pages/OfficialFeeds";
import Login from "./pages/Login";
import SettingsPage from "./pages/SettingsPage";
import HateSpeechMonitor from "./pages/HateSpeechMonitor";
import NotFound from "./pages/NotFound";

const queryClient = new QueryClient();

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Sonner />
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/map" element={<IncidentMap />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/official-feeds" element={<OfficialFeeds />} />
          <Route path="/alerts" element={<Alerts />} />
          <Route path="/hate-speech" element={<HateSpeechMonitor />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/login" element={<Login />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
