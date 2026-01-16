"""
OCR 识别实现
"""

from typing import List, Dict

from PIL import Image

from ptcgp_auto import config
from ptcgp_auto.logger import get_logger

logger = get_logger(__name__)


def perform_ocr(image: Image.Image) -> List[Dict]:
    """使用 Apple Vision Framework 进行 OCR

    Args:
        image: PIL Image 对象

    Returns:
        识别结果列表，每项包含 text, box, confidence
    """
    import Vision
    import Quartz
    from Foundation import NSData
    import objc

    width = image.width
    height = image.height

    import io

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    png_data = buffer.getvalue()
    buffer.close()

    results = []

    with objc.autorelease_pool():
        ns_data = NSData.dataWithBytes_length_(png_data, len(png_data))
        image_source = Quartz.CGImageSourceCreateWithData(ns_data, None)
        cg_image = Quartz.CGImageSourceCreateImageAtIndex(image_source, 0, None)

        if cg_image is None:
            logger.error("无法创建 CGImage")
            return []

        request = Vision.VNRecognizeTextRequest.alloc().init()

        if config.OCR_RECOGNITION_LEVEL == "fast":
            request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelFast)
        else:
            request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)

        request.setRecognitionLanguages_(config.OCR_LANGUAGES)
        request.setAutomaticallyDetectsLanguage_(True)

        handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(
            cg_image, None
        )

        success = handler.performRequests_error_([request], None)

        if not success:
            logger.error("OCR 请求执行失败")
            return []

        observations = request.results()

        if observations:
            for observation in observations:
                top_candidate = observation.topCandidates_(1)
                if top_candidate and len(top_candidate) > 0:
                    text = str(top_candidate[0].string())
                    confidence = float(top_candidate[0].confidence())

                    bounding_box = observation.boundingBox()
                    x = bounding_box.origin.x
                    y = bounding_box.origin.y
                    w = bounding_box.size.width
                    h = bounding_box.size.height

                    x1 = int(x * width)
                    y1 = int((1 - y - h) * height)
                    x2 = int((x + w) * width)
                    y2 = int((1 - y) * height)

                    results.append(
                        {
                            "text": text,
                            "box": (x1, y1, x2, y2),
                            "confidence": confidence,
                        }
                    )

    return results
