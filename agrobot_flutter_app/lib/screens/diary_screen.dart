import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:share_plus/share_plus.dart';

import '../l10n.dart';
import '../services/api_client.dart';
import '../services/reminders.dart';
import '../services/voice.dart';
import '../state/session_state.dart';
import '../widgets/common.dart';

/// Reminder repeat choices: days between reminders -> label (null = one-time).
const reminderRepeats = <int?, String>{null: 'Does not repeat', 1: 'Every day', 2: 'Every 2 days', 3: 'Every 3 days', 7: 'Every week', 14: 'Every 2 weeks', 30: 'Every 30 days'};

const diaryKinds = {
  'spray': ('Spray', Icons.sanitizer_outlined),
  'fertilizer': ('Fertilizer', Icons.grass),
  'irrigation': ('Irrigation', Icons.water_drop_outlined),
  'sowing': ('Sowing', Icons.spa_outlined),
  'weeding': ('Weeding', Icons.content_cut),
  'harvest': ('Harvest', Icons.agriculture),
  'labour': ('Labour', Icons.groups_outlined),
  'sale': ('Sale (money received)', Icons.currency_rupee),
  'note': ('Note', Icons.edit_note),
};

/// Profit book: per plot (spent, earned) from diary amounts. A "sale" amount is money received, every other amount is a cost.
Map<String, (double, double)> profitByPlot(List<Map<String, dynamic>> entries) {
  final rows = <String, (double, double)>{};
  for (final e in entries) {
    final c = e['cost'];
    if (c is! num) continue;
    final (spent, earned) = rows['${e['plot']}'] ?? (0.0, 0.0);
    rows['${e['plot']}'] = e['kind'] == 'sale' ? (spent, earned + c) : (spent + c, earned);
  }
  return rows;
}

/// Money spent per activity (sales are income, not spending), biggest first.
List<(String, double)> spentByKind(List<Map<String, dynamic>> entries) {
  final sums = <String, double>{};
  for (final e in entries) {
    final c = e['cost'];
    if (c is num && e['kind'] != 'sale') sums['${e['kind']}'] = (sums['${e['kind']}'] ?? 0) + c;
  }
  return [for (final e in sums.entries) (e.key, e.value)]..sort((a, b) => b.$2.compareTo(a.$2));
}

String _rupees(num v) => '₹${v.round()}';

String _iso(DateTime d) => '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

/// Farm diary: what was done on each plot (spray, fertiliser, ...) with optional phone reminders.
class DiaryView extends StatefulWidget {
  const DiaryView({super.key});

  @override
  State<DiaryView> createState() => _DiaryViewState();
}

class _DiaryViewState extends State<DiaryView> {
  late Future<List<Map<String, dynamic>>> _future = _load();

  Future<List<Map<String, dynamic>>> _load() async {
    final entries = await context.read<SessionState>().api.diary();
    // Re-schedule upcoming reminders (new phone, reinstall, or entries added from another phone)
    for (final e in entries) {
      if (e['remind_on'] != null && mounted) {
        DiaryReminders.instance.schedule(e, title: context.tr('Farm diary reminder'), body: _reminderBody(e)).ignore();
      }
    }
    return entries;
  }

  String _reminderBody(Map<String, dynamic> e) =>
      '${e['plot']}: ${context.tr(diaryKinds[e['kind']]?.$1 ?? '${e['kind']}')}${(e['product'] ?? '').toString().isNotEmpty ? ' — ${e['product']}' : ''}';

  Future<void> _refresh() async {
    final f = _load();
    setState(() => _future = f);
    await f.catchError((_) => <Map<String, dynamic>>[]);
  }

  Future<void> _add() async {
    final saved = await showModalBottomSheet<Map<String, dynamic>>(
      context: context,
      isScrollControlled: true,
      builder: (_) => const _DiaryForm(),
    );
    if (saved == null || !mounted) return;
    final messenger = ScaffoldMessenger.of(context);
    var text = context.tr('Saved in the farm diary');
    if (saved['remind_on'] != null) {
      final ok = await DiaryReminders.instance
          .schedule(saved, title: context.tr('Farm diary reminder'), body: _reminderBody(saved))
          .catchError((_) => false);
      if (!mounted) return;
      text += ' • ${ok ? context.tr('Reminder set for {date} 8:00', {'date': saved['remind_on']}) : context.tr('Reminder date has passed')}';
    }
    messenger.showSnackBar(SnackBar(content: Text(text)));
    await _refresh();
  }

