import { useState, useCallback, useEffect } from "react";
import { fetchPrograms, checkHealth } from './api.js';
import { buildTree } from './treeBuilder.js';

export default function CareerTreeV2() {
  // ========================================================================
  // STATE
  // ========================================================================
  const [nodes, setNodes] = useState(null);
  const [selectedPath, setSelectedPath] = useState([]);
  const [hoveredNode, setHoveredNode] = useState(null);
  const [activeLeaf, setActiveLeaf] = useState(null);
  const [collapsedNodes, setCollapsedNodes] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [apiHealthy, setApiHealthy] = useState(false);

  // ========================================================================
  // LOAD DATA FROM API
  // ========================================================================
  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);

        // Check API health
        const healthy = await checkHealth();
        setApiHealthy(healthy);

        if (!healthy) {
          throw new Error('API is not responding. Please start the backend server.');
        }

        // Fetch programs from API
        const programs = await fetchPrograms();

        // Build tree dynamically
        const treeNodes = buildTree(programs);
        setNodes(treeNodes);

        setLoading(false);
      } catch (err) {
        console.error('Failed to load data:', err);
        setError(err.message);
        setLoading(false);
      }
    }

    loadData();
  }, []);

  // ========================================================================
  // TREE NAVIGATION LOGIC
  // ========================================================================

  const isDescendantOf = useCallback((nodeId, ancestorId) => {
    if (!nodes) return false;
    const ancestor = nodes[ancestorId];
    if (!ancestor) return false;

    for (const childId of ancestor.children || []) {
      if (childId === nodeId) return true;
      if (isDescendantOf(nodeId, childId)) return true;
    }
    return false;
  }, [nodes]);

  const isInPath = useCallback((id) => selectedPath.includes(id), [selectedPath]);

  const isHighlighted = useCallback((id) => {
    if (selectedPath.length === 0) return true;
    const idx = selectedPath.indexOf(id);
    if (idx !== -1) return true;
    const last = selectedPath[selectedPath.length - 1];
    return isDescendantOf(id, last);
  }, [selectedPath, isDescendantOf]);

  const isNodeVisible = useCallback((nodeId) => {
    for (const [id] of Object.entries(nodes || {})) {
      if (collapsedNodes.has(id)) {
        if (isDescendantOf(nodeId, id)) {
          return false;
        }
      }
    }
    return true;
  }, [collapsedNodes, isDescendantOf, nodes]);

  const toggleCollapse = useCallback((id, e) => {
    e.stopPropagation();
    setCollapsedNodes(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const handleNodeClick = useCallback((id) => {
    if (!nodes) return;
    const node = nodes[id];
    if (!node) return;

    if (id === "root") {
      setSelectedPath([]);
      setActiveLeaf(null);
      return;
    }

    const parentInPath = selectedPath.length === 0 ||
      (nodes[selectedPath[selectedPath.length - 1]]?.children || []).includes(id);

    if (parentInPath) {
      const existingIdx = selectedPath.indexOf(id);
      if (existingIdx !== -1) {
        setSelectedPath(selectedPath.slice(0, existingIdx + 1));
        setActiveLeaf((node.children || []).length === 0 ? id : null);
      } else {
        const newPath = [...selectedPath, id];
        setSelectedPath(newPath);
        setActiveLeaf((node.children || []).length === 0 ? id : null);
      }
    } else {
      setSelectedPath([id]);
      setActiveLeaf((node.children || []).length === 0 ? id : null);
    }
  }, [nodes, selectedPath]);

  // ========================================================================
  // RENDER LOADING / ERROR STATES
  // ========================================================================

  if (loading) {
    return (
      <div style={{
        minHeight: "100vh",
        background: "#070b14",
        color: "#e8eaf6",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexDirection: "column",
        gap: "20px"
      }}>
        <div style={{ fontSize: "24px" }}>⏳ Loading decision tree...</div>
        <div style={{ fontSize: "14px", color: "#64748b" }}>Fetching data from database</div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{
        minHeight: "100vh",
        background: "#070b14",
        color: "#e8eaf6",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexDirection: "column",
        gap: "20px",
        padding: "40px"
      }}>
        <div style={{ fontSize: "32px" }}>❌ Error</div>
        <div style={{
          fontSize: "16px",
          color: "#ef4444",
          maxWidth: "600px",
          textAlign: "center",
          background: "#1a0a0a",
          padding: "20px",
          borderRadius: "10px",
          border: "1px solid #ef4444"
        }}>
          {error}
        </div>
        <div style={{ fontSize: "14px", color: "#64748b", marginTop: "20px" }}>
          Make sure the Flask backend is running:
          <pre style={{
            background: "#0f172a",
            padding: "10px",
            borderRadius: "5px",
            marginTop: "10px"
          }}>cd backend && python3 app.py</pre>
        </div>
      </div>
    );
  }

  if (!nodes) {
    return <div>No data available</div>;
  }

  // ========================================================================
  // BUILD PHASE LAYOUT
  // ========================================================================

  const phaseNodes = [-1, 0, 1, 2, 3].map(ph =>
    Object.values(nodes).filter(n => n.phase === ph && isNodeVisible(n.id))
  );

  // Separate phase 0 nodes by branch type
  const phase0Nodes = phaseNodes[1]; // phaseNodes[1] is phase 0
  const corporateNodes = phase0Nodes.filter(n => n.branchType === "corporate");
  const mastersNodes = phase0Nodes.filter(n => n.branchType === "masters");

  // Group masters nodes by depth for nested rendering
  const mastersByDepth = {
    0: mastersNodes.filter(n => n.depth === 0),
    1: mastersNodes.filter(n => n.depth === 1),
    2: mastersNodes.filter(n => n.depth === 2),
    3: mastersNodes.filter(n => n.depth === 3),
  };

  const pathProbs = selectedPath.reduce((acc, id, i) => {
    const node = nodes[id];
    const prev = i === 0 ? 1 : acc[i - 1];
    acc.push(prev * (node?.prob || 1));
    return acc;
  }, []);

  const leafNode = activeLeaf ? nodes[activeLeaf] : null;

  const PHASE_LABELS = ["Phase 1 · Yr 0–2", "Phase 2 · Yr 2–4", "Phase 3 · Yr 4–7", "Phase 4 · Yr 7–10"];
  const PHASE_COLORS = ["#00e5ff22", "#00ff9f22", "#a29bfe22", "#fd79a822"];

  // ========================================================================
  // RENDER MAIN UI
  // ========================================================================

  return (
    <div style={{
      minHeight: "100vh",
      background: "#070b14",
      color: "#e8eaf6",
      fontFamily: "'DM Mono', 'Fira Code', monospace",
      padding: "24px 16px",
      overflowX: "auto",
    }}>
      {/* Header */}
      <div style={{ textAlign: "center", marginBottom: 28 }}>
        <div style={{
          fontFamily: "'Bebas Neue', 'Impact', sans-serif",
          fontSize: "clamp(22px, 4vw, 44px)",
          letterSpacing: "0.12em",
          background: "linear-gradient(90deg, #00e5ff, #00ff9f, #a29bfe)",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
          marginBottom: 4,
        }}>10-YEAR AI CAREER DECISION TREE v2</div>
        <div style={{ fontSize: 12, color: "#636e72", letterSpacing: "0.2em" }}>
          {Object.keys(nodes).length} NODES · DATABASE-DRIVEN · REAL-TIME DATA
        </div>
        <div style={{ fontSize: 11, color: "#4a5568", marginTop: 6 }}>
          Click nodes to trace a path · Click root to reset · Click − / + to collapse/expand
        </div>
        {apiHealthy && (
          <div style={{ fontSize: 10, color: "#00ff9f", marginTop: 8 }}>
            ✓ Connected to API
          </div>
        )}
      </div>

      {/* Legend */}
      <div style={{ display: "flex", gap: 20, justifyContent: "center", marginBottom: 20, flexWrap: "wrap" }}>
        {[
          { color: "#00ff9f", label: "High prob (≥55%)" },
          { color: "#fdcb6e", label: "Medium prob (35–55%)" },
          { color: "#ff7675", label: "Lower prob (<35%)" },
          { color: "#00e5ff", label: "Motive / Elite US" },
          { color: "#a29bfe", label: "Local / Europe" },
          { color: "#00cec9", label: "Remote / Asia" },
        ].map(({ color, label }) => (
          <div key={label} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11 }}>
            <div style={{ width: 10, height: 10, borderRadius: 2, background: color }} />
            <span style={{ color: "#94a3b8" }}>{label}</span>
          </div>
        ))}
      </div>

      {/* Tree */}
      <div style={{
        display: "flex",
        gap: 0,
        alignItems: "flex-start",
        overflowX: "auto",
        paddingBottom: 24,
        minWidth: "900px",
      }}>
        {/* Root */}
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", minWidth: 140, paddingTop: 60 }}>
          <NodeCard
            node={nodes.root}
            inPath={true}
            highlighted={true}
            onClick={() => handleNodeClick("root")}
            onHover={setHoveredNode}
            hovered={hoveredNode === "root"}
            cumProb={1.0}
            collapsed={collapsedNodes.has("root")}
            onToggleCollapse={toggleCollapse}
            hasChildren={(nodes.root.children || []).length > 0}
          />
        </div>

        <ConnectorArrow />

        {/* Phase 0 - Immediate Decisions (Split by branch type) */}
        <div style={{ display: "flex", alignItems: "stretch" }}>
          <div style={{
            display: "flex",
            flexDirection: "column",
            minWidth: 155,
            background: PHASE_COLORS[0],
            borderRadius: 12,
            padding: "8px 6px",
            gap: 10,
          }}>
            <div style={{
              fontSize: 9,
              letterSpacing: "0.18em",
              color: "#64748b",
              textAlign: "center",
              borderBottom: "1px solid #1e2a3a",
              paddingBottom: 6,
              marginBottom: 2,
            }}>IMMEDIATE DECISIONS · NOW</div>

            {/* Corporate Career Options */}
            {corporateNodes.length > 0 && (
              <>
                <div style={{
                  fontSize: 8,
                  letterSpacing: "0.15em",
                  color: "#4a90d9",
                  paddingLeft: 4,
                  marginTop: 4,
                }}>CORPORATE PATH</div>
                {corporateNodes.map((node) => {
                  const cumIdx = selectedPath.indexOf(node.id);
                  const cumP = cumIdx !== -1 ? pathProbs[cumIdx] : null;
                  return (
                    <NodeCard
                      key={node.id}
                      node={node}
                      inPath={isInPath(node.id)}
                      highlighted={isHighlighted(node.id)}
                      onClick={() => handleNodeClick(node.id)}
                      onHover={setHoveredNode}
                      hovered={hoveredNode === node.id}
                      cumProb={cumP}
                      isLeaf={(node.children || []).length === 0}
                      collapsed={collapsedNodes.has(node.id)}
                      onToggleCollapse={toggleCollapse}
                      hasChildren={(node.children || []).length > 0}
                    />
                  );
                })}
              </>
            )}

            {/* Masters Branch - Nested */}
            {mastersNodes.length > 0 && (
              <>
                <div style={{
                  fontSize: 8,
                  letterSpacing: "0.15em",
                  color: "#a29bfe",
                  paddingLeft: 4,
                  marginTop: 8,
                  borderTop: "1px solid #1e2a3a",
                  paddingTop: 8,
                }}>MASTERS PATH</div>

                {/* Depth 0 - Masters Root */}
                {mastersByDepth[0].map((node) => {
                  const cumIdx = selectedPath.indexOf(node.id);
                  const cumP = cumIdx !== -1 ? pathProbs[cumIdx] : null;
                  return (
                    <div key={node.id}>
                      <NodeCard
                        node={node}
                        inPath={isInPath(node.id)}
                        highlighted={isHighlighted(node.id)}
                        onClick={() => handleNodeClick(node.id)}
                        onHover={setHoveredNode}
                        hovered={hoveredNode === node.id}
                        cumProb={cumP}
                        isLeaf={(node.children || []).length === 0}
                        collapsed={collapsedNodes.has(node.id)}
                        onToggleCollapse={toggleCollapse}
                        hasChildren={(node.children || []).length > 0}
                      />

                      {/* Depth 1 - Tiers (indented) */}
                      {!collapsedNodes.has(node.id) && mastersByDepth[1]
                        .filter(tier => node.children.includes(tier.id))
                        .map((tier) => {
                          const cumIdx = selectedPath.indexOf(tier.id);
                          const cumP = cumIdx !== -1 ? pathProbs[cumIdx] : null;
                          return (
                            <div key={tier.id} style={{ marginLeft: 8, marginTop: 6 }}>
                              <NodeCard
                                node={tier}
                                inPath={isInPath(tier.id)}
                                highlighted={isHighlighted(tier.id)}
                                onClick={() => handleNodeClick(tier.id)}
                                onHover={setHoveredNode}
                                hovered={hoveredNode === tier.id}
                                cumProb={cumP}
                                isLeaf={(tier.children || []).length === 0}
                                collapsed={collapsedNodes.has(tier.id)}
                                onToggleCollapse={toggleCollapse}
                                hasChildren={(tier.children || []).length > 0}
                                compact={true}
                              />

                              {/* Depth 2 - Fields (double indented) */}
                              {!collapsedNodes.has(tier.id) && mastersByDepth[2]
                                .filter(field => tier.children.includes(field.id))
                                .map((field) => {
                                  const cumIdx = selectedPath.indexOf(field.id);
                                  const cumP = cumIdx !== -1 ? pathProbs[cumIdx] : null;
                                  return (
                                    <div key={field.id} style={{ marginLeft: 8, marginTop: 4 }}>
                                      <NodeCard
                                        node={field}
                                        inPath={isInPath(field.id)}
                                        highlighted={isHighlighted(field.id)}
                                        onClick={() => handleNodeClick(field.id)}
                                        onHover={setHoveredNode}
                                        hovered={hoveredNode === field.id}
                                        cumProb={cumP}
                                        isLeaf={(field.children || []).length === 0}
                                        collapsed={collapsedNodes.has(field.id)}
                                        onToggleCollapse={toggleCollapse}
                                        hasChildren={(field.children || []).length > 0}
                                        compact={true}
                                      />

                                      {/* Depth 3 - Programs (triple indented) */}
                                      {!collapsedNodes.has(field.id) && mastersByDepth[3]
                                        .filter(prog => field.children.includes(prog.id))
                                        .slice(0, 5) // Show only first 5 programs by default
                                        .map((prog) => {
                                          const cumIdx = selectedPath.indexOf(prog.id);
                                          const cumP = cumIdx !== -1 ? pathProbs[cumIdx] : null;
                                          return (
                                            <div key={prog.id} style={{ marginLeft: 8, marginTop: 3 }}>
                                              <NodeCard
                                                node={prog}
                                                inPath={isInPath(prog.id)}
                                                highlighted={isHighlighted(prog.id)}
                                                onClick={() => handleNodeClick(prog.id)}
                                                onHover={setHoveredNode}
                                                hovered={hoveredNode === prog.id}
                                                cumProb={cumP}
                                                isLeaf={true}
                                                collapsed={false}
                                                onToggleCollapse={toggleCollapse}
                                                hasChildren={false}
                                                compact={true}
                                              />
                                            </div>
                                          );
                                        })}
                                    </div>
                                  );
                                })}
                            </div>
                          );
                        })}
                    </div>
                  );
                })}
              </>
            )}
          </div>
          <ConnectorArrow />
        </div>

        {/* Phase columns 1, 2, 3 (future expansion) */}
        {[1, 2, 3].map((phaseIdx) => (
          phaseNodes[phaseIdx + 1].length > 0 && (
            <div key={phaseIdx} style={{ display: "flex", alignItems: "stretch" }}>
              <div style={{
                display: "flex",
                flexDirection: "column",
                minWidth: 155,
                background: PHASE_COLORS[phaseIdx],
                borderRadius: 12,
                padding: "8px 6px",
                gap: 10,
              }}>
                <div style={{
                  fontSize: 9,
                  letterSpacing: "0.18em",
                  color: "#64748b",
                  textAlign: "center",
                  borderBottom: "1px solid #1e2a3a",
                  paddingBottom: 6,
                  marginBottom: 2,
                }}>{PHASE_LABELS[phaseIdx]}</div>
                {phaseNodes[phaseIdx + 1].map((node) => {
                  const cumIdx = selectedPath.indexOf(node.id);
                  const cumP = cumIdx !== -1 ? pathProbs[cumIdx] : null;
                  return (
                    <NodeCard
                      key={node.id}
                      node={node}
                      inPath={isInPath(node.id)}
                      highlighted={isHighlighted(node.id)}
                      onClick={() => handleNodeClick(node.id)}
                      onHover={setHoveredNode}
                      hovered={hoveredNode === node.id}
                      cumProb={cumP}
                      isLeaf={(node.children || []).length === 0}
                      collapsed={collapsedNodes.has(node.id)}
                      onToggleCollapse={toggleCollapse}
                      hasChildren={(node.children || []).length > 0}
                    />
                  );
                })}
              </div>
              {phaseIdx < 3 && <ConnectorArrow />}
            </div>
          )
        ))}
      </div>

      {/* Selected Path Summary */}
      {selectedPath.length > 0 && (
        <PathSummary
          selectedPath={selectedPath}
          nodes={nodes}
          pathProbs={pathProbs}
          leafNode={leafNode}
        />
      )}

      {/* Hovered node tooltip */}
      {hoveredNode && hoveredNode !== "root" && nodes[hoveredNode]?.note && !selectedPath.includes(hoveredNode) && (
        <HoverTooltip node={nodes[hoveredNode]} />
      )}
    </div>
  );
}

