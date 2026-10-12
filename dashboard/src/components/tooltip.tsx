import { mergeProps } from '@base-ui/react/merge-props';
import { Tooltip as BaseTooltip } from '@base-ui/react/tooltip';
import { cloneElement, isValidElement, type ReactNode, useId } from 'react';

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
  return (
    <BaseTooltip.Root disabled={disabled} disableHoverablePopup>
      <BaseTooltip.Trigger
        delay={HOVER_MS}
        render={(props, state: TriggerState) => renderTrigger(children, props, state.open ? id : undefined)}
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

type ChildProps = { className?: unknown; ref?: unknown; type?: unknown };

// Puts the trigger on the child. Event handlers from the child and from Base UI both run.
function renderTrigger(children: ReactNode, props: React.ComponentPropsWithRef<'button'>, describedBy: string | undefined) {
  const described = [props['aria-describedby'], describedBy].filter(Boolean).join(' ') || undefined;
  const triggerProps = { ...props, 'aria-describedby': described };
  if (isValidElement<ChildProps>(children)) {
    const childProps = children.props;
    const merged = mergeProps(childProps, triggerProps);
    merged.ref = composeRef(childProps.ref, props.ref);
    if (typeof childProps.className === 'function') merged.className = childProps.className;
    if (children.type !== 'button') delete merged.type;
    return cloneElement(children, merged);
  }
  const { type: _type, ...spanProps } = triggerProps;
  return <span {...spanProps}>{children}</span>;
}

function composeRef(childRef: unknown, triggerRef: unknown) {
  if (!childRef) return triggerRef;
  if (!triggerRef) return childRef;
  return (node: Element | null) => {
    writeRef(childRef, node);
    writeRef(triggerRef, node);
  };
}

function writeRef(ref: unknown, node: Element | null) {
  if (typeof ref === 'function') ref(node);
  else if (ref && typeof ref === 'object' && 'current' in ref) (ref as { current: Element | null }).current = node;
}
