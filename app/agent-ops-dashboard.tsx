"use client";

import {
  Activity,
  ArrowRight,
  Bot,
  Boxes,
  Braces,
  Check,
  CheckCircle2,
  ChevronDown,
  CircleDollarSign,
  Clock3,
  CloudCog,
  Command,
  Database,
  Hexagon,
  LayoutDashboard,
  ListTree,
  LockKeyhole,
  MessageSquareText,
  MoreHorizontal,
  Play,
  Plus,
  Radio,
  RefreshCcw,
  Search,
  ShieldCheck,
  Sparkles,
  TerminalSquare,
  TimerReset,
  TrendingUp,
  UsersRound,
  Wrench,
  XCircle,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useEffect, useMemo, useState } from "react";

type View = "overview" | "playground" | "runs" | "tools" | "settings";

type TraceStep = {
  id: string;
  kind: "reasoning" | "tool" | "response";
  title: string;
  subtitle: string;
  duration: string;
  detail: string;
  status: "complete" | "running" | "queued";
};

type ApiRun = {
  id: string;
  status: string;
  answer: string;
  input_tokens: number;
  output_tokens: number;
  cached_tokens: number;
  cost_usd: string;
  latency_ms: number;
  steps: Array<{
    id: string;
    kind: "model" | "tool";
    name: string;
    status: string;
    arguments: Record<string, unknown> | null;
    output: Record<string, unknown> | null;
    duration_ms: number | null;
  }>;
};

const usageData = [
  { day: "Mon", cost: 1.82, runs: 118 },
  { day: "Tue", cost: 2.48, runs: 147 },
  { day: "Wed", cost: 2.16, runs: 132 },
  { day: "Thu", cost: 3.22, runs: 186 },
  { day: "Fri", cost: 2.74, runs: 164 },
  { day: "Sat", cost: 2.31, runs: 141 },
  { day: "Sun", cost: 3.69, runs: 202 },
];

const toolMix = [
  { name: "Orders", calls: 312 },
  { name: "Revenue", calls: 244 },
  { name: "Customers", calls: 198 },
  { name: "Knowledge", calls: 156 },
  { name: "Inventory", calls: 89 },
];

const runs = [
  { id: "run_9f21", tenant: "Northstar Retail", prompt: "Explain yesterday's revenue drop", status: "Completed", steps: 4, model: "deterministic-demo", cost: "$0.0412", latency: "2.8s", time: "2 min ago" },
  { id: "run_9f20", tenant: "Luma Commerce", prompt: "Find at-risk VIP customers", status: "Completed", steps: 3, model: "deterministic-demo", cost: "$0.0274", latency: "2.1s", time: "8 min ago" },
  { id: "run_9f1f", tenant: "Atlas Supply", prompt: "Summarize delayed fulfillment", status: "Completed", steps: 5, model: "deterministic-demo", cost: "$0.0189", latency: "3.4s", time: "16 min ago" },
  { id: "run_9f1e", tenant: "Northstar Retail", prompt: "Compare refund rate by channel", status: "Guarded", steps: 8, model: "deterministic-demo", cost: "$0.0621", latency: "8.0s", time: "31 min ago" },
  { id: "run_9f1d", tenant: "Orchid Labs", prompt: "Create a weekly support brief", status: "Failed", steps: 2, model: "deterministic-demo", cost: "$0.0068", latency: "1.4s", time: "42 min ago" },
];

const tools = [
  {
    name: "search_orders",
    description: "Search orders with tenant-safe filters and aggregate totals.",
    icon: Search,
    calls: "312 calls",
    latency: "184ms p95",
    properties: ["status", "channel", "date_from", "date_to"],
  },
  {
    name: "get_revenue_summary",
    description: "Return gross sales, refunds, net revenue, and period comparison.",
    icon: TrendingUp,
    calls: "244 calls",
    latency: "126ms p95",
    properties: ["period", "compare_with", "group_by"],
  },
  {
    name: "get_customer_health",
    description: "Surface segments, churn signals, support risk, and LTV bands.",
    icon: UsersRound,
    calls: "198 calls",
    latency: "211ms p95",
    properties: ["segment", "risk_level", "limit"],
  },
  {
    name: "search_knowledge",
    description: "Retrieve grounded operating policy and catalog context.",
    icon: Database,
    calls: "156 calls",
    latency: "238ms p95",
    properties: ["query", "collection", "top_k"],
  },
  {
    name: "get_inventory_alerts",
    description: "Find low-stock, oversold, and fulfillment-risk SKUs.",
    icon: Boxes,
    calls: "89 calls",
    latency: "163ms p95",
    properties: ["warehouse", "severity", "limit"],
  },
];

