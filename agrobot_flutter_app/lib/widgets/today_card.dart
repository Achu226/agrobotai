import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../l10n.dart';
import '../screens/diary_screen.dart' show diaryKinds;
import '../services/reminders.dart';
import '../state/alerts_state.dart' show alertText;
import '../state/session_state.dart';
import 'common.dart';

/// "Today" at the top of the home screen: spraying now, reminders due today, alerts and the last 7 days,
/// all from /api/v1/today (the user's real data). Collapsed to one line; hidden when the server is old or unreachable.
class TodayCard extends StatefulWidget {
  const TodayCard({super.key});

  @override
  State<TodayCard> createState() => _TodayCardState();
}

class _TodayCardState extends State<TodayCard> {
  late final Future<Map<String, dynamic>> _future = context.read<SessionState>().api.today();
  bool _weekly = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_weekly) return;
    _weekly = true;
    // A fixed Sunday-morning nudge; the numbers are shown fresh in this card when the app opens
    DiaryReminders.instance
        .scheduleWeekly(
            title: context.tr('Your farm week'), body: context.tr('Open AGROBOTAI to see this week\'s scans, costs and reminders.'))
        .ignore();
  }

  static String _hm(String iso, {int addHours = 0}) {
    final t = DateTime.tryParse(iso)?.add(Duration(hours: addHours));
    return t == null ? iso : '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}';
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Map<String, dynamic>>(
      future: _future,
      builder: (context, snap) {
        final d = snap.data;
        if (d == null || d['week'] is! Map) return const SizedBox.shrink();
        final spray = (d['spray'] as Map?)?.cast<String, dynamic>() ?? const {};
        final window = (spray['best_window'] as Map?)?.cast<String, dynamic>();
        final reminders = (d['reminders'] as List? ?? const []).cast<Map<String, dynamic>>();
        final nearby = (d['nearby'] as List? ?? const []).cast<Map<String, dynamic>>();
        final alerts = (d['alerts'] as List? ?? const []).cast<Map<String, dynamic>>();
        final week = (d['week'] as Map).cast<String, dynamic>();
        final sprayLine = spray['ok'] != true
            ? null
            : spray['ok_now'] == true
                ? context.tr('Good time to spray now')
                : window != null
                    ? context.tr('Spray window: {span}', {'span': '${_hm('${window['start']}')}–${_hm('${window['end']}', addHours: 1)}'})
                    : context.tr('No safe spraying window in the next 24 h');
        final warnings = nearby.length + alerts.length;
        final summary = [
          if (sprayLine != null) sprayLine,
          if (reminders.isNotEmpty)
            reminders.length == 1 ? context.tr('1 reminder today') : context.tr('{n} reminders today', {'n': reminders.length}),
          if (warnings > 0) warnings == 1 ? context.tr('1 alert') : context.tr('{n} alerts', {'n': warnings}),
          if (sprayLine == null && reminders.isEmpty && warnings == 0) context.tr('Nothing needs attention'),
        ].join(' • ');
        Widget line(IconData icon, String text, {Color? color}) => Padding(
              padding: const EdgeInsets.symmetric(vertical: 3),
              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Icon(icon, size: 18, color: color ?? kGreen),
                const SizedBox(width: 8),
                Expanded(child: Text(text)),
              ]),
            );
        return Card(
          margin: const EdgeInsets.only(bottom: 8),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          clipBehavior: Clip.antiAlias,
          child: ExpansionTile(
            leading: Icon(warnings > 0 ? Icons.notification_important_outlined : Icons.today, color: warnings > 0 ? Colors.orange.shade900 : kGreen),
            title: Text(context.tr('Today'), style: const TextStyle(fontWeight: FontWeight.bold)),
            subtitle: Text(summary),
            childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
            expandedCrossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (sprayLine != null) line(Icons.sanitizer_outlined, sprayLine),
              for (final r in reminders)
                line(Icons.alarm,
                    '${r['plot']}: ${context.tr(diaryKinds[r['kind']]?.$1 ?? '${r['kind']}')}${(r['product'] ?? '').toString().isNotEmpty ? ' — ${r['product']}' : ''}'),
              for (final a in nearby)
                line(Icons.campaign_outlined, context.tr('{name}: {n} confirmed scans near you', {'name': a['display_name'], 'n': a['count']}),
                    color: Colors.orange.shade900),
              for (final a in alerts) line(Icons.warning_amber, alertText(context, a), color: Colors.orange.shade900),
              line(
                  Icons.date_range,
                  context.tr('Last 7 days: {scans} scans • spent ₹{spent} • earned ₹{earned}',
                      {'scans': week['scans'], 'spent': (week['spent'] as num).round(), 'earned': (week['earned'] as num).round()})),
            ],
          ),
        );
      },
    );
  }
}
