import { createPortal } from "react-dom"
import type { ReactNode } from "react"

/** Renders modals on document.body so timeline/dnd layers cannot paint above them. */
export function ModalPortal({ children }: { children: ReactNode }) {
  return createPortal(children, document.body)
}
