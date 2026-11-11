import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../l10n.dart';

import '../models/models.dart';
import '../services/api_client.dart';
import '../services/reminders.dart';
import '../state/session_state.dart';
import 'common.dart';

/// Spray calculator for the confirmed finding of a scan: how much product per tank and for the
/// whole field. Doses come only from the laptop's reference table; findings without a verified
/// table show the server's explanation instead of a number.
class DosageCard extends StatefulWidget {
  const DosageCard({super.key, required this.scan});

  final ScanRecord scan;

  @override
  State<DosageCard> createState() => _DosageCardState();
}

class _DosageCardState extends State<DosageCard> {
  final _acres = TextEditingController(text: '1');
  final _tank = TextEditingController(text: '15');
  Map<String, dynamic>? _plan;
  String? _error;
  bool _loading = false;

  bool get _garden => context.read<SessionState>().gardenMode;

  @override
  void initState() {
    super.initState();
    if (_garden) _tank.text = '1'; // a 1-litre hand sprayer
  }

  bool get _confirmed {
    final s = widget.scan.result?.summaryState;
    return s == 'disease_detected' || s == 'pest_detected' || s == 'disease_and_pest_detected';
  }

  @override
  void dispose() {
    _acres.dispose();
    _tank.dispose();
    super.dispose();
  }

  Future<void> _calculate() async {
    // Pots have no field size: only the per-litre and per-sprayer doses are shown, so any small area works
    final acres = _garden ? 0.02 : double.tryParse(_acres.text.trim());
    final tank = double.tryParse(_tank.text.trim());
    if (acres == null || acres <= 0 || tank == null || tank < 1) {
      setState(() => _error = 'Enter the field size in acres (e.g. 0.5) and the sprayer size in litres (1 for a hand sprayer).');
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final plan = await context.read<SessionState>().api.dosage(widget.scan.id, acres: acres, tankLiters: tank);
      if (mounted) setState(() => _plan = plan);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  static String _iso(DateTime d) => '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

  /// Records today's spray in the farm diary; with a waiting period, reminds on the first harvest-safe day.
  Future<void> _sprayedToday(Map<String, dynamic> t) async {
    final messenger = ScaffoldMessenger.of(context);
    final wait = (t['pre_harvest_interval_days'] as num?)?.toInt() ?? 0;
    final now = DateTime.now();
    final safe = _iso(now.add(Duration(days: wait)));
    try {
      final saved = await context.read<SessionState>().api.addDiaryEntry({
        'plot': widget.scan.plot ?? 'Farm',
        'kind': 'spray',
        'product': '${t['product_name']}'.length > 80 ? '${t['product_name']}'.substring(0, 80) : '${t['product_name']}',
        'quantity': '${t['dose_per_liter']}',
        'note': wait > 0 ? 'Do not harvest before $safe ($wait days after spraying)' : 'No waiting period before harvest',
        'done_on': _iso(now),
        'remind_on': wait > 0 ? safe : null,
      });
      if (!mounted) return;
      final reminded = await DiaryReminders.instance
          .schedule(saved, title: context.tr('Safe to harvest'), body: '${saved['plot']}: ${t['product_name']}')
          .catchError((_) => false);
      if (!mounted) return;
      messenger.showSnackBar(SnackBar(
          content: Text('${context.tr('Saved in the farm diary')}${reminded ? ' • ${context.tr('Reminder set for {date} 8:00', {'date': safe})}' : ''}')));
    } on ApiException catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(e.message)));
    }
  }

  Widget _treatment(String title, Map<String, dynamic>? t) {
    if (t == null) return const SizedBox.shrink();
    final wait = (t['pre_harvest_interval_days'] as num?)?.toInt();
    return Padding(
      padding: const EdgeInsets.only(top: 10),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(title, style: const TextStyle(fontWeight: FontWeight.bold, color: kDarkGreen)),
        InfoRow('Product', '${t['product_name']}'),
        InfoRow('Per litre', '${t['dose_per_liter']}'),
        InfoRow('Per tank', '${t['dose_per_knapsack_tank']}'),
        if (!_garden) InfoRow('Whole field', '${t['total_product_for_field']}'),
        if (wait != null) InfoRow('Wait before harvest', '$wait ${context.tr('days')}'),
        if (wait != null && wait > 0)
          InfoRow('If sprayed today, harvest from', _iso(DateTime.now().add(Duration(days: wait)))),
        if ((t['safety_and_application'] ?? '').toString().isNotEmpty)
          Text('${t['safety_and_application']}', style: TextStyle(color: Colors.grey.shade800, fontSize: 13)),
        OutlinedButton.icon(
            onPressed: () => _sprayedToday(t), icon: const Icon(Icons.event_available), label: Text(context.tr('I sprayed this today'))),
      ]),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (!_confirmed) return const SizedBox.shrink();
    final p = _plan;
    return SectionCard(title: 'Spray calculator', icon: Icons.calculate_outlined, children: [
      Row(children: [
        if (!_garden) ...[
          Expanded(
            child: TextField(
              controller: _acres,
              keyboardType: const TextInputType.numberWithOptions(decimal: true),
              decoration: InputDecoration(labelText: context.tr('Field (acres)'), isDense: true, border: const OutlineInputBorder()),
            ),
          ),
          const SizedBox(width: 8),
        ],
        Expanded(
          child: TextField(
            controller: _tank,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: InputDecoration(labelText: context.tr(_garden ? 'Sprayer (litres)' : 'Tank (litres)'), isDense: true, border: const OutlineInputBorder()),
          ),
        ),
        const SizedBox(width: 8),
        FilledButton(
          style: FilledButton.styleFrom(backgroundColor: kGreen),
          onPressed: _loading ? null : _calculate,
          child: _loading
              ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
              : Text(context.tr('Calculate')),
        ),
      ]),
      if (_error != null) ...[const SizedBox(height: 8), MessagePanel(icon: Icons.info_outline, title: _error!, color: Colors.orange)],
      if (p != null) ...[
        const SizedBox(height: 8),
        InfoRow('For', '${p['target']}'),
        if (!_garden) InfoRow('Water needed', '${p['total_water_needed_liters']} L (${p['number_of_tanks_required']} ${context.tr('tanks')})'),
        _treatment('Chemical option', p['chemical_treatment'] as Map<String, dynamic>?),
        _treatment('Organic / biological option', p['organic_treatment'] as Map<String, dynamic>?),
        const SizedBox(height: 8),
        Text('${p['note']}', style: const TextStyle(fontSize: 12, fontStyle: FontStyle.italic)),
      ],
    ]);
  }
}
