package com.shilapi.xcertplay

import android.Manifest
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothAdapter
import android.content.BroadcastReceiver
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.net.ConnectivityManager
import android.hardware.usb.UsbManager
import android.media.AudioAttributes
import android.media.AudioDeviceInfo
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioRecord
import android.media.AudioTrack
import android.media.MediaRecorder
import android.net.wifi.WifiManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.text.Editable
import android.text.TextWatcher
import android.view.Gravity
import android.view.KeyEvent
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.widget.AdapterView
import android.widget.ArrayAdapter
import android.widget.Button
import android.widget.CheckBox
import android.widget.EditText
import android.widget.GridLayout
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.Spinner
import android.widget.TextView
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.result.contract.ActivityResultContracts
import com.shilapi.xcertplay.host.R
import org.json.JSONArray
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import java.util.UUID
import kotlin.math.sqrt

/**
 * Read-only, foreground diagnostics for the Geely receiver profile. It deliberately does not
 * open CAN/UDS/Vehicle HAL/vendor interfaces, request USB devices, or collect vehicle identifiers.
 */
class GeelyDiagnosticCenterActivity : ComponentActivity() {
    internal companion object {
        const val EXTRA_MFI_AUTH_STATUS = "com.shilapi.xcertplay.extra.MFI_AUTH_STATUS"
    }

    private val handler = Handler(Looper.getMainLooper())
    private val valueViews = linkedMapOf<String, TextView>()
    private var monitoring = false
    private var diagnosticSessionId: String? = null
    private var monitoringReceiverRegistered = false
    private var listeningForWheel = false
    private var wheelKeyObserved = false
    private var lastSnapshotSignature: String? = null
    private var pendingExportCapture: Capture? = null
    private var pendingExportFilename = "CarPaly-Diagnostic.zip"
    private var micThread: Thread? = null
    private var speakerTrack: AudioTrack? = null
    private var speakerStop: Runnable? = null
    private var showingFullHistory = false
    @Volatile private var speakerTestStatus = "NOT_TESTED"
    @Volatile private var microphoneTestStatus = "NOT_TESTED"
    private lateinit var actionButton: Button
    private lateinit var logToggleButton: Button
    private lateinit var logStatusView: TextView
    private lateinit var logPathView: TextView
    private lateinit var logHistoryView: TextView
    private lateinit var logHistoryModeButton: Button
    private lateinit var logModuleFilter: Spinner
    private lateinit var logErrorFilter: CheckBox
    private lateinit var logSearchField: EditText
    private lateinit var wheelStatus: TextView
    private lateinit var micStatus: TextView
    private lateinit var speakerStatus: TextView

