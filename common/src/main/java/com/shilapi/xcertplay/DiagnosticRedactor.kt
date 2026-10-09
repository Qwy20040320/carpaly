package com.shilapi.xcertplay

/** Diagnostics describe state transitions; protocol payloads and credentials are never exported. */
internal object DiagnosticRedactor {
    private val secret = Regex("(?i)(pass(word|phrase)?|token|private.?key|certificate|pair.?record|ssid|body=|payload=|hex=)")
    private val sensitiveAssignment = Regex("(?i)\\b(vin|imei|serial(?:_number)?|phone(?:_number)?|email|bssid|mac(?:_address)?|credential|authorization)\\s*[=:]")
    private val mac = Regex("(?i)(?<![0-9a-f])(?:[0-9a-f]{2}:){5}[0-9a-f]{2}(?![0-9a-f])")
    private val identifier = Regex("(?i)\\b[0-9a-f]{24,}\\b|\\b[0-9a-f]{8}-[0-9a-f-]{27,}\\b")
    private val vin = Regex("(?i)\\b[A-HJ-NPR-Z0-9]{17}\\b")
    private val imei = Regex("\\b[0-9]{14,16}\\b")
    private val email = Regex("(?i)\\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}\\b")
    private val phone = Regex("(?<![0-9])\\+?(?:[0-9][ ()-]?){9,14}[0-9](?![0-9])")
    private val address = Regex("(?<![0-9])(?:[0-9]{1,3}\\.){3}[0-9]{1,3}(?![0-9])")
    private val namedDevice = Regex("(?i)(phone|device|peer|host)?name[=:]")
    private val ipv6 = Regex("(?i)(?:[0-9a-f]{1,4}:)*[0-9a-f]{0,4}::[0-9a-f:]*(?:%[a-z0-9_.-]+)?|(?:[0-9a-f]{1,4}:){7}[0-9a-f]{1,4}")
    private val localPath = Regex("(?i)(?:[a-z]:\\\\(?:users\\\\[^\\s\\\\]+\\\\)?[^\\s,;]+|/data/(?:user|data)/[^\\s,;]+|/storage/emulated/[^\\s,;]+)")
    fun redact(line: String): String? {
        if (line.contains("TRACE ") || line.contains("PHONE ") || line.contains('\n') || line.contains('\r')) return null
        if (secret.containsMatchIn(line) || sensitiveAssignment.containsMatchIn(line) || namedDevice.containsMatchIn(line)) return null
        return line.replace(mac, "[address]").replace(identifier, "[identifier]")
            .replace(vin, "[vehicle-id]").replace(imei, "[device-id]").replace(email, "[email]")
            .replace(address, "[ip]").replace(ipv6, "[ip]").replace(phone, "[phone]")
            .replace(localPath, "[local-path]").take(700)
    }
}
