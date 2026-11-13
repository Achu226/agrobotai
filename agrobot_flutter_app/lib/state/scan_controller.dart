import 'dart:math';

import 'package:camera/camera.dart' show CameraDescription, CameraException;
import 'package:flutter/foundation.dart';

import '../models/models.dart';
import '../services/api_client.dart';
import '../services/camera_service.dart';
import '../services/scan_queue.dart';

/// Every state the scanner screen can be in. The UI renders exactly one of these.
enum ScanPhase {
  initial,
  permissionDenied,
  permissionPermanentlyDenied,
  cameraInitializing,
  cameraReady,
  capturing,
  imageCaptured,
  analyzing,
  analysisSucceeded,
  analysisUncertain,
  savedOffline,
  imageRejected,
  cameraError,
  modelUnavailable,
  inferenceFailed,
}

/// Camera + capture + inference workflow, independent of widgets so it can be unit tested.
///
/// Guarantees:
/// * "Camera ready" only after the controller finished initializing.
/// * A result is shown only after the server returned a completed inference.
/// * One capture / one analysis at a time; a retry reuses the same request id, so the server
///   cannot store the same photo twice.
class ScanController extends ChangeNotifier {
  ScanController(
      {required this.camera, required this.apiProvider, this.onUnauthorized, this.onSuccess, this.queue, this.onSavedOffline});

  final CameraBackend camera;
  final AgrobotApi Function() apiProvider;
  final Future<void> Function(ApiException)? onUnauthorized;
  final Future<void> Function()? onSuccess;

  /// Where photos go when the laptop cannot be reached; null = no offline saving.
  final ScanQueue? queue;
  final Future<void> Function()? onSavedOffline;

  ScanPhase phase = ScanPhase.initial;
  String? message;
  ApiErrorKind? lastErrorKind;
  CameraSession? session;
  List<CameraDescription> lenses = const [];
  int lensIndex = 0;
  FlashSetting flash = FlashSetting.off;
  Uint8List? capturedImage;

  /// Up to 2 more leaves of the same plant; the server averages them with [capturedImage] for the disease decision.
  List<Uint8List> extraImages = const [];
  bool _addingLeaf = false;
  static const maxPhotos = 3;
  DateTime? capturedAt;
  bool importedFromGallery = false;
  String? clientRequestId;
  ScanRecord? result;
  String? crop;
  String? plot;
  bool _disposed = false;
  bool _suspended = false;

  bool get busy => phase == ScanPhase.cameraInitializing || phase == ScanPhase.capturing || phase == ScanPhase.analyzing;
  bool get canSwitchCamera => lenses.length > 1 && phase == ScanPhase.cameraReady;
  bool get hasImage => capturedImage != null;

  void _set(ScanPhase p, {String? msg}) {
    if (_disposed) return;
    phase = p;
    message = msg;
    notifyListeners();
  }

  /// Ask for permission, find a camera (rear first) and open it.
  Future<void> startCamera() async {
    if (busy || _disposed) return;
    _set(ScanPhase.cameraInitializing, msg: 'Starting camera…');
    final permission = await camera.requestPermission();
    switch (permission) {
      case CameraPermission.granted:
        break;
      case CameraPermission.permanentlyDenied:
        return _set(ScanPhase.permissionPermanentlyDenied,
            msg: 'Camera permission is blocked. Open Settings → Permissions → Camera → Allow, then come back.');
      case CameraPermission.restricted:
        return _set(ScanPhase.cameraError, msg: 'Camera access is restricted on this device (e.g. by parental controls).');
      case CameraPermission.denied:
        return _set(ScanPhase.permissionDenied, msg: 'AGROBOTAI needs the camera to photograph leaves. Tap "Allow camera" to try again.');
    }
    try {
      if (lenses.isEmpty) lenses = await camera.availableLenses();
      if (lenses.isEmpty) {
        return _set(ScanPhase.cameraError, msg: 'No camera was found on this device.');
      }
      await _openLens(lensIndex.clamp(0, lenses.length - 1));
    } on CameraException catch (e) {
      _set(ScanPhase.cameraError, msg: _cameraMessage(e));
    } catch (e) {
      _set(ScanPhase.cameraError, msg: 'Camera failed to start: $e');
    }
  }

  Future<void> _openLens(int index) async {
    await _closeSession();
    lensIndex = index;
    final s = camera.open(lenses[index]);
    session = s;
    await s.initialize();
    if (_disposed || _suspended) {
      await s.dispose();
      session = null;
      return;
    }
    if (!s.isInitialized) {
      await _closeSession();
      return _set(ScanPhase.cameraError, msg: 'The camera did not finish initializing.');
    }
    flash = FlashSetting.off;
    _set(ScanPhase.cameraReady);
  }

  String _cameraMessage(CameraException e) => switch (e.code) {
        'CameraAccessDenied' ||
        'CameraAccessDeniedWithoutPrompt' ||
        'cameraPermission' =>
          'Camera permission was denied. Allow it in Settings → Apps → AGROBOTAI → Permissions.',
        'CameraAccessRestricted' => 'Camera access is restricted on this device.',
        _ => 'Camera error (${e.code}): ${e.description ?? 'unknown'}',
      };

  Future<void> switchCamera() async {
    if (!canSwitchCamera) return;
    _set(ScanPhase.cameraInitializing, msg: 'Switching camera…');
    try {
      await _openLens((lensIndex + 1) % lenses.length);
    } on CameraException catch (e) {
      _set(ScanPhase.cameraError, msg: _cameraMessage(e));
    }
  }

