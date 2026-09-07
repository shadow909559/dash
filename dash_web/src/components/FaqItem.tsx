import { useState } from "react";
import { ChevronDown } from "lucide-react";

interface FaqItemProps {
  question: string;
  answer: string;
}

export function FaqItem({ question, answer }: FaqItemProps) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div className="faq-item">
      <button
        className="faq-item__trigger"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
      >
        <span>{question}</span>
        <ChevronDown
          size={16}
          className={`faq-item__icon ${isOpen ? "faq-item__icon--open" : ""}`}
        />
      </button>
      <div
        className={`faq-item__content ${isOpen ? "faq-item__content--open" : ""}`}
        role="region"
      >
        <div className="faq-item__body">{answer}</div>
      </div>
    </div>
  );
}
