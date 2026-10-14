import { Html, OrbitControls } from "@react-three/drei";
import { Canvas } from "@react-three/fiber";
import { useMemo, useState } from "react";
import * as THREE from "three";

import type { GraphEdge, GraphNode } from "@/lib/types";

import { edgeColor, nodeColor, nodeSize } from "./graphStyle";

const SCALE = 6;

function EdgeSet({ nodes, edges, highlight, dashed }: { nodes: Map<string, GraphNode>; edges: GraphEdge[]; highlight: string | null; dashed: boolean }) {
  const obj = useMemo(() => {
    const pos: number[] = [];
    const col: number[] = [];
    for (const e of edges) {
      const a = nodes.get(e.source);
      const b = nodes.get(e.target);
      if (!a || !b) continue;
      const c = new THREE.Color(edgeColor(e));
      const on = highlight !== null && (e.source === highlight || e.target === highlight);
      const k = highlight === null ? 0.55 : on ? 1 : 0.12;
      pos.push(...a.position.map((v) => v * SCALE), ...b.position.map((v) => v * SCALE));
      col.push(c.r * k, c.g * k, c.b * k, c.r * k, c.g * k, c.b * k);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
    g.setAttribute("color", new THREE.Float32BufferAttribute(col, 3));
    const mat = dashed
      ? new THREE.LineDashedMaterial({ vertexColors: true, dashSize: 0.18, gapSize: 0.14, transparent: true, opacity: 0.95 })
      : new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.9 });
    const seg = new THREE.LineSegments(g, mat);
    if (dashed) seg.computeLineDistances();
    return seg;
  }, [nodes, edges, highlight, dashed]);
  return <primitive object={obj} />;
}

export default function Graph3D({
  nodes,
  edges,
  selected,
  onSelect,
}: {
  nodes: GraphNode[];
  edges: GraphEdge[];
  selected: string | null;
  onSelect: (id: string | null) => void;
}) {
  const [hover, setHover] = useState<string | null>(null);
  const byId = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);
  const highlight = hover ?? selected;
  const solid = edges.filter((e) => e.provenance !== "inferred");
  const inferred = edges.filter((e) => e.provenance === "inferred");
  return (
    <Canvas dpr={[1, 1.75]} camera={{ position: [0, 0, 16], fov: 50 }} frameloop="demand" onPointerMissed={() => onSelect(null)}
      role="img" aria-label="Interactive 3D knowledge graph of your skills, roles and resources">
      <color attach="background" args={["#060912"]} />
      <ambientLight intensity={0.7} />
      <pointLight position={[6, 8, 10]} intensity={60} />
      <EdgeSet nodes={byId} edges={solid} highlight={highlight} dashed={false} />
      <EdgeSet nodes={byId} edges={inferred} highlight={highlight} dashed />
      {nodes.map((n) => {
        const color = nodeColor(n);
        const active = n.id === highlight;
        return (
          <mesh
            key={n.id}
            position={n.position.map((v) => v * SCALE) as [number, number, number]}
            onPointerOver={(e) => (e.stopPropagation(), setHover(n.id))}
            onPointerOut={() => setHover(null)}
            onClick={(e) => (e.stopPropagation(), onSelect(n.id))}
          >
            {n.type === "role" ? <octahedronGeometry args={[nodeSize(n)]} /> : <sphereGeometry args={[nodeSize(n), 16, 16]} />}
            {n.type === "skill" && n.status === "unknown" ? (
              <meshBasicMaterial color={color} wireframe />
            ) : (
              <meshStandardMaterial color={color} emissive={color} emissiveIntensity={active ? 1.4 : 0.45} roughness={0.4} />
            )}
            {(active || n.type === "role" || n.type === "student") && (
              <Html center distanceFactor={14} position={[0, nodeSize(n) + 0.35, 0]} style={{ pointerEvents: "none" }}>
                <span className="whitespace-nowrap rounded-md bg-ink-850/90 px-2 py-0.5 text-[12px] text-fg">{n.label}</span>
              </Html>
            )}
          </mesh>
        );
      })}
      <OrbitControls enableDamping makeDefault />
    </Canvas>
  );
}
