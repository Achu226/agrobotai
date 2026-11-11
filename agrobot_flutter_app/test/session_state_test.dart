import 'package:agrobot_flutter_app/state/session_state.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import 'fakes.dart';

Map<String, dynamic> authJson(String role) => {
      'token': 'secret-token-$role',
      'expires_at': '2026-11-20T00:00:00+00:00',
      'user': {'id': 1, 'username': 'ravi', 'role': role, 'full_name': 'Ravi Kumar', 'farm_name': '', 'location': 'Salem'},
    };

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('session and server URL survive an app restart', () async {
    final server = RecordingClient((_) => jsonResponse(authJson('farmer')));
    final s1 = await SessionState.load(httpClient: server.client);
    await s1.setServerUrl('192.168.1.20:8000');
    await s1.signIn('ravi', 'pw-123456');
    await s1.recordSuccess();

    final s2 = await SessionState.load(httpClient: server.client); // "restart"
    expect(s2.isSignedIn, isTrue);
    expect(s2.user!.username, 'ravi');
    expect(s2.serverUrl, 'http://192.168.1.20:8000');
    expect(s2.lastSuccessAt, isNotNull);
    expect(s2.api.token, 'secret-token-farmer');
  });

  test('changing the server signs out so a token is never sent to another server', () async {
    final s = await SessionState.load(httpClient: RecordingClient((_) => jsonResponse(authJson('farmer'))).client);
    await s.signIn('ravi', 'pw-123456');
    await s.setServerUrl('http://10.0.0.9:8000');
    expect(s.isSignedIn, isFalse);
    expect(s.signedOutReason, contains('Server changed'));
  });

  test('sign-out clears the local session even when the server is unreachable', () async {
    var reachable = true;
    final s = await SessionState.load(
        httpClient: RecordingClient((_) {
      if (!reachable) throw http.ClientException('offline');
      return jsonResponse(authJson('admin'));
    }).client);
    await s.signIn('ravi', 'pw-123456');
    reachable = false;
    await s.signOut();
    expect(s.isSignedIn, isFalse);
    expect((await SessionState.load()).isSignedIn, isFalse);
  });

  test('revoked session found on startup signs out', () async {
    var revoked = false;
    final s = await SessionState.load(
        httpClient: RecordingClient((r) {
      if (revoked) return jsonResponse({'detail': 'Session expired or invalid. Please sign in again.'}, 401);
      return jsonResponse(authJson('farmer'));
    }).client);
    await s.signIn('ravi', 'pw-123456');
    revoked = true;
    await s.refreshUser();
    expect(s.isSignedIn, isFalse);
    expect(s.signedOutReason, contains('Session expired'));
  });

  test('server unreachable is recorded by the health check', () async {
    final s = await SessionState.load(httpClient: RecordingClient((_) => throw http.ClientException('refused')).client);
    final h = await s.checkHealth();
    expect(h, isNull);
    expect(s.healthError, contains('Cannot reach'));
  });

  test('diagnostics never contain the session token', () async {
    final s = await SessionState.load(httpClient: RecordingClient((_) => jsonResponse(authJson('farmer'))).client);
    await s.signIn('ravi', 'pw-123456');
    final report = s.diagnosticsReport();
    expect(report, contains('ravi (farmer)'));
    expect(report, isNot(contains('secret-token')));
  });

  group('finding the laptop on the Wi-Fi', () {
    final healthJson = {
      'ok': true,
      'service': 'AGROBOTAI inference server',
      'runtime': {'inference_device': 'cuda'},
      'models': {
        'disease': {'ready': true, 'state': 'ready'},
        'pest': {'ready': true, 'state': 'ready'},
      },
    };

    test('switches to the discovered server when the saved address does not answer', () async {
      final calls = <int>[];
      final s = await SessionState.load(
        httpClient: RecordingClient((r) {
          if (r.url.host == '192.168.1.14') return jsonResponse(healthJson);
          throw http.ClientException('no route to host'); // e.g. 10.0.2.2 on a real phone
        }).client,
        findServer: ({int port = 8000, String? preferHost}) async {
          calls.add(port);
          return 'http://192.168.1.14:$port';
        },
      );
      await s.connect();
      expect(calls, [8000]);
      expect(s.serverUrl, 'http://192.168.1.14:8000');
      expect(s.health, isNotNull);
      expect(s.discoveryMessage, contains('Found'));
      expect(s.discovering, isFalse);
    });

    test('keeps a saved server that answers and does not scan', () async {
      var scanned = false;
      final s = await SessionState.load(
        httpClient: RecordingClient((_) => jsonResponse(healthJson)).client,
        findServer: ({int port = 8000, String? preferHost}) async {
          scanned = true;
          return null;
        },
      );
      await s.setServerUrl('192.168.1.20:8000');
      await s.connect();
      expect(scanned, isFalse);
      expect(s.serverUrl, 'http://192.168.1.20:8000');
      expect(s.health, isNotNull);
    });

    test('explains what to check when no server is found', () async {
      final s = await SessionState.load(
          httpClient: RecordingClient((_) => throw http.ClientException('refused')).client, findServer: noServerOnWifi);
      await s.connect();
      expect(s.health, isNull);
      expect(s.discoveryMessage, contains('start.bat'));
    });
  });
}