  Future<void> _calendar() async {
    final saved = await showModalBottomSheet<int>(context: context, isScrollControlled: true, builder: (_) => const _CalendarForm());
    if (saved == null || !mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(context.tr('{n} reminders added to the diary', {'n': saved}))));
    await _refresh(); // _load schedules the phone reminders for the new entries
  }

  /// Sends the diary as a CSV file (opens in Excel) through the phone's share sheet.
  Future<void> _shareRecords() async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      final csv = await context.read<SessionState>().api.exportCsv('diary');
      await SharePlus.instance.share(ShareParams(
        files: [XFile.fromData(csv, mimeType: 'text/csv', name: 'agrobotai_diary.csv')],
        fileNameOverrides: ['agrobotai_diary.csv'],
        subject: 'AGROBOTAI farm records',
      ));
    } on ApiException catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(e.message)));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text('$e')));
    }
  }

  Future<void> _delete(Map<String, dynamic> e) async {
    final yes = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(context.tr('Delete this diary entry?')),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: Text(context.tr('Cancel'))),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: Text(context.tr('Delete'))),
        ],
      ),
    );
    if (yes != true || !mounted) return;
    try {
      await context.read<SessionState>().api.deleteDiaryEntry(e['id'] as int);
      await DiaryReminders.instance.cancel(e['id'] as int).catchError((_) {});
    } on ApiException catch (err) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(err.message)));
    }
    await _refresh();
  }

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: _refresh,
      child: FutureBuilder<List<Map<String, dynamic>>>(
        future: _future,
        builder: (context, snap) {
          final add = FilledButton.icon(
              style: FilledButton.styleFrom(backgroundColor: kGreen),
              onPressed: _add,
              icon: const Icon(Icons.add),
              label: Text(context.tr('Add diary entry')));
          if (snap.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
          if (snap.hasError) {
            final e = snap.error;
            return ListView(padding: const EdgeInsets.all(16), children: [
              MessagePanel(icon: Icons.cloud_off, title: 'Could not load the diary', message: e is ApiException ? e.message : '$e'),
            ]);
          }
          final entries = snap.data!;
          final today = _iso(DateTime.now());
          final upcoming = entries.where((e) => (e['remind_on'] as String? ?? '').compareTo(today) >= 0).toList()
            ..sort((a, b) => '${a['remind_on']}'.compareTo('${b['remind_on']}'));
          final byPlot = <String, List<Map<String, dynamic>>>{};
          for (final e in entries) {
            byPlot.putIfAbsent('${e['plot']}', () => []).add(e);
          }
          return ListView(padding: const EdgeInsets.fromLTRB(12, 12, 12, 96), children: [
            add,
            OutlinedButton.icon(onPressed: _calendar, icon: const Icon(Icons.calendar_month), label: Text(context.tr('Make crop calendar'))),
            if (entries.isNotEmpty)
              TextButton.icon(
                  onPressed: _shareRecords, icon: const Icon(Icons.ios_share), label: Text(context.tr('Share records (Excel file)'))),
            const SizedBox(height: 12),
            if (entries.isEmpty)
              Text(context.tr('No diary entries yet. Record each spray, fertiliser or watering to keep track and get reminders.'),
                  textAlign: TextAlign.center, style: TextStyle(color: Colors.grey.shade700)),
            if (entries.any((e) => e['cost'] is num)) _profitCard(profitByPlot(entries), spentByKind(entries)),
            if (upcoming.isNotEmpty)
              SectionCard(title: 'Upcoming reminders', icon: Icons.alarm, children: [
                for (final e in upcoming)
                  ListTile(
                    dense: true,
                    contentPadding: EdgeInsets.zero,
                    leading: Icon(diaryKinds[e['kind']]?.$2 ?? Icons.event, color: kGreen),
                    title: Text(_reminderBody(e)),
                    trailing: Text('${e['remind_on']}', style: const TextStyle(fontWeight: FontWeight.bold)),
                  ),
              ]),
            for (final plot in byPlot.entries)
              SectionCard(title: plot.key, icon: Icons.grass, children: [
                for (final e in plot.value) _entryTile(e),
              ]),
          ]);
        },
      ),
    );
  }

  Widget _profitCard(Map<String, (double, double)> rows, List<(String, double)> byKind) {
    Widget line(String name, double spent, double earned, {bool bold = false}) {
      final profit = earned - spent;
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Row(children: [
          Expanded(
              child: Text('$name\n${context.tr('Spent')} ${_rupees(spent)} • ${context.tr('Earned')} ${_rupees(earned)}',
                  style: TextStyle(fontWeight: bold ? FontWeight.bold : FontWeight.normal))),
          Text('${profit < 0 ? '−' : ''}${_rupees(profit.abs())}',
              style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold, color: profit < 0 ? Colors.red.shade800 : kGreen)),
        ]),
      );
    }

    final spent = rows.values.fold(0.0, (a, r) => a + r.$1);
    final earned = rows.values.fold(0.0, (a, r) => a + r.$2);
    return SectionCard(title: 'Profit & expenses', icon: Icons.account_balance_wallet_outlined, children: [
      for (final r in rows.entries) line(r.key, r.value.$1, r.value.$2),
      if (rows.length > 1) ...[const Divider(), line(context.tr('All plots'), spent, earned, bold: true)],
      if (byKind.isNotEmpty && spent > 0) ...[
        const Divider(),
        Text(context.tr('Where the money goes'), style: const TextStyle(fontWeight: FontWeight.bold)),
        for (final (kind, amount) in byKind)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 3),
            child: Row(children: [
              SizedBox(width: 110, child: Text(context.tr(diaryKinds[kind]?.$1 ?? kind), overflow: TextOverflow.ellipsis)),
              Expanded(
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: LinearProgressIndicator(value: amount / spent, minHeight: 10, color: kGreen, backgroundColor: Colors.green.shade50),
                ),
              ),
              const SizedBox(width: 8),
              SizedBox(width: 84, child: Text('${_rupees(amount)} (${(100 * amount / spent).round()}%)', textAlign: TextAlign.right)),
            ]),
          ),
      ],
      Text(context.tr('Profit = money from sales − all costs written in the diary.'), style: TextStyle(fontSize: 12, color: Colors.grey.shade700)),
    ]);
  }

  Widget _entryTile(Map<String, dynamic> e) {
    final (label, icon) = diaryKinds[e['kind']] ?? ('${e['kind']}', Icons.event);
    final details = [
      if ((e['product'] ?? '').toString().isNotEmpty) '${e['product']}',
      if ((e['quantity'] ?? '').toString().isNotEmpty) '${e['quantity']}',
      if (e['cost'] != null) '${e['kind'] == 'sale' ? '+' : ''}₹${(e['cost'] as num).toStringAsFixed(0)}',
    ].join(' • ');
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: CircleAvatar(backgroundColor: Colors.green.shade50, child: Icon(icon, color: kGreen)),
      title: Text('${context.tr(label)} • ${e['done_on']}'),
      subtitle: Text([
        if (details.isNotEmpty) details,
        if ((e['note'] ?? '').toString().isNotEmpty) '${e['note']}',
        if (e['remind_on'] != null)
          '⏰ ${context.tr('Reminder')}: ${e['remind_on']}${e['repeat_days'] != null ? ' • ${context.tr(reminderRepeats[e['repeat_days']] ?? 'Every {n} days', {'n': e['repeat_days']})}' : ''}',
      ].join('\n')),
      trailing: IconButton(tooltip: context.tr('Delete'), icon: const Icon(Icons.delete_outline), onPressed: () => _delete(e)),
    );
  }
}

