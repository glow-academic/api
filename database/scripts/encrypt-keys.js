#!/usr/bin/env node

import crypto from "crypto";

const ALGORITHM = "aes-256-cbc";
const IV_LENGTH = 16;
const SALT_LENGTH = 32;

// Generate a key from the secret using PBKDF2
function deriveKey(password, salt) {
  return crypto.pbkdf2Sync(password, salt, 100000, 32, "sha256");
}

function encryptProviderKey(providerKey) {
  const secretKey = process.env.SECRET_KEY;
  if (!secretKey) {
    throw new Error("SECRET_KEY environment variable is not set");
  }

  const salt = crypto.randomBytes(SALT_LENGTH);
  const iv = crypto.randomBytes(IV_LENGTH);
  const key = deriveKey(secretKey, salt);

  const cipher = crypto.createCipheriv(ALGORITHM, key, iv);

  let encrypted = cipher.update(providerKey, "utf8", "hex");
  encrypted += cipher.final("hex");

  // Combine salt + iv + encrypted data
  const combined = Buffer.concat([salt, iv, Buffer.from(encrypted, "hex")]);

  return combined.toString("base64");
}

// If a key is provided as command line argument, encrypt just that key
const keyArg = process.argv[2];
if (keyArg) {
  try {
    const encrypted = encryptProviderKey(keyArg);
    console.log(encrypted);
  } catch (error) {
    console.error("Encryption failed:", error.message);
    process.exit(1);
  }
  process.exit(0);
}

// Otherwise, get API keys from environment variables (for generate-models.sh)
const openaiKey = process.env.OPENAI_API_KEY;
const googleKey = process.env.GEMINI_API_KEY;

if (!openaiKey) {
  console.error("OPENAI_API_KEY environment variable is not set");
  process.exit(1);
}

if (!googleKey) {
  console.error("GEMINI_API_KEY environment variable is not set");
  process.exit(1);
}

try {
  const encryptedOpenAI = encryptProviderKey(openaiKey);
  const encryptedGoogle = encryptProviderKey(googleKey);

  // Output the encrypted keys in a format that can be used by the shell script
  console.log(`ENCRYPTED_OPENAI_KEY="${encryptedOpenAI}"`);
  console.log(`ENCRYPTED_GOOGLE_KEY="${encryptedGoogle}"`);
} catch (error) {
  console.error("Encryption failed:", error.message);
  process.exit(1);
}
