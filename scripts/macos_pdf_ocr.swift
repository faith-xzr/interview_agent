import AppKit
import Foundation
import PDFKit
import Vision

if CommandLine.arguments.count < 2 {
    fputs("usage: swift macos_pdf_ocr.swift <pdf>\n", stderr)
    exit(2)
}

let url = URL(fileURLWithPath: CommandLine.arguments[1])
guard let document = PDFDocument(url: url) else {
    fputs("failed to open pdf\n", stderr)
    exit(1)
}

var output: [String] = []

for pageIndex in 0..<document.pageCount {
    guard let page = document.page(at: pageIndex) else {
        continue
    }

    let bounds = page.bounds(for: .mediaBox)
    let scale: CGFloat = 2.0
    let imageSize = NSSize(width: bounds.width * scale, height: bounds.height * scale)
    let image = page.thumbnail(of: imageSize, for: .mediaBox)
    guard let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        continue
    }

    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.usesLanguageCorrection = true
    request.recognitionLanguages = ["zh-Hans", "en-US"]

    let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
    try handler.perform([request])

    let lines = (request.results ?? []).compactMap { observation in
        observation.topCandidates(1).first?.string
    }
    output.append(contentsOf: lines)
}

print(output.joined(separator: "\n"))
