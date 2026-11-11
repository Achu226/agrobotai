import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../l10n.dart';
import '../services/api_client.dart';
import '../state/session_state.dart';
import '../services/reminders.dart';
import 'common.dart';

/// Icon + colour for a WMO weather code (Open-Meteo); night uses the moon for clear sky.
(IconData, Color) weatherIcon(Object? code, {bool day = true}) {
  final c = code is num ? code.toInt() : null;
  return switch (c) {
    null => (Icons.cloud_outlined, Colors.blueGrey),
    0 || 1 => day ? (Icons.wb_sunny, Colors.orange) : (Icons.nightlight_round, Colors.indigo),
    2 => (Icons.wb_cloudy, day ? Colors.amber.shade700 : Colors.indigo.shade300),
    3 => (Icons.cloud, Colors.blueGrey),
    45 || 48 => (Icons.foggy, Colors.blueGrey),
    >= 51 && <= 57 => (Icons.grain, Colors.lightBlue),
    >= 61 && <= 67 || >= 80 && <= 82 => (Icons.water_drop, Colors.blue),
    >= 71 && <= 77 || 85 || 86 => (Icons.ac_unit, Colors.cyan),
    >= 95 => (Icons.thunderstorm, Colors.deepPurple),
    _ => (Icons.cloud_outlined, Colors.blueGrey),
  };
}

const _weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

/// "Today" / "Tomorrow" / short weekday for a forecast date (YYYY-MM-DD).
String dayLabel(BuildContext context, String isoDate) {
  final d = DateTime.tryParse(isoDate);
  if (d == null) return isoDate;
  final now = DateTime.now();
  final diff = DateTime(d.year, d.month, d.day).difference(DateTime(now.year, now.month, now.day)).inDays;
  if (diff == 0) return context.tr('Today');
  if (diff == 1) return context.tr('Tomorrow');
  return context.tr(_weekdays[d.weekday - 1]);
}

String irrigationText(BuildContext context, String? code, Map<String, Object?> args) => switch (code) {
      'water_now' => context.tr('Soil is dry ({moisture}%) and no rain is expected — water today.', args),
      'dry_rain_coming' =>
        context.tr('Soil is dry ({moisture}%) but {rain} mm of rain is expected in 2 days — water lightly only if plants wilt.', args),
      'water_this_evening' => context.tr('Soil moisture is getting low ({moisture}%) — water this evening.', args),
      'skip_rain_expected' => context.tr('Rain is expected ({rain} mm in 2 days) — skip watering. Soil moisture is {moisture}%.', args),
      'moisture_ok' => context.tr('Soil moisture is good ({moisture}%) — no watering needed now.', args),
      'waterlogged' => context.tr('Soil is waterlogged ({moisture}%) — do not water; drain the extra water.', args),
      'no_sensor_rain_expected' =>
        context.tr('No soil sensor connected. {rain} mm of rain is expected in the next 2 days — you can probably skip watering.', args),
      _ => context.tr('No soil sensor connected — check the soil by hand before watering.', args),
    };

/// Watering advice from the Raspberry Pi soil sensor + the rain forecast (never a guessed moisture).
class IrrigationCard extends StatefulWidget {
  const IrrigationCard({super.key, this.location = ''});

  final String location;

  @override
  State<IrrigationCard> createState() => _IrrigationCardState();
}

class _IrrigationCardState extends State<IrrigationCard> {
  late Future<Map<String, dynamic>> _future = context.read<SessionState>().api.irrigation(widget.location);

  @override
  void didUpdateWidget(IrrigationCard old) {
    super.didUpdateWidget(old);
    if (old.location != widget.location) _future = context.read<SessionState>().api.irrigation(widget.location);
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Map<String, dynamic>>(
      future: _future,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) return const SizedBox.shrink();
        if (snap.hasError) {
          final e = snap.error;
          return MessagePanel(icon: Icons.water_drop_outlined, title: 'Watering advice', message: e is ApiException ? e.message : '$e',
              color: Colors.grey);
        }
        final d = snap.data!;
        final fields = (d['fields'] as List? ?? const []).cast<Map<String, dynamic>>();
        final rain = d['rain_next_2_days_mm'];
        return SectionCard(title: 'Watering advice', icon: Icons.water_drop_outlined, children: [
          if (fields.isEmpty)
            Text(irrigationText(context, d['code'] as String?, {'rain': rain ?? '?'})),
          for (final f in fields)
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Icon(switch (f['code']) {
                  'water_now' || 'water_this_evening' => Icons.water_drop,
                  'waterlogged' => Icons.warning_amber,
                  _ => Icons.check_circle_outline,
                }, color: f['code'] == 'water_now' || f['code'] == 'waterlogged' ? Colors.orange.shade800 : kGreen, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text('${f['device']}: ${irrigationText(context, f['code'] as String?, {'moisture': f['moisture_pct'], 'rain': rain ?? 0})}'),
                ),
              ]),
            ),
          if (d['forecast_available'] == true)
            Text(context.tr('Rain forecast, today + tomorrow: {rain} mm (chance up to {chance}%).',
                    {'rain': rain, 'chance': d['rain_chance_pct']}),
                style: const TextStyle(fontSize: 12, color: Colors.black54)),
        ]);
      },
    );
  }
}

