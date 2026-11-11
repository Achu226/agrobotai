import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../l10n.dart';

import '../screens/diagnostics_screen.dart';
import '../state/session_state.dart';

/// Server + model readiness, checked against the real /health endpoint.
/// "Reachable" and "models ready" are shown separately: a running server with no model is not "AI active".
class ConnectionIndicator extends StatelessWidget {
  const ConnectionIndicator({super.key});

  @override
  Widget build(BuildContext context) {
    final s = context.watch<SessionState>();
    final h = s.health;
    final (IconData icon, Color color, String label) = s.checkingHealth
        ? (Icons.sync, Colors.white70, 'Checking…')
        : h == null
            ? (Icons.cloud_off, Colors.red.shade200, s.healthCheckedAt == null ? 'Not checked' : 'Server unreachable')
            : !h.anyModelReady
                ? (Icons.warning_amber, Colors.orange.shade200, 'No model loaded')
                : (!h.disease.ready || !h.pest.ready)
                    ? (Icons.warning_amber, Colors.amber.shade200, h.disease.ready ? 'Partial: disease only' : 'Partial: pest only')
                    : (Icons.check_circle, Colors.lightGreenAccent, 'AI ready');
    return TextButton.icon(
      style: TextButton.styleFrom(foregroundColor: color, visualDensity: VisualDensity.compact),
      onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const DiagnosticsScreen())),
      icon: Icon(icon, size: 18),
      label: Text(label == 'AI ready' ? '${context.tr(label)} • ${h!.device.toUpperCase()}' : context.tr(label),
          style: const TextStyle(fontSize: 12)),
    );
  }
}
