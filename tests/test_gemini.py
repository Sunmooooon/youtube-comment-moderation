import unittest

from services.gemini import _as_classification, parse_json_response


class ParseJsonResponseTests(unittest.TestCase):
    def test_parses_plain_json(self):
        self.assertEqual(parse_json_response('[{"id":"abc"}]'), [{"id": "abc"}])

    def test_parses_fenced_json(self):
        payload = "```json\n{\"results\": []}\n```"
        self.assertEqual(parse_json_response(payload), {"results": []})

    def test_string_false_is_not_truthy(self):
        self.assertFalse(_as_classification("false"))
        self.assertTrue(_as_classification("true"))


if __name__ == "__main__":
    unittest.main()