  Future<void> cycleFlash() async {
    final s = session;
    if (s == null || !s.supportsFlash || phase != ScanPhase.cameraReady) return;
    final next = FlashSetting.values[(flash.index + 1) % FlashSetting.values.length];
    try {
      await s.setFlash(next);
      flash = next;
      notifyListeners();
    } on CameraException catch (e) {
      message = 'Flash not available: ${e.description ?? e.code}';
      notifyListeners();
    }
  }

  Future<void> capture() async {
    final s = session;
    if (phase != ScanPhase.cameraReady || s == null) return;
    _set(ScanPhase.capturing, msg: 'Capturing…');
    try {
      final bytes = await s.takePicture();
      if (bytes.isEmpty) throw CameraException('emptyImage', 'The camera returned an empty image.');
      _acceptImage(bytes, fromGallery: false);
      if (flash == FlashSetting.torch) {
        await s.setFlash(FlashSetting.off);
        flash = FlashSetting.off;
      }
      await _closeSession(); // release the camera while the photo is reviewed / analysed
      _set(ScanPhase.imageCaptured);
    } on CameraException catch (e) {
      _set(ScanPhase.cameraError, msg: _cameraMessage(e));
    }
  }

  /// A photo chosen from the gallery instead of the live camera.
  Future<void> useImportedImage(Uint8List bytes) async {
    if (busy) return;
    await _closeSession();
    _acceptImage(bytes, fromGallery: true);
    _set(ScanPhase.imageCaptured);
  }

  /// Opens the camera for one more leaf of the same plant (kept with the first photo).
  Future<void> addLeaf() async {
    if (busy || capturedImage == null || 1 + extraImages.length >= maxPhotos) return;
    _addingLeaf = true;
    await startCamera();
  }

  void _acceptImage(Uint8List bytes, {required bool fromGallery}) {
    if (_addingLeaf && capturedImage != null) {
      _addingLeaf = false;
      extraImages = [...extraImages, bytes];
      clientRequestId = _newRequestId(); // different photos = a different request
      result = null;
      return;
    }
    extraImages = const [];
    capturedImage = bytes;
    capturedAt = fromGallery ? null : DateTime.now();
    importedFromGallery = fromGallery;
    clientRequestId = _newRequestId();
    result = null;
  }

  Future<void> retake() async {
    if (busy) return;
    capturedImage = null;
    extraImages = const [];
    _addingLeaf = false;
    capturedAt = null;
    clientRequestId = null;
    result = null;
    await startCamera();
  }

  Future<void> analyze() async {
    final bytes = capturedImage;
    if (bytes == null || phase == ScanPhase.analyzing) return;
    _set(ScanPhase.analyzing, msg: 'Uploading photo and running the AI models on the laptop…');
    try {
      final response = await apiProvider().analyze(
        bytes,
        extraImages: extraImages,
        clientRequestId: clientRequestId!,
        crop: crop,
        plot: plot,
        capturedAt: capturedAt,
      );
      result = response.scan;
      await onSuccess?.call();
      final uncertain = response.scan.result?.isUncertain ?? false;
      _set(uncertain ? ScanPhase.analysisUncertain : ScanPhase.analysisSucceeded);
    } on ApiException catch (e) {
      lastErrorKind = e.kind;
      if (e.kind == ApiErrorKind.unauthorized) await onUnauthorized?.call(e);
      if (queue != null && (e.kind == ApiErrorKind.serverUnreachable || e.kind == ApiErrorKind.timeout)) {
        try {
          await queue!.save(bytes,
              extraImages: extraImages, clientRequestId: clientRequestId!, crop: crop, plot: plot, capturedAt: capturedAt);
          await onSavedOffline?.call();
          return _set(ScanPhase.savedOffline,
              msg: 'The laptop could not be reached. This photo is saved on the phone and will be analysed automatically '
                  'when the laptop is reachable — see My scans.');
        } catch (_) {
          // phone storage failed: fall through and show the connection error with "Try again"
        }
      }
      final next = switch (e.kind) {
        ApiErrorKind.modelUnavailable => ScanPhase.modelUnavailable,
        ApiErrorKind.poorImageQuality || ApiErrorKind.noLeafDetected || ApiErrorKind.invalidImage => ScanPhase.imageRejected,
        _ => ScanPhase.inferenceFailed,
      };
      _set(next, msg: e.message);
    }
  }

  /// App went to background: release the camera (Android requires it).
  Future<void> suspend() async {
    _suspended = true;
    await _closeSession();
  }

  /// App came back: reopen the camera only if it was in use.
  Future<void> resume() async {
    _suspended = false;
    if (phase == ScanPhase.cameraReady || phase == ScanPhase.cameraInitializing || phase == ScanPhase.capturing) {
      phase = ScanPhase.initial;
      await startCamera();
    }
  }

  Future<void> _closeSession() async {
    final s = session;
    session = null;
    if (s != null) await s.dispose();
  }

  static String _newRequestId() {
    final r = Random.secure();
    return List.generate(16, (_) => r.nextInt(256).toRadixString(16).padLeft(2, '0')).join();
  }

  @override
  void dispose() {
    _disposed = true;
    _closeSession();
    super.dispose();
  }
}
