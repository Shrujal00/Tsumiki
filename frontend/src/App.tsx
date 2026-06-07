import { useState } from "react";
import { CinematicHero } from "@/components/ui/cinematic-landing-hero";
import { ZenPreloader } from "@/components/ui/zen-preloader";

export default function App() {
  const [preloaderFinished, setPreloaderFinished] = useState(false);

  return (
    <main className="overflow-x-hidden w-[100%] min-h-screen bg-background">
      {!preloaderFinished && (
        <ZenPreloader onComplete={() => setPreloaderFinished(true)} />
      )}
      {preloaderFinished && (
        <CinematicHero 
          brandName="Tsumiki"
          tagline1="Tend your goals,"
          tagline2="like a garden."
          cardHeading="Calm, intentional progress."
          cardDescription={<><span className="text-white font-semibold">Tsumiki</span> is a multi-agent system themed around a Japanese garden. Instead of chatting with one generic AI, you work with specialized agents while your real-world progress is visualized as a garden that grows with you.</>}
          metricValue={14}
          metricLabel="Days Tended"
          ctaHeading="Start your garden."
          ctaDescription="Join the calm, autonomous, domain-agnostic coaching system and tend your goals one stone at a time."
        />
      )}
    </main>
  );
}
