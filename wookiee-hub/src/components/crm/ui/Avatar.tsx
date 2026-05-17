import { cn } from '@/lib/utils';

const palettes = [
  'bg-[#F97316]',
  'bg-[#3B82F6]',
  'bg-stone-500',
  'bg-[#EC4899]',
  'bg-[#10B981]',
  'bg-[#F59E0B]',
];

function colorFor(seed: string): string {
  let h = 0;
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) | 0;
  return palettes[Math.abs(h) % palettes.length];
}

const sizes = {
  xs: 'size-7 text-[11px]',
  sm: 'size-8 text-xs',
  md: 'size-12 text-base',
  lg: 'size-16 text-2xl',
} as const;

interface AvatarProps {
  name: string;
  size?: keyof typeof sizes;
  className?: string;
}

export function Avatar({ name, size = 'sm', className }: AvatarProps) {
  const initials = name
    .split(/\s+|\./)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? '')
    .join('');
  return (
    <span
      role="img"
      aria-label={name || 'avatar'}
      className={cn(
        'inline-flex items-center justify-center rounded-full text-white font-semibold font-display shrink-0',
        sizes[size],
        colorFor(name),
        className,
      )}
    >
      {initials || '?'}
    </span>
  );
}

export type { AvatarProps };
