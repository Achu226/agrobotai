import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../l10n.dart';

import '../services/api_client.dart';
import '../state/alerts_state.dart';
import '../state/session_state.dart';
import '../widgets/common.dart';
import '../widgets/weather_widgets.dart';

const _sensorLabels = {
  'soil_moisture_pct': ('Soil moisture', '%', Icons.water_drop_outlined),
  'soil_temp_c': ('Soil temperature', ' °C', Icons.thermostat),
  'air_temp_c': ('Air temperature', ' °C', Icons.device_thermostat),
  'humidity_pct': ('Air humidity', '%', Icons.cloud_outlined),
  'soil_ph': ('Soil pH', '', Icons.science_outlined),
  'soil_ec': ('Soil EC', ' µS/cm', Icons.bolt_outlined),
  'n': ('Nitrogen (N)', ' mg/kg', Icons.grass),
  'p': ('Phosphorus (P)', ' mg/kg', Icons.grass),
  'k': ('Potassium (K)', ' mg/kg', Icons.grass),
  'soil_moisture_raw': ('Soil moisture (raw ADC)', '', Icons.memory),
};

/// IoT tab: live readings from the Raspberry Pi sensor agent (iot/raspberry_pi). Only readings that
/// actually arrived at the laptop are shown, with their age; nothing is simulated.
class SensorsScreen extends StatefulWidget {
  const SensorsScreen({super.key});

  @override
  State<SensorsScreen> createState() => _SensorsScreenState();
}

class _SensorsScreenState extends State<SensorsScreen> {
  late Future<Map<String, dynamic>> _future;
  late Future<Map<String, dynamic>> _device;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _future = context.read<SessionState>().api.sensorStatus();
    _device = context.read<SessionState>().api.deviceStatus()..ignore(); // errors are shown by the card's FutureBuilder
    // Readings arrive every minute or so from the Pi; refresh quietly while this tab is open
    _timer = Timer.periodic(const Duration(seconds: 20), (_) => _refresh());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _refresh() async {
    final api = context.read<SessionState>().api;
    final f = api.sensorStatus();
    // May fail before anything listens (server unreachable); without ignore() that is an uncaught error
    final device = api.deviceStatus()..ignore();
    try {
      await f;
    } catch (_) {
      // shown by the FutureBuilder
    }
    if (mounted) {
      setState(() {
        _future = f;
        _device = device;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: _refresh,
      child: FutureBuilder<Map<String, dynamic>>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done && !snap.hasData) return const Center(child: CircularProgressIndicator());
          if (snap.hasError) {
            final e = snap.error;
            return ListView(padding: const EdgeInsets.all(16), children: [
              MessagePanel(icon: Icons.sensors_off, title: 'Sensor status unavailable', message: e is ApiException ? e.message : '$e'),
            ]);
          }
          final d = snap.data!;
          final devices = (d['devices'] as List?)?.cast<Map<String, dynamic>>() ?? [];
          final alerts = context.watch<AlertsState?>()?.alerts ?? const [];
          return ListView(padding: const EdgeInsets.all(16), children: [
            _ServerDeviceCard(future: _device),
            if (alerts.isNotEmpty)
              MessagePanel(
                icon: Icons.notifications_active_outlined,
                title: 'Field alerts',
                message: [for (final a in alerts) '• ${alertText(context, a)}'].join('\n'),
                color: Colors.orange,
              ),
            if (alerts.isNotEmpty) const SizedBox(height: 12),
            if (devices.isNotEmpty) const IrrigationCard(),
            if (d['configured'] != true)
              const MessagePanel(
                icon: Icons.settings_input_antenna,
                title: 'Sensor link not set up on the laptop yet',
                message:
                    'On the laptop run:  python scripts\\sensor_token.py\nIt creates the sensor token; copy it into the Raspberry Pi\'s config.json.',
                color: Colors.grey,
              ),
            if (devices.isEmpty) ...[
              const SizedBox(height: 12),
              Text(context.tr('${d['message'] ?? 'No sensor data.'}'), style: TextStyle(color: Colors.grey.shade700)),
              const SizedBox(height: 12),
              const _SetupSteps(),
            ],
            for (final dev in devices) _DeviceCard(device: dev, staleAfter: d['stale_after_seconds']),
            const SizedBox(height: 8),
            Text(context.tr('Soil readings describe growing conditions; they cannot by themselves diagnose a leaf disease.'),
                style: const TextStyle(fontSize: 12, fontStyle: FontStyle.italic)),
          ]);
        },
      ),
    );
  }
}

class _DeviceCard extends StatefulWidget {
  const _DeviceCard({required this.device, required this.staleAfter});

  final Map<String, dynamic> device;
  final Object? staleAfter;

  @override
  State<_DeviceCard> createState() => _DeviceCardState();
}

class _DeviceCardState extends State<_DeviceCard> {
  Future<List<Map<String, dynamic>>>? _history;

