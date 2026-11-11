import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

import '../l10n.dart';

import '../services/api_client.dart';
import '../state/session_state.dart';
import '../widgets/common.dart';
import '../widgets/language_menu.dart';
import 'diagnostics_screen.dart';

/// Sign in against the laptop server. The role (farmer / admin) comes from the server account,
/// not from anything chosen on this screen.
class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _form = GlobalKey<FormState>();
  final _username = TextEditingController();
  final _password = TextEditingController();
  final _fullName = TextEditingController();
  final _farm = TextEditingController();
  final _location = TextEditingController();
  bool _register = false;
  bool _busy = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    // After a sign-out the health may be stale; connect() also searches the Wi-Fi if needed
    WidgetsBinding.instance.addPostFrameCallback((_) => context.read<SessionState>().connect());
  }

  @override
  void dispose() {
    for (final c in [_username, _password, _fullName, _farm, _location]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _submit() async {
    if (_busy || !_form.currentState!.validate()) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    final s = context.read<SessionState>();
    try {
      if (_register) {
        await s.register(
            username: _username.text, password: _password.text, fullName: _fullName.text, farmName: _farm.text, location: _location.text);
      } else {
        await s.signIn(_username.text, _password.text);
      }
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = context.watch<SessionState>();
    final h = s.health;
    return Scaffold(
      body: Container(
        decoration: BoxDecoration(
            gradient: LinearGradient(
                begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Colors.green.shade800, Colors.teal.shade900])),
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(20),
              child: Card(
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Form(
                    key: _form,
                    child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                      ClipRRect(
                          borderRadius: BorderRadius.circular(18), child: Image.asset('assets/icon/app_icon.png', width: 72, height: 72)),
                      Text('AGROBOTAI',
                          textAlign: TextAlign.center,
                          style: GoogleFonts.poppins(fontSize: 26, fontWeight: FontWeight.bold, color: kDarkGreen)),
                      Text(context.tr('Crop disease & pest detection'), textAlign: TextAlign.center, style: TextStyle(color: Colors.grey.shade600)),
                      const Center(child: LanguageMenu(color: kDarkGreen, showName: true)),
                      const SizedBox(height: 12),
                      ListTile(
                        dense: true,
                        contentPadding: EdgeInsets.zero,
                        leading: Icon(h != null ? Icons.cloud_done : Icons.cloud_off, color: h != null ? kGreen : Colors.red),
                        title: Text(s.serverUrl, style: const TextStyle(fontSize: 13)),
                        subtitle: Text(s.discovering
                            ? context.tr('Looking for the AGROBOTAI laptop on this Wi-Fi…')
                            : s.checkingHealth
                                ? context.tr('Checking server…')
                                : h != null
                                    ? '${context.tr('Server reachable')} • ${context.tr('disease model')} ${context.tr(h.disease.ready ? 'ready' : 'unavailable')} • ${context.tr('pest model')} ${context.tr(h.pest.ready ? 'ready' : 'unavailable')}'
                                    : (s.discoveryMessage ?? s.healthError ?? context.tr('Not checked'))),
                        trailing: TextButton(
                          onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const DiagnosticsScreen())),
                          child: Text(context.tr('Change')),
                        ),
                      ),
                      if (h == null && !s.discovering && !s.checkingHealth)
                        Align(
                          alignment: Alignment.centerLeft,
                          child: TextButton.icon(
                            onPressed: s.findServer,
                            icon: const Icon(Icons.wifi_find),
                            label: Text(context.tr('Search Wi-Fi for the server')),
                          ),
                        ),
                      if (s.discovering) const LinearProgressIndicator(),
                      if (s.signedOutReason != null) Text(context.tr(s.signedOutReason!), style: TextStyle(color: Colors.orange.shade900)),
                      const SizedBox(height: 8),
                      TextFormField(
                        controller: _username,
                        autofillHints: const [AutofillHints.username],
                        decoration:
                            InputDecoration(labelText: context.tr('Username'), prefixIcon: const Icon(Icons.person), border: const OutlineInputBorder()),
                        validator: (v) => (v ?? '').trim().length < 3 ? context.tr('At least 3 characters') : null,
                      ),
                      const SizedBox(height: 12),
                      TextFormField(
                        controller: _password,
                        obscureText: true,
                        autofillHints: [_register ? AutofillHints.newPassword : AutofillHints.password],
                        decoration:
                            InputDecoration(labelText: context.tr('Password'), prefixIcon: const Icon(Icons.lock), border: const OutlineInputBorder()),
                        validator: (v) =>
                            (v ?? '').length < (_register ? 8 : 1) ? context.tr(_register ? 'At least 8 characters' : 'Enter your password') : null,
                        onFieldSubmitted: (_) => _submit(),
                      ),
                      if (_register) ...[
                        const SizedBox(height: 12),
                        TextFormField(
                            controller: _fullName, decoration: InputDecoration(labelText: context.tr('Full name'), border: const OutlineInputBorder())),
                        const SizedBox(height: 12),
                        TextFormField(
                            controller: _farm,
                            decoration: InputDecoration(labelText: context.tr('Farm name (optional)'), border: const OutlineInputBorder())),
                        const SizedBox(height: 12),
                        TextFormField(
                            controller: _location,
                            decoration: InputDecoration(labelText: context.tr('Village / district (optional)'), border: const OutlineInputBorder())),
                      ],
                      if (_error != null) ...[
                        const SizedBox(height: 12),
                        MessagePanel(
                            icon: Icons.error_outline, title: _register ? 'Registration failed' : 'Sign-in failed', message: _error),
                      ],
                      const SizedBox(height: 16),
                      FilledButton(
                        style: FilledButton.styleFrom(backgroundColor: kGreen, padding: const EdgeInsets.symmetric(vertical: 14)),
                        onPressed: _busy ? null : _submit,
                        child: _busy
                            ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                            : Text(context.tr(_register ? 'Create farmer account' : 'Sign in')),
                      ),
                      if (h?.signupEnabled ?? true)
                        TextButton(
                          onPressed: _busy ? null : () => setState(() => _register = !_register),
                          child: Text(context.tr(_register ? 'I already have an account' : 'New farmer? Create an account')),
                        ),
                      Text(context.tr('Administrator accounts are created on the server laptop.'),
                          textAlign: TextAlign.center, style: const TextStyle(fontSize: 12)),
                    ]),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
