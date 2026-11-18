import pathlib
import re

PATTERN = re.compile(r"url_for\(\s*['\"]([\w.]+)['\"]")


def test_every_url_for_points_to_a_real_endpoint(app):
    root = pathlib.Path(app.root_path)
    missing = set()
    for f in list(root.rglob("*.html")) + list(root.rglob("*.py")):
        for ep in PATTERN.findall(f.read_text(encoding="utf-8")):
            if ep == "static" or ep.endswith("_"):      # 'auth.sign_in_' ~ role is built at run time
                continue
            if ep not in app.view_functions:
                missing.add((f.name, ep))
    assert not missing, sorted(missing)