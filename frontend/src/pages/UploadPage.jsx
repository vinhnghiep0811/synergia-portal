import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { UploadPanel } from "../components/UploadPanel.jsx";
import { uploadManyPapers } from "../services/paperApi";

export function UploadPage() {
  const [lastUploadedCount, setLastUploadedCount] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const navigate = useNavigate();

  // function handleUploadMock(files) {
  //   setLastUploadedCount(files.length);
  //   // Sau này có thể gọi API thật rồi navigate.
  //   navigate("/papers");
  // }

  async function handleUpload(files) {
    setUploadError("");
    setIsUploading(true);

    try {
      const fileList = Array.from(files ?? []);

      if (!fileList.length) {
        setUploadError("Không có file nào để upload.");
        return false;
      }

      // Nếu muốn chỉ cho phép PDF ngay từ FE
      const invalidFiles = fileList.filter(
        (file) =>
          file.type !== "application/pdf" &&
          !file.name.toLowerCase().endsWith(".pdf")
      );

      if (invalidFiles.length > 0) {
        setUploadError("Chỉ chấp nhận file PDF.");
        return false;
      }

      const results = await uploadManyPapers(fileList);

      setLastUploadedCount(results.length);
      navigate("/papers");
    } catch (error) {
      setUploadError(error.message || "Có lỗi xảy ra khi upload file.");
      return false;
    } finally {
      setIsUploading(false);
    }
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
          <UploadPanel
            onUpload={handleUpload}
            isUploading={isUploading}
            uploadError={uploadError}
          />
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
            {/* {lastUploadedCount > 0 && (
              <p style={{ fontSize: "0.85rem", color: "#16a34a" }}>
                Đã upload {lastUploadedCount} file. Bạn vừa được chuyển sang danh
                sách tài liệu để xem trạng thái xử lý.
              </p>
            )} */}
            {isUploading && (
              <p style={{ fontSize: "0.85rem", color: "#2563eb" }}>
                Đang upload file lên hệ thống...
              </p>
            )}

            {/* {uploadError && (
              <p style={{ fontSize: "0.85rem", color: "#dc2626" }}>
                {uploadError}
              </p>
            )} */}

            {lastUploadedCount > 0 && !isUploading && !uploadError && (
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

