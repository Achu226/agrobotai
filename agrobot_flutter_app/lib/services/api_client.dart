import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/foundation.dart' show defaultTargetPlatform;
import 'package:http/http.dart' as http;

import '../models/models.dart';

/// Why a request failed. The UI shows a specific message for each kind and never
/// substitutes a made-up result.
enum ApiErrorKind {
  serverUnreachable,
  timeout,
  unauthorized,
  forbidden,
  notFound,
  modelUnavailable,
  invalidImage,
  poorImageQuality,
  noLeafDetected,
  inferenceFailed,
  conflict,
  validation,
  server,
}

class ApiException implements Exception {
  ApiException(this.kind, this.message, {this.statusCode, this.code, this.details});

  final ApiErrorKind kind;
  final String message;
  final int? statusCode;
  final String? code;
  final Map<String, dynamic>? details;

  @override
  String toString() => message;
}

/// Client for the AGROBOTAI laptop server (FastAPI, /api/v1).
///
/// Phones must use the laptop's LAN address (e.g. http://192.168.1.20:8000) — never
/// localhost/127.0.0.1, which point at the phone itself. The Android emulator reaches the
/// laptop at http://10.0.2.2:8000.
class AgrobotApi {
  AgrobotApi(String baseUrl, {this.token, http.Client? client, this.analyzeTimeout = const Duration(seconds: 180)})
      : baseUrl = normalizeBaseUrl(baseUrl),
        _client = client ?? http.Client();

  final String baseUrl;
  final String? token;
  final http.Client _client;
  final Duration analyzeTimeout;
  static const _shortTimeout = Duration(seconds: 12);

  static const emulatorBaseUrl = 'http://10.0.2.2:8000';

  /// Build-time override: flutter build apk --dart-define=AGROBOT_SERVER_URL=http://192.168.1.20:8000
  static const configuredBaseUrl = String.fromEnvironment('AGROBOT_SERVER_URL', defaultValue: emulatorBaseUrl);

  static String normalizeBaseUrl(String url) {
    var u = url.trim();
    if (u.isEmpty) return configuredBaseUrl;
    if (!u.startsWith('http://') && !u.startsWith('https://')) u = 'http://$u';
    while (u.endsWith('/')) {
      u = u.substring(0, u.length - 1);
    }
    return u;
  }

  /// Returns a warning when the URL cannot work from a physical phone.
  static String? urlWarning(String url) {
    final host = Uri.tryParse(normalizeBaseUrl(url))?.host ?? '';
    if (host == 'localhost' || host == '127.0.0.1') {
      return 'localhost/127.0.0.1 is the phone itself: it only reaches the laptop over a USB cable (start.bat sets '
          'that up when the phone is plugged in). For Wi-Fi, use the laptop\'s address printed by start.bat.';
    }
    return null;
  }

  AgrobotApi withToken(String? newToken) => AgrobotApi(baseUrl, token: newToken, client: _client, analyzeTimeout: analyzeTimeout);

  Uri _uri(String path, [Map<String, String>? query]) => Uri.parse('$baseUrl$path').replace(queryParameters: query);

  // X-Client tells the administrator which device a login came from (ASCII only: it is an HTTP header)
  Map<String, String> get _authHeaders =>
      {'X-Client': 'AGROBOTAI app / ${defaultTargetPlatform.name}', if (token != null) 'Authorization': 'Bearer $token'};

  Future<http.Response> _send(Future<http.Response> Function() request, Duration timeout) async {
    try {
      return await request().timeout(timeout);
    } on TimeoutException {
      throw ApiException(
          ApiErrorKind.timeout,
          'The server at $baseUrl did not answer within ${timeout.inSeconds} s. Check that start.bat is running on the '
          'laptop and both devices are on the same Wi-Fi — or the server is busy; try again.');
    } on http.ClientException catch (e) {
      throw ApiException(
          ApiErrorKind.serverUnreachable,
          'Cannot reach the AGROBOTAI server at $baseUrl. Check that start.bat is running on the laptop, '
          'both devices are on the same Wi-Fi, and the firewall allows port ${Uri.parse(baseUrl).port}. (${e.message})');
    }
  }

