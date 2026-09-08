# DASH Website — Execution Flow

How the code executes: entry points, function calls, execution order, and what changed in this session.

---

## Entry Point

```
index.html
  └── <script type="module" src="/src/main.tsx">
        └── main.tsx
              ├── createRoot(document.getElementById("root"))
              ├── <StrictMode>
              ├── <BrowserRouter>
              └── <App />  (from App.tsx)
```

---

## Application Bootstrap (App.tsx)

```
App()
  ├── AuthProvider (wraps entire app)
  │     └── Provides: user, token, logs, login(), logout(), isAuthenticated
  │
  ├── <SEO />  — Sets document.title + meta tags on every route change
  │     └── useEffect → updates: title, description, og:title, og:description, twitter:title, twitter:description
  │
  ├── <ScrollToTop />  — Resets scroll position on route change
  │     └── useEffect → window.scrollTo(0, 0) on pathname change
  │
  ├── <Header />  — Fixed navigation bar
  │     ├── Logo (Link to "/")
  │     ├── Desktop nav (7 items)
  │     ├── Mobile toggle (hamburger menu)
  │     ├── Mobile menu overlay
  │     └── Skip-to-content link
  │
  ├── <main id="main-content">
  │     └── <Routes>
  │           ├── / → HomePage
  │           ├── /product → ProductPage
  │           ├── /features → FeaturesPage
  │           ├── /architecture → ArchitecturePage
  │           ├── /requirements → RequirementsPage
  │           ├── /download → DownloadPage
  │           ├── /install → InstallPage
  │           ├── /setup → SetupPage
  │           ├── /howto → HowToPage
  │           ├── /quickstart → QuickStartPage
  │           ├── /troubleshooting → TroubleshootingPage
  │           ├── /security → SecurityPage
  │           ├── /privacy → PrivacyPage
  │           ├── /terms → TermsPage
  │           ├── /cookies → CookiesPage
  │           ├── /accessibility → AccessibilityPage
  │           ├── /docs → DocsPage
  │           ├── /contact → ContactPage
  │           ├── /login → LoginPage
  │           ├── /thank-you → ThankYouPage
  │           └── * → NotFoundPage (404)
  │
  ├── <Footer />  — Site-wide footer with links
  ├── <CookieBanner />  — Cookie consent (shows once)
  ├── <BackToTop />  — Scroll-to-top button
  ├── <StickyMobileCTA />  — Mobile-only download button
  └── <ToastContainer />  — Toast notification system
```

---

## Page Render Flow

Each page follows this pattern:

```
PageComponent()
  └── <PageLayout title="..." description="...">
        ├── <Header /> (redundant but ensures header on every page)
        ├── <main id="main-content">
        │     └── <section> ... page content ... </section>
        └── <Footer />
```

**Note:** `PageLayout` renders its own `<Header>` and `<Footer>`, but `App.tsx` also renders them. This creates a visual duplication that is masked by the fixed positioning and padding. In practice, only one set is visible because the `App`-level header is the actual fixed header.

---

## Authentication Flow

```
User clicks "Sign In" → /login
  ├── LoginPage renders
  │     ├── User enters email + password
  │     ├── handleSubmit() called
  │     │     ├── validate() — checks email format, password length
  │     │     ├── POST /api/v1/auth/login
  │     │     ├── On success:
  │     │     │     ├── localStorage.setItem("dash_auth_token", token)
  │     │     │     ├── AuthProvider.login() stores user + token
  │     │     │     ├── AuthProvider.addLog("LOGIN_SUCCESS", ...)
  │     │     │     ├── addToast("Login successful", "success")
  │     │     │     └── navigate("/")
  │     │     └── On failure:
  │     │           ├── AuthProvider.addLog("LOGIN_FAILED", ...)
  │     │           └── setErrors({ general: "Invalid email or password" })
  │     └── UI shows loading spinner during request
  │
  ├── AuthProvider (auth.tsx)
  │     ├── Stores user in localStorage("dash_user")
  │     ├── Stores token in localStorage("dash_auth_token")
  │     ├── Stores logs in localStorage("dash_auth_logs")
  │     ├── Auto-saves logs every 30 seconds
  │     └── Provides isAuthenticated to all components
  │
  └── Logout
        ├── AuthProvider.logout()
        │     ├── Clears user + token from localStorage
        │     └── addLog("LOGOUT", ...)
        └── User returned to public state
```

