import { AuthProvider, useAuth } from "./context/AuthContext";
import { ToastProvider } from "./context/ToastContext";
import { LoginPage } from "./components/login/LoginPage";
import { AppShell } from "./components/layout/AppShell";
import { Dashboard } from "./components/dashboard/Dashboard";
import { ToastContainer } from "./components/ui/Toast";

function AppContent() {
  const { isAuthenticated } = useAuth();

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  return (
    <AppShell>
      <Dashboard />
    </AppShell>
  );
}

export default function App() {
  return (
    <ToastProvider>
      <AuthProvider>
        <AppContent />
        <ToastContainer />
      </AuthProvider>
    </ToastProvider>
  );
}