  Map<String, dynamic> _decode(http.Response res) {
    Map<String, dynamic> body = {};
    final text = utf8.decode(res.bodyBytes, allowMalformed: true);
    if (text.isNotEmpty) {
      try {
        final decoded = jsonDecode(text);
        if (decoded is Map<String, dynamic>) body = decoded;
      } on FormatException {
        if (res.statusCode < 400) {
          throw ApiException(ApiErrorKind.server, 'The server sent an unreadable response.', statusCode: res.statusCode);
        }
      }
    }
    if (res.statusCode < 400) return body;

    final error = body['error'] is Map<String, dynamic> ? body['error'] as Map<String, dynamic> : null;
    final code = error?['code'] as String?;
    final detail = body['detail'];
    final message = detail is String ? detail : (error?['message'] as String? ?? 'Server error ${res.statusCode}');
    final kind = switch ((res.statusCode, code)) {
      (401, _) => ApiErrorKind.unauthorized,
      (403, _) => ApiErrorKind.forbidden,
      (404, _) => ApiErrorKind.notFound,
      (409, _) => ApiErrorKind.conflict,
      (503, _) => ApiErrorKind.modelUnavailable,
      (422, 'poor_image_quality') => ApiErrorKind.poorImageQuality,
      (422, 'no_leaf_detected') => ApiErrorKind.noLeafDetected,
      (400 || 413 || 415, _) => ApiErrorKind.invalidImage,
      (422, _) => ApiErrorKind.validation,
      (500, 'inference_failed') => ApiErrorKind.inferenceFailed,
      _ => ApiErrorKind.server,
    };
    throw ApiException(kind, message, statusCode: res.statusCode, code: code, details: error);
  }

  Future<Map<String, dynamic>> _getJson(String path, {Map<String, String>? query, Duration? timeout}) async =>
      _decode(await _send(() => _client.get(_uri(path, query), headers: _authHeaders), timeout ?? _shortTimeout));

  Future<Map<String, dynamic>> _postJson(String path, Map<String, dynamic> body, {Duration? timeout}) async => _decode(await _send(
      () => _client.post(_uri(path), headers: {..._authHeaders, 'Content-Type': 'application/json'}, body: jsonEncode(body)),
      timeout ?? _shortTimeout));

  /// Advice and chat are written by the laptop's local AI; Indian-language answers can take a minute or more.
  static const advisorTimeout = Duration(seconds: 240);

  Future<Uint8List> _getBytes(String path) async {
    final res = await _send(() => _client.get(_uri(path), headers: _authHeaders), const Duration(seconds: 60));
    if (res.statusCode >= 400) _decode(res);
    return res.bodyBytes;
  }

  // ------------------------------------------------------------ health & auth

  Future<ServerHealth> health({Duration? timeout}) async => ServerHealth.fromJson(await _getJson('/health', timeout: timeout));

  Future<Map<String, dynamic>> modelsStatus() => _getJson('/models/status');

  Future<AuthSession> login(String username, String password) async =>
      AuthSession.fromJson(await _postJson('/api/v1/auth/login', {'username': username.trim(), 'password': password}));

  Future<AuthSession> register(
          {required String username, required String password, String fullName = '', String farmName = '', String location = ''}) async =>
      AuthSession.fromJson(await _postJson('/api/v1/auth/register', {
        'username': username.trim(),
        'password': password,
        'full_name': fullName.trim(),
        'farm_name': farmName.trim(),
        'location': location.trim(),
      }));

  Future<AppUser> me() async => AppUser.fromJson((await _getJson('/api/v1/auth/me'))['user'] as Map<String, dynamic>);

  Future<void> logout() async => _postJson('/api/v1/auth/logout', {});

  // ------------------------------------------------------------ inference

