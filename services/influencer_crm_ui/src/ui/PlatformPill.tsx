import { cn } from '@/lib/cn';

const styles = {
  instagram: 'bg-gradient-to-br from-[#f58529] via-[#dd2a7b] to-[#8134af]',
  tiktok: 'bg-black',
  youtube: 'bg-[#FF0000]',
  telegram: 'bg-[#229ED9]',
  vk: 'bg-[#0077FF]',
} as const;

const labels = {
  instagram: 'IG',
  tiktok: 'TT',
  youtube: 'YT',
  telegram: 'TG',
  vk: 'VK',
} as const;

export type PlatformChannel = keyof typeof styles;

interface PlatformPillProps {
  channel: PlatformChannel;
  className?: string;
}

export function PlatformPill({ channel, className }: PlatformPillProps) {
  return (
    <span
      role="img"
      aria-label={channel}
      className={cn(
        'inline-flex size-[22px] items-center justify-center rounded-md text-[10px] font-bold text-white',
        styles[channel],
        className,
      )}
    >
      {labels[channel]}
    </span>
  );
}

export type { PlatformPillProps };
