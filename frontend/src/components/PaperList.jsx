import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { PaperStatusBadge } from "./PaperStatusBadge.jsx";
import { getPaperFileViewUrl } from "../services/paperApi.js";
import { formatDate } from "../utils/formatDate.js";

const actionButtonStyle = {
  fontSize: "0.8rem",
  padding: "0.2rem 0.4rem",
  textDecoration: "underline",
  background: "none",
  border: "none",
  cursor: "pointer",
};

export function PaperList({ papers, selectedId }) {
  const [searchText, setSearchText] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const navigate = useNavigate();

  function openPaperPdf(event, paperId) {
    event.stopPropagation();
    window.open(getPaperFileViewUrl(paperId), "_blank");
  }

  const filtered = useMemo(() => {
    return papers.filter((p) => {
      const textMatch =
        !searchText ||
        (p.status === "pending" &&
          (p.originalFilename || p.filename || "")
            .toLowerCase()
            .includes(searchText.toLowerCase())) ||
        (p.status !== "pending" &&
          p.title &&
          p.title.toLowerCase().includes(searchText.toLowerCase())) ||
        (p.authors &&
          p.authors.join(", ").toLowerCase().includes(searchText.toLowerCase())) ||
        (p.canonicalKey || "").toLowerCase().includes(searchText.toLowerCase()) ||
        p.id.toLowerCase().includes(searchText.toLowerCase());

      const statusMatch = statusFilter === "all" ? true : p.status === statusFilter;
      return textMatch && statusMatch;
    });
  }, [papers, searchText, statusFilter]);

  const pendingPapers = filtered.filter(
    (p) =>
      p.status === "parse_queued" ||
      p.status === "canonicalized" ||
      p.status === "pending"
  );
  const processedPapers = filtered.filter(
    (p) => p.status === "processed" || p.status === "duplicate_detected"
  );

  return (
    <section className="card list-card">
      <header className="card__header card__header--with-actions">
        <div>
          <h2 className="card__title">Danh sách tài liệu nghiên cứu</h2>
          <p className="card__subtitle">
            Quản lý và theo dõi trạng thái xử lý của các tài liệu học thuật.
          </p>
        </div>
        <div className="list-filters">
          <input
            type="search"
            placeholder="Tìm kiếm theo tên file, tiêu đề, tác giả, DOI..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
          />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="all">Tất cả trạng thái</option>
            <option value="pending">Đang xử lý</option>
            <option value="processed">Đã hoàn thành</option>
            <option value="failed">Xử lý thất bại</option>
          </select>
        </div>
      </header>

      {pendingPapers.length > 0 && (
        <div style={{ marginBottom: "2rem" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
              marginBottom: "1rem",
            }}
          >
            <div
              style={{
                width: "8px",
                height: "8px",
                borderRadius: "999px",
                backgroundColor: "#f59e0b",
                animation: "pulse 2s infinite",
              }}
            />
            <h3
              style={{
                fontSize: "0.95rem",
                fontWeight: "600",
                margin: 0,
                color: "#374151",
              }}
            >
              Đang chờ xử lý ({pendingPapers.length})
            </h3>
          </div>

          <div className="table-wrapper">
            <table className="paper-table">
              <thead>
                <tr>
                  <th>Mã</th>
                  <th>Tệp</th>
                  <th>Dung lượng</th>
                  <th>Tải lên</th>
                  <th>Chi tiết</th>
                  <th>Xem PDF</th>
                </tr>
              </thead>
              <tbody>
                {pendingPapers.map((paper) => (
                  <tr
                    key={paper.id}
                    className={
                      paper.id === selectedId
                        ? "paper-row paper-row--selected"
                        : "paper-row"
                    }
                    style={{ cursor: "pointer" }}
                    onClick={() => navigate(`/papers/${paper.id}`)}
                  >
                    <td>
                      <div className="simple-list-id">{paper.id}</div>
                    </td>
                    <td className="paper-title-cell">
                      <div className="paper-title-main">
                        {paper.originalFilename || paper.filename || "Unknown file"}
                      </div>
                    </td>
                    <td>{paper.sizeMB != null ? `${paper.sizeMB.toFixed(1)} MB` : "-"}</td>
                    <td>{paper.uploadedAt ? formatDate(paper.uploadedAt) : "-"}</td>
                    <td>
                      <button
                        className="btn btn--link"
                        style={{ ...actionButtonStyle, color: "#4f46e5" }}
                        onClick={(event) => {
                          event.stopPropagation();
                          navigate(`/papers/${paper.id}`);
                        }}
                      >
                        Xem
                      </button>
                    </td>
                    <td>
                      <button
                        className="btn btn--link"
                        style={{ ...actionButtonStyle, color: "#0f766e" }}
                        onClick={(event) => openPaperPdf(event, paper.id)}
                      >
                        PDF
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {processedPapers.length > 0 && (
        <div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "0.5rem",
              marginBottom: "1rem",
            }}
          >
            <div
              style={{
                width: "8px",
                height: "8px",
                borderRadius: "999px",
                backgroundColor: "#22c55e",
              }}
            />
            <h3
              style={{
                fontSize: "0.95rem",
                fontWeight: "600",
                margin: 0,
                color: "#374151",
              }}
            >
              Đã xử lý ({processedPapers.length})
            </h3>
          </div>

          <div className="table-wrapper">
            <table className="paper-table">
              <thead>
                <tr>
                  <th>Mã</th>
                  <th>Tiêu đề</th>
                  <th>Trạng thái</th>
                  <th>Năm</th>
                  <th>Chi tiết</th>
                  <th>Xem PDF</th>
                </tr>
              </thead>
              <tbody>
                {processedPapers.map((paper) => (
                  <tr
                    key={paper.id}
                    className={
                      paper.id === selectedId
                        ? "paper-row paper-row--selected"
                        : "paper-row"
                    }
                    style={{ cursor: "pointer" }}
                    onClick={() => navigate(`/papers/${paper.id}`)}
                  >
                    <td>
                      <div className="simple-list-id">{paper.id}</div>
                    </td>
                    <td className="paper-title-cell">
                      <div className="paper-title-main">
                        {paper.title || "Đang xử lý..."}
                      </div>
                      {paper.venue && <div className="paper-title-sub">{paper.venue}</div>}
                    </td>
                    <td>
                      <PaperStatusBadge status={paper.status} />
                    </td>
                    <td>{paper.year || "-"}</td>
                    <td>
                      <button
                        className="btn btn--link"
                        style={{ ...actionButtonStyle, color: "#4f46e5" }}
                        onClick={(event) => {
                          event.stopPropagation();
                          navigate(`/papers/${paper.id}`);
                        }}
                      >
                        Xem
                      </button>
                    </td>
                    <td>
                      <button
                        className="btn btn--link"
                        style={{ ...actionButtonStyle, color: "#0f766e" }}
                        onClick={(event) => openPaperPdf(event, paper.id)}
                      >
                        PDF
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {filtered.length === 0 && (
        <div style={{ textAlign: "center", padding: "2rem", color: "#6b7280" }}>
          Không tìm thấy tài liệu nào phù hợp với tiêu chí tìm kiếm.
        </div>
      )}
    </section>
  );
}
