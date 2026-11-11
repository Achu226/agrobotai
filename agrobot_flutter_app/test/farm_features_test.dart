import 'package:agrobot_flutter_app/widgets/scan_result_view.dart';
import 'package:agrobot_flutter_app/models/models.dart';
import 'dart:io';
import 'package:agrobot_flutter_app/screens/diary_screen.dart';
import 'package:agrobot_flutter_app/screens/library_screen.dart';
import 'package:agrobot_flutter_app/screens/weather_screen.dart';
import 'package:agrobot_flutter_app/services/reminders.dart';
import 'package:agrobot_flutter_app/widgets/weather_widgets.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:timezone/data/latest.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;

import 'fakes.dart';
import 'widget_test.dart' show pumpUntil, pumpWith, signedIn;

String _day(int offset) {
  final d = DateTime.now().add(Duration(days: offset));
  return '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
}

void main() {
  test('weather codes map to sun, moon, rain and storm icons', () {
    expect(weatherIcon(0).$1, Icons.wb_sunny);
    expect(weatherIcon(0, day: false).$1, Icons.nightlight_round);
    expect(weatherIcon(63).$1, Icons.water_drop);
    expect(weatherIcon(81).$1, Icons.water_drop);
    expect(weatherIcon(95).$1, Icons.thunderstorm);
    expect(weatherIcon(null).$1, Icons.cloud_outlined);
  });

  test('diary reminders fire at 8:00 on the day and never in the past', () {
    tzdata.initializeTimeZones();
    final ist = tz.getLocation('Asia/Kolkata');
    final now = tz.TZDateTime(ist, 2026, 10, 27, 9);
    expect(DiaryReminders.when('2026-10-27', ist, now), isNull); // 8:00 today already passed
    final at = DiaryReminders.when('2026-11-03', ist, now)!;
    expect([at.year, at.month, at.day, at.hour], [2026, 11, 3, 8]);
    expect(DiaryReminders.when('not a date', ist, now), isNull);
  });

  testWidgets('weather screen shows now, hourly, 7 days and watering advice', (tester) async {
    final weather = {
      'ok': true,
      'provider': 'Open-Meteo',
      'fetched_at': '2026-10-27T19:30:00',
      'weather': {
        'location': 'Salem',
        'region': 'Tamil Nadu',
        'current': {'temp_c': 26.3, 'humidity': 60, 'precipitation_mm': 0.0, 'wind_kph': 0.6, 'condition': 'Partly cloudy',
          'weather_code': 2, 'is_day': true, 'uv_index': 5},
        'hourly': [
          {'time': '2026-10-27T19:00', 'temp_c': 26.3, 'chance_of_rain': 0, 'weather_code': 2, 'is_day': false},
          {'time': '2026-10-27T20:00', 'temp_c': 25.0, 'chance_of_rain': 70, 'weather_code': 63, 'is_day': false},
        ],
        'forecast': [
          for (var i = 0; i < 7; i++)
            {'date': _day(i), 'min_temp_c': 22.0 + i, 'max_temp_c': 30.0 + i, 'chance_of_rain': i * 10, 'condition': 'Rain', 'weather_code': 61},
        ],
      },
      'risk_analysis': {'ok': false},
    };
    final s = await signedIn(RecordingClient((r) => r.url.path == '/api/v1/irrigation'
        ? jsonResponse({'fields': [{'device': 'pi-1', 'moisture_pct': 18.0, 'code': 'water_now'}], 'rain_next_2_days_mm': 0.0,
            'rain_chance_pct': 10, 'rain_expected': false, 'forecast_available': true, 'code': null})
        : jsonResponse(weather)));
    await pumpWith(tester, s, const WeatherScreen());
    await pumpUntil(tester, () => find.text('Next 24 hours').evaluate().isNotEmpty);
    expect(find.text('26°'), findsWidgets);
    expect(find.text('Now'), findsOneWidget);
    expect(find.text('Today'), findsOneWidget);
    await tester.scrollUntilVisible(find.textContaining('water today'), 300, scrollable: find.byType(Scrollable).first);
    expect(find.textContaining('pi-1: Soil is dry (18.0%)'), findsOneWidget);
  });

  testWidgets('guide lists diseases by crop and pests, and opens a fact sheet', (tester) async {
    final s = await signedIn(RecordingClient((_) => jsonResponse({
          'entries': [
            {'key': 'Tomato_Late_blight', 'kind': 'disease', 'crop': 'Tomato', 'name': 'Tomato Late Blight', 'translated': false,
              'facts': ['Cause: water mould (Phytophthora infestans).']},
            {'key': 'aphids', 'kind': 'pest', 'crop': null, 'name': 'Aphids', 'translated': false, 'facts': ['Small sap-sucking insects.']},
          ],
        })));
    await s.setLanguage('en');
    await pumpWith(tester, s, const LibraryScreen());
    await pumpUntil(tester, () => find.text('Aphids').evaluate().isNotEmpty);
    expect(find.text('Tomato'), findsOneWidget);
    expect(find.text('Insect pests'), findsOneWidget);
    await tester.tap(find.text('Tomato Late Blight'));
    await pumpUntil(tester, () => find.textContaining('Phytophthora').evaluate().isNotEmpty);
    expect(find.text('• Cause: water mould (Phytophthora infestans).'), findsOneWidget);
  });

  testWidgets('guide is saved on the phone and shown offline', (tester) async {
    var online = true;
    final s = await signedIn(RecordingClient((_) => online
        ? jsonResponse({
            'entries': [
              {'key': 'aphids', 'kind': 'pest', 'crop': null, 'name': 'Aphids', 'translated': false, 'facts': ['Small sap-sucking insects.']},
            ],
          })
        : throw const SocketException('no network')));
    await s.setLanguage('en');
    await pumpWith(tester, s, const LibraryScreen());
    await pumpUntil(tester, () => find.text('Aphids').evaluate().isNotEmpty);
    expect(find.text('Offline: showing the guide saved on this phone'), findsNothing);

    online = false;
    await pumpWith(tester, s, const LibraryScreen(key: ValueKey('offline')));
    await pumpUntil(tester, () => find.text('Aphids').evaluate().isNotEmpty);
    expect(find.text('Offline: showing the guide saved on this phone'), findsOneWidget);
  });

  test('where the money goes: costs by activity, sales left out, biggest first', () {
    expect(
        spentByKind([
          {'kind': 'spray', 'cost': 250},
          {'kind': 'labour', 'cost': 800},
          {'kind': 'spray', 'cost': 150},
          {'kind': 'sale', 'cost': 9000},
          {'kind': 'note', 'cost': null},
        ]),
        [('labour', 800.0), ('spray', 400.0)]);
  });

  testWidgets('a disease result offers a rescan reminder and the Kisan Call Centre', (tester) async {
    final s = await signedIn(RecordingClient((r) => jsonResponse({'detail': 'Not Found'}, 404)));
    final scan = ScanRecord.fromJson(scanJson()..['has_image'] = false);
    await pumpWith(tester, s, SingleChildScrollView(child: ScanResultView(scan: scan, localImage: fakePhoto)));
    expect(find.text('Remind me to scan again in 7 days'), findsOneWidget);
    expect(find.textContaining('1800-180-1551'), findsOneWidget);
  });

  testWidgets('diary groups entries by plot and lists upcoming reminders', (tester) async {
    final s = await signedIn(RecordingClient((_) => jsonResponse({
          'entries': [
            {'id': 1, 'plot': 'North field', 'kind': 'spray', 'product': 'Neem oil', 'quantity': '3 ml/L', 'cost': 250,
              'done_on': _day(-1), 'remind_on': _day(6)},
            {'id': 2, 'plot': 'South field', 'kind': 'fertilizer', 'product': 'Urea', 'done_on': _day(-3)},
          ],
        })));
    await pumpWith(tester, s, const DiaryView());
    await pumpUntil(tester, () => find.text('Upcoming reminders').evaluate().isNotEmpty);
    expect(find.text('North field: Spray — Neem oil'), findsOneWidget);
    expect(find.text('Where the money goes'), findsOneWidget);
    await tester.scrollUntilVisible(find.text('South field'), 300, scrollable: find.byType(Scrollable).first);
    expect(find.text('South field'), findsOneWidget);
    expect(find.textContaining('Neem oil • 3 ml/L • ₹250'), findsOneWidget);
  });
}
