import React from 'react';
import './HomeFooter.css';

const supporters = [
  { src: '/assets/logo_eu-BaS7zlNS.png', name: 'Funded by the European Union', className: 'home-footer-eu' },
  { src: '/assets/logo_internews-CLywPOlF.png', name: 'Internews', className: 'home-footer-internews' },
];

export default function HomeFooter() {
  return <footer className="home-footer" aria-label="Pengembang dan pendukung">
    <div className="home-footer-inner">
      <section className="home-footer-developer" aria-label="Pengembang">
        <h2>Developed by</h2>
        <a className="home-footer-identity" href="https://idjnetwork.org" target="_blank" rel="noopener noreferrer" aria-label="Indonesian Data Journalism Network (buka di tab baru)">
          <img src="/assets/pyproject.png" alt="IDJN" width="30" height="30" />
          <span>Indonesian Data<br />Journalism Network</span>
        </a>
      </section>
      <section className="home-footer-supporters" aria-label="Pendukung">
        <h2>Supported by</h2>
        <div className="home-footer-logos">
          {supporters.map(supporter => <div className="home-footer-logo" key={supporter.src}>
            <img src={supporter.src} alt={supporter.name} className={supporter.className} />
          </div>)}
        </div>
      </section>
    </div>
  </footer>;
}
