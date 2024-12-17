#!/bin/zsh
cat <(wc -l generated.xsd | sed 's/ .*//')  <(wc -l small_comp_docs.txt | sed 's/ .*//') | paste -d' ' - - | awk '{print $1 / $2}'
