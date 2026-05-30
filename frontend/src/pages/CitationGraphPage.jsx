import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AppHeader } from "../components/AppHeader.jsx";
import {
  enqueueGlobalCitationRescore,
  getCitationRescoreJobStatus,
  getCitationEdgeMentions,
  getCitationNetwork,
} from "../services/citationApi.js";
import "../styles/CitationGraphPage.css";

const GRAPH_WIDTH = 1240;
const GRAPH_HEIGHT = 720;
const GRAPH_CENTER = { x: GRAPH_WIDTH / 2, y: GRAPH_HEIGHT / 2 };
const ZOOM_MIN = 0.55;
const ZOOM_MAX = 2.6;
const ZOOM_STEP = 0.14;
const DENSE_EDGE_THRESHOLD = 15;

const EDGE_COLORS = {
  low: "#64748b",
  medium: "#f59e0b",
  high: "#0ea5a4",
};

const INTENT_UI = {
  use_method: {
    label: "Use Method",
    tone: "method",
  },
  compare: {
    label: "Compare",
    tone: "compare",
  },
  baseline: {
    label: "Baseline",
    tone: "baseline",
  },
  support: {
    label: "Support",
    tone: "support",
  },
  background: {
    label: "Background",
    tone: "background",
  },
  mention_only: {
    label: "Mention Only",
    tone: "mention",
  },
};

function trimTitle(text, maxLength = 36) {
  if (!text) {
    return "Untitled";
  }
  const normalized = text.trim();
  if (normalized.length <= maxLength) {
    return normalized;
  }
  return `${normalized.slice(0, maxLength - 1)}…`;
}

/** Chia tiêu đề thành tối đa `maxLines` dòng, mỗi dòng tối đa `maxChars` ký tự (ước lượng). */
function splitTitleLines(text, maxChars, maxLines) {
  const base = (text || "").trim() || "Untitled";
  const words = base.split(/\s+/);
  const lines = [];
  let current = "";

  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;
    if (candidate.length <= maxChars) {
      current = candidate;
    } else {
      if (current) {
        lines.push(current);
      }
      current =
        word.length > maxChars ? `${word.slice(0, Math.max(1, maxChars - 1))}…` : word;
      if (lines.length >= maxLines) {
        break;
      }
    }
    if (lines.length >= maxLines) {
      break;
    }
  }

  if (lines.length < maxLines && current) {
    lines.push(current);
  }

  if (!lines.length) {
    return [trimTitle(base, maxChars)];
  }

  if (lines.length > maxLines) {
    return lines.slice(0, maxLines);
  }

  const joined = lines.join(" ");
  if (joined.length < base.length && lines.length === maxLines) {
    const last = lines[maxLines - 1];
    if (last && !last.endsWith("…") && last.length >= maxChars - 2) {
      lines[maxLines - 1] = `${trimTitle(last, maxChars)}`;
    }
  }

  return lines;
}

function toNumber(value) {
  const parsed = Number(value);
  if (Number.isNaN(parsed)) {
    return 0;
  }
  return parsed;
}

function clampValue(value, minValue, maxValue) {
  return Math.min(maxValue, Math.max(minValue, value));
}

function getPointerInViewBox(event, svgElement) {
  if (!svgElement) {
    return null;
  }

  const rect = svgElement.getBoundingClientRect();
  if (!rect.width || !rect.height) {
    return null;
  }

  return {
    x: ((event.clientX - rect.left) / rect.width) * GRAPH_WIDTH,
    y: ((event.clientY - rect.top) / rect.height) * GRAPH_HEIGHT,
  };
}

function applyZoom(view, nextZoom, anchor) {
  const clamped = clampValue(nextZoom, ZOOM_MIN, ZOOM_MAX);
  if (clamped === view.zoom) {
    return view;
  }

  const worldX = (anchor.x - view.panX) / view.zoom;
  const worldY = (anchor.y - view.panY) / view.zoom;
  const panX = anchor.x - worldX * clamped;
  const panY = anchor.y - worldY * clamped;

  return {
    ...view,
    zoom: clamped,
    panX,
    panY,
  };
}

function formatDateTime(value) {
  if (!value) {
    return "n/a";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "n/a";
  }

  return date.toLocaleString("vi-VN", {
    hour12: false,
  });
}

function resolveIntentUi(intentLabel) {
  const normalized = String(intentLabel || "").trim().toLowerCase();
  if (!normalized) {
    return {
      label: "Unknown",
      tone: "unknown",
    };
  }

  const mapped = INTENT_UI[normalized];
  if (mapped) {
    return mapped;
  }

  return {
    label: normalized
      .replaceAll("_", " ")
      .replace(/\b\w/g, (char) => char.toUpperCase()),
    tone: "unknown",
  };
}

