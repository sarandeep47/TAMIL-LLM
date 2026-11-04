import React from 'react';

interface SuggestionCard {
  icon: React.ReactNode;
  title: string;
  description: string;
  onClick: () => void;
}

interface WelcomeScreenProps {
  userName: string;
  suggestions: SuggestionCard[];
}

export const WelcomeScreen: React.FC<WelcomeScreenProps> = ({ userName, suggestions }) => {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen pb-32 px-4">
      {/* Greeting */}
      <div className="text-center mb-16">
        <h1 className="text-5xl md:text-6xl font-bold text-white mb-2">
          Hello, <span className="text-accent-purple">{userName}</span> 👋
        </h1>
        <p className="text-xl text-dark-text-muted">How can I help you today?</p>
      </div>

      {/* Suggestion Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 max-w-2xl w-full">
        {suggestions.map((card, index) => (
          <button
            key={index}
            onClick={card.onClick}
            className="p-6 bg-gradient-to-br from-dark-card to-dark-bg border border-dark-border rounded-2xl hover:border-accent-purple hover:shadow-lg hover:shadow-accent-purple/20 transition transform hover:scale-105 group text-left"
          >
            <div className="flex items-start gap-4">
              <div className="p-3 bg-accent-purple/10 rounded-lg group-hover:bg-accent-purple/20 transition">
                {card.icon}
              </div>
              <div className="flex-1">
                <h3 className="font-semibold text-white mb-1 group-hover:text-accent-purple transition">
                  {card.title}
                </h3>
                <p className="text-sm text-dark-text-muted">{card.description}</p>
              </div>
            </div>
          </button>
        ))}
      </div>

      {/* Features List */}
      <div className="mt-16 text-center text-dark-text-muted text-sm">
        <p>💡 Tip: You can type messages or use the microphone button for voice input</p>
      </div>
    </div>
  );
};
