import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../l10n.dart';
import 'package:share_plus/share_plus.dart';

import '../models/models.dart';
import '../services/api_client.dart';
import '../services/reminders.dart';
import '../state/session_state.dart';
import 'advice_card.dart';
import 'common.dart';
import 'dosage_card.dart';

/// Displays one stored scan exactly as the server recorded it.
class ScanResultView extends StatefulWidget {
  const ScanResultView({super.key, required this.scan, this.localImage, this.footer = const []});

  final ScanRecord scan;

  /// The photo just captured on this phone (avoids re-downloading it).
  final Uint8List? localImage;
  final List<Widget> footer;

  @override
  State<ScanResultView> createState() => _ScanResultViewState();
}

class _ScanResultViewState extends State<ScanResultView> {
  bool _showHeatmap = false;
  Future<Uint8List>? _remoteImage;
  bool _sharing = false;

  @override
  void initState() {
    super.initState();
    if (widget.localImage == null && widget.scan.hasImage) {
      _remoteImage = context.read<SessionState>().api.scanImage(widget.scan.id);
    }
  }

  Future<void> _shareReport() async {
    if (_sharing) return;
    setState(() => _sharing = true);
    final messenger = ScaffoldMessenger.of(context);
    try {
      final pdf = await context.read<SessionState>().api.reportPdf(widget.scan.id);
      if (!mounted) return;
      final s = widget.scan;
      // Short message that travels with the PDF (WhatsApp shows it as the caption)
      final text = [
        'AGROBOTAI scan #${s.id}: ${context.tr(s.headline)}',
        if ((s.cropReported ?? s.cropSelected ?? '').isNotEmpty) '${context.tr('Crop')}: ${context.tr(s.cropReported ?? s.cropSelected!)}',
        '${context.tr('Analysed')}: ${shortTime(s.result?.inferredAt)}',
      ].join('\n');
      await SharePlus.instance.share(ShareParams(
        files: [XFile.fromData(pdf, mimeType: 'application/pdf', name: 'agrobotai_scan_${widget.scan.id}.pdf')],
        fileNameOverrides: ['agrobotai_scan_${widget.scan.id}.pdf'],
        subject: 'AGROBOTAI scan #${widget.scan.id}',
        text: text,
      ));
    } on ApiException catch (e) {
      messenger.showSnackBar(SnackBar(content: Text('Report unavailable: ${e.message}')));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text('Could not open the report: $e')));
    } finally {
      if (mounted) setState(() => _sharing = false);
    }
  }

  /// A diary note with a reminder to scan the same plot again in 7 days, so the recovery tracker gets a second point.
  Future<void> _checkAgain() async {
    final messenger = ScaffoldMessenger.of(context);
    final s = widget.scan;
    String iso(DateTime d) => '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';
    final now = DateTime.now();
    final due = iso(now.add(const Duration(days: 7)));
    try {
      final saved = await context.read<SessionState>().api.addDiaryEntry({
        'plot': s.plot ?? 'Farm',
        'kind': 'note',
        'note': 'Scan again to check recovery (scan #${s.id}: ${s.headline})',
        'done_on': iso(now),
        'remind_on': due,
      });
      if (!mounted) return;
      final reminded = await DiaryReminders.instance
          .schedule(saved, title: context.tr('Scan the leaf again'), body: '${saved['plot']}: ${context.tr(s.headline)}')
          .catchError((_) => false);
      if (!mounted) return;
      messenger.showSnackBar(SnackBar(
          content: Text('${context.tr('Saved in the farm diary')}${reminded ? ' • ${context.tr('Reminder set for {date} 8:00', {'date': due})}' : ''}')));
    } on ApiException catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(e.message)));
    }
  }

  Widget _image() {
    final heatmap = AgrobotApi.decodeDataUrl(widget.scan.result?.gradcam?['heatmap_base64']);
    Widget frame(Uint8List bytes) => ClipRRect(
          borderRadius: BorderRadius.circular(16),
          child: Image.memory(_showHeatmap && heatmap != null ? heatmap : bytes,
              height: 240, width: double.infinity, fit: BoxFit.cover, gaplessPlayback: true),
        );
    final Widget picture;
    if (widget.localImage != null) {
      picture = frame(widget.localImage!);
    } else if (_remoteImage != null) {
      picture = FutureBuilder<Uint8List>(
        future: _remoteImage,
        builder: (context, snap) {
          if (snap.hasData) return frame(snap.data!);
          if (snap.hasError) {
            return MessagePanel(
                icon: Icons.image_not_supported, title: 'Photo could not be loaded', message: '${snap.error}', color: Colors.grey);
          }
          return const SizedBox(height: 240, child: Center(child: CircularProgressIndicator()));
        },
      );
    } else {
      picture = const MessagePanel(icon: Icons.image_not_supported, title: 'No photo stored for this scan', color: Colors.grey);
    }
    return Column(children: [
      picture,
      if (heatmap != null)
        SwitchListTile(
          contentPadding: EdgeInsets.zero,
          value: _showHeatmap,
          onChanged: (v) => setState(() => _showHeatmap = v),
          title: Text(context.tr('Show AI focus heatmap (Grad-CAM)')),
          subtitle: Text('Areas the ${widget.scan.result?.gradcam?['target'] ?? ''} model relied on (red = most).'),
        ),
    ]);
  }

  @override
  Widget build(BuildContext context) {
    final scan = widget.scan;
    final r = scan.result;
    if (r == null) {
      return MessagePanel(
        icon: Icons.error_outline,
        title: scan.inferenceStatus == 'failed' ? 'This analysis attempt failed' : 'Result not available',
        message: scan.error,
      );
    }
    final (MaterialColor color, IconData icon) = switch (r.summaryState) {
      'disease_detected' || 'pest_detected' || 'disease_and_pest_detected' => (Colors.red, Icons.coronavirus_outlined),
      'uncertain' || 'unsupported_crop' => (Colors.orange, Icons.help_outline),
      'no_supported_condition_detected' => (Colors.green, Icons.eco_outlined),
      _ => (Colors.grey, Icons.info_outline),
    };
    final d = r.disease;
    final p = r.pest;
    final sev = r.severity;
    final health = r.healthIndex;

    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      _image(),
      const SizedBox(height: 8),
      MessagePanel(icon: icon, title: r.summaryMessage, color: color),
      const SizedBox(height: 12),
      SectionCard(title: 'Disease (leaf classifier)', icon: Icons.local_florist, children: [
        InfoRow('State', d.state.replaceAll('_', ' ')),
        if (d.displayName != null) InfoRow('Model prediction', d.displayName!),
        InfoRow('Confidence', pct(d.calibratedConfidence)),
        if (d.message != null && d.state != 'disease_detected') Text(d.message!, style: TextStyle(color: Colors.grey.shade800)),
        for (final reason in d.uncertaintyReasons) Text('• $reason', style: TextStyle(color: Colors.orange.shade900)),
        InfoRow('Model version', notAvailable(d.modelVersion)),
      ]),
      SectionCard(title: 'Insect pests (whole-image classifier)', icon: Icons.bug_report_outlined, children: [
        InfoRow('State', p.state.replaceAll('_', ' ')),
        if (p.displayName != null) InfoRow('Result', p.displayName!),
        if (p.topPrediction != null) InfoRow('Top model guess', '${p.topPrediction} (${pct(p.calibratedConfidence)})'),
        if (p.message != null) Text(p.message!, style: TextStyle(color: Colors.grey.shade800)),
        Text(context.tr('This model cannot locate or count insects — no boxes are drawn.'),
            style: const TextStyle(fontSize: 12, fontStyle: FontStyle.italic)),
        InfoRow('Model version', notAvailable(p.modelVersion)),
      ]),
      SectionCard(title: 'Severity & health index', icon: Icons.analytics_outlined, children: [
        InfoRow('Affected leaf area', sev['state'] == 'measured' ? pct((sev['affected_pct'] as num?)?.toDouble()) : 'Not applicable'),
        if (sev['stage'] != null) InfoRow('Stage', '${sev['stage']}'),
        InfoRow('Health index', health == null ? 'Not available' : '${(health['value'] as num).round()}/100 (heuristic)'),
        if (health != null) Text('${health['limitations']}', style: const TextStyle(fontSize: 12, fontStyle: FontStyle.italic)),
      ]),
      AdviceCard(scan: scan),
      DosageCard(scan: scan),
      if (color == Colors.red)
        OutlinedButton.icon(
            onPressed: _checkAgain, icon: const Icon(Icons.event_repeat), label: Text(context.tr('Remind me to scan again in 7 days'))),
      if (color != Colors.green) const KisanCallCentre(),
      if (context.read<SessionState>().user?.role != 'admin') AskExpertCard(scan: scan),
      SectionCard(title: 'Record', icon: Icons.receipt_long, trailing: ReviewChip(scan.reviewStatus), children: [
        InfoRow('Scan ID', '#${scan.id}'),
        InfoRow('Captured', scan.capturedAt == null ? 'Not available (imported photo)' : shortTime(scan.capturedAt)),
        InfoRow('Analysed', shortTime(r.inferredAt)),
        if (r.totalMs != null) InfoRow('Inference time', '${(r.totalMs! / 1000).toStringAsFixed(1)} s'),
        if (scan.reviewer != null) InfoRow('Reviewed by', '${scan.reviewer} • ${shortTime(scan.reviewedAt)}'),
        if ((scan.reviewComment ?? '').isNotEmpty) InfoRow('Review comment', scan.reviewComment!),
      ]),
      FilledButton.icon(
        onPressed: _sharing ? null : _shareReport,
        icon: _sharing
            ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
            : const Icon(Icons.share),
        label: Text(context.tr('Share report (WhatsApp…)')),
      ),
      ...widget.footer,
    ]);
  }
}


