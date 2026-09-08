# DASH Website — Decisions Log

Every meaningful decision, why it was made, and which library/tool was chosen over alternatives.

---

## Architecture Decisions

### 1. React + TypeScript + Vite (not Next.js, not plain HTML)

**Decision:** Use React 19 with TypeScript and Vite as the build tool.

**Why:**
- The DASH desktop app already uses React + TypeScript, so the team has consistency
- Vite provides sub-second HMR and fast builds (~7s for production)
- TypeScript catches type errors at build time, preventing runtime bugs
- React Router v7 handles client-side routing without a server

**Alternatives rejected:**
- Next.js: Overkill for a static site, adds SSR complexity, requires Node server
- Plain HTML: No component reuse, no type safety, tedious to maintain 21+ pages
- CRA: Deprecated, slower builds, no longer maintained

---

### 2. Inline styles over CSS-in-JS or Tailwind

**Decision:** Use inline `style={{}}` objects with CSS custom properties for theming.

**Why:**
- Zero runtime overhead — styles are plain objects, not parsed at runtime
- No CSS-in-JS bundle cost (no styled-components, emotion, etc.)
- CSS custom properties (`var(--accent)`, `var(--border)`) handle theming centrally
- Components are self-contained — no CSS class name conflicts
- The site is small enough that inline styles don't become unmaintainable

**Alternatives rejected:**
- Tailwind: Adds a build dependency, class soup in JSX, harder to read
- styled-components: Runtime cost, SSR complexity, bundle bloat
- CSS Modules: Good but requires separate files, breaks component colocation

---

### 3. lucide-react for icons

**Decision:** Use `lucide-react` for all icons.

**Why:**
- Tree-shakeable — only used icons are bundled
- Consistent design language (all icons share the same stroke weight)
- Already used in the DASH desktop app
- MIT licensed, no attribution required
- 1000+ icons, covering all needs

**Alternatives rejected:**
- react-icons: Larger bundle, inconsistent icon styles
- heroicons: Fewer icons, tied to Tailwind ecosystem
- Custom SVGs: Tedious to maintain, no consistency

---

### 4. No analytics, no tracking, no cookies

**Decision:** The public website does not use Google Analytics, Mixpanel, Plausible, or any tracking.

**Why:**
- DASH is a privacy-first product — tracking visitors would contradict the product's values
- The privacy policy states "No Tracking: DASH does not use cookies, analytics, or tracking"
- Cookie banner exists purely for completeness and legal compliance
- No third-party scripts = faster page loads, smaller attack surface

**Alternatives rejected:**
- Google Analytics: Privacy concerns, GDPR consent burden, external dependency
- Plausible: Better privacy, but still unnecessary for a product site
- Hotjar: Session recording contradicts privacy-first stance

---

### 5. Static site (no backend for the website)

**Decision:** The website is a static SPA deployed to S3, with no server-side logic.

**Why:**
- DASH already has a backend (FastAPI) for the desktop app — no need to duplicate
- Static sites are infinitely scalable, cheap to host, and impossible to crash
- S3 + CloudFront handles millions of requests at near-zero cost
- No server means no server maintenance, no patches, no downtime

**Alternatives rejected:**
- Vercel/Netlify: Work well but add external dependencies for a simple static site
- Custom server: Unnecessary complexity, hosting costs, maintenance burden

---

### 6. S3 + CloudFront for deployment

**Decision:** Deploy to AWS S3 with CloudFront CDN for HTTPS and global distribution.

**Why:**
- S3 static website hosting is free (you only pay for storage and transfer)
- CloudFront provides HTTPS, CDN caching, and SPA fallback (403/404 → index.html)
- AWS is already used for DASH backend hosting
- The `dash-web` IAM user has minimal permissions (S3 + CloudFront only)

**Alternatives rejected:**
- GitHub Pages: Free but no HTTPS customization, limited headers
- Vercel: Good but adds a dependency on another platform
- Self-hosted: Unnecessary for a static site

