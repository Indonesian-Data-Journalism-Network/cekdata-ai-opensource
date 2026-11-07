import {writeFile, rm} from 'node:fs/promises';
// Public builds never distribute locally generated GFW CSV evidence bundles.
await rm(new URL('../dist-public/gfw-evidence',import.meta.url),{recursive:true,force:true});
await writeFile(new URL('../dist-public/_redirects',import.meta.url),
  '/api/*  /.netlify/functions/api/:splat  200!\n/*  /index.html  200\n');
