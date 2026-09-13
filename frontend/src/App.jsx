import { useEffect, useState } from "react";
import "./App.css";

const API_BASE = import.meta.env.VITE_API_BASE || "/api";

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

  const [ragMode, setRagMode] = useState("rag");
  const [selectedModel, setSelectedModel] = useState("qwen2.5-coder:1.5b");

  const [analysis, setAnalysis] = useState(null);
  const [compareResult, setCompareResult] = useState(null);
  const [modelCompareResult, setModelCompareResult] = useState(null);
  const [loadingModelComparison, setLoadingModelComparison] = useState(false);
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

      if (!res.ok) {
        throw new Error(data.detail || "Indexing failed.");
      }

      setIndexStatus(`Indexed ${data.chunk_count} code chunks`);
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
    setModelCompareResult(null);

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
    setModelCompareResult(null);

    try {
      if (ragMode === "compare") {
        const response = await fetch(
          `${API_BASE}/repositories/rag-compare`,
          {
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
          }
        );

        const data = await response.json();

        if (!response.ok) {
          throw new Error(
            data.detail?.message ||
              data.detail ||
              "Comparison analysis failed."
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

  async function compareModels() {
    if (!selectedTarget) {
      setError("Select a target first.");
      return;
    }

    setError("");
    setLoadingModelComparison(true);
    setModelCompareResult(null);

    try {
      const response = await fetch(
        `${API_BASE}/repositories/model-compare`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            repository_url: repositoryUrl,
            repository_name: repositoryName,
            target_id: selectedTarget.id,
            question,
            max_depth: 6,
            top_k_chunks: 5,
          }),
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail?.message ||
            data.detail ||
            "Model comparison failed."
        );
      }

      setModelCompareResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingModelComparison(false);
    }
  }

  const activeData = analysis || compareResult;
  const summary = activeData?.summary;

  const chunks =
    analysis?.rag_chunks?.chunks ||
    compareResult?.rag_chunks?.chunks ||
    [];

  const risk = Number(summary?.risk_score || 0);

  return (
    <div className="app-shell">

      {/* SIDEBAR */}
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="logo-mark">R</div>
          <div>
            <strong>RepoTwin</strong>
            <span>Code Intelligence</span>
          </div>
        </div>

        <nav className="sidebar-nav">
          <div className="nav-label">WORKSPACE</div>

          <button className="nav-item active">
            <span>⌂</span>
            Dashboard
          </button>

        </nav>

        <div className="sidebar-bottom">
          <div className="system-card">
            <div className="system-header">
              <span className="live-dot" />
              System Status
            </div>

            <div className="system-row">
              <span>API</span>
              <strong>
                {apiHealth?.status === "healthy" ? "Online" : "Offline"}
              </strong>
            </div>

            <div className="system-row">
              <span>Ollama</span>
              <strong>
                {apiHealth?.ollama?.available ? "Connected" : "Offline"}
              </strong>
            </div>
          </div>

          <div className="sidebar-version">RepoTwin v1.0</div>
        </div>
      </aside>

      {/* MAIN */}
      <main className="main-content">

        {/* TOP HEADER */}
        <header className="dashboard-header">
          <div>
            <p className="breadcrumb">WORKSPACE / DASHBOARD</p>
            <h1>Code Intelligence Dashboard</h1>
          </div>

          <div className="header-actions">
            <div className="header-model">
              <span className="model-dot" />
              <span>Model</span>

              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
              >
                <option value="qwen2.5-coder:1.5b">
                  Qwen 2.5 Coder 1.5B
                </option>
                <option value="starcoder2:3b">
                  StarCoder2 3B
                </option>
                <option value="opencoder:1.5b">
                  OpenCoder:1.5B
                </option>
              </select>
            </div>
          </div>
        </header>

        {/* HERO / ANALYSIS INPUT */}
        <section className="hero-card">
          <div className="hero-content">
            <div className="hero-badge">
              <span>✦</span>
              AI-POWERED REPOSITORY ANALYSIS
            </div>

            <h2>
              Understand the impact
              <br />
              <span>before you change the code.</span>
            </h2>

            <p>
              Analyze dependencies, callers, tests and repository context
              using deterministic graph analysis and evidence-grounded AI.
            </p>
          </div>

          <div className="repository-input-card">
            <div className="input-heading">
              <div>
                <span className="input-icon">⌘</span>
                <div>
                  <strong>Repository</strong>
                  <small>Connect a GitHub repository</small>
                </div>
              </div>

              {indexStatus && (
                <span className="success-pill">
                  ✓ {indexStatus}
                </span>
              )}
            </div>

            <div className="repo-input-row">
              <input
                value={repositoryUrl}
                onChange={(e) => setRepositoryUrl(e.target.value)}
                placeholder="https://github.com/owner/repository.git"
              />

              <input
                className="repo-name-input"
                value={repositoryName}
                onChange={(e) => setRepositoryName(e.target.value)}
                placeholder="Repository name"
              />

              <button
                className="secondary-button"
                onClick={triggerIndexing}
                disabled={indexing}
              >
                {indexing ? "Indexing..." : "Index Repository"}
              </button>
            </div>
          </div>
        </section>

        {/* SEARCH / TARGET */}
        <section className="workspace-card">
          <div className="section-top">
            <div>
              <span className="section-number">01</span>
              <div>
                <h3>Find a code entity</h3>
                <p>Search for a function, class or method to analyze.</p>
              </div>
            </div>

            {targets.length > 0 && (
              <span className="count-pill">
                {targets.length} entities found
              </span>
            )}
          </div>

          <div className="search-row">
            <div className="search-input">
              <span>⌕</span>
              <input
                value={targetSearch}
                onChange={(e) => setTargetSearch(e.target.value)}
                placeholder="Search functions, classes, methods..."
                onKeyDown={(e) => {
                  if (e.key === "Enter") discoverTargets();
                }}
              />
            </div>

            <button
              className="primary-button"
              onClick={discoverTargets}
              disabled={loadingTargets}
            >
              {loadingTargets ? "Searching..." : "Find Entities →"}
            </button>
          </div>

          {targets.length > 0 && (
            <div className="targets-grid">
              {targets.slice(0, 12).map((target) => (
                <button
                  key={target.id}
                  className={`entity-card ${
                    selectedTarget?.id === target.id ? "selected" : ""
                  }`}
                  onClick={() => {
                    setSelectedTarget(target);
                    setAnalysis(null);
                    setCompareResult(null);
                  }}
                >
                  <div className="entity-icon">
                    {target.type === "method"
                      ? "M"
                      : target.type === "class"
                      ? "C"
                      : "F"}
                  </div>

                  <div className="entity-info">
                    <strong>
                      {target.type === "method"
                        ? target.id.split(":").pop()
                        : target.name}
                    </strong>

                    <span>{target.file}</span>
                  </div>

                  <span className="entity-type">{target.type}</span>
                </button>
              ))}
            </div>
          )}
        </section>

        {/* ANALYSIS CONFIGURATION */}
        {selectedTarget && (
          <section className="workspace-card analysis-config">
            <div className="section-top">
              <div>
                <span className="section-number">02</span>
                <div>
                  <h3>Configure analysis</h3>
                  <p>Choose how RepoTwin should reason about this change.</p>
                </div>
              </div>
            </div>

            <div className="selected-entity">
              <div className="entity-icon large">
                {selectedTarget.type === "method"
                  ? "M"
                  : selectedTarget.type === "class"
                  ? "C"
                  : "F"}
              </div>

              <div>
                <span>SELECTED ENTITY</span>
                <strong>{selectedTarget.id}</strong>
              </div>
            </div>

            <div className="config-grid">

              <div className="config-block">
                <label>Analysis Mode</label>

                <div className="mode-buttons">
                  <button
                    className={ragMode === "rag" ? "active" : ""}
                    onClick={() => setRagMode("rag")}
                  >
                    <span>◈</span>
                    <div>
                      <strong>With RAG</strong>
                      <small>Grounded in repository code</small>
                    </div>
                  </button>

                  <button
                    className={ragMode === "non_rag" ? "active" : ""}
                    onClick={() => setRagMode("non_rag")}
                  >
                    <span>◇</span>
                    <div>
                      <strong>Without RAG</strong>
                      <small>General model reasoning</small>
                    </div>
                  </button>

                  <button
                    className={ragMode === "compare" ? "active" : ""}
                    onClick={() => setRagMode("compare")}
                  >
                    <span>⇄</span>
                    <div>
                      <strong>Compare</strong>
                      <small>RAG vs non-RAG</small>
                    </div>
                  </button>
                </div>
              </div>

              <div className="config-block">
                <label>Engineering Question</label>

                <textarea
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  rows="5"
                  placeholder="What happens if this function is modified?"
                />

                <button
                  className="analyze-button"
                  onClick={runAnalysis}
                  disabled={loadingAnalysis || loadingModelComparison}
                >
                  {loadingAnalysis
                    ? "Running analysis..."
                    : "Run Engineering Analysis  →"}
                </button>

                <button
                  className="compare-models-button"
                  onClick={compareModels}
                  disabled={loadingModelComparison || loadingAnalysis}
                >
                  {loadingModelComparison
                    ? "Comparing models..."
                    : "⇄ Compare 3 Models"}
                </button>
              </div>
            </div>
          </section>
        )}

        {/* MODEL COMPARISON */}
        {modelCompareResult && (
          <section className="workspace-card model-comparison">
            <div className="section-top">
              <div>
                <span className="section-number">03</span>
                <div>
                  <h3>Model Comparison</h3>
                  <p>
                    Same repository context and question evaluated across
                    three coding models.
                  </p>
                </div>
              </div>

              <span className="count-pill">
                {modelCompareResult.models?.length || 0} models
              </span>
            </div>

            <div className="model-comparison-grid">
              {modelCompareResult.models?.map((result) => (
                <div className="model-card" key={result.model}>
                  <div className="model-card-header">
                    <div>
                      <strong>{result.model}</strong>
                      <span>RAG evaluation</span>
                    </div>

                    <span
                      className={`model-status ${
                        result.ollama_available
                          ? "available"
                          : "unavailable"
                      }`}
                    >
                      {result.ollama_available
                        ? "● Available"
                        : "● Unavailable"}
                    </span>
                  </div>

                  <div className="model-metrics">
                    <div>
                      <span>RESPONSE TIME</span>
                      <strong>
                        {result.response_time_seconds}s
                      </strong>
                    </div>

                    <div>
                      <span>GROUNDING</span>
                      <strong>
                        {result.validation?.status || "N/A"}
                      </strong>
                    </div>
                  </div>

                  <div className="model-answer">
                    {result.answer
                      ? result.answer.split("\n").map((line, index) => (
                          <p key={index}>{line || "\u00A0"}</p>
                        ))
                      : (
                        <p className="model-error">
                          {result.error || "No response generated."}
                        </p>
                      )}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* ERROR */}
        {error && (
          <div className="error-box">
            <strong>Analysis Error</strong>
            <span>{error}</span>
          </div>
        )}

        {/* RESULTS */}
        {activeData && (
          <>
            <div className="results-heading">
              <div>
                <p>03 · ANALYSIS RESULTS</p>
                <h2>Repository Impact</h2>
              </div>

              <div className="verified-pill">
                <span>✓</span>
                Deterministic Graph Verified
              </div>
            </div>

            {/* METRICS */}
            <section className="metrics-grid">

              <Metric
                label="Risk Score"
                value={summary?.risk_score}
                suffix="/100"
                danger
                large
              />

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
                label="Risk Level"
                value={summary?.risk_level}
                danger
              />
            </section>

            {/* IMPACT + AI */}
            <div className="result-columns">

              <section className="result-card">
                <div className="result-card-header">
                  <div>
                    <span className="result-icon blue">◎</span>
                    <div>
                      <p>GRAPH ENGINE</p>
                      <h3>Impact Analysis</h3>
                    </div>
                  </div>

                  <span className="verified-small">VERIFIED</span>
                </div>

                <div className="risk-display">
                  <div
                    className="risk-circle"
                    style={{
                      background: `conic-gradient(#5b7cff ${
                        risk * 3.6
                      }deg, #202638 0deg)`,
                    }}
                  >
                    <div>
                      <strong>{risk}</strong>
                      <span>RISK</span>
                    </div>
                  </div>

                  <div className="risk-details">
                    <strong>{summary?.risk_level || "—"} Risk</strong>
                    <span>
                      Determined from repository dependency and impact
                      analysis.
                    </span>
                  </div>
                </div>

                <div className="impact-stats">
                  <div>
                    <span>Direct</span>
                    <strong>{summary?.direct_callers ?? "—"}</strong>
                  </div>

                  <div>
                    <span>Indirect</span>
                    <strong>{summary?.indirect_callers ?? "—"}</strong>
                  </div>

                  <div>
                    <span>Tests</span>
                    <strong>{summary?.affected_tests ?? "—"}</strong>
                  </div>
                </div>
              </section>

              <section className="result-card ai-result">
                <div className="result-card-header">
                  <div>
                    <span className="result-icon purple">✦</span>
                    <div>
                      <p>LLM REASONING</p>
                      <h3>AI Engineering Analysis</h3>
                    </div>
                  </div>

                  <div className="ai-meta">
                    <span>
                      {analysis?.ai_analysis?.model ||
                        selectedModel}
                    </span>

                    <ValidationBadge
                      validation={analysis?.ai_analysis?.validation}
                    />
                  </div>
                </div>

                <div className="ai-answer">
                  {analysis?.ai_analysis?.answer
                    ?.split("\n")
                    .map((line, index) => (
                      <p key={index}>{line || "\u00A0"}</p>
                    ))}

                  {compareResult && (
                    <Comparison
                      result={compareResult}
                    />
                  )}
                </div>
              </section>
            </div>

            {/* RAG */}
            {chunks.length > 0 && (
              <section className="workspace-card rag-results">
                <div className="section-top">
                  <div>
                    <span className="section-number">04</span>
                    <div>
                      <h3>Retrieved code context</h3>
                      <p>
                        AST-aware chunks retrieved from the repository
                        knowledge base.
                      </p>
                    </div>
                  </div>

                  <span className="rag-pill">
                    {chunks.length} chunks · cosine similarity
                  </span>
                </div>

                <div className="chunks-grid">
                  {chunks.map((chunk, index) => (
                    <div className="code-card" key={index}>
                      <div className="code-header">
                        <div>
                          <span className="code-type">
                            {chunk.type}
                          </span>
                          <strong>{chunk.name}</strong>
                        </div>

                        <span className="similarity">
                          {(
                            (chunk.similarity_score ?? 0) * 100
                          ).toFixed(1)}
                          %
                        </span>
                      </div>

                      <div className="code-location">
                        {chunk.file}:{chunk.start_line}-{chunk.end_line}
                      </div>

                      <pre>
                        <code>
                          {chunk.source_code || chunk.text}
                        </code>
                      </pre>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* HISTORY */}
            {analysis?.analysis?.history && (
              <section className="workspace-card">
                <div className="section-top">
                  <div>
                    <span className="section-number">05</span>
                    <div>
                      <h3>Git history</h3>
                      <p>Historical evidence for the analyzed symbol.</p>
                    </div>
                  </div>
                </div>

                <div className="commit-list">
                  {analysis.analysis.history.symbol_history?.commits
                    ?.length ? (
                    analysis.analysis.history.symbol_history.commits.map(
                      (commit) => (
                        <div className="commit-row" key={commit.commit}>
                          <span>{commit.date}</span>

                          <div>
                            <strong>{commit.message}</strong>
                            <code>{commit.commit}</code>
                          </div>
                        </div>
                      )
                    )
                  ) : (
                    <p className="muted">
                      No symbol-history evidence supplied.
                    </p>
                  )}
                </div>
              </section>
            )}
          </>
        )}

        <footer>
          RepoTwin · Evidence-grounded code intelligence
        </footer>
      </main>
    </div>
  );
}

function Metric({
  label,
  value,
  suffix = "",
  danger = false,
  large = false,
}) {
  return (
    <div className={`metric-card ${danger ? "danger" : ""}`}>
      <span>{label}</span>
      <div>
        <strong className={large ? "metric-large" : ""}>
          {value ?? "—"}
        </strong>
        {suffix && <small>{suffix}</small>}
      </div>
    </div>
  );
}

function ValidationBadge({ validation, mode }) {
  if (!validation) return null;

  const supported = validation.status === "SUPPORTED";
  const caution = validation.status === "CAUTION";

  let label = "! REVIEW";

  if (mode === "rag") {
    label = supported
      ? "✓ REPOSITORY GROUNDED"
      : caution
      ? "⚠ CAUTION"
      : "! REVIEW";
  } else if (mode === "non-rag") {
    label = "○ NO REPOSITORY CONTEXT";
  } else {
    label = supported
      ? "✓ SUPPORTED"
      : caution
      ? "⚠ CAUTION"
      : "! REVIEW";
  }

  return (
    <span
      className={`validation ${
        supported
          ? "supported"
          : caution
          ? "caution"
          : "review"
      }`}
    >
      {label}
    </span>
  );
}

function Comparison({ result }) {
  return (
    <div className="comparison">
      <div className="comparison-panel rag-panel">
        <div className="comparison-title">
          <span>WITH RAG</span>
        </div>

        <div className="comparison-answer">
          {result.with_rag?.answer || "No response."}
        </div>

        <ValidationBadge
          validation={result.with_rag?.validation}
          mode="rag"
        />
      </div>

      <div className="comparison-panel non-rag-panel">
        <div className="comparison-title">
          <span>WITHOUT RAG</span>
        </div>

        <div className="comparison-answer">
          {result.without_rag?.answer || "No response."}
        </div>

        <ValidationBadge
          validation={result.without_rag?.validation}
          mode="non-rag"
        />
      </div>
    </div>
  );
}

export default App;
