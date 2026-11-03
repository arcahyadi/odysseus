import Foundation
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers
import MLX
import LaMa
import MIGAN

struct Args {
    var model = ""
    var image = ""
    var mask = ""
    var output = ""
    var mode = ""
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
    out.mask = value(after: "--mask", in: argv) ?? ""
    out.output = value(after: "--output", in: argv) ?? ""
    out.mode = value(after: "--mode", in: argv) ?? ""
    guard !out.model.isEmpty, !out.image.isEmpty, !out.mask.isEmpty, !out.output.isEmpty else {
        throw BridgeError.usage("usage: odysseus-mlx-inpaint --model weights.safetensors --image input.png --mask mask.png --output output.png [--mode best|fast]")
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
    let source = try decodeCGImage(args.image)
    let mask = try decodeCGImage(args.mask)
    let lower = args.model.lowercased()
    let mode = args.mode.lowercased()
    let output: CGImage

    if lower.contains("mi-gan") || lower.contains("migan") || mode == "fast" {
        let resolution = lower.contains("512") ? 512 : 256
        let inpainter = try MIGANInpainter.fromPretrained(args.model, resolution: resolution, dtype: .float16)
        output = inpainter(source, mask: mask)
    } else {
        let inpainter = try LaMaInpainter.fromPretrained(args.model, dtype: .bfloat16)
        output = inpainter(source, mask: mask)
    }
    try encodePNG(output, args.output)
} catch {
    fputs("\(error)\n", stderr)
    exit(1)
}
