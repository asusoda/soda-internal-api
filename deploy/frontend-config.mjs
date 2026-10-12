// Writes config.js for the dashboard container from the container env when the container starts.
// One image then runs with any API URL. index.html loads config.js before the bundle.
// Usage: node frontend-config.mjs <output file> NAME[:required] ...
import { writeFileSync } from 'node:fs';

const [output, ...names] = process.argv.slice(2);
if (!output || names.length === 0) {
  console.error('Usage: node frontend-config.mjs <output file> NAME[:required] ...');
  process.exit(2);
}

const config = {};
for (const spec of names) {
  const [name, flag] = spec.split(':');
  const value = (process.env[name] ?? '').trim();
  if (value) {
    config[name] = value;
  } else if (flag === 'required') {
    console.error(`${name} is not set. Set it in Doppler (for example https://api.thesoda.io) and recreate the container.`);
    process.exit(1);
  }
}

writeFileSync(output, `window.__PLATFORM_CONFIG__ = ${JSON.stringify(config)};\n`);
console.log(`Wrote ${output} with ${Object.keys(config).join(', ') || 'no settings'}.`);
