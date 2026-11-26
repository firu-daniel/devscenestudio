// The renderer's Content-Security-Policy. No imports: build tooling reads this file too.
// Today the production build puts it in a <meta> tag (vite.config.ts); Day 1 step 7 also
// serves it as a header from `vite preview`, and Day 2 serves it from app:// and drops the meta.
export const CSP = [
  "default-src 'none'",
  "script-src 'self'",
  "style-src 'self'",
  "img-src 'self'",
  "connect-src 'none'",
  "base-uri 'none'",
  "form-action 'none'",
  "frame-ancestors 'none'",
].join("; ");
