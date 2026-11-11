/// Web has no raw sockets, so the server cannot be discovered there.
Future<String?> discoverAgrobotServer({int port = 8000, String? preferHost}) async => null;
