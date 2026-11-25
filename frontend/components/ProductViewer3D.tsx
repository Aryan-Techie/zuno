"use client";

import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { RoundedBoxGeometry } from "three/examples/jsm/geometries/RoundedBoxGeometry.js";
import { catalogImageUrl, type CatalogProduct } from "@/lib/api";
import { productShape, safeHex, type ProductShape } from "@/lib/catalog";

/**
 * A procedural stand-in for a beauty product, in plain three.js for the same
 * reason components/Avatar3D.tsx gives (react-three-fiber does not line up
 * with this app's React/Next pair). Not a replica of any real bottle: a glass
 * body with real transmission, a tinted juice inside, a metal or lacquer cap,
 * and the product's own image printed on the label once it loads.
 *
 * The canvas is opaque and cleared to the stage colour rather than
 * transparent: three r153's transmission pass samples the clear colour, so a
 * transparent canvas makes glass read as milky white on a dark ground.
 *
 * Remount it (key on the product id) to show a different product; everything
 * is built once per mount and disposed on unmount.
 */
export function ProductViewer3D({ product, className }: { product: CatalogProduct; className?: string }) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);
  const [ready, setReady] = useState(false);
  // Polls hand back a fresh object for the same product every second; the
  // scene is rebuilt only when the product itself changes.
  const productRef = useRef(product);
  productRef.current = product;

  useEffect(() => {
    const product = productRef.current;
    const wrap = wrapRef.current;
    if (!wrap) return;
    // A fresh canvas per run: the cleanup below force-loses its context, and
    // a context lost on a canvas cannot be had again from that canvas (Strict
    // Mode runs this effect twice in development).
    const canvas = document.createElement("canvas");
    canvas.setAttribute("role", "img");
    canvas.setAttribute("aria-label", `${product.name}, a 3D model you can drag to turn`);
    wrap.prepend(canvas);

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false, powerPreference: "low-power" });
    } catch {
      canvas.remove();
      setFailed(true);
      return;
    }
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    renderer.outputColorSpace = THREE.SRGBColorSpace;

    const scene = new THREE.Scene();
    const pmrem = new THREE.PMREMGenerator(renderer);
    const envTarget = pmrem.fromScene(new RoomEnvironment(), 0.04);
    scene.environment = envTarget.texture;

    // Soft studio: the room environment does most of the work; a key light
    // from above-left puts one crisp highlight down the glass, and a cool rim
    // from behind separates the silhouette from the ground.
    const key = new THREE.DirectionalLight(0xffffff, 1.6);
    key.position.set(-2.5, 4, 3);
    scene.add(key);
    const rim = new THREE.DirectionalLight(0xfff4e6, 1.1);
    rim.position.set(2.5, 1.5, -3);
    scene.add(rim);
    scene.add(new THREE.AmbientLight(0xffffff, 0.25));

    const textures: THREE.Texture[] = [];
    const shape = productShape(product);
    const { group, label } = buildModel(shape, product, textures);
    scene.add(group);

    // Contact shadow: a radial falloff under the object, so it sits on
    // something rather than floating in a void.
    const box = new THREE.Box3().setFromObject(group);
    const size = box.getSize(new THREE.Vector3());
    const shadowTex = radialTexture();
    textures.push(shadowTex);
    const shadow = new THREE.Mesh(
      new THREE.PlaneGeometry(size.x * 2.4 + 0.6, size.z * 2.4 + 0.8),
      new THREE.MeshBasicMaterial({ map: shadowTex, transparent: true, depthWrite: false, opacity: 0.55 })
    );
    shadow.rotation.x = -Math.PI / 2;
    shadow.position.y = box.min.y + 0.002;
    scene.add(shadow);

    // A three-quarter view from a little above, so the first frame already
    // shows the depth of the glass and the top of the cap. Framed on the
    // bounding sphere, so any shape fits whatever the stage's aspect.
    const FOV = 28;
    const camera = new THREE.PerspectiveCamera(FOV, 1, 0.1, 50);
    const center = box.getCenter(new THREE.Vector3());
    const radius = box.getBoundingSphere(new THREE.Sphere()).radius;
    camera.position.copy(center).add(new THREE.Vector3().setFromSphericalCoords(radius * 4, THREE.MathUtils.degToRad(72), 0.62));
    const frameDistance = (aspect: number) => {
      const vHalf = THREE.MathUtils.degToRad(FOV / 2);
      const hHalf = Math.atan(Math.tan(vHalf) * aspect);
      return (radius / Math.sin(Math.min(vHalf, hHalf))) * 1.04;
    };

    const controls = new OrbitControls(camera, canvas);
    controls.target.copy(center);
    controls.enableZoom = false;
    controls.enablePan = false;
    controls.enableDamping = !reduceMotion;
    controls.dampingFactor = 0.08;
    controls.rotateSpeed = 0.7;
    controls.autoRotate = !reduceMotion;
    controls.autoRotateSpeed = 1.5;
    controls.minPolarAngle = Math.PI * 0.3;
    controls.maxPolarAngle = Math.PI * 0.56;
    controls.update();

    // The image goes on the label once it arrives; until then the label is
    // typographic, so the bottle is never blank while the call goes on.
    let disposed = false;
    if (label && product.image_url !== null) {
      const img = new Image();
      img.crossOrigin = "anonymous";
      img.decoding = "async";
      img.onload = () => {
        if (disposed) return;
        label.draw(img);
      };
      img.src = catalogImageUrl(product.id);
      void document.fonts?.load?.('48px "Bodoni Moda"').then(() => {
        if (!disposed && !label.hasImage) label.draw(null);
      });
    }

    const applyBackground = () => {
      const bg = getComputedStyle(wrap).backgroundColor;
      try {
        renderer.setClearColor(new THREE.Color().setStyle(bg), 1);
      } catch {
        renderer.setClearColor(0xf2f2f4, 1);
      }
    };
    applyBackground();
    // The stage colour follows the theme and the mode; re-read it when either
    // flips, and once more after the cross-fade in app/modes.css settles.
    let settleTimer: ReturnType<typeof setTimeout> | null = null;
    const themeObserver = new MutationObserver(() => {
      applyBackground();
      if (settleTimer) clearTimeout(settleTimer);
      settleTimer = setTimeout(applyBackground, 950);
    });
    themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "data-mode"] });

    const resize = () => {
      const r = wrap.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) return;
      renderer.setSize(r.width, r.height, false);
      camera.aspect = r.width / r.height;
      camera.updateProjectionMatrix();
      camera.position.sub(controls.target).setLength(frameDistance(camera.aspect)).add(controls.target);
    };
    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(wrap);
    resize();

    // Only spend frames while the viewer is actually on screen.
    let visible = true;
    const io = new IntersectionObserver(([entry]) => {
      visible = entry?.isIntersecting ?? true;
    });
    io.observe(wrap);

    const start = performance.now();
    let raf = 0;
    let first = true;
    const frame = (now: number) => {
      raf = requestAnimationFrame(frame);
      if (!visible || document.hidden) return;
      // A short rise and quarter-turn on arrival, so a new product lands
      // rather than appears. Cut straight to rest under reduced motion.
      const p = reduceMotion ? 1 : Math.min(1, (now - start) / 1100);
      const e = 1 - Math.pow(1 - p, 3);
      group.position.y = (1 - e) * -0.18;
      group.rotation.y = (1 - e) * -0.9;
      controls.update();
      renderer.render(scene, camera);
      if (first) {
        first = false;
        setReady(true);
      }
    };
    raf = requestAnimationFrame(frame);

    return () => {
      disposed = true;
      cancelAnimationFrame(raf);
      if (settleTimer) clearTimeout(settleTimer);
      themeObserver.disconnect();
      resizeObserver.disconnect();
      io.disconnect();
      controls.dispose();
      scene.traverse((child) => {
        const mesh = child as THREE.Mesh;
        if (!mesh.isMesh) return;
        mesh.geometry?.dispose();
        const mats = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
        mats.forEach((m) => m?.dispose());
      });
      textures.forEach((t) => t.dispose());
      envTarget.dispose();
      pmrem.dispose();
      renderer.dispose();
      // Browsers cap live WebGL contexts (~16); release this one now rather
      // than whenever the collector gets to it, since the spotlight and the
      // catalog remount the viewer for every product.
      renderer.forceContextLoss();
      canvas.remove();
    };
  }, [product.id]);

  if (failed) {
    return (
      <div className={`viewer3d fallback ${className ?? ""}`}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={catalogImageUrl(product.id)} alt={product.name} />
      </div>
    );
  }

  return (
    <div ref={wrapRef} className={`viewer3d${ready ? " ready" : ""} ${className ?? ""}`}>
      <span className="viewer3d-hint" aria-hidden="true">
        Drag to turn
      </span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* models                                                              */
/* ------------------------------------------------------------------ */

interface Label {
  draw: (img: HTMLImageElement | null) => void;
  hasImage: boolean;
}

function defaultTint(p: CatalogProduct): string {
  if (p.category === "makeup") return "#9e2f3a";
  if (p.category === "skincare") return "#efe4d6";
  if (p.gender === "men") return "#2c3a52";
  if (p.gender === "women") return "#e8b9a3";
  return "#d6c3a0";
}

function glass(tint: THREE.Color, frosted = false): THREE.MeshPhysicalMaterial {
  return new THREE.MeshPhysicalMaterial({
    color: 0xffffff,
    metalness: 0,
    roughness: frosted ? 0.32 : 0.03,
    transmission: 1,
    thickness: 0.9,
    ior: 1.5,
    clearcoat: 1,
    clearcoatRoughness: 0.04,
    attenuationColor: tint.clone().lerp(new THREE.Color(0xffffff), 0.7),
    attenuationDistance: 4,
    specularIntensity: 1,
    envMapIntensity: 1.25,
    side: THREE.DoubleSide,
  });
}

function juice(tint: THREE.Color): THREE.MeshPhysicalMaterial {
  // Opaque on purpose: r153's transmission pass only sees opaque objects, so
  // a transmissive liquid would vanish behind the transmissive glass.
  return new THREE.MeshPhysicalMaterial({
    color: tint,
    roughness: 0.12,
    metalness: 0,
    clearcoat: 1,
    clearcoatRoughness: 0.08,
    emissive: tint,
    emissiveIntensity: 0.05,
  });
}

function capMaterial(p: CatalogProduct): THREE.MeshPhysicalMaterial {
  if (p.gender === "men") {
    // Black lacquer
    return new THREE.MeshPhysicalMaterial({ color: 0x0c0c0d, roughness: 0.22, metalness: 0.1, clearcoat: 1, clearcoatRoughness: 0.05 });
  }
  if (p.gender === "women" || p.category !== "fragrance") {
    // Champagne gold
    return new THREE.MeshPhysicalMaterial({ color: 0xd6b47a, roughness: 0.22, metalness: 1 });
  }
  // Brushed silver
  return new THREE.MeshPhysicalMaterial({ color: 0xd9d9de, roughness: 0.28, metalness: 1 });
}

function buildModel(
  shape: ProductShape,
  p: CatalogProduct,
  textures: THREE.Texture[]
): { group: THREE.Group; label: Label | null } {
  const group = new THREE.Group();
  const tint = new THREE.Color(safeHex(p.color_hex) ?? defaultTint(p));
  let label: Label | null = null;

  const addLabel = (geometry: THREE.BufferGeometry, position: THREE.Vector3, aspect: number) => {
    const made = makeLabel(p, aspect);
    textures.push(made.texture);
    const mesh = new THREE.Mesh(
      geometry,
      new THREE.MeshPhysicalMaterial({ map: made.texture, roughness: 0.55, metalness: 0, clearcoat: 0.3, transparent: true })
    );
    mesh.position.copy(position);
    group.add(mesh);
    label = made.label;
  };

  switch (shape) {
    case "flacon": {
      const w = 1.05;
      const h = 1.2;
      const d = 0.52;
      const body = new THREE.Mesh(new RoundedBoxGeometry(w, h, d, 6, 0.09), glass(tint));
      body.position.y = h / 2;
      group.add(body);
      // Thick walls and a heavy base: the clear glass around the juice is
      // what makes it read as glass rather than a painted block.
      const liquidH = h * 0.62;
      const liquid = new THREE.Mesh(new RoundedBoxGeometry(w - 0.3, liquidH, d - 0.22, 4, 0.05), juice(tint));
      liquid.position.y = 0.2 + liquidH / 2;
      group.add(liquid);
      const collar = new THREE.Mesh(new THREE.CylinderGeometry(0.15, 0.17, 0.08, 48), capMaterial({ ...p, gender: "women" }));
      collar.position.y = h + 0.04;
      group.add(collar);
      const cap =
        p.gender === "men"
          ? new THREE.Mesh(new RoundedBoxGeometry(0.46, 0.44, 0.4, 5, 0.05), capMaterial(p))
          : new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.2, 0.46, 64), capMaterial(p));
      cap.position.y = h + 0.08 + 0.22;
      group.add(cap);
      addLabel(new THREE.PlaneGeometry(0.42, 0.52), new THREE.Vector3(0, h * 0.5, d / 2 + 0.004), 0.42 / 0.52);
      break;
    }
    case "amphora": {
      // A tall teardrop on a narrow foot, with a long neck.
      const profile = [
        [0.0, 0],
        [0.2, 0],
        [0.3, 0.05],
        [0.46, 0.3],
        [0.52, 0.55],
        [0.47, 0.85],
        [0.33, 1.12],
        [0.18, 1.34],
        [0.12, 1.48],
        [0.115, 1.62],
      ].map(([x, y]) => new THREE.Vector2(x, y));
      // Smooth the silhouette: a lathe straight off ten points is faceted.
      const smooth = new THREE.SplineCurve(profile).getPoints(80);
      const body = new THREE.Mesh(new THREE.LatheGeometry(smooth, 96), glass(tint));
      group.add(body);
      const inner = new THREE.SplineCurve(
        profile.slice(0, 7).map((v) => new THREE.Vector2(Math.max(0, v.x * 0.8), v.y * 0.82 + 0.1))
      ).getPoints(60);
      const liquid = new THREE.Mesh(new THREE.LatheGeometry(inner, 64), juice(tint));
      group.add(liquid);
      // Stacked rings at the neck - the gesture, not a copy, of a collared amphora.
      const gold = capMaterial({ ...p, gender: "women" });
      for (let i = 0; i < 4; i++) {
        const ring = new THREE.Mesh(new THREE.TorusGeometry(0.15 - i * 0.004, 0.022, 16, 64), gold);
        ring.rotation.x = Math.PI / 2;
        ring.position.y = 1.4 + i * 0.05;
        group.add(ring);
      }
      const cap = new THREE.Mesh(new THREE.SphereGeometry(0.16, 48, 32), glass(tint));
      cap.scale.set(1, 1.5, 1);
      cap.position.y = 1.8;
      group.add(cap);
      addLabel(
        new THREE.CylinderGeometry(0.525, 0.525, 0.3, 64, 1, true, -0.55, 1.1),
        new THREE.Vector3(0, 0.56, 0),
        (0.525 * 1.1) / 0.3
      );
      break;
    }
    case "serum": {
      const body = new THREE.Mesh(new THREE.CylinderGeometry(0.36, 0.38, 1.0, 64), glass(tint));
      body.position.y = 0.5;
      group.add(body);
      const liquid = new THREE.Mesh(new THREE.CylinderGeometry(0.29, 0.31, 0.7, 48), juice(tint));
      liquid.position.y = 0.42;
      group.add(liquid);
      const collar = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.2, 0.22, 48), capMaterial(p));
      collar.position.y = 1.11;
      group.add(collar);
      const bulb = new THREE.Mesh(
        new THREE.CapsuleGeometry(0.13, 0.3, 12, 32),
        new THREE.MeshPhysicalMaterial({ color: 0x111111, roughness: 0.45, clearcoat: 0.6 })
      );
      bulb.position.y = 1.43;
      group.add(bulb);
      addLabel(
        new THREE.CylinderGeometry(0.372, 0.375, 0.44, 64, 1, true, -0.6, 1.2),
        new THREE.Vector3(0, 0.52, 0),
        (0.373 * 1.2) / 0.44
      );
      break;
    }
    case "jar": {
      const body = new THREE.Mesh(new THREE.CylinderGeometry(0.62, 0.6, 0.62, 96), glass(tint, true));
      body.position.y = 0.31;
      group.add(body);
      const cream = new THREE.Mesh(
        new THREE.CylinderGeometry(0.5, 0.48, 0.48, 64),
        new THREE.MeshPhysicalMaterial({ color: tint.clone().lerp(new THREE.Color(0xfaf6ef), 0.6), roughness: 0.6, sheen: 0.8 })
      );
      cream.position.y = 0.3;
      group.add(cream);
      const lidCyl = new THREE.Mesh(new THREE.CylinderGeometry(0.65, 0.65, 0.3, 96), capMaterial(p));
      lidCyl.position.y = 0.62 + 0.15;
      group.add(lidCyl);
      addLabel(
        new THREE.CylinderGeometry(0.622, 0.612, 0.34, 64, 1, true, -0.55, 1.1),
        new THREE.Vector3(0, 0.31, 0),
        (0.62 * 1.1) / 0.34
      );
      break;
    }
    case "lipstick": {
      const metal = capMaterial({ ...p, gender: "women" });
      const base = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.3, 0.86, 64), metal);
      base.position.y = 0.43;
      group.add(base);
      const sleeve = new THREE.Mesh(
        new THREE.CylinderGeometry(0.25, 0.25, 0.24, 64),
        new THREE.MeshPhysicalMaterial({ color: 0x0d0d0d, roughness: 0.2, clearcoat: 1 })
      );
      sleeve.position.y = 0.98;
      group.add(sleeve);
      const bulletGeo = new THREE.CylinderGeometry(0.2, 0.2, 0.5, 64, 8);
      // Bevel the top into the familiar slant by shearing the upper vertices.
      const pos = bulletGeo.attributes.position;
      for (let i = 0; i < pos.count; i++) {
        const y = pos.getY(i);
        if (y > 0) pos.setY(i, y - (pos.getX(i) + 0.2) * 0.55 * (y / 0.25));
      }
      bulletGeo.computeVertexNormals();
      const bullet = new THREE.Mesh(
        bulletGeo,
        new THREE.MeshPhysicalMaterial({ color: tint, roughness: 0.4, sheen: 0.25, sheenColor: tint, clearcoat: 0.35, clearcoatRoughness: 0.3 })
      );
      bullet.position.y = 1.32;
      group.add(bullet);
      break;
    }
    case "compact": {
      const lacquer = capMaterial({ ...p, gender: "men" });
      const base = new THREE.Mesh(new THREE.CylinderGeometry(0.8, 0.8, 0.16, 96), lacquer);
      base.position.y = 0.08;
      group.add(base);
      const pan = new THREE.Mesh(
        new THREE.CylinderGeometry(0.66, 0.66, 0.04, 96),
        new THREE.MeshPhysicalMaterial({ color: tint.clone().multiplyScalar(0.8), roughness: 0.9, sheen: 0.2, sheenColor: tint })
      );
      pan.position.y = 0.165;
      group.add(pan);
      // The lid stands open on its hinge with a mirror inside.
      const hinge = new THREE.Group();
      hinge.position.set(0, 0.16, -0.8);
      hinge.rotation.x = -Math.PI * 0.6;
      const lid = new THREE.Mesh(new THREE.CylinderGeometry(0.8, 0.8, 0.1, 96), lacquer);
      lid.position.set(0, 0.05, 0.8);
      hinge.add(lid);
      const mirror = new THREE.Mesh(
        new THREE.CircleGeometry(0.68, 96),
        new THREE.MeshPhysicalMaterial({ color: 0xffffff, roughness: 0.02, metalness: 1 })
      );
      mirror.rotation.x = Math.PI / 2;
      mirror.position.set(0, -0.002, 0.8);
      hinge.add(mirror);
      const gold = capMaterial({ ...p, gender: "women" });
      const ring = new THREE.Mesh(new THREE.TorusGeometry(0.72, 0.018, 12, 96), gold);
      ring.rotation.x = Math.PI / 2;
      ring.position.set(0, 0.105, 0.8);
      hinge.add(ring);
      group.add(hinge);
      break;
    }
  }

  return { group, label };
}