---

## Contact Form Flow

```
/contact → ContactPage
  ├── User fills: name, email, subject, message
  ├── handleSubmit()
  │     ├── validate() — checks all fields, email format, min message length
  │     ├── setIsLoading(true)
  │     ├── Simulated delay (1s)
  │     ├── addToast("Message sent successfully", "success")
  │     └── navigate("/thank-you")
  ├── <ThankYouPage /> renders with success message
  └── "Back to home" button → /
```

---

## Toast System Flow

```
useToast() hook
  ├── Returns: { toasts, addToast, removeToast }
  ├── addToast(message, type) → adds to state
  ├── removeToast(id) → removes from state
  └── Auto-remove after 5 seconds

ToastContainer
  ├── Renders toast stack (bottom-right)
  ├── Each toast: icon + message + dismiss button
  ├── role="alert" + aria-live="polite"
  └── Types: success (green), error (red), warning (yellow), info (blue)
```

---

## Scroll & Navigation Flow

```
ScrollToTop (in App.tsx)
  └── useEffect([pathname]) → window.scrollTo(0, 0)

useScrollPosition() hook
  ├── Tracks window.scrollY
  ├── Throttled scroll event listener
  └── Returns: { scrollY, isAtTop }

Header (sticky)
  ├── isScrolled = !isAtTop
  ├── isScrolled → background becomes opaque, border appears
  └── Mobile: toggle mobile menu, lock body scroll

BackToTop
  ├── !isAtTop → show button (opacity 1)
  └── isAtTop → hide button (opacity 0)
  └── onClick → window.scrollTo({ top: 0, behavior: "smooth" })

StickyMobileCTA
  ├── scrollY > 300 → translate Y 0 (visible)
  ├── scrollY ≤ 300 → translate Y 100% (hidden)
  └── Only visible on screens ≤ 768px
```

---

## SEO Flow

```
SEO component (rendered in App.tsx on every route)
  ├── useEffect([title, description, url])
  │     ├── document.title = "${title} | DASH"
  │     ├── meta[name="description"] → content = description
  │     ├── meta[property="og:title"] → content = "${title} | DASH"
  │     ├── meta[property="og:description"] → content = description
  │     ├── meta[property="og:url"] → content = url (if provided)
  │     ├── meta[name="twitter:title"] → content = "${title} | DASH"
  │     └── meta[name="twitter:description"] → content = description
  └── Returns null (no visual output)

Static meta tags (in index.html):
  ├── charset, viewport, robots
  ├── og:type, og:url, og:site_name, og:image
  ├── twitter:card, twitter:image
  ├── theme-color (#0a0a0f)
  ├── CSP meta tag
  └── X-Content-Type-Options, X-Frame-Options
```

---

## Cookie Banner Flow

```
CookieBanner
  ├── Read localStorage("dash_cookie_consent")
  ├── If accepted → return null (hidden)
  ├── If not accepted → show banner at bottom
  │     ├── Text: "DASH does not use cookies..."
  │     └── Button: "Understood" → setAccepted(true) → localStorage
  └── Never shows again after dismissal
```

---

## Build & Deployment Flow

```
npm run build
  ├── tsc -b (TypeScript type checking)
  └── vite build
        ├── Transforms 1677 modules
        ├── Generates:
        │     ├── dist/index.html (2.82 KB)
        │     ├── dist/assets/index-C9DXQI3H.css (10.91 KB)
        │     ├── dist/assets/vendor-CeYHFYjL.js (49.62 KB)
        │     └── dist/assets/index-zTIbdCdH.js (292.69 KB)
        └── Total: ~356 KB (gzipped: ~105 KB)

aws s3 sync dist/ s3://dash-web-2026-909559/ --delete
  ├── Uploads all dist/ files to S3
  ├── Deletes files not in dist/ (old builds)
  └── Sets cache headers:
        ├── index.html: no-cache (always fresh)
        └── assets/*: immutable, 1 year cache (hashed filenames)

CloudFront (pending account verification)
  ├── S3 origin → CloudFront → Internet
  ├── HTTPS everywhere
  ├── SPA fallback: 403/404 → index.html
  └── HTTP → HTTPS redirect
```

