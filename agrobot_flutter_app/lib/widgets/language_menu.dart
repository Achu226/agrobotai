import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../l10n.dart';
import '../models/models.dart';
import '../state/session_state.dart';

/// Language picker for the whole app (screens, advice, chat and voice).
class LanguageMenu extends StatelessWidget {
  const LanguageMenu({super.key, this.color, this.showName = false});

  final Color? color;
  final bool showName;

  @override
  Widget build(BuildContext context) {
    final s = context.watch<SessionState>();
    return PopupMenuButton<String>(
      tooltip: context.tr('Language'),
      initialValue: s.language,
      onSelected: s.setLanguage,
      itemBuilder: (_) => [for (final (code, _, _) in kLanguages) PopupMenuItem(value: code, child: Text(languageLabel(code)))],
      child: Padding(
        padding: const EdgeInsets.all(8),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          Icon(Icons.translate, color: color),
          if (showName) ...[const SizedBox(width: 6), Text(languageLabel(s.language), style: TextStyle(color: color))],
        ]),
      ),
    );
  }
}
