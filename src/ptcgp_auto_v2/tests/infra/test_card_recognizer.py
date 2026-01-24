
import unittest
from unittest.mock import MagicMock, patch
import numpy as np
from PIL import Image
import cv2

from ptcgp_auto_v2.infra.card_recognizer import CardRecognizer
from ptcgp_auto_v2.infra.adb import AdbController
from ptcgp_auto_v2.infra.template import TemplateMatcher

class TestCardRecognizer(unittest.TestCase):
    def setUp(self):
        self.mock_adb = MagicMock(spec=AdbController)
        self.mock_tm = MagicMock(spec=TemplateMatcher)
        self.recognizer = CardRecognizer(self.mock_adb, self.mock_tm)

    def test_analyze_result_screen_with_scale_parameter(self):
        """
        Test that analyze_result_screen accepts 'scale' parameter and uses it.
        This test is expected to fail initially because the method signature doesn't match.
        """
        # Setup mocks
        self.mock_tm._loaded_pack_templates = ['test_card']

        # Create a 100x100 dummy template
        template_img = np.zeros((100, 100, 3), dtype=np.uint8)
        # Draw a white rect in the middle to make it matchable
        cv2.rectangle(template_img, (25, 25), (75, 75), (255, 255, 255), -1)
        self.mock_tm.templates = {'test_card': template_img}

        # Create a screenshot that would match the template IF SCALED
        # Let's say scale is 0.5. So on screen the object should be 50x50.
        # But usually 'scale' scales the TEMPLATE to match the screen.
        # If scale=0.5, template becomes 50x50.
        # So we put a 50x50 object on the screen.

        scale = 0.5
        screen_img = np.zeros((500, 500, 3), dtype=np.uint8)
        # Draw the "scaled" version of the template on the screen
        # Template inner rect was 50x50 (25 to 75). Scaled by 0.5 -> 25x25.
        # Template size 100x100 -> 50x50.
        # Let's just put the exact pixels that resizing the template would produce.
        expected_template_size = (int(100 * scale), int(100 * scale))
        scaled_template = cv2.resize(template_img, expected_template_size)

        # Paste it at 200, 200
        h, w = scaled_template.shape[:2]
        screen_img[200:200+h, 200:200+w] = scaled_template

        # Convert to PIL for ADB mock
        screen_pil = Image.fromarray(cv2.cvtColor(screen_img, cv2.COLOR_BGR2RGB))
        self.mock_adb.screenshot.return_value = screen_pil

        # Act
        # This will raise TypeError if 'scale' is not accepted
        results = self.recognizer.analyze_result_screen(scale=scale, threshold=0.8)

        # Assert
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, 'test_card')
        self.assertGreaterEqual(results[0].confidence, 0.8)
