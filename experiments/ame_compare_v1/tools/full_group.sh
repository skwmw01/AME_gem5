#!/bin/bash
set -eu
compare_group=$1
for limits in '0 166' '226 256' '256 316' '316 376' '376 436' '436 496' '496 676' '676 816' '816 956' '956 1096' '1096 1176' '1176 1236'; do
 read -r first last <<< "$limits"
 python3 experiments/ame_compare_v1/tools/run.py run --group "$compare_group" --start "$first" --end "$last" --trace --tag formal
 done
python3 experiments/ame_compare_v1/tools/run.py run --group "$compare_group" --start 166 --end 226 --trace --control --tag formal-control
for id in 43 103 163; do
 for trial in 1 2 3; do
  python3 experiments/ame_compare_v1/tools/run.py run --group "$compare_group" --start "$id" --end "$((id+1))" --trace --tag "formal-repeat-$id-$trial"
 done
done
