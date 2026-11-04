import React, { useEffect, useState } from 'react';
import { Activity } from 'lucide-react';

interface VoiceVisualizerProps {
  isActive: boolean;
  transcribedText?: string;
  isProcessing?: boolean;
}

export const VoiceVisualizer: React.FC<VoiceVisualizerProps> = ({
  isActive,
  transcribedText,
  isProcessing,
}) => {
  const [bars, setBars] = useState<number[]>(Array(20).fill(0.2));
  const animationRef = React.useRef<number | null>(null);

  useEffect(() => {
    if (!isActive && !isProcessing) {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
      return;
    }

    const animate = () => {
      setBars((prev) =>
        prev.map(() => {
          const newHeight = isActive ? Math.random() * 0.8 + 0.2 : 0.2;
          return newHeight;
        })
      );
      animationRef.current = requestAnimationFrame(animate);
    };

    animate();

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [isActive, isProcessing]);

  return (
    <div className={`flex flex-col items-center justify-center p-6 ${isActive || isProcessing ? 'bg-dark-card rounded-lg border border-dark-border' : ''}`}>
      {/* Waveform Bars */}
      {(isActive || isProcessing) && (
        <div className="flex items-center justify-center gap-1 h-16 mb-4">
          {bars.map((height, i) => (
            <div
              key={i}
              className={`w-1 rounded-full transition-all ${
                isActive ? 'bg-accent-purple animate-pulse' : 'bg-accent-purple-dark'
              }`}
              style={{
                height: `${height * 100}%`,
                opacity: isActive ? 0.8 : 0.6,
              }}
            />
          ))}
        </div>
      )}

      {/* Status Text */}
      <div className="text-center">
        {isActive && (
          <div className="flex items-center justify-center gap-2 mb-3">
            <div className="w-3 h-3 bg-red-500 rounded-full animate-pulse" />
            <span className="text-accent-purple font-medium">Listening...</span>
          </div>
        )}

        {isProcessing && !isActive && (
          <div className="flex items-center justify-center gap-2 mb-3">
            <Activity size={20} className="text-accent-purple animate-spin" />
            <span className="text-accent-purple font-medium">Processing...</span>
          </div>
        )}

        {/* Transcribed Text */}
        {transcribedText && (
          <div className="mt-4 p-3 bg-dark-bg rounded border border-dark-border max-w-md">
            <p className="text-sm text-dark-text-muted mb-1">You said:</p>
            <p className="text-dark-text italic">"{transcribedText}"</p>
          </div>
        )}
      </div>
    </div>
  );
};
