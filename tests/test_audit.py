"""Required cases 1–29 below; generated phrase tests exhaust both families (case 30)."""
import contextlib
import io
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from keyboard_claim_audit.audit import audit, claims, evidence, KEYBOARD, NOKEYBOARD, normalize, pattern
from keyboard_claim_audit.__main__ import main

ROOT = Path(__file__).resolve().parents[1]
GOOD = 'import pyautogui\npyautogui.press("a")'

class AuditTests(unittest.TestCase):
    def run_case(self, source='', doc='sends keystrokes', path='app.py', **kwargs):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'README.md').write_text(doc)
            if source:
                target = root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(source)
            return audit(root, **kwargs)

    def good(self, source):
        result = self.run_case(source)
        self.assertEqual(result['verdict'], 'PASS')
        self.assertEqual(result['findings'], [])
        self.assertTrue(result['evidence'])

    def bad(self, source):
        result = self.run_case(source)
        self.assertEqual(result['verdict'], 'FAIL')
        self.assertEqual([(f['rule'], f['severity']) for f in result['findings']], [('documented-keyboard-claim-false', 'HIGH')])

    def test_01_plain(self): self.good(GOOD)
    def test_02_alias(self): self.good('import pyautogui as pg\npg.typewrite("a")')
    def test_03_from_alias(self): self.good('from pyautogui import hotkey as hk\nhk("a")')
    def test_04_bound(self): self.good('from pynput.keyboard import Controller\nctl = Controller()\nctl.press("a")')
    def test_05_self(self): self.good('from pynput.keyboard import Controller\nclass A:\n def f(self):\n  self.ctl = Controller()\n  self.ctl.type("a")')
    def test_06_keyboard(self): self.good('import keyboard\nkeyboard.send("a")')
    def test_07_keyboard_from(self): self.good('from keyboard import write\nwrite("a")')
    def test_08_up_down(self): self.good('import pyautogui\npyautogui.keyDown("a")\npyautogui.keyUp("a")')
    def test_09_import(self):
        for source in ['import pyautogui', 'import keyboard', 'from pynput.keyboard import Controller']:
            self.bad(source)
    def test_10_string(self): self.bad('value = "keystroke"')
    def test_11_mouse(self): self.bad('import pyautogui\npyautogui.click()\npyautogui.moveTo(1,2)')
    def test_12_screenshot(self): self.bad('import pyautogui\npyautogui.screenshot()')
    def test_13_input(self): self.bad('input("key")')
    def test_14_listener(self): self.bad('from pynput.keyboard import Listener\nx=Listener()\nx.start()\nwidget.bind("a", callback)')
    def test_15_hotkey(self):
        for method in ['add_hotkey', 'on_press', 'on_release', 'wait', 'is_pressed', 'read_key']:
            self.bad('import keyboard\nkeyboard.' + method + '()')
    def test_16_unbound(self): self.bad('from pynput.keyboard import Controller\nctl.press("a")')
    def test_17_negative(self):
        result = self.run_case(GOOD, 'no keyboard automation')
        self.assertEqual([(f['rule'], f['severity']) for f in result['findings']], [('documented-no-keyboard-claim-false', 'HIGH')])
        self.assertEqual(result['verdict'], 'FAIL')
    def test_18_no_claim(self): self.assertEqual(self.run_case(GOOD, 'Hello')['findings'], [])
    def test_19_noun(self): self.assertEqual(self.run_case('import pyautogui', 'the keyboard chapter explains delivery')['findings'], [])
    def test_20_shortcuts(self): self.assertEqual(self.run_case(GOOD, 'supports keyboard shortcuts')['findings'], [])
    def test_21_user(self): self.assertEqual(self.run_case('import pyautogui', 'press any key to continue')['findings'], [])
    def test_22_no_source(self):
        self.bad('')
        self.assertEqual(self.run_case('', 'no keyboard automation')['findings'], [])
    def test_23_test_only(self):
        for path in ['tests/app.py', 'test_app.py', 'app_test.py']:
            result = self.run_case(GOOD, path=path)
            self.assertEqual(result['findings'][0]['severity'], 'MEDIUM')
            self.assertEqual(result['verdict'], 'PASS')
            self.assertEqual(self.run_case(GOOD, path=path, fail_on='MEDIUM')['verdict'], 'FAIL')
    def test_24_fence_inline(self):
        self.assertEqual(self.run_case('', '```text\nsends keystrokes\n```')['findings'], [])
        self.assertEqual(self.run_case('', '`sends keystrokes`')['verdict'], 'FAIL')
    def test_25_span(self): self.assertEqual(claims('does not send keystrokes'), (False, True))
    def test_26_self(self):
        result = audit(ROOT)
        self.assertEqual(result['verdict'], 'PASS')
        self.assertEqual(result['claims'], dict(positive=False, negative=False))
        text = normalize((ROOT / 'README.md').read_text())
        self.assertIsNone(pattern(KEYBOARD + NOKEYBOARD).search(text))
        self.assertIsNone(re.search(r'\b(using|uses|with|via|over|supports|sends|send) keyboard claim audit\b', text))
    def cli(self, args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output): code = main(args)
        return code, output.getvalue()
    def test_27_cli(self):
        code, out = self.cli([str(ROOT / 'tests/fixtures/bad'), '--json'])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(out)['verdict'], 'FAIL')
        code, out = self.cli([str(ROOT / 'tests/fixtures/good'), '--verbose'])
        self.assertEqual(code, 0)
        self.assertIn('app.py', out)
        self.assertEqual(self.cli([str(ROOT / 'tests/fixtures/bad'), '--ignore', 'README.md'])[0], 0)
        self.assertEqual(self.cli(['/nonexistent-audit-root'])[0], 1)
        with contextlib.redirect_stdout(io.StringIO()) as out:
            with self.assertRaises(SystemExit) as raised: main(['--version'])
        self.assertEqual(raised.exception.code, 0)
        self.assertEqual(out.getvalue().strip(), '0.1.0')
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised: main(['--invalid'])
        self.assertEqual(raised.exception.code, 1)
    def test_28_env(self):
        original = io.open
        opened = []
        def guarded(file, *args, **kwargs):
            opened.append(str(file))
            self.assertNotEqual(Path(file).name, '.env')
            return original(file, *args, **kwargs)
        with patch('io.open', guarded): audit(ROOT / 'tests/fixtures')
        self.assertFalse(any(Path(p).name == '.env' for p in opened))
    def test_29_packaging(self):
        for path in list((ROOT / 'keyboard_claim_audit').glob('*.py')) + list((ROOT / 'tests').glob('*.py')) + [ROOT/'README.md', ROOT/'pyproject.toml']:
            self.assertIsNone(re.search(r'(?<![\w-])py' + r'thon(?![\w-])', path.read_text()), str(path))
        project = (ROOT/'pyproject.toml').read_text()
        self.assertIn('setuptools>=77', project)
        self.assertIn('license = "MIT"', project)
        self.assertIn('recursive-include tests', (ROOT/'MANIFEST.in').read_text())
    def test_provider_edges(self):
        for source in ['from pynput import keyboard\nkeyboard.Controller().press("a")', 'import pynput.keyboard as kb\nc=kb.Controller()\nc.release("a")', 'import pynput.keyboard\npynput.keyboard.Controller().type("a")', 'from pynput.keyboard import Controller as C\nC().press("a")', 'import keyboard as kbd\nkbd.release("a")', 'from keyboard import send as s\ns("a")', 'from pyautogui.sub import press as p\np("a")']:
            self.good(source)
        for source in ['import pynput\npynput.keyboard.Controller().press("a")', 'from other import press\npress("a")', 'def key_action():\n print("a")', '@app.get("/")\ndef f():\n return "a"', 'import subprocess\nsubprocess.run(["xdotool", "key", "a"])']:
            self.bad(source)
    def test_scope(self):
        for path in ['docs/app.py', 'fixtures/app.py', 'examples/app.py']:
            self.assertEqual(self.run_case(GOOD, path=path)['findings'][0]['severity'], 'HIGH')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'README.md').write_text('sends keystrokes')
            (root/'app.py').symlink_to(ROOT/'tests/fixtures/good/app.py')
            self.assertEqual(audit(root)['verdict'], 'FAIL')
            (root/'docs').mkdir()
            (root/'docs/a.md').write_text('no keyboard automation')
            (root/'app.py').unlink()
            (root/'app.py').write_text(GOOD)
            self.assertEqual(audit(root)['findings'][0]['severity'], 'HIGH')
            self.assertEqual(audit(root, ['docs/*'])['verdict'], 'PASS')
    def test_normalization(self):
        self.assertEqual(claims('SENDS-\nKEYSTROKES'), (True, False))
        self.assertEqual(claims("doesn't send keystrokes"), (False, True))
        self.assertEqual(claims('sends\n\nkeystrokes'), (False, False))
        self.assertEqual(claims('xsends keystrokesx'), (False, False))
    def test_module_pairing(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'README.md').write_text('sends keystrokes')
            (root/'a.py').write_text('from pynput.keyboard import Controller\nc=Controller()')
            (root/'b.py').write_text('c.press("a")')
            self.assertEqual(audit(root)['verdict'], 'FAIL')

# Each generated test covers precisely the corresponding constant's phrase.
def phrase_test(phrase, negative):
    def test(self):
        self.assertEqual(claims(phrase), (not negative, negative))
        result = self.run_case(GOOD if negative else '', phrase)
        self.assertEqual(result['verdict'], 'FAIL')
        self.assertEqual(len(result['findings']), 1)
        self.assertEqual(result['findings'][0]['severity'], 'HIGH')
        self.assertEqual(result['findings'][0]['rule'], 'documented-no-keyboard-claim-false' if negative else 'documented-keyboard-claim-false')
    return test
for family, phrases, negative in [('positive', KEYBOARD, False), ('negative', NOKEYBOARD, True)]:
    for index, phrase in enumerate(phrases):
        setattr(AuditTests, 'test_phrase_%s_%02d' % (family, index), phrase_test(phrase, negative))
