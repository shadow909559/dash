import { useLocalStorage } from "@/hooks/useLocalStorage";

export function CookieBanner() {
  const [accepted, setAccepted] = useLocalStorage(
    "dash_cookie_consent",
    false
  );

  if (accepted) return null;

  return (
    <div
      className="cookie-banner"
      role="complementary"
      aria-label="Cookie notice"
    >
      <p className="cookie-banner__text">
        DASH does not use cookies, analytics, or tracking. This notice exists
        for completeness. Your browsing data is not collected.
      </p>
      <div className="cookie-banner__actions">
        <button
          className="btn btn--primary btn--sm"
          onClick={() => setAccepted(true)}
        >
          Understood
        </button>
      </div>
    </div>
  );
}
