import { useMemo, useState } from "react";
import { PaperStatusBadge } from "./PaperStatusBadge.jsx";
import { formatDate } from "../utils/formatDate.js";

export function PaperList({ papers, onSelect, selectedId }) {
  const [searchText, setSearchText] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  const filtered = useMemo(() => {
    return papers.filter((p) => {
      const textMatch =
        !searchText ||
        (p.status === "pending" && (p.originalFilename || p.filename || "").toLowerCase().includes(searchText.toLowerCase())) ||
        (p.status !== "pending" && p.title && p.title.toLowerCase().includes(searchText.toLowerCase())) ||
        (p.authors && p.authors.join(", ").toLowerCase().includes(searchText.toLowerCase())) ||
        (p.canonicalKey || "").toLowerCase().includes(searchText.toLowerCase()) ||
        p.id.toLowerCase().includes(searchText.toLowerCase());
      const statusMatch =
        statusFilter === "all" ? true : p.status === statusFilter;
      return textMatch && statusMatch;
    });
  }, [papers, searchText, statusFilter]);

  const pendingPapers = filtered.filter(p => p.status === "pending");
  const processedPapers = filtered.filter(p => p.status !== "pending");

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

      {/* Pending Papers - Simple Table */}
      {pendingPapers.length > 0 && (
        <div style={{ marginBottom: "2rem" }}>
          <div style={{ 
            display: "flex", 
            alignItems: "center", 
            gap: "0.5rem",
            marginBottom: "1rem" 
          }}>
            <div style={{
              width: "8px",
              height: "8px",
              borderRadius: "999px",
              backgroundColor: "#f59e0b",
              animation: "pulse 2s infinite"
            }}></div>
            <h3 style={{ 
              fontSize: "0.95rem", 
              fontWeight: "600", 
              margin: 0, 
              color: "#374151" 
            }}>
              Đang chờ xử lý ({pendingPapers.length})
            </h3>
          </div>
          <div className="table-wrapper">
            <table className="paper-table">
              <thead>
                <tr>
                  <th>Mã tài liệu</th>
                  <th>Tên tệp</th>
                  <th>Dung lượng</th>
                  <th>Thời gian tải lên</th>
                  <th>Thao tác</th>
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
                    onClick={() => onSelect(paper.id)}
                  >
                    <td>
                      <div className="simple-list-id">{paper.id}</div>
                    </td>
                    <td className="paper-title-cell">
                      <div className="paper-title-main">
                        {paper.originalFilename || paper.filename || "Unknown file"}
                      </div>
                    </td>
                    <td>{paper.sizeMB?.toFixed(1)} MB</td>
                    <td>{formatDate(paper.uploadedAt)}</td>
                    <td>
                      <button
                        className="btn btn--link"
                        style={{ 
                          fontSize: "0.8rem", 
                          padding: "0.2rem 0.4rem",
                          textDecoration: "underline",
                          color: "#4f46e5",
                          background: "none",
                          border: "none",
                          cursor: "pointer"
                        }}
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelect(paper.id);
                        }}
                      >
                        Xem chi tiết
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Processed Papers - Clean Table */}
      {processedPapers.length > 0 && (
        <div>
          <div style={{ 
            display: "flex", 
            alignItems: "center", 
            gap: "0.5rem",
            marginBottom: "1rem" 
          }}>
            <div style={{
              width: "8px",
              height: "8px",
              borderRadius: "999px",
              backgroundColor: "#22c55e"
            }}></div>
            <h3 style={{ 
              fontSize: "0.95rem", 
              fontWeight: "600", 
              margin: 0, 
              color: "#374151" 
            }}>
              Đã xử lý ({processedPapers.length})
            </h3>
          </div>
          <div className="table-wrapper">
            <table className="paper-table">
              <thead>
                <tr>
                  <th>Mã tài liệu</th>
                  <th>Tiêu đề</th>
                  <th>Trạng thái</th>
                  <th>Tác giả</th>
                  <th>Năm xuất bản</th>
                  <th>Thao tác</th>
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
                    onClick={() => onSelect(paper.id)}
                  >
                    <td>
                      <div className="simple-list-id">{paper.id}</div>
                    </td>
                    <td className="paper-title-cell">
                      <div className="paper-title-main">
                        {paper.title || "Đang xử lý..."}
                      </div>
                      {paper.venue && (
                        <div className="paper-title-sub">
                          {paper.venue}
                        </div>
                      )}
                    </td>
                    <td>
                      <PaperStatusBadge status={paper.status} />
                    </td>
                    <td>
                      <div style={{ 
                        fontSize: "0.8rem", 
                        color: "#6b7280",
                        maxWidth: "200px",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap"
                      }}>
                        {(paper.authors || []).join(", ") || "-"}
                      </div>
                    </td>
                    <td>{paper.year || "-"}</td>
                    <td>
                      <button
                        className="btn btn--link"
                        style={{ 
                          fontSize: "0.8rem", 
                          padding: "0.2rem 0.4rem",
                          textDecoration: "underline",
                          color: "#4f46e5",
                          background: "none",
                          border: "none",
                          cursor: "pointer"
                        }}
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelect(paper.id);
                        }}
                      >
                        Xem chi tiết
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

