import React from 'react';
import './TeamPage.css';

// Professional backgrounds, not assignments of responsibilities within this project.
const team = [
  {
    name: 'Kurniawan Pujianto',
    bio: 'Developer dan programmer yang tergabung dalam tim pengembangan Cek Data AI.',
    sources: [], // Background confirmed by the project owner; no verified public profile yet.
  },
  {
    name: 'Irma Garnesia',
    bio: 'Direktur Riset IDJN, peneliti, pemeriksa fakta, dan pelatih jurnalisme data. Mendampingi jurnalis mengembangkan pelaporan berbasis data, dengan pengalaman dalam riset kuantitatif dan kualitatif, analisis survei, serta visualisasi data.',
    sources: [{ label: 'Profil di IDJN', url: 'https://idjnetwork.org/anggota/' }],
  },
  {
    name: 'Louis Lugas',
    bio: 'Direktur Komunikasi & Kolaborasi IDJN, pengembang web, dan desainer grafis. Menggabungkan riset, pengolahan data, pemetaan, dan pemrograman untuk menghasilkan infografik, artikel interaktif, serta permainan berbasis berita bagi media dan organisasi masyarakat sipil.',
    sources: [{ label: 'Profil di IDJN', url: 'https://idjnetwork.org/anggota/' }],
  },
  {
    name: 'Johanes Hutabarat',
    bio: 'Jurnalis yang berbasis di Jakarta dan pernah bekerja di The Gecko Project serta Kumparan. Karyanya juga terbit di BBC News Indonesia, TRT World, dan Project Multatuli, termasuk peliputan isu energi dan lingkungan.',
    sources: [{ label: 'Profil dan karya di Tanah Air', url: 'https://tanahair.net/id/batubara-captive-ekspansi-yang-tak-terpantau/' }],
  },
  {
    name: 'Mawa Kresna',
    bio: 'Direktur Eksekutif IDJN dan editor Project Multatuli. Menekuni isu agraria, keberagaman, dan hak asasi manusia. Pernah bekerja di Tirto.id dan meraih penghargaan jurnalistik untuk peliputan pekerja rumah tangga serta isu agraria.',
    sources: [
      { label: 'Profil di IDJN', url: 'https://idjnetwork.org/anggota/' },
      { label: 'Tim Project Multatuli', url: 'https://projectmultatuli.org/tentang/tim-kami/' },
    ],
  },
];

export default function TeamPage({ onBack }) {
  return <main className="team-page">
    <button className="team-back" type="button" onClick={onBack}>← Kembali ke Home</button>
    <header className="team-intro">
      <p className="team-eyebrow">CEK DATA AI</p>
      <h1>Tim Pengembangan</h1>
      <p>Orang-orang di balik pengembangan Cek Data AI.</p>
    </header>
    <div className="team-list">
      {team.map(member => <article className="team-member" key={member.name}>
        <h2>{member.name}</h2>
        <div>
          <p>{member.bio}</p>
          {member.sources.length > 0 && <div className="team-sources">
            {member.sources.map(source => <a key={source.url} href={source.url} target="_blank" rel="noopener noreferrer">
              {source.label} <span aria-hidden="true">↗</span>
            </a>)}
          </div>}
        </div>
      </article>)}
    </div>
  </main>;
}
