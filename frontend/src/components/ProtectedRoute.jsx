import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export function ProtectedRoute() {
  const { user, isLoading } = useAuth();
  const location = useLocation();
  if (isLoading) return (
      <div className="loading-screen">
        <div className="loading-spinner"></div>
        <p className="loading-text">Đang kiểm tra quyền truy cập...</p>
      </div>
    );

  if (!user) {
    // Avoid redirect loop if already on login or callback
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  return <Outlet />;
}