  String _ago(int? seconds) {
    if (seconds == null) return '';
    if (seconds < 90) return context.tr('{n} s ago', {'n': seconds});
    if (seconds < 5400) return context.tr('{n} min ago', {'n': (seconds / 60).round()});
    return context.tr('{n} h ago', {'n': (seconds / 3600).toStringAsFixed(1)});
  }

  @override
  Widget build(BuildContext context) {
    final dev = widget.device;
    final connected = dev['connected'] == true;
    final readings = (dev['readings'] as Map<String, dynamic>? ?? {});
    return SectionCard(
      title: '${dev['device_id']}',
      icon: Icons.developer_board,
      trailing: Chip(
        label: Text(context.tr(connected ? 'Connected' : 'Disconnected')),
        backgroundColor: connected ? Colors.green.shade50 : Colors.red.shade50,
      ),
      children: [
        InfoRow('Last reading', '${shortTime(dev['received_at'] as String?)} (${_ago(dev['seconds_since_last_reading'] as int?)})'),
        if (!connected)
          Text(context.tr('No data for over {s} s — the values below are the last ones received, not live.', {'s': widget.staleAfter}),
              style: TextStyle(color: Colors.red.shade800)),
        const SizedBox(height: 8),
        Wrap(spacing: 8, runSpacing: 8, children: [
          for (final e in readings.entries)
            _ReadingTile(
              label: context.tr(_sensorLabels[e.key]?.$1 ?? e.key),
              value: e.value == null ? context.tr('Not reported') : '${e.value}${_sensorLabels[e.key]?.$2 ?? ''}',
              icon: _sensorLabels[e.key]?.$3 ?? Icons.sensors,
              live: connected,
            ),
        ]),
        const SizedBox(height: 8),
        if (_history == null)
          TextButton.icon(
            onPressed: () => setState(() => _history = context.read<SessionState>().api.sensorHistory('${dev['device_id']}')),
            icon: const Icon(Icons.show_chart),
            label: Text(context.tr('Show last 24 hours')),
          )
        else
          FutureBuilder<List<Map<String, dynamic>>>(
            future: _history,
            builder: (context, snap) {
              if (snap.connectionState != ConnectionState.done) return const LinearProgressIndicator();
              if (snap.hasError) return Text('History unavailable: ${snap.error}');
              final rows = snap.data!;
              if (rows.length < 2) return Text(context.tr('Not enough readings in the last 24 hours to draw a trend.'));
              final keys = {for (final r in rows) ...((r['readings'] as Map?)?.keys.cast<String>() ?? const <String>[])};
              return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                Text(context.tr('{n} readings in the last 24 hours', {'n': rows.length}), style: const TextStyle(fontSize: 12)),
                for (final k in keys)
                  _Trend(
                    label: context.tr(_sensorLabels[k]?.$1 ?? k),
                    unit: _sensorLabels[k]?.$2 ?? '',
                    values: [for (final r in rows) ((r['readings'] as Map?)?[k] as num?)?.toDouble()],
                  ),
              ]);
            },
          ),
      ],
    );
  }
}

class _ReadingTile extends StatelessWidget {
  const _ReadingTile({required this.label, required this.value, required this.icon, required this.live});

  final String label;
  final String value;
  final IconData icon;
  final bool live;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 150,
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: live ? Colors.green.shade50 : Colors.grey.shade200,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Icon(icon, color: live ? kGreen : Colors.grey),
        const SizedBox(height: 4),
        Text(value, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
        Text(label, style: const TextStyle(fontSize: 12)),
      ]),
    );
  }
}

class _Trend extends StatelessWidget {
  const _Trend({required this.label, required this.unit, required this.values});

  final String label;
  final String unit;
  final List<double?> values;

  @override
  Widget build(BuildContext context) {
    final present = values.whereType<double>().toList();
    if (present.length < 2) return const SizedBox.shrink();
    final lo = present.reduce((a, b) => a < b ? a : b);
    final hi = present.reduce((a, b) => a > b ? a : b);
    return Padding(
      padding: const EdgeInsets.only(top: 10),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('$label  (min ${lo.toStringAsFixed(1)}$unit • max ${hi.toStringAsFixed(1)}$unit)', style: const TextStyle(fontSize: 12)),
        SizedBox(height: 48, width: double.infinity, child: Sparkline(values)),
      ]),
    );
  }
}

/// Health of the machine running the server (the Raspberry Pi): only values it really reports.
/// Hidden when the server has no /device/status (older laptop server).
class _ServerDeviceCard extends StatelessWidget {
  const _ServerDeviceCard({required this.future});

