import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { apiClient } from "../services/apiClient";

export function AuthCallbackPage() {
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    apiClient
      .get("/auth/me")
      .then(() => {
        navigate("/", { replace: true });
      })
      .catch(() => {
        // Only redirect to /login if not already there
        if (window.location.pathname !== "/login") {
          navigate("/login?error=auth_failed", { replace: true });
        }
      });
  }, [navigate]);

  return (
    <div className="app-shell" style={{ maxWidth: 720 }}>
      <section className="card">
        <h2 className="card__title" style={{ marginTop: 0 }}>
          Đang hoàn tất đăng nhập...
        </h2>
        <p className="card__subtitle">Vui lòng đợi trong giây lát.</p>
      </section>
    </div>
  );
}

