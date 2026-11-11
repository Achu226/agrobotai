import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../l10n.dart';
import '../services/api_client.dart';
import '../state/session_state.dart';
import '../widgets/common.dart';

/// Disease & pest guide: the verified fact sheets the advisor uses, in the farmer's language.
class LibraryScreen extends StatefulWidget {
  const LibraryScreen({super.key});

  @override
  State<LibraryScreen> createState() => _LibraryScreenState();
}

class _LibraryScreenState extends State<LibraryScreen> {
  Future<List<Map<String, dynamic>>>? _future;
  String? _language;
  String _query = '';
  bool _offlineCopy = false;

  /// The guide from the server, saved on the phone each time; without a connection the saved copy is shown.
  Future<List<Map<String, dynamic>>> _load(SessionState s) async {
    final key = 'library_cache_${s.language}';
    final prefs = await SharedPreferences.getInstance();
    try {
      final entries = await s.api.library(s.language);
      await prefs.setString(key, jsonEncode(entries));
      _offlineCopy = false;
      return entries;
    } catch (_) {
      final saved = prefs.getString(key);
      if (saved == null) rethrow;
      _offlineCopy = true;
      return (jsonDecode(saved) as List).cast<Map<String, dynamic>>();
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = context.watch<SessionState>();
    if (_language != s.language) {
      _language = s.language;
      _future = _load(s);
    }
    return FutureBuilder<List<Map<String, dynamic>>>(
      future: _future,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
        if (snap.hasError) {
          final e = snap.error;
          return ListView(padding: const EdgeInsets.all(16), children: [
            MessagePanel(icon: Icons.cloud_off, title: 'Could not load the guide', message: e is ApiException ? e.message : '$e', actions: [
              OutlinedButton(onPressed: () => setState(() => _language = null), child: Text(context.tr('Retry'))),
            ]),
          ]);
        }
        final q = _query.trim().toLowerCase();
        final entries = snap.data!
            .where((e) => q.isEmpty || '${e['name']} ${e['english_name'] ?? ''} ${e['crop'] ?? ''}'.toLowerCase().contains(q))
            .toList();
        final groups = <String, List<Map<String, dynamic>>>{};
        for (final e in entries) {
          groups.putIfAbsent(e['kind'] == 'pest' ? 'Insect pests' : '${e['crop']}', () => []).add(e);
        }
        return ListView(padding: const EdgeInsets.all(12), children: [
          TextField(
            onChanged: (v) => setState(() => _query = v),
            decoration: InputDecoration(
                hintText: context.tr('Search diseases and pests'), prefixIcon: const Icon(Icons.search), border: const OutlineInputBorder(), isDense: true),
          ),
          if (_offlineCopy)
            const Padding(
              padding: EdgeInsets.only(top: 8),
              child: MessagePanel(
                  icon: Icons.cloud_off, title: 'Offline: showing the guide saved on this phone', color: Colors.blueGrey),
            ),
          const SizedBox(height: 8),
          for (final g in groups.entries)
            SectionCard(title: g.key, icon: g.key == 'Insect pests' ? Icons.bug_report_outlined : Icons.local_florist, children: [
              for (final e in g.value)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: Icon(
                      switch (e['kind']) {
                        'pest' => Icons.bug_report,
                        'healthy' => Icons.check_circle_outline,
                        _ => Icons.coronavirus_outlined,
                      },
                      color: e['kind'] == 'healthy' ? kGreen : Colors.red.shade400),
                  title: Text('${e['name']}'),
                  subtitle: e['english_name'] != null ? Text('${e['english_name']}', style: const TextStyle(fontSize: 12)) : null,
                  trailing: const Icon(Icons.chevron_right),
                  onTap: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => LibraryDetailScreen(entry: e))),
                ),
            ]),
        ]);
      },
    );
  }
}

class LibraryDetailScreen extends StatefulWidget {
  const LibraryDetailScreen({super.key, required this.entry});

  final Map<String, dynamic> entry;

  @override
  State<LibraryDetailScreen> createState() => _LibraryDetailScreenState();
}

class _LibraryDetailScreenState extends State<LibraryDetailScreen> {
  late Map<String, dynamic> _entry = widget.entry;
  bool _translating = false;
  bool _showEnglish = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    final lang = context.read<SessionState>().language;
    // Not yet in this language: the laptop AI translates it once (then it is cached for everyone)
    if (lang != 'en' && _entry['translated'] != true) WidgetsBinding.instance.addPostFrameCallback((_) => _translate(lang));
  }

  Future<void> _translate(String lang) async {
    setState(() => _translating = true);
    try {
      final e = await context.read<SessionState>().api.libraryEntry('${_entry['key']}', lang);
      if (mounted) setState(() => _entry = e);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _translating = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final e = _entry;
    final facts = ((_showEnglish ? e['english_facts'] : null) ?? e['facts'] as List).cast<Object?>();
    final machine = e['translated'] == true && e['reviewed'] != true;
    return Scaffold(
      appBar: AppBar(title: Text('${e['name']}'), backgroundColor: kGreen, foregroundColor: Colors.white),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        if (e['english_name'] != null) Text('${e['english_name']}', style: TextStyle(color: Colors.grey.shade700)),
        const SizedBox(height: 8),
        if (_translating) ...[
          const LinearProgressIndicator(),
          Text(context.tr('Translating with the laptop AI…')),
        ],
        if (_error != null) MessagePanel(icon: Icons.translate, title: 'Shown in English', message: _error, color: Colors.grey),
        if (machine)
          const MessagePanel(
              icon: Icons.translate,
              title: 'Machine-translated',
              message: 'Translated by the laptop AI. If something is unclear, check the English text or ask your agriculture officer.',
              color: Colors.orange),
        SectionCard(title: _showEnglish ? 'English' : 'Facts', icon: Icons.menu_book, children: [
          for (final f in facts) Padding(padding: const EdgeInsets.only(bottom: 8), child: Text('• $f', style: const TextStyle(fontSize: 15))),
        ]),
        if (e['english_facts'] != null)
          TextButton.icon(
            onPressed: () => setState(() => _showEnglish = !_showEnglish),
            icon: const Icon(Icons.translate),
            label: Text(context.tr(_showEnglish ? 'Show in my language' : 'Show the English original')),
          ),
        Text(context.tr('General guidance from verified sources. Follow the product label and your agriculture officer before using any chemical.'),
            style: const TextStyle(fontSize: 12, fontStyle: FontStyle.italic)),
      ]),
    );
  }
}
