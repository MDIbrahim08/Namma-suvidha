import React from "react";
import { cn } from "../../lib/utils";

export interface BackgroundComponentProps {
  children?: React.ReactNode;
  className?: string;
}

export const BackgroundGlow: React.FC<BackgroundComponentProps> = ({ children, className }) => {
  return (
    <div className={cn("min-h-screen w-full relative bg-white", className)}>
      {/* Soft Yellow Glow */}
      <div
        className="absolute inset-0 z-0 pointer-events-none"
        style={{
          backgroundImage: `
            radial-gradient(circle at center, #FFF991 0%, transparent 70%)
          `,
          opacity: 0.6,
          mixBlendMode: "multiply",
        }}
      />
      {/* Light Sky Blue Ambient Glow */}
      <div
        className="absolute inset-0 z-0 pointer-events-none opacity-40"
        style={{
          backgroundImage: `
            radial-gradient(circle at 60% 40%, #93c5fd 0%, transparent 60%)
          `,
        }}
      />
      {/* Content */}
      <div className="relative z-10 w-full min-h-screen">
        {children}
      </div>
    </div>
  );
};

export default BackgroundGlow;

