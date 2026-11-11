import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../l10n.dart';
import '../services/api_client.dart';
import '../state/session_state.dart';
import '../widgets/common.dart';
import 'scan_detail_screen.dart';

/// Affected leaf area of one scan for the trend: the measured value; 0 when the scan found no
/// supported disease; null (left out) when it was uncertain or not measured.
double? affectedPct(Map<String, dynamic> scan) {
  final v = scan['severity_pct'];
  if (v is num) return v.toDouble();
  return scan['summary_state'] == 'no_supported_condition_detected' ? 0 : null;
}

/// 'Improving' / 'Getting worse' / 'No clear change', or null with fewer than 2 measured scans.
String? plotTrend(List<double?> values) {
  final measured = values.whereType<double>().toList();
  if (measured.length < 2) return null;
  final change = measured.last - measured.first;
  if (change <= -2) return 'Improving';
  if (change >= 2) return 'Getting worse';
  return 'No clear change';
}

/// Recovery tracker: each plot's scans over time.
class PlotsView extends StatefulWidget {
  const PlotsView({super.key});

  @override
  State<PlotsView> createState() => _PlotsViewState();
}

class _PlotsViewState extends State<PlotsView> {
  late Future<List<Map<String, dynamic>>> _future = context.read<SessionState>().api.plots();

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<Map<String, dynamic>>>(
      future: _future,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
        if (snap.hasError) {
          final e = snap.error;
          return ListView(padding: const EdgeInsets.all(16), children: [
            MessagePanel(icon: Icons.cloud_off, title: 'Could not load scans', message: e is ApiException ? e.message : '$e', actions: [
              OutlinedButton(
                  onPressed: () => setState(() => _future = context.read<SessionState>().api.plots()), child: Text(context.tr('Retry'))),
            ]),
          ]);
        }
        final plots = snap.data!;
        if (plots.isEmpty) {
          return ListView(padding: const EdgeInsets.all(24), children: [
            Icon(Icons.grass, size: 56, color: Colors.grey.shade400),
            const SizedBox(height: 12),
            Text(context.tr('No plots yet. When scanning, enter a plot or plant name to track recovery.'),
                textAlign: TextAlign.center, style: TextStyle(color: Colors.grey.shade700)),
          ]);
        }
        return ListView(padding: const EdgeInsets.all(12), children: [for (final p in plots) _plotCard(p)]);
      },
    );
  }

  Widget _plotCard(Map<String, dynamic> plot) {
    final scans = (plot['scans'] as List).cast<Map<String, dynamic>>();
    final values = [for (final s in scans) affectedPct(s)];
    final trend = plotTrend(values);
    final measured = values.whereType<double>().toList();
    final (Color color, IconData icon) = switch (trend) {
      'Improving' => (Colors.green, Icons.trending_down),
      'Getting worse' => (Colors.red, Icons.trending_up),
      _ => (Colors.grey, Icons.trending_flat),
    };
    final last = scans.last;
    return SectionCard(
      title: '${plot['plot']}',
      icon: Icons.grass,
      trailing: Text(context.tr('{n} scans', {'n': scans.length}), style: const TextStyle(fontSize: 12)),
      children: [
        if (trend == null)
          Text(context.tr('Need 2 scans with a measured affected area to show a trend.'), style: TextStyle(color: Colors.grey.shade700))
        else ...[
          Row(children: [
            Icon(icon, color: color),
            const SizedBox(width: 6),
            Text(context.tr(trend), style: TextStyle(fontWeight: FontWeight.bold, color: color)),
          ]),
          Text(context.tr('Affected leaf area: {first}% → {last}%',
              {'first': measured.first.toStringAsFixed(1), 'last': measured.last.toStringAsFixed(1)})),
          const SizedBox(height: 6),
          SizedBox(height: 48, width: double.infinity, child: Sparkline(values)),
        ],
        if (scans.length >= 2) ...[
          const SizedBox(height: 8),
          Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Expanded(child: _ScanPhoto(scan: scans.first, label: 'First scan')),
            const SizedBox(width: 8),
            Expanded(child: _ScanPhoto(scan: last, label: 'Latest scan')),
          ]),
        ],
        const SizedBox(height: 6),
        InfoRow(context.tr('Captured'), shortTime(last['captured_at'] as String?)),
        if (last['disease_label'] != null) InfoRow(context.tr('Result'), '${last['disease_label']}'),
        Align(
          alignment: Alignment.centerRight,
          child: TextButton(
            onPressed: () => Navigator.of(context)
                .push(MaterialPageRoute(builder: (_) => ScanDetailScreen(scanId: last['id'] as int))),
            child: Text('#${last['id']} →'),
          ),
        ),
      ],
    );
  }
}


/// One scan photo of a plot (first or latest) with its date, for the before/after comparison.
class _ScanPhoto extends StatefulWidget {
  const _ScanPhoto({required this.scan, required this.label});

  final Map<String, dynamic> scan;
  final String label;

  @override
  State<_ScanPhoto> createState() => _ScanPhotoState();
}

class _ScanPhotoState extends State<_ScanPhoto> {
  late final Future<Uint8List> _image = context.read<SessionState>().api.scanImage(widget.scan['id'] as int);

  @override
  Widget build(BuildContext context) {
    final missing = Container(color: Colors.grey.shade200, child: Icon(Icons.image_not_supported_outlined, color: Colors.grey.shade500));
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      AspectRatio(
        aspectRatio: 1,
        child: ClipRRect(
          borderRadius: BorderRadius.circular(10),
          child: FutureBuilder<Uint8List>(
            future: _image,
            builder: (context, snap) => snap.hasData
                ? Image.memory(snap.data!, fit: BoxFit.cover, errorBuilder: (_, __, ___) => missing)
                : snap.hasError
                    ? missing
                    : const Center(child: CircularProgressIndicator(strokeWidth: 2)),
          ),
        ),
      ),
      const SizedBox(height: 4),
      Text('${context.tr(widget.label)} • ${shortTime(widget.scan['captured_at'] as String?)}', style: const TextStyle(fontSize: 12)),
    ]);
  }
}
