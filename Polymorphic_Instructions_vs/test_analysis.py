"""Regression checks for measurement failures, independent of gem5 runtime."""
import copy
import gzip
from pathlib import Path
import struct
import tempfile
import unittest

import analyze


class MeasurementFailures(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)

    def guest_file(self):
        header = struct.pack('<8Q', 0x5a54545049303601, 1, 672, 1, 1, 4, 32, 0)
        records = []
        golden = analyze.reference()['C_R1']
        for seq in range(7):
            for call in range(96):
                kind = seq if seq < 3 else (call // (1, 4, 16, 32)[seq - 3]) % 3
                bits = [(struct.unpack('<I', struct.pack('<f', v))[0] if kind == 0
                         else v & 0xffffffff) for v in golden]
                records.append(struct.pack('<3Q16I', 100, 150, 0, *bits))
        data = bytearray(header + b''.join(records))
        path = self.path / 'results.bin'
        path.write_bytes(data)
        return path, data

    def test_corrupt_output_element_is_rejected(self):
        path, data = self.guest_file()
        self.assertEqual(len(analyze.read_results(path, 'smoke')), 672)
        data[64 + 24 + 15 * 4] ^= 1  # last output, not a sampled prefix
        path.write_bytes(data)
        with self.assertRaisesRegex(ValueError, 'element mismatch'):
            analyze.read_results(path, 'smoke')

    def test_truncated_results_are_rejected(self):
        path, data = self.guest_file()
        path.write_bytes(data[:-1])
        with self.assertRaisesRegex(ValueError, 'truncated'):
            analyze.read_results(path, 'smoke')

    def trace(self, lines):
        path = self.path / 'trace.gz'
        with gzip.open(path, 'wt') as f:
            for pc, flags in lines:
                f.write(f'1: system.cpu: 0x{pc:x} : op : flags=({flags})\n')
        return path

    def parse(self, lines):
        return analyze.parse_trace(self.trace(lines), 'shared',
                                   {0x104: {'mnemonic': 'mmulacc.2d'}},
                                   {'measure_shared_begin': (0x100, 0),
                                    'measure_shared_end': (0x108, 0)},
                                   {0x100: 'auxiliary', 0x104: 'compute'})

    def test_microops_count_as_one_architectural_instruction(self):
        rows = self.parse([(0x100, 'IsInteger'),
                           (0x104, 'IsMicroop|IsFirstMicroop'),
                           (0x104, 'IsMicroop'),
                           (0x104, 'IsMicroop|IsLastMicroop'),
                           (0x108, 'IsInteger')])
        self.assertEqual(rows[0]['raw_architectural'], 2)
        self.assertEqual(rows[0]['counts']['compute'], 1)
        self.assertEqual(rows[0]['microop_records'], 3)

    def test_unknown_pc_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'unclassified'):
            self.parse([(0x100, 'IsInteger'), (0x200, 'IsInteger')])

    def test_missing_end_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'unterminated'):
            self.parse([(0x100, 'IsInteger'), (0x104, 'IsMatrix')])

    def test_counter_mismatch_is_rejected(self):
        interval = self.parse([(0x100, 'IsInteger'), (0x104, 'IsMatrix'),
                               (0x108, 'IsInteger')])[0]
        with self.assertRaisesRegex(ValueError, 'reconciliation'):
            analyze.verify_call({'index': 0, 'instret_before': 100,
                                 'instret_after': 103}, copy.deepcopy(interval))


if __name__ == '__main__':
    unittest.main()
