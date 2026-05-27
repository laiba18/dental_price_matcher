import { FormEvent, useState } from "react";
import { useAuth } from "../../context/AuthContext";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";
import { Card } from "../ui/Card";
import "./LoginPage.css";

export function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-page">
      <div className="login-page__bg" aria-hidden="true">
        <div className="login-page__orb login-page__orb--1" />
        <div className="login-page__orb login-page__orb--2" />
      </div>

      <div className="login-page__content animate-fade-in">
        <div className="login-page__hero">
          <div className="login-page__logo" aria-hidden="true">
            <svg width="40" height="40" viewBox="0 0 32 32" fill="none">
              <rect width="32" height="32" rx="8" fill="#0D9488" />
              <path
                d="M10 22c0-6 2.5-10 6-10s6 4 6 10"
                stroke="#fff"
                strokeWidth="2.5"
                strokeLinecap="round"
              />
              <circle cx="16" cy="8" r="2.5" fill="#fff" />
            </svg>
          </div>
          <h1 className="login-page__title">Dental Price Matcher</h1>
          <p className="login-page__subtitle">
            Upload Henry Schein order PDFs and discover supplier savings in minutes.
          </p>
        </div>

        <Card padding="lg" className="login-page__card">
          <h2 className="login-page__form-title">Welcome back</h2>
          <p className="login-page__form-subtitle">Sign in to access your dashboard</p>

          <form className="login-page__form" onSubmit={handleSubmit}>
            <Input
              label="Email address"
              type="email"
              placeholder="admin@dental.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              required
            />
            <Input
              label="Password"
              type="password"
              placeholder="Enter your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
            />

            {error && (
              <div className="login-page__error" role="alert">
                {error}
              </div>
            )}

            <Button type="submit" fullWidth size="lg" loading={loading}>
              Sign in
            </Button>
          </form>

          <p className="login-page__hint">
            Demo: <code>admin@dental.com</code> / <code>dental123</code>
          </p>
        </Card>
      </div>
    </div>
  );
}
