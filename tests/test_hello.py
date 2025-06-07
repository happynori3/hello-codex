import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from hello import main

def test_main(capsys):
    main()
    captured = capsys.readouterr()
    assert captured.out.strip() == "hello codex"
