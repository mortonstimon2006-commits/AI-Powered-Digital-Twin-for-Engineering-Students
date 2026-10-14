import { Html, OrbitControls } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { useMemo, useRef, useState } from "react";
import * as THREE from "three";

import type { CareerRole, CatalogueSkill } from "@/lib/types";
import { CATEGORY_COLOR } from "@/lib/utils";

import { constellationLayout, type CNode } from "./constellationLayout";

function Edges({ nodes, edges, active }: { nodes: CNode[]; edges: { a: number; b: number; importance: number }[]; active: number | null }) {
  const geom = useMemo(() => {
    const pos: number[] = [];
    const col: number[] = [];
    const base = new THREE.Color("#5eead4");
    const dim = new THREE.Color("#233049");
    for (const e of edges) {
      const on = active !== null && (e.a === active || e.b === active);
      const c = on ? base : dim.clone().lerp(base, e.importance * 0.25);
      pos.push(...nodes[e.a]!.position, ...nodes[e.b]!.position);
      col.push(c.r, c.g, c.b, c.r, c.g, c.b);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
    g.setAttribute("color", new THREE.Float32BufferAttribute(col, 3));
    return g;
  }, [nodes, edges, active]);
  return (
    <lineSegments geometry={geom}>
      <lineBasicMaterial vertexColors transparent opacity={active === null ? 0.35 : 0.8} />
    </lineSegments>
  );
}

function Scene({ roles, skills, animate }: { roles: CareerRole[]; skills: CatalogueSkill[]; animate: boolean }) {
  const { nodes, edges } = useMemo(() => constellationLayout(roles, skills), [roles, skills]);
  const group = useRef<THREE.Group>(null);
  const [hover, setHover] = useState<number | null>(null);
  useFrame((_, dt) => {
    if (animate && group.current && hover === null) group.current.rotation.y += dt * 0.06;
  });
  return (
    <group ref={group}>
      <Edges nodes={nodes} edges={edges} active={hover} />
      {nodes.map((n, i) => {
        const isRole = n.kind === "role";
        const color = isRole ? "#e8edf6" : (CATEGORY_COLOR[n.category ?? ""] ?? "#a3b0c6");
        const r = isRole ? 0.22 : 0.07 + n.degree * 0.012;
        return (
          <mesh
            key={n.id}
            position={n.position}
            onPointerOver={(e) => {
              e.stopPropagation();
              setHover(i);
            }}
            onPointerOut={() => setHover(null)}
          >
            <sphereGeometry args={[r, isRole ? 24 : 12, isRole ? 24 : 12]} />
            <meshStandardMaterial color={color} emissive={color} emissiveIntensity={hover === i ? 1.4 : isRole ? 0.6 : 0.45} roughness={0.35} />
            {(isRole || hover === i) && (
              <Html center distanceFactor={9} style={{ pointerEvents: "none" }} position={[0, r + 0.22, 0]}>
                <span className={`whitespace-nowrap rounded-md px-2 py-0.5 font-display ${isRole ? "text-[13px] text-fg" : "bg-ink-850/90 text-[11px] text-fg-muted"}`}>
                  {n.label}
                </span>
              </Html>
            )}
          </mesh>
        );
      })}
    </group>
  );
}

export default function SkillConstellation({ roles, skills, animate }: { roles: CareerRole[]; skills: CatalogueSkill[]; animate: boolean }) {
  return (
    <Canvas
      dpr={[1, 1.75]}
      camera={{ position: [0, 3.2, 9.5], fov: 45 }}
      frameloop={animate ? "always" : "demand"}
      gl={{ antialias: true, powerPreference: "low-power" }}
      aria-label="3D map of career roles and the skills they require"
      role="img"
    >
      <color attach="background" args={["#060912"]} />
      <fog attach="fog" args={["#060912", 9, 18]} />
      <ambientLight intensity={0.5} />
      <pointLight position={[0, 6, 4]} intensity={30} color="#a78bfa" />
      <pointLight position={[-5, -2, -3]} intensity={20} color="#5eead4" />
      <Scene roles={roles} skills={skills} animate={animate} />
      <OrbitControls enablePan={false} enableZoom={false} autoRotate={false} enableDamping />
    </Canvas>
  );
}
