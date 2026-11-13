import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';

import '../l10n.dart';

import '../services/api_client.dart';
import '../services/camera_service.dart';
import '../state/scan_controller.dart';
import '../state/session_state.dart';
import '../widgets/common.dart';
import '../widgets/scan_result_view.dart';

const kCropChoices = [
  'Tomato',
  'Potato',
  'Bell Pepper',
  'Green Chilli',
  'Brinjal',
  'Corn (Maize)',
  'Rice (Paddy)',
  'Wheat',
  'Cotton',
  'Sugarcane',
  'Soybean',
  'Banana',
  'Apple',
  'Grape',
  'Orange',
  'Peach',
  'Cherry',
  'Strawberry',
  'Squash',
  'Blueberry',
  'Raspberry',
  'Rose',
  'Money Plant',
  'Hibiscus',
  'Marigold',
];

/// Live camera → capture → review → send to the laptop → real result.
class ScanScreen extends StatefulWidget {
  const ScanScreen({super.key, this.cameraBackend = const PluginCameraBackend()});

  final CameraBackend cameraBackend;

  @override
  State<ScanScreen> createState() => _ScanScreenState();
}

class _ScanScreenState extends State<ScanScreen> with WidgetsBindingObserver {
  late final ScanController _c;
  List<String> _plotNames = const [];
  // Crops the server's disease model can diagnose (from /models/status), so the hint is always true
  List<String>? _supportedCrops;

  @override
  void initState() {
    super.initState();
    final session = context.read<SessionState>();
    _c = ScanController(
      camera: widget.cameraBackend,
      apiProvider: () => session.api,
      onUnauthorized: session.handleUnauthorized,
      onSuccess: session.recordSuccess,
      queue: session.queue,
      onSavedOffline: session.refreshQueue,
    )..addListener(_onChange);
    WidgetsBinding.instance.addObserver(this);
    _c.startCamera();
    _loadPlotNames();
    _loadSupportedCrops();
  }

  Future<void> _loadSupportedCrops() async {
    try {
      final s = await context.read<SessionState>().api.modelsStatus();
      final crops = (s['supported_disease_crops'] as List?)?.cast<String>();
      if (mounted && crops != null && crops.isNotEmpty) setState(() => _supportedCrops = crops);
    } catch (_) {
      // older server or offline: keep the default hint
    }
  }

  /// Earlier plot names, offered while typing so the same plot is spelled the same way.
  Future<void> _loadPlotNames() async {
    try {
      final plots = await context.read<SessionState>().api.plots();
      if (mounted) setState(() => _plotNames = [for (final p in plots) '${p['plot']}']);
    } on ApiException {
      // suggestions are optional (offline or older server)
    }
  }

  void _onChange() {
    if (mounted) setState(() {});
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.inactive || state == AppLifecycleState.paused || state == AppLifecycleState.hidden) {
      _c.suspend();
    } else if (state == AppLifecycleState.resumed) {
      _c.resume();
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _c.removeListener(_onChange);
    _c.dispose(); // releases the camera
    super.dispose();
  }

