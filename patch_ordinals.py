import re

with open('assemblyzero/workflows/testing/atlas.py', 'r') as f:
    content = f.read()

content = re.sub(r'TOTAL_STEPS = 13', 'TOTAL_STEPS = 14', content)

content = re.sub(r'("N5_verify_green": \{[^}]*"ordinal":\s*)8', r'\g<1>9', content)
content = re.sub(r'("N6_e2e_validation": \{[^}]*"ordinal":\s*)9', r'\g<1>10', content)
content = re.sub(r'("N7_finalize": \{[^}]*"ordinal":\s*)10', r'\g<1>11', content)
content = re.sub(r'("N7_5_adversarial": \{[^}]*"ordinal":\s*)11', r'\g<1>12', content)
content = re.sub(r'("N8_document": \{[^}]*"ordinal":\s*)12', r'\g<1>13', content)
content = re.sub(r'("N9_cleanup": \{[^}]*"ordinal":\s*)13', r'\g<1>14', content)

with open('assemblyzero/workflows/testing/atlas.py', 'w') as f:
    f.write(content)