const _sprayReasons = {
  'dark': 'Night',
  'rain': 'Raining',
  'rain_soon': 'Rain expected within 6 h',
  'windy': 'Too windy (spray drifts)',
  'too_calm': 'Air too calm (fine spray drifts)',
  'hot': 'Too hot (spray dries before it works)',
  'wind_unknown': 'Wind not known',
  'no_forecast': 'No forecast',
};

/// When is it safe to spray in the next 24 h (real hourly forecast: rain, wind, heat).
class SprayPlanCard extends StatefulWidget {
  const SprayPlanCard({super.key, this.location = ''});

  final String location;

  @override
  State<SprayPlanCard> createState() => _SprayPlanCardState();
}

class _SprayPlanCardState extends State<SprayPlanCard> {
  late final Future<Map<String, dynamic>> _future = context.read<SessionState>().api.sprayPlan(widget.location);

  static String _hm(String iso, {int addHours = 0}) {
    final t = DateTime.tryParse(iso)?.add(Duration(hours: addHours));
    return t == null ? iso : '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}';
  }

  Future<void> _saveToDiary(Map<String, dynamic> window) async {
    final messenger = ScaffoldMessenger.of(context);
    final date = (window['start'] as String).substring(0, 10);
    final span = '${_hm(window['start'] as String)}–${_hm(window['end'] as String, addHours: 1)}';
    try {
      final saved = await context.read<SessionState>().api.addDiaryEntry({
        'plot': 'Farm',
        'kind': 'spray',
        'note': 'Planned spray $span (dry, calm, not too hot by forecast)',
        'done_on': date,
        'remind_on': date,
      });
      if (!mounted) return;
      final reminded = await DiaryReminders.instance
          .schedule(saved, title: context.tr('Spray today'), body: context.tr('Best spraying time: {span}', {'span': span}))
          .catchError((_) => false);
      if (!mounted) return;
      messenger.showSnackBar(SnackBar(
          content: Text('${context.tr('Saved in the farm diary')}${reminded ? ' • ${context.tr('Reminder set for {date} 8:00', {'date': date})}' : ''}')));
    } on ApiException catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(e.message)));
    }
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Map<String, dynamic>>(
      future: _future,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) return const SizedBox.shrink();
        final d = snap.data;
        if (snap.hasError || d == null || d['ok'] != true) {
          final e = snap.error;
          return MessagePanel(
              icon: Icons.sanitizer_outlined,
              title: 'Spray planner',
              message: e is ApiException ? e.message : context.tr('${d?['error'] ?? e ?? ''}'),
              color: Colors.grey);
        }
        final okNow = d['ok_now'] == true;
        final window = d['best_window'] as Map<String, dynamic>?;
        final reasons = (d['now_problems'] as List? ?? const []).map((p) => context.tr(_sprayReasons[p] ?? '$p')).join(', ');
        return SectionCard(title: 'Spray planner', icon: Icons.sanitizer_outlined, children: [
          Row(children: [
            Icon(okNow ? Icons.check_circle : Icons.do_not_disturb_on, color: okNow ? kGreen : Colors.orange.shade800, size: 28),
            const SizedBox(width: 8),
            Expanded(
                child: Text(okNow ? context.tr('Good time to spray now') : '${context.tr('Not now')}: $reasons',
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600))),
          ]),
          const SizedBox(height: 8),
          Text(window == null
              ? context.tr('No safe 2-hour spraying window in the next 24 hours.')
              : context.tr('Best time: {day} {span}', {
                  'day': (window['start'] as String).substring(0, 10),
                  'span': '${_hm(window['start'] as String)}–${_hm(window['end'] as String, addHours: 1)}',
                })),
          if (window != null) ...[
            const SizedBox(height: 8),
            OutlinedButton.icon(
                onPressed: () => _saveToDiary(window), icon: const Icon(Icons.event_note), label: Text(context.tr('Save in farm diary'))),
          ],
          const SizedBox(height: 6),
          Text(context.tr('Checks: no rain for 6 h, wind 3–15 km/h, below 32 °C, daylight. Always follow the product label.'),
              style: TextStyle(fontSize: 12, color: Colors.grey.shade700)),
        ]);
      },
    );
  }
}

