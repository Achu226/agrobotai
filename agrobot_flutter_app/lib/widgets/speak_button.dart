import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../l10n.dart';

import '../services/voice.dart';
import '../state/session_state.dart';
import 'common.dart';

/// Speaker button: reads [text] aloud in [language] with the laptop's voices; tap again to stop.
class SpeakButton extends StatelessWidget {
  const SpeakButton({super.key, required this.id, required this.text, this.language, this.label, this.compact = false});

  final String id;
  final String text;
  final String? language;
  final String? label;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final voice = VoiceController.shared;
    return ListenableBuilder(
      listenable: voice,
      builder: (context, _) {
        final active = voice.isActive(id);
        final icon = active && voice.loading
            ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
            : Icon(active ? Icons.stop_circle_outlined : Icons.volume_up_outlined, color: kGreen);
        void onTap() async {
          await voice.toggle(id, text, context.read<SessionState>(), language: language);
          if (voice.error != null && context.mounted) {
            ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(voice.error!)));
          }
        }

        if (compact || label == null) {
          return IconButton(
            tooltip: context.tr(active ? 'Stop' : 'Listen'),
            visualDensity: VisualDensity.compact,
            onPressed: text.trim().isEmpty ? null : onTap,
            icon: icon,
          );
        }
        return TextButton.icon(onPressed: text.trim().isEmpty ? null : onTap, icon: icon, label: Text(context.tr(active ? 'Stop' : label!)));
      },
    );
  }
}