const baseTrace: TraceStep[] = [
  {
    id: "reason",
    kind: "reasoning",
    title: "Plan the investigation",
    subtitle: "Model decision",
    duration: "420ms",
    detail: "Compare revenue with the prior day, then inspect channel-level orders and customer impact before explaining the change.",
    status: "complete",
  },
  {
    id: "revenue",
    kind: "tool",
    title: "get_revenue_summary",
    subtitle: "Structured function call",
    duration: "126ms",
    detail: '{ "period": "yesterday", "compare_with": "previous_day", "group_by": "channel" }',
    status: "complete",
  },
  {
    id: "orders",
    kind: "tool",
    title: "search_orders",
    subtitle: "Dependent function call",
    duration: "184ms",
    detail: '{ "status": "refunded", "channel": "all", "date_from": "2026-07-24", "date_to": "2026-07-25" }',
    status: "complete",
  },
  {
    id: "customers",
    kind: "tool",
    title: "get_customer_health",
    subtitle: "Dependent function call",
    duration: "211ms",
    detail: '{ "segment": "repeat_buyers", "risk_level": "high", "limit": 20 }',
    status: "complete",
  },
  {
    id: "answer",
    kind: "response",
    title: "Grounded final answer",
    subtitle: "3 tool outputs synthesized",
    duration: "782ms",
    detail: "Revenue declined 12.4%, primarily from Amazon UK refunds and delayed Shopify fulfillment. No broad customer-health regression was detected.",
    status: "complete",
  },
];

const navItems = [
  { id: "overview" as const, label: "Overview", icon: LayoutDashboard },
  { id: "playground" as const, label: "Playground", icon: MessageSquareText },
  { id: "runs" as const, label: "Runs", icon: ListTree, badge: "12" },
  { id: "tools" as const, label: "Tool registry", icon: Wrench },
  { id: "settings" as const, label: "Guardrails", icon: ShieldCheck },
];

function StatusDot({ tone = "green" }: { tone?: "green" | "amber" | "red" }) {
  return <span className={`status-dot status-dot-${tone}`} aria-hidden="true" />;
}

function Brand() {
  return (
    <div className="brand">
      <div className="brand-mark"><Hexagon size={20} strokeWidth={2.2} /><span>A</span></div>
      <div><strong>AgentOps</strong><small>STUDIO</small></div>
    </div>
  );
}

