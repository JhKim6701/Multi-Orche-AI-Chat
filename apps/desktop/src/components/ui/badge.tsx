import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';

import { cn } from '../../lib/utils';

const badgeVariants = cva('inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium', {
  variants: {
    variant: {
      default: 'border-border bg-muted text-slate-700',
      success: 'border-emerald-200 bg-emerald-50 text-emerald-700',
      warning: 'border-amber-200 bg-amber-50 text-amber-700',
      danger: 'border-red-200 bg-red-50 text-red-700',
      info: 'border-blue-200 bg-blue-50 text-blue-700',
    },
  },
  defaultVariants: {
    variant: 'default',
  },
});

function Badge({ className, variant, ...props }: React.HTMLAttributes<HTMLDivElement> & VariantProps<typeof badgeVariants>) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
