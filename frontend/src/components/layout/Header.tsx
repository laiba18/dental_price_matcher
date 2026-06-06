import { ReactNode } from "react";
import { useAuth } from "../../context/AuthContext";
import { useBackendStatus } from "../../hooks/useBackendStatus";
import { Button } from "../ui/Button";
import "./Header.css";

interface HeaderProps {
  children?: ReactNode;
}

export function Header({ children }: HeaderProps) {
  const { user, logout } = useAuth();
  const { status, version } = useBackendStatus();

  return (
    <header className="app-header">
      <div className="app-header__inner">
        <div className="app-header__brand">
          <div className="app-header__logo" aria-hidden="true">
            <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
              <rect width="32" height="32" rx="8" fill="currentColor" />
              <path
                d="M10 22c0-6 2.5-10 6-10s6 4 6 10"
                stroke="#fff"
                strokeWidth="2.5"
                strokeLinecap="round"
              />
              <circle cx="16" cy="8" r="2.5" fill="#fff" />
            </svg>
          </div>
          <div>
            <h1 className="app-header__title">Dental Price Matcher</h1>
            <p className="app-header__tagline">Supply intelligence &amp; savings analysis</p>
          </div>
        </div>

        <div className="app-header__actions">
          {children}
          <div className={`app-header__status app-header__status--${status}`}>
            <span className="app-header__status-dot" aria-hidden="true" />
            {status === "checking" && "Connecting..."}
            {status === "online" && `Backend v${version ?? "5.0.0"}`}
            {status === "offline" && "Backend offline"}
          </div>
          {user && (
            <div className="app-header__user">
              <span className="app-header__avatar">{user.name.charAt(0)}</span>
              <div className="app-header__user-info">
                <span className="app-header__user-name">{user.name}</span>
                <span className="app-header__user-email">{user.email}</span>
              </div>
              <Button variant="ghost" size="sm" onClick={logout}>
                Sign out
              </Button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
