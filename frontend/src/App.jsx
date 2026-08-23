import { useState } from "react";
import "./App.css";

const API_BASE = "http://192.168.195.131:8000";

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

  const [analysis, setAnalysis] = useState(null);
  const [loadingTargets, setLoadingTargets] = useState(false);
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);
  const [error, setError] = useState("");

  async function discoverTargets() {
    setError("");
    setLoadingTargets(true);
    setTargets([]);
    setSelectedTarget(null);
    setAnalysis(null);

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

    try {
      const response = await fetch(
        `${API_BASE}/repositories/engineering-analysis`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            repository_url: repositoryUrl,
            repository_name: repositoryName,
            target_id: selectedTarget.id,
            question,
            max_depth: 6,
            top_k: 10,
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
    } catch (err) {
      setError(err.message);
    } finally {
      setLoadingAnalysis(false);
    }
  }

  const summary = analysis?.summary;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">R</div>
          <div>
            <h1>RepoTwin</h1>
            <span>Repository Intelligence</span>
          </div>
        </div>

        <div className="status">
          <span className="status-dot" />
          API Connected
        </div>
      </header>

      <main className="container">
        <section className="hero-section">
          <div>
            <p className="eyebrow">CODEBASE INTELLIGENCE</p>
            <h2>Understand the impact<br />before you change code.</h2>
            <p className="hero-copy">
              Analyze repository dependencies, affected tests, Git history,
              engineering risk, and evidence-grounded AI reasoning.
            </p>
          </div>
        </section>

        <section className="panel repository-panel">
          <div className="panel-heading">
            <div>
              <p className="section-label">01 · REPOSITORY</p>
              <h3>Connect a repository</h3>
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
                placeholder="close, Response, Session..."
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

        {targets.length > 0 && (
          <section className="panel">
            <div className="panel-heading">
              <div>
                <p className="section-label">02 · TARGET</p>
                <h3>Select a code entity</h3>
              </div>

              <span className="result-count">
                {targets.length} found
              </span>
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
                  }}
                >
                  <div className="target-icon">
                    {target.type === "method" ? "M" : "F"}
                  </div>

                  <div className="target-info">
                    <strong>
                      {target.type === "method"
                        ? target.id.split(":").pop()
                        : target.name}
                    </strong>
                    <span>{target.file}</span>
                    <small>
                      {target.type === "method"
                        ? "method"
                        : target.type}
                    </small>
                  </div>

                  <div className="target-arrow">→</div>
                </button>
              ))}
            </div>
          </section>
        )}

        {selectedTarget && (
          <section className="panel question-panel">
            <div className="panel-heading">
              <div>
                <p className="section-label">03 · ENGINEERING QUESTION</p>
                <h3>
                  Analyze{" "}
                  <code>
                    {selectedTarget.name}
                  </code>
                </h3>
              </div>
            </div>

            <div className="selected-target">
              <span>{selectedTarget.type}</span>
              <strong>{selectedTarget.id}</strong>
            </div>

            <label>
              <span>Your question</span>
              <textarea
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                rows="3"
              />
            </label>

            <button
              className="primary-button analyze-button"
              onClick={runAnalysis}
              disabled={loadingAnalysis}
            >
              {loadingAnalysis ? "Analyzing repository..." : "Run engineering analysis →"}
            </button>
          </section>
        )}

        {error && (
          <div className="error-box">
            <strong>Analysis error</strong>
            <span>{error}</span>
          </div>
        )}

        {analysis && (
          <>
            <section className="results-header">
              <div>
                <p className="section-label">04 · ANALYSIS RESULT</p>
                <h3>Engineering impact report</h3>
              </div>

              <div className="validation-badge">
                <span>✓</span>
                Evidence validated
              </div>
            </section>

            <section className="metrics-grid">
              <Metric
                label="Production impact"
                value={summary?.production_impact}
              />
              <Metric
                label="Direct callers"
                value={summary?.direct_callers}
              />
              <Metric
                label="Indirect callers"
                value={summary?.indirect_callers}
              />
              <Metric
                label="Affected tests"
                value={summary?.affected_tests}
              />
              <Metric
                label="Risk score"
                value={summary?.risk_score}
                danger
              />
              <Metric
                label="Risk level"
                value={summary?.risk_level}
                danger
              />
            </section>

            <section className="analysis-overview">
              <div className="overview-card">
                <span className="overview-label">IMPACT BREAKDOWN</span>
                <div className="overview-row">
                  <span>Direct callers</span>
                  <strong>{summary?.direct_callers ?? 0}</strong>
                </div>
                <div className="overview-row">
                  <span>Indirect callers</span>
                  <strong>{summary?.indirect_callers ?? 0}</strong>
                </div>
                <div className="overview-row">
                  <span>Affected tests</span>
                  <strong>{summary?.affected_tests ?? 0}</strong>
                </div>
              </div>

              <div className="overview-card">
                <span className="overview-label">RISK SIGNALS</span>
                <div className="overview-row">
                  <span>High-confidence paths</span>
                  <strong>
                    {analysis.analysis?.risk?.signals?.high_confidence_paths ?? 0}
                  </strong>
                </div>
                <div className="overview-row">
                  <span>Medium-confidence paths</span>
                  <strong>
                    {analysis.analysis?.risk?.signals?.medium_confidence_paths ?? 0}
                  </strong>
                </div>
                <div className="overview-row">
                  <span>Affected files</span>
                  <strong>
                    {analysis.analysis?.risk?.signals?.affected_files ?? 0}
                  </strong>
                </div>
              </div>
            </section>

            <section className="panel ai-panel">
              <div className="panel-heading">
                <div>
                  <p className="section-label">ENGINEERING ANALYSIS</p>
                  <h3>Evidence-grounded analysis</h3>
                </div>

                <span className="model-label">
                  {analysis.ai_analysis?.model}
                </span>
              </div>

              <div className="answer">
                {analysis.ai_analysis?.answer
                  ?.split("\n")
                  .map((line, index) => (
                    <p key={index}>
                      {line || "\u00A0"}
                    </p>
                  ))}
              </div>
            </section>

            <section className="panel history-panel">
              <div className="panel-heading">
                <div>
                  <p className="section-label">GIT HISTORY</p>
                  <h3>Repository history</h3>
                </div>
              </div>

              <div className="history-section">
                <div className="history-heading">
                  <span className="history-label">SYMBOL HISTORY</span>
                  <strong>
                    {analysis.analysis?.history?.symbol_history?.commit_count ?? 0} commit(s)
                  </strong>
                </div>

                {analysis.analysis?.history?.symbol_history?.commits?.length ? (
                  <div className="commit-list">
                    {analysis.analysis.history.symbol_history.commits.map((commit) => (
                      <div className="commit-item" key={commit.commit}>
                        <div className="commit-date">{commit.date}</div>
                        <div className="commit-content">
                          <strong>{commit.message}</strong>
                          <code>{commit.commit}</code>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="empty-history">
                    No symbol-history evidence supplied.
                  </p>
                )}
              </div>

              <div className="history-section">
                <div className="history-heading">
                  <span className="history-label">FILE HISTORY</span>
                  <strong>
                    {analysis.analysis?.history?.file_history?.commit_count ?? 0} commits
                  </strong>
                </div>

                <div className="commit-list">
                  {analysis.analysis?.history?.file_history?.commits
                    ?.slice(0, 10)
                    .map((commit) => (
                      <div className="commit-item" key={commit.commit}>
                        <div className="commit-date">{commit.date}</div>
                        <div className="commit-content">
                          <strong>{commit.message}</strong>
                          <code>{commit.commit}</code>
                        </div>
                      </div>
                    ))}
                </div>
              </div>
            </section>

            <section className="two-column">
              <div className="panel">
                <div className="panel-heading">
                  <div>
                    <p className="section-label">EVIDENCE</p>
                    <h3>Retrieved evidence</h3>
                  </div>
                </div>

                <div className="evidence-list">
                  {analysis.retrieval?.evidence?.map((item, index) => (
                    <div className="evidence-item" key={index}>
                      <div>
                        <span className="evidence-category">
                          {item.category}
                        </span>
                        <strong>{item.source_name || item.source}</strong>
                      </div>
                      <span className="depth">
                        depth {item.depth}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="panel">
                <div className="panel-heading">
                  <div>
                    <p className="section-label">VALIDATION</p>
                    <h3>Evidence validator</h3>
                  </div>
                </div>

                <div
                  className={`validation-result ${
                    analysis.ai_analysis?.validation?.status === "SUPPORTED"
                      ? "validation-supported"
                      : analysis.ai_analysis?.validation?.status === "CAUTION"
                        ? "validation-caution"
                        : "validation-review"
                  }`}
                >
                  <div className="validation-icon">
                    {analysis.ai_analysis?.validation?.validated ? "✓" : "!"}
                  </div>
                  <div>
                    <strong>
                      {analysis.ai_analysis?.validation?.status || "UNKNOWN"}
                    </strong>
                    <span>
                      {analysis.ai_analysis?.validation?.validated
                        ? "The AI response is consistent with the deterministic repository evidence."
                        : "Some claims require review against the repository evidence."}
                    </span>
                  </div>
                </div>

                <div className="validation-stats">
                  <div>
                    <span>Validated</span>
                    <strong>
                      {String(
                        analysis.ai_analysis?.validation?.validated
                      )}
                    </strong>
                  </div>
                  <div>
                    <span>Claims requiring review</span>
                    <strong>
                      {analysis.ai_analysis?.validation?.claim_count ?? 0}
                    </strong>
                  </div>
                </div>
              </div>
            </section>
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

export default App;
