import React, { useState, useEffect } from 'react';

const splashImages = {
  ryze: 'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Ryze_11.jpg',
  aurelion: 'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/AurelionSol_0.jpg',
  jinx: 'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Jinx_0.jpg',
  ahri: 'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Ahri_0.jpg',
  yasuo: 'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Yasuo_0.jpg',
  lux: 'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Lux_17.jpg',
  senna: 'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Senna_0.jpg',
  pantheon: 'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Pantheon_0.jpg',
  zed: 'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Zed_0.jpg',
  akali: 'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Akali_0.jpg',
  ekko: 'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Ekko_0.jpg',
  diana: 'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Diana_0.jpg',
  sylas: 'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Sylas_0.jpg',
  leona: 'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Leona_0.jpg',
  azir: 'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Azir_0.jpg',
  leesin: 'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/LeeSin_0.jpg',
  thresh: 'https://ddragon.leagueoflegends.com/cdn/img/champion/splash/Thresh_0.jpg'
};

const splashKeys = Object.keys(splashImages);

export function Backgrounds({ onBgNameChange }) {
  const [currentBgLayer, setCurrentBgLayer] = useState(1);
  const [layer1Url, setLayer1Url] = useState(splashImages.ryze);
  const [layer2Url, setLayer2Url] = useState('');
  const [currentIndex, setCurrentIndex] = useState(0);

  const nameMap = {
    ryze: 'Ryze', aurelion: 'Aurelion Sol', jinx: 'Jinx',
    ahri: 'Ahri', yasuo: 'Yasuo', lux: 'Lux', senna: 'Senna',
    pantheon: 'Pantheon', zed: 'Zed', akali: 'Akali', ekko: 'Ekko',
    diana: 'Diana', sylas: 'Sylas', leona: 'Leona', azir: 'Azir',
    leesin: 'Lee Sin', thresh: 'Thresh'
  };

  useEffect(() => {
    // Initial call
    if (onBgNameChange) onBgNameChange(nameMap['ryze']);

    const interval = setInterval(() => {
      setCurrentIndex(prev => {
        const nextIndex = (prev + 1) % splashKeys.length;
        const champKey = splashKeys[nextIndex];
        const url = splashImages[champKey];

        if (onBgNameChange) onBgNameChange(nameMap[champKey] || champKey);

        setCurrentBgLayer(layer => {
          if (layer === 1) {
            setLayer2Url(url);
            return 2;
          } else {
            setLayer1Url(url);
            return 1;
          }
        });

        return nextIndex;
      });
    }, 12000);

    return () => clearInterval(interval);
  }, [onBgNameChange]);

  return (
    <>
      <div id="bg-layer-1" className={`bg-layer ${currentBgLayer === 1 ? 'active' : ''}`} style={{ backgroundImage: layer1Url ? `url('${layer1Url}')` : 'none' }}></div>
      <div id="bg-layer-2" className={`bg-layer ${currentBgLayer === 2 ? 'active' : ''}`} style={{ backgroundImage: layer2Url ? `url('${layer2Url}')` : 'none' }}></div>
      <div id="overlay"></div>
    </>
  );
}
