import * as React from "react"
import { Drawer as DrawerPrimitive } from "@base-ui/react/drawer"

import { cn } from "@/lib/utils"

function Sheet({
  modal = false,
  ...props
}: DrawerPrimitive.Root.Props) {
  return <DrawerPrimitive.Root data-slot="sheet" modal={modal} {...props} />
}

function SheetTrigger({ ...props }: DrawerPrimitive.Trigger.Props) {
  return <DrawerPrimitive.Trigger data-slot="sheet-trigger" {...props} />
}

function SheetPortal({ ...props }: DrawerPrimitive.Portal.Props) {
  return <DrawerPrimitive.Portal data-slot="sheet-portal" {...props} />
}

function SheetClose({ ...props }: DrawerPrimitive.Close.Props) {
  return <DrawerPrimitive.Close data-slot="sheet-close" {...props} />
}

function SheetOverlay({
  className,
  ...props
}: DrawerPrimitive.Backdrop.Props) {
  return (
    <DrawerPrimitive.Backdrop
      data-slot="sheet-overlay"
      className={cn(
        "fixed inset-0 z-40 bg-black/20",
        className,
      )}
      {...props}
    />
  )
}

function SheetContent({
  className,
  children,
  ...props
}: DrawerPrimitive.Popup.Props) {
  return (
    <SheetPortal>
      <SheetOverlay />
      <DrawerPrimitive.Popup
        data-slot="sheet-content"
        className={cn(
          // Position: fixed right side overlay — does NOT move/squeeze the table
          "fixed right-0 top-0 bottom-0 z-50",
          // Width: resizable between 400-800px; resize handle from the left edge
          "min-w-[400px] max-w-[800px] w-[480px]",
          // Appearance
          "border-l border-border shadow-xl bg-background",
          // Layout
          "flex flex-col overflow-hidden",
          // Animations
          "data-open:animate-in data-closed:animate-out",
          "data-open:slide-in-from-right data-closed:slide-out-to-right",
          "duration-200",
          // Horizontal resize from left edge via CSS (rtl trick)
          "resize-x direction-rtl",
          className,
        )}
        style={{ direction: "rtl" }}
        {...props}
      >
        {/* Inner wrapper restores ltr direction */}
        <div className="flex flex-col h-full overflow-hidden" style={{ direction: "ltr" }}>
          {children}
        </div>
      </DrawerPrimitive.Popup>
    </SheetPortal>
  )
}

function SheetTitle({
  className,
  ...props
}: DrawerPrimitive.Title.Props) {
  return (
    <DrawerPrimitive.Title
      data-slot="sheet-title"
      className={cn("text-base leading-none font-medium", className)}
      {...props}
    />
  )
}

export {
  Sheet,
  SheetClose,
  SheetContent,
  SheetOverlay,
  SheetPortal,
  SheetTitle,
  SheetTrigger,
}
