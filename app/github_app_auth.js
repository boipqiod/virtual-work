const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

// 1. Read character from argument
const character = process.argv[2];
if (!character) {
  console.error("Usage: node github_app_auth.js <CharacterName>");
  process.exit(1);
}

// 2. Load .env manually to avoid external dependency
const envPath = path.join(__dirname, '../.env');
if (!fs.existsSync(envPath)) {
  console.error(".env file not found at", envPath);
  process.exit(1);
}

const envContent = fs.readFileSync(envPath, 'utf8');
const env = {};
envContent.split('\n').forEach(line => {
  const match = line.match(/^\s*([^#=]+)\s*=\s*(.*)$/);
  if (match) {
    const key = match[1].trim();
    let val = match[2].trim();
    // Strip optional quotes
    if (val.startsWith('"') && val.endsWith('"')) val = val.slice(1, -1);
    if (val.startsWith("'") && val.endsWith("'")) val = val.slice(1, -1);
    env[key] = val;
  }
});

// 3. Get configurations for character
const upperChar = character.toUpperCase();
const appId = env[`${upperChar}_APP_ID`];
const pemFilename = env[`${upperChar}_PEM_PATH`];

if (!appId || !pemFilename) {
  console.error(`Missing config for ${character} in .env (${upperChar}_APP_ID: ${appId || 'not set'}, ${upperChar}_PEM_PATH: ${pemFilename || 'not set'})`);
  process.exit(1);
}

const pemPath = path.isAbsolute(pemFilename) 
  ? pemFilename 
  : path.join(__dirname, '../.github_apps', pemFilename);

if (!fs.existsSync(pemPath)) {
  console.error(`PEM file not found at ${pemPath}`);
  process.exit(1);
}

const pemContent = fs.readFileSync(pemPath, 'utf8');

// 4. Generate JWT
function generateJWT(appId, pem) {
  const header = { alg: 'RS256', typ: 'JWT' };
  const now = Math.floor(Date.now() / 1000);
  const payload = {
    iat: now - 60, // Account for minor clock drift
    exp: now + 540, // 9 minutes max expiration
    iss: appId
  };
  
  const base64UrlEncode = (obj) => {
    return Buffer.from(JSON.stringify(obj))
      .toString('base64')
      .replace(/=/g, '')
      .replace(/\+/g, '-')
      .replace(/\//g, '_');
  };
  
  const tokenInput = `${base64UrlEncode(header)}.${base64UrlEncode(payload)}`;
  const sign = crypto.createSign('RSA-SHA256');
  sign.update(tokenInput);
  const signature = sign.sign(pem, 'base64')
    .replace(/=/g, '')
    .replace(/\+/g, '-')
    .replace(/\//g, '_');
    
  return `${tokenInput}.${signature}`;
}

const jwt = generateJWT(appId, pemContent);

// 5. Swap JWT for Installation Token
async function getInstallationToken() {
  const userAgent = 'virtual-office-bot';
  const repo = env['GITHUB_REPO'];
  if (!repo) {
    throw new Error('GITHUB_REPO not configured in .env');
  }
  const owner = repo.split('/')[0];
  
  // List installations
  const listRes = await fetch('https://api.github.com/app/installations', {
    headers: {
      'Authorization': `Bearer ${jwt}`,
      'Accept': 'application/vnd.github+json',
      'User-Agent': userAgent
    }
  });
  
  if (!listRes.ok) {
    const errText = await listRes.text();
    throw new Error(`Failed to list installations: ${listRes.status} ${errText}`);
  }
  
  const installations = await listRes.json();
  const inst = installations.find(i => i.account && i.account.login.toLowerCase() === owner.toLowerCase());
  if (!inst) {
    throw new Error(`No installation found for owner "${owner}"`);
  }
  
  const instId = inst.id;
  
  // Create access token
  const tokenRes = await fetch(`https://api.github.com/app/installations/${instId}/access_tokens`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${jwt}`,
      'Accept': 'application/vnd.github+json',
      'User-Agent': userAgent
    }
  });
  
  if (!tokenRes.ok) {
    const errText = await tokenRes.text();
    throw new Error(`Failed to get access token: ${tokenRes.status} ${errText}`);
  }
  
  const tokenData = await tokenRes.json();
  return tokenData.token;
}

getInstallationToken()
  .then(token => {
    console.log(token);
    process.exit(0);
  })
  .catch(err => {
    console.error(err.message);
    process.exit(1);
  });