function buildLayout(nodes) {
  if (!nodes?.length) {
    return {};
  }

  const n = nodes.length;

  // Một vài case nhỏ để đồ thị nhìn cân hơn
  if (n === 1) {
    return {
      [nodes[0].canonical_document_id]: {
        x: GRAPH_WIDTH / 2,
        y: GRAPH_HEIGHT / 2,
      },
    };
  }

  if (n === 2) {
    const centerY = GRAPH_HEIGHT / 2;
    const offsetX = Math.min(GRAPH_WIDTH, GRAPH_HEIGHT) * 0.22;
    return {
      [nodes[0].canonical_document_id]: {
        x: GRAPH_WIDTH / 2 - offsetX,
        y: centerY,
      },
      [nodes[1].canonical_document_id]: {
        x: GRAPH_WIDTH / 2 + offsetX,
        y: centerY,
      },
    };
  }

  // Từ 3 node trở lên: bố cục dạng lưới phẳng, dễ quét theo hàng/cột
  const sorted = [...nodes].sort(
    (left, right) =>
      right.out_degree + right.in_degree - (left.out_degree + left.in_degree)
  );

  const cols = clampValue(Math.round(Math.sqrt(n)), 3, 7);
  const rows = Math.ceil(n / cols);

  const paddingX = 80;
  const paddingY = 60;

  const usableWidth = GRAPH_WIDTH - paddingX * 2;
  const usableHeight = GRAPH_HEIGHT - paddingY * 2;

  const colStep = cols > 1 ? usableWidth / (cols - 1) : 0;
  const rowStep = rows > 1 ? usableHeight / (rows - 1) : 0;

  const positions = {};

  sorted.forEach((node, index) => {
    const row = Math.floor(index / cols);
    const col = index % cols;
    const x = paddingX + col * colStep;
    const y = paddingY + row * rowStep;

    positions[node.canonical_document_id] = { x, y };
  });

  return positions;
}

function buildFocusedLayout(selectedNodeId, nodes, edges, basePositions) {
  if (!selectedNodeId || !nodes?.length) {
    return basePositions || {};
  }

  const linkedNodeIds = [];
  const linkedSet = new Set();

  (edges || []).forEach((edge) => {
    if (edge.source_canonical_id === selectedNodeId && edge.target_canonical_id !== selectedNodeId) {
      if (!linkedSet.has(edge.target_canonical_id)) {
        linkedSet.add(edge.target_canonical_id);
        linkedNodeIds.push(edge.target_canonical_id);
      }
    }
    if (edge.target_canonical_id === selectedNodeId && edge.source_canonical_id !== selectedNodeId) {
      if (!linkedSet.has(edge.source_canonical_id)) {
        linkedSet.add(edge.source_canonical_id);
        linkedNodeIds.push(edge.source_canonical_id);
      }
    }
  });

  const nodeById = new Map(nodes.map((node) => [node.canonical_document_id, node]));
  const positions = { ...(basePositions || {}) };
  const selectedNode = nodeById.get(selectedNodeId);

  if (!selectedNode) {
    return positions;
  }

  positions[selectedNodeId] = { x: GRAPH_CENTER.x, y: GRAPH_CENTER.y };

  if (!linkedNodeIds.length) {
    return positions;
  }

  linkedNodeIds.sort((leftId, rightId) => {
    const leftNode = nodeById.get(leftId);
    const rightNode = nodeById.get(rightId);
    const leftDegree = (leftNode?.in_degree || 0) + (leftNode?.out_degree || 0);
    const rightDegree = (rightNode?.in_degree || 0) + (rightNode?.out_degree || 0);
    return rightDegree - leftDegree;
  });

  const count = linkedNodeIds.length;
  const ringRadius = clampValue(
    130 + Math.sqrt(count) * 44,
    130,
    Math.min(GRAPH_WIDTH, GRAPH_HEIGHT) * 0.36
  );
  const margin = 66;

  linkedNodeIds.forEach((nodeId, index) => {
    const angle = -Math.PI / 2 + (index * 2 * Math.PI) / count;
    const x = GRAPH_CENTER.x + Math.cos(angle) * ringRadius;
    const y = GRAPH_CENTER.y + Math.sin(angle) * ringRadius;
    positions[nodeId] = {
      x: clampValue(x, margin, GRAPH_WIDTH - margin),
      y: clampValue(y, margin, GRAPH_HEIGHT - margin),
    };
  });

  return positions;
}

function nodeRadius(node) {
  const degree = node.in_degree + node.out_degree;
  return Math.max(10, Math.min(19, 9 + degree * 1.4));
}

function edgePath(source, target, sourceRadius, targetRadius, curveOffset = 0) {
  if (!source || !target) {
    return "";
  }

  const dx = target.x - source.x;
  const dy = target.y - source.y;
  const distance = Math.hypot(dx, dy);

  if (!distance) {
    return "";
  }

  const ux = dx / distance;
  const uy = dy / distance;

  const startX = source.x + ux * sourceRadius;
  const startY = source.y + uy * sourceRadius;
  const endX = target.x - ux * targetRadius;
  const endY = target.y - uy * targetRadius;

  if (!curveOffset) {
    return `M ${startX} ${startY} L ${endX} ${endY}`;
  }

  const mx = (startX + endX) / 2;
  const my = (startY + endY) / 2;
  const nx = -uy;
  const ny = ux;

  const cx = mx + nx * curveOffset;
  const cy = my + ny * curveOffset;

  return `M ${startX} ${startY} Q ${cx} ${cy} ${endX} ${endY}`;
}

