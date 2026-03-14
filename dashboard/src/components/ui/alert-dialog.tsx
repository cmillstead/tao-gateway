import * as React from "react";
import { cn } from "@/lib/utils";

interface AlertDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children: React.ReactNode;
}

function AlertDialog({ open, children }: AlertDialogProps) {
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

  // AlertDialog does NOT close on Escape — user must use explicit action buttons

  if (!open) return null;

  return <>{children}</>;
}

const AlertDialogContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, children, ...props }, ref) => {
  const contentRef = React.useRef<HTMLDivElement>(null);
  const previousFocusRef = React.useRef<HTMLElement | null>(null);

  // Store and restore focus
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

  // Focus trap
  React.useEffect(() => {
    const el = contentRef.current;
    if (!el) return;
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        return;
      }
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
        aria-hidden="true"
      />
      <div
        ref={ref}
        role="alertdialog"
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
          <AlertDialogIdContext.Provider value={{ titleId, descId }}>
            {children}
          </AlertDialogIdContext.Provider>
        </div>
      </div>
    </>
  );
});
AlertDialogContent.displayName = "AlertDialogContent";

const AlertDialogIdContext = React.createContext<{
  titleId: string;
  descId: string;
}>({ titleId: "", descId: "" });

function AlertDialogHeader({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("flex flex-col space-y-2 text-left", className)}
      {...props}
    />
  );
}

function AlertDialogTitle({
  className,
  ...props
}: React.HTMLAttributes<HTMLHeadingElement>) {
  const { titleId } = React.useContext(AlertDialogIdContext);
  return <h2 id={titleId} className={cn("text-lg font-semibold", className)} {...props} />;
}

function AlertDialogDescription({
  className,
  ...props
}: React.HTMLAttributes<HTMLParagraphElement>) {
  const { descId } = React.useContext(AlertDialogIdContext);
  return (
    <p
      id={descId}
      className={cn("text-sm text-muted-foreground", className)}
      {...props}
    />
  );
}

function AlertDialogFooter({
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
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
};
