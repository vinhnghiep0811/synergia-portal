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
        p.title.toLowerCase().includes(searchText.toLowerCase()) ||
        (p.authors || [])
          .join(", ")
          .toLowerCase()
          .includes(searchText.toLowerCase()) ||
        (p.canonicalKey || "").toLowerCase().includes(searchText.toLowerCase());
      const statusMatch =
        statusFilter === "all" ? true : p.status === statusFilter;
      return textMatch && statusMatch;
    });
  }, [papers, searchText, statusFilter]);

  return (
    <section className="card list-card">
      <header className="card__header card__header--with-actions">
        <div>
          <h2 className="card__title">Paper list</h2>
          <p className="card__subtitle">
            Danh sách các tài liệu đã upload và trạng thái xử lý hiện tại.
          </p>
        </div>
        <div className="list-filters">
          <input
            type="search"
            placeholder="Tìm theo title, author, DOI/fingerprint..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
          />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="all">All statuses</option>
            <option value="pending">Pending</option>
            <option value="processed">Processed</option>
            <option value="failed">Failed</option>
          </select>
        </div>
      </header>
      <div className="table-wrapper">
        <table className="paper-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Title</th>
              <th>Authors</th>
              <th>Year</th>
              <th>Status</th>
              <th>Uploaded at</th>
              <th>Size</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td colSpan={8} style={{ textAlign: "center", padding: 16 }}>
                  Không có paper nào phù hợp filter.
                </td>
              </tr>
            ) : (
              filtered.map((paper) => (
                <tr
                  key={paper.id}
                  className={
                    paper.id === selectedId
                      ? "paper-row paper-row--selected"
                      : "paper-row"
                  }
                >
                  <td>{paper.id}</td>
                  <td className="paper-title-cell">
                    <div className="paper-title-main">{paper.title}</div>
                    <div className="paper-title-sub">
                      {paper.venue ? `${paper.venue} · ` : ""}
                      {paper.canonicalKey}
                    </div>
                  </td>
                  <td>{(paper.authors || []).join(", ")}</td>
                  <td>{paper.year}</td>
                  <td>
                    <PaperStatusBadge status={paper.status} />
                  </td>
                  <td>{formatDate(paper.uploadedAt)}</td>
                  <td>{paper.sizeMB?.toFixed(1)} MB</td>
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
                      onClick={() => onSelect(paper.id)}
                    >
                      Xem chi tiết
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

