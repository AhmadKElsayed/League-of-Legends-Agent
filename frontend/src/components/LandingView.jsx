import React from 'react';

export function LandingView({ onQueryClick }) {
  const chips = [
    { query: "What is the best build and skill order for Jinx in the current patch?", emoji: "⚔️", title: "Combat Build", desc: "Optimize Jinx runes and items" },
    { query: "How does Kayle survive the early lane matchup against Jax?", emoji: "🛡️", title: "Matchup Strategy", desc: "Kayle vs Jax lane tactics" },
    { query: "Explain the lore relationship between Aurelion Sol and the Targonian Aspect of War.", emoji: "📜", title: "Runeterra Lore", desc: "Aurelion Sol's cosmic history" },
    { query: "Who are the current S-tier Midlaners and what makes them strong in the meta?", emoji: "📈", title: "Meta Analytics", desc: "Find top-tier mid pick rates" }
  ];

  return (
    <div id="landing-view" className="landing-view">
      <div className="hextech-core-container">
        <div className="hextech-core-outer"></div>
        <div className="hextech-core-inner"></div>
        <div className="hextech-core-center"></div>
      </div>
      <h1 className="landing-title">Hextech Intelligence Console</h1>
      <p className="landing-subtitle">Welcome, Summoner. Powered by Runeterra Core and OP.GG match analytics. Select a query matrix or write your own.</p>
      
      <div className="starter-chips-container">
        {chips.map((chip, idx) => (
          <div key={idx} className="starter-chip" onClick={() => onQueryClick(chip.query)}>
            <span className="chip-emoji">{chip.emoji}</span>
            <div className="chip-content">
              <span className="chip-title">{chip.title}</span>
              <span className="chip-desc">{chip.desc}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