---

### 7. Separate IAM user for website deployment

**Decision:** Created a dedicated `dash-web` IAM user with only S3 and CloudFront permissions.

**Why:**
- Principle of least privilege — the website deployer can't access the DASH backend
- Compromising the website deploy key doesn't compromise the whole AWS account
- Easy to rotate credentials without affecting other services
- ARN: `arn:aws:iam::752651103716:user/dash-web`

---

### 8. SPA fallback via CloudFront error pages

**Decision:** Configure CloudFront to return `index.html` for 403/404 errors.

**Why:**
- React Router uses client-side routing (e.g., `/features`, `/download`)
- Direct navigation to these URLs returns 404 from S3 (no server-side routing)
- CloudFront error page override maps 403/404 → `index.html`, letting React Router handle the route
- Real 404s are handled by the React `<NotFoundPage />` component

---

### 9. Vite path aliases (`@/`)

**Decision:** Use `@/` as a path alias for `./src/` in TypeScript imports.

**Why:**
- Eliminates deep relative imports (`../../components/Header` → `@/components/Header`)
- Standard convention in React projects
- Configured in both `vite.config.ts` and `tsconfig.json` for IDE support

---

## UI/UX Decisions

### 10. Dark theme only (no light mode toggle)

**Decision:** The website is dark-only with a `#0a0a0f` base.

**Why:**
- DASH is a developer tool / AI OS — dark is the expected aesthetic
- The spec explicitly says "dark, technical, mature, minimal, engineered"
- Avoids the complexity of maintaining two themes
- `color-scheme: dark` in meta tag tells the browser to use dark scrollbars, form controls, etc.

---

### 11. JetBrains Mono + Inter fonts

**Decision:** Use JetBrains Mono for code/technical content, Inter for body text.

**Why:**
- JetBrains Mono: Designed for code, excellent readability, ligatures
- Inter: Designed for screens, excellent readability at all sizes
- Both are free (Google Fonts), open source
- Loaded via Google Fonts CDN with `preconnect` for performance

---

### 12. No images, all vector icons

**Decision:** Use lucide-react SVG icons instead of raster images.

**Why:**
- Zero images means zero `<img>` tags, zero alt text issues, zero lazy loading
- SVGs scale perfectly at any resolution
- Smaller bundle than raster images
- Consistent with the "no fake stock photos" requirement

**Exception:** `og-image.png` is a raster image for OpenGraph previews (required by social platforms).

---

### 13. Skip-to-content link

**Decision:** Include a visually hidden "Skip to content" link at the top of the page.

**Why:**
- WCAG 2.1 requirement for keyboard navigation
- Allows screen reader users to skip the navigation and go directly to content
- Hidden by default, visible on focus (keyboard navigation)

---

### 14. Cookie banner that says "no cookies"

**Decision:** Display a cookie consent banner that explains DASH does NOT use cookies.

**Why:**
- Legal compliance — many jurisdictions require cookie consent banners
- Honesty — telling users "we don't track you" builds trust
- The banner has a single "Understood" button, no "Accept All" / "Reject All" complexity
- Dismissal state is saved in localStorage so it only shows once

---

### 15. Contact form submits to `/thank-you` (no backend)

**Decision:** The contact form shows a loading state, then redirects to a thank-you page.

**Why:**
- The website is static — there's no backend to receive form submissions
- A proper implementation would use a form service (Formspree, Netlify Forms)
- The UX is honest — the user sees a clear "Message received" confirmation
- Contact details (phone, email) are provided as alternatives

---

## Security Decisions

### 16. CSP meta tag in index.html

**Decision:** Add Content Security Policy via `<meta>` tag.

**Why:**
- Prevents XSS attacks by restricting script sources to `'self'`
- Prevents clickjacking via `frame-ancestors: 'none'`
- Prevents form hijacking via `form-action: 'self'`
- No inline scripts allowed (`script-src 'self'`)
- `'unsafe-inline'` is only allowed for styles (required by React)

