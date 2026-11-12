"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Line, PerformanceMonitor } from "@react-three/drei";
import * as THREE from "three";

/**
 * "The Refinery": messy spreadsheet panels (left) → diagnostic core (centre) → clean table (right)
 * with chart fragments rising from it. Simple instanced geometry, no textures, no post-processing.
 */

const BLUE = new THREE.Color("#3B82F6");
const CYAN = new THREE.Color("#22D3EE");
const TEAL = new THREE.Color("#14B8A6");
const VIOLET = new THREE.Color("#8B5CF6");
const AMBER = new THREE.Color("#F59E0B");
const RED = new THREE.Color("#F87171");
const SLATE = new THREE.Color("#64748B");

// Deterministic pseudo-random numbers so the scene is identical on every load.
function rng(seed: number) {
  let s = seed;
  return () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

const COLS = 5;
const ROWS = 11;
const CELL_W = 0.26;
const CELL_H = 0.105;
const GAP_X = 0.31;
const GAP_Y = 0.16;

function Panel({ width = 1.75, height = 2.05, color = "#172033", edge = "#475569", opacity = 0.55 }) {
  const edges = useMemo(() => new THREE.EdgesGeometry(new THREE.PlaneGeometry(width, height)), [width, height]);
  return (
    <group>
      <mesh>
        <planeGeometry args={[width, height]} />
        <meshBasicMaterial color={color} transparent opacity={opacity} side={THREE.DoubleSide} depthWrite={false} />
      </mesh>
      <lineSegments geometry={edges}>
        <lineBasicMaterial color={edge} transparent opacity={0.9} />
      </lineSegments>
    </group>
  );
}

function Cells({ messy }: { messy: boolean }) {
  const ref = useRef<THREE.InstancedMesh>(null);
  const count = COLS * ROWS;
  const data = useMemo(() => {
    const r = rng(messy ? 7 : 11);
    return Array.from({ length: count }, (_, i) => {
      const col = i % COLS;
      const row = Math.floor(i / COLS);
      const bad = messy && r() < 0.11;
      return {
        x: (col - (COLS - 1) / 2) * GAP_X + (messy ? (r() - 0.5) * 0.09 : 0),
        y: ((ROWS - 1) / 2 - row) * GAP_Y + (messy ? (r() - 0.5) * 0.05 : 0),
        rot: messy ? (r() - 0.5) * 0.35 : 0,
        sx: messy ? 0.55 + r() * 0.6 : 1,
        color: bad ? (r() < 0.5 ? AMBER : RED) : messy ? SLATE : col === 0 ? CYAN : row % 2 ? BLUE : TEAL,
        phase: r() * Math.PI * 2,
        bad,
      };
    });
  }, [messy, count]);

  const dummy = useMemo(() => new THREE.Object3D(), []);
  useEffect(() => {
    const mesh = ref.current;
    if (!mesh) return;
    data.forEach((d, i) => {
      dummy.position.set(d.x, d.y, 0.02);
      dummy.rotation.set(0, 0, d.rot);
      dummy.scale.set(d.sx, 1, 1);
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
      mesh.setColorAt(i, d.color);
    });
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  }, [data, dummy]);

  // Messy cells tremble slightly; clean cells stay perfectly still.
  useFrame(({ clock }) => {
    const mesh = ref.current;
    if (!mesh || !messy) return;
    const t = clock.elapsedTime;
    data.forEach((d, i) => {
      dummy.position.set(d.x + Math.sin(t * 0.9 + d.phase) * 0.012, d.y + Math.cos(t * 0.7 + d.phase) * 0.01, 0.02);
      dummy.rotation.set(0, 0, d.rot + Math.sin(t * 0.5 + d.phase) * 0.04);
      dummy.scale.set(d.sx, 1, 1);
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
    });
    mesh.instanceMatrix.needsUpdate = true;
  });

  return (
    <instancedMesh ref={ref} args={[undefined, undefined, count]}>
      <boxGeometry args={[CELL_W, CELL_H, 0.02]} />
      <meshBasicMaterial transparent opacity={messy ? 0.8 : 0.92} toneMapped={false} />
    </instancedMesh>
  );
}

function MessyStack() {
  const group = useRef<THREE.Group>(null);
  useFrame(({ clock }) => {
    if (group.current) group.current.position.y = Math.sin(clock.elapsedTime * 0.55) * 0.05;
  });
  return (
    <group ref={group} position={[-3.05, -0.15, 0]} rotation={[0, 0.36, 0]}>
      <group position={[0.12, -0.1, -0.5]} rotation={[0, 0, -0.16]}>
        <Panel edge="#334155" opacity={0.35} />
      </group>
      <group position={[-0.1, 0.08, -0.25]} rotation={[0, 0, 0.11]}>
        <Panel edge="#475569" opacity={0.45} />
      </group>
      <group rotation={[0, 0, -0.05]}>
        <Panel edge="#64748B" />
        <Cells messy />
      </group>
    </group>
  );
}

function CleanPanel() {
  const group = useRef<THREE.Group>(null);
  useFrame(({ clock }) => {
    if (group.current) group.current.position.y = -0.35 + Math.sin(clock.elapsedTime * 0.5 + 1.2) * 0.04;
  });
  return (
    <group ref={group} position={[2.95, -0.35, 0]} rotation={[0, -0.36, 0]}>
      <Panel edge="#14B8A6" color="#0f2233" />
      <Cells messy={false} />
    </group>
  );
}

function Core() {
  const a = useRef<THREE.Mesh>(null);
  const b = useRef<THREE.Mesh>(null);
  const c = useRef<THREE.Mesh>(null);
  const nodes = useRef<THREE.Group>(null);
  useFrame(({ clock }) => {
    const t = clock.elapsedTime;
    if (a.current) a.current.rotation.z = t * 0.25;
    if (b.current) b.current.rotation.set(1.1, t * 0.35, 0.4);
    if (c.current) c.current.rotation.set(-0.9, -t * 0.3, 0.2);
    if (nodes.current) nodes.current.rotation.z = -t * 0.25;
  });
  return (
    <group position={[0, -0.1, 0]}>
      <mesh ref={a}>
        <torusGeometry args={[0.95, 0.018, 12, 96]} />
        <meshBasicMaterial color={CYAN} toneMapped={false} />
      </mesh>
      <mesh ref={b}>
        <torusGeometry args={[0.78, 0.012, 10, 80]} />
        <meshBasicMaterial color={VIOLET} toneMapped={false} />
      </mesh>
      <mesh ref={c}>
        <torusGeometry args={[0.62, 0.012, 10, 80]} />
        <meshBasicMaterial color={BLUE} toneMapped={false} />
      </mesh>
      <mesh>
        <icosahedronGeometry args={[0.3, 0]} />
        <meshBasicMaterial color={CYAN} wireframe toneMapped={false} />
      </mesh>
      <mesh>
        <sphereGeometry args={[0.07, 16, 16]} />
        <meshBasicMaterial color="#F8FAFC" toneMapped={false} />
      </mesh>
      <group ref={nodes}>
        {Array.from({ length: 6 }, (_, i) => {
          const ang = (i / 6) * Math.PI * 2;
          return (
            <mesh key={i} position={[Math.cos(ang) * 0.95, Math.sin(ang) * 0.95, 0]}>
              <sphereGeometry args={[0.045, 12, 12]} />
              <meshBasicMaterial color="#F8FAFC" toneMapped={false} />
            </mesh>
          );
        })}
      </group>
      {/* soft glow disc */}
      <mesh position={[0, 0, -0.2]}>
        <circleGeometry args={[1.5, 48]} />
        <meshBasicMaterial color={CYAN} transparent opacity={0.06} depthWrite={false} />
      </mesh>
    </group>
  );
}

const LANES = [-0.62, -0.22, 0.22, 0.62];

function lanePoint(lane: number, t: number, target: THREE.Vector3) {
  // t 0→1: messy panel → core → clean panel. Lanes squeeze together through the core.
  const x = THREE.MathUtils.lerp(-2.2, 2.1, t);
  const squeeze = 1 - Math.exp(-Math.pow((t - 0.5) / 0.2, 2));
  const y = -0.15 + lane * (0.15 + 0.85 * squeeze) - 0.15 * t;
  const z = Math.sin(t * Math.PI) * 0.35;
  return target.set(x, y, z);
}

function FlowLines() {
  const lines = useMemo(
    () =>
      LANES.map((lane) => {
        const v = new THREE.Vector3();
        return Array.from({ length: 48 }, (_, i) => lanePoint(lane, i / 47, v).clone());
      }),
    [],
  );
  return (
    <>
      {lines.map((pts, i) => (
        <Line key={i} points={pts} color="#60A5FA" lineWidth={1} transparent opacity={0.28} />
      ))}
    </>
  );
}

function FlowCells({ count = 20 }) {
  const ref = useRef<THREE.InstancedMesh>(null);
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const v = useMemo(() => new THREE.Vector3(), []);
  const col = useMemo(() => new THREE.Color(), []);
  const seeds = useMemo(() => {
    const r = rng(23);
    return Array.from({ length: count }, (_, i) => ({ lane: LANES[i % LANES.length], offset: r(), spin: (r() - 0.5) * 1.6, bad: r() < 0.5 }));
  }, [count]);

  useFrame(({ clock }) => {
    const mesh = ref.current;
    if (!mesh) return;
    const time = clock.elapsedTime / 9;
    seeds.forEach((s, i) => {
      const t = (time + s.offset) % 1;
      lanePoint(s.lane, t, v);
      const settled = THREE.MathUtils.smoothstep(t, 0.42, 0.62); // 0 = messy, 1 = clean
      dummy.position.copy(v);
      dummy.rotation.set(0, 0, s.spin * (1 - settled));
      const fade = Math.min(1, t / 0.08, (1 - t) / 0.08);
      dummy.scale.setScalar(Math.max(0.001, fade));
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
      col.copy(s.bad ? AMBER : SLATE).lerp(i % 2 ? TEAL : BLUE, settled);
      mesh.setColorAt(i, col);
    });
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  });

  return (
    <instancedMesh ref={ref} args={[undefined, undefined, count]}>
      <boxGeometry args={[CELL_W, CELL_H, 0.03]} />
      <meshBasicMaterial toneMapped={false} />
    </instancedMesh>
  );
}

function Insights() {
  const bars = useRef<THREE.Group>(null);
  const heights = [0.45, 0.8, 0.62, 1.1, 0.92];
  const colors = [BLUE, TEAL, VIOLET, CYAN, BLUE];
  useFrame(({ clock }) => {
    if (!bars.current) return;
    const t = clock.elapsedTime;
    bars.current.children.forEach((child, i) => {
      const grow = 0.88 + 0.12 * Math.sin(t * 0.8 + i * 0.9);
      child.scale.y = grow;
      child.position.y = (heights[i] * grow) / 2;
    });
  });
  const linePts = useMemo(
    () => [
      [-0.62, 0.55, 0.12],
      [-0.3, 0.85, 0.12],
      [0, 0.72, 0.12],
      [0.3, 1.25, 0.12],
      [0.62, 1.08, 0.12],
    ].map(([x, y, z]) => new THREE.Vector3(x, y, z)),
    [],
  );
  return (
    <group position={[2.85, 0.95, 0.15]} rotation={[0, -0.36, 0]}>
      <group ref={bars}>
        {heights.map((h, i) => (
          <mesh key={i} position={[(i - 2) * 0.3, h / 2, 0]}>
            <boxGeometry args={[0.17, h, 0.17]} />
            <meshBasicMaterial color={colors[i]} transparent opacity={0.9} toneMapped={false} />
          </mesh>
        ))}
      </group>
      <Line points={linePts} color="#F8FAFC" lineWidth={2} />
      {linePts.map((p, i) => (
        <mesh key={i} position={p}>
          <sphereGeometry args={[0.04, 12, 12]} />
          <meshBasicMaterial color={CYAN} toneMapped={false} />
        </mesh>
      ))}
    </group>
  );
}

function Particles({ count }: { count: number }) {
  const ref = useRef<THREE.Points>(null);
  const positions = useMemo(() => {
    const r = rng(41);
    const arr = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      arr[i * 3] = (r() - 0.5) * 11;
      arr[i * 3 + 1] = (r() - 0.5) * 5;
      arr[i * 3 + 2] = (r() - 0.5) * 4 - 1;
    }
    return arr;
  }, [count]);
  useFrame((_, delta) => {
    const pts = ref.current;
    if (!pts) return;
    const pos = pts.geometry.attributes.position as THREE.BufferAttribute;
    for (let i = 0; i < count; i++) {
      let x = pos.getX(i) + delta * 0.12;
      if (x > 5.5) x = -5.5;
      pos.setX(i, x);
    }
    pos.needsUpdate = true;
  });
  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial color="#93C5FD" size={0.03} transparent opacity={0.55} sizeAttenuation depthWrite={false} />
    </points>
  );
}

