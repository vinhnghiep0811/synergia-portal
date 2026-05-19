import { useNavigate } from "react-router-dom";

export function AppHeader({
  title,
  subtitle,
  showUploadButton = true,
  extraAction
}) {
  const navigate = useNavigate();

  const handleLogout = () => {
    // Xóa token người dùng
    localStorage.removeItem("token");

    // Nếu lưu thêm dữ liệu user thì xóa luôn
    localStorage.removeItem("user");

    // Điều hướng về login
    navigate("/login", { replace: true });
  };

  return (
    <header className="app-header">
      <div className="app-header__main">
        <button
          type="button"
          className="app-logo"
          onClick={() => navigate("/")}
        >
          SY
        </button>

        <div className="app-header__titles">
          <h1 className="app-title">
            {title || "Synergia Portal"}
          </h1>
          {subtitle && (
            <p className="app-subtitle">{subtitle}</p>
          )}
        </div>
      </div>

      <div className="app-header__meta">
        {extraAction}

        {showUploadButton && (
          <button
            className="btn btn--primary"
            style={{ marginRight: "1rem" }}
            onClick={() => navigate("/upload")}
          >
            Upload PDF
          </button>
        )}

        

        {/* <span className="app-tag">
          Single workspace · VM on-prem
        </span> */}
       {/* Logout button */}
          <button
            className="btn"
            style={{
              marginRight: "1rem",
              backgroundColor: "#dc3545",
              color: "white",
              border: "none"
            }}
            onClick={handleLogout}
          >
            Logout
          </button>
      </div>
    </header>

  );
}