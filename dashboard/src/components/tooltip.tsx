import { mergeProps } from '@base-ui/react/merge-props';
import { Tooltip as BaseTooltip } from '@base-ui/react/tooltip';
import { cloneElement, Fragment, isValidElement, type ReactNode, useId, useRef } from 'react';

type Side = 'right' | 'top' | 'bottom';

// How long a tooltip waits before it opens on hover. A later tooltip in the same group opens at once.
const HOVER_MS = 350;

// The key name of Ctrl on this computer: the Command sign on a Mac.
export const MOD_KEY = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform) ? '⌘' : 'Ctrl';

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="inline-flex h-4 min-w-4 items-center justify-center rounded border border-current/25 px-1 font-sans text-[10px] leading-none opacity-80">
      {children}
    </kbd>
  );
}

// One delay for every tooltip. Adjacent tips open at once while one is open.
export function TooltipProvider({ children }: { children: ReactNode }) {
  return <BaseTooltip.Provider delay={HOVER_MS}>{children}</BaseTooltip.Provider>;
}

type TriggerState = { open: boolean };

// A label that shows next to its child on hover and keyboard focus. The child keeps its own aria-label.
// The tooltip is in a portal, so a scroll box does not clip it.
export function Tooltip({
  label,
  keys,
  side = 'right',
  disabled = false,
  children,
}: {
  label: ReactNode;
  keys?: string[];
  side?: Side;
  disabled?: boolean;
  children: ReactNode;
}) {
  const id = useId();
  const bindRef = useTriggerRef();
  return (
    <BaseTooltip.Root disabled={disabled} disableHoverablePopup>
      <BaseTooltip.Trigger
        delay={HOVER_MS}
        render={(props, state: TriggerState) => renderTrigger(children, props, state.open ? id : undefined, bindRef)}
      />
      <BaseTooltip.Portal>
        <BaseTooltip.Positioner side={side} sideOffset={side === 'right' ? 8 : 6} className="z-50">
          <BaseTooltip.Popup
            id={id}
            role="tooltip"
            className="pointer-events-none flex origin-(--transform-origin) items-center gap-2 rounded-md bg-fg px-2 py-1 text-xs font-medium whitespace-nowrap text-bg shadow-md outline-none transition-opacity duration-100 data-ending-style:opacity-0 data-starting-style:opacity-0"
          >
            {label}
            {keys?.length ? (
              <span className="flex gap-0.5">
                {keys.map((k) => (
                  <Kbd key={k}>{k}</Kbd>
                ))}
              </span>
            ) : null}
          </BaseTooltip.Popup>
        </BaseTooltip.Positioner>
      </BaseTooltip.Portal>
    </BaseTooltip.Root>
  );
}

type ChildProps = { className?: unknown; ref?: unknown; type?: unknown; 'aria-describedby'?: unknown };

type RefCallback = (node: Element | null) => (() => void) | void;

type BindRef = (child: unknown, trigger: unknown) => RefCallback;

// Puts the trigger on the child. A fragment gets a span. Event handlers from the child and from Base UI both run.
function renderTrigger(
  children: ReactNode,
  props: React.ComponentPropsWithRef<'button'>,
  describedBy: string | undefined,
  bindRef: BindRef,
) {
  if (!isValidElement<ChildProps>(children) || children.type === Fragment) {
    const { type: _type, ref: _ref, ...spanProps } = props;
    return (
      <span {...spanProps} ref={bindRef(undefined, props.ref)} aria-describedby={joinDescribed(props['aria-describedby'], describedBy)}>
        {children}
      </span>
    );
  }
  const childProps = children.props;
  const { type: _triggerType, ...triggerRest } = props;
  const described = joinDescribed(childProps['aria-describedby'], props['aria-describedby'], describedBy);
  const triggerProps = described ? { ...triggerRest, 'aria-describedby': described } : triggerRest;
  const merged = mergeProps(childProps, triggerProps);
  merged.ref = bindRef(childProps.ref, props.ref);
  if (typeof childProps.className === 'function') merged.className = childProps.className;
  return cloneElement(children, merged);
}

// A new callback when the child ref or the trigger ref changes. React then cleans
// up the previous refs and attaches these ones. The same callback stays while both refs stay.
function useTriggerRef(): BindRef {
  const composed = useRef<{ child: unknown; trigger: unknown; callback: RefCallback } | null>(null);

  return (child, trigger) => {
    const current = composed.current;
    if (current && current.child === child && current.trigger === trigger) return current.callback;
    const callback: RefCallback = (node) => {
      const cleanChild = attachRef(child, node);
      const cleanTrigger = attachRef(trigger, node);
      return () => {
        cleanChild?.();
        cleanTrigger?.();
      };
    };
    composed.current = { child, trigger, callback };
    return callback;
  };
}

function joinDescribed(...values: unknown[]): string | undefined {
  const ids = values.flatMap((value) => (typeof value === 'string' ? value.split(/\s+/) : []));
  const unique = ids.filter((id, index) => id && ids.indexOf(id) === index);
  return unique.length ? unique.join(' ') : undefined;
}

// Calls the cleanup a callback ref returns, and clears an object ref.
function attachRef(ref: unknown, node: Element | null): (() => void) | void {
  if (typeof ref === 'function') {
    const clean = ref(node);
    if (typeof clean === 'function') return clean;
    return () => {
      ref(null);
    };
  }
  if (ref && typeof ref === 'object' && 'current' in ref) {
    const box = ref as { current: Element | null };
    box.current = node;
    return () => {
      box.current = null;
    };
  }
}
