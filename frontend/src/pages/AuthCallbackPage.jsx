import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { apiClient } from "../services/apiClient";

export function AuthCallbackPage() {
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const token = params.get("token");
    if (!token) {
      navigate("/login?error=auth_failed", { replace: true });
      return;
    }

    localStorage.setItem("access_token", token);

    apiClient
      .get("/api/auth/me")
      .then(() => {
        navigate("/", { replace: true });
      })
      .catch(() => {
        localStorage.removeItem("access_token");
        navigate("/login?error=auth_failed", { replace: true });
      });
  }, [location.search, navigate]);

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

