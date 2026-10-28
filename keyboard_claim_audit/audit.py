import ast
import fnmatch
import re
from pathlib import Path

KEYBOARD = (
    "automates keyboard input", "automate keyboard input", "simulates keyboard input",
    "simulate keyboard input", "keyboard input automation", "presses keys automatically",
    "press keys automatically", "types keys automatically", "type keys automatically",
    "sends keystrokes", "send keystrokes", "simulates keystrokes", "simulate keystrokes",
    "injects keystrokes", "inject keystrokes", "emulates keystrokes", "emulate keystrokes",
    "keystroke simulation", "keystroke automation", "simulated keystrokes",
    "automated keystrokes", "keyboard automation", "keyboard injection",
)
NOKEYBOARD = (
    "does not send keystrokes", "does not simulate keystrokes",
    "does not automate keyboard input", "does not simulate keyboard input",
    "does not inject keystrokes", "keyboard automation not supported",
    "keystroke simulation not supported", "no keyboard automation",
    "no keystroke simulation", "without keyboard automation",
    "without keystroke simulation", "no keyboard injection",
)

def normalize(text):
    return re.sub(r"\s+", " ", text.lower().replace("n't", " not").replace("-", " ")).strip()

def pattern(phrases):
    return re.compile(r"\b(?:" + "|".join(re.escape(p) for p in sorted(phrases, key=len, reverse=True)) + r")\b")

def claims(text):
    lines = []
    fence = None
    for line in text.splitlines():
        match = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if match:
            token = match.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            continue
        if fence is None:
            lines.append(line)
    positive = negative = False
    for para in re.split(r"\n\s*\n", "\n".join(lines)):
        para = normalize(para)
        negative |= bool(pattern(NOKEYBOARD).search(para))
        positive |= bool(pattern(KEYBOARD).search(pattern(NOKEYBOARD).sub(" ", para)))
    return positive, negative

def dotted(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = dotted(node.value)
        return base + "." + node.attr if base else ""
    return ""

def evidence(text):
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return False
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name == "pyautogui" or a.name.startswith("pyautogui.") or a.name in ("keyboard", "pynput.keyboard") or a.name.startswith("pynput.keyboard."):
                    aliases[a.asname or a.name.split('.')[0]] = a.name if a.asname else a.name.split('.')[0]
        elif isinstance(node, ast.ImportFrom) and node.module:
            m = node.module
            if m == "pyautogui" or m.startswith("pyautogui.") or m == "keyboard" or m == "pynput.keyboard" or m.startswith("pynput.keyboard.") or m == "pynput":
                for a in node.names:
                    if m != "pynput" or a.name == "keyboard":
                        aliases[a.asname or a.name] = m + "." + a.name
    def resolve(node):
        path = dotted(node)
        head, sep, tail = path.partition('.')
        return aliases.get(head, "") + (sep + tail if sep else "") if head in aliases else ""
    def controller(node):
        if not isinstance(node, ast.Call):
            return False
        path = resolve(node.func)
        return path.startswith("pynput.keyboard.") and path.endswith(".Controller")
    bound = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and controller(node.value):
            for target in node.targets:
                if isinstance(target, ast.Name) or (isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self"):
                    bound.add(dotted(target))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        path = resolve(node.func)
        method = path.rsplit('.', 1)[-1]
        if path.startswith("pyautogui.") and method in {"press", "hotkey", "typewrite", "write", "keyDown", "keyUp"}:
            return True
        if path.startswith("keyboard.") and path.count('.') == 1 and method in {"press", "release", "send", "write"}:
            return True
        if isinstance(node.func, ast.Attribute) and node.func.attr in {"press", "release", "type"}:
            receiver = node.func.value
            if (dotted(receiver) and dotted(receiver) in bound) or controller(receiver):
                return True
    return False

def audit(root, ignore=(), fail_on="HIGH"):
    root = Path(root)
    if not root.is_dir():
        raise ValueError("root must be a readable directory")
    if not root.stat().st_mode & 0o444:
        raise ValueError("root must be a readable directory")
    pos = neg = False
    prod, tests = [], []
    for path in sorted(root.rglob('*')):
        rel = path.relative_to(root)
        if path.is_symlink() or any(p.is_symlink() for p in path.parents if p != root) or not path.is_file():
            continue
        if any(fnmatch.fnmatch(rel.as_posix(), g) for g in ignore):
            continue
        parts = rel.parts
        if rel.as_posix() == 'README.md' or ('docs' in parts[:-1] and path.suffix.lower() == '.md'):
            p, n = claims(path.read_text(encoding='utf-8'))
            pos |= p
            neg |= n
        if path.suffix != '.py':
            continue
        if any(p in {'fixtures', 'docs', 'examples'} for p in parts[:-1]):
            continue
        is_test = 'tests' in parts[:-1] or path.name.startswith('test_') or path.name.endswith('_test.py')
        if evidence(path.read_text(encoding='utf-8')):
            (tests if is_test else prod).append(rel.as_posix())
    findings = []
    if pos and not prod:
        findings.append(dict(rule='documented-keyboard-claim-false', severity='MEDIUM' if tests else 'HIGH', message='Documented synthetic key input lacks production evidence.'))
    if neg and prod:
        findings.append(dict(rule='documented-no-keyboard-claim-false', severity='HIGH', message='Documented absence conflicts with production synthetic key input.'))
    failed = any(f['severity'] == 'HIGH' or fail_on == 'MEDIUM' for f in findings)
    return dict(verdict='FAIL' if failed else 'PASS', findings=findings, claims=dict(positive=pos, negative=neg), evidence=prod, test_evidence=tests)