function Sidebar({ view, onChange }: { view: View; onChange: (view: View) => void }) {
  return (
    <aside className="sidebar">
      <Brand />
      <div className="workspace-switcher">
        <div className="workspace-avatar">N</div>
        <div><span>Northstar Labs</span><small>Synthetic demo</small></div>
        <ChevronDown size={15} />
      </div>
      <nav className="nav" aria-label="Main navigation">
        <p className="nav-label">OPERATE</p>
        {navItems.slice(0, 3).map((item) => {
          const Icon = item.icon;
          return (
            <button key={item.id} className={view === item.id ? "nav-item active" : "nav-item"} onClick={() => onChange(item.id)}>
              <Icon size={18} />
              <span>{item.label}</span>
              {item.badge && <em>{item.badge}</em>}
            </button>
          );
        })}
        <p className="nav-label nav-label-spaced">BUILD</p>
        {navItems.slice(3).map((item) => {
          const Icon = item.icon;
          return (
            <button key={item.id} className={view === item.id ? "nav-item active" : "nav-item"} onClick={() => onChange(item.id)}>
              <Icon size={18} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>
      <div className="sidebar-foot">
        <div className="plan-row"><span>Monthly budget</span><strong>$18.42 / $75</strong></div>
        <div className="budget-track"><span /></div>
        <button className="profile-row">
          <div className="profile-avatar">SZ</div>
          <div><strong>Sijie Zhang</strong><small>Workspace admin</small></div>
          <MoreHorizontal size={17} />
        </button>
      </div>
    </aside>
  );
}

function Header({ view }: { view: View }) {
  const labels: Record<View, string> = {
    overview: "Operations overview",
    playground: "Agent playground",
    runs: "Run explorer",
    tools: "Tool registry",
    settings: "Guardrails & limits",
  };
  return (
    <header className="topbar">
      <div><span className="breadcrumb">AgentOps /</span><strong>{labels[view]}</strong></div>
      <div className="top-actions">
        <div className="live-pill"><StatusDot /> All systems operational</div>
        <button className="icon-button" aria-label="Open command menu"><Command size={17} /><kbd>⌘ K</kbd></button>
        <button className="primary-button"><Plus size={16} /> New run</button>
      </div>
    </header>
  );
}

function MetricCard({ label, value, delta, icon: Icon, accent }: { label: string; value: string; delta: string; icon: typeof Activity; accent: string }) {
  return (
    <article className="metric-card">
      <div className="metric-head"><span>{label}</span><div className={`metric-icon ${accent}`}><Icon size={18} /></div></div>
      <div className="metric-value">{value}</div>
      <div className="metric-foot"><TrendingUp size={14} /><strong>{delta}</strong><span>vs last week</span></div>
    </article>
  );
}

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ value: number; name: string }>; label?: string }) {
  if (!active || !payload?.length) return null;
  return <div className="chart-tooltip"><strong>{label}</strong><span>${payload[0].value.toFixed(2)} model cost</span></div>;
}

function RunStatus({ status }: { status: string }) {
  const tone = status === "Completed" ? "success" : status === "Guarded" ? "guarded" : "failed";
  return <span className={`run-status ${tone}`}>{status === "Completed" ? <Check size={13} /> : status === "Guarded" ? <ShieldCheck size={13} /> : <XCircle size={13} />}{status}</span>;
}

function RunsTable({ expanded = false }: { expanded?: boolean }) {
  const visibleRuns = expanded ? runs : runs.slice(0, 4);
  return (
    <div className="table-wrap">
      <table>
        <thead><tr><th>Run</th><th>Tenant</th><th>Status</th><th>Steps</th>{expanded && <th>Model</th>}<th>Cost</th><th>Latency</th><th>Started</th></tr></thead>
        <tbody>
          {visibleRuns.map((run) => (
            <tr key={run.id}>
              <td><div className="run-cell"><span>{run.id}</span><small>{run.prompt}</small></div></td>
              <td>{run.tenant}</td>
              <td><RunStatus status={run.status} /></td>
              <td><span className="step-count">{run.steps}</span></td>
              {expanded && <td><code>{run.model}</code></td>}
              <td>{run.cost}</td><td>{run.latency}</td><td className="muted-cell">{run.time}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Overview({ onView }: { onView: (view: View) => void }) {
  return (
    <div className="page-content">
      <section className="page-intro">
        <div><p className="eyebrow"><Sparkles size={14} /> CONTROL PLANE</p><h1>See what every agent is doing.<br /><span>Know what every answer costs.</span></h1><p>Trace multi-step decisions, inspect tool outputs, and keep every tenant inside reliable cost and safety boundaries.</p></div>
        <div className="intro-actions"><button className="secondary-button"><RefreshCcw size={16} /> Sync data</button><button className="primary-button" onClick={() => onView("playground")}><Play size={16} fill="currentColor" /> Open playground</button></div>
      </section>

      <section className="metric-grid">
        <MetricCard label="Agent runs" value="1,090" delta="18.6%" icon={Activity} accent="violet" />
        <MetricCard label="Model spend" value="$18.42" delta="8.2%" icon={CircleDollarSign} accent="lime" />
        <MetricCard label="Tokens processed" value="1.24M" delta="21.4%" icon={Braces} accent="cyan" />
        <MetricCard label="Successful runs" value="98.7%" delta="1.2%" icon={CheckCircle2} accent="blue" />
      </section>

      <section className="analytics-grid">
        <article className="panel usage-panel">
          <div className="panel-head"><div><p className="panel-kicker">USAGE & COST</p><h2>Seven-day model spend</h2></div><button className="range-button">Last 7 days <ChevronDown size={14} /></button></div>
          <div className="chart-summary"><strong>$18.42</strong><span><TrendingUp size={13} /> 8.2%</span><small>Across 1,090 synthetic demo runs</small></div>
          <div className="main-chart">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={usageData} margin={{ top: 8, right: 4, left: -24, bottom: 0 }}>
                <defs><linearGradient id="costGradient" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#9bf56f" stopOpacity={0.35}/><stop offset="100%" stopColor="#9bf56f" stopOpacity={0}/></linearGradient></defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,.07)" />
                <XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fill: "#7f899b", fontSize: 11 }} />
                <YAxis axisLine={false} tickLine={false} tick={{ fill: "#7f899b", fontSize: 11 }} tickFormatter={(v) => `$${v}`} />
                <Tooltip content={<ChartTooltip />} cursor={{ stroke: "rgba(155,245,111,.25)" }} />
                <Area type="monotone" dataKey="cost" stroke="#9bf56f" strokeWidth={2.5} fill="url(#costGradient)" activeDot={{ r: 5, fill: "#9bf56f", stroke: "#10151e", strokeWidth: 3 }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </article>

        <article className="panel tool-panel">
          <div className="panel-head"><div><p className="panel-kicker">TOOL TRAFFIC</p><h2>Calls by operation</h2></div><button className="icon-button small"><MoreHorizontal size={17} /></button></div>
          <div className="tool-chart">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={toolMix} layout="vertical" margin={{ left: 5, right: 8, top: 8, bottom: 0 }}>
                <XAxis type="number" hide />
                <YAxis type="category" dataKey="name" axisLine={false} tickLine={false} width={72} tick={{ fill: "#aeb7c6", fontSize: 11 }} />
                <Bar dataKey="calls" fill="#8e7dff" radius={[0, 5, 5, 0]} barSize={13} background={{ fill: "rgba(255,255,255,.045)", radius: 5 }} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="tool-total"><div><Wrench size={16} /><span>999 tool calls</span></div><small>0.8% retry rate</small></div>
        </article>
      </section>

      <section className="reliability-row">
        <article className="reliability-card"><div className="ring ring-green"><span>98.7<small>%</small></span></div><div><p>Run success rate</p><strong>Above 97% SLO</strong><small>14 guarded · 9 failed</small></div></article>
        <article className="reliability-card"><div className="ring ring-violet"><span>842<small>ms</small></span></div><div><p>Model latency p95</p><strong>Within 1.2s target</strong><small>Tool p95 is 238ms</small></div></article>
        <article className="reliability-card guard-card"><div className="guard-icon"><ShieldCheck size={23} /></div><div><p>Guardrail coverage</p><strong>5 policies enforced</strong><small>Step, repeat, budget, timeout, schema</small></div><span className="healthy-label"><StatusDot /> Healthy</span></article>
      </section>

      <section className="panel recent-panel">
        <div className="panel-head"><div><p className="panel-kicker">LIVE ACTIVITY</p><h2>Recent agent runs</h2></div><button className="text-button" onClick={() => onView("runs")}>Explore all runs <ArrowRight size={15} /></button></div>
        <RunsTable />
      </section>
    </div>
  );
}

function TraceIcon({ step }: { step: TraceStep }) {
  if (step.status === "running") return <span className="trace-spinner" />;
  if (step.status === "queued") return <Clock3 size={15} />;
  if (step.kind === "tool") return <TerminalSquare size={15} />;
  if (step.kind === "response") return <Sparkles size={15} />;
  return <Bot size={15} />;
}

function Playground({ apiUrl }: { apiUrl?: string }) {
  const [message, setMessage] = useState("Why did revenue drop yesterday, and which customers need attention?");
  const [running, setRunning] = useState(false);
  const [trace, setTrace] = useState<TraceStep[]>(baseTrace);
  const [showAnswer, setShowAnswer] = useState(true);
  const [answer, setAnswer] = useState("Revenue declined 12.4%, primarily from Amazon UK refunds and delayed Shopify fulfillment. Six repeat buyers need proactive outreach, but overall customer health remains stable.");
  const [runMeta, setRunMeta] = useState({ id: "run_9f21", latency: "2.8s", input: "3,842", output: "618", cached: "1,204", cost: "$0.0412" });

  const animateDemo = () => {
    baseTrace.forEach((_, index) => {
      window.setTimeout(() => {
        setTrace((current) => current.map((step, stepIndex) => ({ ...step, status: stepIndex <= index ? "complete" : stepIndex === index + 1 ? "running" : "queued" })));
        if (index === baseTrace.length - 1) {
          setShowAnswer(true);
          setRunning(false);
        }
      }, 520 + index * 560);
    });
  };

  const runAgent = async () => {
    if (running || !message.trim()) return;
    setRunning(true);
    setShowAnswer(false);
    setTrace(baseTrace.map((step, index) => ({ ...step, status: index === 0 ? "running" : "queued" })));
    if (!apiUrl) {
      animateDemo();
      return;
    }
    try {
      const conversationResponse = await fetch(`${apiUrl}/api/v1/conversations`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Tenant-ID": "tenant_northstar" },
        body: JSON.stringify({ title: "Live operations investigation" }),
      });
      if (!conversationResponse.ok) throw new Error("Could not create conversation");
      const conversation = await conversationResponse.json() as { id: string };
      const runResponse = await fetch(`${apiUrl}/api/v1/conversations/${conversation.id}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Tenant-ID": "tenant_northstar" },
        body: JSON.stringify({ content: message }),
      });
      if (!runResponse.ok) throw new Error("Agent run failed");
      const payload = await runResponse.json() as { run: ApiRun };
      const run = payload.run;
      const liveTrace: TraceStep[] = run.steps.map((step, index) => {
        const isFinal = step.kind === "model" && index === run.steps.length - 1;
        return {
          id: step.id,
          kind: isFinal ? "response" : step.kind === "tool" ? "tool" : "reasoning",
          title: isFinal ? "Grounded final answer" : step.kind === "tool" ? step.name : "Model decision",
          subtitle: step.kind === "tool" ? "Structured function call" : isFinal ? "Tool outputs synthesized" : "Reason over current context",
          duration: `${step.duration_ms ?? 0}ms`,
          detail: step.kind === "tool" ? JSON.stringify(step.arguments) : isFinal ? run.answer : `Selected next action at step ${index + 1}`,
          status: "complete",
        };
      });
      setTrace(liveTrace);
      setAnswer(run.answer);
      setRunMeta({
        id: run.id,
        latency: `${(run.latency_ms / 1000).toFixed(2)}s`,
        input: run.input_tokens.toLocaleString(),
        output: run.output_tokens.toLocaleString(),
        cached: run.cached_tokens.toLocaleString(),
        cost: `$${Number(run.cost_usd).toFixed(4)}`,
      });
      setShowAnswer(true);
    } catch {
      setAnswer("The live API was unavailable, so AgentOps switched this run back to the deterministic demonstration trace.");
      animateDemo();
      return;
    }
    setRunning(false);
  };

  return (
    <div className="playground-page">
      <section className="playground-main">
        <div className="playground-head">
          <div><p className="eyebrow"><Radio size={14} /> LIVE ORCHESTRATION</p><h1>Revenue investigation</h1><p>Conversation <code>conv_7d32ac</code> · Northstar Retail</p></div>
          <div className="model-select"><span>MODEL</span><strong>deterministic-demo</strong><ChevronDown size={14} /></div>
        </div>
        <div className="chat-canvas">
          <div className="chat-date">TODAY, 09:42</div>
          <div className="message user-message"><div className="message-avatar user-avatar">SZ</div><div><span>You</span><p>{message}</p></div></div>
          {(running || showAnswer) && <div className="message agent-message"><div className="message-avatar agent-avatar"><Bot size={17} /></div><div><span>Operations copilot</span>{showAnswer ? <div className="answer-card"><p>{answer}</p><div className="evidence-row"><span><CheckCircle2 size={14} /> {trace.filter((step) => step.kind === "tool").length} sources verified</span><span><Clock3 size={14} /> {runMeta.latency}</span><span><CircleDollarSign size={14} /> {runMeta.cost}</span></div></div> : <div className="thinking-card"><span className="thinking-orb" /><div><strong>Working through the plan</strong><small>Executing tenant-scoped tools…</small></div></div>}</div></div>}
        </div>
        <div className="prompt-composer">
          <div className="suggestions"><button onClick={() => setMessage("Compare refund rate across Shopify, Amazon UK, and WooCommerce.")}>Compare refund channels</button><button onClick={() => setMessage("Which delayed orders are likely to impact our highest-value customers?")}>Find high-risk orders</button></div>
          <div className="composer-box"><textarea aria-label="Message the operations copilot" value={message} onChange={(event) => setMessage(event.target.value)} /><div className="composer-foot"><div><button className="mini-control"><Plus size={15} /></button><span>5 tools available</span></div><button className="send-button" onClick={() => void runAgent()} disabled={running}>{running ? <span className="button-spinner" /> : <ArrowRight size={17} />}</button></div></div>
          <p className="composer-note"><LockKeyhole size={12} /> Tenant context and tool outputs are isolated by workspace.</p>
        </div>
      </section>
      <aside className="trace-panel">
        <div className="trace-head"><div><p className="panel-kicker">EXECUTION TRACE</p><h2>Run graph</h2></div><span className={running ? "trace-live active" : "trace-live"}><StatusDot tone={running ? "amber" : "green"} />{running ? "Running" : "Complete"}</span></div>
        <div className="run-meta"><div><span>RUN ID</span><code>{runMeta.id}</code></div><div><span>TOTAL</span><strong>{running ? "—" : runMeta.latency}</strong></div><div><span>STEPS</span><strong>{running ? trace.filter((step) => step.status === "complete").length : trace.length} / {trace.length}</strong></div></div>
        <div className="trace-list">
          {trace.map((step, index) => (
            <div className={`trace-item ${step.status}`} key={step.id}>
              <div className="trace-rail"><div className={`trace-node ${step.kind}`}><TraceIcon step={step} /></div>{index < trace.length - 1 && <span />}</div>
              <div className="trace-content"><div className="trace-title"><div><strong>{step.title}</strong><small>{step.subtitle}</small></div><em>{step.status === "complete" ? step.duration : step.status}</em></div><pre>{step.detail}</pre></div>
            </div>
          ))}
        </div>
        <div className="token-strip"><div><span>INPUT</span><strong>{runMeta.input}</strong></div><div><span>OUTPUT</span><strong>{runMeta.output}</strong></div><div><span>CACHED</span><strong>{runMeta.cached}</strong></div><div><span>COST</span><strong>{runMeta.cost}</strong></div></div>
      </aside>
    </div>
  );
}

function RunsView() {
  return <div className="page-content compact-page"><section className="page-intro"><div><p className="eyebrow"><ListTree size={14} /> TRACE EXPLORER</p><h1>Every run, fully reconstructable.</h1><p>Filter failures, inspect model and tool steps, and replay production incidents without guessing.</p></div><div className="intro-actions"><button className="secondary-button"><Search size={16} /> Filter runs</button><button className="primary-button"><RefreshCcw size={16} /> Replay selected</button></div></section><div className="filter-row"><span className="filter-chip active">All runs <strong>1,090</strong></span><span className="filter-chip">Completed <strong>1,067</strong></span><span className="filter-chip">Guarded <strong>14</strong></span><span className="filter-chip">Failed <strong>9</strong></span><div className="filter-search"><Search size={15}/><input aria-label="Search runs" placeholder="Search run ID or prompt" /></div></div><section className="panel runs-panel"><RunsTable expanded /></section></div>;
}

function ToolsView() {
  return <div className="page-content compact-page"><section className="page-intro"><div><p className="eyebrow"><Wrench size={14} /> STRICT SCHEMAS</p><h1>A tool registry agents can trust.</h1><p>Versioned JSON schemas, tenant-safe execution, typed errors, and latency telemetry for every operation.</p></div><button className="primary-button"><Plus size={16} /> Register tool</button></section><div className="schema-note"><Braces size={18}/><div><strong>Strict mode enabled</strong><span>All object fields are required and <code>additionalProperties</code> is disabled.</span></div><span className="healthy-label"><StatusDot /> Valid</span></div><section className="tool-grid">{tools.map((tool) => { const Icon = tool.icon; return <article className="tool-card" key={tool.name}><div className="tool-card-head"><div className="tool-card-icon"><Icon size={19}/></div><span className="version-pill">v1.4</span></div><code>{tool.name}</code><p>{tool.description}</p><div className="schema-props">{tool.properties.map((property) => <span key={property}>{property}</span>)}</div><div className="tool-card-foot"><span><Activity size={13}/>{tool.calls}</span><span><Clock3 size={13}/>{tool.latency}</span></div></article>; })}</section></div>;
}

function GuardrailsView() {
  const policies = [
    { icon: TimerReset, title: "Maximum loop steps", description: "Stop a run after 8 model turns.", value: "8 steps", tone: "violet" },
    { icon: RefreshCcw, title: "Repeated call detection", description: "Block an identical tool signature after 2 attempts.", value: "2 repeats", tone: "cyan" },
    { icon: CircleDollarSign, title: "Per-run budget", description: "Interrupt requests before model spend exceeds the cap.", value: "$0.25", tone: "lime" },
    { icon: Clock3, title: "Tool timeout", description: "Classify and retry transient tool failures once.", value: "5 seconds", tone: "blue" },
    { icon: Braces, title: "Schema enforcement", description: "Reject unknown fields and malformed arguments.", value: "Strict", tone: "violet" },
  ];
  return <div className="page-content compact-page"><section className="page-intro"><div><p className="eyebrow"><ShieldCheck size={14} /> RELIABILITY ENVELOPE</p><h1>Bounded autonomy by default.</h1><p>Give agents enough room to solve a task without allowing silent loops, runaway spend, or unvalidated actions.</p></div><button className="primary-button"><Check size={16} /> Save policies</button></section><div className="policy-layout"><section className="policy-list">{policies.map((policy) => { const Icon = policy.icon; return <article className="policy-card" key={policy.title}><div className={`metric-icon ${policy.tone}`}><Icon size={18}/></div><div><strong>{policy.title}</strong><p>{policy.description}</p></div><button>{policy.value}<ChevronDown size={14}/></button></article>; })}</section><aside className="panel security-panel"><div className="security-visual"><ShieldCheck size={36}/><span/><span/></div><p className="panel-kicker">LAST 7 DAYS</p><h2>Guardrails stopped 14 unsafe runs</h2><p>Repeated tool calls accounted for 64% of interventions. No tenant crossed its spend budget.</p><div className="security-stat"><span>Repeated calls</span><strong>9</strong></div><div className="security-stat"><span>Step limit</span><strong>3</strong></div><div className="security-stat"><span>Schema violation</span><strong>2</strong></div></aside></div></div>;
}

export function AgentOpsDashboard() {
  const [view, setView] = useState<View>("overview");
  const [apiConnected, setApiConnected] = useState(false);
  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  const title = useMemo(() => navItems.find((item) => item.id === view)?.label ?? "Overview", [view]);

  useEffect(() => {
    if (!apiUrl) return;
    fetch(`${apiUrl}/health`).then((response) => setApiConnected(response.ok)).catch(() => setApiConnected(false));
  }, [apiUrl]);

  return (
    <main className="app-shell">
      <Sidebar view={view} onChange={setView} />
      <section className="main-column" aria-label={title}>
        <Header view={view} />
        {view === "overview" && <Overview onView={setView} />}
        {view === "playground" && <Playground apiUrl={apiConnected ? apiUrl : undefined} />}
        {view === "runs" && <RunsView />}
        {view === "tools" && <ToolsView />}
        {view === "settings" && <GuardrailsView />}
        <div className="connection-badge"><CloudCog size={13}/>{apiConnected ? "FastAPI connected" : "Deterministic demo mode"}</div>
      </section>
    </main>
  );
}
