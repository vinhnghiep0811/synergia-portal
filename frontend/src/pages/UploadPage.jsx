import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { UploadPanel } from "../components/UploadPanel.jsx";

export function UploadPage() {
  const [lastUploadedCount, setLastUploadedCount] = useState(0);
  const navigate = useNavigate();

  function handleUploadMock(files) {
    setLastUploadedCount(files.length);
    // Sau này có thể gọi API thật rồi navigate.
    navigate("/papers");
  }

  return (
    <div className="app-shell">
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
            <h1 className="app-title">Upload PDF</h1>
            <p className="app-subtitle">Tải tài liệu nghiên cứu lên hệ thống.</p>
          </div>
        </div>
        <div className="app-header__meta">
          <span className="app-tag">Week 2 · Ingestion MVP</span>
        </div>
      </header>

      <main className="app-main app-main--upload">
        <div className="app-main__full">
          <UploadPanel onUploadMock={handleUploadMock} />
        </div>
        <div className="app-main__below">
          <section className="card detail-card">
            <header className="card__header">
              <div>
                <h2 className="card__title">Thông tin xử lý tài liệu</h2>
                <p className="card__subtitle">
                  Sau khi upload, hệ thống sẽ kiểm tra file, lưu trữ an toàn và
                  đưa vào hàng chờ xử lý nội dung.
                </p>
              </div>
            </header>
            <p style={{ fontSize: "0.85rem", color: "#4b5563" }}>
              Hệ thống sẽ tự động:
            </p>
            <ul style={{ fontSize: "0.85rem", color: "#4b5563" }}>
              <li>Upload file PDF lên kho lưu trữ nội bộ.</li>
              <li>Tạo bản ghi tài liệu với trạng thái chờ xử lý.</li>
              <li>
                Kích hoạt worker parse PDF, trích DOI/title/fingerprint và tạo{" "}
                <code>CanonicalDocument</code>.
              </li>
            </ul>
            {lastUploadedCount > 0 && (
              <p style={{ fontSize: "0.85rem", color: "#16a34a" }}>
                Đã upload {lastUploadedCount} file. Bạn vừa được chuyển sang danh
                sách tài liệu để xem trạng thái xử lý.
              </p>
            )}
          </section>
        </div>
      </main>
    </div>
  );
}