/// Crop calendar: crop + plot + sowing date -> preview of the dated tasks -> saved as diary reminders.
class _CalendarForm extends StatefulWidget {
  const _CalendarForm();

  @override
  State<_CalendarForm> createState() => _CalendarFormState();
}

class _CalendarFormState extends State<_CalendarForm> {
  late final Future<List<String>> _crops = context.read<SessionState>().api.calendarCrops();
  final _plot = TextEditingController();
  String? _crop;
  DateTime _sown = DateTime.now();
  Map<String, dynamic>? _preview;
  String? _error;
  bool _busy = false;

  @override
  void dispose() {
    _plot.dispose();
    super.dispose();
  }

  Future<void> _run({bool save = false}) async {
    if (_crop == null) return;
    final session = context.read<SessionState>();
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final r = await session.api.calendar(_crop!, _iso(_sown), session.language, plot: save ? _plot.text.trim() : null);
      if (!mounted) return;
      if (save) {
        Navigator.pop(context, (r['entries'] as List).length);
        return;
      }
      setState(() => _preview = r);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final tasks = (_preview?['tasks'] as List? ?? const []).cast<Map<String, dynamic>>();
    return Padding(
      padding: EdgeInsets.fromLTRB(16, 16, 16, 16 + MediaQuery.of(context).viewInsets.bottom),
      child: FutureBuilder<List<String>>(
        future: _crops,
        builder: (context, snap) {
          if (snap.hasError) return MessagePanel(icon: Icons.cloud_off, title: 'Could not load the crop list', message: '${snap.error}');
          if (!snap.hasData) return const SizedBox(height: 120, child: Center(child: CircularProgressIndicator()));
          return ListView(shrinkWrap: true, children: [
            Text(context.tr('Make crop calendar'), style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            DropdownButtonFormField<String>(
              initialValue: _crop,
              decoration: InputDecoration(labelText: context.tr('Crop')),
              items: [for (final c in snap.data!) DropdownMenuItem(value: c, child: Text(context.tr(c)))],
              onChanged: (v) => setState(() {
                _crop = v;
                _preview = null;
              }),
            ),
            TextField(controller: _plot, maxLength: 60, onChanged: (_) => setState(() {}), decoration: InputDecoration(labelText: context.tr('Plot / field name'))),
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.event),
              title: Text(context.tr('Sowing / transplanting date')),
              subtitle: Text(_iso(_sown)),
              onTap: () async {
                final d = await showDatePicker(
                    context: context, initialDate: _sown, firstDate: DateTime(DateTime.now().year - 1), lastDate: DateTime(DateTime.now().year + 2));
                if (d != null) {
                  setState(() {
                    _sown = d;
                    _preview = null;
                  });
                }
              },
            ),
            if (_error != null) Text(_error!, style: const TextStyle(color: Colors.red)),
            if (_preview != null) ...[
              Text('${_preview!['note']}', style: TextStyle(fontSize: 12, color: Colors.grey.shade700)),
              for (final t in tasks)
                ListTile(
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                  leading: Icon(diaryKinds[t['kind']]?.$2 ?? Icons.event_note, color: kGreen),
                  title: Text('${t['task']}'),
                  subtitle: Text('${t['date']} • ${context.tr('Day {n}', {'n': t['day']})}'),
                ),
            ],
            const SizedBox(height: 8),
            _preview == null
                ? FilledButton(onPressed: _crop == null || _busy ? null : _run, child: Text(context.tr('Show the calendar')))
                : FilledButton(
                    onPressed: _busy || _plot.text.trim().isEmpty ? null : () => _run(save: true),
                    child: Text(context.tr('Save as diary reminders'))),
          ]);
        },
      ),
    );
  }
}