// ============================================================================
// HELPER COMPONENTS
// ============================================================================

function NodeCard({ node, inPath, highlighted, onClick, onHover, hovered, cumProb, isLeaf, collapsed, onToggleCollapse, hasChildren, compact = false }) {
  const dim = !highlighted;

  function getProbColor(prob) {
    if (prob >= 0.55) return "#00ff9f";
    if (prob >= 0.35) return "#fdcb6e";
    return "#ff7675";
  }

  return (
    <div
      onClick={onClick}
      onMouseEnter={() => onHover(node.id)}
      onMouseLeave={() => onHover(null)}
      style={{
        background: inPath ? `${node.color}18` : hovered ? "#131c2e" : "#0c1220",
        border: `1.5px solid ${inPath ? node.color : hovered ? node.color + "88" : "#1e2a3a"}`,
        borderRadius: compact ? 6 : 9,
        padding: compact ? "6px 8px" : "9px 10px",
        cursor: "pointer",
        opacity: dim ? 0.28 : 1,
        transition: "all 0.15s ease",
        boxShadow: inPath ? `0 0 12px ${node.color}33` : "none",
        minHeight: compact ? 60 : 84,
        position: "relative",
      }}
    >
      {hasChildren && !isLeaf && (
        <div
          onClick={(e) => onToggleCollapse(node.id, e)}
          style={{
            position: "absolute",
            top: -1,
            left: -1,
            background: collapsed ? "#1a2744" : "#2d4a66",
            borderRadius: "8px 0 4px 0",
            padding: "2px 6px",
            fontSize: 11,
            color: "#93c5fd",
            cursor: "pointer",
            fontWeight: "bold",
            transition: "all 0.15s ease",
          }}
          title={collapsed ? "Expand subtree" : "Collapse subtree"}
        >{collapsed ? "+" : "−"}</div>
      )}
      {isLeaf && (
        <div style={{
          position: "absolute",
          top: -1,
          right: -1,
          background: "#1a2744",
          borderRadius: "0 8px 0 4px",
          padding: "1px 5px",
          fontSize: 8,
          color: "#4a90d9",
          letterSpacing: "0.1em"
        }}>END</div>
      )}
      <div style={{
        fontSize: compact ? 9 : 10.5,
        fontWeight: 700,
        color: inPath ? node.color : hovered ? node.color + "cc" : "#94a3b8",
        lineHeight: 1.35,
        marginBottom: compact ? 3 : 5,
        whiteSpace: "pre-line",
      }}>{node.label.replace(/\\n/g, "\n")}</div>
      <div style={{ fontSize: compact ? 8 : 9.5, color: "#64748b", lineHeight: 1.3, whiteSpace: "pre-line" }}>
        {node.salary.replace(/\\n/g, "\n")}
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: compact ? 4 : 6 }}>
        <div style={{
          fontSize: compact ? 8 : 9,
          color: getProbColor(node.prob),
          background: `${getProbColor(node.prob)}18`,
          borderRadius: 4,
          padding: "1px 5px",
        }}>
          {(node.prob * 100).toFixed(0)}% branch
        </div>
        {cumProb !== null && (
          <div style={{ fontSize: compact ? 8 : 9, color: "#4a5568" }}>
            {(cumProb * 100).toFixed(1)}% overall
          </div>
        )}
      </div>
    </div>
  );
}

