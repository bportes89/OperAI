"use client";

import {
  useEffect,
  useRef,
  type CSSProperties,
  type MouseEvent as ReactMouseEvent,
  type ReactNode,
} from "react";

const FLOATS = [
  { label: "BYOK", href: "#diferenciais", x: "8%", y: "22%", delay: "0s", depth: 18 },
  { label: "WhatsApp", href: "#funcionalidades", x: "78%", y: "18%", delay: "0.6s", depth: 28 },
  { label: "CRM", href: "#funcionalidades", x: "86%", y: "62%", delay: "1.1s", depth: 22 },
  { label: "Cobrança", href: "#casos-de-uso", x: "12%", y: "68%", delay: "1.7s", depth: 26 },
  { label: "Agentes", href: "#como-funciona", x: "48%", y: "12%", delay: "0.3s", depth: 14 },
];

function prefersReducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** Global pointer parallax + reveal + magnetic CTAs for the landing. */
export function LandingFX() {
  const frame = useRef(0);

  useEffect(() => {
    const root = document.querySelector(".lp") as HTMLElement | null;
    if (!root) return;

    const reveal = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) entry.target.classList.add("is-in");
        }
      },
      { threshold: 0.14, rootMargin: "0px 0px -8% 0px" },
    );
    root.querySelectorAll(".lp-reveal").forEach((el) => reveal.observe(el));

    if (prefersReducedMotion()) {
      root.querySelectorAll(".lp-reveal").forEach((el) => el.classList.add("is-in"));
      return () => reveal.disconnect();
    }

    const onMove = (event: MouseEvent) => {
      cancelAnimationFrame(frame.current);
      frame.current = requestAnimationFrame(() => {
        const rect = root.getBoundingClientRect();
        const x = (event.clientX - rect.left) / rect.width - 0.5;
        const y = (event.clientY - rect.top) / rect.height - 0.5;
        root.style.setProperty("--mx", x.toFixed(4));
        root.style.setProperty("--my", y.toFixed(4));
      });
    };

    window.addEventListener("pointermove", onMove, { passive: true });

    return () => {
      cancelAnimationFrame(frame.current);
      window.removeEventListener("pointermove", onMove);
      reveal.disconnect();
    };
  }, []);

  useEffect(() => {
    if (prefersReducedMotion()) return;

    const buttons = Array.from(
      document.querySelectorAll<HTMLElement>(".lp-btn-primary"),
    );

    const cleanups = buttons.map((btn) => {
      const onMove = (event: PointerEvent) => {
        const rect = btn.getBoundingClientRect();
        const dx = event.clientX - (rect.left + rect.width / 2);
        const dy = event.clientY - (rect.top + rect.height / 2);
        btn.style.transform = `translate(${dx * 0.18}px, ${dy * 0.22}px)`;
      };
      const onLeave = () => {
        btn.style.transform = "";
      };
      btn.addEventListener("pointermove", onMove);
      btn.addEventListener("pointerleave", onLeave);
      return () => {
        btn.removeEventListener("pointermove", onMove);
        btn.removeEventListener("pointerleave", onLeave);
      };
    });

    return () => cleanups.forEach((fn) => fn());
  }, []);

  return null;
}

/** Floating interactive chips around the hero composition. */
export function HeroFloatLayer() {
  function onEnter(event: ReactMouseEvent<HTMLAnchorElement>) {
    event.currentTarget.classList.add("is-hot");
  }

  function onLeave(event: ReactMouseEvent<HTMLAnchorElement>) {
    event.currentTarget.classList.remove("is-hot");
  }

  return (
    <div className="lp-float-layer">
      <div className="lp-orbit lp-orbit-a" aria-hidden="true" />
      <div className="lp-orbit lp-orbit-b" aria-hidden="true" />
      <div className="lp-orbit lp-orbit-c" aria-hidden="true" />
      {FLOATS.map((item) => (
        <a
          key={item.label}
          href={item.href}
          className="lp-float"
          style={
            {
              left: item.x,
              top: item.y,
              animationDelay: item.delay,
              "--depth": item.depth,
            } as CSSProperties
          }
          onMouseEnter={onEnter}
          onMouseLeave={onLeave}
        >
          <span className="lp-float-dot" aria-hidden="true" />
          {item.label}
        </a>
      ))}
    </div>
  );
}

/** Soft 3D tilt on the hero operations panel. */
export function HeroPanelTilt({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);

  function onMove(event: ReactMouseEvent<HTMLDivElement>) {
    if (prefersReducedMotion()) return;
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const x = (event.clientX - rect.left) / rect.width - 0.5;
    const y = (event.clientY - rect.top) / rect.height - 0.5;
    el.style.transform = `perspective(1200px) rotateY(${x * 8}deg) rotateX(${-y * 7}deg)`;
  }

  function onLeave() {
    if (ref.current) ref.current.style.transform = "";
  }

  return (
    <div
      className="lp-tilt-wrap"
      ref={ref}
      onMouseMove={onMove}
      onMouseLeave={onLeave}
    >
      {children}
    </div>
  );
}
