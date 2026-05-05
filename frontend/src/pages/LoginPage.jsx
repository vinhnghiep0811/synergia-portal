import { useLocation } from "react-router-dom";
import { API_BASE_URL } from "../utils/api";
import "../styles/LoginPage.css";

export function LoginPage() {
  const location = useLocation();
  const error = new URLSearchParams(location.search).get("error");

  const backendLoginUrl = `${API_BASE_URL}/api/auth/google/login`;
  const from = location.state?.from?.pathname || "/";

  const handleLoginClick = () => {
    localStorage.setItem("redirect_after_login", from);
  };

  return (
    <div className="login-container">
      {/* Header */}
      <header className="login-header">
        <button
          onClick={() => (window.location.href = "/")}
          style={{
            fontSize: "1.25rem",
            fontWeight: "700",
            background: "none",
            border: "none",
            cursor: "pointer",
            color: "#4f46e5",
          }}
        >
          SY
        </button>

        <div style={{ marginLeft: "1rem" }}>
          <div style={{ fontWeight: 600 }}>Synergia Portal</div>
          <div style={{ fontSize: "0.85rem", color: "#6b7280" }}>
            Trích dẫn & phân tích tài liệu
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="login-main">
        <section className="login-card">
          {/* Logo */}
          <div className="login-logo">
            SY
          </div>

          {/* Title */}
          <h2 className="login-title">
            Đăng nhập
          </h2>

          <p className="login-subtitle">
            Sử dụng tài khoản{" "}
            <span className="login-highlight">
              @hcmut.edu.vn
            </span>{" "}
            để truy cập hệ thống
          </p>

          {/* Error */}
          {error && (
            <div className="login-error">
              {error === "auth_failed"
                ? "Đăng nhập thất bại. Vui lòng thử lại."
                : error}
            </div>
          )}

          {/* Button */}
          <a
            href={backendLoginUrl}
            onClick={handleLoginClick}
            className="login-button"
          >
            <svg width="20" height="20" viewBox="0 0 24 24">
              <path
                fill="#4285F4"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="#34A853"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="#FBBC05"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22z"
              />
              <path
                fill="#EA4335"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
              />
            </svg>
            Đăng nhập với Google
          </a>

          {/* Footer */}
          <p className="login-footer">
            Bằng việc đăng nhập, bạn đồng ý với điều khoản sử dụng
          </p>
        </section>
      </main>
    </div>
  );
}