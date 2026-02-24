import { useState, useEffect, useCallback } from "react";
import {
  getApiKey,
  setApiKey,
  fetchAuthUser,
  logout,
  type AuthUser,
} from "./api";
import { OverviewPage } from "./pages/OverviewPage";
import { EventsPage } from "./pages/EventsPage";
import { ErrorsPage } from "./pages/ErrorsPage";
import { ComparisonPage } from "./pages/ComparisonPage";
import { RepoDetailPage } from "./pages/RepoDetailPage";

type Tab = "overview" | "events" | "errors" | "comparison" | "repo";

const tabs: { id: Tab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "events", label: "Events" },
  { id: "errors", label: "Errors" },
  { id: "comparison", label: "Comparison" },
  { id: "repo", label: "Repo Detail" },
];

export function App() {
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  // API key fallback state
  const [showApiKey, setShowApiKey] = useState(false);
  const [keyInput, setKeyInput] = useState(getApiKey());
  const [apiKeyConnected, setApiKeyConnected] = useState(!!getApiKey());

  // Check for existing session on mount
  useEffect(() => {
    fetchAuthUser().then((u) => {
      setUser(u);
      setLoading(false);
    });
  }, []);

  const handleLogout = useCallback(async () => {
    await logout();
    setUser(null);
  }, []);

  const handleApiKeyConnect = useCallback(() => {
    setApiKey(keyInput);
    setApiKeyConnected(true);
  }, [keyInput]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") handleApiKeyConnect();
    },
    [handleApiKeyConnect],
  );

  const isAuthenticated = !!user || apiKeyConnected;

  return (
    <div className="max-w-6xl mx-auto px-4 py-6">
      {/* Header */}
      <header className="relative flex items-center justify-between mb-8 pb-4 border-b border-border scanlines overflow-hidden">
        <div>
          <h1 className="text-xl font-bold font-mono tracking-tight">
            <span className="text-accent">AZ</span>
            <span className="text-text-muted mx-1">/</span>
            <span>Telemetry</span>
          </h1>
          <p className="text-xs font-mono text-text-muted mt-0.5">
            assemblyzero workflow observability
          </p>
        </div>

        <div className="flex items-center gap-3">
          {loading ? (
            <span className="text-xs font-mono text-text-muted">...</span>
          ) : user ? (
            <>
              <img
                src={user.avatar}
                alt={user.login}
                className="w-7 h-7 rounded-full border border-border"
              />
              <span className="text-sm font-mono text-text">{user.login}</span>
              <button
                onClick={handleLogout}
                className="text-xs font-mono text-text-muted hover:text-text transition-colors"
              >
                logout
              </button>
            </>
          ) : (
            <>
              <a
                href="/api/auth/github"
                className="bg-accent/10 text-accent border border-accent/20 hover:bg-accent/20 px-4 py-1.5 rounded text-sm font-mono font-medium transition-colors inline-flex items-center gap-2"
              >
                <svg className="w-4 h-4" viewBox="0 0 16 16" fill="currentColor">
                  <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
                </svg>
                Login with GitHub
              </a>
              <button
                onClick={() => setShowApiKey(!showApiKey)}
                className="text-xs font-mono text-text-muted hover:text-text transition-colors"
                title="Use API key instead"
              >
                key
              </button>
            </>
          )}
        </div>
      </header>

      {/* API key fallback (hidden by default) */}
      {!user && showApiKey && (
        <div className="flex items-center gap-2 mb-6 p-3 bg-surface rounded border border-border">
          <input
            type="password"
            placeholder="API Key"
            value={keyInput}
            onChange={(e) => setKeyInput(e.target.value)}
            onKeyDown={handleKeyDown}
            className="bg-bg border border-border rounded px-3 py-1.5 text-sm font-mono text-text w-56 focus:outline-none focus:border-accent/50 placeholder:text-text-muted/50"
          />
          <button
            onClick={handleApiKeyConnect}
            className="bg-accent/10 text-accent border border-accent/20 hover:bg-accent/20 px-4 py-1.5 rounded text-sm font-mono font-medium transition-colors"
          >
            {apiKeyConnected ? "Reconnect" : "Connect"}
          </button>
          {apiKeyConnected && (
            <span className="w-2 h-2 rounded-full bg-human animate-pulse" title="Connected" />
          )}
        </div>
      )}

      {/* Tab navigation */}
      <nav className="flex gap-1 mb-6 border-b border-border">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 text-sm font-mono transition-colors relative ${
              activeTab === tab.id
                ? "text-accent"
                : "text-text-muted hover:text-text"
            }`}
          >
            {tab.label}
            {activeTab === tab.id && (
              <span className="absolute bottom-0 left-0 right-0 h-px bg-accent" />
            )}
          </button>
        ))}
      </nav>

      {/* Tab content */}
      {isAuthenticated ? (
        <>
          {activeTab === "overview" && <OverviewPage />}
          {activeTab === "events" && <EventsPage />}
          {activeTab === "errors" && <ErrorsPage />}
          {activeTab === "comparison" && <ComparisonPage />}
          {activeTab === "repo" && <RepoDetailPage />}
        </>
      ) : (
        <div className="text-center py-20">
          <div className="text-text-muted font-mono text-sm">
            Login with GitHub to view telemetry data
          </div>
        </div>
      )}
    </div>
  );
}
