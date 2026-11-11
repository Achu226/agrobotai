import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../l10n.dart';
import '../services/api_client.dart';
import '../state/session_state.dart';
import '../widgets/common.dart';
import '../widgets/weather_widgets.dart';

/// Weather like a weather app (now, next 24 hours, 7 days) + watering advice + disease risk.
/// Data comes from the laptop (Open-Meteo); nothing is simulated.
class WeatherScreen extends StatefulWidget {
  const WeatherScreen({super.key});

  @override
  State<WeatherScreen> createState() => _WeatherScreenState();
}

class _WeatherScreenState extends State<WeatherScreen> {
  late final TextEditingController _location;
  Map<String, dynamic>? _data;
  String? _error;
  bool _loading = false;
  String _loaded = '';

  @override
  void initState() {
    super.initState();
    final user = context.read<SessionState>().user;
    _location = TextEditingController(text: (user?.location.isNotEmpty ?? false) ? user!.location : '');
    if (_location.text.isNotEmpty) WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  @override
  void dispose() {
    _location.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    final place = _location.text.trim();
    if (place.length < 2) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final d = await context.read<SessionState>().api.weather(place);
      setState(() {
        _data = d;
        _loaded = place;
      });
    } on ApiException catch (e) {
      setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final d = _data;
    final weather = d?['weather'] as Map<String, dynamic>?;
    final current = weather?['current'] as Map<String, dynamic>?;
    final risk = d?['risk_analysis'] as Map<String, dynamic>?;
    final forecast = (weather?['forecast'] as List?)?.cast<Map<String, dynamic>>() ?? const [];
    final hourly = (weather?['hourly'] as List?)?.cast<Map<String, dynamic>>() ?? const [];
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(padding: const EdgeInsets.all(16), children: [
        TextField(
          controller: _location,
          textInputAction: TextInputAction.search,
          onSubmitted: (_) => _load(),
          decoration: InputDecoration(
            labelText: context.tr('Farm location (town or district)'),
            prefixIcon: const Icon(Icons.location_on),
            suffixIcon: IconButton(icon: const Icon(Icons.search), onPressed: _load),
            border: const OutlineInputBorder(),
          ),
        ),
        const SizedBox(height: 16),
        if (_loading) const Center(child: CircularProgressIndicator()),
        if (_error != null) MessagePanel(icon: Icons.cloud_off, title: 'Weather unavailable', message: _error),
        if (d != null && d['ok'] != true)
          MessagePanel(icon: Icons.cloud_off, title: 'Weather unavailable', message: '${d['error'] ?? ''}', color: Colors.grey),
        if (d != null && d['ok'] == true && current != null) ...[
          _NowCard(weather: weather!, current: current, today: forecast.isNotEmpty ? forecast.first : null),
          const SizedBox(height: 12),
          if (hourly.isNotEmpty) _HourlyStrip(hours: hourly),
          if (forecast.isNotEmpty) _DailyList(days: forecast),
          const NearbyAlertsCard(),
          IrrigationCard(key: ValueKey(_loaded), location: _loaded),
          SprayPlanCard(key: ValueKey('spray$_loaded'), location: _loaded),
          if (!context.watch<SessionState>().gardenMode) ...[const MarketPricesCard(), const FertilizerCard()],
          if (risk != null && risk['ok'] == true)
            SectionCard(title: 'Disease risk from weather', icon: Icons.coronavirus_outlined, children: [
              InfoRow('Highest risk', '${risk['highest_risk_disease']} (${risk['risk_value']}/100, ${risk['risk_level']})'),
              Text('${risk['recommended_action']}'),
              if (risk['warning'] != null) Text('${risk['warning']}', style: TextStyle(color: Colors.red.shade800)),
              const SizedBox(height: 4),
              Text(context.tr('Risk is a rule-based estimate from temperature, humidity and rain; it is not a diagnosis.'),
                  style: const TextStyle(fontSize: 12, fontStyle: FontStyle.italic)),
            ]),
          Text(context.tr('Source: {provider} • fetched {time}', {'provider': d['provider'], 'time': shortTime(d['fetched_at'] as String?)}),
              style: const TextStyle(fontSize: 12, color: Colors.black54)),
        ],
        if (d == null && !_loading && _error == null)
          Text(context.tr('Enter a location to fetch the current weather.'), style: TextStyle(color: Colors.grey.shade700)),
      ]),
    );
  }
}

class _NowCard extends StatelessWidget {
  const _NowCard({required this.weather, required this.current, this.today});

  final Map<String, dynamic> weather;
  final Map<String, dynamic> current;
  final Map<String, dynamic>? today;

