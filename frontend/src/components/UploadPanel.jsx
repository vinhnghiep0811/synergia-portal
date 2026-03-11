import { useRef, useState } from "react";

export function UploadPanel({ onUpload, isUploading = false, uploadError = "" }) {
  const [files, setFiles] = useState([]);
  const fileInputRef = useRef(null);

  function handleFileChange(e) {
    const list = Array.from(e.target.files ?? []);
    setFiles(list);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!files.length || isUploading) return;

    const success = await onUpload(files);

    if (success) {
      setFiles([]);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  }

  // function handleSubmit(e) {
  //   e.preventDefault();
  //   if (!files.length) return;
  //   setIsUploading(true);
  //   setTimeout(() => {
  //     onUploadMock(files);
  //     setFiles([]);
  //     setIsUploading(false);
  //   }, 500);
  // }

  return (
    <section className="card upload-card">
      <header className="card__header">
        <div>
          <h2 className="card__title">Upload PDF</h2>
          <p className="card__subtitle">
            Tải lên paper hoặc technical report vào hệ thống.
          </p>
        </div>
      </header>
      <form onSubmit={handleSubmit} className="upload-form">
        <div className="form-row">
          <label className="form-label">
            PDF files
            <input
              ref={fileInputRef}
              type="file"
              accept="application/pdf,.pdf"
              multiple
              onChange={handleFileChange}
              disabled={isUploading}
            />
          </label>
          <p className="form-help">
            Hỗ trợ PDF text-based, tối đa ~20MB (giới hạn thật sẽ kiểm ở
            backend).
          </p>
        </div>
        <div className="form-row form-row--inline">
          <label className="form-label">
            Người upload
            <input
              type="text"
              name="uploader"
              defaultValue="can.nguyen"
              disabled
            />
          </label>
          <label className="form-label">
            Workspace
            <input type="text" value="Default workspace" disabled />
          </label>
        </div>
        <div className="upload-summary">
          {files.length ? (
            <span>
              Đã chọn <strong>{files.length}</strong> file.
            </span>
          ) : (
            <span>Chưa chọn file nào.</span>
          )}
        </div>

        {uploadError && (
          <p style={{ fontSize: "0.85rem", color: "#dc2626", marginTop: "0.5rem" }}>
            {uploadError}
          </p>
        )}

        <div className="form-actions">
          <button
            type="submit"
            className="btn btn--primary"
            disabled={!files.length || isUploading}
          >
            {isUploading ? "Đang upload & xử lý..." : "Upload & xử lý"}
          </button>
        </div>
      </form>
    </section>
  );
}

