'use client';

import { Pause, Play } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

const SRC = '/demo/platform-demo';

/**
 * The product demo video of the hero. It plays muted in a loop. With reduced motion it shows the poster and
 * a play button, and plays only when the reader selects it. A button on the frame pauses and plays it.
 */
export function DemoVideo({ className = '' }: { className?: string }) {
  const video = useRef<HTMLVideoElement>(null);
  const [playing, setPlaying] = useState(false);
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReduced(query.matches);
    if (!query.matches) video.current?.play().catch(() => setPlaying(false));
  }, []);

  const toggle = () => {
    const v = video.current;
    if (!v) return;
    if (v.paused) v.play().catch(() => setPlaying(false));
    else v.pause();
  };

  const started = playing || !reduced;
  return (
    <div className={`group relative rounded-xl border bg-fd-card p-1.5 shadow-sm ${className}`}>
      <div className="relative overflow-hidden rounded-lg border">
        <video
          ref={video}
          className="block aspect-[16/10] h-auto w-full bg-fd-muted"
          width={1600}
          height={1000}
          muted
          loop
          playsInline
          preload="metadata"
          poster="/demo/poster.webp"
          aria-label="Demo of the officer dashboard: sign in, turn on features, award points, upload documents, deploy an app and create a token"
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
        >
          <source src={`${SRC}.webm`} type="video/webm" />
          <source src={`${SRC}.mp4`} type="video/mp4" />
        </video>
        {started ? (
          <button
            type="button"
            onClick={toggle}
            aria-label={playing ? 'Pause the demo' : 'Play the demo'}
            className="absolute right-3 bottom-3 flex size-9 items-center justify-center rounded-full bg-black/60 text-white opacity-0 backdrop-blur transition-opacity duration-150 ease-out group-hover:opacity-100 focus-visible:opacity-100"
          >
            {playing ? <Pause className="size-4" /> : <Play className="size-4" />}
          </button>
        ) : (
          <button
            type="button"
            onClick={toggle}
            className="absolute inset-0 flex items-center justify-center bg-black/10 transition-colors duration-150 ease-out hover:bg-black/20"
          >
            <span className="inline-flex h-11 items-center gap-2 rounded-full bg-fd-foreground px-5 text-sm font-medium text-fd-background shadow-lg">
              <Play className="size-4" />
              Watch the demo
            </span>
          </button>
        )}
      </div>
    </div>
  );
}
