"""Diagnostic only: frozen B11 protobuf enum rejects Matrix opclasses.
Not used in formal results; retained to reproduce the documented failure.
"""
from pathlib import Path
source_path = Path(__file__).resolve().parents[3] / 'example/ame_config.py'
source = source_path.read_text().replace('m5.instantiate()', '''
from m5.objects import InstPBTrace
system.cpu.tracer = InstPBTrace(file_name="trace.pb.gz")
m5.instantiate()
''')
exec(compile(source,str(source_path),'exec'))
