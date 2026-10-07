import AppKit

final class WorkbenchLauncher: NSObject, NSApplicationDelegate {
    private var backend: Process?
    private var timer: Timer?
    private var sessionURL: URL?
    private var runFolder: URL?
    private var readyFile: URL?
    private var quitting = false
    private let dataRoot = ProcessInfo.processInfo.environment["HKUST_WORKBENCH_DATA_DIR"].map { URL(fileURLWithPath: $0) } ?? FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0].appendingPathComponent("HKUST_Canvas_MCP")
    private var logURL: URL { dataRoot.appendingPathComponent("launcher/launcher.log") }

    func applicationDidFinishLaunching(_ notification: Notification) {
        let menu = NSMenu()
        let root = NSMenuItem()
        let appMenu = NSMenu()
        appMenu.addItem(withTitle: "Open workbench", action: #selector(openWorkbench), keyEquivalent: "o").target = self
        appMenu.addItem(withTitle: "Show logs", action: #selector(showLogs), keyEquivalent: "l").target = self
        appMenu.addItem(.separator())
        appMenu.addItem(withTitle: "Quit Canvas Workbench", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        root.submenu = appMenu
        menu.addItem(root)
        NSApp.mainMenu = menu
        start()
    }

    func start() {
        do {
            let folder = dataRoot.appendingPathComponent("launcher/run-" + UUID().uuidString)
            try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
            runFolder = folder
            let ready = folder.appendingPathComponent("ready.json")
            readyFile = ready
            if !FileManager.default.fileExists(atPath: logURL.path) {
                FileManager.default.createFile(atPath: logURL.path, contents: nil, attributes: [.posixPermissions: 0o600])
            }
            let log = try FileHandle(forWritingTo: logURL)
            try log.truncate(atOffset: 0)
            let process = Process()
            process.executableURL = Bundle.main.resourceURL!.appendingPathComponent("backend/workbench-server")
            let port = ProcessInfo.processInfo.environment["HKUST_WORKBENCH_PORT"] ?? String(UserDefaults.standard.integer(forKey: "WorkbenchPort") == 0 ? 8765 : UserDefaults.standard.integer(forKey: "WorkbenchPort"))
            process.arguments = ["--data-dir", dataRoot.path, "--ready-file", ready.path, "--parent-pid", String(ProcessInfo.processInfo.processIdentifier), "--port", port]
            process.currentDirectoryURL = folder
            process.standardOutput = log
            process.standardError = log
            process.terminationHandler = { [weak self] ended in
                DispatchQueue.main.async {
                    guard let self = self, self.backend === ended, self.sessionURL != nil, !self.quitting else { return }
                    self.backend = nil
                    self.sessionURL = nil
                    self.failure()
                }
            }
            backend = process
            try process.run()
            let deadline = Date().addingTimeInterval(60)
            timer = Timer.scheduledTimer(withTimeInterval: 0.15, repeats: true) { [weak self] _ in
                guard let self = self else { return }
                if let data = try? Data(contentsOf: ready), let state = try? JSONSerialization.jsonObject(with: data) as? [String: Any], let value = state["url"] as? String, let url = URL(string: value), url.host == "127.0.0.1", url.scheme == "http" {
                    self.timer?.invalidate()
                    self.sessionURL = url
                    if state["owned"] as? Bool == false { self.backend = nil }
                    self.openWorkbench()
                    if CommandLine.arguments.contains("--lifecycle-smoke") {
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                            self.stopOwnedServer()
                            print("{\"native_lifecycle\":\"passed\"}")
                            NSApp.terminate(nil)
                        }
                    }
                } else if !process.isRunning || Date() > deadline {
                    self.timer?.invalidate()
                    self.stopOwnedServer()
                    self.failure()
                }
            }
        } catch {
            stopOwnedServer()
            failure()
        }
    }

    @objc func openWorkbench() {
        if CommandLine.arguments.contains("--lifecycle-smoke") { return }
        if let url = sessionURL { NSWorkspace.shared.open(url) }
    }
    @objc func showLogs() { NSWorkspace.shared.open(logURL) }
    func failure() {
        guard !quitting else { return }
        if CommandLine.arguments.contains("--lifecycle-smoke") { exit(1) }
        NSApp.activate(ignoringOtherApps: true)
        let alert = NSAlert()
        alert.messageText = "HKUST Canvas Workbench could not start."
        alert.informativeText = "Check the local launcher logs, then retry. Your Chrome profile and saved work are unchanged."
        alert.addButton(withTitle: "Show logs")
        alert.addButton(withTitle: "Retry")
        alert.addButton(withTitle: "Quit")
        var choice = alert.runModal()
        while choice == .alertFirstButtonReturn { showLogs(); choice = alert.runModal() }
        if choice == .alertSecondButtonReturn { start() }
        else { NSApp.terminate(nil) }
    }
    func stopOwnedServer() {
        timer?.invalidate()
        let owned = backend
        backend = nil
        sessionURL = nil
        if let process = owned, process.isRunning {
            process.terminate()
            let deadline = Date().addingTimeInterval(5)
            while process.isRunning && Date() < deadline { Thread.sleep(forTimeInterval: 0.05) }
            if process.isRunning { kill(process.processIdentifier, SIGKILL) }
        }
        if let folder = runFolder { try? FileManager.default.removeItem(at: folder) }
        runFolder = nil
    }
    func applicationWillTerminate(_ notification: Notification) { quitting = true; stopOwnedServer() }
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool { openWorkbench(); return false }
}

if CommandLine.arguments.contains("--smoke") {
    let process = Process()
    process.executableURL = Bundle.main.resourceURL!.appendingPathComponent("backend/workbench-server")
    process.arguments = ["--self-test"]
    try process.run()
    process.waitUntilExit()
    exit(process.terminationStatus)
} else {
    let app = NSApplication.shared
    let launcher = WorkbenchLauncher()
    app.delegate = launcher
    app.setActivationPolicy(CommandLine.arguments.contains("--lifecycle-smoke") ? .prohibited : .regular)
    app.run()
}
