/* eslint-disable react-refresh/only-export-components */
import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "../../lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-none text-sm font-bold uppercase tracking-wide transition-all focus-visible:outline-none focus-visible:ring-2 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0 border-2 border-[var(--border)] hover:-translate-y-1 hover:shadow-[4px_4px_0px_0px_var(--border)] active:translate-y-0 active:shadow-none duration-200",
  {
    variants: {
      variant: {
        default:
          "bg-[var(--accent)] text-[var(--background)] hover:bg-[var(--accent)]/90",
        destructive:
          "bg-red-600 text-white hover:bg-red-700",
        outline:
          "bg-[var(--background)] text-[var(--foreground)] hover:bg-[var(--foreground)] hover:text-[var(--background)]",
        secondary:
          "bg-[var(--surface)] text-[var(--foreground)] hover:bg-[var(--foreground)] hover:text-[var(--background)]",
        ghost: "border-transparent hover:border-[var(--border)] hover:bg-[var(--surface)] hover:shadow-none hover:-translate-y-0",
        link: "border-transparent shadow-none hover:shadow-none hover:-translate-y-0 text-[var(--accent)] underline-offset-4 hover:underline",
        glass: "bg-[var(--surface)] text-[var(--foreground)]"
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-8 rounded-md px-3 text-xs",
        lg: "h-12 rounded-md px-8",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
