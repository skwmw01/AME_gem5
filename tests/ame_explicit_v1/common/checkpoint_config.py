"""Run the unchanged example machine; snapshot on genuine m5 checkpoint exits."""
import os
from pathlib import Path

source_path = Path(__file__).resolve().parents[3] / 'example/ame_config.py'
source = source_path.read_text()
source = source.replace('m5.instantiate()', 'm5.instantiate(os.environ.get("AME_RESTORE"))')
source = source.replace('exit_event = m5.simulate()', '''
checkpoint_index = 0
exit_event = m5.simulate()
while exit_event.getCause() == 'checkpoint':
    destination = os.environ['AME_CHECKPOINT_ROOT'] + '/' + str(checkpoint_index)
    m5.checkpoint(destination)
    checkpoint_index += 1
    if os.environ.get('AME_STOP_AFTER_CHECKPOINT') == '1':
        sys.exit(0)
    exit_event = m5.simulate()
''')
exec(compile(source, str(source_path), 'exec'))