  final Future<Map<String, dynamic>> future;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<Map<String, dynamic>>(
      future: future,
      builder: (context, snap) {
        final d = snap.data;
        if (d == null || d['disk_total_gb'] == null) return const SizedBox.shrink();
        final temp = (d['cpu_temp_c'] as num?)?.toDouble();
        final power = d['power'] as Map<String, dynamic>?;
        final mem = d['memory_used_pct'] as num?;
        final up = d['uptime_s'] as num?;
        final warnings = [
          if (power?['under_voltage_now'] == true) context.tr('Low voltage right now. Use a 5 V 3 A charger.'),
          if (power?['under_voltage_now'] != true && power?['under_voltage_since_boot'] == true)
            context.tr('Low voltage happened since the Pi started. The charger may be weak.'),
          if ((temp ?? 0) >= 80 || power?['temp_limit_now'] == true) context.tr('The Pi is too hot. Keep it in shade with air flow.'),
        ];
        return Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: SectionCard(title: context.tr('Server device'), icon: Icons.developer_board, children: [
            Text('${d['device']}', style: TextStyle(color: Colors.grey.shade700)),
            const SizedBox(height: 8),
            Wrap(spacing: 8, runSpacing: 8, children: [
              if (temp != null)
                _ReadingTile(label: context.tr('CPU temperature'), value: '${temp.toStringAsFixed(1)} °C', icon: Icons.thermostat, live: temp < 80),
              if (power != null)
                _ReadingTile(
                    label: context.tr('Power'),
                    value: context.tr(power['under_voltage_now'] == true ? 'Low' : 'OK'),
                    icon: Icons.power,
                    live: power['under_voltage_now'] != true),
              if (mem != null) _ReadingTile(label: context.tr('Memory used'), value: '${mem.round()}%', icon: Icons.memory, live: mem < 90),
              _ReadingTile(
                  label: context.tr('Storage free'),
                  value: context.tr('{free} of {total} GB', {'free': d['disk_free_gb'], 'total': d['disk_total_gb']}),
                  icon: Icons.sd_storage_outlined,
                  live: (d['disk_free_gb'] as num) > 1),
              if (up != null)
                _ReadingTile(
                    label: context.tr('Running for'),
                    value: context.tr('{h} h {m} min', {'h': up ~/ 3600, 'm': up % 3600 ~/ 60}),
                    icon: Icons.timer_outlined,
                    live: true),
            ]),
            for (final w in warnings) ...[
              const SizedBox(height: 8),
              MessagePanel(icon: Icons.warning_amber_rounded, title: context.tr('Device warning'), message: w, color: Colors.orange),
            ],
            if (d['auto_off_idle_hours'] != null) ...[
              const SizedBox(height: 8),
              Text(context.tr('Turns off by itself after {h} h without use. Plug it in again to start it.', {'h': d['auto_off_idle_hours']}),
                  style: TextStyle(fontSize: 12, color: Colors.grey.shade700)),
            ],
            if (d['can_shutdown'] == true && (context.watch<SessionState>().user?.isAdmin ?? false)) ...[
              const SizedBox(height: 8),
              OutlinedButton.icon(
                onPressed: () => _confirmShutdown(context),
                icon: const Icon(Icons.power_settings_new),
                label: Text(context.tr('Turn off Pi')),
              ),
            ],
          ]),
        );
      },
    );
  }
}

Future<void> _confirmShutdown(BuildContext context) async {
  final yes = await showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: Text(context.tr('Turn off the Raspberry Pi?')),
      content: Text(context.tr('Scanning stops until someone plugs the Pi in again.')),
      actions: [
        TextButton(onPressed: () => Navigator.pop(ctx, false), child: Text(context.tr('Cancel'))),
        FilledButton(onPressed: () => Navigator.pop(ctx, true), child: Text(context.tr('Turn off'))),
      ],
    ),
  );
  if (yes != true || !context.mounted) return;
  final messenger = ScaffoldMessenger.of(context);
  try {
    final res = await context.read<SessionState>().api.shutdownDevice();
    messenger.showSnackBar(SnackBar(content: Text(context.mounted ? context.tr('${res['message']}') : '${res['message']}')));
  } on ApiException catch (e) {
    messenger.showSnackBar(SnackBar(content: Text(e.message)));
  }
}

class _SetupSteps extends StatelessWidget {
  const _SetupSteps();

  @override
  Widget build(BuildContext context) {
    const steps = [
      'Laptop: run  python scripts\\sensor_token.py  and note the token.',
      'Copy the folder iot\\raspberry_pi to the Raspberry Pi.',
      'On the Pi, edit config.json: paste the token and enable the sensors you wired.',
      'On the Pi run:  python3 agrobot_sensor_agent.py --test  (shows real readings, sends nothing).',
      'Then run it for real (see iot/raspberry_pi/README.md to start it automatically on boot).',
      'The laptop\'s Wi-Fi must be set to "Private" so the Pi can reach it.',
    ];
    return SectionCard(title: 'Connect your Raspberry Pi', icon: Icons.developer_board, children: [
      for (var i = 0; i < steps.length; i++) Padding(padding: const EdgeInsets.only(bottom: 6), child: Text('${i + 1}. ${steps[i]}')),
    ]);
  }
}