class _DiaryForm extends StatefulWidget {
  const _DiaryForm();

  @override
  State<_DiaryForm> createState() => _DiaryFormState();
}

class _DiaryFormState extends State<_DiaryForm> {
  final _plot = TextEditingController();
  final _product = TextEditingController();
  final _quantity = TextEditingController();
  final _cost = TextEditingController();
  final _note = TextEditingController();
  String _kind = 'spray';
  DateTime _doneOn = DateTime.now();
  DateTime? _remindOn;
  int? _repeatDays;
  VoiceRecorder? _recorder;
  bool _recording = false;
  bool _transcribing = false;
  List<String> _plotNames = const [];
  bool _saving = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    context.read<SessionState>().api.plots().then((p) {
      if (mounted) setState(() => _plotNames = [for (final x in p) '${x['plot']}']);
    }).catchError((_) {});
  }

  @override
  void dispose() {
    for (final c in [_plot, _product, _quantity, _cost, _note]) {
      c.dispose();
    }
    _recorder?.dispose();
    super.dispose();
  }

  Future<DateTime?> _pick(DateTime initial, {DateTime? first}) => showDatePicker(
      context: context, initialDate: initial, firstDate: first ?? DateTime(2020), lastDate: DateTime.now().add(const Duration(days: 365)));

  /// Speak the note instead of typing: tap to record, tap again and the server's Whisper writes the words into Note.
  Future<void> _voiceNote() async {
    if (_transcribing) return;
    final api = context.read<SessionState>().api;
    try {
      if (!_recording) {
        _recorder ??= PluginVoiceRecorder();
        if (!await _recorder!.hasPermission()) {
          if (mounted) setState(() => _error = context.tr('Microphone permission is needed to ask by voice. Allow it in Settings → Apps → AGROBOTAI.'));
          return;
        }
        await _recorder!.start();
        if (mounted) setState(() => _recording = true);
        return;
      }
      setState(() {
        _recording = false;
        _transcribing = true;
      });
      final wav = await _recorder!.stop();
      if (wav == null || wav.isEmpty) return;
      final text = '${(await api.transcribe(wav))['text'] ?? ''}'.trim();
      if (text.isNotEmpty) _note.text = [_note.text.trim(), text].where((t) => t.isNotEmpty).join(' ');
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    } finally {
      if (mounted) setState(() => _transcribing = false);
    }
  }

  Future<void> _save() async {
    final cost = _cost.text.trim().isEmpty ? null : double.tryParse(_cost.text.trim());
    if (_plot.text.trim().isEmpty || (_cost.text.trim().isNotEmpty && (cost == null || cost < 0))) {
      setState(() => _error = context.tr('Enter the plot name, and the cost as a number (or leave it empty).'));
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      final entry = await context.read<SessionState>().api.addDiaryEntry({
        'plot': _plot.text.trim(),
        'kind': _kind,
        'product': _product.text.trim(),
        'quantity': _quantity.text.trim(),
        'cost': cost,
        'note': _note.text.trim(),
        'done_on': _iso(_doneOn),
        'remind_on': _remindOn == null ? null : _iso(_remindOn!),
        'repeat_days': _remindOn == null ? null : _repeatDays,
      });
      if (mounted) Navigator.pop(context, entry);
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    InputDecoration deco(String label) => InputDecoration(labelText: context.tr(label), border: const OutlineInputBorder(), isDense: true);
    return Padding(
      padding: EdgeInsets.fromLTRB(16, 16, 16, MediaQuery.of(context).viewInsets.bottom + 16),
      child: SingleChildScrollView(
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text(context.tr('Add diary entry'), style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
          const SizedBox(height: 12),
          Autocomplete<String>(
            optionsBuilder: (v) => _plotNames.where((n) => n.toLowerCase().contains(v.text.trim().toLowerCase())),
            onSelected: (v) => _plot.text = v,
            fieldViewBuilder: (context, controller, focus, _) => TextField(
              controller: controller,
              focusNode: focus,
              onChanged: (v) => _plot.text = v,
              decoration: deco('Plot / plant name'),
            ),
          ),
          const SizedBox(height: 10),
          DropdownButtonFormField<String>(
            initialValue: _kind,
            decoration: deco('What was done'),
            items: [
              for (final k in diaryKinds.entries)
                DropdownMenuItem(value: k.key, child: Row(children: [Icon(k.value.$2, size: 18), const SizedBox(width: 8), Text(context.tr(k.value.$1))])),
            ],
            onChanged: (v) => setState(() => _kind = v ?? _kind),
          ),
          const SizedBox(height: 10),
          TextField(controller: _product, decoration: deco('Product (e.g. Neem oil)')),
          const SizedBox(height: 10),
          Row(children: [
            Expanded(child: TextField(controller: _quantity, decoration: deco('Quantity'))),
            const SizedBox(width: 8),
            Expanded(
                child: TextField(
                    controller: _cost, keyboardType: const TextInputType.numberWithOptions(decimal: true), decoration: deco(_kind == 'sale' ? 'Amount received (₹)' : 'Cost (₹)'))),
          ]),
          const SizedBox(height: 10),
          TextField(
            controller: _note,
            maxLines: 2,
            decoration: deco(_recording ? 'Listening… tap the microphone to stop' : 'Note').copyWith(
              suffixIcon: _transcribing
                  ? const Padding(padding: EdgeInsets.all(12), child: SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2)))
                  : IconButton(
                      tooltip: context.tr('Speak the note'),
                      icon: Icon(_recording ? Icons.stop_circle : Icons.mic, color: _recording ? Colors.red : kGreen),
                      onPressed: _voiceNote),
            ),
          ),
          const SizedBox(height: 6),
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.event_available),
            title: Text('${context.tr('Done on')}: ${_iso(_doneOn)}'),
            onTap: () async {
              final d = await _pick(_doneOn);
              if (d != null) setState(() => _doneOn = d);
            },
          ),
          ListTile(
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.alarm),
            title: Text(_remindOn == null ? context.tr('Add a reminder (optional)') : '${context.tr('Reminder')}: ${_iso(_remindOn!)} 8:00'),
            trailing: _remindOn == null ? null : IconButton(icon: const Icon(Icons.close), onPressed: () => setState(() => _remindOn = null)),
            onTap: () async {
              final d = await _pick(_remindOn ?? DateTime.now().add(const Duration(days: 7)), first: DateTime.now());
              if (d != null) setState(() => _remindOn = d);
            },
          ),
          if (_remindOn != null)
            DropdownButtonFormField<int?>(
              initialValue: _repeatDays,
              decoration: deco('Repeat reminder'),
              items: [for (final r in reminderRepeats.entries) DropdownMenuItem(value: r.key, child: Text(context.tr(r.value)))],
              onChanged: (v) => setState(() => _repeatDays = v),
            ),
          if (_error != null) Text(_error!, style: TextStyle(color: Colors.red.shade800)),
          const SizedBox(height: 8),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: kGreen, padding: const EdgeInsets.symmetric(vertical: 14)),
            onPressed: _saving ? null : _save,
            child: Text(context.tr(_saving ? 'Saving…' : 'Save')),
          ),
        ]),
      ),
    );
  }
}
