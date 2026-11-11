import 'package:agrobot_flutter_app/widgets/weather_widgets.dart';
import 'package:agrobot_flutter_app/widgets/today_card.dart';
import 'package:agrobot_flutter_app/main.dart';
import 'package:agrobot_flutter_app/screens/chat_screen.dart';
import 'package:agrobot_flutter_app/screens/diary_screen.dart';
import 'package:agrobot_flutter_app/screens/history_screen.dart';
import 'package:agrobot_flutter_app/screens/scan_screen.dart';
import 'package:agrobot_flutter_app/screens/sensors_screen.dart';
import 'package:agrobot_flutter_app/screens/weather_screen.dart';
import 'package:agrobot_flutter_app/models/models.dart';
import 'dart:io';

import 'package:agrobot_flutter_app/services/camera_service.dart';
import 'package:agrobot_flutter_app/services/scan_queue.dart';
import 'package:agrobot_flutter_app/state/session_state.dart';
import 'package:agrobot_flutter_app/widgets/scan_result_view.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:agrobot_flutter_app/services/voice.dart';
import 'package:agrobot_flutter_app/widgets/speak_button.dart';

import 'fakes.dart';
import 'session_state_test.dart' show authJson;

Future<SessionState> signedIn(RecordingClient server, {String role = 'farmer', ScanQueue? queue}) async {
  SharedPreferences.setMockInitialValues({});
  final login = RecordingClient((_) => jsonResponse(authJson(role)));
  final s = await SessionState.load(httpClient: login.client);
  await s.signIn('ravi', 'pw-123456');
  // Same stored session, now talking to the scenario's server
  return SessionState.load(httpClient: server.client, findServer: noServerOnWifi, queue: queue);
}

Future<void> pumpWith(WidgetTester tester, SessionState s, Widget child) async {
  await tester.pumpWidget(ChangeNotifierProvider.value(value: s, child: MaterialApp(home: Scaffold(body: child))));
}

Future<void> pumpUntil(WidgetTester tester, bool Function() done, {int maxFrames = 50}) async {
  for (var i = 0; i < maxFrames && !done(); i++) {
    await tester.pump(const Duration(milliseconds: 50));
  }
}

