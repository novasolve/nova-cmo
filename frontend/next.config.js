// Load backend env from the Python project's .env
const path = require('path');
const dotenv = require('dotenv');

dotenv.config({ path: '/Users/seb/leads/cmo_agent/.env' });

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  env: {
    // Prefer API_BASE or BACKEND_URL from the Python .env; fallback to localhost:8000
    NEXT_PUBLIC_API_BASE: process.env.API_BASE || process.env.BACKEND_URL || 'http://localhost:8000',
  },
};

module.exports = nextConfig;


