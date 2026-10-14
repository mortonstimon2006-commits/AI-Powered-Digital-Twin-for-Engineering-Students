import { Html, OrbitControls } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

import { CATEGORY_COLOR, CATEGORY_LABEL } from "@/lib/utils";

export interface TwinAxis {
  category: string;
  level: number | null; // student's evidence-weighted level (null = unknown)
  required: number | null; // max level required by the target role in this category
}

const radius = (lvl: number) => 0.55 + lvl * 0.62;

function Spoke({ axis, angle, active, onHover }: { axis: TwinAxis; angle: number; active: boolean; onHover: (h: boolean) => void }) {
  const color = CATEGORY_COLOR[axis.category] ?? "#a3b0c6";
  const dir = new THREE.Vector3(Math.cos(angle), 0, Math.sin(angle));
  const end = dir.clone().multiplyScalar(radius(4));
  const known = axis.level !== null;
  const pos = dir.clone().multiplyScalar(known ? radius(axis.level ?? 0) : 0.9);
  const req = axis.required !== null ? dir.clone().multiplyScalar(radius(axis.required)) : null;
  const line = useMemo(() => {
    const geom = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0, 0), end]);
    return new THREE.Line(geom, new THREE.LineBasicMaterial({ color: "#31405e", transparent: true, opacity: 0.8 }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [angle]);
  useEffect(() => () => {
    line.geometry.dispose();
    (line.material as THREE.Material).dispose();
  }, [line]);
  return (
    <group>
      <primitive object={line} />
      {req && (
        <mesh position={req} rotation={[0, -angle, Math.PI / 2]}>
          <torusGeometry args={[0.2, 0.018, 8, 40]} />
          <meshBasicMaterial color="#e8edf6" transparent opacity={0.55} />
        </mesh>
      )}
      <mesh position={pos} onPointerOver={(e) => (e.stopPropagation(), onHover(true))} onPointerOut={() => onHover(false)}>
        <sphereGeometry args={[known ? 0.17 : 0.13, 24, 24]} />
        {known ? (
          <meshStandardMaterial color={color} emissive={color} emissiveIntensity={active ? 1.5 : 0.75} roughness={0.3} />
        ) : (
          <meshBasicMaterial color={color} wireframe transparent opacity={0.6} />
        )}
        <Html center distanceFactor={7} position={[0, 0.38, 0]} style={{ pointerEvents: "none" }}>
          <span className="whitespace-nowrap rounded-md bg-ink-850/85 px-2 py-0.5 text-[11px] text-fg">
            {CATEGORY_LABEL[axis.category] ?? axis.category}
            {active && (
              <span className="ml-1.5 font-mono text-fg-muted">
                {known ? axis.level!.toFixed(1) : "unknown"}
                {axis.required !== null ? ` / req ${axis.required}` : ""}
              </span>
            )}
          </span>
        </Html>
      </mesh>
    </group>
  );
}

function Core({ axes, animate }: { axes: TwinAxis[]; animate: boolean }) {
  const group = useRef<THREE.Group>(null);
  const core = useRef<THREE.Mesh>(null);
  const [active, setActive] = useState<number | null>(null);
  useFrame(({ clock }, dt) => {
    if (!animate) return;
    if (group.current && active === null) group.current.rotation.y += dt * 0.12;
    if (core.current) core.current.scale.setScalar(1 + Math.sin(clock.elapsedTime * 1.6) * 0.04);
  });
  const known = axes.filter((a) => a.level !== null);
  const shape = new THREE.Shape();
  axes.forEach((a, i) => {
    const t = (i / axes.length) * Math.PI * 2;
    const r = radius(a.level ?? 0);
    const x = Math.cos(t) * r;
    const y = Math.sin(t) * r;
    if (i === 0) shape.moveTo(x, y);
    else shape.lineTo(x, y);
  });
  return (
    <group ref={group}>
      <mesh ref={core}>
        <icosahedronGeometry args={[0.38, 2]} />
        <meshStandardMaterial color="#5eead4" emissive="#5eead4" emissiveIntensity={0.9} wireframe />
      </mesh>
      {known.length >= 3 && (
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <shapeGeometry args={[shape]} />
          <meshBasicMaterial color="#a78bfa" transparent opacity={0.12} side={THREE.DoubleSide} />
        </mesh>
      )}
      {axes.map((a, i) => (
        <Spoke key={a.category} axis={a} angle={(i / axes.length) * Math.PI * 2} active={active === i} onHover={(h) => setActive(h ? i : null)} />
      ))}
    </group>
  );
}

export default function TwinCore({ axes, animate }: { axes: TwinAxis[]; animate: boolean }) {
  return (
    <Canvas dpr={[1, 1.75]} camera={{ position: [0, 4.6, 5.6], fov: 45 }} frameloop={animate ? "always" : "demand"} role="img"
      aria-label="3D view of your skill levels by category compared with your target role">
      <ambientLight intensity={0.6} />
      <pointLight position={[3, 5, 3]} intensity={25} color="#a78bfa" />
      <pointLight position={[-4, 2, -3]} intensity={20} color="#5eead4" />
      <Core axes={axes} animate={animate} />
      <OrbitControls enablePan={false} enableZoom={false} maxPolarAngle={Math.PI / 2.1} enableDamping />
    </Canvas>
  );
}
