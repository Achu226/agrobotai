import 'dart:typed_data';

import 'package:camera/camera.dart';
import 'package:flutter/material.dart';
import 'package:permission_handler/permission_handler.dart';

enum CameraPermission { granted, denied, permanentlyDenied, restricted }

enum FlashSetting { off, auto, torch }

class CameraUnavailableException implements Exception {
  CameraUnavailableException(this.message);
  final String message;

  @override
  String toString() => message;
}

/// One open camera. Implemented by [PluginCameraSession] on devices and by fakes in tests.
abstract class CameraSession {
  String get lensName;
  bool get isInitialized;
  bool get supportsFlash;
  Future<void> initialize();
  Future<Uint8List> takePicture();
  Future<void> setFlash(FlashSetting mode);
  Widget buildPreview();
  Future<void> dispose();
}

/// Access to the device cameras and the camera permission.
abstract class CameraBackend {
  Future<CameraPermission> requestPermission();
  Future<void> openPermissionSettings();

  /// Cameras ordered rear-first.
  Future<List<CameraDescription>> availableLenses();
  CameraSession open(CameraDescription description);
}

class PluginCameraBackend implements CameraBackend {
  const PluginCameraBackend();

  @override
  Future<CameraPermission> requestPermission() async {
    final status = await Permission.camera.request();
    if (status.isGranted || status.isLimited) return CameraPermission.granted;
    if (status.isPermanentlyDenied) return CameraPermission.permanentlyDenied;
    if (status.isRestricted) return CameraPermission.restricted;
    return CameraPermission.denied;
  }

  @override
  Future<void> openPermissionSettings() => openAppSettings();

  @override
  Future<List<CameraDescription>> availableLenses() async {
    final cams = await availableCameras();
    int rank(CameraDescription c) => switch (c.lensDirection) {
          CameraLensDirection.back => 0,
          CameraLensDirection.external => 1,
          CameraLensDirection.front => 2,
        };
    return [...cams]..sort((a, b) => rank(a).compareTo(rank(b)));
  }

  @override
  CameraSession open(CameraDescription description) => PluginCameraSession(description);
}

class PluginCameraSession implements CameraSession {
  PluginCameraSession(this.description)
      : controller = CameraController(description, ResolutionPreset.high, enableAudio: false, imageFormatGroup: ImageFormatGroup.jpeg);

  final CameraDescription description;
  final CameraController controller;

  @override
  String get lensName => switch (description.lensDirection) {
        CameraLensDirection.back => 'Rear camera',
        CameraLensDirection.front => 'Front camera',
        CameraLensDirection.external => 'External camera',
      };

  @override
  bool get isInitialized => controller.value.isInitialized;

  // Rear lenses on Android phones have a flash; the plugin reports an error if not, which we surface.
  @override
  bool get supportsFlash => description.lensDirection == CameraLensDirection.back;

  @override
  Future<void> initialize() => controller.initialize();

  @override
  Future<Uint8List> takePicture() async => (await controller.takePicture()).readAsBytes();

  @override
  Future<void> setFlash(FlashSetting mode) => controller.setFlashMode(switch (mode) {
        FlashSetting.off => FlashMode.off,
        FlashSetting.auto => FlashMode.auto,
        FlashSetting.torch => FlashMode.torch,
      });

  @override
  Widget buildPreview() {
    final size = controller.value.previewSize;
    if (size == null) return CameraPreview(controller);
    // previewSize is reported in landscape; swap for a portrait cover-fit without distortion
    return ClipRect(
      child: FittedBox(
        fit: BoxFit.cover,
        child: SizedBox(width: size.height, height: size.width, child: CameraPreview(controller)),
      ),
    );
  }

  @override
  Future<void> dispose() => controller.dispose();
}
