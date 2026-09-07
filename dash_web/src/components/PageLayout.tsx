import { Header } from "./Header";
import { Footer } from "./Footer";

interface PageLayoutProps {
  children: React.ReactNode;
  title?: string;
  description?: string;
}

export function PageLayout({ children, title, description }: PageLayoutProps) {
  return (
    <>
      <Header />
      <main id="main-content" style={{ paddingTop: "var(--header-height)" }}>
        {title && (
          <div className="container" style={{ paddingTop: 48, paddingBottom: 16 }}>
            <h1>{title}</h1>
            {description && (
              <p style={{ marginTop: 12, fontSize: 16 }}>{description}</p>
            )}
          </div>
        )}
        {children}
      </main>
      <Footer />
    </>
  );
}
