import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../profile/services/profile_service.dart';

class HelpFaq {
  final String id;
  final String question;
  final String answer;
  final IconData? icon;

  const HelpFaq({
    required this.id,
    required this.question,
    required this.answer,
    this.icon,
  });
}

class HelpState {
  final List<HelpFaq> faqs;
  final bool isLoading;
  final String? errorMessage;

  const HelpState({
    this.faqs = const [],
    this.isLoading = false,
    this.errorMessage,
  });

  HelpState copyWith({
    List<HelpFaq>? faqs,
    bool? isLoading,
    String? errorMessage,
    bool clearError = false,
  }) {
    return HelpState(
      faqs: faqs ?? this.faqs,
      isLoading: isLoading ?? this.isLoading,
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
    );
  }
}

class HelpNotifier extends StateNotifier<HelpState> {
  final PersonalService _personalService;

  HelpNotifier(this._personalService) : super(const HelpState()) {
    loadFaqs();
  }

  Future<void> loadFaqs() async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      await _personalService.getProfile();
      await Future.delayed(const Duration(milliseconds: 200));
      state = state.copyWith(faqs: _defaultFaqs, isLoading: false);
    } catch (e) {
      debugPrint('Help faqs load failed: $e');
      state = state.copyWith(faqs: _defaultFaqs, isLoading: false);
    }
  }

  static const _defaultFaqs = [
    HelpFaq(
      id: '1',
      question: 'How do I set up DASH?',
      answer: 'Add the backend URL in Settings using the form field provided. Ensure the backend is running on your local machine or network.',
      icon: Icons.settings,
    ),
    HelpFaq(
      id: '2',
      question: 'How do I create a conversation?',
      answer: 'Go to the Chat tab and tap the compose button. Type your message and send it to start a conversation with DASH.',
      icon: Icons.chat_bubble_outline,
    ),
    HelpFaq(
      id: '3',
      question: 'What is Memory?',
      answer: 'Memory is an AI-powered knowledge base that remembers important information about you across conversations.',
      icon: Icons.memory,
    ),
    HelpFaq(
      id: '4',
      question: 'How do I enable dark mode?',
      answer: 'Go to Settings and toggle the Dark Mode switch at the top of the Appearance section.',
      icon: Icons.dark_mode,
    ),
    HelpFaq(
      id: '5',
      question: 'Are my conversations private?',
      answer: 'DASH provides secure, end-to-end encryption for your data. Your conversations are never shared with third parties.',
      icon: Icons.lock_outlined,
    ),
    HelpFaq(
      id: '6',
      question: 'How do I manage plugins?',
      answer: 'Open the Plugins page from the navigation menu. You can install, enable, or disable plugins from there.',
      icon: Icons.extension,
    ),
    HelpFaq(
      id: '7',
      question: 'What is the WebSocket connection for?',
      answer: 'The WebSocket connection enables real-time streaming of AI responses and live updates across all your devices.',
      icon: Icons.circle_outlined,
    ),
    HelpFaq(
      id: '8',
      question: 'How do I search across my data?',
      answer: 'Use the Search page to search across conversations, memories, tasks, and files. Results are tabbed for easy navigation.',
      icon: Icons.search_outlined,
    ),
  ];
}

final helpProvider = StateNotifierProvider<HelpNotifier, HelpState>((ref) {
  final personalService = ref.watch(personalServiceProvider);
  return HelpNotifier(personalService);
});
