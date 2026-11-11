import 'dart:async';
import 'dart:io';

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';

import '../state/session_state.dart';
import 'api_client.dart';

/// Microphone access. The plugin version records 16 kHz mono WAV, which the laptop's Whisper reads directly.
abstract class VoiceRecorder {
  Future<bool> hasPermission();
  Future<void> start();

  /// Stops and returns the WAV bytes (null if nothing was recorded).
  Future<Uint8List?> stop();
  Future<void> cancel();
  Future<void> dispose();
}

class PluginVoiceRecorder implements VoiceRecorder {
  final _recorder = AudioRecorder();
  String? _path;

  @override
  Future<bool> hasPermission() => _recorder.hasPermission();

  @override
  Future<void> start() async {
    final dir = await getTemporaryDirectory();
    _path = '${dir.path}/agrobot_question.wav';
    await _recorder.start(
      const RecordConfig(encoder: AudioEncoder.wav, sampleRate: 16000, numChannels: 1, noiseSuppress: true, autoGain: true),
      path: _path!,
    );
  }

  @override
  Future<Uint8List?> stop() async {
    final path = await _recorder.stop() ?? _path;
    if (path == null) return null;
    final file = File(path);
    if (!await file.exists()) return null;
    final bytes = await file.readAsBytes();
    unawaited(file.delete());
    return bytes;
  }

  @override
  Future<void> cancel() => _recorder.cancel();

  @override
  Future<void> dispose() => _recorder.dispose();
}

/// Speaker output.
abstract class AudioOut {
  Future<void> play(Uint8List bytes, String mimeType);
  Future<void> stop();
  Stream<void> get onComplete;
  Future<void> dispose();
}

class PluginAudioOut implements AudioOut {
  final _player = AudioPlayer();

  @override
  Future<void> play(Uint8List bytes, String mimeType) => _player.play(BytesSource(bytes, mimeType: mimeType));

  @override
  Future<void> stop() => _player.stop();

  @override
  Stream<void> get onComplete => _player.onPlayerComplete;

  @override
  Future<void> dispose() => _player.dispose();
}

/// Reads text aloud with the laptop's voices. One clip plays at a time; [activeKey] tells the UI
/// which message/card is loading or speaking so it can show a stop button.
class VoiceController extends ChangeNotifier {
  VoiceController({AudioOut Function()? audioOut}) : _makeOut = audioOut ?? PluginAudioOut.new;

  /// App-wide instance (tests replace it with one using a fake speaker).
  static VoiceController shared = VoiceController();

  final AudioOut Function() _makeOut;
  AudioOut? _out;
  String? activeKey;
  bool loading = false;
  String? lastEngine;
  String? error;
  final _cache = <String, (Uint8List, String)>{};

  bool isActive(String key) => activeKey == key;

  /// Splits an answer into short pieces at sentence ends so the first one can play within about a second.
  static List<String> chunks(String text, {int maxLen = 220}) {
    final clean = text.replaceAll(RegExp(r'[*#_`>|~]+'), ' ').replaceAll(RegExp(r'\s+'), ' ').trim();
    if (clean.isEmpty) return const [];
    final out = <String>[];
    var current = '';
    for (final sentence in clean.split(RegExp(r'(?<=[.!?।॥:])\s+'))) {
      if (current.isNotEmpty && current.length + sentence.length + 1 > maxLen) {
        out.add(current);
        current = '';
      }
      current = current.isEmpty ? sentence : '$current $sentence';
      while (current.length > maxLen) {
        final cut = current.lastIndexOf(' ', maxLen);
        final at = cut > 40 ? cut : maxLen;
        out.add(current.substring(0, at).trim());
        current = current.substring(at).trim();
      }
    }
    if (current.isNotEmpty) out.add(current);
    return out;
  }

  /// Reads [text] aloud (or stops it, if it is the one playing). Pieces are fetched one ahead of playback.
  Future<void> toggle(String key, String text, SessionState session, {String? language}) async {
    if (activeKey == key) return stop();
    await stop();
    final pieces = chunks(text);
    if (pieces.isEmpty) return;
    final run = ++_run;
    activeKey = key;
    loading = true;
    error = null;
    notifyListeners();
    final lang = language ?? session.language;
    try {
      _out ??= _makeOut();
      var next = _clip(session, pieces.first, lang);
      for (var i = 0; i < pieces.length; i++) {
        final (bytes, mime) = await next;
        if (run != _run) return; // stopped or replaced while loading
        if (i + 1 < pieces.length) next = _clip(session, pieces[i + 1], lang); // prefetch while this one plays
        loading = false;
        notifyListeners();
        final finished = _out!.onComplete.first;
        await _out!.play(bytes, mime);
        await finished;
        if (run != _run) return;
      }
      activeKey = null;
      notifyListeners();
    } on ApiException catch (e) {
      _fail(run, e.message);
    } catch (e) {
      _fail(run, 'Could not play the voice: $e');
    }
  }

  int _run = 0;

  void _fail(int run, String message) {
    if (run != _run) return;
    error = message;
    activeKey = null;
    loading = false;
    notifyListeners();
  }

  Future<(Uint8List, String)> _clip(SessionState session, String text, String lang) async {
    final cacheKey = '${session.voiceEngine}|$lang|$text';
    final cached = _cache[cacheKey];
    if (cached != null) return cached;
    final (bytes, mime, engine) = await session.api.speak(text, language: lang, engine: session.voiceEngine);
    lastEngine = engine;
    if (_cache.length > 60) _cache.remove(_cache.keys.first);
    return _cache[cacheKey] = (bytes, mime);
  }

  Future<void> stop() async {
    _run++;
    activeKey = null;
    loading = false;
    await _out?.stop();
    notifyListeners();
  }

  @override
  void dispose() {
    _run++;
    _out?.dispose();
    super.dispose();
  }
}