  /// Sends a captured photo for full analysis. [clientRequestId] makes retries idempotent:
  /// the server returns the already-saved scan instead of creating a duplicate.
  Future<AnalyzeResponse> analyze(
    Uint8List imageBytes, {
    required String clientRequestId,
    String filename = 'leaf.jpg',
    String? crop,
    String? plot,
    DateTime? capturedAt,
    bool includeAdvice = false,
    String language = 'ta',
  }) async {
    final req = http.MultipartRequest('POST', _uri('/api/v1/analyze'))
      ..headers.addAll(_authHeaders)
      ..fields['client_request_id'] = clientRequestId
      ..fields['include_advice'] = includeAdvice.toString()
      ..fields['language'] = language
      ..fields['crop'] = crop ?? ''
      ..fields['plot'] = plot ?? ''
      ..fields['captured_at'] = capturedAt?.toIso8601String() ?? ''
      ..files.add(http.MultipartFile.fromBytes('file', imageBytes, filename: filename));
    final res = await _send(() async => http.Response.fromStream(await _client.send(req)), analyzeTimeout);
    return AnalyzeResponse.fromJson(_decode(res));
  }

  // ------------------------------------------------------------ scans & reviews

  /// Recovery tracking: the user's scans grouped by plot / plant name (oldest first in each plot).
  Future<List<Map<String, dynamic>>> plots() async =>
      ((await _getJson('/api/v1/plots'))['plots'] as List<dynamic>? ?? const []).cast<Map<String, dynamic>>();

  /// Field alerts computed by the laptop from the latest live sensor readings.
  /// Home-screen summary: spraying now, reminders due today, alerts, last 7 days.
  Future<Map<String, dynamic>> today() => _getJson('/api/v1/today', timeout: const Duration(seconds: 25));

  Future<List<Map<String, dynamic>>> alerts() async =>
      ((await _getJson('/api/v1/alerts'))['alerts'] as List<dynamic>? ?? const []).cast<Map<String, dynamic>>();

