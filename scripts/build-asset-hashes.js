const fs = require('fs');
const crypto = require('crypto');
const path = require('path');

const staticDir = path.join(__dirname, '..', 'server', 'static');

function fileHash(filePath) {
  const data = fs.readFileSync(filePath);
  return crypto.createHash('sha256').update(data).digest('hex').slice(0, 12);
}

const hashes = {};

const cssPath = path.join(staticDir, 'css', 'output.css');
if (fs.existsSync(cssPath)) {
  hashes['css/output.css'] = fileHash(cssPath);
}

const jsFiles = ['app.js', 'auth-session.js'];
for (const name of jsFiles) {
  const jsPath = path.join(staticDir, 'js', name);
  if (fs.existsSync(jsPath)) {
    hashes[name] = fileHash(jsPath);
  }
}

// Also hash page-specific modules
const modulesDir = path.join(staticDir, 'js', 'modules');
if (fs.existsSync(modulesDir)) {
  for (const name of fs.readdirSync(modulesDir)) {
    if (name.endsWith('.js')) {
      hashes[`modules/${name}`] = fileHash(path.join(modulesDir, name));
    }
  }
}

const outPath = path.join(staticDir, '.hashes.json');
fs.writeFileSync(outPath, JSON.stringify(hashes, null, 2) + '\n');
console.log(`Asset hashes written to ${outPath}`);