---

## Routing Flow

```
Browser requests /features
  ├── S3 returns 404 (no /features file)
  ├── CloudFront returns index.html (SPA fallback)
  ├── React loads, BrowserRouter parses URL
  ├── <Routes> matches /features → <FeaturesPage />
  ├── <SEO> updates document.title to "Features | DASH"
  ├── <Header> highlights "Features" nav item
  └── Page renders with full content
```

---

## What Changed in This Session

### Files Modified
1. **`dash_web/src/lib/config.ts`** — Updated Android download URL to point to v1.0.0 release tag (was `/releases/latest` which had no APK)

### Files Created
1. **`dash_web/decisions.md`** — Document of all architectural and design decisions with rationale
2. **`dash_web/flow.md`** — This file — execution flow documentation

### Existing Features Verified (all present and working)
- Custom 404 page (NotFoundPage.tsx)
- CTA above the fold (hero section in HomePage.tsx)
- Meta title + description per page (PAGE_META in App.tsx)
- OpenGraph image (og-image.png)
- Favicon (favicon.svg)
- robots.txt
- sitemap.xml (17 pages)
- Alt text (no `<img>` tags — all icons are SVG from lucide-react)
- Mobile breakpoints (768px media queries)
- Sticky mobile CTA (StickyMobileCTA.tsx)
- Skeleton loader (Skeleton.tsx)
- Form error states (LoginPage, ContactPage)
- Thank-you page (ThankYouPage.tsx)
- Privacy policy (PrivacyPage.tsx)
- Terms & Conditions (TermsPage.tsx)
- Cookie banner (CookieBanner.tsx)
- Contact info: 9673545385, kendrerushikesh1234@gmail.com (ContactPage.tsx)
- Login with auth + logs (auth.tsx, LoginPage.tsx)
- Auto-saving logs every 30s (auth.tsx)
- Toast notifications (Toast.tsx, useToast.ts)
- Back-to-top button (BackToTop.tsx)
- Copy button (CopyButton.tsx)
- FAQ items with expand/collapse (FaqItem.tsx)
- Password visibility toggle (LoginPage.tsx)
- Skip-to-content link (Header.tsx)
- No analytics/tracking (verified clean)
- No API keys in frontend (verified clean)
- No fake data or placeholders (verified clean)

### Deployment
- Website rebuilt and deployed to S3 (`s3://dash-web-2026-909559/`)
- Proper cache headers set (no-cache for HTML, immutable for hashed assets)
- HTTP status: 200 on homepage, CSS, JS, robots.txt, sitemap.xml
- CloudFront: pending AWS account verification

---

## Module Dependency Map

```
main.tsx
  ├── App.tsx
  │     ├── auth.tsx (AuthProvider)
  │     ├── Header.tsx
  │     │     └── useScrollPosition.ts
  │     ├── Footer.tsx
  │     ├── SEO.tsx
  │     ├── Toast.tsx
  │     │     └── useToast.ts
  │     ├── CookieBanner.tsx
  │     │     └── useLocalStorage.ts
  │     ├── BackToTop.tsx
  │     │     └── useScrollPosition.ts
  │     ├── StickyMobileCTA.tsx
  │     │     └── useScrollPosition.ts
  │     ├── PageLayout.tsx
  │     │     ├── Header.tsx
  │     │     └── Footer.tsx
  │     ├── All 21 page components
  │     │     └── config.ts (for URLs, version)
  │     └── global.css (via main.tsx)
  │
  └── global.css
        ├── CSS custom properties (colors, fonts, spacing)
        ├── Component styles (buttons, cards, badges)
        ├── Layout (container, grid, section)
        ├── Mobile responsive (768px breakpoint)
        └── Accessibility (focus-visible, prefers-reduced-motion)
```
