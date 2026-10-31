import React from "react";
import { cn } from "../../lib/utils";
import { DotPattern } from "./dot-pattern";

export interface BackgroundComponentProps {
  children?: React.ReactNode;
  className?: string;
}

export const BackgroundGlow: React.FC<BackgroundComponentProps> = ({ children, className }) => {
  return (
    <div className={cn("min-h-screen w-full relative bg-slate-50/60 overflow-x-hidden", className)}>
      {/* Subtle Dot Pattern Grid for Whole Webapp */}
      <DotPattern
        width={20}
        height={20}
        cx={1}
        cy={1}
        cr={1}
        className={cn(
          "fill-slate-300/60 [mask-image:radial-gradient(ellipse_at_top,white_40%,transparent_90%)]",
        )}
      />

      {/* Soft Civic Teal & Yellow Glow Accent */}
      <div
        className="absolute inset-0 z-0 pointer-events-none"
        style={{
          backgroundImage: `
            radial-gradient(circle at 50% 10%, rgba(18, 60, 58, 0.05) 0%, transparent 60%),
            radial-gradient(circle at 80% 30%, rgba(255, 249, 145, 0.25) 0%, transparent 50%),
            radial-gradient(circle at 20% 70%, rgba(147, 197, 253, 0.20) 0%, transparent 60%)
          `,
        }}
      />

      {/* Content */}
      <div className="relative z-10 w-full min-h-screen flex flex-col">
        {children}
      </div>
    </div>
  );
};

export default BackgroundGlow;