  @override
  Widget build(BuildContext context) {
    final day = current['is_day'] != false;
    final (icon, color) = weatherIcon(current['weather_code'], day: day);
    final rainy = icon == Icons.water_drop || icon == Icons.grain || icon == Icons.thunderstorm;
    final colors = !day
        ? [Colors.indigo.shade800, Colors.indigo.shade400]
        : rainy
            ? [Colors.blueGrey.shade700, Colors.blue.shade400]
            : [Colors.lightBlue.shade600, Colors.orange.shade300];
    const white = TextStyle(color: Colors.white);
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(borderRadius: BorderRadius.circular(20), gradient: LinearGradient(colors: colors)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('${weather['location']}${(weather['region'] ?? '').toString().isNotEmpty ? ', ${weather['region']}' : ''}',
            style: white.copyWith(fontSize: 16, fontWeight: FontWeight.w600)),
        Row(children: [
          Text('${(current['temp_c'] as num).round()}°', style: white.copyWith(fontSize: 64, fontWeight: FontWeight.w300)),
          const SizedBox(width: 12),
          Icon(icon, size: 64, color: day && !rainy ? Colors.yellow.shade300 : Colors.white),
        ]),
        Text(context.tr('${current['condition']}'), style: white.copyWith(fontSize: 18)),
        if (today != null)
          Text('↑ ${(today!['max_temp_c'] as num).round()}°  ↓ ${(today!['min_temp_c'] as num).round()}°', style: white),
        const SizedBox(height: 12),
        Wrap(spacing: 16, runSpacing: 6, children: [
          _stat(Icons.water_drop_outlined, '${context.tr('Humidity')} ${current['humidity']}%'),
          _stat(Icons.air, '${context.tr('Wind')} ${current['wind_kph']} km/h'),
          _stat(Icons.umbrella_outlined, '${context.tr('Rain (now)')} ${current['precipitation_mm']} mm'),
          if (current['uv_index'] != null) _stat(Icons.wb_sunny_outlined, 'UV ${current['uv_index']}'),
        ]),
      ]),
    );
  }

  Widget _stat(IconData icon, String text) => Row(mainAxisSize: MainAxisSize.min, children: [
        Icon(icon, size: 16, color: Colors.white70),
        const SizedBox(width: 4),
        Text(text, style: const TextStyle(color: Colors.white)),
      ]);
}

class _HourlyStrip extends StatelessWidget {
  const _HourlyStrip({required this.hours});

  final List<Map<String, dynamic>> hours;

  @override
  Widget build(BuildContext context) {
    return SectionCard(title: 'Next 24 hours', icon: Icons.schedule, children: [
      SizedBox(
        height: 104,
        child: ListView.separated(
          scrollDirection: Axis.horizontal,
          itemCount: hours.length,
          separatorBuilder: (_, __) => const SizedBox(width: 14),
          itemBuilder: (context, i) {
            final h = hours[i];
            final (icon, color) = weatherIcon(h['weather_code'], day: h['is_day'] != false);
            final rain = (h['chance_of_rain'] as num?) ?? 0;
            return Column(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
              Text(i == 0 ? context.tr('Now') : '${h['time']}'.substring(11, 16), style: const TextStyle(fontSize: 12)),
              Icon(icon, color: color, size: 28),
              Text('${(h['temp_c'] as num).round()}°', style: const TextStyle(fontWeight: FontWeight.bold)),
              Text(rain > 0 ? '💧$rain%' : ' ', style: TextStyle(fontSize: 11, color: Colors.blue.shade700)),
            ]);
          },
        ),
      ),
    ]);
  }
}

class _DailyList extends StatelessWidget {
  const _DailyList({required this.days});

  final List<Map<String, dynamic>> days;

  @override
  Widget build(BuildContext context) {
    final lo = days.map((d) => (d['min_temp_c'] as num).toDouble()).reduce((a, b) => a < b ? a : b);
    final hi = days.map((d) => (d['max_temp_c'] as num).toDouble()).reduce((a, b) => a > b ? a : b);
    final span = (hi - lo).abs() < 0.1 ? 1.0 : hi - lo;
    return SectionCard(title: 'Daily forecast', icon: Icons.calendar_month_outlined, children: [
      for (final d in days)
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 5),
          child: Row(children: [
            SizedBox(
                width: 92,
                child: Text(dayLabel(context, '${d['date']}'),
                    maxLines: 1, softWrap: false, overflow: TextOverflow.fade, style: const TextStyle(fontWeight: FontWeight.w600))),
            Icon(weatherIcon(d['weather_code']).$1, color: weatherIcon(d['weather_code']).$2, size: 22),
            SizedBox(
              width: 48,
              child: Text((d['chance_of_rain'] as num? ?? 0) > 0 ? ' 💧${d['chance_of_rain']}%' : '',
                  style: TextStyle(fontSize: 11, color: Colors.blue.shade700)),
            ),
            Text('${(d['min_temp_c'] as num).round()}°', style: const TextStyle(color: Colors.black54)),
            const SizedBox(width: 6),
            Expanded(
              child: LayoutBuilder(builder: (context, c) {
                final left = ((d['min_temp_c'] as num) - lo) / span * c.maxWidth;
                final width = (((d['max_temp_c'] as num) - (d['min_temp_c'] as num)) / span * c.maxWidth).clamp(4.0, c.maxWidth);
                return Stack(children: [
                  Container(height: 6, decoration: BoxDecoration(color: Colors.grey.shade200, borderRadius: BorderRadius.circular(3))),
                  Positioned(
                    left: left,
                    child: Container(
                      height: 6,
                      width: width,
                      decoration: BoxDecoration(
                          gradient: const LinearGradient(colors: [Colors.lightBlue, Colors.orange]), borderRadius: BorderRadius.circular(3)),
                    ),
                  ),
                ]);
              }),
            ),
            const SizedBox(width: 6),
            Text('${(d['max_temp_c'] as num).round()}°', style: const TextStyle(fontWeight: FontWeight.bold)),
          ]),
        ),
    ]);
  }
}
