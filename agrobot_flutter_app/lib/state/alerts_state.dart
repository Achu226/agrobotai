import 'dart:async';

import 'package:flutter/widgets.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

import '../l10n.dart';
import 'session_state.dart';

/// Farmer-readable text for one alert from /api/v1/alerts (values are the real readings).
String alertText(BuildContext context, Map<String, dynamic> a) {
  final args = {'device': a['device'], 'value': a['value']};
  return switch (a['code']) {
    'soil_dry' => context.tr('Soil is dry ({value}% moisture at {device}). Water the field.', args),
    'waterlogged' => context.tr('Soil is waterlogged ({value}% moisture at {device}). Stop irrigation and drain the excess water.', args),
    'heat' => context.tr('Very hot air ({value} °C at {device}). Irrigate in the evening and watch for wilting.', args),
    'blight_weather' =>
      context.tr('Cool and very humid ({value}% humidity at {device}): high risk of blight. Inspect the leaves today.', args),
    'pi_hot' => context.tr('The Raspberry Pi is very hot ({value} °C). Move it to shade or give it more air.', args),
    'pi_low_power' => context.tr('The Raspberry Pi is not getting enough power. Use its original power supply and a short cable.'),
    'sensor_offline' => context.tr('Sensor {device} has sent no data for {value} min.', args),
    _ => '${a['code']} (${a['device']})',
  };
}

/// Shows a phone notification. Separate so tests can replace it.
typedef Notify = Future<void> Function(int id, String title, String body);

Future<void> Function(int, String, String) phoneNotifier() {
  final plugin = FlutterLocalNotificationsPlugin();
  var ready = false;
  return (id, title, body) async {
    if (!ready) {
      await plugin.initialize(settings: const InitializationSettings(android: AndroidInitializationSettings('@mipmap/ic_launcher')));
      await plugin.resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>()?.requestNotificationsPermission();
      ready = true;
    }
    await plugin.show(
      id: id,
      title: title,
      body: body,
      notificationDetails: const NotificationDetails(
        android: AndroidNotificationDetails('field_alerts', 'Field alerts', importance: Importance.high, priority: Priority.high),
      ),
    );
  };
}

/// Polls the laptop for field alerts while the app is open and notifies each new one once.
/// shortcut: no alerts while the app is fully closed; that needs a background worker or push service.
class AlertsState extends ChangeNotifier {
  AlertsState({Notify? notify}) : _notify = notify;

  Notify? _notify;
  List<Map<String, dynamic>> alerts = const [];
  final _notified = <String>{};
  Timer? _timer;

  void start(SessionState session, String Function(Map<String, dynamic>) text, String title) {
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(seconds: 60), (_) => poll(session, text, title));
    poll(session, text, title);
  }

  Future<void> poll(SessionState session, String Function(Map<String, dynamic>) text, String title) async {
    if (!session.isSignedIn) return;
    try {
      alerts = await session.api.alerts();
    } catch (_) {
      return; // laptop unreachable or an older server: keep the last known alerts
    }
    notifyListeners();
    final current = {for (final a in alerts) '${a['code']}|${a['device']}'};
    _notified.retainAll(current); // a cleared alert may notify again if it comes back
    for (final a in alerts) {
      final key = '${a['code']}|${a['device']}';
      if (_notified.add(key)) {
        try {
          await (_notify ??= phoneNotifier())(key.hashCode & 0x7fffffff, title, text(a));
        } catch (_) {
          // notifications unavailable (permission denied, tests): the IoT tab still shows the alert
        }
      }
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }
}