    private val createZip = registerForActivityResult(ActivityResultContracts.CreateDocument("application/zip")) { uri ->
        if (uri != null) pendingExportCapture?.let { exportZip(uri, it) }
    }
    private val micPermission = registerForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        if (granted) runMicrophoneTest() else {
            micStatus.text = "PERMISSION_DENIED · 麦克风权限未授予；未开始录音。"
            Toast.makeText(this, "未授予麦克风权限", Toast.LENGTH_SHORT).show()
        }
    }

    private val refresh = object : Runnable {
        override fun run() {
            renderSnapshot()
            if (monitoring) handler.postDelayed(this, 1_500)
        }
    }

    private val transportReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent?) {
            val action = intent?.action ?: return
            when (action) {
                UsbManager.ACTION_USB_DEVICE_ATTACHED, UsbManager.ACTION_USB_DEVICE_DETACHED -> {
                    val device = if (Build.VERSION.SDK_INT >= 33) {
                        intent.getParcelableExtra(UsbManager.EXTRA_DEVICE, android.hardware.usb.UsbDevice::class.java)
                    } else {
                        @Suppress("DEPRECATION")
                        intent.getParcelableExtra(UsbManager.EXTRA_DEVICE)
                    }
                    val description = device?.let {
                        "VID=0x%04X PID=0x%04X interfaces=%s".format(Locale.US, it.vendorId, it.productId,
                            (0 until it.interfaceCount).map { index -> it.getInterface(index).interfaceClass }.distinct())
                    } ?: "设备信息 NO_DATA"
                    GeelyDiagnosticHistory.append(this@GeelyDiagnosticCenterActivity,
                        "USB ${if (action == UsbManager.ACTION_USB_DEVICE_ATTACHED) "attached" else "detached"}: $description",
                        if (action == UsbManager.ACTION_USB_DEVICE_ATTACHED) "device_attached" else "device_detached",
                        "usb", "INFO", diagnosticSessionId)
                }
                WifiManager.WIFI_STATE_CHANGED_ACTION -> {
                    val state = intent.getIntExtra(WifiManager.EXTRA_WIFI_STATE, WifiManager.WIFI_STATE_UNKNOWN)
                    val name = when (state) {
                        WifiManager.WIFI_STATE_ENABLED -> "enabled"
                        WifiManager.WIFI_STATE_DISABLED -> "disabled"
                        WifiManager.WIFI_STATE_ENABLING -> "enabling"
                        WifiManager.WIFI_STATE_DISABLING -> "disabling"
                        else -> "unknown"
                    }
                    GeelyDiagnosticHistory.append(this@GeelyDiagnosticCenterActivity, "Wi-Fi 状态：$name",
                        "adapter_state", "network", "INFO", diagnosticSessionId)
                }
                WifiManager.NETWORK_STATE_CHANGED_ACTION -> {
                    val connected = runCatching {
                        getSystemService(ConnectivityManager::class.java)?.activeNetwork != null
                    }.getOrNull()
                    GeelyDiagnosticHistory.append(this@GeelyDiagnosticCenterActivity,
                        "网络连接状态：${connected?.let { if (it) "connected" else "disconnected" } ?: "NO_DATA"}",
                        "network_state", "network", "INFO", diagnosticSessionId)
                }
                BluetoothAdapter.ACTION_STATE_CHANGED -> {
                    val state = intent.getIntExtra(BluetoothAdapter.EXTRA_STATE, BluetoothAdapter.ERROR)
                    val name = when (state) {
                        BluetoothAdapter.STATE_ON -> "enabled"
                        BluetoothAdapter.STATE_OFF -> "disabled"
                        BluetoothAdapter.STATE_TURNING_ON -> "enabling"
                        BluetoothAdapter.STATE_TURNING_OFF -> "disabling"
                        else -> "unknown"
                    }
                    GeelyDiagnosticHistory.append(this@GeelyDiagnosticCenterActivity, "Bluetooth adapter 状态：$name",
                        "adapter_state", "network", "INFO", diagnosticSessionId)
                }
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        DiagnosticLogManager.prune(applicationContext)
        GeelyDiagnosticCrashRecorder.install(applicationContext)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        window.statusBarColor = 0xff11151c.toInt()
        window.navigationBarColor = 0xff11151c.toInt()
        setContentView(buildView())
        renderSnapshot()
        renderLogManagement()
        renderLogHistory()
    }

    override fun onResume() {
        super.onResume()
        renderSnapshot()
    }

    override fun onPause() {
        handler.removeCallbacks(refresh)
        if (monitoring) {
            monitoring = false
            GeelyDiagnosticHistory.append(this, "诊断监测在页面离开时停止", "monitoring_stopped", "diagnostic", "INFO", diagnosticSessionId)
            unregisterMonitoringReceiver()
            diagnosticSessionId = null
            updateActionButton()
        }
        stopSpeakerTest()
        if (micThread?.isAlive == true) {
            micThread?.interrupt()
            runCatching { micThread?.join(250) }
            microphoneTestStatus = "INTERRUPTED · diagnostic page left foreground; no background capture"
            GeelyDiagnosticHistory.append(this, "页面离开前台；麦克风短测已中断", "microphone_test_interrupted", "audio", "INFO", diagnosticSessionId)
        }
        listeningForWheel = false
        super.onPause()
    }

    override fun onDestroy() {
        handler.removeCallbacksAndMessages(null)
        stopSpeakerTest()
        micThread?.interrupt()
        micThread = null
        super.onDestroy()
    }

    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        if (listeningForWheel && event.action == KeyEvent.ACTION_DOWN && event.repeatCount == 0 &&
            event.keyCode != KeyEvent.KEYCODE_BACK) {
            wheelKeyObserved = true
            val safeCode = KeyEvent.keyCodeToString(event.keyCode).take(80)
            wheelStatus.text = "OBSERVED · $safeCode（仅监听，不执行车辆操作）"
            GeelyDiagnosticHistory.append(this, "方向盘按键观测：$safeCode", "key_event", "vehicle", "INFO", diagnosticSessionId)
        }
        return super.dispatchKeyEvent(event)
    }

    private fun buildView(): View {
        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setBackgroundColor(0xff11151c.toInt())
            setPadding(dp(18), dp(12), dp(18), dp(12))
        }
        val toolbar = LinearLayout(this).apply { gravity = Gravity.CENTER_VERTICAL }
        toolbar.addView(button("‹ 返回", false) { finish() }, LinearLayout.LayoutParams(dp(112), dp(52)))
        toolbar.addView(text("CarPaly 诊断中心", 25, 0xfff3f5f8.toInt(), true),
            LinearLayout.LayoutParams(0, -2, 1f).apply { marginStart = dp(18) })
        root.addView(toolbar)
        root.addView(text("只读取 Android 与 CarPlay 接收端可见信息；车辆总线、VIN、序列号、网络凭据均不读取。导出由你手动发起，不会自动上传。", 14, 0xffaab3c2.toInt())
            .apply { setPadding(dp(8), dp(4), dp(8), dp(12)) })

        val controls = GridLayout(this).apply { columnCount = 4 }
        actionButton = button("开始完整诊断", true) { toggleMonitoring() }
        controls.addView(actionButton, gridParams())
        logToggleButton = button(logToggleCaption(), false) { toggleLogging() }
        controls.addView(logToggleButton, gridParams())
        controls.addView(button("检测 USB", false) {
            renderSnapshot()
            Toast.makeText(this, "USB 只读检测已刷新", Toast.LENGTH_SHORT).show()
        }, gridParams())
        controls.addView(button("检测 Wi-Fi / 蓝牙", false) {
            renderSnapshot()
            Toast.makeText(this, "Wi-Fi / 蓝牙状态已刷新", Toast.LENGTH_SHORT).show()
        }, gridParams())
        controls.addView(button(getString(R.string.save_diagnostic_report), false) { prepareExport(saveToDownloads = true) }, gridParams())
        controls.addView(button(getString(R.string.choose_save_location), false) { prepareExport(saveToDownloads = false) }, gridParams())
        controls.addView(button("查看实时日志", false) {
            renderLogHistory()
            renderLogManagement()
            valueViews["live"]?.let { view ->
                view.requestFocus()
                Toast.makeText(this, "实时日志在页面下方；上下滑动查看。", Toast.LENGTH_SHORT).show()
            }
        }, gridParams())
        controls.addView(button("清空本机日志", false) { confirmClear() }, gridParams())
        controls.addView(button("应用权限", false) {
            runCatching { startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).setData(android.net.Uri.parse("package:$packageName"))) }
        }, gridParams())
        root.addView(controls)

        val scroll = ScrollView(this).apply { isFillViewport = true }
        val body = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(0, dp(10), 0, dp(12))
        }
        val grid = GridLayout(this).apply {
            columnCount = if (resources.configuration.screenWidthDp >= 850) 2 else 1
            useDefaultMargins = false
            alignmentMode = GridLayout.ALIGN_BOUNDS
        }
        addPanel(grid, "device", "设备与版本")
        addPanel(grid, "vehicle", "车辆身份与适配证据")
        addPanel(grid, "display", "屏幕、视频与显示")
        addPanel(grid, "transport", "USB、Wi-Fi 与蓝牙")
        addPanel(grid, "carplay", "CarPlay 与音频路由")
        addPanel(grid, "permissions", "权限与 Android Car 能力")
        body.addView(grid)

        val testCard = panelContainer("交互测试（均由用户主动启动）")
        testCard.addView(text("方向盘按键", 17, 0xffe8edf5.toInt(), true))
        testCard.addView(text("仅在此页前台观察按键码；不发送指令、不消费按键。", 13, 0xffaab3c2.toInt()))
        val wheelRow = LinearLayout(this).apply { gravity = Gravity.CENTER_VERTICAL }
        wheelStatus = text("NOT_TESTED · 尚未监听", 14, 0xffb8c3d1.toInt())
        wheelRow.addView(wheelStatus, LinearLayout.LayoutParams(0, -2, 1f))
        wheelRow.addView(button("开始监听", false) {
            listeningForWheel = !listeningForWheel
            (it as Button).text = if (listeningForWheel) "停止监听" else "开始监听"
            if (listeningForWheel) wheelStatus.text = "NOT_TESTED · 等待方向盘按键"
            else GeelyDiagnosticHistory.append(this, "方向盘按键监听已停止", "wheel_listener_stopped", "vehicle", "INFO", diagnosticSessionId)
        }, LinearLayout.LayoutParams(dp(150), dp(50)))
        testCard.addView(wheelRow)
        testCard.addView(text("扬声器", 17, 0xffe8edf5.toInt(), true).apply { setPadding(0, dp(14), 0, 0) })
        testCard.addView(text("低音量 440 Hz、约 0.4 秒；请停车并确认周围安全。", 13, 0xffaab3c2.toInt()))
        testCard.addView(button("播放一次提示音", false) { startSpeakerTest() }, LinearLayout.LayoutParams(-1, dp(50)))
        speakerStatus = text("NOT_TESTED · 尚未测试", 14, 0xffb8c3d1.toInt())
        testCard.addView(speakerStatus)
        testCard.addView(button("立即停止提示音", false) {
            stopSpeakerTest()
            speakerTestStatus = "STOPPED_BY_USER · audibility NOT_TESTED"
            speakerStatus.text = speakerTestStatus
            GeelyDiagnosticHistory.append(this, "用户立即停止扬声器提示音", "speaker_test_stopped", "audio", "INFO", diagnosticSessionId)
        }, LinearLayout.LayoutParams(-1, dp(50)))
        testCard.addView(text("麦克风", 17, 0xffe8edf5.toInt(), true).apply { setPadding(0, dp(14), 0, 0) })
        testCard.addView(text("需要单独授权；前台采样约 1.5 秒，只计算电平，不保存/上传音频。", 13, 0xffaab3c2.toInt()))
        micStatus = text("NOT_TESTED · 未启动", 14, 0xffb8c3d1.toInt())
        testCard.addView(micStatus)
        testCard.addView(button("开始麦克风自测", false) { requestOrRunMicrophoneTest() }, LinearLayout.LayoutParams(-1, dp(50)))
        testCard.addView(button("停止麦克风自测", false) {
            micThread?.interrupt()
            microphoneTestStatus = "INTERRUPTED_BY_USER · no audio saved"
            micStatus.text = "已请求停止；不保存录音。"
            GeelyDiagnosticHistory.append(this, "用户停止麦克风自测", "microphone_test_interrupted", "audio", "INFO", diagnosticSessionId)
        }, LinearLayout.LayoutParams(-1, dp(50)))
        body.addView(testCard)

        val logCard = panelContainer("日志管理")
        logStatusView = text("读取日志状态…", 14, 0xffc8d1dd.toInt())
        logCard.addView(logStatusView)
        logPathView = text("保存路径：读取中…", 12, 0xffaab3c2.toInt()).apply { setTextIsSelectable(true) }
        logCard.addView(logPathView)
        logCard.addView(button("刷新日志统计", false) { renderLogManagement() }, LinearLayout.LayoutParams(-1, dp(48)))
        logCard.addView(button("复制日志目录路径", false) {
            val path = DiagnosticLogManager.displayPath(this)
            (getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager)
                .setPrimaryClip(ClipData.newPlainText("CarPaly diagnostic logs", path))
            Toast.makeText(this, "日志目录路径已复制", Toast.LENGTH_SHORT).show()
        }, LinearLayout.LayoutParams(-1, dp(48)))

        val filterRow = LinearLayout(this).apply { gravity = Gravity.CENTER_VERTICAL }
        logModuleFilter = Spinner(this).apply {
            val options = listOf("全部模块", "CarPlay", "诊断", "USB", "网络", "音频", "车辆/按键")
            adapter = ArrayAdapter(this@GeelyDiagnosticCenterActivity, android.R.layout.simple_spinner_item, options)
                .also { it.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item) }
        }
        filterRow.addView(logModuleFilter, LinearLayout.LayoutParams(0, dp(52), 1f))
        logErrorFilter = CheckBox(this).apply {
            text = "仅错误"
            setTextColor(0xffedf2f8.toInt())
        }
        filterRow.addView(logErrorFilter)
        logCard.addView(filterRow)
        logSearchField = EditText(this).apply {
            hint = "按关键字筛选时间、模块或内容"
            setSingleLine(true)
            setTextColor(0xffedf2f8.toInt())
            setHintTextColor(0xffaab3c2.toInt())
            addTextChangedListener(object : TextWatcher {
                override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) = Unit
                override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) = renderLogHistory()
                override fun afterTextChanged(s: Editable?) = Unit
            })
        }
        logCard.addView(logSearchField, LinearLayout.LayoutParams(-1, dp(52)))
        logHistoryModeButton = button("查看全部历史（最多 300 条）", false) {
            showingFullHistory = !showingFullHistory
            logHistoryModeButton.text = if (showingFullHistory) "切回实时日志（最近 30 条）" else "查看全部历史（最多 300 条）"
            renderLogHistory()
        }
        logCard.addView(logHistoryModeButton, LinearLayout.LayoutParams(-1, dp(48)))
        logHistoryView = text("尚无日志记录。", 13, 0xffc8d1dd.toInt()).apply {
            typeface = android.graphics.Typeface.MONOSPACE
            setTextIsSelectable(true)
        }
        valueViews["live"] = logHistoryView
        logCard.addView(logHistoryView)
        logModuleFilter.onItemSelectedListener = object : AdapterView.OnItemSelectedListener {
            override fun onItemSelected(parent: AdapterView<*>?, view: View?, position: Int, id: Long) = renderLogHistory()
            override fun onNothingSelected(parent: AdapterView<*>?) = Unit
        }
        logErrorFilter.setOnCheckedChangeListener { _, _ -> renderLogHistory() }
        body.addView(logCard)

        scroll.addView(body)
        root.addView(scroll, LinearLayout.LayoutParams(-1, 0, 1f))
        return root
    }

    private fun addPanel(parent: GridLayout, key: String, title: String) {
        val container = panelContainer(title)
        valueViews[key] = text("读取中…", 14, 0xffc8d1dd.toInt()).apply {
            typeface = android.graphics.Typeface.MONOSPACE
            setTextIsSelectable(true)
        }
        container.addView(valueViews.getValue(key))
        parent.addView(container, gridParams())
    }

    private fun panelContainer(title: String): LinearLayout = LinearLayout(this).apply {
        orientation = LinearLayout.VERTICAL
        setBackgroundColor(0xff1b222d.toInt())
        setPadding(dp(18), dp(14), dp(18), dp(14))
        addView(text(title, 18, 0xffedf2f8.toInt(), true))
        (layoutParams as? ViewGroup.MarginLayoutParams)?.setMargins(dp(6), dp(6), dp(6), dp(6))
    }

    private fun gridParams(): GridLayout.LayoutParams = GridLayout.LayoutParams().apply {
        width = 0
        height = ViewGroup.LayoutParams.WRAP_CONTENT
        columnSpec = GridLayout.spec(GridLayout.UNDEFINED, 1f)
        setMargins(dp(5), dp(5), dp(5), dp(5))
    }

    private fun button(caption: String, primary: Boolean, action: (View) -> Unit): Button = Button(this).apply {
        text = caption
        isAllCaps = false
        textSize = 15f
        setTextColor(if (primary) 0xff101820.toInt() else 0xffedf2f8.toInt())
        backgroundTintList = android.content.res.ColorStateList.valueOf(if (primary) 0xff80c7ff.toInt() else 0xff313c4b.toInt())
        setOnClickListener(action)
    }

    private fun text(value: String, size: Int, color: Int, bold: Boolean = false): TextView = TextView(this).apply {
        text = value
        textSize = size.toFloat()
        setTextColor(color)
        if (bold) setTypeface(typeface, android.graphics.Typeface.BOLD)
        setPadding(0, dp(3), 0, dp(3))
    }

    private fun toggleMonitoring() {
        monitoring = !monitoring
        if (monitoring) {
            diagnosticSessionId = UUID.randomUUID().toString()
            registerMonitoringReceiver()
            GeelyDiagnosticHistory.append(this, "前台诊断监测已开始", "monitoring_started", "diagnostic", "INFO", diagnosticSessionId)
            handler.removeCallbacks(refresh)
            handler.post(refresh)
        } else {
            handler.removeCallbacks(refresh)
            GeelyDiagnosticHistory.append(this, "前台诊断监测已停止", "monitoring_stopped", "diagnostic", "INFO", diagnosticSessionId)
            unregisterMonitoringReceiver()
            renderSnapshot()
            diagnosticSessionId = null
        }
        updateActionButton()
    }

    private fun toggleLogging() {
        val enable = !DiagnosticLogManager.isEnabled(this)
        if (!enable) {
            GeelyDiagnosticHistory.append(this, "用户手动关闭诊断日志", "logging_disabled", "diagnostic", "INFO", diagnosticSessionId)
        }
        DiagnosticLogManager.setEnabled(this, enable)
        if (enable) {
            DiagnosticLogManager.prune(applicationContext)
            GeelyDiagnosticCrashRecorder.install(applicationContext)
            GeelyDiagnosticHistory.append(this, "用户手动开启诊断日志", "logging_enabled", "diagnostic", "INFO", diagnosticSessionId)
            Toast.makeText(this, "日志已开启；仅保存在本机，不会自动上传。", Toast.LENGTH_SHORT).show()
        } else {
            Toast.makeText(this, "日志已关闭；已有日志保留至自动清理或手动清除。", Toast.LENGTH_SHORT).show()
        }
        logToggleButton.text = logToggleCaption()
        renderLogManagement()
        renderLogHistory()
    }

    private fun logToggleCaption(): String =
        if (DiagnosticLogManager.isEnabled(this)) "停止日志记录" else "手动开启日志"

    private fun renderLogManagement() {
        if (!::logStatusView.isInitialized) return
        val summary = DiagnosticLogManager.summary(this)
        val state = if (DiagnosticLogManager.isEnabled(this)) "已开启（用户手动控制）" else "已关闭（默认关闭）"
        logStatusView.text = "状态：$state\n日志文件：${summary.fileCount}/20 · 总占用：${formatBytes(summary.totalBytes)} / 50 MB\n单文件上限：5 MB · 自动保留：7 天 · 结构化历史：${summary.structuredEventCount}/300 条"
        logPathView.text = "日志保存路径：${summary.directoryPath}\n最近 ZIP 导出：${summary.lastExportLocation ?: "尚未导出"}"
        if (::logToggleButton.isInitialized) logToggleButton.text = logToggleCaption()
    }

    private fun formatBytes(bytes: Long): String = when {
        bytes >= 1024L * 1024L -> "%.2f MB".format(Locale.US, bytes / (1024.0 * 1024.0))
        bytes >= 1024L -> "%.1f KB".format(Locale.US, bytes / 1024.0)
        else -> "$bytes B"
    }

    private fun renderLogHistory() {
        if (!::logHistoryView.isInitialized) return
        val module = when (logModuleFilter.selectedItemPosition) {
            1 -> "carplay"
            2 -> "diagnostic"
            3 -> "usb"
            4 -> "network"
            5 -> "audio"
            6 -> "vehicle"
            else -> null
        }
        val keyword = if (::logSearchField.isInitialized) logSearchField.text.toString().trim() else ""
        val errorPattern = Regex("(?i)error|failed|exception|crash|错误|失败")
        val entries = GeelyDiagnosticHistory.read(this)
            .filter { module == null || it.optString("module") == module }
            .filter { event ->
                !logErrorFilter.isChecked || event.optString("severity").equals("ERROR", true) ||
                    errorPattern.containsMatchIn(event.optString("message"))
            }
            .filter { event ->
                keyword.isBlank() || listOf("timestamp", "module", "severity", "message")
                    .any { event.optString(it).contains(keyword, ignoreCase = true) }
            }
        val visible = if (showingFullHistory) entries else entries.takeLast(30)
        logHistoryView.text = visible.joinToString("\n") { event ->
            "${event.optString("timestamp")} [${event.optString("module")}/${event.optString("severity")}] ${event.optString("message")}"
        }.ifEmpty {
            if (DiagnosticLogManager.isEnabled(this)) "当前筛选条件下暂无日志。" else "日志默认关闭；手动开启后才会记录新的事件。"
        }
    }

    private fun registerMonitoringReceiver() {
        if (monitoringReceiverRegistered) return
        val filter = IntentFilter().apply {
            addAction(UsbManager.ACTION_USB_DEVICE_ATTACHED)
            addAction(UsbManager.ACTION_USB_DEVICE_DETACHED)
            addAction(WifiManager.WIFI_STATE_CHANGED_ACTION)
            addAction(WifiManager.NETWORK_STATE_CHANGED_ACTION)
            addAction(BluetoothAdapter.ACTION_STATE_CHANGED)
        }
        runCatching {
            if (Build.VERSION.SDK_INT >= 33) registerReceiver(transportReceiver, filter, Context.RECEIVER_NOT_EXPORTED)
            else @Suppress("DEPRECATION") registerReceiver(transportReceiver, filter)
            monitoringReceiverRegistered = true
        }.onFailure {
            GeelyDiagnosticHistory.append(this, "无法注册传输状态监听：${it.javaClass.simpleName}",
                "receiver_registration_failed", "diagnostic", "WARN", diagnosticSessionId)
        }
    }

    private fun unregisterMonitoringReceiver() {
        if (!monitoringReceiverRegistered) return
        runCatching { unregisterReceiver(transportReceiver) }
        monitoringReceiverRegistered = false
    }

    private fun updateActionButton() {
        if (::actionButton.isInitialized) actionButton.text = if (monitoring) "停止诊断" else "开始完整诊断"
    }

    private fun renderSnapshot() {
        if (isFinishing || isDestroyed || valueViews.isEmpty()) return
        val capture = capture()
        capture.panels.forEach { (key, value) -> valueViews[key]?.text = value }
        renderLogHistory()
        val signature = capture.signature
        if (monitoring && signature != lastSnapshotSignature) {
            GeelyDiagnosticHistory.append(this, "状态变化：$signature", "state_snapshot", "diagnostic", "INFO", diagnosticSessionId)
            val state = when {
                CarPlayBackgroundSession.active -> "STREAMING"
                CarPlayBackgroundSession.hasSession() -> "SESSION_STARTING_OR_STOPPING"
                else -> "DISCONNECTED"
            }
            GeelyDiagnosticHistory.append(this, "源状态可见值：$state（只映射现有接收端状态）",
                "state_snapshot", "carplay", "INFO", diagnosticSessionId)
        }
        lastSnapshotSignature = signature
    }

    private fun capture(): Capture {
        val recordedAt = nowIso()
        val appInfo = packageManager.getPackageInfo(packageName, 0)
        val appVersion = appInfo.versionName ?: "未知"
        val gitCommit = BuildIdentity.gitCommit()
        val detection = GeelyVehicleAdapter.currentBuild()
        val manual = GeelyVehicleAdapter.manualProfile(this)
        val activeProfile = manual?.let(GeelyVehicleAdapter::label)
            ?: detection.profile?.let(GeelyVehicleAdapter::label) ?: "未识别"

        val display = windowManager.defaultDisplay
        val decor = window.decorView
        val bounds = if (Build.VERSION.SDK_INT >= 30) windowManager.currentWindowMetrics.bounds else null
        val active = CarPlayBackgroundSession.active
        val hasSession = CarPlayBackgroundSession.hasSession()
        val session = CarPlayBackgroundSession.snapshot()
        val panelRefresh = if (Build.VERSION.SDK_INT >= 23) runCatching { display.mode.refreshRate }.getOrNull() else null
        val fps = VideoFrameRateTracker.currentFps()
        val displayLines = DisplayDiagnosticSnapshot.report(this)
        val usbManager = getSystemService(UsbManager::class.java)
        val usbDevices = usbManager?.deviceList?.values.orEmpty().map { device ->
            mapOf("vendor_id_hex" to "0x%04X".format(Locale.US, device.vendorId),
                "product_id_hex" to "0x%04X".format(Locale.US, device.productId),
                "interface_classes" to (0 until device.interfaceCount).map { device.getInterface(it).interfaceClass }.distinct())
        }
        val wifiFeature = packageManager.hasSystemFeature(PackageManager.FEATURE_WIFI)
        val wifiEnabled = runCatching { getSystemService(WifiManager::class.java)?.isWifiEnabled }.getOrNull()
        val btFeature = packageManager.hasSystemFeature(PackageManager.FEATURE_BLUETOOTH)
        val btPermission = Build.VERSION.SDK_INT < 31 || checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT) == PackageManager.PERMISSION_GRANTED
        val bluetoothEnabled = if (!btPermission) null else runCatching {
            getSystemService(BluetoothManager::class.java)?.adapter?.isEnabled
        }.getOrNull()
        val audio = getSystemService(AudioManager::class.java)
        val audioOutputs = if (Build.VERSION.SDK_INT >= 23) runCatching {
            audio.getDevices(AudioManager.GET_DEVICES_OUTPUTS).map { audioTypeName(it.type) }.distinct().sorted()
        }.getOrElse { emptyList() } else emptyList()
        val focus = CarPlayMediaKeys.diagnosticState()
        val packageAutomotive = packageManager.hasSystemFeature(PackageManager.FEATURE_AUTOMOTIVE)
        val micGranted = checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
        val permissions = linkedMapOf(
            "record_audio" to mapOf("status" to if (micGranted) "AVAILABLE" else "PERMISSION_DENIED", "granted" to micGranted),
            "bluetooth_connect" to mapOf("status" to if (btPermission) "AVAILABLE" else "PERMISSION_DENIED", "granted" to btPermission),
            "access_wifi_state" to mapOf("status" to "AVAILABLE", "granted" to (checkSelfPermission(Manifest.permission.ACCESS_WIFI_STATE) == PackageManager.PERMISSION_GRANTED)),
        )

        val history = GeelyDiagnosticHistory.read(this)
        val sessionState = when {
            active -> "STREAMING"
            hasSession -> "SESSION_STARTING_OR_STOPPING"
            else -> "DISCONNECTED"
        }
        val mfiAuthStatus = intent.getStringExtra(EXTRA_MFI_AUTH_STATUS) ?: "UNKNOWN"
        val sessionEvents = JSONArray().apply {
            history.filter { it.optString("module") == "carplay" }.forEach(::put)
            put(JSONObject().apply {
                put("timestamp", recordedAt)
                put("event_type", "state_snapshot")
                put("module", "carplay")
                put("severity", "INFO")
                put("correlation_session_id", diagnosticSessionId)
                put("message", "Observed receiver state=$sessionState; source=CarPlayBackgroundSession")
            })
        }
        val files = linkedMapOf<String, String>()
        files["device_info.json"] = json(mapOf(
            "recorded_at" to recordedAt, "app" to "CarPaly", "app_version" to appVersion,
            "git_commit" to gitCommit, "android_release" to Build.VERSION.RELEASE, "android_api" to Build.VERSION.SDK_INT,
            "manufacturer" to Build.MANUFACTURER, "brand" to Build.BRAND, "product" to Build.PRODUCT,
            "model" to Build.MODEL, "firmware_display" to safeBuildValue(Build.DISPLAY),
            "firmware_incremental" to safeBuildValue(Build.VERSION.INCREMENTAL),
            "package" to packageName, "permissions" to permissions,
        ))
        files["display_info.json"] = json(mapOf(
            "orientation" to when (resources.configuration.orientation) {
                android.content.res.Configuration.ORIENTATION_LANDSCAPE -> "landscape"
                android.content.res.Configuration.ORIENTATION_PORTRAIT -> "portrait"
                else -> "unknown"
            },
            "window_px" to mapOf("width" to (decor.width.takeIf { it > 0 } ?: bounds?.width()), "height" to (decor.height.takeIf { it > 0 } ?: bounds?.height())),
            "density_dpi" to resources.displayMetrics.densityDpi,
            "reported_xdpi" to resources.displayMetrics.xdpi,
            "reported_ydpi" to resources.displayMetrics.ydpi,
            "panel_refresh_hz" to panelRefresh,
            "carplay_surface_px" to session?.let { mapOf("width" to it.width, "height" to it.height) },
            "configured_fps" to AirPlayPersistence.loadFps(this),
            "observed_video_fps" to fps,
            "observed_video_fps_status" to if (fps == null) "NO_DATA" else "OBSERVED",
            "decoder_and_negotiation_log" to displayLines,
            "profile_viewport_match" to session?.let { GeelyXingyueLProfile.matchesViewport(it.width, it.height) },
        ))
        files["usb_events.json"] = json(mapOf(
            "recorded_at" to recordedAt,
            "status" to if (!packageManager.hasSystemFeature(PackageManager.FEATURE_USB_HOST) || usbDevices.isEmpty()) "NO_DATA" else "OBSERVED",
            "usb_host_feature" to packageManager.hasSystemFeature(PackageManager.FEATURE_USB_HOST),
            "usb_attached_count" to usbDevices.size,
            "usb_devices" to usbDevices,
            "events" to JSONArray().apply { history.filter { it.optString("module") == "usb" }.forEach(::put) },
            "identity_policy" to "No deviceName, serial number, or permission-grant payload is collected.",
        ))
        files["network_events.json"] = json(mapOf(
            "recorded_at" to recordedAt,
            "wifi_feature" to wifiFeature,
            "wifi_enabled" to wifiEnabled,
            "wifi_status" to if (!wifiFeature || wifiEnabled == null) "NO_DATA" else "OBSERVED",
            "bluetooth_feature" to btFeature,
            "bluetooth_permission_status" to if (btPermission) "AVAILABLE" else "PERMISSION_DENIED",
            "bluetooth_enabled" to bluetoothEnabled,
            "events" to JSONArray().apply { history.filter { it.optString("module") == "network" }.forEach(::put) },
            "identity_policy" to "No SSID, BSSID, IP address, device name, password, token, or pairing identity is collected.",
        ))
        files["carplay_session.json"] = json(mapOf(
            "recorded_at" to recordedAt,
            "source" to "CarPlayBackgroundSession",
            "mfi_auth_setup_status" to mfiAuthStatus,
            "observed_state" to sessionState,
            "session_present" to hasSession,
            "media_active" to active,
            "state_mapping_note" to "STREAMING only when receiver reports active; starting/stopping remains combined because source API does not distinguish it; discovery, pairing, and authentication are not exposed here.",
            "events" to sessionEvents,
        ))
        files["audio_events.json"] = json(mapOf(
            "recorded_at" to recordedAt,
            "audio_mode" to audio.mode,
            "music_active" to audio.isMusicActive,
            "output_types" to audioOutputs,
            "actual_selected_output" to "NOT_EXPOSED_BY_CURRENT_PUBLIC_RECEIVER_API",
            "audio_track_state" to speakerTrack?.state,
            "speaker_test_requested_volume_percent" to if (speakerTrack != null) 5 else null,
            "carplay_audio_focus_held" to focus.focusHeld,
            "carplay_media_active" to focus.mediaActive,
            "audibility" to "NOT_TESTED: API state cannot prove that sound was heard.",
            "speaker_test_status" to speakerTestStatus,
            "microphone_permission_status" to if (micGranted) "AVAILABLE" else "PERMISSION_DENIED",
            "microphone_test_status" to microphoneTestStatus,
            "microphone_samples_saved" to false,
            "events" to JSONArray().apply { history.filter { it.optString("module") == "audio" }.forEach(::put) },
        ))
        files["vehicle_events.json"] = json(mapOf(
            "recorded_at" to recordedAt,
            "profile" to activeProfile,
            "manual_profile" to manual?.key,
            "build_detection_confidence" to detection.confidence.name,
            "build_evidence_fields" to detection.evidence,
            "vehicle_identity_status" to if (manual != null || detection.profile != null) "OBSERVED" else "NO_DATA",
            "reverse_status" to "NOT_TESTED",
            "surround_view_360_status" to "NOT_TESTED",
            "power_sleep_wake_status" to "NOT_TESTED",
            "android_automotive_feature" to if (packageAutomotive) "AVAILABLE" else "NO_DATA",
            "android_car_property_api" to "NOT_TESTED: no privileged vehicle property API is queried",
            "geely_ecarx_api" to "NOT_TESTED: no documented public API/SDK integrated",
            "headlight_and_day_night" to "NOT_IMPLEMENTED: no authorized headlight-state API integrated",
            "fuel_and_refueling_inference" to "NOT_IMPLEMENTED: no reliable fuel-level data source",
            "climate_status_and_control" to "NOT_IMPLEMENTED: no authorized climate API integrated",
            "ambient_light_status_and_control" to "NOT_IMPLEMENTED: no authorized ambient-light API integrated",
            "cluster_and_hud" to "NOT_TESTED: no authorized Geely cluster/HUD interface validated",
            "siri_vehicle_control" to "NOT_IMPLEMENTED: no authorized iPhone-to-vehicle command path",
            "vehicle_bus_access" to "DISABLED: no CAN/UDS/Vehicle HAL/vendor Binder access",
            "events" to JSONArray().apply { history.filter { it.optString("module") == "vehicle" }.forEach(::put) },
        ))
        files["errors.txt"] = collectErrors().ifEmpty { listOf("NO_DATA · 尚无可导出的错误事件") }.joinToString("\n")
        files["app_logs.txt"] = "用户选择导出时将读取最近日志尾部；当前页面刷新不会扫描日志文件。\n"
        files["test_summary.md"] = listOf(
            "# CarPaly 吉利车机诊断摘要",
            "",
            "- 生成时间（UTC）：$recordedAt",
            "- MFi 认证资源初始化：$mfiAuthStatus；Apple/iPhone 信任状态：NOT_TESTED",
            "- 车型档案：$activeProfile；实车/具体年款验证：NOT_TESTED",
            "- CarPlay 接收端状态：$sessionState（不代表认证、配对或完整连接能力）",
            "- 扬声器 API 测试：$speakerTestStatus；实际可听效果：NOT_TESTED",
            "- 麦克风测试：$microphoneTestStatus；原始录音保存：否",
            "- 方向盘按键观测：${if (wheelKeyObserved) "OBSERVED" else "NOT_TESTED"}（监听=${listeningForWheel}）",
            "- USB：${if (usbDevices.isEmpty()) "NO_DATA" else "OBSERVED"}；Wi-Fi：${if (wifiFeature && wifiEnabled != null) "OBSERVED" else "NO_DATA"}；蓝牙：${if (!btPermission) "PERMISSION_DENIED" else if (btFeature && bluetoothEnabled != null) "OBSERVED" else "NO_DATA"}",
            "- 倒车/360、ECARX/CarProperty、HUD/仪表：NOT_TESTED；车辆总线写入：DISABLED",
            "- 所有导出均由用户主动触发；未自动上传。",
        ).joinToString("\n")
        files["manifest.json"] = JSONObject().apply {
            put("format", "CarPaly Geely diagnostics ZIP v1")
            put("created_at", recordedAt)
            put("files", JSONArray().apply { (files.keys + "manifest.json").sorted().forEach(::put) })
            put("logging", if (DiagnosticLogManager.isEnabled(this@GeelyDiagnosticCenterActivity)) "user enabled" else "disabled by default; user opt-in required")
            put("retention", "private app storage; max 5 MiB per file, 50 MiB total, 7 days, 20 files; at most 300 structured events")
            put("upload", "never automatic; export is user initiated")
            put("redaction", "VIN, IMEI, serial numbers, MAC, SSID, IPs, personal identifiers, credentials, pair records, call contents, and audio payloads are not exported")
        }.toString(2)

        val panels = linkedMapOf(
            "device" to listOf(
                "App $appVersion · commit $gitCommit", "Android ${Build.VERSION.RELEASE} / API ${Build.VERSION.SDK_INT}",
                "${Build.MANUFACTURER} ${Build.MODEL}", "固件显示：${safeBuildValue(Build.DISPLAY)}",
            ).joinToString("\n"),
            "vehicle" to listOf(
                "适配档案：$activeProfile", "构建识别：${detection.confidence.name}",
                "证据：${detection.evidence.joinToString("；").ifBlank { "暂无" }}",
                "大灯/日夜模式：NOT_IMPLEMENTED · 未接入获授权的大灯状态接口",
                "油量/续航/加油推断：NOT_IMPLEMENTED · 未取得可靠燃油数据源",
                "空调读取/控制：NOT_IMPLEMENTED · 未接入获授权的空调接口",
                "氛围灯读取/控制：NOT_IMPLEMENTED · 未接入获授权的氛围灯接口",
                "仪表/HUD：NOT_TESTED · 尚无经过验证的吉利接口",
                "Siri 车辆控制：NOT_IMPLEMENTED · APK 无可用的授权车辆命令通道",
                "真实车辆/年款验证：NOT_TESTED", "ECARX/车辆总线写入：已禁用",
            ).joinToString("\n"),
            "display" to listOf(
                "当前窗口：${decor.width.takeIf { it > 0 } ?: bounds?.width() ?: "NO_DATA"} × ${decor.height.takeIf { it > 0 } ?: bounds?.height() ?: "NO_DATA"} px",
                "资源密度：${resources.displayMetrics.densityDpi} dpi；报告物理 DPI：${"%.1f".format(Locale.US, resources.displayMetrics.xdpi)} × ${"%.1f".format(Locale.US, resources.displayMetrics.ydpi)}",
                "面板刷新率：${panelRefresh?.let { "%.1f Hz".format(Locale.US, it) } ?: "NO_DATA"}",
                "CarPlay 视频帧：${fps?.let { "OBSERVED · %.1f fps".format(Locale.US, it) } ?: "NO_DATA · 暂无帧"}；设置 ${AirPlayPersistence.loadFps(this)} fps",
                "CarPlay Surface：${session?.let { "${it.width}×${it.height} px" } ?: "NO_DATA"}",
                "解码/协商：\n$displayLines",
            ).joinToString("\n"),
            "transport" to listOf(
                "USB Host：${if (usbDevices.isEmpty()) "NO_DATA · 未见已连接设备" else "OBSERVED · ${usbDevices.size} 台"}",
                "USB 只列 VID/PID/接口类别；不申请 USB 授权、不读取序列号。",
                "Wi-Fi：${if (!wifiFeature) "NO_DATA · 无系统特性" else if (wifiEnabled == true) "OBSERVED · 已开启" else if (wifiEnabled == false) "OBSERVED · 已关闭" else "NO_DATA"}",
                "蓝牙：${when { !btFeature -> "NO_DATA · 无系统特性"; !btPermission -> "PERMISSION_DENIED"; bluetoothEnabled == true -> "OBSERVED · 已开启"; bluetoothEnabled == false -> "OBSERVED · 已关闭"; else -> "NO_DATA" }}",
                "不读取 Wi-Fi/蓝牙名称、地址、SSID、密码或配对记录。",
            ).joinToString("\n"),
            "carplay" to listOf(
                "MFi 认证资源初始化：$mfiAuthStatus（不代表 Apple/iPhone 已信任或 CarPlay 已通过认证）",
                "会话：${if (active) "OBSERVED · 活跃" else if (hasSession) "OBSERVED · 连接中/停止中" else "NO_DATA · 未连接"}",
                "传输模式设置：${if (AirPlayPersistence.loadWirelessEnabled(this)) "无线" else "USB（设置值）"}",
                "Android 音频模式：${audio.mode}；系统报告正在播放：${audio.isMusicActive}",
                "输出类型：${audioOutputs.ifEmpty { listOf("NO_DATA") }.joinToString("、")}",
                "CarPlay 音频焦点：${if (focus.focusHeld) "OBSERVED · 已持有" else "NO_DATA · 未持有"}",
                "可听效果：NOT_TESTED（需要人工试听）",
            ).joinToString("\n"),
            "permissions" to listOf(
                "麦克风：${if (micGranted) "AVAILABLE · 已授权" else "PERMISSION_DENIED · 未授权"}",
                "蓝牙连接：${if (btPermission) "AVAILABLE" else "PERMISSION_DENIED"}",
                "Android Automotive 特性：${if (packageAutomotive) "AVAILABLE" else "NO_DATA"}",
                "ECARX 车辆属性 API：NOT_TESTED · 未接入厂商/特权接口",
                "隐私：诊断不需要 root、系统签名或车辆控制权限。",
            ).joinToString("\n"),
        )
        return Capture(files, panels, panels.values.joinToString("|").replace(Regex("\\s+"), " ").take(700))
    }

    private fun collectErrors(): List<String> {
        val matches = mutableListOf<String>()
        for (event in GeelyDiagnosticHistory.read(this)) {
            val message = "${event.optString("timestamp")} [${event.optString("module")}/${event.optString("severity")}] ${event.optString("message")}"
            if (event.optString("severity") == "ERROR" || Regex("(?i)error|failed|exception|crash|错误|失败").containsMatchIn(message)) {
                DiagnosticRedactor.redact(message)?.let(matches::add)
            }
        }
        return matches.takeLast(100)
    }

    private fun prepareExport(saveToDownloads: Boolean) {
        val snapshot = capture()
        val stamp = SimpleDateFormat("yyyyMMdd-HHmmss", Locale.US).format(Date())
        val filename = "CarPaly-Diagnostic-$stamp.zip"
        pendingExportFilename = filename
        Toast.makeText(this, "正在安全读取最近日志并准备 ZIP…", Toast.LENGTH_SHORT).show()
        Thread({
            val outcome = runCatching {
                val files = snapshot.files.toMutableMap()
                val appLogs = DiagnosticLogManager.exportRecentLogs(applicationContext)
                files["app_logs.txt"] = appLogs
                val errorPattern = Regex("(?i)error|failed|exception|crash|错误|失败")
                val priorErrors = files["errors.txt"].orEmpty().lineSequence()
                    .filter { it.isNotBlank() && !it.startsWith("NO_DATA") }.toList()
                val sessionErrors = appLogs.lineSequence()
                    .filter { errorPattern.containsMatchIn(it) }
                    .mapNotNull(DiagnosticRedactor::redact).toList()
                files["errors.txt"] = (priorErrors + sessionErrors).takeLast(100)
                    .ifEmpty { listOf("NO_DATA · 尚无可导出的错误事件") }.joinToString("\n")
                val exportCapture = snapshot.copy(files = files)
                val saved = if (saveToDownloads) {
                    DiagnosticExportStore.saveArchiveWithoutPicker(applicationContext, filename) { output ->
                        DiagnosticArchive.write(output, exportCapture.files)
                    }
                } else null
                exportCapture to saved
            }
            runOnUiThread {
                if (isFinishing || isDestroyed) return@runOnUiThread
                outcome.fold(
                    { (exportCapture, saved) ->
                        if (saved == null) {
                            pendingExportCapture = exportCapture
                            runCatching { createZip.launch(filename) }
                                .onFailure { saveAndOfferShareFallback(filename, exportCapture) }
                        } else {
                            val location = saved.savedPath
                                ?: if (saved.savedInApp) "应用私有目录/diagnostic-reports/$filename" else "Downloads/CarPaly/$filename"
                            DiagnosticLogManager.recordExportLocation(applicationContext, location)
                            renderLogManagement()
                            Toast.makeText(this, "诊断报告 ZIP 已保存：$location；不会自动上传。导出后请自行检查隐私内容。", Toast.LENGTH_LONG).show()
                        }
                    },
                    { failure ->
                        Toast.makeText(this, "诊断 ZIP 保存失败：${failure.javaClass.simpleName}", Toast.LENGTH_LONG).show()
                    },
                )
            }
        }, "carpaly-diagnostic-export-prepare").apply { isDaemon = true }.start()
    }

    private fun saveAndOfferShareFallback(filename: String, capture: Capture) {
        Toast.makeText(this, "文件选择器不可用；正在保存到下载目录并打开系统分享菜单…", Toast.LENGTH_LONG).show()
        Thread({
            val result = runCatching {
                DiagnosticExportStore.saveArchiveWithoutPicker(applicationContext, filename) { output ->
                    DiagnosticArchive.write(output, capture.files)
                }
            }
            runOnUiThread {
                if (isFinishing || isDestroyed) return@runOnUiThread
                result.onSuccess { saved ->
                    val location = saved.savedPath
                        ?: if (saved.savedInApp) "应用私有目录/diagnostic-reports/$filename"
                        else "Downloads/CarPaly/$filename"
                    DiagnosticLogManager.recordExportLocation(applicationContext, location)
                    renderLogManagement()
                    val share = Intent(Intent.ACTION_SEND).apply {
                        type = "application/zip"
                        putExtra(Intent.EXTRA_STREAM, saved.uri)
                        clipData = android.content.ClipData.newRawUri("CarPaly diagnostic ZIP", saved.uri)
                        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                    }
                    runCatching { startActivity(Intent.createChooser(share, "选择如何导出诊断 ZIP")) }
                        .onSuccess { Toast.makeText(this, "已保存；请在系统分享菜单中选择目标。", Toast.LENGTH_LONG).show() }
                        .onFailure {
                            val location = saved.savedPath ?: if (saved.savedInApp) "应用私有目录（需分享权限读取）" else "下载/CarPaly"
                            Toast.makeText(this, "ZIP 已保存：$location；当前设备没有可用分享应用。", Toast.LENGTH_LONG).show()
                        }
                }.onFailure {
                    Toast.makeText(this, "诊断 ZIP 备用保存失败：${it.javaClass.simpleName}", Toast.LENGTH_LONG).show()
                }
            }
        }, "carpaly-diagnostic-fallback-export").apply { isDaemon = true }.start()
    }

    private fun exportZip(uri: android.net.Uri, capture: Capture) {
        Toast.makeText(this, "正在生成脱敏诊断包…", Toast.LENGTH_SHORT).show()
        Thread({
            val result = runCatching {
                val output = contentResolver.openOutputStream(uri, "wt") ?: error("无法打开用户选择的导出位置")
                DiagnosticArchive.write(output, capture.files)
                capture.files.values.sumOf { it.toByteArray(Charsets.UTF_8).size }
            }
            runOnUiThread {
                result.onSuccess { bytes ->
                    DiagnosticLogManager.recordExportLocation(applicationContext, uri.toString())
                    renderLogManagement()
                    Toast.makeText(this, "诊断 ZIP 已保存（${bytes} 字节）；不会自动上传。", Toast.LENGTH_LONG).show()
                }.onFailure {
                    Toast.makeText(this, "选择位置写入失败；改用下载目录/系统分享兜底。", Toast.LENGTH_LONG).show()
                    saveAndOfferShareFallback(pendingExportFilename, capture)
                }
            }
        }, "carpaly-diagnostic-export").apply { isDaemon = true }.start()
    }

    private fun confirmClear() {
        android.app.AlertDialog.Builder(this)
            .setTitle("清空诊断日志？")
            .setMessage("清空本应用的结构化历史、CarPlay 会话日志和崩溃日志；已导出的 ZIP 不受影响。")
            .setNegativeButton("取消", null)
            .setPositiveButton("清空") { _, _ -> clearLogsInBackground() }
            .show()
    }

    private fun clearLogsInBackground() {
        val wasEnabled = DiagnosticLogManager.isEnabled(this)
        DiagnosticLogManager.setEnabled(this, false)
        Toast.makeText(this, "正在安全清空本机日志…", Toast.LENGTH_SHORT).show()
        Thread({
            val result = runCatching {
                check(AsyncDiagnosticLog.awaitIdle(10_000)) { "日志写入队列暂未排空" }
                DiagnosticLogManager.clearFiles(applicationContext)
                GeelyDiagnosticHistory.clear(applicationContext)
            }
            DiagnosticLogManager.setEnabled(applicationContext, wasEnabled)
            runOnUiThread {
                if (isFinishing || isDestroyed) return@runOnUiThread
                lastSnapshotSignature = null
                renderLogManagement()
                renderLogHistory()
                renderSnapshot()
                Toast.makeText(this,
                    if (result.isSuccess) "本机日志已清空${if (wasEnabled) "；日志记录仍保持开启" else ""}"
                    else "日志未清空：${result.exceptionOrNull()?.javaClass?.simpleName ?: "未知错误"}",
                    Toast.LENGTH_LONG).show()
            }
        }, "carpaly-diagnostic-log-clear").apply { isDaemon = true }.start()
    }

    private fun startSpeakerTest() {
        if (isFinishing || isDestroyed) return
        stopSpeakerTest()
        runCatching {
            val sampleRate = 44_100
            val durationMs = 400
            val count = sampleRate * durationMs / 1000
            val samples = ShortArray(count) { index ->
                (kotlin.math.sin(2.0 * Math.PI * 440.0 * index / sampleRate) * Short.MAX_VALUE * 0.025).toInt().toShort()
            }
            val track = AudioTrack.Builder()
                .setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ASSISTANCE_SONIFICATION)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION).build())
                .setAudioFormat(AudioFormat.Builder().setSampleRate(sampleRate).setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                    .setChannelMask(AudioFormat.CHANNEL_OUT_MONO).build())
                .setBufferSizeInBytes(samples.size * 2)
                .setTransferMode(AudioTrack.MODE_STATIC)
                .build()
            track.setVolume(0.05f)
            track.write(samples, 0, samples.size)
            speakerTrack = track
            track.play()
            speakerTestStatus = "OBSERVED · AudioTrack API accepted playback; audibility NOT_TESTED"
            if (::speakerStatus.isInitialized) speakerStatus.text = speakerTestStatus
            GeelyDiagnosticHistory.append(this, "用户启动低电平扬声器提示音测试（AudioTrack API 开始播放；实际听感未验证）",
                "speaker_test_started", "audio", "INFO", diagnosticSessionId)
            speakerStop = Runnable {
                speakerTestStatus = "OBSERVED · short AudioTrack playback completed; audibility NOT_TESTED"
                speakerStatus.text = speakerTestStatus
                GeelyDiagnosticHistory.append(this, "短时扬声器提示音 API 播放结束；实际听感未验证",
                    "speaker_test_completed", "audio", "INFO", diagnosticSessionId)
                stopSpeakerTest()
            }.also {
                handler.postAtTime(it, speakerStopToken, android.os.SystemClock.uptimeMillis() + 700)
            }
            Toast.makeText(this, "提示音已播放（低音量）", Toast.LENGTH_SHORT).show()
        }.onFailure {
            speakerTestStatus = "ERROR · ${it.javaClass.simpleName}; audibility NOT_TESTED"
            if (::speakerStatus.isInitialized) speakerStatus.text = speakerTestStatus
            GeelyDiagnosticHistory.append(this, "扬声器 API 测试失败：${it.javaClass.simpleName}",
                "speaker_test_failed", "audio", "ERROR", diagnosticSessionId)
            stopSpeakerTest()
            Toast.makeText(this, "提示音测试不可用：${it.javaClass.simpleName}", Toast.LENGTH_LONG).show()
        }
    }

    private fun stopSpeakerTest() {
        handler.removeCallbacksAndMessages(speakerStopToken)
        speakerStop = null
        speakerTrack?.let { track -> runCatching { track.pause() }; runCatching { track.flush() }; runCatching { track.release() } }
        speakerTrack = null
    }

    private val speakerStopToken = Any()

    private fun requestOrRunMicrophoneTest() {
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            microphoneTestStatus = "PERMISSION_DENIED"
            GeelyDiagnosticHistory.append(this, "麦克风测试未启动：RECORD_AUDIO 权限未授予",
                "microphone_test_denied", "audio", "WARN", diagnosticSessionId)
            micPermission.launch(Manifest.permission.RECORD_AUDIO)
        } else runMicrophoneTest()
    }

    private fun runMicrophoneTest() {
        if (micThread?.isAlive == true) return
        microphoneTestStatus = "RUNNING · 1500 ms RMS only; no audio saved"
        GeelyDiagnosticHistory.append(this, "用户主动启动前台麦克风短测；不保存原始录音",
            "microphone_test_started", "audio", "INFO", diagnosticSessionId)
        micStatus.text = "OBSERVED · 正在前台短时采样；不保存音频…"
        micThread = Thread({
            var recorder: AudioRecord? = null
            val result = runCatching {
                val sampleRate = 16_000
                val min = AudioRecord.getMinBufferSize(sampleRate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
                require(min > 0) { "当前设备不支持录音格式" }
                recorder = AudioRecord(MediaRecorder.AudioSource.MIC, sampleRate, AudioFormat.CHANNEL_IN_MONO,
                    AudioFormat.ENCODING_PCM_16BIT, maxOf(min, 4096))
                require(recorder?.state == AudioRecord.STATE_INITIALIZED) { "麦克风初始化失败" }
                recorder?.startRecording()
                val data = ShortArray(1024)
                val start = android.os.SystemClock.elapsedRealtime()
                var squares = 0.0
                var samples = 0L
                while (!Thread.currentThread().isInterrupted && android.os.SystemClock.elapsedRealtime() - start < 1_500) {
                    val read = recorder?.read(data, 0, data.size, AudioRecord.READ_NON_BLOCKING) ?: 0
                    if (read > 0) {
                        for (index in 0 until read) { val value = data[index].toDouble(); squares += value * value }
                        samples += read
                    } else Thread.sleep(20)
                }
                require(samples > 0) { "没有采集到音频样本" }
                val rms = sqrt(squares / samples) / Short.MAX_VALUE
                "OBSERVED · 已采集 $samples 个样本，RMS ${(rms * 100).toInt()}%（原始音频未保存）"
            }
            runCatching { recorder?.stop() }
            runCatching { recorder?.release() }
            val display = result.getOrElse { "NO_DATA · ${it.javaClass.simpleName}（音频未保存）" }
            microphoneTestStatus = if (result.isSuccess) "OBSERVED · RMS computed; raw samples not saved" else "ERROR · ${result.exceptionOrNull()?.javaClass?.simpleName ?: "unavailable"}"
            GeelyDiagnosticHistory.append(this, "麦克风自测完成：${if (result.isSuccess) "已采集样本并计算 RMS" else "不可用"}；未保存音频",
                if (result.isSuccess) "microphone_test_completed" else "microphone_test_failed",
                "audio", if (result.isSuccess) "INFO" else "WARN", diagnosticSessionId)
            runOnUiThread { if (!isFinishing && !isDestroyed) micStatus.text = display }
        }, "carpaly-mic-test").apply { isDaemon = true; start() }
    }

    private fun audioTypeName(type: Int): String = when (type) {
        AudioDeviceInfo.TYPE_BUILTIN_SPEAKER -> "内置扬声器"
        AudioDeviceInfo.TYPE_BUILTIN_EARPIECE -> "听筒"
        AudioDeviceInfo.TYPE_BLUETOOTH_A2DP -> "蓝牙 A2DP"
        AudioDeviceInfo.TYPE_BLUETOOTH_SCO -> "蓝牙 SCO"
        AudioDeviceInfo.TYPE_USB_DEVICE -> "USB 音频设备"
        AudioDeviceInfo.TYPE_USB_HEADSET -> "USB 耳机"
        AudioDeviceInfo.TYPE_HDMI -> "HDMI"
        AudioDeviceInfo.TYPE_LINE_ANALOG -> "模拟线路输出"
        AudioDeviceInfo.TYPE_LINE_DIGITAL -> "数字线路输出"
        AudioDeviceInfo.TYPE_AUX_LINE -> "AUX"
        else -> "Android 音频设备类型 $type"
    }

    private fun safeBuildValue(value: String?): String = value?.let(DiagnosticRedactor::redact)?.take(140) ?: "已隐藏/无数据"
    private fun json(value: Map<String, Any?>): String = JSONObject(value).toString(2)
    private fun nowIso(): String = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSS'Z'", Locale.US)
        .apply { timeZone = TimeZone.getTimeZone("UTC") }.format(Date())
    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()

    private data class Capture(val files: Map<String, String>, val panels: Map<String, String>, val signature: String)
}

internal object BuildIdentity {
    /** App BuildConfig is generated by the Android application module; unit-test hosts may not have it. */
    fun gitCommit(): String = runCatching {
        Class.forName("com.shilapi.xcertplay.BuildConfig").getField("GIT_COMMIT").get(null) as? String
    }.getOrNull()?.takeIf { it.matches(Regex("[0-9a-f]{7,40}")) } ?: "unknown"
}
