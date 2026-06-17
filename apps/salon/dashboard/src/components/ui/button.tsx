/* eslint-disable react-refresh/only-export-components */
import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "../../lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[var(--radius-md)] text-sm font-bold uppercase tracking-wide transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0 border border-[var(--border)] hover:-translate-y-0.5 active:translate-y-0",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-[image:var(--grad)] text-white hover:glow-accent",
        destructive:
          "border-transparent bg-[var(--danger)] text-[#1a0b0f] hover:brightness-110",
        outline:
          "bg-transparent text-[var(--foreground)] hover:bg-[var(--purple-soft)] hover:border-[var(--accent)]",
        secondary:
          "glass-panel text-[var(--foreground)] hover:border-[var(--accent)]",
        ghost: "border-transparent hover:bg-[var(--surface-glass)] hover:-translate-y-0",
        link: "border-transparent hover:-translate-y-0 text-[var(--accent)] underline-offset-4 hover:underline",
        glass: "glass-panel text-[var(--foreground)] hover:glow-accent"
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-8 px-3 text-xs",
        lg: "h-12 px-8",
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