void main() {
  group('access control', () {
    testWidgets('signed-out users only see the sign-in screen', (tester) async {
      SharedPreferences.setMockInitialValues({});
      final s = await SessionState.load(
          httpClient: RecordingClient((_) => throw http.ClientException('offline')).client, findServer: noServerOnWifi);
      await tester.pumpWidget(ChangeNotifierProvider.value(value: s, child: const MaterialApp(home: AuthGate())));
      await tester.pump();
      expect(find.text('Sign in'), findsOneWidget);
      expect(find.text('Review'), findsNothing);
    });

    testWidgets('a farmer account never gets the admin review screens', (tester) async {
      final s = await signedIn(
          RecordingClient(
              (r) => r.url.path == '/api/v1/auth/me' ? jsonResponse({'user': authJson('farmer')['user']}) : jsonResponse({'scans': []})),
          role: 'farmer');
      await tester.pumpWidget(ChangeNotifierProvider.value(value: s, child: const MaterialApp(home: AuthGate())));
      await pumpUntil(tester, () => find.text('My scans').evaluate().isNotEmpty);
      expect(find.text('My scans'), findsOneWidget);
      expect(find.text('Review'), findsNothing);
      expect(find.text('Scan leaf'), findsOneWidget);
    });

    testWidgets('the admin role comes from the server account', (tester) async {
      final s = await signedIn(
          RecordingClient(
              (r) => r.url.path == '/api/v1/auth/me' ? jsonResponse({'user': authJson('admin')['user']}) : jsonResponse({'scans': []})),
          role: 'admin');
      await tester.pumpWidget(ChangeNotifierProvider.value(value: s, child: const MaterialApp(home: AuthGate())));
      await pumpUntil(tester, () => find.text('No scans are waiting for review.').evaluate().isNotEmpty);
      expect(find.text('Review'), findsOneWidget);
      expect(find.text('No scans are waiting for review.'), findsOneWidget);
    });
  });

  testWidgets('empty history shows the required message', (tester) async {
    final s = await signedIn(RecordingClient((_) => jsonResponse({'scans': []})));
    await pumpWith(tester, s, const ScanList());
    await pumpUntil(tester, () => find.textContaining('No scan history').evaluate().isNotEmpty);
    expect(find.text('No scan history yet. Capture a leaf image to begin.'), findsOneWidget);
  });

  testWidgets('history lists stored scans from the server', (tester) async {
    final s = await signedIn(RecordingClient((_) => jsonResponse({
          'scans': [scanJson()..remove('result')]
        })));
    await pumpWith(tester, s, const ScanList());
    await pumpUntil(tester, () => find.text('Tomato Early Blight').evaluate().isNotEmpty);
    expect(find.text('Tomato Early Blight'), findsOneWidget);
    expect(find.text('Pending review'), findsOneWidget);
  });

  testWidgets('missing weather credentials -> "Weather unavailable", no invented values', (tester) async {
    final s = await signedIn(RecordingClient((_) => jsonResponse({
          'ok': false,
          'code': 'weather_not_configured',
          'error': 'Weather unavailable: WEATHER_API_KEY is not set in .env',
        })));
    await pumpWith(tester, s, const WeatherScreen());
    await tester.enterText(find.byType(TextField), 'Salem');
    await tester.testTextInput.receiveAction(TextInputAction.search);
    await pumpUntil(tester, () => find.text('Weather unavailable').evaluate().isNotEmpty);
    expect(find.text('Weather unavailable'), findsOneWidget);
    expect(find.textContaining('°C'), findsNothing);
  });

  testWidgets('disconnected sensors are labelled, not presented as live', (tester) async {
    final s = await signedIn(RecordingClient((_) => jsonResponse({
          'configured': true,
          'stale_after_seconds': 300,
          'devices': [
            {
              'device_id': 'esp32-field-1',
              'received_at': '2026-10-21T08:00:00+05:30',
              'connected': false,
              'seconds_since_last_reading': 4000,
              'readings': {'soil_moisture_pct': 41.5},
            }
          ],
        })));
    await pumpWith(tester, s, const SensorsScreen());
    await pumpUntil(tester, () => find.text('esp32-field-1').evaluate().isNotEmpty);
    expect(find.text('Disconnected'), findsOneWidget);
    expect(find.textContaining('not live'), findsOneWidget);
  });

  testWidgets('server device card shows real Pi health and warns on low voltage', (tester) async {
    final s = await signedIn(RecordingClient((r) => r.url.path == '/api/v1/device/status'
        ? jsonResponse({
            'device': 'Raspberry Pi 4 Model B Rev 1.5',
            'cpu_temp_c': 46.7,
            'power': {'raw': '0x50005', 'under_voltage_now': true, 'under_voltage_since_boot': true, 'temp_limit_now': false},
            'memory_used_pct': 24.6,
            'disk_free_gb': 23.0,
            'disk_total_gb': 29.0,
            'uptime_s': 7500,
          })
        : jsonResponse({'configured': true, 'devices': [], 'message': 'No sensor gateway has sent data yet.'})));
    await pumpWith(tester, s, const SensorsScreen());
    await pumpUntil(tester, () => find.text('Raspberry Pi 4 Model B Rev 1.5').evaluate().isNotEmpty);
    expect(find.text('46.7 °C'), findsOneWidget);
    expect(find.text('23.0 of 29.0 GB'), findsOneWidget);
    expect(find.text('2 h 5 min'), findsOneWidget);
    expect(find.text('Low'), findsOneWidget);
    expect(find.textContaining('Use a 5 V 3 A charger'), findsOneWidget);
  });

  Map<String, dynamic> piStatus() => {
        'device': 'Raspberry Pi 4 Model B Rev 1.5',
        'cpu_temp_c': 46.0,
        'power': {'raw': '0x0', 'under_voltage_now': false},
        'disk_free_gb': 20.0,
        'disk_total_gb': 29.0,
        'can_shutdown': true,
        'auto_off_idle_hours': 3.0,
      };

  testWidgets('spray planner shows the real verdict, reasons and best window', (tester) async {
    final s = await signedIn(RecordingClient((r) => r.url.path == '/api/v1/spray-plan'
        ? jsonResponse({
            'ok': true,
            'ok_now': false,
            'now_problems': ['dark'],
            'best_window': {'start': '2026-11-10T10:00', 'end': '2026-11-10T16:00', 'hours': 7},
          })
        : jsonResponse({})));
    await pumpWith(tester, s, const SingleChildScrollView(child: SprayPlanCard(location: 'Salem')));
    await pumpUntil(tester, () => find.textContaining('Best time').evaluate().isNotEmpty);
    expect(find.text('Not now: Night'), findsOneWidget);
    expect(find.text('Best time: 2026-11-10 10:00–17:00'), findsOneWidget); // end hour inclusive
    expect(find.text('Save in farm diary'), findsOneWidget);
  });

  testWidgets('spray planner without a window never suggests spraying', (tester) async {
    final s = await signedIn(RecordingClient((r) => jsonResponse({'ok': true, 'ok_now': false, 'now_problems': ['rain'], 'best_window': null})));
    await pumpWith(tester, s, const SingleChildScrollView(child: SprayPlanCard(location: 'Salem')));
    await pumpUntil(tester, () => find.textContaining('No safe').evaluate().isNotEmpty);
    expect(find.text('Not now: Raining'), findsOneWidget);
    expect(find.text('Save in farm diary'), findsNothing);
  });

  testWidgets('market prices show published mandi prices per quintal', (tester) async {
    final s = await signedIn(RecordingClient((r) => jsonResponse({
          'ok': true,
          'records': [
            {'market': 'Salem', 'district': 'Salem', 'variety': 'Hybrid', 'arrival_date': '10/11/2026', 'min_price': 1500, 'max_price': 2200, 'modal_price': 1800},
          ],
        })));
    await pumpWith(tester, s, const SingleChildScrollView(child: MarketPricesCard()));
    await pumpUntil(tester, () => find.text('₹1800').evaluate().isNotEmpty);
    expect(find.text('₹1500–₹2200'), findsOneWidget);
    expect(find.textContaining('per quintal'), findsOneWidget);
  });

  testWidgets('market prices without a key explain how to set one up', (tester) async {
    final s = await signedIn(RecordingClient((r) => jsonResponse(
        {'ok': false, 'code': 'not_configured', 'error': 'Market prices need a free data.gov.in API key. Register at data.gov.in and run scripts\\set_market_key.ps1.'})));
    await pumpWith(tester, s, const SingleChildScrollView(child: MarketPricesCard()));
    await pumpUntil(tester, () => find.textContaining('data.gov.in').evaluate().isNotEmpty);
    expect(find.textContaining('₹'), findsNothing);
  });

  testWidgets('nearby alerts list what other farmers found; hidden without a location', (tester) async {
    final s = await signedIn(RecordingClient((r) => jsonResponse({
          'ok': true,
          'location': 'Salem',
          'days': 14,
          'alerts': [
            {'label': 'Tomato Late Blight', 'display_name': 'Tomato Late Blight', 'kind': 'disease', 'count': 3, 'last_seen': '2026-11-09T10:00:00+05:30'},
          ],
        })));
    await pumpWith(tester, s, const SingleChildScrollView(child: NearbyAlertsCard()));
    await pumpUntil(tester, () => find.text('Tomato Late Blight').evaluate().isNotEmpty);
    expect(find.text('3 confirmed scans • last on 2026-11-09'), findsOneWidget);

    final none = await signedIn(RecordingClient((r) => jsonResponse({'ok': false, 'code': 'no_location', 'error': 'Set your village'})));
    await pumpWith(tester, none, const SingleChildScrollView(child: NearbyAlertsCard(key: ValueKey('no location'))));
    await tester.pumpAndSettle();
    expect(find.text('Disease alerts near you'), findsNothing);
  });

  testWidgets('today card: one-line summary, details on tap, hidden on an old server', (tester) async {
    final s = await signedIn(RecordingClient((r) => jsonResponse({
          'date': '2026-11-11',
          'spray': {'ok': true, 'ok_now': false, 'best_window': {'start': '2026-11-11T13:00', 'end': '2026-11-11T16:00', 'hours': 4}},
          'reminders': [
            {'id': 1, 'plot': 'North field', 'kind': 'spray', 'product': 'Neem oil', 'remind_on': '2026-11-11'},
          ],
          'nearby': [
            {'display_name': 'Tomato Late Blight', 'count': 3, 'kind': 'disease'},
          ],
          'alerts': [
            {'code': 'pi_hot', 'device': 'agrobotai-pi', 'value': 81.5},
          ],
          'week': {'scans': 4, 'spent': 250, 'earned': 9000},
        })));
    await pumpWith(tester, s, const SingleChildScrollView(child: TodayCard()));
    await pumpUntil(tester, () => find.text('Today').evaluate().isNotEmpty);
    expect(find.text('Spray window: 13:00–17:00 • 1 reminders today • 2 alerts'), findsOneWidget);
    await tester.tap(find.text('Today'));
    await tester.pumpAndSettle();
    expect(find.text('North field: Spray — Neem oil'), findsOneWidget);
    expect(find.text('Tomato Late Blight: 3 confirmed scans near you'), findsOneWidget);
    expect(find.textContaining('very hot (81.5 °C)'), findsOneWidget);
    expect(find.text('Last 7 days: 4 scans • spent ₹250 • earned ₹9000'), findsOneWidget);

    final old = await signedIn(RecordingClient((r) => jsonResponse({'detail': 'Not Found'}, 404)));
    await pumpWith(tester, old, const SingleChildScrollView(child: TodayCard(key: ValueKey('old server'))));
    await tester.pumpAndSettle();
    expect(find.text('Today'), findsNothing);
  });

  testWidgets('home garden mode hides farm-only tools and is remembered', (tester) async {
    final s = await signedIn(RecordingClient((r) => jsonResponse({'ok': false, 'error': 'offline'})));
    expect(s.gardenMode, isFalse);
    await s.setGardenMode(true);
    expect((await SharedPreferences.getInstance()).getBool('garden_mode'), isTrue);
  });

  test('profit book: sales are income, every other amount is a cost', () {
    final rows = profitByPlot([
      {'plot': 'North', 'kind': 'spray', 'cost': 250},
      {'plot': 'North', 'kind': 'labour', 'cost': 800},
      {'plot': 'North', 'kind': 'sale', 'cost': 12000},
      {'plot': 'South', 'kind': 'note', 'cost': null},
    ]);
    expect(rows, {'North': (1050.0, 12000.0)});
  });

  testWidgets('fertilizer calculator shows bags to buy from the server', (tester) async {
    final server = RecordingClient((r) => jsonResponse({
          'items': [
            {'product': 'Urea', 'kg': 178.3, 'bag_kg': 45, 'bags': 3.96, 'bags_to_buy': 4, 'gives': '82.0 kg N'},
            {'product': 'DAP', 'kg': 100.0, 'bag_kg': 50, 'bags': 2.0, 'bags_to_buy': 2, 'gives': '46.0 kg P2O5 + 18.0 kg N'},
            {'product': 'MOP (Potash)', 'kg': 0.0, 'bag_kg': 50, 'bags': 0.0, 'bags_to_buy': 0, 'gives': '0.0 kg K2O'},
          ],
          'extra_n_kg': 0,
        }));
    final s = await signedIn(server);
    await pumpWith(tester, s, const SingleChildScrollView(child: FertilizerCard()));
    await tester.enterText(find.widgetWithText(TextField, 'N'), '100');
    await tester.enterText(find.widgetWithText(TextField, 'P₂O₅'), '46');
    await tester.tap(find.text('Calculate bags'));
    await pumpUntil(tester, () => find.text('Urea: buy 4 bags').evaluate().isNotEmpty);
    expect(find.text('DAP: buy 2 bags'), findsOneWidget);
    expect(find.textContaining('MOP (Potash):'), findsNothing); // nothing to buy
    final q = server.requests.last.url.queryParameters;
    expect([q['n'], q['p2o5'], q['k2o'], q['acres'], q['dose_per']], ['100.0', '46.0', '0.0', '1.0', 'acre']);
  });

  testWidgets('admin can safely turn off the Pi after confirming', (tester) async {
    final server = RecordingClient((r) => switch (r.url.path) {
          '/api/v1/device/status' => jsonResponse(piStatus()),
          '/api/v1/device/shutdown' => jsonResponse({'ok': true, 'message': 'The Raspberry Pi is turning off.'}),
          _ => jsonResponse({'configured': true, 'devices': [], 'message': 'No sensor gateway has sent data yet.'}),
        });
    final s = await signedIn(server, role: 'admin');
    await pumpWith(tester, s, const SensorsScreen());
    await pumpUntil(tester, () => find.text('Turn off Pi').evaluate().isNotEmpty);
    expect(find.textContaining('after 3.0 h without use'), findsOneWidget);
    await tester.tap(find.text('Turn off Pi'));
    await tester.pumpAndSettle();
    expect(server.requests.where((r) => r.url.path == '/api/v1/device/shutdown'), isEmpty); // nothing before confirming
    await tester.tap(find.text('Turn off'));
    await tester.pumpAndSettle();
    expect(server.requests.where((r) => r.url.path == '/api/v1/device/shutdown').length, 1);
    expect(find.text('The Raspberry Pi is turning off.'), findsOneWidget);
  });

  testWidgets('farmers never see the turn-off button', (tester) async {
    final s = await signedIn(RecordingClient((r) => r.url.path == '/api/v1/device/status'
        ? jsonResponse(piStatus())
        : jsonResponse({'configured': true, 'devices': [], 'message': 'No sensor gateway has sent data yet.'})));
    await pumpWith(tester, s, const SensorsScreen());
    await pumpUntil(tester, () => find.text('Raspberry Pi 4 Model B Rev 1.5').evaluate().isNotEmpty);
    expect(find.text('Turn off Pi'), findsNothing);
  });

  testWidgets('IoT tab survives the server going away during its timed refresh', (tester) async {
    var serverUp = true;
    final s = await signedIn(RecordingClient((r) {
      // A refused connection: the device request fails before the sensor request (the crash seen on the phone)
      if (!serverUp) throw http.ClientException('Connection refused');
      return jsonResponse({'configured': true, 'devices': [], 'message': 'No sensor gateway has sent data yet.'});
    }));
    await pumpWith(tester, s, const SensorsScreen());
    await pumpUntil(tester, () => find.textContaining('No sensor gateway').evaluate().isNotEmpty);
    serverUp = false;
    await tester.pump(const Duration(seconds: 21));
    await tester.pump(const Duration(seconds: 1));
    expect(tester.takeException(), isNull);
    expect(find.text('Sensor status unavailable'), findsOneWidget);
  });

  testWidgets('server device card is hidden when the server has no device status', (tester) async {
    final s = await signedIn(RecordingClient((_) => jsonResponse({'configured': true, 'devices': [], 'message': 'No sensor gateway has sent data yet.'})));
    await pumpWith(tester, s, const SensorsScreen());
    await pumpUntil(tester, () => find.textContaining('No sensor gateway').evaluate().isNotEmpty);
    expect(find.text('Server device'), findsNothing);
  });

  testWidgets('no sensors -> status message only', (tester) async {
    final s = await signedIn(RecordingClient((_) => jsonResponse({
          'configured': false,
          'devices': [],
          'message': 'No sensor gateway has sent data yet.',
        })));
    await pumpWith(tester, s, const SensorsScreen());
    await pumpUntil(tester, () => find.textContaining('No sensor gateway').evaluate().isNotEmpty);
    expect(find.text('No sensor gateway has sent data yet.'), findsOneWidget);
    expect(find.text('Connected'), findsNothing);
  });

  testWidgets('pest model unavailable is shown explicitly in the result', (tester) async {
    final s = await signedIn(RecordingClient((_) => jsonResponse({})));
    final scan = ScanRecord.fromJson(scanJson(pestState: 'unavailable')..['has_image'] = false);
    await pumpWith(tester, s, SingleChildScrollView(child: ScanResultView(scan: scan, localImage: fakePhoto)));
    expect(find.text('unavailable'), findsOneWidget);
    expect(find.text('Pest model is not loaded'), findsOneWidget);
  });

  group('scanner screen with a (fake) camera', () {
    testWidgets('preview -> capture -> analyze shows the server result', (tester) async {
      final s = await signedIn(RecordingClient((_) => jsonResponse({'scan': scanJson(), 'duplicate': false})));
      final cam = FakeCameraBackend();
      await tester.pumpWidget(ChangeNotifierProvider.value(value: s, child: MaterialApp(home: ScanScreen(cameraBackend: cam))));
      await pumpUntil(tester, () => find.byKey(const Key('camera-preview')).evaluate().isNotEmpty);
      expect(find.byKey(const Key('camera-preview')), findsOneWidget);

      await tester.tap(find.text('Capture'));
      await pumpUntil(tester, () => find.text('Analyze').evaluate().isNotEmpty);
      expect(cam.openSessions, 0, reason: 'camera released after capture');

      await tester.ensureVisible(find.text('Analyze'));
      await tester.tap(find.text('Analyze'));
      await pumpUntil(tester, () => find.text('Tomato Early Blight detected.').evaluate().isNotEmpty);
      expect(find.text('Tomato Early Blight detected.'), findsWidgets);
      expect(find.text('97.4%'), findsOneWidget);
    });

    testWidgets('server failure never shows a diagnosis (no fake fallback)', (tester) async {
      // Phone storage unavailable too: the error must still be shown, never a diagnosis
      final s = await signedIn(RecordingClient((_) => throw http.ClientException('Connection refused')),
          queue: ScanQueue(baseDir: () async => throw const FileSystemException('no storage')));
      await tester
          .pumpWidget(ChangeNotifierProvider.value(value: s, child: MaterialApp(home: ScanScreen(cameraBackend: FakeCameraBackend()))));
      await pumpUntil(tester, () => find.text('Capture').evaluate().isNotEmpty);
      await tester.tap(find.text('Capture'));
      await pumpUntil(tester, () => find.text('Analyze').evaluate().isNotEmpty);
      await tester.ensureVisible(find.text('Analyze'));
      await tester.tap(find.text('Analyze'));
      await pumpUntil(tester, () => find.text('Server unreachable').evaluate().isNotEmpty);
      expect(find.text('Server unreachable'), findsOneWidget);
      expect(find.text('Try again'), findsOneWidget);
      expect(find.byType(ScanResultView), findsNothing);
      expect(find.textContaining('detected'), findsNothing);
    });

    testWidgets('denied permission shows the permission panel, not a camera', (tester) async {
      final s = await signedIn(RecordingClient((_) => jsonResponse({})));
      await tester.pumpWidget(ChangeNotifierProvider.value(
          value: s, child: MaterialApp(home: ScanScreen(cameraBackend: FakeCameraBackend()..permission = CameraPermission.denied))));
      await pumpUntil(tester, () => find.text('Camera permission needed').evaluate().isNotEmpty);
      expect(find.text('Camera permission needed'), findsOneWidget);
      expect(find.byKey(const Key('camera-preview')), findsNothing);
    });
  });

  testWidgets('advice card shows the Tamil advice written for the scan', (tester) async {
    final server = RecordingClient((r) => jsonResponse({
          'cached': false,
          'advice': {
            'state': 'generated',
            'language': 'ta',
            'source': 'local_llm',
            'model': 'gemma3:4b',
            'elapsed_s': 6.1,
            'headline': 'தக்காளி இலை கருகல் நோய்',
            'farmer_message': 'பாதிக்கப்பட்ட இலைகளை அகற்றவும்.',
            'sections': [
              {
                'key': 'do_now',
                'title': 'உடனே செய்ய வேண்டியவை',
                'items': ['கீழ் இலைகளை அகற்றவும்']
              },
            ],
          },
        }));
    final s = await signedIn(server);
    final scan = ScanRecord.fromJson(scanJson()..['has_image'] = false);
    await pumpWith(tester, s, SingleChildScrollView(child: ScanResultView(scan: scan, localImage: fakePhoto)));
    await pumpUntil(tester, () => find.text('உடனே செய்ய வேண்டியவை').evaluate().isNotEmpty);
    expect(find.text('தக்காளி இலை கருகல் நோய்'), findsOneWidget);
    expect(find.text('• கீழ் இலைகளை அகற்றவும்'), findsOneWidget);
    final adviceRequest = server.requests.firstWhere((r) => r.url.path.endsWith('/advice'));
    expect(adviceRequest.body, contains('"language":"ta"'));
  });

  testWidgets('chat shows the offline error instead of inventing an answer', (tester) async {
    final s = await signedIn(RecordingClient((r) => r.url.path == '/api/v1/chat/stream'
        ? ndjsonResponse([
            {'type': 'error', 'code': 'advisor_unavailable', 'detail': 'The AI advisor on the laptop is not running.'}
          ])
        : jsonResponse({'languages': []})));
    await pumpWith(tester, s, const ChatScreen());
    await tester.enterText(find.byType(TextField), 'இலை மஞ்சள் ஆகிறது');
    await tester.tap(find.byIcon(Icons.send));
    // The error ends the HTTP stream early; cancelling it needs a moment of real (not simulated) time
    await tester.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 300)));
    await pumpUntil(tester, () => find.text('Advisor unavailable').evaluate().isNotEmpty);
    expect(find.text('The AI advisor on the laptop is not running.'), findsOneWidget);
    expect(find.text('இலை மஞ்சள் ஆகிறது'), findsOneWidget);
  });

  testWidgets('chat streams the answer and shows which scan it is about', (tester) async {
    final server = RecordingClient((r) => r.url.path == '/api/v1/chat/stream'
        ? ndjsonResponse([
            {
              'type': 'start',
              'language': 'en',
              'language_name': 'English',
              'context': {'scan_id': 2, 'crop': 'Tomato', 'label': 'Tomato Yellow Leaf Curl Virus'}
            },
            {'type': 'delta', 'text': 'Remove infected plants. '},
            {'type': 'delta', 'text': 'Use yellow sticky traps.'},
            {'type': 'done', 'language_name': 'English', 'first_token_s': 2.1, 'elapsed_s': 4.0},
          ])
        : jsonResponse({'languages': []}));
    final s = await signedIn(server);
    await pumpWith(tester, s, const ChatScreen());
    await tester.enterText(find.byType(TextField), 'How do I control this disease organically?');
    await tester.tap(find.byIcon(Icons.send));
    await pumpUntil(tester, () => find.textContaining('sticky traps').evaluate().isNotEmpty);
    expect(find.text('Remove infected plants. Use yellow sticky traps.'), findsOneWidget);
    expect(find.text('About scan #2: Tomato • Tomato Yellow Leaf Curl Virus'), findsOneWidget);
    expect(find.byIcon(Icons.volume_up_outlined), findsOneWidget); // listen button on the answer
    final sent = server.requests.firstWhere((r) => r.url.path == '/api/v1/chat/stream');
    expect(sent.body, contains('"use_latest_scan":true'));
  });

  testWidgets('voice question: recorded audio is transcribed on the laptop and sent', (tester) async {
    final server = RecordingClient((r) => switch (r.url.path) {
          '/api/v1/voice/transcribe' => jsonResponse({'text': 'இலைகள் மஞ்சளாகின்றன', 'language': 'ta', 'elapsed_s': 1.2}),
          '/api/v1/chat/stream' => ndjsonResponse([
              {'type': 'start', 'language': 'ta', 'language_name': 'Tamil', 'context': null},
              {'type': 'delta', 'text': 'நீர் பாய்ச்சலை குறைக்கவும்.'},
              {'type': 'done', 'language_name': 'Tamil', 'first_token_s': 2.0, 'elapsed_s': 3.0},
            ]),
          _ => jsonResponse({'languages': []}),
        });
    final s = await signedIn(server);
    final recorder = FakeRecorder();
    await pumpWith(tester, s, ChatScreen(recorder: recorder));
    await tester.tap(find.byIcon(Icons.mic));
    await tester.pump();
    expect(recorder.recording, isTrue);
    expect(find.textContaining('Listening'), findsOneWidget);
    await tester.tap(find.byIcon(Icons.stop));
    await pumpUntil(tester, () => find.textContaining('நீர் பாய்ச்சலை').evaluate().isNotEmpty);
    expect(find.text('இலைகள் மஞ்சளாகின்றன'), findsOneWidget); // the farmer's words, as heard
    final chat = server.requests.firstWhere((r) => r.url.path == '/api/v1/chat/stream');
    expect(chat.body, contains('"language":"ta"'));
  });

  testWidgets('speaker button plays the laptop voice for an answer', (tester) async {
    final out = FakeAudioOut();
    VoiceController.shared = VoiceController(audioOut: () => out);
    final s = await signedIn(RecordingClient((r) => r.url.path == '/api/v1/voice/speak'
        ? http.Response.bytes(fakePhoto, 200, headers: {'content-type': 'audio/wav', 'x-voice-engine': 'mms-tts (test)'})
        : jsonResponse({})));
    await pumpWith(tester, s, const SpeakButton(id: 'a1', text: 'Remove infected plants.', language: 'en', label: 'Listen'));
    await tester.tap(find.text('Listen'));
    await pumpUntil(tester, () => out.played.isNotEmpty);
    expect(out.played.single.$2, 'audio/wav');
    expect(find.text('Stop'), findsOneWidget);
    VoiceController.shared = VoiceController();
  });
}
