import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export function ProtectedRoute() {
  const { user, isLoading } = useAuth();
  const location = window.location.pathname;
  if (isLoading) return null;
  if (!user) {
    // Avoid redirect loop if already on login or callback
    if (location !== "/login" && location !== "/auth/callback") {
      return <Navigate to="/login" replace />;
    }
    return null;
  }
  return <Outlet />;
}
