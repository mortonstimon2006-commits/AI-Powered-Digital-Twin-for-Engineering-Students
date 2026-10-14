import { fireEvent, render, screen } from "@testing-library/react";
import { Tooltip } from "radix-ui";
import { describe, expect, it, vi } from "vitest";

import { Graph2D } from "@/components/three/Graph2D";
import { LevelMeter } from "@/components/ui/primitives";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { ApiError } from "@/lib/api";
import type { GraphEdge, GraphNode } from "@/lib/types";
import { axeViolations } from "@/test/utils";

import { PasswordChecklist } from "./PasswordChecklist";
import { SafeMarkdown } from "./SafeMarkdown";

describe("SafeMarkdown (model output rendering)", () => {
  it("never interprets HTML from the model", () => {
    const { container } = render(<SafeMarkdown text={'<img src=x onerror="alert(1)"> <script>alert(2)</script> **bold**'} />);
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("script")).toBeNull();
    expect(container.textContent).toContain("<img src=x");
    expect(container.querySelector("strong")?.textContent).toBe("bold");
  });

  it("renders lists and clickable citations", () => {
    const onCite = vi.fn();
    render(<SafeMarkdown text={"Do this:\n\n- learn SQL [S1]\n- build a dashboard"} onCite={onCite} />);
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    fireEvent.click(screen.getByRole("button", { name: "Source S1" }));
    expect(onCite).toHaveBeenCalledWith("S1");
  });
});

describe("LevelMeter", () => {
  it("distinguishes unknown from zero", () => {
    render(<><LevelMeter value={null} required={3} /><LevelMeter value={0} /></>);
    expect(screen.getByRole("img", { name: /unknown level, required 3/i })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /level 0 of 4/i })).toBeInTheDocument();
  });
});

describe("states", () => {
  it("shows an offline message with a retry action", () => {
    const retry = vi.fn();
    render(<ErrorState error={new ApiError(0, "network_error", "You appear to be offline.")} onRetry={retry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("You're offline");
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(retry).toHaveBeenCalled();
  });

  it("shows the request reference for server errors", () => {
    render(<ErrorState error={new ApiError(503, "database_unavailable", "Down", undefined, "req-9")} />);
    expect(screen.getByText(/Service unavailable/)).toBeInTheDocument();
    expect(screen.getByText(/req-9/)).toBeInTheDocument();
  });

  it("empty state is accessible", async () => {
    const { container } = render(<EmptyState title="Nothing here">Add something.</EmptyState>);
    expect(await axeViolations(container)).toEqual([]);
  });
});

describe("PasswordChecklist", () => {
  it("reflects the backend policy", () => {
    render(<PasswordChecklist password="password123" email="asha@example.edu" />);
    expect(screen.getByText(/At least 12 characters/).closest("li")).toHaveTextContent("not met");
    expect(screen.getByText(/Not a common password/).closest("li")).toHaveTextContent("not met");
  });
});

describe("Graph2D", () => {
  const nodes: GraphNode[] = [
    { id: "student:me", type: "student", label: "You", position: [0, 0, 0] },
    { id: "skill:1", type: "skill", label: "SQL", position: [1, 1, 0], category: "databases", status: "unknown" },
  ];
  const edges: GraphEdge[] = [{ source: "student:me", target: "skill:1", type: "STUDENT_LIKELY_HAS_SKILL", provenance: "inferred" }];

  it("lets keyboard users select nodes and marks inferred edges as dashed", () => {
    const onSelect = vi.fn();
    const { container } = render(<Tooltip.Provider><Graph2D nodes={nodes} edges={edges} selected={null} onSelect={onSelect} /></Tooltip.Provider>);
    const node = screen.getByRole("button", { name: "skill SQL" });
    node.focus();
    fireEvent.keyDown(node, { key: "Enter" });
    expect(onSelect).toHaveBeenCalledWith("skill:1");
    expect(container.querySelector("line")?.getAttribute("stroke-dasharray")).toBe("5 4");
  });
});

describe("SafeMarkdown links", () => {
  it("renders only https links, safely", () => {
    const { container } = render(<SafeMarkdown text={"See [SQLBolt](https://sqlbolt.com/) and [bad](javascript:alert(1))."} />);
    const links = container.querySelectorAll("a");
    expect(links).toHaveLength(1);
    expect(links[0]!.getAttribute("href")).toBe("https://sqlbolt.com/");
    expect(links[0]!.getAttribute("rel")).toContain("noopener");
    expect(container.textContent).toContain("[bad](javascript:alert(1))");
  });
});
