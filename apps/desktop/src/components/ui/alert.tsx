import * as React from 'react';
import { cn } from '../../lib/utils';

export function Alert({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('rounded-lg border border-border bg-muted p-3 text-xs', className)} role="alert" {...props} />;
}
