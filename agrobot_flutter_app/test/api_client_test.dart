import 'dart:convert';

import 'package:agrobot_flutter_app/services/api_client.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

import 'fakes.dart';

void main() {
  group('base URL configuration', () {
    test('normalizes user input', () {
      expect(AgrobotApi.normalizeBaseUrl('192.168.1.20:8000/'), 'http://192.168.1.20:8000');
      expect(AgrobotApi.normalizeBaseUrl('https://farm.example/'), 'https://farm.example');
      expect(AgrobotApi.normalizeBaseUrl('  '), AgrobotApi.configuredBaseUrl);
      expect(AgrobotApi.configuredBaseUrl, AgrobotApi.emulatorBaseUrl);
    });

    test('warns that localhost cannot work from a phone', () {
      expect(AgrobotApi.urlWarning('http://localhost:8000'), contains('phone itself'));
      expect(AgrobotApi.urlWarning('127.0.0.1:8000'), isNotNull);
      expect(AgrobotApi.urlWarning('http://192.168.1.20:8000'), isNull);
    });
  });

  test('server unreachable is reported, not hidden', () async {
    final api =
        AgrobotApi('http://192.168.1.20:8000', client: RecordingClient((_) => throw http.ClientException('Connection refused')).client);
    await expectLater(
      api.health(),
      throwsA(isA<ApiException>()
          .having((e) => e.kind, 'kind', ApiErrorKind.serverUnreachable)
          .having((e) => e.message, 'message', contains('start.bat'))),
    );
  });

  test('health parses real readiness, separately per model', () async {
    final api = AgrobotApi('http://h:8000',
        client: RecordingClient((_) => jsonResponse({
              'ok': true,
              'runtime': {'inference_device': 'cuda', 'gpu': 'RTX 4050'},
              'models': {
                'disease': {'ready': true, 'state': 'ready', 'version': 'v-abc', 'num_classes': 15},
                'pest': {'ready': false, 'state': 'unavailable', 'error': 'models/pest_model.pt is missing'},
              },
            })).client);
    final h = await api.health();
    expect(h.disease.ready, isTrue);
    expect(h.pest.ready, isFalse);
    expect(h.pest.error, contains('missing'));
    expect(h.device, 'cuda');
  });

  test('analyze uploads the photo with auth + request id and parses the stored scan', () async {
    final rec = RecordingClient((_) => jsonResponse({'scan': scanJson(), 'duplicate': false}));
    final api = AgrobotApi('http://h:8000', token: 'tok-1', client: rec.client);
    final res = await api.analyze(fakePhoto, clientRequestId: 'req-42', crop: 'Tomato', capturedAt: DateTime.utc(2026, 10, 21, 3, 45));

    final req = rec.requests.single;
    expect(req.url.path, '/api/v1/analyze');
    expect(req.headers['Authorization'], 'Bearer tok-1');
    final body = latin1.decode(req.bodyBytes); // multipart contains binary image bytes
    expect(body, contains('name="client_request_id"'));
    expect(body, contains('req-42'));
    expect(body, contains('2026-10-21T03:45:00.000Z'));
    expect(res.scan.id, 7);
    expect(res.scan.result!.disease.displayName, 'Tomato Early Blight');
    expect(res.scan.result!.disease.calibratedConfidence, 97.4);
  });

  test('error responses map to explicit kinds', () async {
    Future<ApiErrorKind> kindFor(int status, Map<String, dynamic> body) async {
      final api = AgrobotApi('http://h:8000', client: RecordingClient((_) => jsonResponse(body, status)).client);
      try {
        await api.analyze(fakePhoto, clientRequestId: 'r');
        fail('expected an ApiException');
      } on ApiException catch (e) {
        return e.kind;
      }
    }

    expect(
        await kindFor(503, {
          'detail': 'Neither model is loaded',
          'error': {'code': 'models_unavailable'}
        }),
        ApiErrorKind.modelUnavailable);
    expect(
        await kindFor(422, {
          'detail': 'Photo is blurry',
          'error': {'code': 'poor_image_quality'}
        }),
        ApiErrorKind.poorImageQuality);
    expect(
        await kindFor(422, {
          'detail': 'No leaf',
          'error': {'code': 'no_leaf_detected'}
        }),
        ApiErrorKind.noLeafDetected);
    expect(await kindFor(413, {'detail': 'too big'}), ApiErrorKind.invalidImage);
    expect(
        await kindFor(500, {
          'detail': 'CUDA error',
          'error': {'code': 'inference_failed'}
        }),
        ApiErrorKind.inferenceFailed);
    expect(await kindFor(401, {'detail': 'Session expired'}), ApiErrorKind.unauthorized);
  });

  test('decodes data URLs from the server', () {
    expect(AgrobotApi.decodeDataUrl('data:image/png;base64,AQID'), [1, 2, 3]);
    expect(AgrobotApi.decodeDataUrl(null), isNull);
    expect(AgrobotApi.decodeDataUrl('garbage'), isNull);
  });
}
