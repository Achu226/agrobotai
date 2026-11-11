/// Typed views over the server's JSON. Fields the server did not send stay null and are
/// shown as "Not available" — never filled with defaults that look like real values.
library;

Map<String, dynamic> _map(Object? v) => v is Map<String, dynamic> ? v : const {};
double? _num(Object? v) => v is num ? v.toDouble() : null;

class AppUser {
  AppUser(
      {required this.id,
      required this.username,
      required this.role,
      this.fullName = '',
      this.farmName = '',
      this.location = '',
      this.scanCount});

  factory AppUser.fromJson(Map<String, dynamic> j) => AppUser(
        id: j['id'] as int,
        username: j['username'] as String,
        role: j['role'] as String,
        fullName: (j['full_name'] as String?) ?? '',
        farmName: (j['farm_name'] as String?) ?? '',
        location: (j['location'] as String?) ?? '',
        scanCount: j['scan_count'] as int?,
      );

  final int id;
  final String username;
  final String role;
  final String fullName;
  final String farmName;
  final String location;
  final int? scanCount;

  bool get isAdmin => role == 'admin';
  String get displayName => fullName.isNotEmpty ? fullName : username;

  Map<String, dynamic> toJson() =>
      {'id': id, 'username': username, 'role': role, 'full_name': fullName, 'farm_name': farmName, 'location': location};
}

class AuthSession {
  AuthSession({required this.token, required this.user, this.expiresAt});

  factory AuthSession.fromJson(Map<String, dynamic> j) => AuthSession(
      token: j['token'] as String, user: AppUser.fromJson(j['user'] as Map<String, dynamic>), expiresAt: j['expires_at'] as String?);

  final String token;
  final AppUser user;
  final String? expiresAt;
}

class ModelHealth {
  ModelHealth({required this.ready, required this.state, this.version, this.error, this.numClasses});

  factory ModelHealth.fromJson(Map<String, dynamic> j) => ModelHealth(
        ready: j['ready'] == true,
        state: (j['state'] as String?) ?? 'unknown',
        version: j['version'] as String?,
        error: j['error'] as String?,
        numClasses: j['num_classes'] as int?,
      );

  final bool ready;
  final String state;
  final String? version;
  final String? error;
  final int? numClasses;
}

class ServerHealth {
  ServerHealth({required this.disease, required this.pest, required this.device, this.gpu, this.signupEnabled = false, this.serverTime});

  factory ServerHealth.fromJson(Map<String, dynamic> j) {
    final models = _map(j['models']);
    final runtime = _map(j['runtime']);
    return ServerHealth(
      disease: ModelHealth.fromJson(_map(models['disease'])),
      pest: ModelHealth.fromJson(_map(models['pest'])),
      device: (runtime['inference_device'] as String?) ?? 'unknown',
      gpu: runtime['gpu'] as String?,
      signupEnabled: j['farmer_signup_enabled'] == true,
      serverTime: j['time'] as String?,
    );
  }

  final ModelHealth disease;
  final ModelHealth pest;
  final String device;
  final String? gpu;
  final bool signupEnabled;
  final String? serverTime;

  bool get anyModelReady => disease.ready || pest.ready;
}

/// One analysis section (disease or pest) exactly as the server reported it.
class ModelFinding {
  ModelFinding(this.raw);

  final Map<String, dynamic> raw;

  String get state => (raw['state'] as String?) ?? 'unknown';
  String? get label => raw['label'] as String?;
  String? get displayName => raw['display_name'] as String?;
  String? get message => raw['message'] as String?;
  double? get calibratedConfidence => _num(raw['calibrated_confidence']);
  double? get modelScore => _num(raw['model_score']);
  double? get inferenceMs => _num(raw['inference_ms']);
  String? get modelVersion => _map(raw['model'])['version'] as String?;
  String? get topPrediction => raw['top_prediction'] as String?;
  List<String> get uncertaintyReasons => ((raw['uncertainty_reasons'] as List?) ?? const []).cast<String>();
  List<Map<String, dynamic>> get topPredictions => ((raw['top_predictions'] as List?) ?? const []).cast<Map<String, dynamic>>();
}

class AnalysisResult {
  AnalysisResult(this.raw);

  final Map<String, dynamic> raw;

  String get summaryState => (_map(raw['summary'])['state'] as String?) ?? 'unknown';
  String get summaryMessage => (_map(raw['summary'])['message'] as String?) ?? '';
  ModelFinding get disease => ModelFinding(_map(raw['disease']));
  ModelFinding get pest => ModelFinding(_map(raw['pest']));
  Map<String, dynamic> get severity => _map(raw['severity']);
  Map<String, dynamic>? get healthIndex => raw['health_index'] is Map<String, dynamic> ? raw['health_index'] as Map<String, dynamic> : null;
  Map<String, dynamic> get advice => _map(raw['advice']);
  Map<String, dynamic>? get gradcam => raw['gradcam'] is Map<String, dynamic> ? raw['gradcam'] as Map<String, dynamic> : null;
  String? get inferredAt => raw['inferred_at'] as String?;
  double? get totalMs => _num(_map(raw['timing_ms'])['total']);

