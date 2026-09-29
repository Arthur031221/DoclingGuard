Output demo/demo.gif
Set FontSize 18
Set Width 1100
Set Height 540
Set Theme "Dracula"

Type "ROOT=$(.venv/bin/docling-guard demo)"
Enter
Sleep 1s
Type ".venv/bin/docling-guard compare $ROOT/before.json $ROOT/after.json --fail-on-drop"
Enter
Sleep 3s
