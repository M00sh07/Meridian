import { motion, AnimatePresence } from "motion/react";

export const ease = [0.22, 1, 0.36, 1] as const;

export const fadeUp = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.45, ease },
};

export const stagger = (delay = 0.06) => ({
  animate: { transition: { staggerChildren: delay } },
});

export { motion, AnimatePresence };