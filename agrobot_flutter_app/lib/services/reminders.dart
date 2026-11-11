import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:timezone/data/latest.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;

/// Phone reminders for farm-diary entries: a notification at 8:00 on the reminder date.
/// The id is the diary entry id, so scheduling again replaces it and a deleted entry cancels it.
/// A repeating entry (repeat_days) gets its next [_ahead] dates; opening the diary schedules further ones.
class DiaryReminders {
  DiaryReminders._();

  static final instance = DiaryReminders._();
  final _plugin = FlutterLocalNotificationsPlugin();
  bool _ready = false;
  // shortcut: a repeating reminder stops after 6 dates if the diary is never opened; use periodic alarms if that matters
  static const _ahead = 6;

  static int _id(int entryId, int k) => k == 0 ? 100000 + entryId : 50000000 + entryId * 8 + k;

  Future<void> _init() async {
    if (_ready) return;
    tzdata.initializeTimeZones();
    // shortcut: fixed to India time (all farmers are in India); use flutter_timezone if the app goes abroad
    tz.setLocalLocation(tz.getLocation('Asia/Kolkata'));
    await _plugin.initialize(settings: const InitializationSettings(android: AndroidInitializationSettings('@mipmap/ic_launcher')));
    await _plugin.resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>()?.requestNotificationsPermission();
    _ready = true;
  }

  /// 8:00 local time on `isoDate` (YYYY-MM-DD), or null when that moment has passed.
  static tz.TZDateTime? when(String isoDate, tz.Location location, DateTime now) {
    final d = DateTime.tryParse(isoDate);
    if (d == null) return null;
    final at = tz.TZDateTime(location, d.year, d.month, d.day, 8);
    return at.isAfter(now) ? at : null;
  }

  /// Schedules (or replaces) the reminder for one diary entry; past dates are skipped.
  Future<bool> schedule(Map<String, dynamic> entry, {required String title, required String body}) async {
    final remind = entry['remind_on'] as String?;
    if (remind == null) return false;
    await _init();
    final repeat = (entry['repeat_days'] as num?)?.toInt();
    final first = DateTime.tryParse(remind);
    if (first == null) return false;
    final now = tz.TZDateTime.now(tz.local);
    var any = false;
    for (var k = 0; k < (repeat == null ? 1 : _ahead); k++) {
      final day = first.add(Duration(days: k * (repeat ?? 0)));
      final at = when('${day.year}-${day.month.toString().padLeft(2, '0')}-${day.day.toString().padLeft(2, '0')}', tz.local, now);
      if (at == null) continue;
      await _plugin.zonedSchedule(
        id: _id(entry['id'] as int, k),
        scheduledDate: at,
        title: title,
        body: body,
        notificationDetails: const NotificationDetails(
          android: AndroidNotificationDetails('diary_reminders', 'Farm diary reminders', importance: Importance.high, priority: Priority.high),
        ),
        // Inexact is fine for a morning reminder and needs no "exact alarm" permission
        androidScheduleMode: AndroidScheduleMode.inexactAllowWhileIdle,
      );
      any = true;
    }
    return any;
  }

  /// One repeating notification every Sunday at 8:00 (replaces itself when scheduled again).
  Future<void> scheduleWeekly({required String title, required String body}) async {
    await _init();
    final now = tz.TZDateTime.now(tz.local);
    var at = tz.TZDateTime(tz.local, now.year, now.month, now.day, 8);
    while (at.weekday != DateTime.sunday || !at.isAfter(now)) {
      at = at.add(const Duration(days: 1));
    }
    await _plugin.zonedSchedule(
      id: 99000,
      scheduledDate: at,
      title: title,
      body: body,
      notificationDetails: const NotificationDetails(
        android: AndroidNotificationDetails('weekly_summary', 'Weekly farm summary'),
      ),
      androidScheduleMode: AndroidScheduleMode.inexactAllowWhileIdle,
      matchDateTimeComponents: DateTimeComponents.dayOfWeekAndTime,
    );
  }

  Future<void> cancel(int entryId) async {
    await _init();
    for (var k = 0; k < _ahead; k++) {
      await _plugin.cancel(id: _id(entryId, k));
    }
  }
}
