import { useEffect, useCallback } from "react";
import { Routes, Route, useLocation } from "react-router-dom";
import { AuthProvider } from "@/lib/auth";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { ToastContainer } from "@/components/Toast";
import { useToast } from "@/hooks/useToast";
import { CookieBanner } from "@/components/CookieBanner";
import { BackToTop } from "@/components/BackToTop";
import { StickyMobileCTA } from "@/components/StickyMobileCTA";
import { SEO } from "@/components/SEO";
import { HomePage } from "@/pages/HomePage";
import { ProductPage } from "@/pages/ProductPage";
import { FeaturesPage } from "@/pages/FeaturesPage";
import { ArchitecturePage } from "@/pages/ArchitecturePage";
import { RequirementsPage } from "@/pages/RequirementsPage";
import { DownloadPage } from "@/pages/DownloadPage";
import { InstallPage } from "@/pages/InstallPage";
import { SetupPage } from "@/pages/SetupPage";
import { HowToPage } from "@/pages/HowToPage";
import { QuickStartPage } from "@/pages/QuickStartPage";
import { TroubleshootingPage } from "@/pages/TroubleshootingPage";
import { SecurityPage } from "@/pages/SecurityPage";
import { PrivacyPage } from "@/pages/PrivacyPage";
import { TermsPage } from "@/pages/TermsPage";
import { CookiesPage } from "@/pages/CookiesPage";
import { AccessibilityPage } from "@/pages/AccessibilityPage";
import { DocsPage } from "@/pages/DocsPage";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { ThankYouPage } from "@/pages/ThankYouPage";
import { ContactPage } from "@/pages/ContactPage";
import { LoginPage } from "@/pages/LoginPage";

const PAGE_META: Record<string, { title: string; desc: string }> = {
  "/": { title: "Home", desc: "DASH - Your AI, working from your desktop. A personal AI operating system." },
  "/product": { title: "Product", desc: "DASH is a personal AI operating system, not a chatbot." },
  "/features": { title: "Features", desc: "Chat, memory, coding, research, automation, agents, and more." },
  "/architecture": { title: "Architecture", desc: "How DASH is built. Desktop app, backend, AI layer, memory engine." },
  "/requirements": { title: "System Requirements", desc: "Minimum and recommended hardware for DASH." },
  "/download": { title: "Download DASH", desc: "Get DASH for Windows. Open source, free to use." },
  "/install": { title: "Install DASH", desc: "Step-by-step installation guide." },
  "/setup": { title: "First-Time Setup", desc: "Configure AI providers, permissions, and integrations." },
  "/quickstart": { title: "Quick Start", desc: "From download to productive in under 5 minutes." },
  "/howto": { title: "How to Use DASH", desc: "Practical guides for every feature." },
  "/troubleshooting": { title: "Troubleshooting", desc: "Common issues and solutions." },
  "/security": { title: "Security", desc: "How DASH protects your data and system." },
  "/docs": { title: "Documentation", desc: "Everything you need to install, configure, and use DASH." },
  "/privacy": { title: "Privacy Policy", desc: "How DASH handles your data. Local-first, no tracking." },
  "/terms": { title: "Terms & Conditions", desc: "Terms of use for DASH." },
  "/cookies": { title: "Cookie Policy", desc: "DASH does not use cookies." },
  "/accessibility": { title: "Accessibility", desc: "Our commitment to accessibility." },
  "/contact": { title: "Contact", desc: "Get in touch with the DASH team." },
  "/login": { title: "Sign In", desc: "Sign in to your DASH account." },
  "/thank-you": { title: "Thank You", desc: "Your message has been received." },
};

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => { window.scrollTo(0, 0); }, [pathname]);
  return null;
}

function App() {
  const { toasts, addToast, removeToast } = useToast();
  const { pathname } = useLocation();
  const meta = PAGE_META[pathname] || { title: "Page", desc: "DASH - Your AI, working from your desktop." };

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        addToast("Search coming soon", "info");
      }
    },
    [addToast]
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  return (
    <AuthProvider>
      <SEO title={meta.title} description={meta.desc} />
      <ScrollToTop />
      <Header />
      <main id="main-content" style={{ paddingTop: "var(--header-height)" }}>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/product" element={<ProductPage />} />
          <Route path="/features" element={<FeaturesPage />} />
          <Route path="/architecture" element={<ArchitecturePage />} />
          <Route path="/requirements" element={<RequirementsPage />} />
          <Route path="/download" element={<DownloadPage />} />
          <Route path="/install" element={<InstallPage />} />
          <Route path="/setup" element={<SetupPage />} />
          <Route path="/howto" element={<HowToPage />} />
          <Route path="/quickstart" element={<QuickStartPage />} />
          <Route path="/troubleshooting" element={<TroubleshootingPage />} />
          <Route path="/security" element={<SecurityPage />} />
          <Route path="/privacy" element={<PrivacyPage />} />
          <Route path="/terms" element={<TermsPage />} />
          <Route path="/cookies" element={<CookiesPage />} />
          <Route path="/accessibility" element={<AccessibilityPage />} />
          <Route path="/docs" element={<DocsPage />} />
          <Route path="/contact" element={<ContactPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/thank-you" element={<ThankYouPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </main>
      <Footer />
      <CookieBanner />
      <BackToTop />
      <StickyMobileCTA />
      <ToastContainer toasts={toasts} onRemove={removeToast} />
    </AuthProvider>
  );
}

export default App;