/// India's free farmer helpline (Ministry of Agriculture): experts answer in the caller's language.
/// "Ask an expert": the farmer's question about this scan goes to the officer/admin website; the answer comes back
/// as the review comment (shown in the Record card and on the Today card).
class AskExpertCard extends StatefulWidget {
  const AskExpertCard({super.key, required this.scan});

  final ScanRecord scan;

  @override
  State<AskExpertCard> createState() => _AskExpertCardState();
}

class _AskExpertCardState extends State<AskExpertCard> {
  late String? _question = widget.scan.question;
  late final bool _answered = _question != null && widget.scan.reviewStatus != 'pending';
  bool _sending = false;

  Future<void> _ask() async {
    final ctrl = TextEditingController();
    final text = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(ctx.tr('Ask an expert')),
        content: TextField(
          controller: ctrl,
          autofocus: true,
          maxLength: 500,
          maxLines: 4,
          decoration: InputDecoration(hintText: ctx.tr('What do you see? Since when? What did you spray?')),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: Text(ctx.tr('Cancel'))),
          FilledButton(onPressed: () => Navigator.pop(ctx, ctrl.text.trim()), child: Text(ctx.tr('Send'))),
        ],
      ),
    );
    ctrl.dispose();
    if (text == null || text.length < 3 || !mounted) return;
    final messenger = ScaffoldMessenger.of(context);
    setState(() => _sending = true);
    try {
      final saved = await context.read<SessionState>().api.askExpert(widget.scan.id, text);
      if (!mounted) return;
      setState(() => _question = saved.question);
      messenger.showSnackBar(SnackBar(content: Text(context.tr('Question sent. The answer will appear on this scan.'))));
    } on ApiException catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(e.message)));
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) => Card(
        child: ListTile(
          leading: const Icon(Icons.support_agent, color: kGreen),
          title: Text(context.tr(_question == null ? 'Ask an expert' : 'Your question to the expert'),
              style: const TextStyle(fontWeight: FontWeight.bold)),
          subtitle: Text(_question == null
              ? context.tr('An agriculture officer looks at your photo and answers here.')
              : '“$_question”\n${context.tr(_answered ? 'Answered — see Review comment below' : 'Waiting for the answer')}'),
          isThreeLine: _question != null,
          trailing: _sending
              ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
              : _question == null
                  ? const Icon(Icons.chevron_right)
                  : null,
          onTap: _sending || _question != null ? null : _ask,
        ),
      );
}

class KisanCallCentre extends StatelessWidget {
  const KisanCallCentre({super.key});

  static const number = '1800-180-1551';

  @override
  Widget build(BuildContext context) => Card(
        margin: const EdgeInsets.symmetric(vertical: 8),
        color: Colors.blue.shade50,
        child: ListTile(
          leading: Icon(Icons.support_agent, color: Colors.blue.shade900),
          title: Text('${context.tr('Free expert help: Kisan Call Centre')} $number', style: const TextStyle(fontWeight: FontWeight.bold)),
          subtitle: Text(context.tr('Toll-free, 6 am to 10 pm, in your language. Tell them the result above.')),
          trailing: IconButton(
            tooltip: context.tr('Copy number'),
            icon: const Icon(Icons.copy),
            onPressed: () {
              Clipboard.setData(const ClipboardData(text: number));
              ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(context.tr('Number copied: paste it in the phone app'))));
            },
          ),
        ),
      );
}
