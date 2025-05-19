import unittest
import sys
import os

# Add the project root to the Python path to import modules properly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.summarizer.service import SummarizerService

class TestCitationEdgeCases(unittest.TestCase):
    """Test edge cases in citation parsing that have caused issues in production"""

    def setUp(self):
        """Set up test fixtures"""
        self.service = SummarizerService()
        # Create a sample citation map with Discord URLs
        self.citation_map = {
            'c1': 'https://discord.com/channels/123/456/789',
            'c2': 'https://discord.com/channels/123/456/790',
            'c3': 'https://discord.com/channels/123/456/791',
            'c4': 'https://discord.com/channels/123/456/792',
            'c5': 'https://discord.com/channels/123/456/793',
            'c10': 'https://discord.com/channels/123/456/800',
            'c178': 'https://discord.com/channels/123/456/978',
            'c185': 'https://discord.com/channels/123/456/985',
            'c186': 'https://discord.com/channels/123/456/986',
            'c187': 'https://discord.com/channels/123/456/987',
            'c208': 'https://discord.com/channels/123/456/1008',
            'c723': 'https://discord.com/channels/123/456/1523',
            'c724': 'https://discord.com/channels/123/456/1524',
            'c741': 'https://discord.com/channels/123/456/1541',
            'c765': 'https://discord.com/channels/123/456/1565',
        }

    def test_comma_separated_citations(self):
        """Test citations separated by commas the way they appeared in the problematic output"""
        # This simulates the problematic format we saw but with bracketed citations
        input_text = "Ben introduced himself multiple times [c3], [[c4]], [c7]."
        # We only have c3 and c4 in our map, c7 should remain as is but converted to [7]
        expected_parts = [
            f"[3]({self.citation_map['c3']})",
            f"[4]({self.citation_map['c4']})",
            "[7]"  # This should remain as [7] but not linked since c7 is not in our map
        ]
        result = self.service._parse_citations(input_text, self.citation_map)
        for part in expected_parts:
            self.assertIn(part, result)
        
        # Double brackets should not appear in the result
        self.assertNotIn("[[c", result)
        self.assertNotIn("]]", result)
        
        # Original citations should not appear in the result
        self.assertNotIn("[c3]", result)
        self.assertNotIn("[c4]", result)
        self.assertNotIn("[c7]", result)

    def test_nested_citation_brackets(self):
        """Test nested citation brackets which can cause rendering issues"""
        input_text = "This contains nested citation brackets [[c1]] and [[[c2]]]."
        result = self.service._parse_citations(input_text, self.citation_map)
        
        # The result should have properly formatted links with numeric IDs without nested brackets
        self.assertIn(f"[1]({self.citation_map['c1']})", result)
        self.assertIn(f"[2]({self.citation_map['c2']})", result)
        
        # Make sure we don't have triple brackets or other nesting issues
        self.assertNotIn("[[[", result)
        self.assertNotIn("]]]", result)
        
        # Original citations should not appear in the result
        self.assertNotIn("[c1]", result)
        self.assertNotIn("[c2]", result)

    def test_comma_in_citation_group(self):
        """Test comma formatting in citation groups"""
        input_text = "This has a citation group [c1, c2, c3]."
        result = self.service._parse_citations(input_text, self.citation_map)
        
        # Confirm each citation is properly linked with numeric IDs
        self.assertIn(f"[1]({self.citation_map['c1']})", result)
        self.assertIn(f"[2]({self.citation_map['c2']})", result)
        self.assertIn(f"[3]({self.citation_map['c3']})", result)
        
        # The links should be comma-separated but not nested in brackets
        self.assertNotIn("[c1, c2, c3]", result)
        self.assertNotIn("[1, 2, 3]", result)
        
        # Original citations should not appear in the result
        self.assertNotIn("[c1]", result)
        self.assertNotIn("[c2]", result)
        self.assertNotIn("[c3]", result)

    def test_sequential_citations(self):
        """Test sequential citations that might run together"""
        input_text = "This has sequential citations [c1][c2][c3]."
        result = self.service._parse_citations(input_text, self.citation_map)
        
        # Each citation should be properly linked with numeric IDs
        self.assertIn(f"[1]({self.citation_map['c1']})", result)
        self.assertIn(f"[2]({self.citation_map['c2']})", result)
        self.assertIn(f"[3]({self.citation_map['c3']})", result)
        
        # Original citations should not appear in the result
        self.assertNotIn("[c1]", result)
        self.assertNotIn("[c2]", result)
        self.assertNotIn("[c3]", result)

    def test_citation_after_period(self):
        """Test citation immediately after a period, which might not get parsed correctly"""
        input_text = "This is a sentence.[c1] Another sentence [c2]."
        result = self.service._parse_citations(input_text, self.citation_map)
        
        # Both citations should be properly linked with numeric IDs
        self.assertIn(f"[1]({self.citation_map['c1']})", result)
        self.assertIn(f"[2]({self.citation_map['c2']})", result)
        
        # Original citations should not appear in the result
        self.assertNotIn("[c1]", result)
        self.assertNotIn("[c2]", result)

    def test_citation_with_markdown_link_conflict(self):
        """Test citation that might conflict with existing markdown links"""
        input_text = "This has a [link](https://example.com) and a citation [c1]."
        result = self.service._parse_citations(input_text, self.citation_map)
        
        # The link should remain unchanged
        self.assertIn("[link](https://example.com)", result)
        # The citation should be properly linked with numeric ID
        self.assertIn(f"[1]({self.citation_map['c1']})", result)
        
        # Original citation should not appear in the result
        self.assertNotIn("[c1]", result)

    def test_realistic_model_output(self):
        """Test a realistic example of formatted text from a model with citations"""
        input_text = """# Action Items ✨
- **Ben:** talk to the summarizer in a day [c5]

# Conversation Summary ✨
## Conversation Purpose
Ben initiated the conversation by greeting others, introducing himself, and inquiring about other participants.

## Key Takeaways
- Ben introduced himself multiple times [c3], [c4], [c1].
- He inquired about the presence of others [c2].
- He requested a follow-up conversation with the summarizer [c5].

## Topics
### Greetings and Introductions
- Ben repeatedly greeted and introduced himself [c1], [c3], [c4].
- He asked who else was present in the conversation [c2]."""

        result = self.service._parse_citations(input_text, self.citation_map)
        
        # Check that citations are properly formatted with numeric IDs
        for i in range(1, 6):
            citation_id = f'c{i}'
            numeric_id = citation_id[1:]  # Remove the 'c' prefix
            if citation_id in self.citation_map:
                self.assertIn(f"[{numeric_id}]({self.citation_map[citation_id]})", result)
                # Original citation should not appear in the result
                self.assertNotIn(f"[{citation_id}]", result)
        
        # Check that the Markdown structure is preserved
        self.assertIn("# Action Items ✨", result)
        self.assertIn("# Conversation Summary ✨", result)
        self.assertIn("## Conversation Purpose", result)
        self.assertIn("## Key Takeaways", result)
        self.assertIn("## Topics", result)
        self.assertIn("### Greetings and Introductions", result)
        
        # Check that the bold formatting is preserved
        self.assertIn("**Ben:**", result)

    def test_complex_range_with_comma(self):
        """Test citation format with range and comma like [c723-c741, c765]"""
        input_text = "This has a complex citation format [c723-c741, c765]."
        
        # Expected should have links for the range bounds and the individual citation
        result = self.service._parse_citations(input_text, self.citation_map)
        
        # Check that range bounds and individual citation are correctly linked
        self.assertIn(f"[723]({self.citation_map['c723']})", result)
        self.assertIn(f"[724]({self.citation_map['c724']})", result)
        self.assertIn(f"[741]({self.citation_map['c741']})", result)
        self.assertIn(f"[765]({self.citation_map['c765']})", result)
        
        # Make sure the original format is replaced
        self.assertNotIn("[c723-c741, c765]", result)
        
        # Make sure the citations are properly comma-separated
        # We'll check for ", " between the last citation in the range and the individual citation
        range_end_pos = result.find(f"[741]({self.citation_map['c741']})")
        individual_pos = result.find(f"[765]({self.citation_map['c765']})")
        between_text = result[range_end_pos + len(f"[741]({self.citation_map['c741']})"): individual_pos]
        self.assertIn(", ", between_text)

    def test_comma_followed_by_range(self):
        """Test citation format with comma followed by range like [c178, c185-c208]"""
        input_text = "This has a complex citation format [c178, c185-c208]."
        
        # Expected should have links for the individual citation and range bounds
        result = self.service._parse_citations(input_text, self.citation_map)
        
        # Check that individual citation and range bounds are correctly linked
        self.assertIn(f"[178]({self.citation_map['c178']})", result)
        self.assertIn(f"[185]({self.citation_map['c185']})", result)
        self.assertIn(f"[186]({self.citation_map['c186']})", result)
        self.assertIn(f"[187]({self.citation_map['c187']})", result)
        self.assertIn(f"[208]({self.citation_map['c208']})", result)
        
        # Make sure the original format is replaced
        self.assertNotIn("[c178, c185-c208]", result)
        
        # Make sure the citations are properly comma-separated
        # We'll check for ", " between the individual citation and the first citation in the range
        individual_pos = result.find(f"[178]({self.citation_map['c178']})")
        range_start_pos = result.find(f"[185]({self.citation_map['c185']})")
        between_text = result[individual_pos + len(f"[178]({self.citation_map['c178']})"): range_start_pos]
        self.assertIn(", ", between_text)

    def test_multiple_ranges_and_individual_citations(self):
        """Test citation format with multiple ranges and individual citations"""
        input_text = "This has very complex citations [c1-c3, c5, c185-c187, c765]."
        
        result = self.service._parse_citations(input_text, self.citation_map)
        
        # Check that all citations are correctly linked
        for citation_id in ['c1', 'c2', 'c3', 'c5', 'c185', 'c186', 'c187', 'c765']:
            num_id = citation_id[1:]
            self.assertIn(f"[{num_id}]({self.citation_map[citation_id]})", result)
        
        # Make sure the original format is replaced
        self.assertNotIn("[c1-c3, c5, c185-c187, c765]", result)

if __name__ == '__main__':
    unittest.main()