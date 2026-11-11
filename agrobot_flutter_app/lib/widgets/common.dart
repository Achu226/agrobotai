import 'package:flutter/material.dart';

import '../l10n.dart';

const kGreen = Color(0xFF2E7D32);
const kDarkGreen = Color(0xFF1B5E20);

String notAvailable(Object? v, [String suffix = '']) => v == null || (v is String && v.isEmpty) ? 'Not available' : '$v$suffix';

String pct(double? v) => v == null ? 'Not available' : '${v.toStringAsFixed(1)}%';

/// "2026-10-21T09:15:03+05:30" -> "2026-10-21 09:15"
String shortTime(String? iso) {
  if (iso == null || iso.isEmpty) return 'Not available';
  final t = DateTime.tryParse(iso);
  if (t == null) return iso;
  final l = t.toLocal();
  String two(int n) => n.toString().padLeft(2, '0');
  return '${l.year}-${two(l.month)}-${two(l.day)} ${two(l.hour)}:${two(l.minute)}';
}

class InfoRow extends StatelessWidget {
  const InfoRow(this.label, this.value, {super.key, this.valueColor});

  final String label;
  final String value;
  final Color? valueColor;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 3),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          SizedBox(width: 140, child: Text(context.tr(label), style: TextStyle(color: Colors.grey.shade700))),
          Expanded(child: Text(context.tr(value), style: TextStyle(fontWeight: FontWeight.w600, color: valueColor))),
        ]),
      );
}

class MessagePanel extends StatelessWidget {
  const MessagePanel({super.key, required this.icon, required this.title, this.message, this.color = Colors.red, this.actions = const []});

  final IconData icon;
  final String title;
  final String? message;
  final MaterialColor color;
  final List<Widget> actions;

  @override
  Widget build(BuildContext context) => Container(
        width: double.infinity,
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: color.shade50,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: color.shade200),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Icon(icon, color: color.shade800),
            const SizedBox(width: 8),
            Expanded(child: Text(context.tr(title), style: TextStyle(fontWeight: FontWeight.bold, color: color.shade900))),
          ]),
          if (message != null) ...[
            const SizedBox(height: 6),
            Text(context.tr(message!), style: TextStyle(color: color.shade900)),
          ],
          if (actions.isNotEmpty) ...[
            const SizedBox(height: 8),
            Wrap(spacing: 8, runSpacing: 4, children: actions),
          ],
        ]),
      );
}

class SectionCard extends StatelessWidget {
  const SectionCard({super.key, required this.title, required this.children, this.icon, this.trailing});

  final String title;
  final IconData? icon;
  final Widget? trailing;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) => Card(
        margin: const EdgeInsets.only(bottom: 12),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              if (icon != null) ...[Icon(icon, color: kGreen, size: 20), const SizedBox(width: 8)],
              Expanded(
                  child: Text(context.tr(title), style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: kDarkGreen))),
              if (trailing != null) trailing!,
            ]),
            const SizedBox(height: 8),
            ...children,
          ]),
        ),
      );
}

class ReviewChip extends StatelessWidget {
  const ReviewChip(this.status, {super.key});

  final String status;

  @override
  Widget build(BuildContext context) {
    final (color, label) = switch (status) {
      'approved' => (Colors.green, 'Approved'),
      'rejected' => (Colors.red, 'Rejected'),
      _ => (Colors.orange, 'Pending review'),
    };
    // Capped width: a long translation is shortened with … instead of squeezing the scan title
    return ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 150),
      child: Chip(
        label: Text(context.tr(label),
            maxLines: 1, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: 11, color: color.shade900)),
        backgroundColor: color.shade50,
        side: BorderSide(color: color.shade200),
        visualDensity: VisualDensity.compact,
        materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
      ),
    );
  }
}

/// Small line chart; null values leave a gap (missing readings are never interpolated).
class Sparkline extends StatelessWidget {
  const Sparkline(this.values, {super.key});

  final List<double?> values;

  @override
  Widget build(BuildContext context) {
    final present = values.whereType<double>();
    if (present.isEmpty) return const SizedBox.shrink();
    final lo = present.reduce((a, b) => a < b ? a : b);
    final hi = present.reduce((a, b) => a > b ? a : b);
    return CustomPaint(painter: _SparklinePainter(values, lo, hi));
  }
}

class _SparklinePainter extends CustomPainter {
  _SparklinePainter(this.values, this.lo, this.hi);

  final List<double?> values;
  final double lo;
  final double hi;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = kGreen
      ..strokeWidth = 2
      ..style = PaintingStyle.stroke;
    final span = (hi - lo).abs() < 1e-9 ? 1.0 : hi - lo;
    Path? path;
    for (var i = 0; i < values.length; i++) {
      final v = values[i];
      if (v == null) {
        path = null; // gap where the sensor did not report: never interpolated
        continue;
      }
      final x = values.length == 1 ? 0.0 : size.width * i / (values.length - 1);
      final y = size.height - (v - lo) / span * size.height;
      if (path == null) {
        path = Path()..moveTo(x, y);
        canvas.drawCircle(Offset(x, y), 1.5, paint);
      } else {
        path.lineTo(x, y);
        canvas.drawPath(path, paint);
      }
    }
  }

  @override
  bool shouldRepaint(covariant _SparklinePainter old) => old.values != values;
}

