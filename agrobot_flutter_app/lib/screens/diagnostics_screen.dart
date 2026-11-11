import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../services/api_client.dart';
import '../state/session_state.dart';
import '../widgets/common.dart';

/// Server address, live /health check, model status and a copyable report for troubleshooting.
class DiagnosticsScreen extends StatefulWidget {
  const DiagnosticsScreen({super.key});

  @override
  State<DiagnosticsScreen> createState() => _DiagnosticsScreenState();
}

class _DiagnosticsScreenState extends State<DiagnosticsScreen> {
  late final TextEditingController _url;
  Map<String, dynamic>? _modelStatus;
  String? _modelStatusError;

  @override
  void initState() {
    super.initState();
    final s = context.read<SessionState>();
    _url = TextEditingController(text: s.serverUrl);
    WidgetsBinding.instance.addPostFrameCallback((_) => _test());
  }

  @override
  void dispose() {
    _url.dispose();
    super.dispose();
  }

  Future<void> _test() async {
    final s = context.read<SessionState>();
    if (AgrobotApi.normalizeBaseUrl(_url.text) != s.serverUrl) await s.setServerUrl(_url.text);
    await s.checkHealth();
    if (s.isSignedIn && s.health != null) {
      try {
        final m = await s.api.modelsStatus();
        setState(() {
          _modelStatus = m;
          _modelStatusError = null;
        });
      } on ApiException catch (e) {
        setState(() => _modelStatusError = e.message);
      }
    }
  }

  Future<void> _find() async {
    final s = context.read<SessionState>();
    await s.findServer();
    if (mounted) setState(() => _url.text = s.serverUrl);
  }

  @override
  Widget build(BuildContext context) {
    final s = context.watch<SessionState>();
    final h = s.health;
    final warning = AgrobotApi.urlWarning(_url.text);
    return Scaffold(
      appBar: AppBar(title: const Text('Server diagnostics'), backgroundColor: kGreen, foregroundColor: Colors.white),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        TextField(
          controller: _url,
          keyboardType: TextInputType.url,
          onChanged: (_) => setState(() {}),
          decoration: InputDecoration(
            labelText: 'Server URL',
            hintText: 'http://192.168.1.20:8000',
            helperText: 'Phone: tap "Find server on Wi-Fi", or type the "Phone server URL" shown by start.bat. '
                'Emulator: ${AgrobotApi.emulatorBaseUrl}',
            helperMaxLines: 2,
            errorText: warning,
            errorMaxLines: 3,
            border: const OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 8),
        FilledButton.icon(
          onPressed: s.checkingHealth ? null : _test,
          icon: const Icon(Icons.network_check),
          label: Text(s.checkingHealth ? 'Testing…' : 'Save & test /health'),
        ),
        const SizedBox(height: 8),
        OutlinedButton.icon(
          onPressed: s.discovering || s.checkingHealth ? null : _find,
          icon: s.discovering
              ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2))
              : const Icon(Icons.wifi_find),
          label: Text(s.discovering ? 'Searching this Wi-Fi…' : 'Find server on Wi-Fi'),
        ),
        if (s.discoveryMessage != null)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text(s.discoveryMessage!, style: TextStyle(color: s.health != null ? kGreen : Colors.red.shade800)),
          ),
        const SizedBox(height: 16),
        if (s.healthError != null && !s.discovering)
          MessagePanel(icon: Icons.cloud_off, title: 'Server unreachable', message: s.healthError),
        if (h != null)
          SectionCard(title: 'Server reachable', icon: Icons.dns, children: [
            InfoRow('Inference device', h.gpu != null ? '${h.device.toUpperCase()} • ${h.gpu}' : h.device.toUpperCase()),
            InfoRow('Disease model', h.disease.ready ? 'Ready • ${h.disease.version}' : 'Unavailable',
                valueColor: h.disease.ready ? kGreen : Colors.red),
            if (h.disease.error != null) Text(h.disease.error!, style: TextStyle(color: Colors.red.shade800, fontSize: 12)),
            InfoRow('Pest model', h.pest.ready ? 'Ready • ${h.pest.version}' : 'Unavailable',
                valueColor: h.pest.ready ? kGreen : Colors.red),
            if (h.pest.error != null) Text(h.pest.error!, style: TextStyle(color: Colors.red.shade800, fontSize: 12)),
            InfoRow('Server time', shortTime(h.serverTime)),
            InfoRow('Checked', shortTime(s.healthCheckedAt?.toIso8601String())),
          ]),
        if (_modelStatus != null)
          SectionCard(title: 'Model details', icon: Icons.memory, children: [
            for (final e in (_modelStatus!['models'] as Map<String, dynamic>).entries) ...[
              Text(e.key, style: const TextStyle(fontWeight: FontWeight.bold)),
              InfoRow('Architecture', notAvailable((e.value as Map)['architecture'])),
              InfoRow('Classes', notAvailable((e.value as Map)['num_classes'])),
              InfoRow('Test accuracy', notAvailable((e.value as Map)['test_accuracy'], '%')),
              InfoRow('Calibrated', '${(e.value as Map)['calibrated'] ?? false}'),
              const SizedBox(height: 6),
            ],
          ]),
        if (_modelStatusError != null) Text('Model details: $_modelStatusError'),
        SectionCard(title: 'This phone', icon: Icons.smartphone, children: [
          InfoRow('Signed in', s.isSignedIn ? '${s.user!.username} (${s.user!.role})' : 'No'),
          InfoRow('Last successful analysis', shortTime(s.lastSuccessAt?.toIso8601String())),
        ]),
        OutlinedButton.icon(
          onPressed: () async {
            final report = s.diagnosticsReport() + (_modelStatus == null ? '' : '\nModels: ${jsonEncode(_modelStatus!['models'])}');
            await Clipboard.setData(ClipboardData(text: report));
            if (context.mounted) {
              ScaffoldMessenger.of(context)
                  .showSnackBar(const SnackBar(content: Text('Diagnostics copied (no password or token included)')));
            }
          },
          icon: const Icon(Icons.copy),
          label: const Text('Copy diagnostics'),
        ),
      ]),
    );
  }
}
