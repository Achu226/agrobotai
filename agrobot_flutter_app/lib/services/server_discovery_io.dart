import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:http/http.dart' as http;

/// The `service` field of the server's /health response.
const agrobotServiceName = 'AGROBOTAI inference server';

/// Looks for the AGROBOTAI server, first through a USB cable, then on the Wi-Fi.
///
/// 1. 127.0.0.1:[port] — reaches the laptop when the phone is plugged in and start.bat has run
///    `adb reverse tcp:PORT tcp:PORT` (the connection goes over USB, so Windows Firewall and the
///    Wi-Fi's Public/Private setting do not matter). Also finds a server on the same computer.
/// 2. Every address of the device's own /24 Wi-Fi subnet(s) on [port].
/// Each open port is confirmed with GET /health. Returns the base URL (http://ip:port), or null.
Future<String?> discoverAgrobotServer({int port = 8000, String? preferHost}) async {
  final hosts = <String>['127.0.0.1'];
  if (preferHost != null && isPrivateIPv4(preferHost)) hosts.add(preferHost);
  for (final own in await _ownAddresses()) {
    final prefix = own.substring(0, own.lastIndexOf('.'));
    for (var i = 1; i < 255; i++) {
      final h = '$prefix.$i';
      if (!hosts.contains(h)) hosts.add(h);
    }
  }

  final client = http.Client();
  try {
    const parallel = 64;
    for (var start = 0; start < hosts.length; start += parallel) {
      final batch = hosts.sublist(start, min(start + parallel, hosts.length));
      final open = (await Future.wait(batch.map((h) => _portOpen(h, port)))).whereType<String>();
      for (final h in open) {
        final url = 'http://$h:$port';
        if (await _isAgrobot(client, url)) return url;
      }
    }
    return null;
  } finally {
    client.close();
  }
}

bool isPrivateIPv4(String ip) {
  final p = ip.split('.').map(int.tryParse).toList();
  if (p.length != 4 || p.any((x) => x == null)) return false;
  return p[0] == 10 || (p[0] == 192 && p[1] == 168) || (p[0] == 172 && p[1]! >= 16 && p[1]! <= 31);
}

/// Private IPv4 addresses of this device, Wi-Fi/Ethernet first (mobile-data interfaces last,
/// since the laptop is never on the carrier network).
Future<List<String>> _ownAddresses() async {
  final ifaces = await NetworkInterface.list(type: InternetAddressType.IPv4, includeLoopback: false);
  bool isLan(NetworkInterface i) {
    final n = i.name.toLowerCase();
    return n.startsWith('wlan') || n.startsWith('wi-fi') || n.startsWith('wifi') || n.startsWith('eth') || n.startsWith('en');
  }

  ifaces.sort((a, b) => (isLan(a) ? 0 : 1).compareTo(isLan(b) ? 0 : 1));
  return [
    for (final i in ifaces)
      for (final a in i.addresses)
        if (isPrivateIPv4(a.address)) a.address,
  ];
}

Future<String?> _portOpen(String host, int port) async {
  try {
    final s = await Socket.connect(host, port, timeout: const Duration(milliseconds: 700));
    s.destroy();
    return host;
  } catch (_) {
    return null;
  }
}

Future<bool> _isAgrobot(http.Client client, String url) async {
  try {
    final res = await client.get(Uri.parse('$url/health')).timeout(const Duration(seconds: 4));
    final body = jsonDecode(utf8.decode(res.bodyBytes));
    return body is Map && body['service'] == agrobotServiceName;
  } catch (_) {
    return false;
  }
}
