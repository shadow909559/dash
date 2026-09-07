import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { PageLayout } from "@/components/PageLayout";
import { Mail, Phone, MapPin, Send, AlertTriangle } from "lucide-react";
import { useToast } from "@/hooks/useToast";

interface ContactFormData {
  name: string;
  email: string;
  subject: string;
  message: string;
}

interface FormErrors {
  name?: string;
  email?: string;
  subject?: string;
  message?: string;
  general?: string;
}

export function ContactPage() {
  const navigate = useNavigate();
  const { addToast } = useToast();
  const [formData, setFormData] = useState<ContactFormData>({
    name: "",
    email: "",
    subject: "",
    message: "",
  });
  const [errors, setErrors] = useState<FormErrors>({});
  const [isLoading, setIsLoading] = useState(false);

  const validate = (): boolean => {
    const e: FormErrors = {};
    if (!formData.name.trim()) e.name = "Name is required";
    if (!formData.email) e.email = "Email is required";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email))
      e.email = "Enter a valid email";
    if (!formData.subject.trim()) e.subject = "Subject is required";
    if (!formData.message.trim()) e.message = "Message is required";
    else if (formData.message.trim().length < 10)
      e.message = "Message must be at least 10 characters";
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    setIsLoading(true);
    setErrors({});
    // Simulate form submission
    await new Promise((r) => setTimeout(r, 1000));
    addToast("Message sent successfully", "success");
    navigate("/thank-you");
  };

  const inputStyle = (hasError: boolean): React.CSSProperties => ({
    width: "100%",
    padding: "10px 12px",
    background: "var(--bg-tertiary)",
    border: `1px solid ${hasError ? "var(--danger)" : "var(--border)"}`,
    borderRadius: "var(--radius-md)",
    color: "var(--text-primary)",
    fontSize: 14,
    fontFamily: "var(--font-sans)",
  });

  return (
    <PageLayout title="Contact" description="Get in touch with the DASH team.">
      <section className="section--sm">
        <div className="container" style={{ maxWidth: 800 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1.5fr", gap: 40 }}>
            {/* Contact Info */}
            <div>
              <h3 style={{ marginBottom: 16 }}>Get in touch</h3>
              <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
                <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
                  <Mail size={16} style={{ color: "var(--accent)", marginTop: 2 }} />
                  <div>
                    <p style={{ fontSize: 13, fontWeight: 500, marginBottom: 2 }}>Email</p>
                    <a href="mailto:kendrerushikesh1234@gmail.com" style={{ fontSize: 13 }}>
                      kendrerushikesh1234@gmail.com
                    </a>
                  </div>
                </div>
                <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
                  <Phone size={16} style={{ color: "var(--accent)", marginTop: 2 }} />
                  <div>
                    <p style={{ fontSize: 13, fontWeight: 500, marginBottom: 2 }}>Phone</p>
                    <a href="tel:+919673545385" style={{ fontSize: 13 }}>
                      +91 9673545385
                    </a>
                  </div>
                </div>
                <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
                  <MapPin size={16} style={{ color: "var(--accent)", marginTop: 2 }} />
                  <div>
                    <p style={{ fontSize: 13, fontWeight: 500, marginBottom: 2 }}>Location</p>
                    <p style={{ fontSize: 13, color: "var(--text-secondary)" }}>India</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Contact Form */}
            <div className="card" style={{ padding: 28 }}>
              <form onSubmit={handleSubmit}>
                {errors.general && (
                  <div style={{
                    padding: "10px 14px", background: "rgba(239,68,68,0.1)",
                    border: "1px solid rgba(239,68,68,0.3)", borderRadius: "var(--radius-md)",
                    fontSize: 13, color: "var(--danger)", marginBottom: 16,
                    display: "flex", alignItems: "center", gap: 8,
                  }}>
                    <AlertTriangle size={14} /> {errors.general}
                  </div>
                )}

                <div style={{ marginBottom: 14 }}>
                  <label htmlFor="contact-name" style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 4, color: "var(--text-secondary)" }}>Name</label>
                  <input id="contact-name" type="text" value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} style={inputStyle(!!errors.name)} placeholder="Your name" />
                  {errors.name && <p style={{ fontSize: 12, color: "var(--danger)", marginTop: 4 }}>{errors.name}</p>}
                </div>

                <div style={{ marginBottom: 14 }}>
                  <label htmlFor="contact-email" style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 4, color: "var(--text-secondary)" }}>Email</label>
                  <input id="contact-email" type="email" value={formData.email} onChange={(e) => setFormData({ ...formData, email: e.target.value })} style={inputStyle(!!errors.email)} placeholder="you@example.com" />
                  {errors.email && <p style={{ fontSize: 12, color: "var(--danger)", marginTop: 4 }}>{errors.email}</p>}
                </div>

                <div style={{ marginBottom: 14 }}>
                  <label htmlFor="contact-subject" style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 4, color: "var(--text-secondary)" }}>Subject</label>
                  <input id="contact-subject" type="text" value={formData.subject} onChange={(e) => setFormData({ ...formData, subject: e.target.value })} style={inputStyle(!!errors.subject)} placeholder="How can we help?" />
                  {errors.subject && <p style={{ fontSize: 12, color: "var(--danger)", marginTop: 4 }}>{errors.subject}</p>}
                </div>

                <div style={{ marginBottom: 20 }}>
                  <label htmlFor="contact-message" style={{ display: "block", fontSize: 13, fontWeight: 500, marginBottom: 4, color: "var(--text-secondary)" }}>Message</label>
                  <textarea id="contact-message" rows={5} value={formData.message} onChange={(e) => setFormData({ ...formData, message: e.target.value })} style={{ ...inputStyle(!!errors.message), resize: "vertical" }} placeholder="Tell us more..." />
                  {errors.message && <p style={{ fontSize: 12, color: "var(--danger)", marginTop: 4 }}>{errors.message}</p>}
                </div>

                <button type="submit" className="btn btn--primary" disabled={isLoading} style={{ width: "100%", justifyContent: "center" }}>
                  {isLoading ? "Sending..." : <><Send size={14} /> Send message</>}
                </button>
              </form>
            </div>
          </div>
        </div>
      </section>
    </PageLayout>
  );
}
