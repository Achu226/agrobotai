import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../l10n.dart';

import '../models/models.dart';
import '../services/api_client.dart';
import '../services/voice.dart';
import '../state/session_state.dart';
import '../widgets/common.dart';
import '../widgets/speak_button.dart';

class _Message {
  _Message(this.role, this.text, {this.isError = false});

  final String role; // 'user' | 'assistant'
  String text;
  String? meta;
  final bool isError;
  String? language;
  final String id = '${DateTime.now().microsecondsSinceEpoch}';
}

/// Farm advisor chat in 12 languages, by typing or by voice.
///
/// * Answers stream in word by word from the laptop's local AI.
/// * By default the advisor knows the farmer's latest scan (shown as a chip that can be cleared).
/// * Mic: speech is turned into text by Whisper on the laptop; the speaker icon reads answers aloud.
/// When the laptop AI is offline the error is shown — there are no canned answers.
class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key, this.scanId, this.recorder});

  /// When set, the advisor talks about this scan instead of the latest one.
  final int? scanId;
  final VoiceRecorder? recorder;

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final _input = TextEditingController();
  final _scroll = ScrollController();
  final _messages = <_Message>[];
  Map<String, List<String>> _suggestions = {};
  bool _sending = false;
  bool _useScan = true;
  Map<String, dynamic>? _context; // {scan_id, crop, label} the advisor used last
  VoiceRecorder? _recorder;
  bool _recording = false;
  bool _transcribing = false;
  DateTime? _recordStarted;
  Timer? _recordTimer;

  @override
  void initState() {
    super.initState();
    _loadSuggestions();
  }

  @override
  void dispose() {
    _recordTimer?.cancel();
    _recorder?.dispose();
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _loadSuggestions() async {
    try {
      final langs = await context.read<SessionState>().api.languages();
      if (!mounted) return;
      setState(() => _suggestions = {
            for (final l in langs) l['code'] as String: ((l['suggestions'] as List?) ?? const []).map((e) => '$e').toList(),
          });
    } on ApiException {
      // Suggestions are optional; chat still works
    }
  }

  Future<void> _send([String? preset, String? spokenLanguage]) async {
    final text = (preset ?? _input.text).trim();
    if (text.isEmpty || _sending) return;
    final s = context.read<SessionState>();
    final history = [
      for (final m in _messages.where((m) => !m.isError).toList().reversed.take(8).toList().reversed) {'role': m.role, 'content': m.text},
    ];
    final answer = _Message('assistant', '');
    setState(() {
      _messages.add(_Message('user', text));
      _sending = true;
      _input.clear();
    });
    _scrollToEnd();
    final started = DateTime.now();
    var added = false;
    try {
      await for (final ev in s.api
          .chatStream(text, language: spokenLanguage ?? s.language, history: history, scanId: widget.scanId, useLatestScan: _useScan)) {
        if (!mounted) return;
        switch (ev['type']) {
          case 'start':
            setState(() {
              _context = ev['context'] as Map<String, dynamic>?;
              answer.language = ev['language'] as String?;
              _messages.add(answer);
              added = true;
            });
          case 'delta':
            setState(() => answer.text += '${ev['text']}');
            _scrollToEnd(animate: false);
          case 'done':
            final first = ev['first_token_s'];
            setState(() => answer.meta =
                '${context.tr('Laptop AI')} • ${ev['language_name']} • ${context.tr('first words')} ${first}s • ${ev['elapsed_s']} s');
        }
      }
      if (s.autoRead && mounted && answer.text.trim().isNotEmpty) {
        unawaited(VoiceController.shared.toggle(answer.id, answer.text, s, language: answer.language));
      }
    } on ApiException catch (e) {
      if (e.kind == ApiErrorKind.unauthorized) await s.handleUnauthorized(e);
      if (!mounted) return;
      setState(() {
        if (added && answer.text.isEmpty) _messages.remove(answer);
        _messages.add(_Message('assistant', e.message, isError: true));
      });
    } finally {
      if (mounted) {
        setState(() {
          _sending = false;
          answer.meta ??= 'Laptop AI • ${DateTime.now().difference(started).inMilliseconds / 1000} s';
        });
      }
      _scrollToEnd();
    }
  }

  // ------------------------------------------------------------ voice input

  Future<void> _toggleRecording() async {
    if (_transcribing || _sending) return;
    if (_recording) return _stopRecording();
    _recorder ??= widget.recorder ?? PluginVoiceRecorder();
    try {
      if (!await _recorder!.hasPermission()) {
        if (!mounted) return;
        _snack(context.tr('Microphone permission is needed to ask by voice. Allow it in Settings → Apps → AGROBOTAI.'));
        return;
      }
      await VoiceController.shared.stop();
      await _recorder!.start();
      setState(() {
        _recording = true;
        _recordStarted = DateTime.now();
      });
      _recordTimer = Timer.periodic(const Duration(milliseconds: 500), (_) {
        if (!mounted) return;
        setState(() {});
        if (DateTime.now().difference(_recordStarted!).inSeconds >= 55) _stopRecording();
      });
    } catch (e) {
      _snack('Could not start the microphone: $e');
    }
  }

  Future<void> _stopRecording() async {
    _recordTimer?.cancel();
    setState(() {
      _recording = false;
      _transcribing = true;
    });
    final s = context.read<SessionState>();
    try {
      final wav = await _recorder!.stop();
      if (wav == null || wav.isEmpty) throw ApiException(ApiErrorKind.validation, 'Nothing was recorded.');
      final res = await s.api.transcribe(wav);
      final text = '${res['text']}'.trim();
      if (!mounted) return;
      setState(() => _transcribing = false);
      await _send(text, res['language'] as String?);
    } on ApiException catch (e) {
      if (e.kind == ApiErrorKind.unauthorized) await s.handleUnauthorized(e);
      _snack(e.message);
    } catch (e) {
      _snack('Voice input failed: $e');
    } finally {
      if (mounted) setState(() => _transcribing = false);
    }
  }

  void _snack(String text) {
    if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
  }

  void _scrollToEnd({bool animate = true}) => WidgetsBinding.instance.addPostFrameCallback((_) {
        if (!_scroll.hasClients) return;
        final end = _scroll.position.maxScrollExtent;
        animate ? _scroll.animateTo(end, duration: const Duration(milliseconds: 250), curve: Curves.easeOut) : _scroll.jumpTo(end);
      });

  Future<void> _voiceSettings() async {
    final s = context.read<SessionState>();
    await showModalBottomSheet<void>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setSheet) => SafeArea(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            ListTile(title: Text(context.tr('Voice'), style: const TextStyle(fontWeight: FontWeight.bold))),
            for (final (value, title, subtitle) in const [
              ('local', 'Offline voice (laptop)', 'Runs on the laptop GPU — works without internet'),
              ('online', 'Natural voice (internet)', 'Microsoft neural voices — needs internet on the laptop'),
              ('auto', 'Automatic', 'Natural voice when online, offline voice otherwise'),
            ])
              ListTile(
                leading: Icon(s.voiceEngine == value ? Icons.radio_button_checked : Icons.radio_button_off, color: kGreen),
                title: Text(context.tr(title)),
                subtitle: Text(context.tr(subtitle)),
                onTap: () async {
                  await s.setVoiceEngine(value);
                  setSheet(() {});
                },
              ),
            SwitchListTile(
              value: s.autoRead,
              onChanged: (v) async {
                await s.setAutoRead(v);
                setSheet(() {});
              },
              title: Text(context.tr('Read answers aloud automatically')),
            ),
          ]),
        ),
      ),
    );
    if (mounted) setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    final s = context.watch<SessionState>();
    final suggestions = _suggestions[s.language] ?? const <String>[];
    final ctx = _context;
    final recSeconds = _recording && _recordStarted != null ? DateTime.now().difference(_recordStarted!).inSeconds : 0;
    return Column(children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(12, 4, 4, 0),
        child: Row(children: [
          const Icon(Icons.translate, color: kGreen),
          const SizedBox(width: 8),
          Expanded(
            child: DropdownButton<String>(
              value: s.language,
              isExpanded: true,
              underline: const SizedBox.shrink(),
              items: [for (final (code, _, _) in kLanguages) DropdownMenuItem(value: code, child: Text(languageLabel(code)))],
              onChanged: (v) => v == null ? null : s.setLanguage(v),
            ),
          ),
          IconButton(
              tooltip: context.tr('Voice settings'),
              onPressed: _voiceSettings,
              icon: Icon(s.autoRead ? Icons.record_voice_over : Icons.settings_voice_outlined)),
        ]),
      ),
      if (widget.scanId == null)
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12),
          child: Align(
            alignment: Alignment.centerLeft,
            child: _useScan
                ? InputChip(
                    avatar: const Icon(Icons.eco, size: 18, color: kGreen),
                    label: Text(
                        ctx == null
                            ? context.tr('Using your latest scan')
                            : '${context.tr('About scan #{id}', {'id': ctx['scan_id']})}: ${context.tr('${ctx['crop']}')} • ${ctx['label']}',
                        overflow: TextOverflow.ellipsis),
                    onDeleted: () => setState(() {
                      _useScan = false;
                      _context = null;
                    }),
                    deleteButtonTooltipMessage: context.tr('General question (no scan)'),
                  )
                : ActionChip(
                    avatar: const Icon(Icons.add, size: 18),
                    label: Text(context.tr('Use my latest scan')),
                    onPressed: () => setState(() => _useScan = true),
                  ),
          ),
        ),
      const Divider(height: 1),
      Expanded(
        child: _messages.isEmpty
            ? ListView(padding: const EdgeInsets.all(16), children: [
                Text(
                    widget.scanId != null
                        ? context.tr('Ask anything about scan #{id}.', {'id': widget.scanId})
                        : context.tr('Ask the farm advisor anything about your crop.'),
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                const SizedBox(height: 6),
                Text(context.tr('Type or tap the mic and speak in Tamil, English or any of the 12 languages. '
                    'Tap the speaker on an answer to hear it.')),
                const SizedBox(height: 12),
                for (final q in suggestions)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: OutlinedButton(
                      style: OutlinedButton.styleFrom(alignment: Alignment.centerLeft, padding: const EdgeInsets.all(12)),
                      onPressed: () => _send(q),
                      child: Text(q),
                    ),
                  ),
              ])
            : ListView.builder(
                controller: _scroll,
                padding: const EdgeInsets.all(12),
                itemCount: _messages.length + (_sending && (_messages.isEmpty || _messages.last.role == 'user') ? 1 : 0),
                itemBuilder: (context, i) {
                  if (i == _messages.length) return _Bubble(role: 'assistant', text: context.tr('Thinking…'), pending: true);
                  final m = _messages[i];
                  return _Bubble(
                    role: m.role,
                    text: m.text,
                    meta: m.meta,
                    isError: m.isError,
                    speak: m.role == 'assistant' && !m.isError && m.meta != null
                        ? SpeakButton(id: m.id, text: m.text, language: m.language, compact: true)
                        : null,
                  );
                },
              ),
      ),
      if (_recording || _transcribing)
        Container(
          width: double.infinity,
          color: _recording ? Colors.red.shade50 : Colors.green.shade50,
          padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 12),
          child: Text(
            _recording
                ? '● ${context.tr('Listening… {s}s — tap the mic again when you finish', {'s': recSeconds})}'
                : context.tr('Understanding your voice on the laptop…'),
            style: TextStyle(color: _recording ? Colors.red.shade900 : kDarkGreen, fontWeight: FontWeight.w600),
          ),
        ),
      SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(8, 4, 8, 8),
          child: Row(children: [
            IconButton.filledTonal(
              tooltip: context.tr(_recording ? 'Stop and send' : 'Ask by voice'),
              style: IconButton.styleFrom(
                  backgroundColor: _recording ? Colors.red : null, foregroundColor: _recording ? Colors.white : kGreen),
              onPressed: _sending || _transcribing ? null : _toggleRecording,
              icon: _transcribing
                  ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                  : Icon(_recording ? Icons.stop : Icons.mic),
            ),
            const SizedBox(width: 4),
            Expanded(
              child: TextField(
                controller: _input,
                minLines: 1,
                maxLines: 4,
                textInputAction: TextInputAction.send,
                onSubmitted: (_) => _send(),
                decoration: InputDecoration(hintText: context.tr('Type or speak your question…'), border: const OutlineInputBorder(), isDense: true),
              ),
            ),
            const SizedBox(width: 4),
            IconButton.filled(
              style: IconButton.styleFrom(backgroundColor: kGreen),
              onPressed: _sending || _recording ? null : _send,
              icon: const Icon(Icons.send),
            ),
          ]),
        ),
      ),
    ]);
  }
}

