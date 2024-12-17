#!/bin/zsh
cat <(wc -c generated.xsd | sed 's/ .*//')  <(wc -c small_comp_docs.txt | sed 's/ .*//') | paste -d' ' - - | awk '{print $1 / $2}'
