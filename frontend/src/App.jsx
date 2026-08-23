import { useState, useEffect } from "react";
import "./App.css";

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

function App() {
  const [repositoryUrl, setRepositoryUrl] = useState(
    "https://github.com/psf/requests.git"
  );
  const [repositoryName, setRepositoryName] = useState("requests");
  const [targetSearch, setTargetSearch] = useState("close");
  const [targets, setTargets] = useState([]);
  const [selectedTarget, setSelectedTarget] = useState(null);
  const [question, setQuestion] = useState(
    "What happens if Response.close is changed?"
  );

  const [ragMode, setRagMode] = useState("rag"); // "rag", "non_rag", "compare"
  const [selectedModel, setSelectedModel] = useState("codellama:7b");

  const [analysis, setAnalysis] = useState(null);
  const [compareResult, setCompareResult] = useState(null);
  const [loadingTargets, setLoadingTargets] = useState(false);
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);
  const [indexing, setIndexing] = useState(false);
  const [indexStatus, setIndexStatus] = useState("");
  const [apiHealth, setApiHealth] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${API_BASE}/health`)
      .then((res) => res.json())
      .then((data) => setApiHealth(data))
      .catch(() => setApiHealth({ status: "disconnected" }));
  }, []);

  async function triggerIndexing() {
    setError("");
    setIndexing(true);
    setIndexStatus("");
    try {
      const res = await fetch(`${API_BASE}/repositories/index`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repository_url: repositoryUrl,
          repository_name: repositoryName,
          force_reindex: true,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Indexing failed.");
      setIndexStatus(`✓ Indexed ${data.chunk_count} code chunks`);
    } catch (err) {
      setError(err.message);
    } finally {
      setIndexing(false);
    }
  }

  async function discoverTargets() {
    setError("");
    setLoadingTargets(true);
    setTargets([]);
    setSelectedTarget(null);
    setAnalysis(null);
    setCompareResult(null);

    try {
      const params = new URLSearchParams({
        repository_url: repositoryUrl,
        repository_name: repositoryName,
        search: targetSearch.trim(),
        limit: "50",
      });

      const response = await fetch(
        `${API_BASE}/repositories/targets?${params.toString()}`
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Target discovery failed.");
      }

      setTargets(data.targets || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingTargets(false);
    }
  }

  async function runAnalysis() {
    if (!selectedTarget) {
      setError("Select a target first.");
      return;
    }

    setError("");
    setLoadingAnalysis(true);
    setAnalysis(null);
    setCompareResult(null);

    try {
      if (ragMode === "compare") {
        const response = await fetch(`${API_BASE}/repositories/rag-compare`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            repository_url: repositoryUrl,
            repository_name: repositoryName,
            target_id: selectedTarget.id,
            question,
            max_depth: 6,
            top_k_chunks: 5,
            model: selectedModel,
          }),
        });

        const data = await response.json();
        if (!response.ok) {
          throw new Error(
            data.detail?.message || data.detail || "Comparison analysis failed."
          );
        }
        setCompareResult(data);
      } else {
        const response = await fetch(
          `${API_BASE}/repositories/engineering-analysis`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              repository_url: repositoryUrl,
              repository_name: repositoryName,
              target_id: selectedTarget.id,
              question,
              max_depth: 6,
              top_k: 10,
              use_rag: ragMode === "rag",
              model: selectedModel,
              top_k_chunks: 5,
            }),
          }
        );

        const data = await response.json();
        if (!response.ok) {
          throw new Error(
            data.detail?.message ||
              data.detail ||
              "Engineering analysis failed."
          );
        }
        setAnalysis(data);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingAnalysis(false);
    }
  }

  const activeData = analysis || compareResult;
  const summary = activeData?.summary;
  const chunks =
    analysis?.rag_chunks?.chunks || compareResult?.rag_chunks?.chunks || [];

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">R</div>
          <div>
            <h1>RepoTwin</h1>
            <span>Code Intelligence & RAG Analysis</span>
          </div>
        </div>

        <div className="status-indicators">
          <div className="status">
            <span
              className={`status-dot ${
                apiHealth?.status === "healthy" ? "online" : "offline"
              }`}
            />
            {apiHealth?.status === "healthy" ? "API Online" : "API Offline"}
          </div>

          <div className="status status-ollama">
            <span
              className={`status-dot ${
                apiHealth?.ollama?.available ? "online" : "neutral"
              }`}
            />
            Ollama:{" "}
            {apiHealth?.ollama?.available ? "Connected" : "Not connected"}
          </div>
        </div>
      </header>

      <main className="container">
        <section className="hero-section">
          <div>
            <p className="eyebrow">EXERCISES 1–5: KNOWLEDGE BASE + VECTOR RAG + CODE LLAMA</p>
            <h2>
              Evidence-Grounded Code Intelligence
            </h2>
            <p className="hero-copy">
              Combines AST-driven code chunking, vector similarity retrieval,
              authoritative deterministic call-graphs, and Code Llama reasoning.
            </p>
          </div>
        </section>

        {/* 01. Connect Repository */}
        <section className="panel repository-panel">
          <div className="panel-heading">
            <div>
              <p className="section-label">01 · REPOSITORY & KNOWLEDGE BASE</p>
              <h3>Connect & Index Repository</h3>
            </div>
            <div className="action-buttons">
              <button
                className="secondary-button"
                onClick={triggerIndexing}
                disabled={indexing}
              >
                {indexing ? "Indexing chunks..." : "Build Vector Index"}
              </button>
              {indexStatus && <span className="index-badge">{indexStatus}</span>}
            </div>
          </div>

          <div className="form-grid">
            <label>
              <span>GitHub repository URL</span>
              <input
                value={repositoryUrl}
                onChange={(e) => setRepositoryUrl(e.target.value)}
                placeholder="https://github.com/owner/repository.git"
              />
            </label>

            <label>
              <span>Repository name</span>
              <input
                value={repositoryName}
                onChange={(e) => setRepositoryName(e.target.value)}
                placeholder="repository"
              />
            </label>
          </div>

          <div className="target-search">
            <label>
              <span>Search code entities</span>
              <input
                value={targetSearch}
                onChange={(e) => setTargetSearch(e.target.value)}
                placeholder="close, Response, Session, include_router..."
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    discoverTargets();
                  }
                }}
              />
            </label>

            <button
              className="primary-button"
              onClick={discoverTargets}
              disabled={loadingTargets}
            >
              {loadingTargets ? "Discovering..." : "Discover targets"}
            </button>
          </div>
        </section>

        {/* 02. Target Selection */}
        {targets.length > 0 && (
          <section className="panel">
            <div className="panel-heading">
              <div>
                <p className="section-label">02 · TARGET SELECTION</p>
                <h3>Select a code entity</h3>
              </div>
              <span className="result-count">{targets.length} found</span>
            </div>

            <div className="target-list">
              {targets.map((target) => (
                <button
                  key={target.id}
                  className={`target-card ${
                    selectedTarget?.id === target.id ? "selected" : ""
                  }`}
                  onClick={() => {
                    setSelectedTarget(target);
                    setAnalysis(null);
                    setCompareResult(null);
                  }}
                >
                  <div className="target-icon">
                    {target.type === "method"
                      ? "M"
                      : target.type === "class"
                      ? "C"
                      : "F"}
                  </div>

                  <div className="target-info">
                    <strong>
                      {target.type === "method"
                        ? target.id.split(":").pop()
                        : target.name}
                    </strong>
                    <span>{target.file}</span>
                    <small>{target.type}</small>
                  </div>

                  <div className="target-arrow">→</div>
                </button>
              ))}
            </div>
          </section>
        )}

        {/* 03. Engineering Question & RAG Settings */}
        {selectedTarget && (
          <section className="panel question-panel">
            <div className="panel-heading">
              <div>
                <p className="section-label">03 · RAG CONFIGURATION & QUESTION</p>
                <h3>
                  Analyze <code>{selectedTarget.name}</code>
                </h3>
              </div>
            </div>

            <div className="selected-target">
              <span>{selectedTarget.type}</span>
              <strong>{selectedTarget.id}</strong>
            </div>

            <div className="rag-controls-grid">
              <div className="control-group">
                <label className="control-label">RAG Mode</label>
                <div className="button-group">
                  <button
                    type="button"
                    className={`toggle-btn ${ragMode === "rag" ? "active" : ""}`}
                    onClick={() => setRagMode("rag")}
                  >
                    With RAG (Grounded)
                  </button>
                  <button
                    type="button"
                    className={`toggle-btn ${ragMode === "non_rag" ? "active" : ""}`}
                    onClick={() => setRagMode("non_rag")}
                  >
                    Without RAG (General LLM)
                  </button>
                  <button
                    type="button"
                    className={`toggle-btn ${ragMode === "compare" ? "active" : ""}`}
                    onClick={() => setRagMode("compare")}
                  >
                    Compare Side-by-Side
                  </button>
                </div>
              </div>

              <div className="control-group">
                <label className="control-label">Model Selection</label>
                <select
                  className="model-select"
                  value={selectedModel}
                  onChange={(e) => setSelectedModel(e.target.value)}
                >
                  <option value="codellama:7b">Code Llama (codellama:7b) [Required]</option>
                  <option value="qwen2.5-coder:1.5b">Qwen (qwen2.5-coder:1.5b) [Optional]</option>
                </select>
              </div>
            </div>

            <label className="question-input-label">
              <span>Engineering Question</span>
              <textarea
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                rows="3"
                placeholder="e.g. What happens if this entity is modified?"
              />
            </label>

            <button
              className="primary-button analyze-button"
              onClick={runAnalysis}
              disabled={loadingAnalysis}
            >
              {loadingAnalysis
                ? "Running Orchestration & Analysis..."
                : ragMode === "compare"
                ? "Run RAG vs Non-RAG Comparison →"
                : "Run Engineering Analysis →"}
            </button>
          </section>
        )}

        {error && (
          <div className="error-box">
            <strong>Analysis Error</strong>
            <span>{error}</span>
          </div>
        )}

        {/* 04. Deterministic Authoritative Metrics */}
        {activeData && (
          <>
            <section className="results-header">
              <div>
                <p className="section-label">04 · AUTHORITATIVE DETERMINISTIC IMPACT</p>
                <h3>Deterministic Repository Metrics</h3>
              </div>
              <div className="validation-badge">
                <span>✓</span>
                Deterministic Graph Verified
              </div>
            </section>

            <section className="metrics-grid">
              <Metric
                label="Production Impact"
                value={summary?.production_impact}
              />
              <Metric
                label="Direct Callers"
                value={summary?.direct_callers}
              />
              <Metric
                label="Indirect Callers"
                value={summary?.indirect_callers}
              />
              <Metric
                label="Affected Tests"
                value={summary?.affected_tests}
              />
              <Metric
                label="Risk Score"
                value={summary?.risk_score}
                danger
              />
              <Metric
                label="Risk Level"
                value={summary?.risk_level}
                danger
              />
            </section>

            {/* 05. Retrieved Code Chunks Panel (Knowledge Base & Vector Similarity) */}
            {chunks.length > 0 && (
              <section className="panel chunks-panel">
                <div className="panel-heading">
                  <div>
                    <p className="section-label">VECTOR SEARCH & KNOWLEDGE BASE</p>
                    <h3>Retrieved AST Code Chunks ({chunks.length})</h3>
                  </div>
                  <span className="kb-badge">Real Cosine Similarity</span>
                </div>

                <div className="chunks-list">
                  {chunks.map((chunk, idx) => (
                    <div className="chunk-card" key={idx}>
                      <div className="chunk-header">
                        <div className="chunk-title">
                          <span className="chunk-type">{chunk.type}</span>
                          <strong>{chunk.name}</strong>
                          <span className="chunk-file">
                            {chunk.file}:{chunk.start_line}-{chunk.end_line}
                          </span>
                        </div>
                        <div className="chunk-score">
                          Similarity:{" "}
                          <strong>
                            {(
                              (chunk.similarity_score ?? 0) * 100
                            ).toFixed(1)}
                            %
                          </strong>
                        </div>
                      </div>
                      <pre className="chunk-code">
                        <code>{chunk.source_code || chunk.text}</code>
                      </pre>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* 06. Side-by-Side Comparison Mode */}
            {compareResult && (
              <section className="compare-grid">
                <div className="panel compare-card">
                  <div className="panel-heading">
                    <div>
                      <p className="section-label">WITH RAG</p>
                      <h3>Evidence-Grounded Reasoning</h3>
                    </div>
                    <ValidationBadge
                      validation={compareResult.with_rag?.validation}
                    />
                  </div>
                  <div className="answer-box">
                    <p className="answer-text">
                      {compareResult.with_rag?.answer}
                    </p>
                  </div>
                  {compareResult.with_rag?.error && (
                    <small className="error-note">
                      {compareResult.with_rag.error}
                    </small>
                  )}
                </div>

                <div className="panel compare-card">
                  <div className="panel-heading">
                    <div>
                      <p className="section-label">WITHOUT RAG</p>
                      <h3>Ungrounded General Model</h3>
                    </div>
                    <ValidationBadge
                      validation={compareResult.without_rag?.validation}
                    />
                  </div>
                  <div className="answer-box">
                    <p className="answer-text">
                      {compareResult.without_rag?.answer}
                    </p>
                  </div>
                  {compareResult.without_rag?.error && (
                    <small className="error-note">
                      {compareResult.without_rag.error}
                    </small>
                  )}
                </div>
              </section>
            )}

            {/* 07. Single Mode AI Explanation */}
            {analysis && (
              <section className="panel ai-panel">
                <div className="panel-heading">
                  <div>
                    <p className="section-label">
                      {analysis.use_rag
                        ? "RAG EVIDENCE-GROUNDED REASONING"
                        : "NON-RAG GENERAL ANALYSIS"}
                    </p>
                    <h3>AI Engineering Analysis</h3>
                  </div>
                  <div className="panel-meta">
                    <span className="model-label">
                      Model: {analysis.ai_analysis?.model}
                    </span>
                    <ValidationBadge
                      validation={analysis.ai_analysis?.validation}
                    />
                  </div>
                </div>

                <div className="answer">
                  {analysis.ai_analysis?.answer
                    ?.split("\n")
                    .map((line, index) => (
                      <p key={index}>{line || "\u00A0"}</p>
                    ))}
                </div>

                {analysis.ai_analysis?.error && (
                  <div className="notice-box">
                    <strong>Integration Notice:</strong>{" "}
                    {analysis.ai_analysis.error}
                  </div>
                )}
              </section>
            )}

            {/* 08. Git History Evidence */}
            {analysis?.analysis?.history && (
              <section className="panel history-panel">
                <div className="panel-heading">
                  <div>
                    <p className="section-label">GIT HISTORY EVIDENCE</p>
                    <h3>Repository & Symbol History</h3>
                  </div>
                </div>

                <div className="history-section">
                  <div className="history-heading">
                    <span className="history-label">SYMBOL HISTORY</span>
                    <strong>
                      {analysis.analysis.history.symbol_history?.commit_count ??
                        0}{" "}
                      commit(s)
                    </strong>
                  </div>

                  {analysis.analysis.history.symbol_history?.commits?.length ? (
                    <div className="commit-list">
                      {analysis.analysis.history.symbol_history.commits.map(
                        (commit) => (
                          <div className="commit-item" key={commit.commit}>
                            <div className="commit-date">{commit.date}</div>
                            <div className="commit-content">
                              <strong>{commit.message}</strong>
                              <code>{commit.commit}</code>
                            </div>
                          </div>
                        )
                      )}
                    </div>
                  ) : (
                    <p className="empty-history">
                      No symbol-history evidence supplied.
                    </p>
                  )}
                </div>
              </section>
            )}
          </>
        )}
      </main>
    </div>
  );
}

function Metric({ label, value, danger = false }) {
  return (
    <div className={`metric ${danger ? "metric-danger" : ""}`}>
      <span>{label}</span>
      <strong>{value ?? "—"}</strong>
    </div>
  );
}

function ValidationBadge({ validation }) {
  if (!validation) return null;
  const isSupported = validation.status === "SUPPORTED";
  const isCaution = validation.status === "CAUTION";
  return (
    <span
      className={`validation-tag ${
        isSupported
          ? "val-supported"
          : isCaution
          ? "val-caution"
          : "val-review"
      }`}
    >
      {isSupported ? "✓ SUPPORTED" : isCaution ? "⚠ CAUTION" : "! REVIEW"}
    </span>
  );
}

export default App;