  bool get isUncertain => summaryState == 'uncertain';

  List<String> get adviceItems => [
        for (final k in ['immediate_actions', 'next_24_48_hours', 'next_7_days', 'prevention', 'items'])
          ...((advice[k] as List?) ?? const []).map((e) => e.toString()),
      ];
}

class ScanRecord {
  ScanRecord(this.raw);

  factory ScanRecord.fromJson(Map<String, dynamic> j) => ScanRecord(j);

  final Map<String, dynamic> raw;

  int get id => raw['id'] as int;
  String? get username => raw['username'] as String?;
  String? get farmerName => (raw['full_name'] as String?)?.isNotEmpty == true ? raw['full_name'] as String : username;
  String? get capturedAt => raw['captured_at'] as String?;
  String get receivedAt => (raw['received_at'] as String?) ?? '';
  String? get cropSelected => raw['crop_selected'] as String?;
  String? get plot => (raw['plot'] as String?)?.isNotEmpty == true ? raw['plot'] as String : null;
  String? get cropReported => raw['crop_reported'] as String?;
  String get inferenceStatus => (raw['inference_status'] as String?) ?? 'unknown';
  String? get summaryState => raw['summary_state'] as String?;
  String? get diseaseLabel => raw['disease_label'] as String?;
  String? get diseaseState => raw['disease_state'] as String?;
  double? get diseaseConfidence => _num(raw['disease_confidence']);
  String? get pestLabel => raw['pest_label'] as String?;
  String? get pestState => raw['pest_state'] as String?;
  double? get healthIndex => _num(raw['health_index']);
  String get reviewStatus => (raw['review_status'] as String?) ?? 'pending';
  String? get reviewer => raw['reviewer_username'] as String?;
  String? get reviewedAt => raw['reviewed_at'] as String?;
  String? get reviewComment => raw['review_comment'] as String?;
  String? get error => raw['error'] as String?;
  bool get hasImage => raw['has_image'] == true;
  Map<String, dynamic> get modelVersions => _map(raw['model_versions']);
  AnalysisResult? get result => raw['result'] is Map<String, dynamic> ? AnalysisResult(raw['result'] as Map<String, dynamic>) : null;

  String get headline {
    if (inferenceStatus == 'failed') return 'Failed attempt';
    return switch (summaryState) {
      'uncertain' => 'Uncertain — no reliable diagnosis',
      'no_supported_condition_detected' => 'No supported condition detected',
      'unsupported_crop' => 'Crop not supported by the model',
      _ => [if (diseaseLabel != null && diseaseState == 'disease_detected') diseaseLabel, if (pestLabel != null) pestLabel]
          .whereType<String>()
          .join(' + ')
          .ifEmpty(diseaseLabel ?? 'Analysis saved'),
    };
  }
}

class AnalyzeResponse {
  AnalyzeResponse({required this.scan, required this.duplicate});

  factory AnalyzeResponse.fromJson(Map<String, dynamic> j) =>
      AnalyzeResponse(scan: ScanRecord.fromJson(j['scan'] as Map<String, dynamic>), duplicate: j['duplicate'] == true);

  final ScanRecord scan;
  final bool duplicate;
}

extension on String {
  String ifEmpty(String other) => isEmpty ? other : this;
}

/// The 12 advice languages (same codes as the server's src/languages.py): (code, native name, English name).
const kLanguages = <(String, String, String)>[
  ('ta', 'தமிழ்', 'Tamil'),
  ('en', 'English', 'English'),
  ('hi', 'हिन्दी', 'Hindi'),
  ('te', 'తెలుగు', 'Telugu'),
  ('kn', 'ಕನ್ನಡ', 'Kannada'),
  ('ml', 'മലയാളം', 'Malayalam'),
  ('mr', 'मराठी', 'Marathi'),
  ('bn', 'বাংলা', 'Bengali'),
  ('gu', 'ગુજરાતી', 'Gujarati'),
  ('pa', 'ਪੰਜਾਬੀ', 'Punjabi'),
  ('or', 'ଓଡ଼ିଆ', 'Odia'),
  ('ur', 'اردو', 'Urdu'),
];

String languageLabel(String code) {
  for (final (c, native, english) in kLanguages) {
    if (c == code) return native == english ? english : '$native ($english)';
  }
  return code;
}
