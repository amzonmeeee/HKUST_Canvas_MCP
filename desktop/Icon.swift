// Render the existing book/concept mark from web/src/assets/canvas-mark.svg.
import AppKit
let folder = URL(fileURLWithPath: CommandLine.arguments[1])
try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
for size in [16, 32, 128, 256, 512] {
    for scale in [1, 2] {
        let pixels = size * scale
        let image = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: pixels, pixelsHigh: pixels, bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: image)
        let transform = AffineTransform(translationByX: 0, byY: CGFloat(pixels))
        let matrix = NSAffineTransform(transform: transform)
        matrix.scaleX(by: CGFloat(pixels) / 40, yBy: -CGFloat(pixels) / 40)
        matrix.concat()
        NSColor(calibratedRed: 0, green: 90 / 255.0, blue: 156 / 255.0, alpha: 1).setFill()
        NSBezierPath(roundedRect: NSRect(x: 0, y: 0, width: 40, height: 40), xRadius: 8, yRadius: 8).fill()
        NSColor(calibratedRed: 245 / 255.0, green: 247 / 255.0, blue: 248 / 255.0, alpha: 1).setStroke()
        let path = NSBezierPath()
        path.lineWidth = 2
        path.lineJoinStyle = .round
        path.move(to: NSPoint(x: 5, y: 8)); path.line(to: NSPoint(x: 17, y: 8)); path.curve(to: NSPoint(x: 20, y: 11), controlPoint1: NSPoint(x: 19, y: 8), controlPoint2: NSPoint(x: 20, y: 9)); path.line(to: NSPoint(x: 20, y: 34)); path.curve(to: NSPoint(x: 15, y: 29), controlPoint1: NSPoint(x: 20, y: 31), controlPoint2: NSPoint(x: 18, y: 29)); path.line(to: NSPoint(x: 5, y: 29)); path.close()
        path.move(to: NSPoint(x: 35, y: 8)); path.line(to: NSPoint(x: 23, y: 8)); path.curve(to: NSPoint(x: 20, y: 11), controlPoint1: NSPoint(x: 21, y: 8), controlPoint2: NSPoint(x: 20, y: 9)); path.line(to: NSPoint(x: 20, y: 34)); path.curve(to: NSPoint(x: 25, y: 29), controlPoint1: NSPoint(x: 20, y: 31), controlPoint2: NSPoint(x: 22, y: 29)); path.line(to: NSPoint(x: 35, y: 29)); path.close(); path.stroke()
        let line = NSBezierPath(); line.lineWidth = 2; line.lineCapStyle = .round
        line.move(to: NSPoint(x: 9, y: 20)); for point in [(13, 24), (20, 14), (27, 21), (31, 16)] { line.line(to: NSPoint(x: point.0, y: point.1)) }; line.stroke()
        NSGraphicsContext.restoreGraphicsState()
        let name = "icon_\(size)x\(size)" + (scale == 2 ? "@2x" : "") + ".png"
        try image.representation(using: .png, properties: [:])!.write(to: folder.appendingPathComponent(name))
    }
}
