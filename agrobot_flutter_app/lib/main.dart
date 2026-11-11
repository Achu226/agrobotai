import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:provider/provider.dart';

import 'l10n.dart';
import 'screens/home_screens.dart';
import 'screens/login_screen.dart';
import 'state/alerts_state.dart';
import 'state/session_state.dart';
import 'theme.dart';

Future<void> main() async {
  // Release builds show a plain black screen when startup throws; show the error instead.
  var started = false;
  runZonedGuarded(() async {
    WidgetsFlutterBinding.ensureInitialized();
    ErrorWidget.builder = (details) => _ErrorText('${details.exception}');
    final session = await SessionState.load();
    runApp(ChangeNotifierProvider.value(value: session, child: const AgrobotApp()));
    started = true;
  }, (error, stack) {
    // Once running, a stray background error (e.g. a request while the server is off) must not replace the app
    if (started) {
      debugPrint('Uncaught error: $error\n$stack');
      return;
    }
    runApp(MaterialApp(home: Scaffold(body: SafeArea(child: _ErrorText('AGROBOTAI could not start:\n$error\n\n$stack')))));
  });
}

class _ErrorText extends StatelessWidget {
  const _ErrorText(this.message);

  final String message;

  @override
  Widget build(BuildContext context) => Material(
        color: Colors.white,
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Text(message, style: const TextStyle(color: Colors.red, fontSize: 13), textDirection: TextDirection.ltr),
        ),
      );
}

class AgrobotApp extends StatelessWidget {
  const AgrobotApp({super.key});

  @override
  Widget build(BuildContext context) {
    final language = context.watch<SessionState>().language;
    return MaterialApp(
      title: 'AGROBOTAI',
      // The language picker switches the whole app; untranslated languages show English UI text
      locale: Locale(translatedLanguages.contains(language) ? language : 'en'),
      supportedLocales: [for (final code in translatedLanguages) Locale(code)],
      localizationsDelegates: GlobalMaterialLocalizations.delegates,
      debugShowCheckedModeBanner: false,
      theme: agrobotTheme(context),
      builder: largerText,
      home: const AuthGate(),
    );
  }
}

/// Routes by the role stored on the server account (confirmed via /api/v1/auth/me on start).
class AuthGate extends StatefulWidget {
  const AuthGate({super.key});

  @override
  State<AuthGate> createState() => _AuthGateState();
}

class _AuthGateState extends State<AuthGate> {
  final _alerts = AlertsState();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      final s = context.read<SessionState>();
      await s.connect(); // finds the laptop (USB or Wi-Fi) if the saved address does not answer
      await s.refreshUser();
      if (mounted) _alerts.start(s, (a) => alertText(context, a), context.tr('Field alert'));
    });
  }

  @override
  void dispose() {
    _alerts.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final s = context.watch<SessionState>();
    if (!s.isSignedIn) return const LoginScreen();
    return ChangeNotifierProvider.value(value: _alerts, child: s.user!.isAdmin ? const AdminHome() : const FarmerHome());
  }
}
