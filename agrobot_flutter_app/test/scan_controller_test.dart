import 'dart:convert';
import 'dart:async';

import 'package:agrobot_flutter_app/services/api_client.dart';
import 'package:agrobot_flutter_app/services/camera_service.dart';
import 'package:agrobot_flutter_app/state/scan_controller.dart';
import 'package:camera/camera.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

import 'fakes.dart';

void main() {
  late FakeCameraBackend cam;

  ScanController build(RecordingClient server, {List<String>? events}) => ScanController(
        camera: cam,
        apiProvider: () => AgrobotApi('http://h:8000', token: 't', client: server.client),
        onSuccess: () async => events?.add('success'),
        onUnauthorized: (_) async => events?.add('unauthorized'),
      );

  final okServer = RecordingClient((_) => jsonResponse({'scan': scanJson(), 'duplicate': false}));

  setUp(() => cam = FakeCameraBackend());

  group('camera permission', () {
    test('denied shows a permission state, not a camera', () async {
      cam.permission = CameraPermission.denied;
      final c = build(okServer);
      await c.startCamera();
      expect(c.phase, ScanPhase.permissionDenied);
      expect(cam.sessions, isEmpty);
    });

    test('permanently denied offers settings', () async {
      cam.permission = CameraPermission.permanentlyDenied;
      final c = build(okServer);
      await c.startCamera();
      expect(c.phase, ScanPhase.permissionPermanentlyDenied);
      await c.camera.openPermissionSettings();
      expect(cam.settingsOpened, isTrue);
    });
  });

  group('camera initialization', () {
    test('"ready" only after the controller finished initializing; rear camera first', () async {
      cam.initGate = Completer<void>();
      final c = build(okServer);
      final starting = c.startCamera();
      await Future<void>.delayed(Duration.zero);
      expect(c.phase, ScanPhase.cameraInitializing);
      cam.initGate!.complete();
      await starting;
      expect(c.phase, ScanPhase.cameraReady);
      expect(cam.current!.description.lensDirection, CameraLensDirection.back);
      expect(c.session!.isInitialized, isTrue);
    });

    test('initialization failure is shown with the real error and can be retried', () async {
      cam.initError = CameraException('CameraAccessDenied', 'User denied access');
      final c = build(okServer);
      await c.startCamera();
      expect(c.phase, ScanPhase.cameraError);
      expect(c.message, contains('permission'));
      cam.initError = null;
      await c.startCamera();
      expect(c.phase, ScanPhase.cameraReady);
    });

    test('no camera on the device', () async {
      cam.lenses = [];
      final c = build(okServer);
      await c.startCamera();
      expect(c.phase, ScanPhase.cameraError);
      expect(c.message, contains('No camera'));
    });

    test('switching lens disposes the previous controller', () async {
      final c = build(okServer);
      await c.startCamera();
      await c.switchCamera();
      expect(cam.current!.description.lensDirection, CameraLensDirection.front);
      expect(cam.openSessions, 1);
    });

    test('app pause releases the camera, resume reopens it; dispose releases it', () async {
      final c = build(okServer);
      await c.startCamera();
      await c.suspend();
      expect(cam.openSessions, 0);
      await c.resume();
      expect(c.phase, ScanPhase.cameraReady);
      expect(cam.openSessions, 1);
      c.dispose();
      await Future<void>.delayed(Duration.zero);
      expect(cam.openSessions, 0);
    });
  });

  group('capture', () {
    test('captures a real frame, releases the camera, retake reopens it', () async {
      final c = build(okServer);
      await c.startCamera();
      await c.capture();
      expect(c.phase, ScanPhase.imageCaptured);
      expect(c.capturedImage, fakePhoto);
      expect(c.capturedAt, isNotNull);
      expect(cam.openSessions, 0);
      await c.retake();
      expect(c.phase, ScanPhase.cameraReady);
      expect(c.capturedImage, isNull);
    });

    test('capture is ignored unless the camera is ready (no overlapping captures)', () async {
      final c = build(okServer);
      await c.capture();
      expect(cam.captures, 0);
      await c.startCamera();
      await Future.wait([c.capture(), c.capture()]);
      expect(cam.captures, 1);
    });
  });

  group('analysis', () {
    Future<ScanController> captured(RecordingClient server, {List<String>? events}) async {
      final c = build(server, events: events);
      await c.startCamera();
      await c.capture();
      return c;
    }

    test('success shows the stored server result', () async {
      final events = <String>[];
      final c = await captured(okServer, events: events);
      await c.analyze();
      expect(c.phase, ScanPhase.analysisSucceeded);
      expect(c.result!.id, 7);
      expect(c.result!.result!.disease.displayName, 'Tomato Early Blight');
      expect(events, ['success']);
    });

    test('uncertain predictions get their own state', () async {
      final server = RecordingClient((_) => jsonResponse({
            'scan': scanJson(summaryState: 'uncertain', diseaseState: 'uncertain', summaryMessage: 'Unable to make a reliable diagnosis.'),
            'duplicate': false,
          }));
      final c = await captured(server);
      await c.analyze();
      expect(c.phase, ScanPhase.analysisUncertain);
    });

    test('model unavailable -> explicit state and no result', () async {
      final server = RecordingClient((_) => jsonResponse({
            'detail': 'Neither the disease nor the pest model is loaded.',
            'error': {'code': 'models_unavailable'}
          }, 503));
      final c = await captured(server);
      await c.analyze();
      expect(c.phase, ScanPhase.modelUnavailable);
      expect(c.result, isNull);
    });

    test('unusable photo -> imageRejected with the server reason', () async {
      final server = RecordingClient((_) => jsonResponse({
            'detail': 'Photo is blurry.',
            'error': {'code': 'poor_image_quality'}
          }, 422));
      final c = await captured(server);
      await c.analyze();
      expect(c.phase, ScanPhase.imageRejected);
      expect(c.message, 'Photo is blurry.');
    });

    test('server unreachable keeps the photo; retry reuses the same request id (no duplicates)', () async {
      var fail = true;
      final server = RecordingClient((_) {
        if (fail) throw http.ClientException('No route to host');
        return jsonResponse({'scan': scanJson(), 'duplicate': false});
      });
      final c = await captured(server);
      await c.analyze();
      expect(c.phase, ScanPhase.inferenceFailed);
      expect(c.lastErrorKind, ApiErrorKind.serverUnreachable);
      expect(c.result, isNull);
      expect(c.capturedImage, isNotNull);

      fail = false;
      await c.analyze();
      expect(c.phase, ScanPhase.analysisSucceeded);
      final ids = server.requests
          .map((r) => RegExp(r'name="client_request_id"\r\n\r\n(\w+)').firstMatch(latin1.decode(r.bodyBytes))!.group(1))
          .toSet();
      expect(server.requests, hasLength(2));
      expect(ids, hasLength(1));
    });

    test('double tap on Analyze sends one request', () async {
      final gate = Completer<void>();
      final server = RecordingClient((_) async {
        await gate.future;
        return jsonResponse({'scan': scanJson(), 'duplicate': false});
      });
      final c = await captured(server);
      final first = c.analyze();
      final second = c.analyze();
      gate.complete();
      await Future.wait([first, second]);
      expect(server.requests, hasLength(1));
    });

    test('401 signs the user out instead of showing a result', () async {
      final events = <String>[];
      final server = RecordingClient((_) => jsonResponse({'detail': 'Session expired'}, 401));
      final c = await captured(server, events: events);
      await c.analyze();
      expect(c.phase, ScanPhase.inferenceFailed);
      expect(events, ['unauthorized']);
    });

    test('a new capture gets a new request id', () async {
      final c = await captured(okServer);
      final first = c.clientRequestId;
      await c.retake();
      await c.capture();
      expect(c.clientRequestId, isNot(first));
    });
  });
}
