// GitHub App authentication via Web Crypto API (CF Workers compatible).
// Generates RS256 JWTs and exchanges them for installation access tokens.

/**
 * Import a PKCS#8 PEM private key for RS256 signing.
 * @param {string} b64Key - Base64-encoded PKCS#8 PEM (no headers/whitespace)
 * @returns {Promise<CryptoKey>}
 */
async function importPrivateKey(b64Key) {
  const binaryStr = atob(b64Key);
  const bytes = new Uint8Array(binaryStr.length);
  for (let i = 0; i < binaryStr.length; i++) {
    bytes[i] = binaryStr.charCodeAt(i);
  }
  return crypto.subtle.importKey(
    "pkcs8",
    bytes.buffer,
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["sign"]
  );
}

/**
 * Base64url-encode a buffer or string.
 */
function base64url(input) {
  const str =
    typeof input === "string"
      ? btoa(input)
      : btoa(String.fromCharCode(...new Uint8Array(input)));
  return str.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

/**
 * Generate a GitHub App JWT (valid for 10 minutes).
 * @param {string} appId
 * @param {string} privateKeyB64 - Base64-encoded PKCS#8 private key
 * @returns {Promise<string>} JWT
 */
export async function createAppJWT(appId, privateKeyB64) {
  const now = Math.floor(Date.now() / 1000);
  const header = { alg: "RS256", typ: "JWT" };
  const payload = {
    iat: now - 60, // clock skew tolerance
    exp: now + 600, // 10 minutes
    iss: appId,
  };

  const encodedHeader = base64url(JSON.stringify(header));
  const encodedPayload = base64url(JSON.stringify(payload));
  const signingInput = `${encodedHeader}.${encodedPayload}`;

  const key = await importPrivateKey(privateKeyB64);
  const signature = await crypto.subtle.sign(
    "RSASSA-PKCS1-v1_5",
    key,
    new TextEncoder().encode(signingInput)
  );

  return `${signingInput}.${base64url(signature)}`;
}

/**
 * Get an installation access token for the given installation ID.
 * @param {string} appId
 * @param {string} privateKeyB64
 * @param {number} installationId
 * @returns {Promise<string>} Installation access token
 */
export async function getInstallationToken(
  appId,
  privateKeyB64,
  installationId
) {
  const jwt = await createAppJWT(appId, privateKeyB64);

  const response = await fetch(
    `https://api.github.com/app/installations/${installationId}/access_tokens`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${jwt}`,
        Accept: "application/vnd.github+json",
        "User-Agent": "pr-sentinel",
        "X-GitHub-Api-Version": "2022-11-28",
      },
    }
  );

  if (!response.ok) {
    const text = await response.text();
    throw new Error(
      `Failed to get installation token: ${response.status} ${text}`
    );
  }

  const data = await response.json();
  return data.token;
}
