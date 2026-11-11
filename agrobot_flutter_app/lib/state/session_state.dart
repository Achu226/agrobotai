import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../models/models.dart';
import '../services/api_client.dart';
import '../services/scan_queue.dart';
import '../services/server_discovery.dart';

/// Looks for the AGROBOTAI server on the local network; returns its base URL or null.
typedef ServerFinder = Future<String?> Function({int port, String? preferHost});

/// Signed-in user, server address and server health. Persisted with shared_preferences so
/// the session survives app restarts; the server remains the source of truth for roles.
class SessionState extends ChangeNotifier {
  SessionState(this._prefs, {http.Client? httpClient, ServerFinder? findServer, ScanQueue? queue})
      : _httpClient = httpClient,
        _findServer = findServer ?? discoverAgrobotServer,
        queue = queue ?? ScanQueue() {
    serverUrl = AgrobotApi.normalizeBaseUrl(_prefs.getString(_kServer) ?? AgrobotApi.configuredBaseUrl);
    _token = _prefs.getString(_kToken);
    final userJson = _prefs.getString(_kUser);
    if (_token != null && userJson != null) {
      user = AppUser.fromJson(jsonDecode(userJson) as Map<String, dynamic>);
    }
    final last = _prefs.getString(_kLastSuccess);
    lastSuccessAt = last != null ? DateTime.tryParse(last) : null;
    language = _prefs.getString(_kLanguage) ?? 'ta';
    voiceEngine = _prefs.getString(_kVoiceEngine) ?? 'local';
    autoRead = _prefs.getBool(_kAutoRead) ?? false;
    gardenMode = _prefs.getBool(_kGarden) ?? false;
  }

  static Future<SessionState> load({http.Client? httpClient, ServerFinder? findServer, ScanQueue? queue}) async =>
      SessionState(await SharedPreferences.getInstance(), httpClient: httpClient, findServer: findServer, queue: queue);

  static const _kServer = 'server_url';
  static const _kToken = 'session_token';
  static const _kUser = 'session_user';
  static const _kLastSuccess = 'last_success_at';
  static const _kLanguage = 'advice_language';
  static const _kVoiceEngine = 'voice_engine';
  static const _kAutoRead = 'voice_auto_read';
  static const _kGarden = 'garden_mode';

  final SharedPreferences _prefs;
  final http.Client? _httpClient;
  final ServerFinder _findServer;
  Future<void>? _connecting;

  late String serverUrl;

  /// Language for advice and chat (one of kLanguages); Tamil by default.
  late String language;

  /// 'local' = voices running on the laptop (offline); 'online' = Microsoft neural voices (internet);
  /// 'auto' = online when available, else local.
  late String voiceEngine;

  /// Read every chat answer aloud as soon as it is complete.
  late bool autoRead;

  /// Home-garden mode (pots, terrace): doses per litre, and farm-only tools (market prices, fertilizer bags) hidden.
  late bool gardenMode;
  String? _token;
  AppUser? user;
  ServerHealth? health;
  String? healthError;
  DateTime? healthCheckedAt;
  DateTime? lastSuccessAt;
  bool checkingHealth = false;
  bool discovering = false;
  String? discoveryMessage;
  String? signedOutReason;

  bool get isSignedIn => _token != null && user != null;
  AgrobotApi get api => AgrobotApi(serverUrl, token: _token, client: _httpClient);

  Future<void> setServerUrl(String url) async {
    final normalized = AgrobotApi.normalizeBaseUrl(url);
    if (normalized != serverUrl && isSignedIn) {
      // A session token belongs to one server; never send it to a different one
      await _clearSession('Server changed — please sign in to the new server.');
    }
    serverUrl = normalized;
    await _prefs.setString(_kServer, serverUrl);
    health = null;
    healthError = null;
    notifyListeners();
  }

  Future<void> setLanguage(String code) async {
    language = code;
    await _prefs.setString(_kLanguage, code);
    notifyListeners();
  }

  Future<void> setVoiceEngine(String engine) async {
    voiceEngine = engine;
    await _prefs.setString(_kVoiceEngine, engine);
    notifyListeners();
  }

  Future<void> setGardenMode(bool value) async {
    gardenMode = value;
    await _prefs.setBool(_kGarden, value);
    notifyListeners();
  }

  Future<void> setAutoRead(bool value) async {
    autoRead = value;
    await _prefs.setBool(_kAutoRead, value);
    notifyListeners();
  }

  Future<ServerHealth?> checkHealth({Duration? timeout}) async {
    checkingHealth = true;
    notifyListeners();
    try {
      health = await api.health(timeout: timeout);
      healthError = null;
    } on ApiException catch (e) {
      health = null;
      healthError = e.message;
    } finally {
      checkingHealth = false;
      healthCheckedAt = DateTime.now();
      notifyListeners();
    }
    return health;
  }

