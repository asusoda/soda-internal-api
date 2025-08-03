import unittest
import re
import sys
import os

# Add the project root to the Python path to import modules properly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.summarizer.service import SummarizerService

class TestCitationParsing(unittest.TestCase):
    """Test cases for the citation parsing functionality in SummarizerService"""

    def setUp(self):
        """Set up test fixtures"""
        self.service = SummarizerService()
        # Create a sample citation map for testing
        self.citation_map = {
            'c1': 'https://discord.com/channels/123/456/789',
            'c2': 'https://discord.com/channels/123/456/790',
            'c3': 'https://discord.com/channels/123/456/791',
            'c4': 'https://discord.com/channels/123/456/792',
            'c5': 'https://discord.com/channels/123/456/793',
            'c10': 'https://discord.com/channels/123/456/800',
        }

    def test_standard_citation_format(self):
        """Test standard citation format [c1] converts to [1]"""
        input_text = "This is a test [c1] with a citation."
        # Should convert [c1] to [1] with the link
        expected = f"This is a test [1]({self.citation_map['c1']}) with a citation."
        result = self.service._parse_citations(input_text, self.citation_map)
        self.assertEqual(result, expected)

    def test_multiple_standard_citations(self):
        """Test multiple standard citations [c1], [c2] convert to [1], [2]"""
        input_text = "This is a test [c1] with multiple [c2] citations."
        expected = f"This is a test [1]({self.citation_map['c1']}) with multiple [2]({self.citation_map['c2']}) citations."
        result = self.service._parse_citations(input_text, self.citation_map)
        self.assertEqual(result, expected)

    def test_only_bracketed_citations_supported(self):
        """Test that bare citations (without brackets) are NOT replaced"""
        input_text = "This is a test c1 with a bare citation."
        expected = input_text  # Should remain unchanged
        result = self.service._parse_citations(input_text, self.citation_map)
        self.assertEqual(result, expected)

    def test_range_citation_format(self):
        """Test range citation format [c1-c3] converts to [1-3]"""
        input_text = "This is a test [c1-c3] with a range citation."
        # Expected should have individual links for 1, 2, 3 (not c1, c2, c3)
        expected_parts = [
            f"[1]({self.citation_map['c1']})",
            f"[2]({self.citation_map['c2']})",
            f"[3]({self.citation_map['c3']})"
        ]
        result = self.service._parse_citations(input_text, self.citation_map)
        # The replacement includes comma-separated links, so we check each part is in the result
        for part in expected_parts:
            self.assertIn(part, result)
        # Make sure the original format is replaced
        self.assertNotIn("[c1-c3]", result)
        self.assertNotIn("[1-3]", result)  # Should be expanded to individual citations

    def test_grouped_citation_format(self):
        """Test grouped citation format [c1, c2, c3] converts to [1, 2, 3]"""
        input_text = "This is a test [c1, c2, c3] with a grouped citation."
        # Expected should have individual links for 1, 2, 3 (not c1, c2, c3)
        expected_parts = [
            f"[1]({self.citation_map['c1']})",
            f"[2]({self.citation_map['c2']})",
            f"[3]({self.citation_map['c3']})"
        ]
        result = self.service._parse_citations(input_text, self.citation_map)
        # The replacement includes comma-separated links, so we check each part is in the result
        for part in expected_parts:
            self.assertIn(part, result)
        # Make sure the original formats are replaced
        self.assertNotIn("[c1, c2, c3]", result)
        self.assertNotIn("[1, 2, 3]", result)  # Should be expanded to individual citations

    def test_citation_only_in_brackets(self):
        """Test that citations are only processed when in brackets"""
        input_text = "This has [c1] in brackets but c1 without brackets and c1at in a word."
        result = self.service._parse_citations(input_text, self.citation_map)
        # [c1] should be replaced with [1]
        self.assertIn(f"[1]({self.citation_map['c1']})", result)
        # 'c1' without brackets should remain unchanged
        self.assertIn(" c1 ", result)
        # 'c1at' should remain unchanged
        self.assertIn("c1at", result)

    def test_already_processed_citation(self):
        """Test that already processed citations are not replaced again"""
        # Start with a citation that's already processed with the numeric format
        input_text = f"This has a citation [1]({self.citation_map['c1']}) that should not be processed again."
        result = self.service._parse_citations(input_text, self.citation_map)
        # The citation should remain unchanged - no double processing
        self.assertEqual(result, input_text)
        # Make sure we don't get something like [1](url)](url)
        self.assertNotIn(")]", result)

    def test_citation_in_markdown_header(self):
        """Test citations in Markdown headers"""
        input_text = "# Header with citation [c1]\n## Subheader with citation [c2]"
        expected = f"# Header with citation [1]({self.citation_map['c1']})\n## Subheader with citation [2]({self.citation_map['c2']})"
        result = self.service._parse_citations(input_text, self.citation_map)
        self.assertEqual(result, expected)

    def test_citation_in_bullet_points(self):
        """Test citations in bullet points"""
        input_text = "- Bullet point with citation [c1]\n- Another bullet with citation [c2]"
        expected = f"- Bullet point with citation [1]({self.citation_map['c1']})\n- Another bullet with citation [2]({self.citation_map['c2']})"
        result = self.service._parse_citations(input_text, self.citation_map)
        self.assertEqual(result, expected)

    def test_missing_citation_id(self):
        """Test behavior with citation IDs not in the map"""
        input_text = "This has a valid citation [c1] and an invalid one [c99]."
        # c1 should be replaced with [1], but [c99] should be converted to [99] but not linked
        expected = f"This has a valid citation [1]({self.citation_map['c1']}) and an invalid one [99]."
        result = self.service._parse_citations(input_text, self.citation_map)
        self.assertEqual(result, expected)

    def test_complex_mixed_citations(self):
        """Test complex mixed citation formats"""
        input_text = """
# Summary ✨
- This point has standard citation [c1] and bracketed citation [c2]
- This has a range citation [c3-c5]
- This has grouped citations [c1, c4, c5]
- This mentions [c10] at the end
"""
        result = self.service._parse_citations(input_text, self.citation_map)
        
        # Check that all citation formats are properly processed with numeric IDs
        self.assertIn(f"[1]({self.citation_map['c1']})", result)
        self.assertIn(f"[2]({self.citation_map['c2']})", result)
        self.assertIn(f"[3]({self.citation_map['c3']})", result)
        self.assertIn(f"[4]({self.citation_map['c4']})", result)
        self.assertIn(f"[5]({self.citation_map['c5']})", result)
        self.assertIn(f"[10]({self.citation_map['c10']})", result)
        
        # Ensure no double processing
        self.assertNotIn("[[c", result)
        self.assertNotIn(")]", result)
        
        # Ensure range and group citations are replaced
        self.assertNotIn("[c3-c5]", result)
        self.assertNotIn("[3-5]", result)
        self.assertNotIn("[c1, c4, c5]", result)
        self.assertNotIn("[1, 4, 5]", result)

if __name__ == '__main__':
    unittest.main()