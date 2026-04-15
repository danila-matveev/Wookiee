import type { Transition, Variants } from "motion/react"

// ─── Spring presets ───

export const springDefault: Transition = {
  type: "spring",
  stiffness: 300,
  damping: 30,
  mass: 0.8,
}

export const springSnappy: Transition = {
  type: "spring",
  stiffness: 500,
  damping: 35,
  mass: 0.5,
}

export const springGentle: Transition = {
  type: "spring",
  stiffness: 200,
  damping: 25,
  mass: 1,
}

// ─── Stagger variants ───

export const staggerContainer: Variants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.05 },
  },
}

export const staggerItem: Variants = {
  hidden: { opacity: 0, y: 8 },
  visible: {
    opacity: 1,
    y: 0,
    transition: springDefault,
  },
}
