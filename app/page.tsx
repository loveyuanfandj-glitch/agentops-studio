import type { Metadata } from "next";
import { AgentOpsDashboard } from "./agent-ops-dashboard";

export const metadata: Metadata = {
  title: "AgentOps Studio — AI operations, without the blind spots",
  description:
    "A production-minded control plane for multi-step AI agents, tool traces, tenant usage, cost, and reliability.",
};

export default function Home() {
  return <AgentOpsDashboard />;
}