/// Agmarknet commodity names (exactly as published) with the label shown to the farmer.
const marketCommodities = {
  'Tomato': 'Tomato',
  'Potato': 'Potato',
  'Onion': 'Onion',
  'Paddy(Dhan)(Common)': 'Paddy',
  'Banana': 'Banana',
  'Brinjal': 'Brinjal',
  'Green Chilli': 'Green Chilli',
  'Maize': 'Maize',
  'Coconut': 'Coconut',
  'Grapes': 'Grapes',
};

/// Today's mandi prices in Tamil Nadu (real published prices only; needs the laptop/Pi to have a data.gov.in key).
class MarketPricesCard extends StatefulWidget {
  const MarketPricesCard({super.key});

  @override
  State<MarketPricesCard> createState() => _MarketPricesCardState();
}

class _MarketPricesCardState extends State<MarketPricesCard> {
  String _commodity = 'Tomato';
  late Future<Map<String, dynamic>> _future = _fetch();

  Future<Map<String, dynamic>> _fetch() => context.read<SessionState>().api.marketPrices(_commodity);

  @override
  Widget build(BuildContext context) {
    return SectionCard(title: 'Market prices', icon: Icons.storefront_outlined, children: [
      DropdownButton<String>(
        value: _commodity,
        isExpanded: true,
        items: [for (final e in marketCommodities.entries) DropdownMenuItem(value: e.key, child: Text(context.tr(e.value)))],
        onChanged: (v) => setState(() {
          _commodity = v ?? _commodity;
          _future = _fetch();
        }),
      ),
      FutureBuilder<Map<String, dynamic>>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const Padding(padding: EdgeInsets.all(12), child: Center(child: CircularProgressIndicator()));
          }
          final d = snap.data;
          if (snap.hasError || d == null || d['ok'] != true) {
            final e = snap.error;
            return Text(e is ApiException ? e.message : context.tr('${d?['error'] ?? e ?? ''}'), style: TextStyle(color: Colors.grey.shade700));
          }
          final rows = (d['records'] as List? ?? const []).cast<Map<String, dynamic>>();
          if (rows.isEmpty) return Text(context.tr('No prices published today for this crop in Tamil Nadu.'));
          String rs(Object? v) => v is num ? '₹${v.round()}' : '—';
          return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            for (final r in rows.take(15))
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Row(children: [
                  Expanded(
                      child: Text('${r['market']}\n${r['district']} • ${r['variety'] ?? ''} • ${r['arrival_date'] ?? ''}',
                          style: const TextStyle(fontSize: 13))),
                  Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
                    Text(rs(r['modal_price']), style: const TextStyle(fontSize: 17, fontWeight: FontWeight.bold)),
                    Text('${rs(r['min_price'])}–${rs(r['max_price'])}', style: TextStyle(fontSize: 12, color: Colors.grey.shade700)),
                  ]),
                ]),
              ),
            Text(context.tr('Price per quintal (100 kg). Source: Agmarknet, Government of India.'),
                style: TextStyle(fontSize: 12, color: Colors.grey.shade700)),
          ]);
        },
      ),
    ]);
  }
}


/// Soil Health Card N-P-K (kg) -> bags of Urea, DAP and MOP to buy. Pure arithmetic on the server.
class FertilizerCard extends StatefulWidget {
  const FertilizerCard({super.key});

  @override
  State<FertilizerCard> createState() => _FertilizerCardState();
}

class _FertilizerCardState extends State<FertilizerCard> {
  final _n = TextEditingController();
  final _p = TextEditingController();
  final _k = TextEditingController();
  final _acres = TextEditingController(text: '1');
  String _per = 'acre';
  Map<String, dynamic>? _result;
  String? _error;
  bool _busy = false;

