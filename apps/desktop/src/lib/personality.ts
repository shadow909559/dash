// Voice Personality System - Tone, speed, pitch, and response style controls.

export type PersonalityType = 
  | 'friendly'
  | 'professional'
  | 'serious'
  | 'funny'
  | 'assistant'
  | 'companion'
  | 'developer'
  | 'researcher';

export interface VoicePersonality {
  type: PersonalityType;
  name: string;
  tone: 'warm' | 'neutral' | 'cool' | 'energetic' | 'calm';
  speed: number; // 0.5 to 2.0
  pitch: number; // 0.5 to 2.0
  pauseDuration: number; // ms between phrases
  responseStyle: 'concise' | 'detailed' | 'conversational' | 'technical';
  emotion: 'happy' | 'neutral' | 'focused' | 'curious' | 'serious';
  useEmojis: boolean;
  usePunctuation: boolean;
  greeting: string;
  farewell: string;
}

export const personalities: Record<PersonalityType, VoicePersonality> = {
  friendly: {
    type: 'friendly',
    name: 'Friendly',
    tone: 'warm',
    speed: 1.1,
    pitch: 1.1,
    pauseDuration: 300,
    responseStyle: 'conversational',
    emotion: 'happy',
    useEmojis: true,
    usePunctuation: true,
    greeting: "Hey there! How can I help you today?",
    farewell: "Take care! Let me know if you need anything else!",
  },
  professional: {
    type: 'professional',
    name: 'Professional',
    tone: 'neutral',
    speed: 1.0,
    pitch: 1.0,
    pauseDuration: 400,
    responseStyle: 'detailed',
    emotion: 'focused',
    useEmojis: false,
    usePunctuation: true,
    greeting: "Hello. I'm ready to assist you.",
    farewell: "Thank you for using DASH. Goodbye.",
  },
  serious: {
    type: 'serious',
    name: 'Serious',
    tone: 'cool',
    speed: 0.9,
    pitch: 0.9,
    pauseDuration: 500,
    responseStyle: 'concise',
    emotion: 'serious',
    useEmojis: false,
    usePunctuation: true,
    greeting: "I'm listening.",
    farewell: "Task complete.",
  },
  funny: {
    type: 'funny',
    name: 'Funny',
    tone: 'energetic',
    speed: 1.2,
    pitch: 1.15,
    pauseDuration: 250,
    responseStyle: 'conversational',
    emotion: 'happy',
    useEmojis: true,
    usePunctuation: true,
    greeting: "Yo! What's up? Ready to do some cool stuff?",
    farewell: "Later! Don't be a stranger!",
  },
  assistant: {
    type: 'assistant',
    name: 'Assistant',
    tone: 'warm',
    speed: 1.0,
    pitch: 1.0,
    pauseDuration: 350,
    responseStyle: 'detailed',
    emotion: 'focused',
    useEmojis: false,
    usePunctuation: true,
    greeting: "Hello! I'm your AI assistant. How may I help you?",
    farewell: "I hope that was helpful. Have a great day!",
  },
  companion: {
    type: 'companion',
    name: 'Companion',
    tone: 'warm',
    speed: 1.05,
    pitch: 1.05,
    pauseDuration: 300,
    responseStyle: 'conversational',
    emotion: 'happy',
    useEmojis: true,
    usePunctuation: true,
    greeting: "Hi! I'm so glad you're here. What would you like to do?",
    farewell: "I'll be here whenever you need me. Take care!",
  },
  developer: {
    type: 'developer',
    name: 'Developer',
    tone: 'neutral',
    speed: 1.1,
    pitch: 1.0,
    pauseDuration: 300,
    responseStyle: 'technical',
    emotion: 'focused',
    useEmojis: false,
    usePunctuation: true,
    greeting: "Ready to code. What are we working on?",
    farewell: "Code committed. Happy hacking!",
  },
  researcher: {
    type: 'researcher',
    name: 'Researcher',
    tone: 'neutral',
    speed: 0.95,
    pitch: 1.0,
    pauseDuration: 450,
    responseStyle: 'detailed',
    emotion: 'curious',
    useEmojis: false,
    usePunctuation: true,
    greeting: "Hello. I'm ready to help you research and explore.",
    farewell: "Interesting findings. Let me know if you need more analysis.",
  },
};

class PersonalityManager {
  private currentPersonality: VoicePersonality = personalities.assistant;
  private listeners: Set<(personality: VoicePersonality) => void> = new Set();

  setPersonality(type: PersonalityType): void {
    this.currentPersonality = personalities[type];
    this.notifyListeners();
  }

  getPersonality(): VoicePersonality {
    return this.currentPersonality;
  }

  adaptResponse(text: string): string {
    const p = this.currentPersonality;
    
    let adapted = text;
    
    // Add personality-specific elements
    if (p.useEmojis && p.emotion === 'happy') {
      adapted = adapted + " 😊";
    }
    
    // Adjust punctuation based on style
    if (!p.usePunctuation) {
      adapted = adapted.replace(/[.,!?;:]/g, '');
    }
    
    return adapted;
  }

  getVoiceSettings(): { speed: number; pitch: number } {
    return {
      speed: this.currentPersonality.speed,
      pitch: this.currentPersonality.pitch,
    };
  }

  getGreeting(): string {
    return this.currentPersonality.greeting;
  }

  getFarewell(): string {
    return this.currentPersonality.farewell;
  }

  onChange(callback: (personality: VoicePersonality) => void): () => void {
    this.listeners.add(callback);
    return () => this.listeners.delete(callback);
  }

  private notifyListeners(): void {
    this.listeners.forEach(listener => listener(this.currentPersonality));
  }
}

export const personalityManager = new PersonalityManager();
