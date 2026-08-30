/**
 * VoicePersonality - Defines DASH's voice personality and response style
 * 
 * Features:
 * - Professional, confident, calm, friendly
 * - Not overly emotional
 * - Not childish
 * - Not robotic
 * - No unnecessary apologies
 * - No unnecessary introductions
 * - Natural conversation flow
 */

export interface PersonalityConfig {
  style: 'professional' | 'casual' | 'formal';
  confidence: number;
  friendliness: number;
  verbosity: 'concise' | 'normal' | 'detailed';
  useEmojis: boolean;
  useGreetings: boolean;
  useApologies: boolean;
}

export class VoicePersonality {
  private config: PersonalityConfig;

  constructor(config: Partial<PersonalityConfig> = {}) {
    this.config = {
      style: 'professional',
      confidence: 0.8,
      friendliness: 0.7,
      verbosity: 'normal',
      useEmojis: false,
      useGreetings: true,
      useApologies: false,
      ...config,
    };
  }

  /**
   * Apply personality to response
   */
  applyPersonality(response: string, context?: any): string {
    let processed = response;

    // Remove unnecessary apologies
    if (!this.config.useApologies) {
      processed = this.removeApologies(processed);
    }

    // Adjust verbosity
    processed = this.adjustVerbosity(processed);

    // Add appropriate greeting if needed
    if (this.config.useGreetings && context?.isFirstInteraction) {
      processed = this.addGreeting(processed);
    }

    // Adjust confidence level
    processed = this.adjustConfidence(processed);

    return processed;
  }

  /**
   * Generate natural response based on intent
   */
  generateResponse(intent: string, data: any): string {
    switch (intent) {
      case 'open_application':
        return `Opening ${data.application}.`;

      case 'close_application':
        return `Closing ${data.application}.`;

      case 'search':
        return `Searching for ${data.query}.`;

      case 'create':
        return `Creating ${data.item}.`;

      case 'delete':
        return `Deleting ${data.item}.`;

      case 'information_query':
        return this.generateInformationResponse(data);

      case 'greeting':
        return this.generateGreeting();

      case 'farewell':
        return 'Goodbye.';

      default:
        return this.generateDefaultResponse(data);
    }
  }

  private removeApologies(text: string): string {
    const apologyPatterns = [
      /sorry about that/gi,
      /i apologize for/gi,
      /my apologies for/gi,
      /excuse me for/gi,
      /i'm sorry/gi,
    ];

    let processed = text;
    apologyPatterns.forEach(pattern => {
      processed = processed.replace(pattern, '');
    });

    return processed.trim();
  }

  private adjustVerbosity(text: string): string {
    switch (this.config.verbosity) {
      case 'concise':
        return this.makeConcise(text);
      case 'detailed':
        return this.makeDetailed(text);
      default:
        return text;
    }
  }

  private makeConcise(text: string): string {
    // Remove filler words and unnecessary phrases
    const fillerPatterns = [
      /i would be happy to/gi,
      /i can certainly/gi,
      /allow me to/gi,
      /please note that/gi,
      /it is important to mention that/gi,
    ];

    let processed = text;
    fillerPatterns.forEach(pattern => {
      processed = processed.replace(pattern, '');
    });

    return processed.trim();
  }

  private makeDetailed(text: string): string {
    // Add helpful context
    if (text.length < 50) {
      return `${text} Let me know if you need anything else.`;
    }
    return text;
  }

  private addGreeting(text: string): string {
    const greetings = [
      'Hello. ',
      'Hi. ',
      'Hey. ',
    ];
    const greeting = greetings[Math.floor(Math.random() * greetings.length)];
    return greeting + text;
  }

  private adjustConfidence(text: string): string {
    if (this.config.confidence < 0.5) {
      // Add hedging for low confidence
      const hedges = [
        'I think ',
        'It seems that ',
        'Probably ',
      ];
      const hedge = hedges[Math.floor(Math.random() * hedges.length)];
      return hedge + text.charAt(0).toLowerCase() + text.slice(1);
    } else if (this.config.confidence > 0.8) {
      // Remove hedging for high confidence
      return text.replace(/i think |it seems that |probably /gi, '');
    }
    return text;
  }

  private generateInformationResponse(data: any): string {
    // Natural, direct responses to information queries
    const responses = [
      `${data.answer}`,
      `Based on what I know, ${data.answer}`,
      `${data.answer}. Is there anything specific you'd like to know?`,
    ];
    return responses[Math.floor(Math.random() * responses.length)];
  }

  private generateGreeting(): string {
    const greetings = [
      'Hello. How can I help you?',
      'Hi there. What can I do for you?',
      'Hello. I\'m ready to assist.',
    ];
    return greetings[Math.floor(Math.random() * greetings.length)];
  }

  private generateDefaultResponse(data: any): string {
    return 'I understand. Let me help you with that.';
  }

  /**
   * Check if response is natural (not robotic)
   */
  isNaturalResponse(response: string): boolean {
    const roboticPatterns = [
      /certainly/i,
      /i would be happy to/i,
      /as an ai/i,
      /i am an artificial intelligence/i,
      /please let me know if you have any other questions/i,
    ];

    return !roboticPatterns.some(pattern => pattern.test(response));
  }

  /**
   * Suggest improvements to make response more natural
   */
  suggestImprovements(response: string): string[] {
    const suggestions: string[] = [];

    if (response.includes('Certainly')) {
      suggestions.push('Replace "Certainly" with a more natural response');
    }

    if (response.includes('I would be happy to')) {
      suggestions.push('Remove "I would be happy to" - be more direct');
    }

    if (response.includes('As an AI')) {
      suggestions.push('Remove "As an AI" - not necessary');
    }

    if (response.split(' ').length > 30) {
      suggestions.push('Consider making the response more concise');
    }

    return suggestions;
  }

  updateConfig(config: Partial<PersonalityConfig>): void {
    this.config = { ...this.config, ...config };
  }

  getConfig(): PersonalityConfig {
    return { ...this.config };
  }
}