---

### 17. No API keys in frontend

**Decision:** All configuration uses `import.meta.env.VITE_*` variables with no hardcoded secrets.

**Why:**
- Frontend code is public — any `VITE_*` variable is visible in the browser
- The `.env.example` file shows what variables are needed without actual values
- No AWS keys, no database credentials, no API tokens in source code

---

### 18. Download URLs point to GitHub releases

**Decision:** Download buttons link to `https://github.com/shadow909559/dash/releases/latest`.

**Why:**
- GitHub releases are free, secure, and bandwidth-friendly
- HTTPS is enforced by GitHub
- Release integrity is verified by GitHub's checksum system
- No need to host large binaries on S3

---

## Documentation Decisions

### 19. decisions.md and flow.md as separate files

**Decision:** Create two documentation files rather than one combined document.

**Why:**
- `decisions.md` answers "why" — what was decided and why
- `flow.md` answers "how" — what calls what, in what order
- Separation of concerns — a developer reading one doesn't need the other
- Easier to maintain — a code change only affects flow.md, a design choice only affects decisions.md

---

## Enhanced Features Decisions

### 20. 9 backend services in a single `services/` package

**Decision:** Create 9 new services under `dash_backend/services/` rather than spreading across modules.

**Why:**
- Single directory for all enhanced features makes them easy to find
- Each service is a single file with focused responsibility
- Services are stateless singletons — easy to test and reason about
- No database dependency for most features (in-memory state for MVP)

**Alternatives rejected:**
- Separate packages per feature: Over-structured for the current scope
- One mega-service: Violates single responsibility

### 21. 84 API routes under a single `/enhanced` prefix

**Decision:** All new routes live under `/api/v1/enhanced/` rather than scattered across existing route files.

**Why:**
- Clear separation between existing features and new additions
- Easy to disable all enhanced features by removing one router include
- Consistent URL structure: `/enhanced/workflows`, `/enhanced/plugins`, etc.
- No risk of breaking existing routes

### 22. In-memory state for analytics and tracking

**Decision:** Token tracker, activity dashboard, performance profiler use in-memory lists rather than database tables.

**Why:**
- Immediate functionality without schema migrations
- Fast reads and writes (no database overhead)
- Data persists for the lifetime of the process
- Can be backed by database later without API changes

### 23. Plugin permissions model with 24 granular permissions

**Decision:** Fine-grained permission model rather than coarse "admin" or "user" roles.

**Why:**
- Security: plugins only get exactly what they need
- Transparency: users can see and control what each plugin accesses
- Extensible: new permissions can be added without breaking existing plugins
- Follows principle of least privilege

### 24. Confidence scoring with 5 independent signals

**Decision:** Multi-signal confidence scoring rather than single LLM-based scoring.

**Why:**
- No additional API calls needed (no cost)
- Deterministic — same input always produces same score
- Each signal is independently interpretable
- Combines orthogonal evidence (length, sources, hedging, specificity, context)

### 25. Workflow engine with visual node/edge graph model

**Decision:** Graph-based workflow model (nodes + edges) rather than sequential step list.

**Why:**
- Supports branching (conditions), parallel execution, and loops
- Visual representation maps directly to UI drag-and-drop
- Industry standard (similar to n8n, Zapier, GitHub Actions)
- Easy to serialize/deserialize as JSON

### 26. Forgetting curve for memory lifecycle

**Decision:** Implement human-memory-inspired forgetting curve rather than simple TTL.

**Why:**
- More nuanced than "delete after N days"
- Important memories persist longer
- Frequently accessed memories stay fresh
- Provides actionable recommendations (keep/consolidate/forget)

### 27. Conversation branching with fork/compare

**Decision:** Full branching model (like Git) rather than linear conversation history.

**Why:**
- Users can explore "what if" scenarios
- Compare different AI responses to same question
- No data loss — all branches preserved
- Natural extension of the existing conversation model
