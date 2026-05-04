import { useState, useEffect, useCallback } from "react";
import { AppHeader } from "../components/AppHeader.jsx";
import { 
  getAdminOverview, 
  getAdminPapers, 
  getAdminCanonicalDocuments, 
  getAdminActivities 
} from "../services/adminApi.js";

export function AdminPage() {
  const [activeTab, setActiveTab] = useState("overview");
  const [overview, setOverview] = useState(null);
  const [papers, setPapers] = useState([]);
  const [canonicalDocuments, setCanonicalDocuments] = useState([]);
  const [activities, setActivities] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  
  // Pagination states
  const [papersPage, setPapersPage] = useState(1);
  const [canonicalPage, setCanonicalPage] = useState(1);
  const [activitiesPage, setActivitiesPage] = useState(1);
  
  // Total counts for pagination
  const [papersTotal, setPapersTotal] = useState(0);
  const [canonicalTotal, setCanonicalTotal] = useState(0);
  const [activitiesTotal, setActivitiesTotal] = useState(0);
  
  // Different page sizes for each tab
  const papersPageSize = 5;
  const canonicalPageSize = 5;
  const activitiesPageSize = 20;

  const loadOverview = useCallback(async () => {
    try {
      setLoading(true);
      setError("");
      const data = await getAdminOverview();
      setOverview(data);
    } catch (err) {
      setError(err.message || "Không thể tải overview");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadPapers = useCallback(async () => {
    try {
      setLoading(true);
      setError("");
      const data = await getAdminPapers(papersPage, papersPageSize);
      console.log('Papers API response:', data);
      setPapers(data.items);
      setPapersTotal(data.pagination?.total || 0);
    } catch (err) {
      setError(err.message || "Không thể tải danh sách papers");
    } finally {
      setLoading(false);
    }
  }, [papersPage, papersPageSize]);

  const loadCanonicalDocuments = useCallback(async () => {
    try {
      setLoading(true);
      setError("");
      const data = await getAdminCanonicalDocuments(canonicalPage, canonicalPageSize);
      console.log('Canonical documents API response:', data);
      setCanonicalDocuments(data.items);
      setCanonicalTotal(data.pagination?.total || 0);
    } catch (err) {
      setError(err.message || "Không thể tải danh sách canonical documents");
    } finally {
      setLoading(false);
    }
  }, [canonicalPage, canonicalPageSize]);

  const loadActivities = useCallback(async () => {
    try {
      setLoading(true);
      setError("");
      console.log(`Loading activities page ${activitiesPage} with size ${activitiesPageSize}`);
      const data = await getAdminActivities(activitiesPage, activitiesPageSize);
      console.log('Activities API response:', data);
      setActivities(data.items);
      setActivitiesTotal(data.total || 0);
    } catch (err) {
      console.error('Error loading activities:', err);
      setError(err.message || "Không thể tải danh sách activities");
    } finally {
      setLoading(false);
    }
  }, [activitiesPage, activitiesPageSize]);

  // Load Overview
  useEffect(() => {
    if (activeTab === "overview") {
      loadOverview();
    }
  }, [activeTab, loadOverview]);

  // Load Papers
  useEffect(() => {
    if (activeTab === "papers") {
      loadPapers();
    }
  }, [activeTab, loadPapers]);

  // Load Canonical Documents
  useEffect(() => {
    if (activeTab === "canonical") {
      loadCanonicalDocuments();
    }
  }, [activeTab, loadCanonicalDocuments]);

  // Load Activities
  useEffect(() => {
    if (activeTab === "activities") {
      loadActivities();
    }
  }, [activeTab, loadActivities]);

  const getStatusColor = (status) => {
    const colors = {
      success: "#22c55e",
      info: "#3b82f6", 
      warning: "#f59e0b",
      error: "#ef4444"
    };
    return colors[status] || "#6b7280";
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleString('vi-VN');
  };

  // Pagination component
  const Pagination = ({ currentPage, totalPages, onPageChange }) => {
    if (totalPages <= 1) return null;
    
    const pages = [];
    const maxVisiblePages = 5;
    
    let startPage = Math.max(1, currentPage - Math.floor(maxVisiblePages / 2));
    let endPage = Math.min(totalPages, startPage + maxVisiblePages - 1);
    
    if (endPage - startPage + 1 < maxVisiblePages) {
      startPage = Math.max(1, endPage - maxVisiblePages + 1);
    }
    
    for (let i = startPage; i <= endPage; i++) {
      pages.push(i);
    }
    
    return (
      <div style={{ 
        display: "flex", 
        justifyContent: "center", 
        alignItems: "center", 
        gap: "0.5rem", 
        marginTop: "1rem" 
      }}>
        <button
          onClick={() => onPageChange(1)}
          disabled={currentPage === 1}
          style={{
            padding: "0.5rem",
            border: "1px solid #d1d5db",
            backgroundColor: currentPage === 1 ? "#f9fafb" : "white",
            cursor: currentPage === 1 ? "not-allowed" : "pointer",
            borderRadius: "0.25rem"
          }}
        >
          «
        </button>
        
        <button
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage === 1}
          style={{
            padding: "0.5rem",
            border: "1px solid #d1d5db",
            backgroundColor: currentPage === 1 ? "#f9fafb" : "white",
            cursor: currentPage === 1 ? "not-allowed" : "pointer",
            borderRadius: "0.25rem"
          }}
        >
          ‹
        </button>
        
        {startPage > 1 && (
          <>
            <button
              onClick={() => onPageChange(1)}
              style={{
                padding: "0.5rem",
                border: "1px solid #d1d5db",
                backgroundColor: "white",
                cursor: "pointer",
                borderRadius: "0.25rem"
              }}
            >
              1
            </button>
            {startPage > 2 && <span>...</span>}
          </>
        )}
        
        {pages.map(page => (
          <button
            key={page}
            onClick={() => onPageChange(page)}
            style={{
              padding: "0.5rem",
              border: "1px solid #d1d5db",
              backgroundColor: page === currentPage ? "#3b82f6" : "white",
              color: page === currentPage ? "white" : "black",
              cursor: "pointer",
              borderRadius: "0.25rem"
            }}
          >
            {page}
          </button>
        ))}
        
        {endPage < totalPages && (
          <>
            {endPage < totalPages - 1 && <span>...</span>}
            <button
              onClick={() => onPageChange(totalPages)}
              style={{
                padding: "0.5rem",
                border: "1px solid #d1d5db",
                backgroundColor: "white",
                cursor: "pointer",
                borderRadius: "0.25rem"
              }}
            >
              {totalPages}
            </button>
          </>
        )}
        
        <button
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage === totalPages}
          style={{
            padding: "0.5rem",
            border: "1px solid #d1d5db",
            backgroundColor: currentPage === totalPages ? "#f9fafb" : "white",
            cursor: currentPage === totalPages ? "not-allowed" : "pointer",
            borderRadius: "0.25rem"
          }}
        >
          ›
        </button>
        
        <button
          onClick={() => onPageChange(totalPages)}
          disabled={currentPage === totalPages}
          style={{
            padding: "0.5rem",
            border: "1px solid #d1d5db",
            backgroundColor: currentPage === totalPages ? "#f9fafb" : "white",
            cursor: currentPage === totalPages ? "not-allowed" : "pointer",
            borderRadius: "0.25rem"
          }}
        >
          »
        </button>
      </div>
    );
  };

  return (
    <div className="app-shell">
      <AppHeader 
        title="Quản trị hệ thống" 
        subtitle="Quản lý và giám sát hệ thống"
      />

      <main className="app-main app-main--papers">
        <div className="app-main__full">
          {/* Tabs */}
          <div className="tabs">
            <button
              className={`tab ${activeTab === "overview" ? "tab--active" : ""}`}
              onClick={() => setActiveTab("overview")}
            >
              <div className="tab__indicator tab__indicator--overview"></div>
              Tổng quan
            </button>
            <button
              className={`tab ${activeTab === "papers" ? "tab--active" : ""}`}
              onClick={() => setActiveTab("papers")}
            >
              <div className="tab__indicator tab__indicator--papers"></div>
              Papers
            </button>
            <button
              className={`tab ${activeTab === "canonical" ? "tab--active" : ""}`}
              onClick={() => setActiveTab("canonical")}
            >
              <div className="tab__indicator tab__indicator--canonical"></div>
              Canonical Documents
            </button>
            <button
              className={`tab ${activeTab === "activities" ? "tab--active" : ""}`}
              onClick={() => setActiveTab("activities")}
            >
              <div className="tab__indicator tab__indicator--activities"></div>
              Hoạt động
            </button>
          </div>

          {/* Error */}
          {error && (
            <div className="card" style={{ 
              padding: "1rem", 
              marginBottom: "1rem", 
              color: "#dc2626",
              backgroundColor: "#fef2f2",
              border: "1px solid #fecaca"
            }}>
              {error}
            </div>
          )}

          {/* Loading */}
          {loading && (
            <div className="card" style={{ padding: "1rem" }}>
              Đang tải...
            </div>
          )}

          {/* Overview Tab */}
          {activeTab === "overview" && overview && (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "1rem" }}>
              {/* Total Papers */}
              <div className="card" style={{ padding: "1.5rem" }}>
                <h3 style={{ margin: "0 0 1rem 0", color: "#374151" }}>Tổng số Papers</h3>
                <div style={{ fontSize: "2rem", fontWeight: "bold", color: "#1f2937" }}>
                  {overview.total_papers}
                </div>
              </div>

              {/* Processing Status */}
              <div className="card" style={{ padding: "1.5rem" }}>
                <h3 style={{ margin: "0 0 1rem 0", color: "#374151" }}>Trạng thái xử lý</h3>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                  {Object.entries(overview.processing_status).map(([status, count]) => (
                    <div key={status} style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ textTransform: "capitalize" }}>{status}:</span>
                      <span style={{ fontWeight: "bold" }}>{count}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Processing Stage */}
              <div className="card" style={{ padding: "1.5rem" }}>
                <h3 style={{ margin: "0 0 1rem 0", color: "#374151" }}>Giai đoạn xử lý</h3>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                  {Object.entries(overview.processing_stage).map(([stage, count]) => (
                    <div key={stage} style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ textTransform: "capitalize" }}>{stage}:</span>
                      <span style={{ fontWeight: "bold" }}>{count}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Publication Status */}
              <div className="card" style={{ padding: "1.5rem" }}>
                <h3 style={{ margin: "0 0 1rem 0", color: "#374151" }}>Trạng thái xuất bản</h3>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                  {Object.entries(overview.publication_status).map(([status, count]) => (
                    <div key={status} style={{ display: "flex", justifyContent: "space-between" }}>
                      <span style={{ textTransform: "capitalize" }}>{status}:</span>
                      <span style={{ fontWeight: "bold" }}>{count}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Duplicate Count */}
              <div className="card" style={{ padding: "1.5rem" }}>
                <h3 style={{ margin: "0 0 1rem 0", color: "#374151" }}>Số trùng lặp</h3>
                <div style={{ fontSize: "2rem", fontWeight: "bold", color: "#ef4444" }}>
                  {overview.duplicate_count}
                </div>
              </div>

              {/* Current Admin */}
              <div className="card" style={{ padding: "1.5rem", gridColumn: "span 2" }}>
                <h3 style={{ margin: "0 0 1rem 0", color: "#374151" }}>Admin hiện tại</h3>
                <div style={{ display: "flex", gap: "2rem", alignItems: "center" }}>
                  <div>
                    <strong>Email:</strong> {overview.current_admin.email}
                  </div>
                  <div>
                    <strong>Role:</strong> 
                    <span style={{ 
                      backgroundColor: "#dc2626", 
                      color: "white", 
                      padding: "0.25rem 0.5rem", 
                      borderRadius: "0.25rem",
                      fontSize: "0.875rem"
                    }}>
                      {overview.current_admin.role}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Papers Tab */}
          {activeTab === "papers" && (
            <div className="card">
              <div className="card__header">
                <h2 className="card__title">Danh sách Papers</h2>
                <p className="card__subtitle">
                  Tổng số: {papersTotal} papers (Trang {papersPage}/{Math.ceil(papersTotal/papersPageSize) || 1})
                </p>
              </div>
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ backgroundColor: "#f9fafb" }}>
                      <th style={{ padding: "0.75rem", textAlign: "left", borderBottom: "1px solid #e5e7eb" }}>ID</th>
                      <th style={{ padding: "0.75rem", textAlign: "left", borderBottom: "1px solid #e5e7eb" }}>Filename</th>
                      <th style={{ padding: "0.75rem", textAlign: "left", borderBottom: "1px solid #e5e7eb" }}>Status</th>
                      <th style={{ padding: "0.75rem", textAlign: "left", borderBottom: "1px solid #e5e7eb" }}>Created At</th>
                    </tr>
                  </thead>
                  <tbody>
                    {papers.length === 0 ? (
                      <tr>
                        <td colSpan="4" style={{ padding: "2rem", textAlign: "center", color: "#6b7280" }}>
                          Không có papers nào
                        </td>
                      </tr>
                    ) : (
                      papers.map((paper) => (
                        <tr key={paper.id} style={{ borderBottom: "1px solid #e5e7eb" }}>
                          <td style={{ padding: "0.75rem" }}>{paper.id}</td>
                          <td style={{ padding: "0.75rem" }}>{paper.original_filename || paper.filename}</td>
                          <td style={{ padding: "0.75rem" }}>
                            <span style={{ 
                              backgroundColor: getStatusColor(paper.processing_status),
                              color: "white",
                              padding: "0.25rem 0.5rem",
                              borderRadius: "0.25rem",
                              fontSize: "0.75rem"
                            }}>
                              {paper.processing_status}
                            </span>
                          </td>
                          <td style={{ padding: "0.75rem" }}>
                            {formatDate(paper.created_at)}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
              <Pagination 
                currentPage={papersPage}
                totalPages={Math.ceil(papersTotal/papersPageSize) || 1}
                onPageChange={setPapersPage}
              />
            </div>
          )}

          {/* Canonical Documents Tab */}
          {activeTab === "canonical" && (
            <div className="card">
              <div className="card__header">
                <h2 className="card__title">Danh sách Canonical Documents</h2>
                <p className="card__subtitle">
                  Tổng số: {canonicalTotal} tài liệu chuẩn hóa (Trang {canonicalPage}/{Math.ceil(canonicalTotal/canonicalPageSize) || 1})
                </p>
              </div>
              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ backgroundColor: "#f9fafb" }}>
                      <th style={{ padding: "0.75rem", textAlign: "left", borderBottom: "1px solid #e5e7eb" }}>ID</th>
                      <th style={{ padding: "0.75rem", textAlign: "left", borderBottom: "1px solid #e5e7eb" }}>Canonical Key</th>
                      <th style={{ padding: "0.75rem", textAlign: "left", borderBottom: "1px solid #e5e7eb" }}>Title</th>
                      <th style={{ padding: "0.75rem", textAlign: "left", borderBottom: "1px solid #e5e7eb" }}>Year</th>
                      <th style={{ padding: "0.75rem", textAlign: "left", borderBottom: "1px solid #e5e7eb" }}>Venue</th>
                      <th style={{ padding: "0.75rem", textAlign: "left", borderBottom: "1px solid #e5e7eb" }}>Status</th>
                      <th style={{ padding: "0.75rem", textAlign: "left", borderBottom: "1px solid #e5e7eb" }}>Created At</th>
                    </tr>
                  </thead>
                  <tbody>
                    {canonicalDocuments.length === 0 ? (
                      <tr>
                        <td colSpan="7" style={{ padding: "2rem", textAlign: "center", color: "#6b7280" }}>
                          Không có canonical documents nào
                        </td>
                      </tr>
                    ) : (
                      canonicalDocuments.map((doc) => (
                        <tr key={doc.id} style={{ borderBottom: "1px solid #e5e7eb" }}>
                          <td style={{ padding: "0.75rem" }}>{doc.id.substring(0, 8)}...</td>
                          <td style={{ padding: "0.75rem" }}>
                            <span style={{ fontFamily: "monospace", fontSize: "0.8rem" }}>
                              {doc.canonical_key}
                            </span>
                          </td>
                          <td style={{ padding: "0.75rem" }}>{doc.title}</td>
                          <td style={{ padding: "0.75rem" }}>{doc.publication_year}</td>
                          <td style={{ padding: "0.75rem" }}>{doc.venue}</td>
                          <td style={{ padding: "0.75rem" }}>
                            <span style={{ 
                              backgroundColor: getStatusColor(doc.enrichment_status === "enriched" ? "success" : "info"),
                              color: "white",
                              padding: "0.25rem 0.5rem",
                              borderRadius: "0.25rem",
                              fontSize: "0.75rem"
                            }}>
                              {doc.enrichment_status}
                            </span>
                          </td>
                          <td style={{ padding: "0.75rem" }}>
                            {formatDate(doc.created_at)}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
              <Pagination 
                currentPage={canonicalPage}
                totalPages={Math.ceil(canonicalTotal/canonicalPageSize) || 1}
                onPageChange={setCanonicalPage}
              />
            </div>
          )}

          {/* Activities Tab */}
          {activeTab === "activities" && (
            <div className="card">
              <div className="card__header">
                <h2 className="card__title">Hoạt động hệ thống</h2>
                <p className="card__subtitle">
                  Tổng số: {activitiesTotal} hoạt động (Trang {activitiesPage}/{Math.ceil(activitiesTotal/activitiesPageSize) || 1})
                </p>
              </div>
              <div style={{ maxHeight: "600px", overflowY: "auto" }}>
                {activities.length === 0 ? (
                  <div style={{ padding: "2rem", textAlign: "center", color: "#6b7280" }}>
                    Không có hoạt động nào
                  </div>
                ) : (
                  activities.map((activity) => (
                    <div key={activity.id} style={{ 
                      borderBottom: "1px solid #e5e7eb", 
                      padding: "1rem 0",
                      display: "flex",
                      gap: "1rem",
                      alignItems: "flex-start"
                    }}>
                      {/* Status Indicator */}
                      <div style={{ 
                        width: "4px", 
                        height: "100%", 
                        backgroundColor: getStatusColor(activity.status),
                        borderRadius: "2px",
                        flexShrink: 0
                      }}></div>
                      
                      {/* Activity Content */}
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "0.5rem" }}>
                          <div>
                            <span style={{ 
                              backgroundColor: getStatusColor(activity.status),
                              color: "white",
                              padding: "0.25rem 0.5rem",
                              borderRadius: "0.25rem",
                              fontSize: "0.75rem",
                              fontWeight: "bold"
                            }}>
                              {activity.status_label}
                            </span>
                          </div>
                          <div style={{ fontSize: "0.875rem", color: "#6b7280" }}>
                            {formatDate(activity.created_at)}
                          </div>
                        </div>
                        
                        <div style={{ marginBottom: "0.5rem" }}>
                          <strong>{activity.event_label}</strong>
                        </div>
                        
                        <div style={{ color: "#374151", marginBottom: "0.5rem" }}>
                          {activity.message}
                        </div>
                        
                        <div style={{ display: "flex", gap: "1rem", fontSize: "0.875rem", color: "#6b7280" }}>
                          <span><strong>Actor:</strong> {activity.actor_display}</span>
                          {activity.object_type && (
                            <span><strong>Type:</strong> {activity.object_type}</span>
                          )}
                          {activity.canonical_key && (
                            <span><strong>Key:</strong> 
                              <span style={{ fontFamily: "monospace" }}>{activity.canonical_key}</span>
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
              <Pagination 
                currentPage={activitiesPage}
                totalPages={Math.ceil(activitiesTotal/activitiesPageSize) || 1}
                onPageChange={setActivitiesPage}
              />
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
