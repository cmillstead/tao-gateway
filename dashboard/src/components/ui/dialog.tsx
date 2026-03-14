import * as React from "react";
import { cn } from "@/lib/utils";
import { X } from "lucide-react";

interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children: React.ReactNode;
}

function Dialog({ open, children }: DialogProps) {
  React.useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  if (!open) return null;

  return <>{children}</>;
}

interface DialogContentProps extends React.HTMLAttributes<HTMLDivElement> {
  onClose: () => void;
  preventBackdropClose?: boolean;
  preventEscapeClose?: boolean;
}

const DialogContent = React.forwardRef<HTMLDivElement, DialogContentProps>(
  (
    {
      className,
      children,
      onClose,
      preventBackdropClose = false,
      preventEscapeClose = false,
      ...props
    },
    ref,
  ) => {
    const contentRef = React.useRef<HTMLDivElement>(null);
    const previousFocusRef = React.useRef<HTMLElement | null>(null);

    // Store the previously focused element to restore on close
    React.useEffect(() => {
      previousFocusRef.current = document.activeElement as HTMLElement;
      return () => {
        previousFocusRef.current?.focus();
      };
    }, []);

    // Focus the first focusable element on mount
    React.useEffect(() => {
      const el = contentRef.current;
      if (el) {
        const focusable = el.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
        );
        if (focusable.length > 0) {
          focusable[0].focus();
        }
      }
    }, []);

    // Escape key handler
    React.useEffect(() => {
      if (preventEscapeClose) return;
      function handleKeyDown(e: KeyboardEvent) {
        if (e.key === "Escape") {
          e.stopPropagation();
          onClose();
        }
      }
      document.addEventListener("keydown", handleKeyDown);
      return () => document.removeEventListener("keydown", handleKeyDown);
    }, [onClose, preventEscapeClose]);

    // Focus trap
    React.useEffect(() => {
      const el = contentRef.current;
      if (!el) return;
      function handleKeyDown(e: KeyboardEvent) {
        if (e.key !== "Tab") return;
        const focusable = el!.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
        );
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
      document.addEventListener("keydown", handleKeyDown);
      return () => document.removeEventListener("keydown", handleKeyDown);
    }, []);

    const dialogId = React.useId();
    const titleId = `${dialogId}-title`;
    const descId = `${dialogId}-desc`;

    return (
      <>
        <div
          className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm"
          onClick={preventBackdropClose ? undefined : onClose}
          aria-hidden="true"
        />
        <div
          ref={ref}
          role="dialog"
          aria-modal="true"
          aria-labelledby={titleId}
          aria-describedby={descId}
          className={cn(
            "fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-lg border border-border bg-background p-6 shadow-lg",
            className,
          )}
          {...props}
        >
          <div ref={contentRef}>
            <DialogIdContext.Provider value={{ titleId, descId }}>
              {children}
            </DialogIdContext.Provider>
          </div>
          <button
            onClick={onClose}
            className="absolute right-4 top-4 rounded-sm opacity-70 hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </>
    );
  },
);
DialogContent.displayName = "DialogContent";

// Context for passing IDs to title/description
const DialogIdContext = React.createContext<{
  titleId: string;
  descId: string;
}>({ titleId: "", descId: "" });

function DialogHeader({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("flex flex-col space-y-1.5 text-left", className)}
      {...props}
    />
  );
}

function DialogTitle({
  className,
  ...props
}: React.HTMLAttributes<HTMLHeadingElement>) {
  const { titleId } = React.useContext(DialogIdContext);
  return (
    <h2
      id={titleId}
      className={cn(
        "text-lg font-semibold leading-none tracking-tight",
        className,
      )}
      {...props}
    />
  );
}

function DialogDescription({
  className,
  ...props
}: React.HTMLAttributes<HTMLParagraphElement>) {
  const { descId } = React.useContext(DialogIdContext);
  return (
    <p
      id={descId}
      className={cn("text-sm text-muted-foreground", className)}
      {...props}
    />
  );
}

function DialogFooter({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2 mt-6",
        className,
      )}
      {...props}
    />
  );
}

export {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
};
