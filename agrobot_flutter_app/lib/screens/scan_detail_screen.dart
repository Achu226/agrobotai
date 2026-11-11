import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/models.dart';
import '../services/api_client.dart';
import '../state/session_state.dart';
import '../widgets/common.dart';
import '../widgets/scan_result_view.dart';

/// A stored scan, loaded from the server (never re-analysed). Admins can approve or reject it.
class ScanDetailScreen extends StatefulWidget {
  const ScanDetailScreen({super.key, required this.scanId});

  final int scanId;

  @override
  State<ScanDetailScreen> createState() => _ScanDetailScreenState();
}

class _ScanDetailScreenState extends State<ScanDetailScreen> {
  late Future<ScanRecord> _future;
  bool _submitting = false;

  @override
  void initState() {
    super.initState();
    _future = context.read<SessionState>().api.scan(widget.scanId);
  }

  Future<void> _review(bool approve) async {
    final comment = await showDialog<String>(
      context: context,
      builder: (ctx) {
        final controller = TextEditingController();
        return AlertDialog(
          title: Text(approve ? 'Approve diagnosis' : 'Reject diagnosis'),
          content: TextField(
            controller: controller,
            maxLines: 3,
            decoration: InputDecoration(
                labelText: approve ? 'Comment (optional)' : 'Reason (shown to the farmer)', border: const OutlineInputBorder()),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
            FilledButton(onPressed: () => Navigator.pop(ctx, controller.text), child: Text(approve ? 'Approve' : 'Reject')),
          ],
        );
      },
    );
    if (comment == null || !mounted) return;
    setState(() => _submitting = true);
    final session = context.read<SessionState>();
    final messenger = ScaffoldMessenger.of(context);
    try {
      final updated = await session.api.review(widget.scanId, approve: approve, comment: comment);
      // Reload the full record so the screen shows exactly what the server stored
      setState(() => _future = session.api.scan(widget.scanId));
      messenger.showSnackBar(SnackBar(content: Text('Saved: ${updated.reviewStatus} by ${updated.reviewer}')));
    } on ApiException catch (e) {
      if (e.kind == ApiErrorKind.unauthorized) await session.handleUnauthorized(e);
      messenger.showSnackBar(SnackBar(content: Text('Review not saved: ${e.message}')));
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final isAdmin = context.watch<SessionState>().user?.isAdmin ?? false;
    return Scaffold(
      appBar: AppBar(title: Text('Scan #${widget.scanId}'), backgroundColor: kGreen, foregroundColor: Colors.white),
      body: FutureBuilder<ScanRecord>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
          if (snap.hasError) {
            return Padding(
                padding: const EdgeInsets.all(16),
                child: MessagePanel(icon: Icons.error_outline, title: 'Could not load this scan', message: '${snap.error}'));
          }
          final scan = snap.data!;
          return SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: ScanResultView(
              key: ValueKey('${scan.id}-${scan.reviewStatus}'),
              scan: scan,
              footer: [
                if (isAdmin) ...[
                  const SizedBox(height: 16),
                  Text('Farmer: ${scan.farmerName ?? 'local dashboard'}', style: const TextStyle(fontWeight: FontWeight.bold)),
                  const SizedBox(height: 8),
                  Row(children: [
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: _submitting ? null : () => _review(false),
                        icon: const Icon(Icons.close, color: Colors.red),
                        label: const Text('Reject'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: FilledButton.icon(
                        style: FilledButton.styleFrom(backgroundColor: kGreen),
                        onPressed: _submitting ? null : () => _review(true),
                        icon: const Icon(Icons.check),
                        label: const Text('Approve'),
                      ),
                    ),
                  ]),
                ],
              ],
            ),
          );
        },
      ),
    );
  }
}
