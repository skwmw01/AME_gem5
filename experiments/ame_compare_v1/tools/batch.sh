#!/bin/bash
set -eu
python3 experiments/ame_compare_v1/tools/build.py
python3 experiments/ame_compare_v1/tools/run.py run --end 31 --trace --tag calibration-final
for range in '226 227' '246 247' '256 257' '376 377' '676 677' '816 817' '956 957' '1096 1097' '1136 1137' '1176 1177'; do
 read -r first last <<< "$range"
 python3 experiments/ame_compare_v1/tools/run.py run --start "$first" --end "$last" --trace --tag smoke
 done
