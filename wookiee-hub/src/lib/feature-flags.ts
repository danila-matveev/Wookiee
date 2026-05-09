export const featureFlags = {
  marketing: import.meta.env.VITE_FEATURE_MARKETING === 'true',
} as const

export type FeatureFlag = keyof typeof featureFlags
export const isEnabled = (flag: FeatureFlag): boolean => featureFlags[flag]
