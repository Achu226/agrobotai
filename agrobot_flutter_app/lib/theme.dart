import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import 'widgets/common.dart';

/// App-wide look: large, high-contrast text and buttons for farmers reading in sunlight, in a green theme.
ThemeData agrobotTheme(BuildContext context) {
  final scheme = ColorScheme.fromSeed(seedColor: kGreen, primary: kGreen, surface: Colors.white);
  final text = GoogleFonts.poppinsTextTheme(Theme.of(context).textTheme).apply(bodyColor: const Color(0xFF1C2B1E));
  final round = RoundedRectangleBorder(borderRadius: BorderRadius.circular(14));
  const bigLabel = TextStyle(fontSize: 16, fontWeight: FontWeight.w600);
  const minSize = Size(64, 52);
  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    textTheme: text,
    scaffoldBackgroundColor: const Color(0xFFF3F7F1),
    materialTapTargetSize: MaterialTapTargetSize.padded,
    appBarTheme: AppBarTheme(
      backgroundColor: kDarkGreen,
      foregroundColor: Colors.white,
      titleTextStyle: GoogleFonts.poppins(fontSize: 20, fontWeight: FontWeight.w600, color: Colors.white),
    ),
    cardTheme: CardThemeData(
      color: Colors.white,
      elevation: 0,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18), side: const BorderSide(color: Color(0xFFDDE8D9))),
    ),
    filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(minimumSize: minSize, shape: round, textStyle: bigLabel, padding: const EdgeInsets.symmetric(horizontal: 20))),
    elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(minimumSize: minSize, shape: round, textStyle: bigLabel, padding: const EdgeInsets.symmetric(horizontal: 20))),
    outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
            minimumSize: minSize, shape: round, textStyle: bigLabel, side: const BorderSide(color: kGreen, width: 1.5))),
    textButtonTheme: TextButtonThemeData(style: TextButton.styleFrom(minimumSize: const Size(48, 48), textStyle: bigLabel)),
    floatingActionButtonTheme: FloatingActionButtonThemeData(
        backgroundColor: kGreen, foregroundColor: Colors.white, extendedTextStyle: bigLabel, shape: round),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: Colors.white,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(14)),
      enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: Color(0xFFC9D8C4))),
      focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: kGreen, width: 2)),
    ),
    navigationBarTheme: NavigationBarThemeData(
      height: 72,
      backgroundColor: Colors.white,
      indicatorColor: const Color(0xFFCDE8C8),
      labelTextStyle: WidgetStatePropertyAll(GoogleFonts.poppins(fontSize: 13, fontWeight: FontWeight.w600)),
    ),
    snackBarTheme: SnackBarThemeData(behavior: SnackBarBehavior.floating, shape: round, contentTextStyle: const TextStyle(fontSize: 15)),
    dividerTheme: const DividerThemeData(color: Color(0xFFE3ECDF)),
  );
}

/// Text 10% larger than the phone's own setting (capped so layouts still fit).
Widget largerText(BuildContext context, Widget? child) {
  final mq = MediaQuery.of(context);
  final scale = (mq.textScaler.scale(1) * 1.1).clamp(1.0, 1.6);
  return MediaQuery(data: mq.copyWith(textScaler: TextScaler.linear(scale)), child: child ?? const SizedBox.shrink());
}