  Future<List<ScanRecord>> scans({String? reviewStatus, bool includeFailed = false, int limit = 100}) async {
    final body = await _getJson('/api/v1/scans', query: {
      'limit': '$limit',
      if (reviewStatus != null) 'review_status': reviewStatus,
      if (includeFailed) 'include_failed': 'true',
    });
    return (body['scans'] as List<dynamic>).map((e) => ScanRecord.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<ScanRecord> scan(int id) async => ScanRecord.fromJson((await _getJson('/api/v1/scans/$id'))['scan'] as Map<String, dynamic>);

  Future<Uint8List> scanImage(int id) => _getBytes('/api/v1/scans/$id/image');

  /// The user's own records ('diary' or 'scans') as a CSV file for Excel.
  Future<Uint8List> exportCsv(String what) => _getBytes('/api/v1/export.csv?what=$what');

  Future<Uint8List> reportPdf(int id) => _getBytes('/api/v1/scans/$id/report.pdf');

  /// Advice card for a scan in [language]; the server caches one card per language.
  Future<Map<String, dynamic>> scanAdvice(int id, {required String language, bool refresh = false}) async {
    final advice =
        (await _postJson('/api/v1/scans/$id/advice', {'language': language, 'refresh': refresh}, timeout: advisorTimeout))['advice'];
    if (advice is! Map<String, dynamic>) throw ApiException(ApiErrorKind.server, 'The server sent no advice for this scan.');
    return advice;
  }

  // ------------------------------------------------------------ languages & chat

  Future<List<Map<String, dynamic>>> languages() async =>
      ((await _getJson('/api/v1/languages'))['languages'] as List<dynamic>).cast<Map<String, dynamic>>();

  /// Asks the farm advisor. [history] holds earlier turns as {'role': 'user'|'assistant', 'content': ...}.
  Future<Map<String, dynamic>> chat(String message,
          {required String language, List<Map<String, String>> history = const [], int? scanId}) =>
      _postJson('/api/v1/chat', {'message': message, 'language': language, 'history': history, if (scanId != null) 'scan_id': scanId},
          timeout: advisorTimeout);

  /// Streams the advisor's answer as it is written. Yields the server's events:
  /// {'type':'start', 'context':{scan_id, crop, label}|null, ...}, {'type':'delta','text':...}..., {'type':'done',...}.
  /// A server-side failure arrives as an ApiException (kind modelUnavailable when the LLM is offline).
  Stream<Map<String, dynamic>> chatStream(String message,
      {required String language, List<Map<String, String>> history = const [], int? scanId, bool useLatestScan = true}) async* {
    final req = http.Request('POST', _uri('/api/v1/chat/stream'))
      ..headers.addAll({..._authHeaders, 'Content-Type': 'application/json'})
      ..body = jsonEncode({
        'message': message,
        'language': language,
        'history': history,
        'use_latest_scan': useLatestScan,
        if (scanId != null) 'scan_id': scanId,
      });
    final http.StreamedResponse res;
    try {
      res = await _client.send(req).timeout(const Duration(seconds: 30));
    } on TimeoutException {
      throw ApiException(ApiErrorKind.timeout, 'The laptop did not start answering within 30 s. Try again.');
    } on http.ClientException catch (e) {
      throw ApiException(ApiErrorKind.serverUnreachable, 'Cannot reach the AGROBOTAI server at $baseUrl. (${e.message})');
    }
    if (res.statusCode >= 400) {
      _decode(await http.Response.fromStream(res));
    }
    final lines = res.stream.transform(utf8.decoder).transform(const LineSplitter()).timeout(advisorTimeout);
    try {
      await for (final line in lines) {
        if (line.trim().isEmpty) continue;
        final event = jsonDecode(line) as Map<String, dynamic>;
        if (event['type'] == 'error') {
          throw ApiException(event['code'] == 'advisor_unavailable' ? ApiErrorKind.modelUnavailable : ApiErrorKind.server,
              '${event['detail'] ?? 'The AI advisor failed.'}',
              code: event['code'] as String?);
        }
        yield event;
      }
    } on TimeoutException {
      throw ApiException(ApiErrorKind.timeout, 'The answer stopped arriving. Try again.');
    } on http.ClientException catch (e) {
      throw ApiException(ApiErrorKind.serverUnreachable, 'Connection to the laptop was lost. (${e.message})');
    }
  }

  // ------------------------------------------------------------ voice (runs on the laptop)

  Future<Map<String, dynamic>> voiceStatus() => _getJson('/api/v1/voice/status');

  /// Spoken question (16-bit PCM WAV) -> text. [language] 'auto' lets Whisper detect it.
  Future<Map<String, dynamic>> transcribe(Uint8List wav, {String language = 'auto'}) async {
    final req = http.MultipartRequest('POST', _uri('/api/v1/voice/transcribe'))
      ..headers.addAll(_authHeaders)
      ..fields['language'] = language
      ..files.add(http.MultipartFile.fromBytes('file', wav, filename: 'question.wav'));
    return _decode(await _send(() async => http.Response.fromStream(await _client.send(req)), const Duration(seconds: 90)));
  }

  /// Text read aloud by the laptop. Returns (audio bytes, mime type, engine description).
  Future<(Uint8List, String, String)> speak(String text, {required String language, String engine = 'local'}) async {
    final res = await _send(
        () => _client.post(_uri('/api/v1/voice/speak'),
            headers: {..._authHeaders, 'Content-Type': 'application/json'},
            body: jsonEncode({'text': text, 'language': language, 'engine': engine})),
        const Duration(seconds: 90));
    if (res.statusCode >= 400) _decode(res);
    return (res.bodyBytes, res.headers['content-type'] ?? 'audio/wav', res.headers['x-voice-engine'] ?? '');
  }

  /// Spray quantities for the confirmed finding of a scan (reference table only).
  Future<Map<String, dynamic>> dosage(int scanId, {double acres = 1, double tankLiters = 15}) =>
      _getJson('/api/v1/dosage', query: {'scan_id': '$scanId', 'acres': '$acres', 'tank_liters': '$tankLiters'});

  Future<ScanRecord> review(int id, {required bool approve, String comment = ''}) async => ScanRecord.fromJson(
      (await _postJson('/api/v1/scans/$id/review', {'decision': approve ? 'approved' : 'rejected', 'comment': comment}))['scan']
          as Map<String, dynamic>);

  Future<List<AppUser>> adminUsers() async =>
      ((await _getJson('/api/v1/admin/users'))['users'] as List<dynamic>).map((e) => AppUser.fromJson(e as Map<String, dynamic>)).toList();

  Future<Map<String, dynamic>> adminStats() => _getJson('/api/v1/admin/stats');

  // ------------------------------------------------------------ weather & sensors

  /// Watering advice from live soil moisture + rain forecast (`location` empty = the account's farm location).
  Future<Map<String, dynamic>> irrigation(String location) => _getJson('/api/v1/irrigation', query: {'location': location});

  /// Safe spraying hours in the next 24 h from the real hourly forecast.
  Future<Map<String, dynamic>> sprayPlan(String location) => _getJson('/api/v1/spray-plan', query: {'location': location});

  /// Today's published mandi prices (Agmarknet via data.gov.in) for one commodity.
  Future<Map<String, dynamic>> marketPrices(String commodity, {String state = 'Tamil Nadu'}) =>
      _getJson('/api/v1/market-prices', query: {'commodity': commodity, 'state': state}, timeout: const Duration(seconds: 25));

  /// Bags of Urea / DAP / MOP for an N-P-K recommendation (kg per acre or per hectare) on [acres].
  Future<Map<String, dynamic>> fertilizer({required double n, required double p2o5, required double k2o, required double acres, String dosePer = 'acre'}) =>
      _getJson('/api/v1/fertilizer', query: {'n': '$n', 'p2o5': '$p2o5', 'k2o': '$k2o', 'acres': '$acres', 'dose_per': dosePer});

  /// Confirmed diseases and pests other farmers found in the user's village (counts only).
  Future<Map<String, dynamic>> nearbyOutbreaks() => _getJson('/api/v1/outbreaks/nearby');

  // ------------------------------------------------------------ disease & pest library

  Future<List<Map<String, dynamic>>> library(String language) async =>
      ((await _getJson('/api/v1/library', query: {'language': language}))['entries'] as List<dynamic>? ?? const [])
          .cast<Map<String, dynamic>>();

  /// One entry; the laptop AI translates it on first use, so this can take a while.
  Future<Map<String, dynamic>> libraryEntry(String key, String language) async =>
      (await _getJson('/api/v1/library/$key', query: {'language': language}, timeout: advisorTimeout))['entry']
          as Map<String, dynamic>;

  // ------------------------------------------------------------ farm diary

  Future<List<Map<String, dynamic>>> diary({String? plot}) async =>
      ((await _getJson('/api/v1/diary', query: {if (plot != null) 'plot': plot}))['entries'] as List<dynamic>? ?? const [])
          .cast<Map<String, dynamic>>();

  Future<Map<String, dynamic>> addDiaryEntry(Map<String, dynamic> entry) async =>
      (await _postJson('/api/v1/diary', entry))['entry'] as Map<String, dynamic>;

  Future<void> deleteDiaryEntry(int id) async =>
      _decode(await _send(() => _client.delete(_uri('/api/v1/diary/$id'), headers: _authHeaders), _shortTimeout));

  Future<Map<String, dynamic>> weather(String location, {String crop = 'Tomato', String? detectedDisease}) => _getJson('/api/v1/weather',
      query: {'location': location, 'crop': crop, if (detectedDisease != null) 'detected_disease': detectedDisease});

  Future<Map<String, dynamic>> sensorStatus() => _getJson('/api/v1/sensors/status');

  /// Real health of the machine running the server (Raspberry Pi temperature, power, storage).
  Future<Map<String, dynamic>> deviceStatus() => _getJson('/api/v1/device/status');

  /// Admin only: safe power-off of the Raspberry Pi server.
  Future<Map<String, dynamic>> shutdownDevice() => _postJson('/api/v1/device/shutdown', const {});

  Future<List<Map<String, dynamic>>> sensorHistory(String deviceId, {int hours = 24}) async =>
      ((await _getJson('/api/v1/sensors/history', query: {'device_id': deviceId, 'hours': '$hours'}))['readings'] as List<dynamic>)
          .cast<Map<String, dynamic>>();

  /// Decodes a `data:image/...;base64,...` URL returned by the API.
  static Uint8List? decodeDataUrl(Object? dataUrl) {
    if (dataUrl is! String || !dataUrl.contains(',')) return null;
    try {
      return base64Decode(dataUrl.substring(dataUrl.indexOf(',') + 1));
    } on FormatException {
      return null;
    }
  }
}
