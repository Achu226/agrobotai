import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:path_provider/path_provider.dart';

import 'api_client.dart';

/// Photos captured while the laptop was unreachable, kept on the phone until they can be analysed.
/// Each keeps its original client request id, so an upload that already reached the server is
/// returned as the existing scan instead of a duplicate.
class ScanQueue {
  ScanQueue({Future<Directory> Function()? baseDir}) : _baseDir = baseDir ?? getApplicationDocumentsDirectory;

  final Future<Directory> Function() _baseDir;
  bool _flushing = false;

  Future<Directory> _root() async => Directory('${(await _baseDir()).path}${Platform.pathSeparator}scan_queue');

  Future<void> save(Uint8List photo,
      {List<Uint8List> extraImages = const [], required String clientRequestId, String? crop, String? plot, DateTime? capturedAt}) async {
    final dir = Directory('${(await _root()).path}${Platform.pathSeparator}$clientRequestId');
    await dir.create(recursive: true);
    await File('${dir.path}${Platform.pathSeparator}photo.jpg').writeAsBytes(photo, flush: true);
    for (var i = 0; i < extraImages.length; i++) {
      await File('${dir.path}${Platform.pathSeparator}photo${i + 2}.jpg').writeAsBytes(extraImages[i], flush: true);
    }
    // meta.json last: an item counts as queued only once it is complete
    await File('${dir.path}${Platform.pathSeparator}meta.json').writeAsString(jsonEncode({
      'client_request_id': clientRequestId,
      'crop': crop,
      'plot': plot,
      'captured_at': capturedAt?.toIso8601String(),
    }), flush: true);
  }

  Future<List<Directory>> _items() async {
    final root = await _root();
    if (!await root.exists()) return [];
    final dirs = [
      for (final e in await root.list().toList())
        if (e is Directory && await File('${e.path}${Platform.pathSeparator}meta.json').exists()) e
    ];
    dirs.sort((a, b) => a.statSync().modified.compareTo(b.statSync().modified));
    return dirs;
  }

  Future<int> count() async {
    try {
      return (await _items()).length;
    } catch (_) {
      return 0; // storage not available (e.g. widget tests)
    }
  }

  /// Uploads queued photos oldest first. Stops at the first connection problem (the rest stay
  /// queued); a photo the server rejects as unusable is removed and its reason returned.
  Future<({int uploaded, List<String> rejected})> flush(AgrobotApi api, {String language = 'ta'}) async {
    var uploaded = 0;
    final rejected = <String>[];
    if (_flushing) return (uploaded: 0, rejected: rejected);
    _flushing = true;
    try {
      for (final dir in await _items()) {
        final meta = jsonDecode(await File('${dir.path}${Platform.pathSeparator}meta.json').readAsString()) as Map<String, dynamic>;
        final photo = await File('${dir.path}${Platform.pathSeparator}photo.jpg').readAsBytes();
        final extras = [
          for (final n in [2, 3])
            if (await File('${dir.path}${Platform.pathSeparator}photo$n.jpg').exists())
              await File('${dir.path}${Platform.pathSeparator}photo$n.jpg').readAsBytes()
        ];
        try {
          await api.analyze(photo,
              extraImages: extras,
              clientRequestId: meta['client_request_id'] as String,
              crop: meta['crop'] as String?,
              plot: meta['plot'] as String?,
              capturedAt: DateTime.tryParse('${meta['captured_at']}'),
              language: language);
          uploaded++;
        } on ApiException catch (e) {
          final permanent = {ApiErrorKind.poorImageQuality, ApiErrorKind.noLeafDetected, ApiErrorKind.invalidImage, ApiErrorKind.validation};
          if (!permanent.contains(e.kind)) break; // unreachable, signed out, model loading...: retry later
          rejected.add(e.message);
        }
        await dir.delete(recursive: true);
      }
    } on FileSystemException {
      // storage problem: keep whatever is left for the next attempt
    } finally {
      _flushing = false;
    }
    return (uploaded: uploaded, rejected: rejected);
  }
}