function ConnectorArrow() {
  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      minWidth: 24,
      color: "#1e3a5f",
      fontSize: 18,
      flexShrink: 0,
      alignSelf: "center",
    }}>›</div>
  );
}

function PathSummary({ selectedPath, nodes, pathProbs, leafNode }) {
  return (
    <div style={{
      margin: "20px auto",
      maxWidth: 820,
      background: "#0d1424",
      border: "1px solid #1e3a5f",
      borderRadius: 12,
      padding: "18px 22px",
    }}>
      <div style={{ fontSize: 11, letterSpacing: "0.2em", color: "#4a90d9", marginBottom: 12 }}>
        ▸ SELECTED PATH
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center", marginBottom: 14 }}>
        <Chip label="START · 220K PKR" color="#00ff9f" />
        {selectedPath.map((id, i) => {
          const n = nodes[id];
          return (
            <div key={id} style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ color: "#334155", fontSize: 16 }}>→</span>
              <Chip
                label={n.label.replace(/\\n/g, " · ")}
                color={n.color}
                sub={`${(pathProbs[i] * 100).toFixed(1)}% cumulative`}
              />
            </div>
          );
        })}
      </div>

      {leafNode && (
        <div style={{
          background: "#111827",
          borderRadius: 8,
          padding: "14px 16px",
          borderLeft: `3px solid ${leafNode.color}`,
        }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: leafNode.color, marginBottom: 6 }}>
            FINAL OUTCOME: {leafNode.label.replace(/\\n/g, " ")}
          </div>
          <div style={{ fontSize: 13, color: "#94a3b8", marginBottom: 4 }}>
            💰 Salary: <span style={{ color: "#e2e8f0" }}>{leafNode.salary.replace(/\\n/g, " · ")}</span>
          </div>
          <div style={{ fontSize: 12, color: "#64748b", lineHeight: 1.6 }}>{leafNode.note}</div>
          <div style={{ marginTop: 10, fontSize: 11, color: "#4a5568" }}>
            Probability of this exact path: <span style={{ color: "#fdcb6e", fontWeight: 700 }}>
              {(pathProbs[pathProbs.length - 1] * 100).toFixed(1)}%
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

function HoverTooltip({ node }) {
  return (
    <div style={{
      position: "fixed",
      bottom: 24,
      left: "50%",
      transform: "translateX(-50%)",
      background: "#111827",
      border: `1px solid ${node.color}`,
      borderRadius: 10,
      padding: "12px 18px",
      maxWidth: 460,
      fontSize: 12,
      color: "#94a3b8",
      lineHeight: 1.6,
      zIndex: 100,
      pointerEvents: "none",
      boxShadow: "0 8px 32px rgba(0,0,0,0.6)",
    }}>
      <span style={{ color: node.color, fontWeight: 700 }}>
        {node.label.replace(/\\n/g, " ")}
      </span><br />
      {node.note}
    </div>
  );
}

function Chip({ label, color, sub }) {
  return (
    <div style={{
      background: `${color}18`,
      border: `1px solid ${color}55`,
      borderRadius: 6,
      padding: "4px 10px",
      display: "inline-flex",
      flexDirection: "column",
    }}>
      <span style={{ fontSize: 11, color, fontWeight: 600 }}>{label}</span>
      {sub && <span style={{ fontSize: 9, color: "#4a5568" }}>{sub}</span>}
    </div>
  );
}
