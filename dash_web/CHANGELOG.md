# DASH Website — Changelog

## 1.1.0 — Security Audit & Features (2026-09-08)

### New Pages
- **Custom 404 page** — Shows "404" with home/back buttons instead of generic error
- **Contact page** — Form with validation, real contact info (phone: +91 9673545385, email: kendrerushikesh1234@gmail.com)
- **Login page** — Email/password form with validation, password visibility toggle, error states, loading spinner
- **Thank-you page** — Shown after form submission

### SEO & Meta
- **Per-page meta titles** — Each route has unique `<title>` tag (e.g., "Features | DASH")
- **Per-page meta descriptions** — Each route has unique description for search engines
- **robots.txt** — Allows crawling, disallows /api/ and /admin/
- **sitemap.xml** — All 17 pages listed with priorities
- **OpenGraph tags** — og:title, og:description, og:url, og:image per page
- **Twitter Card tags** — twitter:title, twitter:description, twitter:image

### UI Components
- **Sticky mobile CTA** — Download button appears at bottom on mobile after scrolling 300px
- **SEO component** — Dynamically updates meta tags on route change
- **Auth context** — Login/logout with localStorage persistence, session logging

### Why
- 404 page prevents user confusion on broken links
- Contact page provides real support channel
- Login page enables future app authentication
- Meta tags improve SEO ranking and social sharing
- Mobile CTA increases download conversions

---

## 1.0.0 — Initial Release (2026-09-07)

### Pages (17)
Home, Product, Features, Architecture, Requirements, Download, Install, Setup, QuickStart, HowTo, Troubleshooting, Security, Privacy, Terms, Cookies, Accessibility, Docs

### Components
Header (sticky, mobile menu), Footer, CookieBanner, BackToTop, Toast, CopyButton, CodeBlock, FaqItem, Skeleton, PageLayout

### Hooks
useToast, useScrollPosition, useLocalStorage

### Build
React 19 + TypeScript + Vite, 335KB total, zero TypeScript errors

### Deployment
S3 bucket: dash-web-2026-909559, region: ap-south-1
Website: http://dash-web-2026-909559.s3-website.ap-south-1.amazonaws.com

### Why
- React + TypeScript + Vite chosen for fast builds and type safety
- Dark theme with green accent matches DASH desktop app design
- No fake claims, no placeholder data, no hardcoded secrets
- All content based on actual DASH implementation
