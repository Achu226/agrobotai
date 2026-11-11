import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../l10n.dart';
import 'package:share_plus/share_plus.dart';

import '../models/models.dart';
import '../screens/chat_screen.dart';
import '../services/api_client.dart';
import '../state/session_state.dart';
import 'common.dart';
import 'speak_button.dart';

const _advisableStates = {'disease_detected', 'pest_detected', 'disease_and_pest_detected'};

/// Advice for one scan in the farmer's language. Written by the laptop's local AI on request
/// (cached per language on the server); an offline rule-book card is labelled as such.
class AdviceCard extends StatefulWidget {
  const AdviceCard({super.key, required this.scan});

  final ScanRecord scan;

  @override
  State<AdviceCard> createState() => _AdviceCardState();
}

class _AdviceCardState extends State<AdviceCard> {
  Map<String, dynamic>? _advice;
  String? _error;
  bool _loading = false;
  late String _language;

  AnalysisResult? get _result => widget.scan.result;
  bool get _advisable => _advisableStates.contains(_result?.summaryState);

  @override
  void initState() {
    super.initState();
    _language = context.read<SessionState>().language;
    if (_advisable) {
      final cached = _cached(_language);
      if (cached != null) {
        _advice = cached;
      } else {
        WidgetsBinding.instance.addPostFrameCallback((_) => _load());
      }
    }
  }

  Map<String, dynamic>? _cached(String code) {
    final byLang = _result?.raw['advice_by_language'];
    final card = byLang is Map ? byLang[code] : null;
    return card is Map<String, dynamic> && card['source'] == 'local_llm' ? card : null;
  }

  Future<void> _load({bool refresh = false}) async {
    if (_loading) return;
    final s = context.read<SessionState>();
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final card = await s.api.scanAdvice(widget.scan.id, language: _language, refresh: refresh);
      if (mounted) setState(() => _advice = card);
    } on ApiException catch (e) {
      if (e.kind == ApiErrorKind.unauthorized) await s.handleUnauthorized(e);
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _changeLanguage(String code) async {
    await context.read<SessionState>().setLanguage(code);
    setState(() {
      _language = code;
      _advice = _cached(code);
    });
    if (_advice == null) await _load();
  }

  /// The whole card as plain text — read aloud and shared exactly as shown.
  String _adviceText(Map<String, dynamic> a) => [
        if ((a['headline'] as String? ?? '').isNotEmpty) a['headline'],
        if ((a['farmer_message'] as String? ?? '').isNotEmpty) a['farmer_message'],
        for (final section in (a['sections'] as List? ?? const []).cast<Map<String, dynamic>>()) ...[
          '${section['title']}:',
          for (final item in (section['items'] as List? ?? const [])) '- $item',
        ],
      ].join('\n');

  @override
  Widget build(BuildContext context) {
    final r = _result;
    if (r == null) return const SizedBox.shrink();
    if (!_advisable) {
      final items = r.adviceItems;
      return SectionCard(title: 'Advice', icon: Icons.tips_and_updates_outlined, children: [
        if (items.isEmpty) Text(context.tr('No disease or pest was confirmed, so no treatment advice is needed.')),
        for (final item in items) Padding(padding: const EdgeInsets.only(bottom: 4), child: Text('• $item')),
      ]);
    }
    final a = _advice;
    final offline = a?['source'] == 'rule_book_offline';
    return SectionCard(title: 'Advice', icon: Icons.tips_and_updates_outlined, children: [
      DropdownButtonFormField<String>(
        initialValue: _language,
        isExpanded: true,
        decoration: InputDecoration(labelText: context.tr('Language'), isDense: true, border: const OutlineInputBorder()),
        items: [for (final (code, _, _) in kLanguages) DropdownMenuItem(value: code, child: Text(languageLabel(code)))],
        onChanged: _loading ? null : (v) => v == null ? null : _changeLanguage(v),
      ),
      const SizedBox(height: 12),
      if (_loading) ...[
        const LinearProgressIndicator(),
        const SizedBox(height: 8),
        Text(context.tr('Writing advice in {lang}… the laptop AI can take up to a minute.', {'lang': languageLabel(_language)})),
      ] else if (_error != null) ...[
        MessagePanel(icon: Icons.cloud_off, title: 'Advice not available', message: _error),
        TextButton.icon(onPressed: _load, icon: const Icon(Icons.refresh), label: Text(context.tr('Try again'))),
      ] else if (a != null) ...[
        if (offline)
          MessagePanel(
            icon: Icons.warning_amber,
            title: 'AI advisor offline — general guidance only',
            message: '${a['note'] ?? ''} Start Ollama on the laptop (start.bat does this), then tap "Write again".'.trim(),
            color: Colors.orange,
          ),
        if ((a['headline'] as String? ?? '').isNotEmpty)
          Text(a['headline'] as String, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
        if ((a['farmer_message'] as String? ?? '').isNotEmpty)
          Padding(padding: const EdgeInsets.only(top: 4, bottom: 8), child: Text(a['farmer_message'] as String)),
        for (final section in (a['sections'] as List? ?? const []).cast<Map<String, dynamic>>()) ...[
          Padding(
            padding: const EdgeInsets.only(top: 8, bottom: 4),
            child: Text('${section['title']}', style: const TextStyle(fontWeight: FontWeight.bold, color: kDarkGreen)),
          ),
          for (final item in (section['items'] as List? ?? const []))
            Padding(padding: const EdgeInsets.only(bottom: 4), child: Text('• $item')),
        ],
        const SizedBox(height: 8),
        Text(
          offline
              ? context.tr('Source: built-in rule book (not specific to this scan)')
              : context.tr(
                  'Written by the laptop AI ({model}) in {s} s from the findings above. '
                  'Check with your agriculture officer before spraying.',
                  {'model': a['model'], 's': a['elapsed_s']}),
          style: const TextStyle(fontSize: 12, fontStyle: FontStyle.italic),
        ),
        Wrap(spacing: 8, children: [
          SpeakButton(id: 'advice-${widget.scan.id}-$_language', text: _adviceText(a), language: _language, label: context.tr('Listen')),
          TextButton.icon(
            onPressed: () => SharePlus.instance
                .share(ShareParams(text: 'AGROBOTAI advice — scan #${widget.scan.id}\n\n${_adviceText(a)}', subject: 'AGROBOTAI advice')),
            icon: const Icon(Icons.share_outlined),
            label: Text(context.tr('Share')),
          ),
          TextButton.icon(onPressed: () => _load(refresh: true), icon: const Icon(Icons.refresh), label: Text(context.tr('Write again'))),
          TextButton.icon(
            onPressed: () => Navigator.of(context).push(MaterialPageRoute(
                builder: (_) => Scaffold(
                      appBar: AppBar(title: Text(context.tr('Ask about this scan')), backgroundColor: kGreen, foregroundColor: Colors.white),
                      body: ChatScreen(scanId: widget.scan.id),
                    ))),
            icon: const Icon(Icons.chat_outlined),
            label: Text(context.tr('Ask a question')),
          ),
        ]),
      ],
    ]);
  }
}