/**
 * The label: an ivory card with a hairline gold frame. Typographic (brand and
 * line in the display face) until the product image loads, then the image
 * with the brand set beneath it.
 */
function makeLabel(p: CatalogProduct, aspect: number): { texture: THREE.CanvasTexture; label: Label } {
  const H = 640;
  const W = Math.round(H * aspect);
  const canvas = document.createElement("canvas");
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d")!;
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 8;

  const label: Label = {
    hasImage: false,
    draw(img) {
      if (img) label.hasImage = true;
      ctx.clearRect(0, 0, W, H);
      ctx.fillStyle = "#f7f2e8";
      roundRect(ctx, 0, 0, W, H, 18);
      ctx.fill();
      ctx.strokeStyle = "rgba(160, 128, 78, 0.85)";
      ctx.lineWidth = 3;
      roundRect(ctx, 14, 14, W - 28, H - 28, 10);
      ctx.stroke();

      const brand = (p.brand || "").toUpperCase().split("").join(String.fromCharCode(8202));
      ctx.fillStyle = "#14120f";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      if (img && img.naturalWidth > 0) {
        const pad = 34;
        const boxW = W - pad * 2;
        const boxH = H - pad * 2 - 110;
        const scale = Math.min(boxW / img.naturalWidth, boxH / img.naturalHeight);
        const iw = img.naturalWidth * scale;
        const ih = img.naturalHeight * scale;
        ctx.save();
        ctx.globalCompositeOperation = "multiply";
        ctx.drawImage(img, (W - iw) / 2, pad + (boxH - ih) / 2, iw, ih);
        ctx.restore();
        ctx.font = `500 ${Math.round(W * 0.11)}px "Bodoni Moda", Didot, "Bodoni 72", Georgia, serif`;
        ctx.fillText(brand, W / 2, H - 92);
        ctx.font = `400 ${Math.round(W * 0.055)}px -apple-system, "Inter", sans-serif`;
        ctx.fillStyle = "#5f574b";
        ctx.fillText(fit(ctx, (p.line || p.name).toUpperCase(), W - 70), W / 2, H - 50);
      } else {
        ctx.font = `500 ${Math.round(W * 0.15)}px "Bodoni Moda", Didot, "Bodoni 72", Georgia, serif`;
        ctx.fillText(brand, W / 2, H * 0.4);
        ctx.strokeStyle = "rgba(160, 128, 78, 0.7)";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(W * 0.38, H * 0.5);
        ctx.lineTo(W * 0.62, H * 0.5);
        ctx.stroke();
        ctx.font = `italic 400 ${Math.round(W * 0.085)}px "Bodoni Moda", Didot, Georgia, serif`;
        ctx.fillStyle = "#3b352d";
        ctx.fillText(fit(ctx, p.line || p.name, W - 70), W / 2, H * 0.6);
      }
      texture.needsUpdate = true;
    },
  };
  label.draw(null);
  return { texture, label };
}

function fit(ctx: CanvasRenderingContext2D, text: string, max: number): string {
  if (ctx.measureText(text).width <= max) return text;
  let t = text;
  while (t.length > 1 && ctx.measureText(`${t}…`).width > max) t = t.slice(0, -1);
  return `${t}…`;
}

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function radialTexture(): THREE.CanvasTexture {
  const c = document.createElement("canvas");
  c.width = c.height = 256;
  const ctx = c.getContext("2d")!;
  const g = ctx.createRadialGradient(128, 128, 0, 128, 128, 128);
  g.addColorStop(0, "rgba(0,0,0,0.55)");
  g.addColorStop(0.45, "rgba(0,0,0,0.18)");
  g.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 256, 256);
  return new THREE.CanvasTexture(c);
}
