#!/bin/zsh
# Abre ContaXcell desde el código con doble clic en el Finder. Hace falta el
# Python de Homebrew con su tkinter: brew install python@3.14 python-tk@3.14
set -eu
cd -- "${0:A:h}/escritorio"
for python in .venv/bin/python /opt/homebrew/bin/python3.14 /usr/local/bin/python3.14; do
  if [[ -x $python ]]; then
    exec $python ejecutar.py
  fi
done
print 'Falta Python 3.14 con tkinter. Instálalo con:'
print '    brew install python@3.14 python-tk@3.14'
read '?Pulsa Intro para cerrar.'
exit 1
