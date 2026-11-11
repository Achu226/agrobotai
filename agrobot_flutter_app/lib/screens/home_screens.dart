import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../l10n.dart';

import '../models/models.dart';
import '../services/api_client.dart';
import '../state/session_state.dart';
import '../widgets/common.dart';
import '../widgets/connection_indicator.dart';
import '../widgets/language_menu.dart';
import 'chat_screen.dart';
import 'history_screen.dart';
import 'scan_screen.dart';
import 'sensors_screen.dart';
import 'library_screen.dart';
import 'weather_screen.dart';

AppBar _appBar(BuildContext context, String subtitle) {
  final s = context.watch<SessionState>();
  return AppBar(
    backgroundColor: kGreen,
    foregroundColor: Colors.white,
    titleSpacing: 12,
    title: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(s.user?.displayName ?? '', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
      Text(context.tr(subtitle), style: const TextStyle(fontSize: 11, color: Colors.white70)),
    ]),
    actions: [
      const ConnectionIndicator(),
      if (!(s.user?.isAdmin ?? false))
        IconButton(
          tooltip: context.tr(s.gardenMode ? 'Home garden mode (tap for farm mode)' : 'Farm mode (tap for home garden mode)'),
          icon: Icon(s.gardenMode ? Icons.yard_outlined : Icons.agriculture_outlined),
          onPressed: () {
            final messenger = ScaffoldMessenger.of(context);
            final text = context.tr(s.gardenMode
                ? 'Farm mode: field sizes in acres, market prices and fertilizer bags are shown.'
                : 'Home garden mode: spray doses per litre for pots; market prices and fertilizer bags are hidden.');
            s.setGardenMode(!s.gardenMode);
            messenger.showSnackBar(SnackBar(content: Text(text)));
          },
        ),
      const LanguageMenu(color: Colors.white),
      IconButton(tooltip: context.tr('Sign out'), icon: const Icon(Icons.logout), onPressed: () => s.signOut()),
    ],
  );
}

class FarmerHome extends StatefulWidget {
  const FarmerHome({super.key});

  @override
  State<FarmerHome> createState() => _FarmerHomeState();
}

class _FarmerHomeState extends State<FarmerHome> {
  int _tab = 0;
  final _historyKey = GlobalKey<ScanListState>();

  Future<void> _openScanner() async {
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => const ScanScreen()));
    _historyKey.currentState?.refresh();
  }

  @override
  Widget build(BuildContext context) {
    final tabs = [
      ScanList(key: _historyKey),
      const ChatScreen(),
      const WeatherScreen(),
      const SensorsScreen(),
      const LibraryScreen(),
    ];
    return Scaffold(
      appBar: _appBar(context, 'Farmer'),
      body: tabs[_tab],
      // The chat tab has its own input bar at the bottom; the scan button would cover it
      floatingActionButton: _tab == 1
          ? null
          : FloatingActionButton.extended(
              backgroundColor: kGreen,
              foregroundColor: Colors.white,
              onPressed: _openScanner,
              icon: const Icon(Icons.camera_alt),
              label: Text(context.tr('Scan leaf')),
            ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: (i) => setState(() => _tab = i),
        destinations: [
          NavigationDestination(icon: const Icon(Icons.history), label: context.tr('My scans')),
          NavigationDestination(icon: const Icon(Icons.chat_outlined), label: context.tr('Ask AI')),
          NavigationDestination(icon: const Icon(Icons.wb_sunny_outlined), label: context.tr('Weather')),
          NavigationDestination(icon: const Icon(Icons.sensors), label: context.tr('IoT')),
          NavigationDestination(icon: const Icon(Icons.menu_book_outlined), label: context.tr('Guide')),
        ],
      ),
    );
  }
}

class AdminHome extends StatefulWidget {
  const AdminHome({super.key});

  @override
  State<AdminHome> createState() => _AdminHomeState();
}

class _AdminHomeState extends State<AdminHome> {
  int _tab = 0;

  @override
  Widget build(BuildContext context) {
    final tabs = [
      const ScanList(key: ValueKey('pending'), reviewStatus: 'pending', emptyMessage: 'No scans are waiting for review.'),
      const ScanList(key: ValueKey('all'), includeFailed: true, emptyMessage: 'No scans have been submitted yet.'),
      const _UsersAndStats(),
      const SensorsScreen(),
    ];
    return Scaffold(
      appBar: _appBar(context, 'Administrator'),
      body: tabs[_tab],
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: (i) => setState(() => _tab = i),
        destinations: [
          const NavigationDestination(icon: Icon(Icons.pending_actions), label: 'Review'),
          NavigationDestination(icon: const Icon(Icons.list_alt), label: context.tr('All scans')),
          const NavigationDestination(icon: Icon(Icons.people_outline), label: 'Users'),
          NavigationDestination(icon: const Icon(Icons.sensors), label: context.tr('IoT')),
        ],
      ),
    );
  }
}

class _UsersAndStats extends StatefulWidget {
  const _UsersAndStats();

  @override
  State<_UsersAndStats> createState() => _UsersAndStatsState();
}

class _UsersAndStatsState extends State<_UsersAndStats> {
  late Future<(Map<String, dynamic>, List<AppUser>)> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<(Map<String, dynamic>, List<AppUser>)> _load() async {
    final api = context.read<SessionState>().api;
    return (await api.adminStats(), await api.adminUsers());
  }

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: () async {
        final f = _load();
        setState(() => _future = f);
        await f.catchError((_) => (<String, dynamic>{}, <AppUser>[]));
      },
      child: FutureBuilder<(Map<String, dynamic>, List<AppUser>)>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
          if (snap.hasError) {
            final e = snap.error;
            return ListView(padding: const EdgeInsets.all(16), children: [
              MessagePanel(icon: Icons.error_outline, title: 'Could not load users', message: e is ApiException ? e.message : '$e'),
            ]);
          }
          final (stats, users) = snap.data!;
          return ListView(padding: const EdgeInsets.all(16), children: [
            SectionCard(title: 'Totals (from the server database)', icon: Icons.insights, children: [
              InfoRow('Successful scans', '${stats['successful_scans']}'),
              InfoRow('Pending review', '${stats['pending_review']}'),
              InfoRow('Approved / rejected', '${stats['approved']} / ${stats['rejected']}'),
              InfoRow('Failed attempts', '${stats['failed_attempts']} (not counted as scans)'),
              InfoRow('Farmers / admins', '${stats['farmers']} / ${stats['admins']}'),
            ]),
            SectionCard(title: 'Accounts', icon: Icons.people, children: [
              if (users.isEmpty) const Text('No accounts.'),
              for (final u in users)
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: Icon(u.isAdmin ? Icons.admin_panel_settings : Icons.agriculture, color: kGreen),
                  title: Text(u.displayName),
                  subtitle: Text('@${u.username} • ${u.role}${u.location.isNotEmpty ? ' • ${u.location}' : ''}'),
                  trailing: Text('${u.scanCount ?? 0} scans'),
                ),
            ]),
          ]);
        },
      ),
    );
  }
}
