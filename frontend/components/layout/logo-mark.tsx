import Image from 'next/image';

import { cn } from '../../lib/utils';

export function LogoMark({
  collapsed = false,
  auth = false,
}: Readonly<{ collapsed?: boolean; auth?: boolean }>) {
  const mark = (
    <Image
      src="/invoro-logo.svg"
      className="app-logo-image"
      alt=""
      width={96}
      height={96}
      aria-hidden="true"
      draggable={false}
    />
  );

  if (collapsed) {
    return (
      <div className="app-logo app-logo-collapsed">
        <div className="app-logo-mark">{mark}</div>
      </div>
    );
  }

  return (
    <div className="app-logo">
      <div className={cn('app-logo-mark', auth && 'app-logo-mark-large')}>{mark}</div>
      <div className="app-logo-copy">
        <span className="app-logo-title">Invoro</span>
      </div>
    </div>
  );
}
