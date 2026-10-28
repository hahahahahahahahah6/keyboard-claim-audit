# keyboard-claim-audit

Version 0.1.0. Offline static audit of documented synthetic key input against
provider-resolved Python AST calls. Source is parsed, never executed.

Install and run:

```sh
python3 -m pip install .
keyboard-claim-audit /path/to/project
python3 -m keyboard_claim_audit /path/to/project --json
python3 -m unittest discover
python3 -m build
```

The positional root defaults to the current directory. Options: `--json` emits
valid JSON; `--verbose` lists evidence paths; repeatable `--ignore GLOB` excludes
relative paths; `--fail-on HIGH` is the default; `--fail-on MEDIUM` also fails
on test-only evidence; `--version` prints 0.1.0. Usage errors exit 1.
PASS exits 0; FAIL exits 2. Findings contain rule, severity, and message.
A positive assertion without production evidence produces the HIGH rule
`documented-keyboard-claim-false`; test-only evidence lowers it to MEDIUM.
A negative assertion contradicted by production evidence produces the HIGH rule
`documented-no-keyboard-claim-false`. Each family produces at most one finding.

## Limitations

Only the fixed phrase vocabulary encoded in the source constitutes a claim.
Bare nouns, user-facing shortcuts, instructions for the user to press a key,
and descriptions of mouse actions, screen capture, clipboard, voice, or network
activity are outside scope. The audited capability is synthetic key input.
Root README.md and Markdown beneath any docs path component supply assertions.
Fenced blocks are excluded; inline code counts. Case, hyphens, contractions,
and whitespace are normalized within blank-line-separated paragraphs.

Evidence requires recognized calls from pyautogui, pynput.keyboard Controller
instances, or the keyboard library. Imports, listeners, strings, and user prompts
alone provide no evidence. Controller bindings must occur in the same module.
Shell key helpers such as xdotool and xte are outside scope. Static analysis
cannot establish runtime reachability or successful delivery, and does not model
rebinding or dynamic imports. Invalid syntax provides no evidence.
Tests can supply only MEDIUM evidence. Fixtures, docs, examples, and symlinked
files are excluded from source evidence. Files named .env are never read.
A positive assertion without source fails; a negative assertion without source
passes. No assertion passes regardless of source evidence.
