import Foundation
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers
import MLX
import DDColor

struct Args {
    var model = ""
    var image = ""
    var output = ""
    var tier = ""
}

func value(after flag: String, in args: [String]) -> String? {
    guard let i = args.firstIndex(of: flag), i + 1 < args.count else { return nil }
    return args[i + 1]
}

func parseArgs() throws -> Args {
    let argv = Array(CommandLine.arguments.dropFirst())
    var out = Args()
    out.model = value(after: "--model", in: argv) ?? ""
    out.image = value(after: "--image", in: argv) ?? ""
    out.output = value(after: "--output", in: argv) ?? ""
    out.tier = value(after: "--tier", in: argv) ?? ""
    guard !out.model.isEmpty, !out.image.isEmpty, !out.output.isEmpty else {
        throw BridgeError.usage("usage: odysseus-mlx-colorize --model weights.safetensors --image input.png --output output.png [--tier tiny|large]")
    }
    return out
}

func decodeCGImage(_ path: String) throws -> CGImage {
    let url = URL(fileURLWithPath: path)
    guard let src = CGImageSourceCreateWithURL(url as CFURL, nil),
          let cg = CGImageSourceCreateImageAtIndex(src, 0, nil) else {
        throw BridgeError.decode(path)
    }
    return cg
}

func encodePNG(_ image: CGImage, _ path: String) throws {
    let url = URL(fileURLWithPath: path)
    guard let dest = CGImageDestinationCreateWithURL(url as CFURL, UTType.png.identifier as CFString, 1, nil) else {
        throw BridgeError.encode(path)
    }
    CGImageDestinationAddImage(dest, image, nil)
    guard CGImageDestinationFinalize(dest) else { throw BridgeError.encode(path) }
}

enum BridgeError: Error, CustomStringConvertible {
    case usage(String)
    case decode(String)
    case encode(String)

    var description: String {
        switch self {
        case .usage(let s): return s
        case .decode(let p): return "failed to decode image: \(p)"
        case .encode(let p): return "failed to write PNG: \(p)"
        }
    }
}

do {
    let args = try parseArgs()
    let image = try decodeCGImage(args.image)
    let text = (args.tier + " " + args.model).lowercased()
    let tier: DDColorTier = text.contains("tiny") ? .tiny : .large
    let colorizer = try DDColorColorizer.fromPretrained(
        args.model,
        config: DDColorConfig(tier: tier),
        dtype: .float16
    )
    let output = colorizer(image)
    try encodePNG(output, args.output)
} catch {
    fputs("\(error)\n", stderr)
    exit(1)
}