  /// Startup: try the saved server; if it does not answer (new Wi-Fi, laptop got a new IP, or the
  /// emulator-only default address on a real phone), search the Wi-Fi for it. Concurrent calls share one run.
  Future<void> connect() => _connecting ??= () async {
        try {
          if (await checkHealth(timeout: const Duration(seconds: 4)) == null) await findServer();
          if (health != null) unawaited(uploadQueued());
        } finally {
          _connecting = null;
        }
      }();

  /// Scans the phone's Wi-Fi for the AGROBOTAI laptop and switches to it when found.
  Future<bool> findServer() async {
    if (discovering) return false;
    discovering = true;
    discoveryMessage = null;
    notifyListeners();
    try {
      final current = Uri.tryParse(serverUrl);
      final port = (current != null && current.hasPort) ? current.port : 8000;
      final found = await _findServer(port: port, preferHost: current?.host);
      if (found == null) {
        discoveryMessage = 'No AGROBOTAI server found on this Wi-Fi (port $port). Check that start.bat is running on the '
            'laptop, both devices use the same Wi-Fi, and start.bat shows no firewall warning.';
        return false;
      }
      if (AgrobotApi.normalizeBaseUrl(found) != serverUrl) await setServerUrl(found);
      discoveryMessage = 'Found the AGROBOTAI server at $serverUrl';
      return await checkHealth() != null;
    } catch (e) {
      discoveryMessage = 'Searching the Wi-Fi failed: $e';
      return false;
    } finally {
      discovering = false;
      notifyListeners();
    }
  }

  Future<void> signIn(String username, String password) async => _adopt(await api.login(username, password));

  Future<void> register(
          {required String username, required String password, String fullName = '', String farmName = '', String location = ''}) async =>
      _adopt(await api.register(username: username, password: password, fullName: fullName, farmName: farmName, location: location));

  Future<void> _adopt(AuthSession session) async {
    _token = session.token;
    user = session.user;
    signedOutReason = null;
    await _prefs.setString(_kToken, session.token);
    await _prefs.setString(_kUser, jsonEncode(session.user.toJson()));
    notifyListeners();
  }

  /// Confirms the stored token with the server (role changes, revoked sessions).
  Future<void> refreshUser() async {
    if (!isSignedIn) return;
    try {
      user = await api.me();
      await _prefs.setString(_kUser, jsonEncode(user!.toJson()));
      notifyListeners();
    } on ApiException catch (e) {
      if (e.kind == ApiErrorKind.unauthorized) await _clearSession(e.message);
    }
  }

  Future<void> signOut() async {
    try {
      await api.logout();
    } on ApiException {
      // Server unreachable: the local session is still removed
    }
    await _clearSession(null);
  }

  /// Call when any request returns 401.
  Future<void> handleUnauthorized(ApiException e) async => _clearSession(e.message);

  Future<void> _clearSession(String? reason) async {
    _token = null;
    user = null;
    signedOutReason = reason;
    await _prefs.remove(_kToken);
    await _prefs.remove(_kUser);
    notifyListeners();
  }

  Future<void> recordSuccess() async {
    lastSuccessAt = DateTime.now();
    await _prefs.setString(_kLastSuccess, lastSuccessAt!.toIso8601String());
    notifyListeners();
    unawaited(uploadQueued()); // the laptop is reachable now
  }

  // ------------------------------------------------------------ offline scan queue

  final ScanQueue queue;

  /// Photos saved on this phone while the laptop was unreachable.
  int queuedScans = 0;
  bool uploadingQueue = false;

  Future<void> refreshQueue() async {
    queuedScans = await queue.count();
    notifyListeners();
  }

  /// Sends queued photos; returns how many were analysed and why any were rejected.
  Future<({int uploaded, List<String> rejected})> uploadQueued() async {
    if (!isSignedIn || uploadingQueue) return (uploaded: 0, rejected: <String>[]);
    uploadingQueue = true;
    notifyListeners();
    try {
      return await queue.flush(api, language: language);
    } catch (_) {
      return (uploaded: 0, rejected: <String>[]); // storage not available
    } finally {
      uploadingQueue = false;
      await refreshQueue();
    }
  }

  /// Text for the diagnostics screen. Never includes the session token.
  String diagnosticsReport() {
    final h = health;
    return [
      'AGROBOTAI diagnostics ${DateTime.now().toIso8601String()}',
      'Server URL: $serverUrl',
      'Signed in: ${isSignedIn ? '${user!.username} (${user!.role})' : 'no'}',
      'Health check: ${healthCheckedAt?.toIso8601String() ?? 'never'}',
      if (healthError != null) 'Health error: $healthError',
      if (h != null) ...[
        'Inference device: ${h.device}${h.gpu != null ? ' (${h.gpu})' : ''}',
        'Disease model: ${h.disease.state} ${h.disease.version ?? ''} ${h.disease.error ?? ''}'.trim(),
        'Pest model: ${h.pest.state} ${h.pest.version ?? ''} ${h.pest.error ?? ''}'.trim(),
      ],
      'Last successful analysis: ${lastSuccessAt?.toIso8601String() ?? 'none'}',
    ].join('\n');
  }
}