function Rig({ children }: { children: React.ReactNode }) {
  const group = useRef<THREE.Group>(null);
  useFrame(({ pointer, camera }) => {
    if (group.current) {
      // Gentle parallax (max ≈ 4°), damped.
      group.current.rotation.y = THREE.MathUtils.lerp(group.current.rotation.y, pointer.x * 0.07, 0.05);
      group.current.rotation.x = THREE.MathUtils.lerp(group.current.rotation.x, -pointer.y * 0.05, 0.05);
    }
    // Scroll moves the camera along the pipeline while the hero is on screen.
    const progress = Math.min(1, Math.max(0, window.scrollY / Math.max(1, window.innerHeight)));
    camera.position.x = THREE.MathUtils.lerp(camera.position.x, progress * 1.6, 0.06);
    camera.position.z = THREE.MathUtils.lerp(camera.position.z, 8.6 - progress * 1.4, 0.06);
    camera.lookAt(progress * 1.6, 0.1, 0);
  });
  return <group ref={group}>{children}</group>;
}

export default function HeroScene({ compact, onReady }: { compact: boolean; onReady: () => void }) {
  const wrap = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(true);
  const [dpr, setDpr] = useState(compact ? 1 : 1.5);
  const [lowQuality, setLowQuality] = useState(false);

  // Pause rendering when the hero is off screen or the tab is hidden.
  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    let onScreen = true;
    const update = () => setActive(onScreen && !document.hidden);
    const io = new IntersectionObserver(([entry]) => {
      onScreen = entry.isIntersecting;
      update();
    });
    io.observe(el);
    document.addEventListener("visibilitychange", update);
    return () => {
      io.disconnect();
      document.removeEventListener("visibilitychange", update);
    };
  }, []);

  return (
    <div ref={wrap} className="absolute inset-0" data-rendering={active}>
      <Canvas
        frameloop={active ? "always" : "never"}
        dpr={dpr}
        camera={{ position: [0, 0.35, 8.6], fov: 36 }}
        gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
        onCreated={onReady}
        aria-hidden
      >
        {/* Step quality down automatically on slow devices. */}
        <PerformanceMonitor
          onDecline={() => {
            setDpr(1);
            setLowQuality(true);
          }}
        />
        <Rig>
          <group scale={compact ? 0.86 : 1} rotation={[0.1, 0, 0]} position={[-0.15, compact ? 0.1 : 0, 0]}>
            <MessyStack />
            <FlowLines />
            <FlowCells count={compact ? 12 : 20} />
            <Core />
            <CleanPanel />
            <Insights />
            {!lowQuality && <Particles count={compact ? 60 : 150} />}
          </group>
        </Rig>
      </Canvas>
    </div>
  );
}