export function CitationGraphPage() {
  const navigate = useNavigate();

  const [network, setNetwork] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [minScore, setMinScore] = useState(0.0);
  const [edgeLimit, setEdgeLimit] = useState(300);

  const [selectedEdgeId, setSelectedEdgeId] = useState(null);
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [nodeFocusMode, setNodeFocusMode] = useState(false);
  const [mentions, setMentions] = useState([]);
  const [loadingMentions, setLoadingMentions] = useState(false);
  const [mentionError, setMentionError] = useState("");

  const [rescoreBusy, setRescoreBusy] = useState(false);
  const [rescoreMessage, setRescoreMessage] = useState("");
  const [rescoreError, setRescoreError] = useState("");
  const [rescoreTracking, setRescoreTracking] = useState(false);
  const [rescoreTrackingJobId, setRescoreTrackingJobId] = useState("");
  const [rescoreTrackingMessage, setRescoreTrackingMessage] = useState("");
  const [lastLoadedAt, setLastLoadedAt] = useState(null);
  const [view, setView] = useState({ zoom: 1, panX: 0, panY: 0 });
  const [isPanning, setIsPanning] = useState(false);

  const svgRef = useRef(null);
  const panRef = useRef({ active: false, startX: 0, startY: 0, originX: 0, originY: 0 });

  const loadNetwork = useCallback(async () => {
    try {
      setLoading(true);
      setError("");

      const data = await getCitationNetwork({
        minScore,
        limitEdges: edgeLimit,
        includeAllDocuments: true,
      });

      setNetwork(data);
      setSelectedEdgeId((previousEdgeId) =>
        data.edges?.some((edge) => edge.edge_id === previousEdgeId)
          ? previousEdgeId
          : data.edges?.[0]?.edge_id ?? null
      );
      setLastLoadedAt(new Date().toISOString());
    } catch (fetchError) {
      setError(fetchError.message || "Không thể tải mạng trích dẫn.");
      setNetwork(null);
      setSelectedEdgeId(null);
    } finally {
      setLoading(false);
    }
  }, [edgeLimit, minScore]);

  useEffect(() => {
    loadNetwork();
  }, [loadNetwork]);

  useEffect(() => {
    if (!selectedEdgeId) {
      setMentions([]);
      setMentionError("");
      return;
    }

    let cancelled = false;

    const run = async () => {
      try {
        setLoadingMentions(true);
        setMentionError("");
        const response = await getCitationEdgeMentions(selectedEdgeId, 20);
        if (!cancelled) {
          setMentions(response.items || []);
        }
      } catch (fetchError) {
        if (!cancelled) {
          setMentionError(fetchError.message || "Không thể tải evidence cho cạnh này.");
          setMentions([]);
        }
      } finally {
        if (!cancelled) {
          setLoadingMentions(false);
        }
      }
    };

    run();

    return () => {
      cancelled = true;
    };
  }, [selectedEdgeId]);

  useEffect(() => {
    if (!rescoreTracking || !rescoreTrackingJobId) {
      return undefined;
    }

    let cancelled = false;

    const trackRun = async () => {
      try {
        const jobStatus = await getCitationRescoreJobStatus(rescoreTrackingJobId);
        if (cancelled || !jobStatus) {
          return;
        }

        const normalizedStatus = String(jobStatus.status || "").toLowerCase();

        if (["queued", "deferred", "scheduled"].includes(normalizedStatus)) {
          setRescoreTrackingMessage(
            `Đã enqueue job ${rescoreTrackingJobId}. Đang chờ worker nhận job...`
          );
          return;
        }

        if (["started", "running", "busy"].includes(normalizedStatus)) {
          setRescoreTrackingMessage(
            `Worker đang xử lý job ${rescoreTrackingJobId}. Vui lòng chờ hoàn tất.`
          );
          return;
        }

        if (["finished", "complete", "completed"].includes(normalizedStatus)) {
          setRescoreTracking(false);
          setRescoreTrackingMessage("");
          setRescoreMessage(
            `Global rescore hoàn tất (job: ${rescoreTrackingJobId}). Bấm "Làm mới mạng" để xem dữ liệu mới.`
          );
          return;
        }

        if (["failed", "stopped", "canceled", "cancelled"].includes(normalizedStatus)) {
          setRescoreTracking(false);
          setRescoreTrackingMessage("");
          const detail = jobStatus.error_excerpt ? ` Chi tiết: ${jobStatus.error_excerpt}` : "";
          setRescoreError(
            `Global rescore thất bại (job: ${rescoreTrackingJobId}).${detail}`
          );
          return;
        }

        setRescoreTrackingMessage(
          `Job ${rescoreTrackingJobId} đã được enqueue. Trạng thái hiện tại: ${jobStatus.status}.`
        );
      } catch {
        if (!cancelled) {
          setRescoreTrackingMessage(
            `Đã enqueue job ${rescoreTrackingJobId}. Đang đợi worker cập nhật trạng thái...`
          );
        }
      }
    };

    void trackRun();
    const interval = setInterval(() => {
      void trackRun();
    }, 5000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [rescoreTracking, rescoreTrackingJobId]);

  const zoomPercent = Math.round(view.zoom * 100);
  const viewTransform = `translate(${view.panX} ${view.panY}) scale(${view.zoom})`;

  const baseNodePosition = useMemo(() => buildLayout(network?.nodes || []), [network]);

  const nodeById = useMemo(() => {
    const map = new Map();
    (network?.nodes || []).forEach((node) => {
      map.set(node.canonical_document_id, node);
    });
    return map;
  }, [network]);

  const reversePairs = useMemo(() => {
    const set = new Set();
    (network?.edges || []).forEach((edge) => {
      set.add(`${edge.source_canonical_id}::${edge.target_canonical_id}`);
    });
    return set;
  }, [network]);

  const totalNodes = network?.nodes?.length || 0;
  const shownEdges = network?.edges?.length || 0;
  const hasNodeButNoEdge = totalNodes > 0 && shownEdges === 0;
  const isDenseGraph = shownEdges > DENSE_EDGE_THRESHOLD;

  useEffect(() => {
    if (isDenseGraph) {
      setNodeFocusMode(true);
      return;
    }
    setNodeFocusMode(false);
  }, [isDenseGraph]);

  const filteredEdges = useMemo(() => {
    const allEdges = network?.edges || [];
    if (!allEdges.length) {
      return [];
    }

    if (!nodeFocusMode && !selectedNodeId) {
      return allEdges;
    }

    if (!selectedNodeId) {
      return allEdges;
    }

    return allEdges.filter(
      (edge) =>
        edge.source_canonical_id === selectedNodeId || edge.target_canonical_id === selectedNodeId
    );
  }, [network, nodeFocusMode, selectedNodeId]);

  const visibleNodeIds = useMemo(() => {
    const ids = new Set();
    const allNodes = network?.nodes || [];

    if (!selectedNodeId) {
      allNodes.forEach((node) => ids.add(node.canonical_document_id));
      return ids;
    }

    filteredEdges.forEach((edge) => {
      ids.add(edge.source_canonical_id);
      ids.add(edge.target_canonical_id);
    });
    ids.add(selectedNodeId);
    return ids;
  }, [network, selectedNodeId, filteredEdges]);

  const nodePosition = useMemo(
    () =>
      buildFocusedLayout(
        selectedNodeId,
        network?.nodes || [],
        network?.edges || [],
        baseNodePosition
      ),
    [selectedNodeId, network, baseNodePosition]
  );

  const resetGraphView = useCallback(() => {
    setView({ zoom: 1, panX: 0, panY: 0 });
  }, []);

  const toggleNodeSelection = useCallback(
    (nodeId) => {
      setSelectedNodeId((previousId) => (previousId === nodeId ? null : nodeId));
      resetGraphView();
    },
    [resetGraphView]
  );

  useEffect(() => {
    if (!selectedEdgeId) {
      return;
    }
    const isStillVisible = filteredEdges.some((edge) => edge.edge_id === selectedEdgeId);
    if (!isStillVisible) {
      setSelectedEdgeId(filteredEdges[0]?.edge_id ?? null);
    }
  }, [filteredEdges, selectedEdgeId]);

  useEffect(() => {
    if (!selectedNodeId) {
      return;
    }
    const exists = (network?.nodes || []).some(
      (node) => node.canonical_document_id === selectedNodeId
    );
    if (!exists) {
      setSelectedNodeId(null);
    }
  }, [network, selectedNodeId]);

  const selectedEdge = useMemo(
    () => filteredEdges.find((edge) => edge.edge_id === selectedEdgeId) || null,
    [filteredEdges, selectedEdgeId]
  );

  const handleRescore = async () => {
    try {
      setRescoreBusy(true);
      setRescoreError("");
      setRescoreMessage("");
      setRescoreTrackingMessage("");

      const response = await enqueueGlobalCitationRescore({});
      setRescoreTracking(true);
      setRescoreTrackingJobId(response.queued_job_id);
      setRescoreTrackingMessage(
        `Đã enqueue job ${response.queued_job_id}. Đang chờ worker bắt đầu xử lý...`
      );
      setRescoreMessage(
        `Đã enqueue global rescore (job: ${response.queued_job_id}). Hệ thống đang theo dõi tiến trình và sẽ báo khi hoàn tất.`
      );
    } catch (runError) {
      setRescoreError(runError.message || "Không thể enqueue global rescore.");
    } finally {
      setRescoreBusy(false);
    }
  };

  const handleWheel = useCallback((event) => {
    if (!svgRef.current) {
      return;
    }

    event.preventDefault();
    const anchor = getPointerInViewBox(event, svgRef.current);
    if (!anchor) {
      return;
    }

    const direction = event.deltaY < 0 ? 1 : -1;
    setView((prev) => applyZoom(prev, prev.zoom + direction * ZOOM_STEP, anchor));
  }, []);

  const handlePanStart = (event) => {
    if (!svgRef.current || event.button !== 0) {
      return;
    }

    if (event.target !== svgRef.current) {
      return;
    }

    event.preventDefault();
    panRef.current = {
      active: true,
      startX: event.clientX,
      startY: event.clientY,
      originX: view.panX,
      originY: view.panY,
    };
    setIsPanning(true);
  };

  const handlePanMove = (event) => {
    if (!svgRef.current || !panRef.current.active) {
      return;
    }

    const rect = svgRef.current.getBoundingClientRect();
    const scaleX = rect.width ? GRAPH_WIDTH / rect.width : 1;
    const scaleY = rect.height ? GRAPH_HEIGHT / rect.height : 1;
    const dx = (event.clientX - panRef.current.startX) * scaleX;
    const dy = (event.clientY - panRef.current.startY) * scaleY;

    setView((prev) => ({
      ...prev,
      panX: panRef.current.originX + dx,
      panY: panRef.current.originY + dy,
    }));
  };

  const handlePanEnd = () => {
    if (!panRef.current.active) {
      return;
    }

    panRef.current.active = false;
    setIsPanning(false);
  };

  const handleZoomIn = () => {
    setView((prev) => applyZoom(prev, prev.zoom + ZOOM_STEP, GRAPH_CENTER));
  };

  const handleZoomOut = () => {
    setView((prev) => applyZoom(prev, prev.zoom - ZOOM_STEP, GRAPH_CENTER));
  };

  const handleZoomReset = () => {
    resetGraphView();
  };

  const handleZoomSlider = (event) => {
    const nextZoom = Number(event.target.value);
    if (Number.isNaN(nextZoom)) {
      return;
    }
    setView((prev) => applyZoom(prev, nextZoom, GRAPH_CENTER));
  };

  return (
    <div className="app-shell">
      <AppHeader
        title="Mạng lưới trích dẫn"
        subtitle="Mạng trích dẫn giữa các canonical document với mũi tên thể hiện hướng source tới target."
        showUploadButton={false}
        extraAction={
          <button className="btn btn--secondary" onClick={() => navigate("/papers")}>
            Quay lại danh sách tài liệu
          </button>
        }
      />

      <main className="app-main app-main--papers">
        <div className="app-main__full">
          <section className="card">
  <div className="card__header card__header--with-actions">
    <div>
      <h2 className="card__title">Bảng điều khiển mạng trích dẫn</h2>
      <p className="card__subtitle">
        Điều chỉnh ngưỡng và giới hạn cạnh • Thực hiện Global Rescore
      </p>
    </div>
  </div>

  <div className="citation-controls">
    <div className="citation-control-group">
      <label className="form-label">
        Điểm cạnh tối thiểu
        <input
          type="number"
          min="0"
          max="1"
          step="0.05"
          value={minScore}
          onChange={(event) => setMinScore(Math.max(0, Math.min(1, toNumber(event.target.value))))}
          className="citation-input"
        />
      </label>

      <label className="form-label">
        Số cạnh tối đa
        <select
          value={edgeLimit}
          onChange={(event) => setEdgeLimit(Number(event.target.value) || 300)}
          className="citation-select"
        >
          <option value={120}>120 cạnh</option>
          <option value={200}>200 cạnh</option>
          <option value={300}>300 cạnh</option>
          <option value={500}>500 cạnh</option>
          <option value={800}>800 cạnh</option>
        </select>
      </label>
    </div>

    <div className="citation-controls__actions">
      <button 
        className="btn btn--secondary" 
        onClick={() => loadNetwork()} 
        disabled={loading}
      >
        {loading ? "Đang tải..." : "⟳ Làm mới mạng"}
      </button>
      
      <button
        className="btn btn--primary"
        onClick={handleRescore}
        disabled={rescoreBusy || rescoreTracking}
      >
        {rescoreBusy
          ? "Đang enqueue..."
          : rescoreTracking
            ? "Đang chạy rescore..."
            : "🚀 Global Rescore"}
      </button>
    </div>
  </div>

  {/* Last updated */}
  <div className="citation-last-updated">
    Dữ liệu cập nhật lần cuối: <strong>{formatDateTime(lastLoadedAt)}</strong>
  </div>

  {/* Messages */}
  {rescoreMessage && (
    <div className="citation-notice">{rescoreMessage}</div>
  )}
  
  {rescoreTracking && rescoreTrackingMessage && (
    <div className="citation-notice citation-notice--pending">
      {rescoreTrackingMessage}
    </div>
  )}
  
  {rescoreError && (
    <div className="citation-notice citation-notice--error">{rescoreError}</div>
  )}
  
  {error && (
    <div className="citation-notice citation-notice--error">{error}</div>
  )}
</section>

          <section className="citation-layout">
            <article className="card">
              <div className="card__header">
                <div>
                  <h3 className="card__title">Bản đồ trích dẫn</h3>
                  <p className="card__subtitle">
                    Click vào cạnh để xem điểm số và evidence chi tiết.
                  </p>
                </div>
              </div>

              <div className="citation-graph-toolbar">
                <div className="citation-graph-toolbar__hint">
                  Kéo nền để di chuyển, lăn chuột để phóng to / thu nhỏ, click node để lọc liên kết.
                </div>
                <div className="citation-graph-toolbar__controls">
                  <span className="citation-chip">Node: {totalNodes}</span>
                  <span className="citation-chip">Cạnh: {filteredEdges.length}/{shownEdges}</span>
                  <button
                    type="button"
                    className={`btn btn--secondary citation-toggle ${nodeFocusMode ? "citation-toggle--active" : ""}`}
                    onClick={() => {
                      setNodeFocusMode((prev) => !prev);
                      setSelectedNodeId(null);
                      resetGraphView();
                    }}
                  >
                    {nodeFocusMode ? "Đang lọc theo node" : "Đang lọc theo node"}
                  </button>
                  {nodeFocusMode && selectedNodeId ? (
                    <button
                      type="button"
                      className="btn btn--secondary citation-toggle"
                      onClick={() => {
                        setSelectedNodeId(null);
                        resetGraphView();
                      }}
                    >
                      Bỏ chọn node
                    </button>
                  ) : null}
                  <button
                    type="button"
                    className="btn btn--secondary btn--icon"
                    onClick={handleZoomOut}
                    disabled={view.zoom <= ZOOM_MIN + 0.01}
                    aria-label="Thu nhỏ"
                  >
                    −
                  </button>
                  <input
                    type="range"
                    min={ZOOM_MIN}
                    max={ZOOM_MAX}
                    step="0.01"
                    value={view.zoom}
                    onChange={handleZoomSlider}
                    aria-label="Mức zoom"
                  />
                  <button
                    type="button"
                    className="btn btn--secondary btn--icon"
                    onClick={handleZoomIn}
                    disabled={view.zoom >= ZOOM_MAX - 0.01}
                    aria-label="Phóng to"
                  >
                    +
                  </button>
                  <button
                    type="button"
                    className="btn btn--secondary"
                    onClick={handleZoomReset}
                  >
                    Reset
                  </button>
                  <span className="citation-graph-toolbar__value">{zoomPercent}%</span>
                </div>
              </div>

              {loading ? (
                <div className="citation-empty">Đang tải dữ liệu mạng trích dẫn...</div>
              ) : !network?.nodes?.length ? (
                <div className="citation-empty">Chưa có tài liệu nào để hiển thị trên mạng trích dẫn.</div>
              ) : (
                <>
                  {hasNodeButNoEdge ? (
                    <div className="citation-notice citation-notice--pending">
                      Hiện có {totalNodes} tài liệu nhưng chưa có cạnh trích dẫn nào theo bộ lọc hiện tại.
                      Hãy giảm “Điểm cạnh tối thiểu” hoặc tăng “Số cạnh tối đa” để xem thêm liên kết.
                    </div>
                  ) : null}
                  {nodeFocusMode && !selectedNodeId && shownEdges > 0 ? (
                    <div className="citation-notice citation-notice--pending">
                      Mạng có rất nhiều liên kết ({shownEdges} cạnh). Chọn một node để chỉ xem các cạnh liên quan, dễ theo dõi hướng trích dẫn hơn.
                    </div>
                  ) : null}
                  <div className="citation-graph-wrap">
                    <svg
                      ref={svgRef}
                      className={`citation-graph-svg ${isPanning ? "citation-graph-svg--panning" : ""}`}
                      viewBox={`0 0 ${GRAPH_WIDTH} ${GRAPH_HEIGHT}`}
                      role="img"
                      aria-label="Citation network graph"
                      onWheel={handleWheel}
                      onMouseDown={handlePanStart}
                      onMouseMove={handlePanMove}
                      onMouseUp={handlePanEnd}
                      onMouseLeave={handlePanEnd}
                    >
                     <defs>
                    {["low", "medium", "high"].map((level) => (
                      <marker
                        key={level}
                        id={`citation-arrow-${level}`}
                        viewBox="0 0 14 14"
                        markerWidth="10"
                        markerHeight="10"
                        refX="11"
                        refY="7"
                        orient="auto-start-reverse"
                        markerUnits="userSpaceOnUse"
                        overflow="visible"
                      >
                        <path
                          d="
                            M1,1
                            L11,7
                            L1,13
                            Q4,7 1,1
                          "
                          fill={EDGE_COLORS[level]}
                          stroke={EDGE_COLORS[level]}
                          strokeWidth="0.6"
                          strokeLinejoin="round"
                        />
                      </marker>
                    ))}

                    {/* selected arrow */}
                    <marker
                      id="citation-arrow-selected"
                      viewBox="0 0 14 14"
                      markerWidth="12"
                      markerHeight="12"
                      refX="11"
                      refY="7"
                      orient="auto-start-reverse"
                      markerUnits="userSpaceOnUse"
                    >
                      <path
                        d="
                          M1,1
                          L11,7
                          L1,13
                          Q4,7 1,1
                        "
                        fill="#2563eb"
                        stroke="#ffffff"
                        strokeWidth="1"
                      />
                    </marker>
                  </defs>

                      <g className="citation-graph-layer" transform={viewTransform}>
                        {filteredEdges.map((edge) => {
                          const source = nodePosition[edge.source_canonical_id];
                          const target = nodePosition[edge.target_canonical_id];

                          if (!source || !target) {
                            return null;
                          }

                          const sourceNode = nodeById.get(edge.source_canonical_id);
                          const targetNode = nodeById.get(edge.target_canonical_id);
                          const sourceRadius = nodeRadius(sourceNode);
                          const targetRadius = nodeRadius(targetNode);

                          const hasReverse = reversePairs.has(
                            `${edge.target_canonical_id}::${edge.source_canonical_id}`
                          );
                          const curveOffset = hasReverse
                            ? edge.source_canonical_id < edge.target_canonical_id
                              ? 28
                              : -28
                            : 0;

                          const path = edgePath(
                            source,
                            target,
                            sourceRadius,
                            targetRadius,
                            curveOffset
                          );

                          if (!path) {
                            return null;
                          }

                          const isSelected = edge.edge_id === selectedEdgeId;
                          const isConnectedToSelected =
                            !selectedEdge ||
                            isSelected ||
                            selectedEdge.source_canonical_id === edge.source_canonical_id ||
                            selectedEdge.source_canonical_id === edge.target_canonical_id ||
                            selectedEdge.target_canonical_id === edge.source_canonical_id ||
                            selectedEdge.target_canonical_id === edge.target_canonical_id;
                          const score = Number(edge.citation_score ?? 0);

                          return (
                            <g key={edge.edge_id}>
                              <path
                                d={path}
                                stroke="transparent"
                                strokeWidth="14"
                                fill="none"
                                onClick={() => setSelectedEdgeId(edge.edge_id)}
                              />
                              <path
                                d={path}
                                className={`citation-edge citation-edge--${edge.score_band || "low"} ${
                                  isSelected ? "citation-edge--selected" : ""
                                } ${!isConnectedToSelected ? "citation-edge--dim" : ""}`}
                                strokeWidth={isSelected ? 3.2 : 1.2 + score * 2.2}
                                markerEnd={`url(#citation-arrow-${edge.score_band || "low"})`}
                                onClick={() => setSelectedEdgeId(edge.edge_id)}
                              />
                            </g>
                          );
                        })}

                        {(network.nodes || []).map((node) => {
                          const position = nodePosition[node.canonical_document_id];
                          if (!position) {
                            return null;
                          }
                          if (!visibleNodeIds.has(node.canonical_document_id)) {
                            return null;
                          }

                          const radius = nodeRadius(node);
                          const isActive =
                            node.canonical_document_id === selectedNodeId ||
                            (selectedEdge &&
                              (selectedEdge.source_canonical_id === node.canonical_document_id ||
                                selectedEdge.target_canonical_id === node.canonical_document_id));

                          return (
                            <g
                              key={node.canonical_document_id}
                              className={`citation-node ${
                                isActive ? "citation-node--active" : ""
                              } ${selectedEdge && !isActive ? "citation-node--dim" : ""}`}
                              transform={`translate(${position.x}, ${position.y})`}
                              onClick={() => toggleNodeSelection(node.canonical_document_id)}
                            >
                              <circle r={radius} />
                              {(() => {
                                const lines = splitTitleLines(node.title, 20, 2);
                                const lineHeight = 13;
                                const labelPaddingX = 6;
                                const labelPaddingY = 4;
                                const textWidth = Math.max(
                                  28,
                                  ...lines.map((line) => Math.min(160, line.length * 6.1))
                                );
                                const labelX = radius + 7;
                                const labelY = -lineHeight + 1;
                                const boxHeight = lines.length * lineHeight + labelPaddingY * 2 - 2;
                                const boxWidth = textWidth + labelPaddingX * 2;
                                return (
                                  <>
                                    <rect
                                      className="citation-node__label-bg"
                                      x={labelX - labelPaddingX}
                                      y={labelY - labelPaddingY}
                                      width={boxWidth}
                                      height={boxHeight}
                                      rx="6"
                                      ry="6"
                                    />
                                    <text className="citation-node__label" x={labelX} y={labelY + lineHeight - 1}>
                                      {lines.map((line, lineIndex) => (
                                        <tspan key={`${node.canonical_document_id}-${lineIndex}`} x={labelX} dy={lineIndex === 0 ? 0 : lineHeight}>
                                          {line}
                                        </tspan>
                                      ))}
                                    </text>
                                  </>
                                );
                              })()}
                            </g>
                          );
                        })}
                      </g>
                    </svg>
                  </div>

                  <div className="citation-legend">
                    <span className="citation-legend__line">
                      <span className="citation-legend__swatch" style={{ backgroundColor: EDGE_COLORS.low }} />
                      Điểm thấp
                    </span>
                    <span className="citation-legend__line">
                      <span className="citation-legend__swatch" style={{ backgroundColor: EDGE_COLORS.medium }} />
                      Điểm trung bình
                    </span>
                    <span className="citation-legend__line">
                      <span className="citation-legend__swatch" style={{ backgroundColor: EDGE_COLORS.high }} />
                      Điểm cao
                    </span>
                    <span>Mũi tên thể hiện hướng source -&gt; target</span>
                    <span>Click node để lọc các cạnh liên quan</span>
                  </div>
                </>
              )}
            </article>

            <aside className="card">
              <div className="card__header">
                <div>
                  <h3 className="card__title">Thông tin mạng</h3>
                  <p className="card__subtitle">Run hiện tại và chi tiết cạnh được chọn.</p>
                </div>
              </div>

              {network?.run ? (
                <>
                  <div className="citation-summary">
                    <div className="citation-stat">
                      <div className="citation-stat__label">Run ID</div>
                      <div className="citation-stat__value">{network.run.id.slice(0, 8)}...</div>
                    </div>
                    <div className="citation-stat">
                      <div className="citation-stat__label">Version</div>
                      <div className="citation-stat__value">{network.run.algorithm_version}</div>
                    </div>
                    <div className="citation-stat">
                      <div className="citation-stat__label">Số node</div>
                      <div className="citation-stat__value">{network.total_nodes}</div>
                    </div>
                    <div className="citation-stat">
                      <div className="citation-stat__label">Số cạnh</div>
                      <div className="citation-stat__value">{network.total_edges}</div>
                    </div>
                    <div className="citation-stat">
                      <div className="citation-stat__label">Mentions đã xử lý</div>
                      <div className="citation-stat__value">{network.run.processed_mentions}</div>
                    </div>
                    <div className="citation-stat">
                      <div className="citation-stat__label">Edges đã xử lý</div>
                      <div className="citation-stat__value">{network.run.processed_edges}</div>
                    </div>
                  </div>

                  <div className="citation-stat" style={{ marginTop: "0.6rem" }}>
                    <div className="citation-stat__label">Run kết thúc lúc</div>
                    <div className="citation-stat__value" style={{ fontSize: "0.84rem" }}>
                      {formatDateTime(network.run.ended_at)}
                    </div>
                  </div>

                  <div className="citation-edge-list-box">
                    <div className="citation-edge-list-box__head">
                      Danh sách cạnh ({filteredEdges.length}/{shownEdges})
                    </div>
                    <div className="citation-edge-list" role="list" aria-label="Danh sách cạnh trích dẫn">
                      {filteredEdges.map((edge) => (
                        <div
                          key={edge.edge_id}
                          className={`citation-edge-item ${
                            edge.edge_id === selectedEdgeId ? "citation-edge-item--active" : ""
                          }`}
                          onClick={() => setSelectedEdgeId(edge.edge_id)}
                        >
                          <div className="citation-edge-item__title">
                            {trimTitle(edge.source_title, 28)}{" -> "}{trimTitle(edge.target_title, 28)}
                          </div>
                          <div className="citation-edge-item__meta">
                            score {Number(edge.citation_score).toFixed(4)} | mentions {edge.mention_count}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {selectedEdge && (
                    <div style={{ marginTop: "0.8rem" }}>
                      <h4 className="detail-section__title" style={{ marginBottom: "0.4rem" }}>
                        Chi tiết cạnh đang chọn
                      </h4>
                      <div className="citation-stat" style={{ marginBottom: "0.5rem" }}>
                        <div className="citation-stat__label">Nguồn -&gt; Đích</div>
                        <div className="citation-stat__value" style={{ fontSize: "0.84rem" }}>
                          {trimTitle(selectedEdge.source_title, 45)}{" -> "}{trimTitle(selectedEdge.target_title, 45)}
                        </div>
                      </div>
                      <div className="citation-stat" style={{ marginBottom: "0.5rem" }}>
                        <div className="citation-stat__label">Citation score</div>
                        <div className="citation-stat__value">
                          {Number(selectedEdge.citation_score).toFixed(4)} ({selectedEdge.score_band || "n/a"})
                        </div>
                      </div>

                      {loadingMentions ? (
                        <div className="citation-empty">Đang tải evidence...</div>
                      ) : mentionError ? (
                        <div className="citation-notice citation-notice--error">{mentionError}</div>
                      ) : mentions.length ? (
                        <div className="citation-mention-list">
                          {mentions.map((mention) => {
                            const intentUi = resolveIntentUi(mention.intent_label);
                            return (
                              <div className="citation-mention" key={mention.id}>
                                <div className="citation-mention__head">
                                  <span className="citation-mention__anchor">
                                    {mention.anchor_text || "(no anchor)"}
                                  </span>
                                  <span className="citation-mention__score">
                                    m={Number(mention.mention_score).toFixed(4)}
                                  </span>
                                </div>

                                <div className="citation-mention__meta">
                                  <span
                                    className={`citation-intent-badge citation-intent-badge--${intentUi.tone}`}
                                  >
                                    Intent: {intentUi.label}
                                  </span>
                                  <span className="citation-mention__intent-score">
                                    Intent Score: {Number(mention.intent_score).toFixed(4)}
                                  </span>
                                </div>

                                <div className="citation-mention__snippet">{mention.context_snippet}</div>
                              </div>
                            );
                          })}
                        </div>
                      ) : (
                        <div className="citation-empty">Cạnh này chưa có evidence nội bộ.</div>
                      )}
                    </div>
                  )}
                </>
              ) : (
                <div className="citation-empty">Chưa có run hoàn tất để dựng citation network.</div>
              )}
            </aside>
          </section>
        </div>
      </main>
    </div>
  );
}
