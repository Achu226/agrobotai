// Finds the AGROBOTAI laptop on the phone's Wi-Fi so nobody has to type an IP address.
// The real scanner needs dart:io; web builds get a stub that finds nothing.
export 'server_discovery_stub.dart' if (dart.library.io) 'server_discovery_io.dart';
