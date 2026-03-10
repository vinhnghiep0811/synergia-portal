import { useNavigate } from "react-router-dom";

export function HomeDashboard() {
  const navigate = useNavigate();

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
            <h1 className="app-title">Synergia Portal</h1>
            <p className="app-subtitle">
              Cổng quản lý và chia sẻ tài liệu nghiên cứu cho nhóm.
            </p>
          </div>
        </div>
        <div className="app-header__meta">
          <span className="app-tag">Single workspace · VM on-prem</span>
        </div>
      </header>

      <main className="app-main app-main--home">
        <div className="app-main__left">
          <section
            className="card upload-card home-card"
            style={{ cursor: "pointer" }}
            onClick={() => navigate("/upload")}
          >
            <header className="card__header">
              <div>
                <h2 className="card__title">Upload PDF</h2>
                <p className="card__subtitle">
                  Tải lên paper hoặc báo cáo nghiên cứu mới vào kho tài liệu.
                </p>
              </div>
            </header>
            <p style={{ fontSize: "0.85rem", color: "#4b5563" }}>
              Chuyển đến màn hình upload chi tiết với form chọn file, thông tin
              người upload và workspace.
            </p>
          </section>

          <section className="card stats-card">
            <header className="card__header">
              <div>
                <h2 className="card__title">Thống kê nhanh</h2>
                <p className="card__subtitle">
                  Tổng quan về kho tài liệu của nhóm.
                </p>
              </div>
            </header>
            <div className="stats-grid">
              <div className="stat-item">
                <div className="stat-number">24</div>
                <div className="stat-label">Tổng số tài liệu</div>
              </div>
              <div className="stat-item">
                <div className="stat-number">18</div>
                <div className="stat-label">Đã xử lý</div>
              </div>
              <div className="stat-item">
                <div className="stat-number">4</div>
                <div className="stat-label">Đang chờ</div>
              </div>
              <div className="stat-item">
                <div className="stat-number">2</div>
                <div className="stat-label">Lỗi</div>
              </div>
            </div>
          </section>
        </div>

        <div className="app-main__right">
          <section
            className="card list-card home-card"
            style={{ cursor: "pointer" }}
            onClick={() => navigate("/papers")}
          >
            <header className="card__header">
              <div>
                <h2 className="card__title">Danh sách tài liệu</h2>
                <p className="card__subtitle">
                  Xem tất cả tài liệu đã upload, trạng thái xử lý, và chi tiết
                  canonical/LLM.
                </p>
              </div>
            </header>
            <p style={{ fontSize: "0.85rem", color: "#4b5563" }}>
              Chuyển đến màn hình danh sách + chi tiết paper với filter, badge
              trạng thái và timeline xử lý.
            </p>
          </section>

          <section className="card activity-card">
            <header className="card__header">
              <div>
                <h2 className="card__title">Hoạt động gần đây</h2>
                <p className="card__subtitle">
                  Các tài liệu được thêm gần đây.
                </p>
              </div>
            </header>
            <div className="activity-list">
              <div className="activity-item">
                <div className="activity-dot activity-dot--success"></div>
                <div className="activity-content">
                  <div className="activity-title">Scaling Evidence-Backed Metadata...</div>
                  <div className="activity-time">2 giờ trước</div>
                </div>
              </div>
              <div className="activity-item">
                <div className="activity-dot activity-dot--pending"></div>
                <div className="activity-content">
                  <div className="activity-title">Human-in-the-loop Knowledge...</div>
                  <div className="activity-time">5 giờ trước</div>
                </div>
              </div>
              <div className="activity-item">
                <div className="activity-dot activity-dot--success"></div>
                <div className="activity-content">
                  <div className="activity-title">A Survey on Reference and Citation...</div>
                  <div className="activity-time">1 ngày trước</div>
                </div>
              </div>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
}