class _Bubble extends StatelessWidget {
  const _Bubble({required this.role, required this.text, this.meta, this.isError = false, this.pending = false, this.speak});

  final String role;
  final String text;
  final String? meta;
  final bool isError;
  final bool pending;
  final Widget? speak;

  @override
  Widget build(BuildContext context) {
    final mine = role == 'user';
    final color = isError ? Colors.red.shade50 : (mine ? kGreen : Colors.grey.shade200);
    return Align(
      alignment: mine ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.fromLTRB(12, 10, 6, 10),
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.86),
        decoration: BoxDecoration(color: color, borderRadius: BorderRadius.circular(14)),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          if (isError) Text(context.tr('Advisor unavailable'), style: TextStyle(fontWeight: FontWeight.bold, color: Colors.red.shade900)),
          if (pending)
            const Padding(
                padding: EdgeInsets.only(bottom: 6),
                child: SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))),
          Padding(
            padding: const EdgeInsets.only(right: 6),
            child: SelectableText(text.isEmpty ? '…' : text, style: TextStyle(color: mine ? Colors.white : Colors.black87, fontSize: 15)),
          ),
          if (meta != null || speak != null)
            Row(mainAxisSize: MainAxisSize.min, children: [
              if (meta != null) Flexible(child: Text(meta!, style: const TextStyle(fontSize: 11, color: Colors.black54))),
              if (speak != null) speak!,
            ]),
        ]),
      ),
    );
  }
}
