"""Tests for the buses app
"""
from django.test import TestCase
from . import utils


class UtilsTests(TestCase):
    """Tests for the buses.utils module
    """
    def test_minify(self):
        """Test that the minify function minifies (while preserving some characters) as expected
        """
        self.assertEqual(utils.minify("""
                   \n
            <marquee>
                {% if foo %}\n     \n                    {% if bar %}
                        <strong>Golf sale</strong>  \n
                    {% endif %}
                {% endif %}
            </marquee>
            """), """
<marquee>
{% if foo %}{% if bar %}<strong>Golf sale</strong>  \n{% endif %}{% endif %}</marquee>
""")
