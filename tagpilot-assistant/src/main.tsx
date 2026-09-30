import { lazy, StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./index.css";

const InsightPreview = import.meta.env.DEV
  ? lazy(() => import("./insight/InsightPreview"))
  : null;
const showInsightPreview = import.meta.env.DEV && new URLSearchParams(window.location.search).get("insightPreview") === "1";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {showInsightPreview && InsightPreview
      ? <Suspense fallback={<p role="status">正在加载合成洞察预览…</p>}><InsightPreview /></Suspense>
      : <App />}
  </StrictMode>,
);