  Future<void> _importFromGallery() async {
    try {
      final file = await ImagePicker().pickImage(source: ImageSource.gallery, maxWidth: 2000, imageQuality: 92);
      if (file != null) await _c.useImportedImage(await file.readAsBytes());
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Could not open the gallery: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(context.tr('Scan a leaf')),
        backgroundColor: kGreen,
        foregroundColor: Colors.white,
        actions: [
          if (_c.phase == ScanPhase.cameraReady && (_c.session?.supportsFlash ?? false))
            IconButton(
              tooltip: 'Flash: ${_c.flash.name}',
              onPressed: _c.cycleFlash,
              icon: Icon(switch (_c.flash) {
                FlashSetting.off => Icons.flash_off,
                FlashSetting.auto => Icons.flash_auto,
                FlashSetting.torch => Icons.flashlight_on
              }),
            ),
          if (_c.canSwitchCamera) IconButton(tooltip: context.tr('Switch camera'), onPressed: _c.switchCamera, icon: const Icon(Icons.cameraswitch)),
        ],
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: _body()),
        ),
      ),
    );
  }

  List<Widget> _body() {
    switch (_c.phase) {
      case ScanPhase.initial:
      case ScanPhase.cameraInitializing:
        return [
          _viewport(Center(
              child: Column(mainAxisSize: MainAxisSize.min, children: [
            const CircularProgressIndicator(color: Colors.white),
            const SizedBox(height: 12),
            Text(context.tr('Starting camera…'), style: const TextStyle(color: Colors.white)),
          ])))
        ];
      case ScanPhase.permissionDenied:
        return [
          MessagePanel(icon: Icons.no_photography, title: 'Camera permission needed', message: _c.message, actions: [
            FilledButton(onPressed: _c.startCamera, child: Text(context.tr('Allow camera'))),
            OutlinedButton(onPressed: _importFromGallery, child: Text(context.tr('Import photo instead'))),
          ])
        ];
      case ScanPhase.permissionPermanentlyDenied:
        return [
          MessagePanel(icon: Icons.no_photography, title: 'Camera permission blocked', message: _c.message, actions: [
            FilledButton(onPressed: () => _c.camera.openPermissionSettings(), child: Text(context.tr('Open settings'))),
            OutlinedButton(onPressed: _c.startCamera, child: Text(context.tr('Try again'))),
          ])
        ];
      case ScanPhase.cameraError:
        return [
          MessagePanel(icon: Icons.videocam_off, title: 'Camera could not start', message: _c.message, actions: [
            FilledButton(onPressed: _c.startCamera, child: Text(context.tr('Retry'))),
            OutlinedButton(onPressed: _importFromGallery, child: Text(context.tr('Import photo instead'))),
          ])
        ];
      case ScanPhase.cameraReady:
      case ScanPhase.capturing:
        final s = _c.session;
        return [
          _viewport(s != null && s.isInitialized ? s.buildPreview() : const SizedBox()),
          const SizedBox(height: 8),
          Text('${s?.lensName ?? ''} • ${context.tr('fill the frame with one leaf, in daylight, and hold steady.')}',
              textAlign: TextAlign.center, style: TextStyle(color: Colors.grey.shade700)),
          if (_c.message != null && _c.phase == ScanPhase.cameraReady)
            Text(context.tr(_c.message!), textAlign: TextAlign.center, style: TextStyle(color: Colors.orange.shade900)),
          const SizedBox(height: 12),
          Row(children: [
            Expanded(
              child: OutlinedButton.icon(
                  onPressed: _c.busy ? null : _importFromGallery, icon: const Icon(Icons.photo_library), label: Text(context.tr('Gallery'))),
            ),
            const SizedBox(width: 12),
            Expanded(
              flex: 2,
              child: FilledButton.icon(
                style: FilledButton.styleFrom(backgroundColor: kGreen, padding: const EdgeInsets.symmetric(vertical: 14)),
                onPressed: _c.phase == ScanPhase.cameraReady ? _c.capture : null,
                icon: _c.phase == ScanPhase.capturing
                    ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                    : const Icon(Icons.camera),
                label: Text(context.tr(_c.phase == ScanPhase.capturing ? 'Capturing…' : 'Capture')),
              ),
            ),
          ]),
        ];
      case ScanPhase.imageCaptured:
      case ScanPhase.analyzing:
      case ScanPhase.imageRejected:
      case ScanPhase.modelUnavailable:
      case ScanPhase.inferenceFailed:
        return _reviewAndAnalyze();
      case ScanPhase.savedOffline:
        return [
          ClipRRect(
              borderRadius: BorderRadius.circular(16),
              child: Image.memory(_c.capturedImage!, height: 240, fit: BoxFit.cover, gaplessPlayback: true)),
          const SizedBox(height: 12),
          MessagePanel(icon: Icons.save_alt, title: 'Saved on this phone', message: _c.message, color: Colors.blue, actions: [
            FilledButton.icon(onPressed: _c.retake, icon: const Icon(Icons.camera_alt), label: Text(context.tr('Scan another leaf'))),
            OutlinedButton(onPressed: () => Navigator.of(context).pop(), child: Text(context.tr('Done'))),
          ]),
        ];
      case ScanPhase.analysisSucceeded:
      case ScanPhase.analysisUncertain:
        return [
          ScanResultView(scan: _c.result!, localImage: _c.capturedImage, footer: [
            const SizedBox(height: 8),
            OutlinedButton.icon(onPressed: _c.retake, icon: const Icon(Icons.refresh), label: Text(context.tr('Scan another leaf'))),
          ]),
        ];
    }
  }

  Widget _viewport(Widget child) => Container(
        height: 380,
        decoration:
            BoxDecoration(color: Colors.black, borderRadius: BorderRadius.circular(20), border: Border.all(color: kGreen, width: 3)),
        child: ClipRRect(borderRadius: BorderRadius.circular(17), child: child),
      );

  List<Widget> _reviewAndAnalyze() {
    final analyzing = _c.phase == ScanPhase.analyzing;
    final error = switch (_c.phase) {
      ScanPhase.imageRejected =>
        MessagePanel(icon: Icons.photo_camera_back, title: 'Photo not usable — please retake', message: _c.message, color: Colors.orange),
      ScanPhase.modelUnavailable => MessagePanel(
          icon: Icons.memory,
          title: 'AI model unavailable on the server',
          message: '${_c.message}\n\nOn the laptop, check the start.bat window and models/ folder. No diagnosis was made.'),
      ScanPhase.inferenceFailed => MessagePanel(
          icon: _c.lastErrorKind == ApiErrorKind.serverUnreachable || _c.lastErrorKind == ApiErrorKind.timeout
              ? Icons.wifi_off
              : Icons.error_outline,
          title: switch (_c.lastErrorKind) {
            ApiErrorKind.serverUnreachable => 'Server unreachable',
            ApiErrorKind.timeout => 'Server timed out',
            ApiErrorKind.unauthorized => 'Signed out',
            _ => 'Analysis failed',
          },
          message: '${context.tr(_c.message ?? '')}\n\n${context.tr('No result was saved. Your photo is kept — tap "Try again".')}'),
      _ => null,
    };
    return [
      ClipRRect(
          borderRadius: BorderRadius.circular(16),
          child: Image.memory(_c.capturedImage!, height: 320, fit: BoxFit.cover, gaplessPlayback: true)),
      if (_c.extraImages.isNotEmpty) ...[
        const SizedBox(height: 6),
        Row(children: [
          for (final img in _c.extraImages)
            Padding(
                padding: const EdgeInsets.only(right: 6),
                child: ClipRRect(borderRadius: BorderRadius.circular(8), child: Image.memory(img, width: 64, height: 64, fit: BoxFit.cover))),
        ]),
      ],
      if (!analyzing && _c.phase == ScanPhase.imageCaptured && 1 + _c.extraImages.length < ScanController.maxPhotos)
        TextButton.icon(
            onPressed: _c.addLeaf,
            icon: const Icon(Icons.add_a_photo_outlined),
            label: Text(context.tr('Add another leaf of the same plant ({n}/3) — more accurate', {'n': 1 + _c.extraImages.length}))),
      const SizedBox(height: 4),
      Text(
          _c.importedFromGallery
              ? context.tr('Imported photo (capture time unknown)')
              : context.tr('Captured {time}', {'time': shortTime(_c.capturedAt?.toIso8601String())}),
          textAlign: TextAlign.center, style: TextStyle(color: Colors.grey.shade700)),
      const SizedBox(height: 12),
      DropdownButtonFormField<String?>(
        initialValue: _c.crop,
        decoration: InputDecoration(
            labelText: context.tr('Crop (optional)'),
            border: const OutlineInputBorder(),
            helperMaxLines: 3,
            helperText: _supportedCrops == null
                ? context.tr('Disease model supports Tomato, Potato and Bell Pepper')
                : context.tr('Disease model supports: {crops}', {'crops': _supportedCrops!.map(context.tr).join(', ')})),
        items: [
          DropdownMenuItem(value: null, child: Text(context.tr('Let the model decide'))),
          for (final c in kCropChoices) DropdownMenuItem(value: c, child: Text(context.tr(c)))
        ],
        onChanged: analyzing ? null : (v) => setState(() => _c.crop = v),
      ),
      const SizedBox(height: 12),
      Autocomplete<String>(
        initialValue: TextEditingValue(text: _c.plot ?? ''),
        optionsBuilder: (v) => _plotNames.where((n) => n.toLowerCase().contains(v.text.trim().toLowerCase())),
        onSelected: (v) => _c.plot = v,
        fieldViewBuilder: (context, controller, focus, onSubmit) => TextField(
          controller: controller,
          focusNode: focus,
          enabled: !analyzing,
          maxLength: 60,
          onChanged: (v) => _c.plot = v.trim().isEmpty ? null : v.trim(),
          decoration: InputDecoration(
            labelText: context.tr('Plot / plant name (optional)'),
            helperText: context.tr('Use the same name each time to track recovery'),
            prefixIcon: const Icon(Icons.grass),
            border: const OutlineInputBorder(),
            counterText: '',
          ),
        ),
      ),
      const SizedBox(height: 12),
      if (error != null) ...[error, const SizedBox(height: 12)],
      if (analyzing) ...[
        const LinearProgressIndicator(),
        const SizedBox(height: 8),
        Text(context.tr(_c.message ?? 'Analysing…'), textAlign: TextAlign.center),
        Text(context.tr('The first analysis after starting the server can take up to a minute.'),
            textAlign: TextAlign.center, style: const TextStyle(fontSize: 12)),
        const SizedBox(height: 12),
      ],
      Row(children: [
        Expanded(
            child:
                OutlinedButton.icon(onPressed: analyzing ? null : _c.retake, icon: const Icon(Icons.replay), label: Text(context.tr('Retake')))),
        const SizedBox(width: 12),
        Expanded(
          flex: 2,
          child: FilledButton.icon(
            style: FilledButton.styleFrom(backgroundColor: kGreen, padding: const EdgeInsets.symmetric(vertical: 14)),
            onPressed: analyzing || _c.phase == ScanPhase.imageRejected ? null : _c.analyze,
            icon: const Icon(Icons.biotech),
            label: Text(context.tr(_c.phase == ScanPhase.imageCaptured ? 'Analyze' : 'Try again')),
          ),
        ),
      ]),
    ];
  }
}
