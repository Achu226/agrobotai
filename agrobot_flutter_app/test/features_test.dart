import 'dart:io';
import 'dart:typed_data';

import 'package:agrobot_flutter_app/main.dart';
import 'package:agrobot_flutter_app/screens/plots_screen.dart';
import 'package:agrobot_flutter_app/services/api_client.dart';
import 'package:agrobot_flutter_app/services/scan_queue.dart';
import 'package:agrobot_flutter_app/state/alerts_state.dart';
import 'package:agrobot_flutter_app/state/scan_controller.dart';
import 'package:agrobot_flutter_app/state/session_state.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:provider/provider.dart';

import 'fakes.dart';
import 'widget_test.dart' show signedIn;

final photo = Uint8List.fromList([1, 2, 3, 4]);

AgrobotApi api(RecordingClient server) => AgrobotApi('http://h:8000', token: 't', client: server.client);

void main() {
  group('offline scan queue', () {
    late Directory tmp;
    late ScanQueue queue;

    setUp(() async {
      tmp = await Directory.systemTemp.createTemp('agrobot_queue');
      queue = ScanQueue(baseDir: () async => tmp);
    });
    tearDown(() => tmp.delete(recursive: true));

    test('uploads with the original request id and plot, then removes the photo', () async {
      await queue.save(photo, clientRequestId: 'req-1', plot: 'North field', crop: 'Tomato');
      expect(await queue.count(), 1);
      final server = RecordingClient((_) => jsonResponse({'scan': scanJson(), 'duplicate': false}));
      final res = await queue.flush(api(server));
      expect(res.uploaded, 1);
      expect(await queue.count(), 0);
      final body = server.requests.single.body;
      expect(body, contains('req-1'));
      expect(body, contains('North field'));
    });

    test('keeps photos while the laptop is unreachable', () async {
      await queue.save(photo, clientRequestId: 'req-1');
      await queue.save(photo, clientRequestId: 'req-2');
      final res = await queue.flush(api(RecordingClient((_) => throw http.ClientException('offline'))));
      expect(res.uploaded, 0);
      expect(await queue.count(), 2);
    });

    test('drops a photo the server rejects and reports why', () async {
      await queue.save(photo, clientRequestId: 'req-1');
      final res = await queue.flush(api(RecordingClient((_) => jsonResponse(
          {'detail': 'No plant leaf detected in the photo.', 'error': {'code': 'no_leaf_detected'}}, 422))));
      expect(res.rejected, ['No plant leaf detected in the photo.']);
      expect(await queue.count(), 0);
    });

    test('scanner saves the photo instead of losing it when the laptop is unreachable', () async {
      final cam = FakeCameraBackend();
      var saved = 0;
      final c = ScanController(
        camera: cam,
        apiProvider: () => api(RecordingClient((_) => throw http.ClientException('no route to host'))),
        queue: queue,
        onSavedOffline: () async => saved++,
      )..plot = 'Plot A';
      await c.startCamera();
      await c.capture();
      await c.analyze();
      expect(c.phase, ScanPhase.savedOffline);
      expect(saved, 1);
      expect(await queue.count(), 1);
    });
  });

  group('recovery tracker', () {
    test('trend needs two measured scans and a real change', () {
      expect(plotTrend([12.0]), isNull);
      expect(plotTrend([null, 12.0, null]), isNull);
      expect(plotTrend([20.0, 14.5]), 'Improving');
      expect(plotTrend([5.0, 9.0]), 'Getting worse');
      expect(plotTrend([5.0, 6.0]), 'No clear change');
    });

    test('a scan with no disease counts as 0%, an uncertain one is left out', () {
      expect(affectedPct({'severity_pct': 7.5}), 7.5);
      expect(affectedPct({'severity_pct': null, 'summary_state': 'no_supported_condition_detected'}), 0);
      expect(affectedPct({'severity_pct': null, 'summary_state': 'uncertain'}), isNull);
    });
  });

  group('field alerts', () {
    test('each alert notifies once; a cleared alert can notify again', () async {
      var alerts = [
        {'code': 'soil_dry', 'device': 'pi-1', 'value': 18.0, 'threshold': 25.0}
      ];
      final s = await signedIn(RecordingClient((_) => jsonResponse({'alerts': alerts})));
      final shown = <String>[];
      final state = AlertsState(notify: (id, title, body) async => shown.add(body));
      String text(Map<String, dynamic> a) => '${a['code']}@${a['device']}';
      await state.poll(s, text, 'Field alert');
      await state.poll(s, text, 'Field alert');
      expect(shown, ['soil_dry@pi-1']);
      alerts = [];
      await state.poll(s, text, 'Field alert');
      alerts = [
        {'code': 'soil_dry', 'device': 'pi-1', 'value': 17.0, 'threshold': 25.0}
      ];
      await state.poll(s, text, 'Field alert');
      expect(shown, ['soil_dry@pi-1', 'soil_dry@pi-1']);
      state.dispose();
    });
  });

  testWidgets('choosing Tamil shows the farmer screens in Tamil', (tester) async {
    final s = await signedIn(RecordingClient((r) => r.url.path == '/api/v1/auth/me'
        ? jsonResponse({'user': {'id': 1, 'username': 'ravi', 'role': 'farmer', 'full_name': 'Ravi'}})
        : jsonResponse({'scans': [], 'alerts': []})));
    await s.setLanguage('ta');
    await tester.pumpWidget(ChangeNotifierProvider<SessionState>.value(value: s, child: const AgrobotApp()));
    for (var i = 0; i < 20 && find.text('ஸ்கேன்கள்').evaluate().isEmpty; i++) {
      await tester.pump(const Duration(milliseconds: 50));
    }
    expect(find.text('ஸ்கேன்கள்'), findsWidgets);
    expect(find.text('இலை ஸ்கேன்'), findsOneWidget);
    expect(find.text('My scans'), findsNothing);
  });

}
