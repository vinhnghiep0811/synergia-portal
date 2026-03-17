import { useMemo } from "react";
import { useLocation } from "react-router-dom";
import { API_BASE_URL } from "../utils/api";

export function LoginPage() {
  const location = useLocation();
  const error = new URLSearchParams(location.search).get("error");

  const backendLoginUrl = `${API_BASE_URL}/api/auth/google/login`;

  const from = location.state?.from?.pathname || "/";

  const handleLoginClick = () => {
    localStorage.setItem("redirect_after_login", from);
  };

  return (
    <div className="app-shell" style={{ maxWidth: 720 }}>
      <header className="app-header">
        <div className="app-header__main">
          <div className="app-header__titles">
            <h1 className="app-title">Đăng nhập</h1>
            <p className="app-subtitle">
              Chỉ chấp nhận tài khoản email <strong>@hcmut.edu.vn</strong>.
            </p>
          </div>
        </div>
      </header>

      <main className="app-main app-main--upload" style={{ gridTemplateColumns: "1fr" }}>
        <section className="card">
          <header className="card__header">
            <div>
              <h2 className="card__title">Google OAuth2</h2>
              <p className="card__subtitle">Đăng nhập để truy cập Synergia Portal.</p>
            </div>
          </header>

          {error && (
            <p style={{ fontSize: "0.9rem", color: "#dc2626", marginTop: 0 }}>
              {error === "auth_failed"
                ? "Đăng nhập thất bại hoặc token không hợp lệ. Vui lòng thử lại."
                : `Lỗi: ${error}`}
            </p>
          )}

          <div className="form-actions" style={{ justifyContent: "flex-start" }}>
            <a className="btn btn--primary" href={backendLoginUrl} onClick={handleLoginClick}>
              Đăng nhập với Google (@hcmut.edu.vn)
            </a>
          </div>
        </section>
      </main>
    </div>
  );
}

