from django.test import TestCase
from .utils import minify


class MinifyTests(TestCase):
    def test_minify(self):
        self.assertEqual(minify("""
            
            <marquee>
                {% if foo %}

                    {% if bar %}
                        <strong>Golf sale</strong> 

                    {% endif %}
                {% endif %}
            </marquee>
            """), """
<marquee>
{% if foo %}{% if bar %}<strong>Golf sale</strong> 
{% endif %}{% endif %}</marquee>
""")
