import { useState, useEffect } from "react";
import { getCanonicalDocumentByPaper } from "../services/paperApi.js";

export function CanonicalLink({ paperId }) {
  const [canonicalDoc, setCanonicalDoc] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function loadCanonicalDoc() {
      if (!paperId) return;
      
      try {
        setLoading(true);
        setError(null);
        const doc = await getCanonicalDocumentByPaper(paperId);
        setCanonicalDoc(doc);
      } catch (err) {
        // 404 is expected if paper has no canonical document
        if (err.message?.includes("404") || err.response?.status === 404) {
          setCanonicalDoc(null);
        } else {
          setError(err.message);
        }
      } finally {
        setLoading(false);
      }
    }

    loadCanonicalDoc();
  }, [paperId]);

  if (loading) {
    return <span style={{ fontSize: "0.8rem", color: "#6b7280" }}>...</span>;
  }

  if (error) {
    return <span style={{ fontSize: "0.8rem", color: "#dc2626" }}>Lỗi</span>;
  }

  if (!canonicalDoc) {
    return <span style={{ fontSize: "0.8rem", color: "#6b7280" }}>-</span>;
  }

  return (
    <a
      href={`/canonical/${canonicalDoc.id}`}
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        window.location.href = `/canonical/${canonicalDoc.id}`;
      }}
      style={{
        fontSize: "0.8rem",
        color: "#4f46e5",
        textDecoration: "underline",
        cursor: "pointer"
      }}
    >
      {canonicalDoc.title_candidate || canonicalDoc.title || "Xem"}
    </a>
  );
}
