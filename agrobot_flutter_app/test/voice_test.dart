import 'package:agrobot_flutter_app/services/voice.dart';
import 'package:agrobot_flutter_app/state/session_state.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import 'fakes.dart';
import 'session_state_test.dart' show authJson;

void main() {
  test('long answers are split at sentence ends into short pieces', () {
    final text = List.generate(12, (i) => 'Sentence number $i is here.').join(' ');
    final pieces = VoiceController.chunks('* $text');
    expect(pieces.length, greaterThan(1));
    expect(pieces.every((p) => p.length <= 220), isTrue);
    expect(pieces.join(' '), text); // nothing lost, markdown removed
    expect(VoiceController.chunks('  '), isEmpty);
  });

  test('pieces are fetched one ahead and played in order', () async {
    SharedPreferences.setMockInitialValues({});
    final spoken = <String>[];
    final server = RecordingClient((r) {
      if (r.url.path == '/api/v1/voice/speak') {
        spoken.add(r.body);
        return http.Response.bytes([spoken.length], 200, headers: {'content-type': 'audio/wav'});
      }
      return jsonResponse(authJson('farmer'));
    });
    final session = await SessionState.load(httpClient: server.client);
    await session.signIn('ravi', 'pw-123456');
    final out = FakeAudioOut(autoComplete: true);
    final voice = VoiceController(audioOut: () => out);
    final text = List.generate(12, (i) => 'Sentence number $i is here.').join(' ');
    await voice.toggle('a', text, session, language: 'en');
    expect(out.played.map((p) => p.$1.single), List.generate(VoiceController.chunks(text).length, (i) => i + 1));
    expect(voice.activeKey, isNull); // finished
  });
}
