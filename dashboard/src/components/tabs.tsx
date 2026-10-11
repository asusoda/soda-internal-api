import { type KeyboardEvent, type ReactNode, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router';
import { cx } from './ui';

export type Tab<T extends string> = { id: T; label: string };

// The tab named by the ?tab= query parameter, and a function to change it. The first tab has no parameter.
// aliases maps an old ?tab= value to the tab that replaced it, so old links still open the right tab.
export function useTabParam<T extends string>(tabs: readonly Tab<T>[], aliases: Record<string, T> = {}): [T, (id: T) => void] {
  const [params, setParams] = useSearchParams();
  const first = tabs[0].id;
  const asked = params.get('tab') ?? '';
  const tab = tabs.find((t) => t.id === (aliases[asked] ?? asked))?.id ?? first;
  return [tab, (id: T) => setParams(id === first ? {} : { tab: id }, { replace: true })];
}

// A row of tabs with an underline under the open one. The underline slides to the tab that opens.
// Arrow keys move between tabs. extra adds content after a label, such as a count. action sits at the right end of
// the row, such as a search field or a filter.
export function TabBar<T extends string>({
  label,
  tabs,
  value,
  onChange,
  extra,
  action,
}: {
  label: string;
  tabs: readonly Tab<T>[];
  value: T;
  onChange: (id: T) => void;
  extra?: (id: T) => ReactNode;
  action?: ReactNode;
}) {
  const list = useRef<HTMLDivElement>(null);
  const [bar, setBar] = useState<{ left: number; width: number } | null>(null);
  // The underline slides only after its first place is set, so it does not slide in when the page opens.
  const [slide, setSlide] = useState(false);
  useEffect(() => {
    if (!bar || slide) return;
    const frame = requestAnimationFrame(() => setSlide(true));
    return () => cancelAnimationFrame(frame);
  }, [bar, slide]);

  useLayoutEffect(() => {
    const el = list.current;
    if (!el) return;
    const measure = () => {
      const tab = el.querySelector<HTMLElement>('[aria-selected="true"]');
      setBar(tab ? { left: tab.offsetLeft, width: tab.offsetWidth } : null);
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, [value, tabs]);

  const move = (e: KeyboardEvent<HTMLDivElement>) => {
    const step = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
    if (!step) return;
    const i = tabs.findIndex((t) => t.id === value);
    const next = tabs[(i + step + tabs.length) % tabs.length];
    onChange(next.id);
    list.current?.querySelector<HTMLElement>(`[data-tab="${next.id}"]`)?.focus();
  };

  return (
    <div className="mb-6 flex flex-wrap items-center justify-between gap-x-4 border-b border-line">
    <div ref={list} role="tablist" aria-label={label} onKeyDown={move} className="relative flex min-w-0 gap-1 overflow-x-auto">
      {tabs.map((t) => (
        <button
          key={t.id}
          type="button"
          role="tab"
          data-tab={t.id}
          aria-selected={value === t.id}
          tabIndex={value === t.id ? 0 : -1}
          onClick={() => onChange(t.id)}
          className={cx(
            'my-1 flex h-8 shrink-0 cursor-pointer items-center rounded-md px-3 text-sm whitespace-nowrap transition-colors duration-150 hover:bg-panel-2/70',
            value === t.id ? 'font-medium text-fg' : 'text-muted hover:text-fg',
          )}
        >
          {t.label}
          {extra?.(t.id)}
        </button>
      ))}
      <span
        aria-hidden
        className={cx(
          'absolute bottom-0 left-0 h-0.5 rounded-full bg-fg',
          !bar && 'opacity-0',
          slide && 'transition-[translate,width] duration-200 ease-out',
        )}
        style={bar ? { width: bar.width, translate: `${bar.left}px 0` } : undefined}
      />
    </div>
    {action ? <div className="flex w-full items-center gap-2 py-1.5 sm:w-auto">{action}</div> : null}
    </div>
  );
}
