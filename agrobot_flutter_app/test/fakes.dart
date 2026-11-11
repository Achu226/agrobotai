// Test doubles. These live only under test/ and are never compiled into the app.
import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:agrobot_flutter_app/services/camera_service.dart';
import 'package:agrobot_flutter_app/services/voice.dart';
import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const rearCamera = CameraDescription(name: '0', lensDirection: CameraLensDirection.back, sensorOrientation: 90);
const frontCamera = CameraDescription(name: '1', lensDirection: CameraLensDirection.front, sensorOrientation: 270);

/// A valid 1x1 PNG, so Image.memory can decode it in widget tests.
final fakePhoto = base64Decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==');

class FakeCameraSession implements CameraSession {
  FakeCameraSession(this.description, this.backend);

  final CameraDescription description;
  final FakeCameraBackend backend;
  bool initialized = false;
  bool disposed = false;
  FlashSetting? flash;

  @override
  String get lensName => description.lensDirection == CameraLensDirection.back ? 'Rear camera' : 'Front camera';

  @override
  bool get isInitialized => initialized && !disposed;

  @override
  bool get supportsFlash => description.lensDirection == CameraLensDirection.back;

  @override
  Future<void> initialize() async {
    if (backend.initGate != null) await backend.initGate!.future;
    if (backend.initError != null) throw backend.initError!;
    initialized = true;
  }

  @override
  Future<Uint8List> takePicture() async {
    backend.captures++;
    if (backend.captureError != null) throw backend.captureError!;
    return fakePhoto;
  }

  @override
  Future<void> setFlash(FlashSetting mode) async => flash = mode;

  @override
  Widget buildPreview() => const ColoredBox(key: Key('camera-preview'), color: Colors.green);

  @override
  Future<void> dispose() async => disposed = true;
}

class FakeCameraBackend implements CameraBackend {
  FakeCameraBackend({this.permission = CameraPermission.granted, this.lenses = const [rearCamera, frontCamera]});

  CameraPermission permission;
  List<CameraDescription> lenses;
  Object? initError;
  Object? captureError;
  Completer<void>? initGate;
  int captures = 0;
  bool settingsOpened = false;
  final sessions = <FakeCameraSession>[];

  FakeCameraSession? get current => sessions.isEmpty ? null : sessions.last;
  int get openSessions => sessions.where((s) => !s.disposed).length;

  @override
  Future<CameraPermission> requestPermission() async => permission;

  @override
  Future<void> openPermissionSettings() async => settingsOpened = true;

  @override
  Future<List<CameraDescription>> availableLenses() async => lenses;

  @override
  CameraSession open(CameraDescription description) {
    final s = FakeCameraSession(description, this);
    sessions.add(s);
    return s;
  }
}

/// Builds a server scan JSON like /api/v1/analyze returns.
Map<String, dynamic> scanJson({
  int id = 7,
  String summaryState = 'disease_detected',
  String summaryMessage = 'Tomato Early Blight detected.',
  String diseaseState = 'disease_detected',
  String? diseaseName = 'Tomato Early Blight',
  double? diseaseConfidence = 97.4,
  String pestState = 'no_pest_detected',
  String reviewStatus = 'pending',
}) =>
    {
      'id': id,
      'username': 'ravi',
      'full_name': 'Ravi Kumar',
      'captured_at': '2026-10-21T09:15:00+05:30',
      'received_at': '2026-10-21T09:15:04+05:30',
      'crop_reported': 'Tomato',
      'inference_status': pestState == 'unavailable' ? 'partial' : 'succeeded',
      'summary_state': summaryState,
      'disease_label': diseaseName,
      'disease_state': diseaseState,
      'disease_confidence': diseaseConfidence,
      'pest_state': pestState,
      'review_status': reviewStatus,
      'has_image': true,
      'model_versions': {'disease': 'efficientnet_v2_s-abc', 'pest': pestState == 'unavailable' ? null : 'efficientnet_v2_s-def'},
      'result': {
        'summary': {'state': summaryState, 'message': summaryMessage},
        'disease': {
          'state': diseaseState,
          'display_name': diseaseName,
          'label': diseaseName == null ? null : 'Tomato_Early_blight',
          'calibrated_confidence': diseaseConfidence,
          'message': summaryMessage,
          'model': {'version': 'efficientnet_v2_s-abc'},
        },
        'pest': {
          'state': pestState,
          'message': pestState == 'unavailable' ? 'Pest model is not loaded' : 'None of the 9 supported insect pests was detected.',
          'model': {'version': pestState == 'unavailable' ? null : 'efficientnet_v2_s-def'},
        },
        'severity': {'state': 'not_applicable'},
        'advice': {'state': 'not_requested'},
        'inferred_at': '2026-10-21T09:15:04+05:30',
      },
    };

http.Response jsonResponse(Object body, [int status = 200]) =>
    http.Response(jsonEncode(body), status, headers: {'content-type': 'application/json'});

/// MockClient that records requests and answers from a handler.
class RecordingClient {
  RecordingClient(this.handler);

  final FutureOr<http.Response> Function(http.Request request) handler;
  final requests = <http.Request>[];

  late final http.Client client = MockClient((request) async {
    requests.add(request);
    return handler(request);
  });
}

/// Server finder for tests: never touches the real network.
Future<String?> noServerOnWifi({int port = 8000, String? preferHost}) async => null;

/// Newline-delimited JSON, like /api/v1/chat/stream.
http.Response ndjsonResponse(List<Map<String, dynamic>> events) =>
    http.Response.bytes(utf8.encode(events.map(jsonEncode).join('\n')), 200, headers: {'content-type': 'application/x-ndjson'});

class FakeRecorder implements VoiceRecorder {
  bool recording = false;

  @override
  Future<bool> hasPermission() async => true;

  @override
  Future<void> start() async => recording = true;

  @override
  Future<Uint8List?> stop() async {
    recording = false;
    return Uint8List.fromList(List.filled(3200, 1));
  }

  @override
  Future<void> cancel() async => recording = false;

  @override
  Future<void> dispose() async {}
}

class FakeAudioOut implements AudioOut {
  FakeAudioOut({this.autoComplete = false});

  /// Finish each clip right away (like a very short sound) instead of "playing" until stopped.
  final bool autoComplete;
  final played = <(Uint8List, String)>[];
  final _done = StreamController<void>.broadcast();

  @override
  Future<void> play(Uint8List bytes, String mimeType) async {
    played.add((bytes, mimeType));
    if (autoComplete) scheduleMicrotask(() => _done.add(null));
  }

  @override
  Future<void> stop() async {}

  @override
  Stream<void> get onComplete => _done.stream;

  @override
  Future<void> dispose() async => _done.close();
}
