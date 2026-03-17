import { useEffect, useRef } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { apiClient } from "../services/apiClient";
import { useAuth } from "../context/AuthContext";

export function AuthCallbackPage() {
  const { checkSession } = useAuth();
  const navigate = useNavigate();
  const called = useRef(false);
  // const from = location.state?.from?.pathname || "/";
  useEffect(() => {
    if (called.current) return;
    called.current = true;

    // Lấy lại địa chỉ trang cũ đã lưu trong localStorage (nếu có)
    const savedPath = localStorage.getItem("redirect_after_login") || "/";

    checkSession()
      .then(() => {
        // Xóa dấu vết sau khi dùng xong
        localStorage.removeItem("redirect_after_login");
        navigate(savedPath, { replace: true });
      })
      .catch(() => {
        navigate("/login?error=auth_failed", { replace: true });
      });
  }, [checkSession, navigate]);

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

