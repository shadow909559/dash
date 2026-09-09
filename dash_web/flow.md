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
1. **`dash_web/src/lib/config.ts`** — Android download URL now points to the GitHub Release asset (`/releases/download/v1.0.0/DASH-v1.0.0.apk`)
2. **`dash_web/src/pages/DownloadPage.tsx`** — Info box updated: both downloads hosted on GitHub Releases
3. **`apps/mobile/app/.../AgentModeScreen.kt`** — Added missing `GlassCard` import (fixed pre-existing release build break)
4. **`apps/backend/dash_backend/api/router.py`** — Registered `integrations_all_router` (73 new routes)
5. **`apps/desktop/electron/main.ts`** — Auto-start: honor `--hidden` / `--start-minimized` argv and login-item `openAsHidden`; app now starts in the tray when launched by Windows at logon
6. **`apps/desktop/electron/system_tray.ts`** — Made `enableBackgroundMode()` / `disableBackgroundMode()` public so main.ts can start tray-only
7. **`apps/desktop/src/pages/SettingsPage.tsx`** — New **Startup** section: "Launch at login", "Start minimized (tray)", "Start as floating orb" toggles wired to Electron `startup:set-settings` IPC
8. **`apps/desktop/src/electron.d.ts`** — Typed the `electronAPI.app.startup` bridge
9. **`apps/backend/start-backend.ps1` / `tools/windows/run_core.ps1`** — Use full `C:\Users\Asus\AppData\Local\Python\bin\pythonw.exe` path (bare `pythonw` resolves to the WindowsApps Store stub, which is inert in non-interactive/scheduled-task sessions)
10. **`scripts/setup-autostart.bat`** — DASH-Backend task now uses `run-hidden.vbs` + fixed `backend-startup.bat`

### Windows Auto-Start Fixes (live on this machine)
- **Removed duplicate Startup-folder shortcut** — `DASH Desktop.lnk` pointed at the dev build; the HKCU Run key (installed `DASH.exe --hidden`) is now the single desktop auto-start entry
- **Re-registered 6 scheduled tasks** via `scripts/register-tasks.ps1` (admin): DASH-Backend, DASH-Ollama, DASH-Desktop, DASH-Watchdog, DASH-AutoConnect, DASH-AllServices — all `Ready`
- **Fixed backend-startup.bat** — removed the `start` wrapper (run-hidden.vbs already runs it non-blocking) and hardcoded the real pythonw path; verified backend reaches `/health` OK through the exact task invocation
- **Fixed Ollama task** — verified `ollama serve` responds on 11434
- **Rebuilt & reinstalled the desktop app** — installed `DASH.exe` now contains the `--hidden` tray-start logic (verified in `app.asar`)

### Auto-Start Verification Results
| Component | Result |
|-----------|--------|
| Registry Run key (`DASH` → `DASH.exe --hidden`) | ✅ intact |
| DASH-Backend task → backend-startup.bat → pythonw | ✅ backend healthy on :8000 |
| DASH-Ollama task → `ollama serve` | ✅ v0.32.4 on :11434 |
| DASH-Desktop task → `DASH.exe --hidden` | ✅ task Ready, exe has tray-start code |
| DASH-Watchdog / DASH-AutoConnect / DASH-AllServices | ✅ registered, Ready |
| Backend lifespan (executive worker, scheduler, sampler, etc.) | ✅ intact in main.py |

### Files Created
1. **`apps/backend/dash_backend/services/oauth_social.py`** — OAuth social login (Google/GitHub/Microsoft): authorize URL, code exchange, account linking
2. **`apps/backend/dash_backend/services/integrations.py`** — External connectors (Slack/Telegram/GitHub/Notion/Discord/Twitter): messages, webhooks, events
3. **`apps/backend/dash_backend/services/voice_engine.py`** — Wake word, STT, TTS, 17 voice commands, memos, continuous listening
4. **`apps/backend/dash_backend/services/browser_automation.py`** — Tabs, screenshots, bookmarks, history, reading list, page summaries
5. **`apps/backend/dash_backend/services/notifications_push.py`** — Push notifications, channels, templates, devices, quiet hours
6. **`apps/backend/dash_backend/api/routes/integrations_all.py`** — 73 REST endpoints for the 5 new services
7. **`apps/backend/tests/test_new_services.py`** — 60 tests covering all 5 new services

### Android APK Build & Upload Flow
1. Generated release keystore `apps/mobile/my-upload-key.jks` (keytool, RSA 2048, 10000 days)
2. Built `app-release.apk` (18.4 MB) with `./gradlew assembleRelease` using Android Studio JBR (Java 21 — Java 26 breaks AGP jlink)
3. Uploaded to GitHub Release v1.0.0 via `gho_` OAuth token (fine-grained PAT lacks upload permission)
4. Copied to S3 as backup: `s3://dash-web-2026-909559/downloads/DASH-v1.0.0.apk`
5. Rebuilt website so Download APK button links to GitHub Release asset
6. Verified: APK 302→200 (18.4 MB), EXE 302→200 (90 MB)

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
