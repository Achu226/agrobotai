import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../l10n.dart';

import '../models/models.dart';
import '../services/api_client.dart';
import '../state/session_state.dart';
import '../widgets/common.dart';
import '../widgets/today_card.dart';
import 'diary_screen.dart';
import 'plots_screen.dart';
import 'scan_detail_screen.dart';

/// Scans stored on the server. Farmers see their own; admins see everyone's.
class ScanList extends StatefulWidget {
  const ScanList(
      {super.key,
      this.reviewStatus,
      this.includeFailed = false,
      this.emptyMessage = 'No scan history yet. Capture a leaf image to begin.'});

  final String? reviewStatus;
  final bool includeFailed;
  final String emptyMessage;

  @override
  State<ScanList> createState() => ScanListState();
}

class ScanListState extends State<ScanList> {
  late Future<List<ScanRecord>> _future;
  int _view = 0; // 0 all scans, 1 by plot, 2 farm diary

  @override
  void initState() {
    super.initState();
    _future = _load();
    WidgetsBinding.instance.addPostFrameCallback((_) => context.read<SessionState>().refreshQueue());
  }

  Future<void> _uploadQueued() async {
    final messenger = ScaffoldMessenger.of(context);
    final s = context.read<SessionState>();
    final res = await s.uploadQueued();
    if (!mounted) return;
    final text = [
      if (res.uploaded > 0) context.tr('{n} uploaded', {'n': res.uploaded}),
      if (res.uploaded == 0 && res.rejected.isEmpty) '${context.tr('Not uploaded')}: ${context.tr('Server unreachable')}',
      for (final r in res.rejected) '${context.tr('Rejected')}: $r',
    ].join('\n');
    messenger.showSnackBar(SnackBar(content: Text(text)));
    await refresh(); // the laptop may be back even when nothing was uploaded
  }

  /// Farmers: photos waiting on the phone, and the All scans / By plot switch.
  Widget _farmerHeader(SessionState s) => Padding(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 0),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          const TodayCard(),
          if (s.queuedScans > 0)
            MessagePanel(
              icon: Icons.cloud_upload_outlined,
              title: s.queuedScans == 1
                  ? context.tr('1 scan waiting to upload')
                  : context.tr('{n} scans waiting to upload', {'n': s.queuedScans}),
              message: 'Saved on this phone; they upload automatically when the laptop is reachable.',
              color: Colors.blue,
              actions: [
                FilledButton.icon(
                  onPressed: s.uploadingQueue ? null : _uploadQueued,
                  icon: s.uploadingQueue
                      ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Icon(Icons.upload),
                  label: Text(context.tr(s.uploadingQueue ? 'Uploading…' : 'Upload now')),
                ),
              ],
            ),
          const SizedBox(height: 8),
          SegmentedButton<int>(
            segments: [
              ButtonSegment(value: 0, label: Text(context.tr('All scans'))),
              ButtonSegment(value: 1, label: Text(context.tr('By plot'))),
              ButtonSegment(value: 2, label: Text(context.tr('Diary'))),
            ],
            selected: {_view},
            showSelectedIcon: false,
            onSelectionChanged: (v) => setState(() => _view = v.first),
          ),
        ]),
      );

  Future<List<ScanRecord>> _load() async {
    final session = context.read<SessionState>();
    try {
      return await session.api.scans(reviewStatus: widget.reviewStatus, includeFailed: widget.includeFailed);
    } on ApiException catch (e) {
      if (e.kind == ApiErrorKind.unauthorized) await session.handleUnauthorized(e);
      rethrow;
    }
  }

  Future<void> refresh() async {
    final f = _load();
    setState(() => _future = f);
    await f.catchError((_) => <ScanRecord>[]);
  }

  @override
  Widget build(BuildContext context) {
    final session = context.watch<SessionState>();
    final isAdmin = session.user?.isAdmin ?? false;
    final list = _list(isAdmin);
    if (isAdmin) return list;
    return Column(children: [_farmerHeader(session), Expanded(child: switch (_view) { 1 => const PlotsView(), 2 => const DiaryView(), _ => list })]);
  }

  Widget _list(bool isAdmin) {
    return RefreshIndicator(
      onRefresh: refresh,
      child: FutureBuilder<List<ScanRecord>>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
          if (snap.hasError) {
            return ListView(padding: const EdgeInsets.all(16), children: [
              MessagePanel(
                  icon: Icons.cloud_off,
                  title: 'Could not load scans',
                  message: '${snap.error}',
                  actions: [OutlinedButton(onPressed: refresh, child: Text(context.tr('Retry')))]),
            ]);
          }
          final scans = snap.data!;
          if (scans.isEmpty) {
            return ListView(padding: const EdgeInsets.all(24), children: [
              Icon(Icons.history, size: 56, color: Colors.grey.shade400),
              const SizedBox(height: 12),
              Text(context.tr(widget.emptyMessage), textAlign: TextAlign.center, style: TextStyle(color: Colors.grey.shade700)),
            ]);
          }
          return ListView.builder(
            padding: const EdgeInsets.all(12),
            itemCount: scans.length,
            itemBuilder: (context, i) => _tile(context, scans[i], isAdmin),
          );
        },
      ),
    );
  }

  Widget _tile(BuildContext context, ScanRecord s, bool isAdmin) {
    final failed = s.inferenceStatus == 'failed';
    final color = failed
        ? Colors.grey
        : switch (s.summaryState) {
            'uncertain' || 'unsupported_crop' => Colors.orange,
            'no_supported_condition_detected' => Colors.green,
            _ => Colors.red,
          };
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      child: ListTile(
        leading:
            CircleAvatar(backgroundColor: color.shade100, child: Icon(failed ? Icons.error_outline : Icons.eco, color: color.shade800)),
        title: Text(s.headline, style: const TextStyle(fontWeight: FontWeight.bold)),
        subtitle: Text([
          if (isAdmin) 'Farmer: ${s.farmerName ?? 'local dashboard'}',
          '${context.tr(s.cropReported ?? s.cropSelected ?? 'Crop not identified')} • ${shortTime(s.capturedAt ?? s.receivedAt)}'
              '${s.plot != null ? ' • ${context.tr('Plot')}: ${s.plot}' : ''}',
          if (s.diseaseConfidence != null && s.diseaseState == 'disease_detected')
            '${context.tr('Confidence')} ${pct(s.diseaseConfidence)}',
          if (failed) 'Error: ${s.error ?? 'unknown'}',
        ].join('\n')),
        isThreeLine: true,
        trailing: failed ? null : ReviewChip(s.reviewStatus),
        onTap: failed
            ? null
            : () async {
                await Navigator.of(context).push(MaterialPageRoute(builder: (_) => ScanDetailScreen(scanId: s.id)));
                refresh();
              },
      ),
    );
  }
}
