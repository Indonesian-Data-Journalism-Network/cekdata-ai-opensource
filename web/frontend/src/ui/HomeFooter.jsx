import React from 'react';
import './HomeFooter.css';

const supporters = [
  { src: '/assets/logo_eu-BaS7zlNS.png', name: 'Funded by the European Union', className: 'home-footer-eu' },
  { src: '/assets/logo_internews-CLywPOlF.png', name: 'Internews', className: 'home-footer-internews' },
  { src: '/assets/donors/ims.png', name: 'IMS — International Media Support', className: 'home-footer-ims' },
  { src: '/assets/donors/informed-earth-bright-green.png', name: 'Informed Earth', className: 'home-footer-informed', frameClassName: 'home-footer-informed-frame' },
];

export default function HomeFooter({ onNavigate }) {
  return <footer className="home-footer" aria-label="Pengembang dan pendukung">
    <div className="home-footer-inner">
      <section className="home-footer-developer" aria-label="Pengembang">
        <h2>Developed by</h2>
        <a className="home-footer-identity" href="https://idjnetwork.org" target="_blank" rel="noopener noreferrer" aria-label="Indonesian Data Journalism Network (buka di tab baru)">
          <img src="/assets/pyproject.png" alt="IDJN" width="30" height="30" />
          <span>Indonesian Data<br />Journalism Network</span>
        </a>
        <nav className="home-footer-navigation" aria-label="Tentang Cek Data AI dan pengembang">
          <a href="https://idjnetwork.org/tentang-kami/" target="_blank" rel="noopener noreferrer">Tentang IDJN</a>
          <button type="button" onClick={() => onNavigate('about')}>Tentang Cek Data AI</button>
          <button type="button" onClick={() => onNavigate('team')}>Tim Pengembangan</button>
        </nav>
      </section>
      <section className="home-footer-supporters" aria-label="Pendukung">
        <h2>Supported by</h2>
        <div className="home-footer-logos">
          {supporters.map(supporter => <div className={`home-footer-logo ${supporter.frameClassName || ''}`} key={supporter.src}>
            <img src={supporter.src} alt={supporter.name} className={supporter.className} />
          </div>)}
        </div>
      </section>

    </div>
  </footer>;
}