  @override
  void dispose() {
    for (final c in [_n, _p, _k, _acres]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _calc() async {
    double? num0(TextEditingController c) => c.text.trim().isEmpty ? 0 : double.tryParse(c.text.trim());
    final n = num0(_n), p = num0(_p), k = num0(_k), acres = double.tryParse(_acres.text.trim());
    if (n == null || p == null || k == null || n < 0 || p < 0 || k < 0 || acres == null || acres <= 0 || n + p + k == 0) {
      setState(() => _error = context.tr('Enter N, P and K as numbers (kg) and the field size in acres.'));
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final r = await context.read<SessionState>().api.fertilizer(n: n, p2o5: p, k2o: k, acres: acres, dosePer: _per);
      if (mounted) setState(() => _result = r);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    InputDecoration deco(String label) => InputDecoration(labelText: label, border: const OutlineInputBorder(), isDense: true);
    TextField field(TextEditingController c, String label) =>
        TextField(controller: c, keyboardType: const TextInputType.numberWithOptions(decimal: true), decoration: deco(label));
    final r = _result;
    return SectionCard(title: 'Fertilizer bag calculator', icon: Icons.inventory_2_outlined, children: [
      Text(context.tr('Type the N-P-K (kg) from your Soil Health Card or agriculture officer.'),
          style: TextStyle(color: Colors.grey.shade700)),
      const SizedBox(height: 10),
      Row(children: [
        Expanded(child: field(_n, 'N')),
        const SizedBox(width: 6),
        Expanded(child: field(_p, 'P₂O₅')),
        const SizedBox(width: 6),
        Expanded(child: field(_k, 'K₂O')),
      ]),
      const SizedBox(height: 8),
      Row(children: [
        Expanded(
          child: DropdownButtonFormField<String>(
            initialValue: _per,
            isExpanded: true,
            decoration: deco(context.tr('Dose is')),
            items: [
              DropdownMenuItem(value: 'acre', child: Text(context.tr('kg per acre'))),
              DropdownMenuItem(value: 'hectare', child: Text(context.tr('kg per hectare'))),
            ],
            onChanged: (v) => setState(() => _per = v ?? _per),
          ),
        ),
        const SizedBox(width: 6),
        Expanded(child: field(_acres, context.tr('Field size (acres)'))),
      ]),
      const SizedBox(height: 8),
      FilledButton.icon(
          style: FilledButton.styleFrom(backgroundColor: kGreen),
          onPressed: _busy ? null : _calc,
          icon: const Icon(Icons.calculate_outlined),
          label: Text(context.tr('Calculate bags'))),
      if (_error != null) Padding(padding: const EdgeInsets.only(top: 8), child: Text(_error!, style: TextStyle(color: Colors.red.shade800))),
      if (r != null) ...[
        const SizedBox(height: 8),
        for (final i in (r['items'] as List).cast<Map<String, dynamic>>())
          if ((i['kg'] as num) > 0)
            ListTile(
              dense: true,
              contentPadding: EdgeInsets.zero,
              title: Text('${i['product']}: ${context.tr('buy {n} bags', {'n': i['bags_to_buy']})}',
                  style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
              subtitle: Text('${i['kg']} kg = ${i['bags']} × ${i['bag_kg']} kg • ${i['gives']}'),
            ),
        if ((r['extra_n_kg'] as num) > 0)
          Text(context.tr('DAP already gives {kg} kg more nitrogen than asked, so no urea is needed.', {'kg': r['extra_n_kg']}),
              style: TextStyle(color: Colors.orange.shade900)),
        Text(context.tr('All phosphorus from DAP, potash from MOP. Split urea into 2–3 doses as your officer advises.'),
            style: TextStyle(fontSize: 12, color: Colors.grey.shade700)),
      ],
    ]);
  }
}


/// Diseases and pests that other farmers' scans confirmed in the user's own village in the last 14 days.
/// Hidden when the server is old or the user has no location; counts only, never who.
class NearbyAlertsCard extends StatefulWidget {
  const NearbyAlertsCard({super.key});

  @override
  State<NearbyAlertsCard> createState() => _NearbyAlertsCardState();
}

class _NearbyAlertsCardState extends State<NearbyAlertsCard> {
  late final Future<Map<String, dynamic>> _future = context.read<SessionState>().api.nearbyOutbreaks();

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Map<String, dynamic>>(
      future: _future,
      builder: (context, snap) {
        final d = snap.data;
        if (d == null || d['ok'] != true) return const SizedBox.shrink();
        final alerts = (d['alerts'] as List? ?? const []).cast<Map<String, dynamic>>();
        return SectionCard(title: 'Disease alerts near you', icon: Icons.campaign_outlined, children: [
          if (alerts.isEmpty)
            Text(context.tr('No disease or pest was confirmed near {place} in the last {days} days.', {'place': d['location'], 'days': d['days']}),
                style: TextStyle(color: Colors.grey.shade700)),
          for (final a in alerts)
            ListTile(
              dense: true,
              contentPadding: EdgeInsets.zero,
              leading: Icon(a['kind'] == 'pest' ? Icons.bug_report_outlined : Icons.coronavirus_outlined, color: Colors.orange.shade900),
              title: Text('${a['display_name']}', style: const TextStyle(fontWeight: FontWeight.bold)),
              subtitle: Text(context.tr('{n} confirmed scans • last on {date}', {'n': a['count'], 'date': '${a['last_seen']}'.substring(0, 10)})),
            ),
          if (alerts.isNotEmpty)
            Text(context.tr('Found by other farmers near {place} in the last {days} days. Check your crop for the same signs.', {'place': d['location'], 'days': d['days']}),
                style: TextStyle(fontSize: 12, color: Colors.grey.shade700)),
        ]);
      },
    );
  }
}
