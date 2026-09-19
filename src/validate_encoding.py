import sys
import io
import re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# ============================================================
# Final validation of encoding fixes
# ============================================================

files_to_check = [
    'static/index.html',
    'static/app.js',
    'static/styles.css',
    'server.py',
]

# Mojibake detection patterns (CP437->UTF-8 double-encoded sequences)
# These are sequences that should NOT appear in properly encoded UTF-8 files
MOJIBAKE_PATTERNS = [
    ('\u0393', 'Gamma character (CP437 mojibake indicator)'),
    ('\u2261', 'Three-bar equals (CP437 mojibake indicator)'),
    ('\u00C3\u00A2', 'Ã + â sequence (Latin-1 mojibake)'),
    ('\u00C3\u00B3', 'ó (Latin-1 mojibake for ó)'),
]

# Legitimate chars that should be present
EXPECTED_CHARS = [
    ('—', 'Em-dash (U+2014)'),
    ('→', 'Right arrow (U+2192)'),
    ('⚠', 'Warning sign (U+26A0)'),
    ('·', 'Middle dot (U+00B7)'),
]

# Check for remaining problematic patterns
print("=" * 60)
print("FINAL ENCODING VALIDATION")
print("=" * 60)

total_issues = 0

for fpath in files_to_check:
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"\nERROR reading {fpath}: {e}")
        continue
    
    print(f"\n--- {fpath} ---")
    issues = 0
    
    # Check for mojibake patterns
    for pat, desc in MOJIBAKE_PATTERNS:
        count = content.count(pat)
        if count > 0:
            print(f"  ISSUE: {desc} appears {count} times")
            # Show context of first occurrence
            idx = content.find(pat)
            ctx = content[max(0,idx-40):idx+40].replace('\n', ' ').replace('\r', '')
            print(f"    Context: {repr(ctx)}")
            issues += count
    
    # Check charset declarations for HTML
    if fpath.endswith('.html'):
        if 'charset="UTF-8"' in content or "charset='UTF-8'" in content or 'charset=UTF-8' in content:
            print("  OK: HTML has charset=UTF-8 meta tag")
        else:
            print("  ISSUE: HTML missing charset=UTF-8 meta tag")
            issues += 1
    
    # Check server.py for charset in headers
    if fpath.endswith('server.py'):
        if 'charset=utf-8' in content.lower():
            count = content.lower().count('charset=utf-8')
            print(f"  OK: server.py has {count} charset=utf-8 header declarations")
        else:
            print("  ISSUE: server.py missing charset=utf-8 headers")
            issues += 1
        if 'ensure_ascii=False' in content:
            print("  OK: json.dumps uses ensure_ascii=False")
        else:
            print("  ISSUE: json.dumps missing ensure_ascii=False")
            issues += 1
    
    if issues == 0:
        print("  All checks passed")
    else:
        total_issues += issues

# Check sidebar SVG icons
print("\n--- Sidebar icon check ---")
with open('static/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Check all nav-icons have SVG
nav_icons = re.findall(r'class="nav-icon">(.*?)</span>', html, re.DOTALL)
svg_count = sum(1 for icon in nav_icons if '<svg' in icon)
emoji_count = sum(1 for icon in nav_icons if re.search(r'[\U00010000-\U0010FFFF]', icon))
print(f"  Nav icons total: {len(nav_icons)}")
print(f"  Nav icons with SVG: {svg_count}")
print(f"  Nav icons with emoji: {emoji_count}")

if svg_count == len(nav_icons) and emoji_count == 0:
    print("  OK: All sidebar icons use SVG")
else:
    print(f"  WARNING: {len(nav_icons) - svg_count} nav icons still use non-SVG content")

# Check for report card icons
report_icons = re.findall(r'class="report-icon">(.*?)</div>', html, re.DOTALL)
svg_report = sum(1 for icon in report_icons if '<svg' in icon)
print(f"\n  Report card icons: {len(report_icons)} total, {svg_report} with SVG")

print(f"\n{'='*60}")
print(f"TOTAL ISSUES: {total_issues}")
if total_issues == 0:
    print("ALL CHECKS PASSED - Encoding fixes are complete!")
else:
    print(f"WARNING: {total_issues} issues need attention")
print("=" * 60)
