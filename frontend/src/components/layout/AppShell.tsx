import { ReactNode } from "react";
import { Header } from "./Header";
import "./AppShell.css";

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="app-shell">
      <Header />
      <main className="app-shell__main">{children}</main>
    </div>
  );
}
