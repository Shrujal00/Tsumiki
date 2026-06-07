"use client";

import { useEffect, useRef } from "react";
import { gsap } from "gsap";

export interface ZenPreloaderProps {
  onComplete: () => void;
}

export function ZenPreloader({ onComplete }: ZenPreloaderProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const textRef = useRef<HTMLHeadingElement>(null);
  const lineRef = useRef<HTMLDivElement>(null);
  const circleRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const ctx = gsap.context(() => {
      const tl = gsap.timeline({
        onComplete: () => {
          onComplete();
        },
      });

      // Initial state
      gsap.set(textRef.current, { autoAlpha: 0, y: 20, letterSpacing: "0.1em" });
      gsap.set(lineRef.current, { scaleX: 0, transformOrigin: "left center" });
      gsap.set(circleRef.current, { autoAlpha: 0, scale: 0 });

      // The Animation
      tl.to(circleRef.current, {
        duration: 1.5,
        autoAlpha: 1,
        scale: 1,
        ease: "expo.out",
      })
      .to(textRef.current, {
        duration: 2,
        autoAlpha: 1,
        y: 0,
        letterSpacing: "0.35em",
        ease: "power3.out",
      }, "-=1")
      .to(lineRef.current, {
        duration: 1.5,
        scaleX: 1,
        ease: "power4.inOut",
      }, "-=1.5")
      // Hold for a moment of silence
      .to({}, { duration: 0.8 })
      // Fade everything out softly
      .to(containerRef.current, {
        duration: 1.5,
        autoAlpha: 0,
        ease: "power2.inOut",
      });

    }, containerRef);

    return () => ctx.revert();
  }, [onComplete]);

  return (
    <div
      ref={containerRef}
      className="fixed inset-0 z-[9999] flex flex-col items-center justify-center bg-background pointer-events-none"
    >
      <div className="relative flex flex-col items-center justify-center">
        {/* Zen Circle Metaphor */}
        <div 
          ref={circleRef}
          className="absolute w-32 h-32 rounded-full border border-primary/20 opacity-0 mix-blend-screen"
          style={{ filter: "blur(2px)" }}
        />
        
        <h1 
          ref={textRef}
          className="text-white text-sm md:text-base font-light uppercase tracking-[0.35em] z-10"
        >
          Tsumiki
        </h1>
        
        <div className="w-24 h-[1px] bg-primary/40 mt-6 overflow-hidden relative">
          <div 
            ref={lineRef}
            className="absolute inset-0 bg-primary origin-left"
          />
        </div>
      </div>
    </div>
  );
}
